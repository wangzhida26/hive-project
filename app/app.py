"""云购生活 · 智能经营问答（Streamlit + NL2SQL 闭环）

提问 → 引擎生成 SQL（护栏校验）→ 执行 Hive/MySQL → 结果表格 + 自动图表渲染。

运行：
  宿主机：streamlit run app/app.py            （NL2SQL_BACKEND=hive，docker exec beeline）
  容器内：docker compose up -d app            （NL2SQL_BACKEND=mysql，查报表镜像库）
"""
import os
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "nl2sql"))
from nl2sql_core import NL2SQL, run_query  # noqa: E402

st.set_page_config(page_title="云购生活 · 智能经营问答", page_icon="🛒", layout="wide")

BACKEND = os.environ.get("NL2SQL_BACKEND", "hive")


# ---------- NL2SQL 执行器（按 NL2SQL_BACKEND 分派，引擎内部自动选择 beeline/pymysql） ----------
def execute_sql(sql: str):
    return run_query(sql)


@st.cache_resource(show_spinner=False)
def get_engine() -> NL2SQL:
    return NL2SQL()


# ---------- 会话状态 ----------
if "history" not in st.session_state:
    st.session_state.history = []          # [(question, engine, sql, result)]
if "log" not in st.session_state:
    st.session_state.log = []              # 侧边栏消息


# ---------- 侧边栏 ----------
with st.sidebar:
    st.title("🛒 云购生活")
    st.caption("数据仓库 NL2SQL 智能问答（第 3 周引擎 + 第 4 周界面）")
    st.markdown(
        f"**后端**：`{BACKEND}`\n\n"
        f"**引擎**：{get_engine().status()}"
    )

    st.subheader("💬 示例问题")
    examples = [
        "整体经营大盘怎么样",
        "最近一个月 GMV 趋势如何",
        "卖得最好的品类是哪个",
        "浙江和广东哪个省卖得好",
        "销售额最高的门店排名",
        "各支付方式占比",
    ]
    for e in examples:
        if st.button(e, use_container_width=True, key=f"ex-{e}"):
            st.session_state.pending = e

    if st.button("🗑️ 清空对话历史", use_container_width=True):
        st.session_state.history = []
        st.session_state.log = []
        st.rerun()


# ---------- 主界面 ----------
st.title("云购生活 · 智能经营问答")
st.caption("提问 → 自动生成 SQL（护栏校验）→ 执行 → 表格与图表渲染")

q = st.chat_input("请输入你的问题，例如：广东省上月销售额是多少？")
if st.session_state.get("pending"):
    q, st.session_state.pending = st.session_state.pop("pending"), None

if q:
    t0 = time.time()
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant"):
        with st.spinner("🤔 正在理解问题并生成 SQL …"):
            try:
                ans = get_engine().ask(q, verbose=False)
            except Exception as exc:
                st.error(f"查询链路异常：{exc}")
                ans = None
        if ans is None:
            st.session_state.log.append((q, "ERROR", "", None))
        else:
            badge = "🧠 LLM 引擎" if ans.engine == "LLM" else "📏 规则引擎"
            if ans.fallback_note:
                st.info(f"{badge} · {ans.fallback_note}")
            else:
                st.markdown(f"`{badge}`")
            st.code(ans.sql.strip(), language="sql")

            res = ans.result
            if not res.ok:
                st.error(f"❌ SQL 执行失败：{res.error}")
            elif not res.rows:
                st.warning("查询成功但没有返回数据。")
            else:
                df = pd.DataFrame(res.rows, columns=res.columns)
                st.dataframe(df.head(50), use_container_width=True)
                if len(res.rows) > 50:
                    st.caption(f"共 {len(res.rows)} 行，仅展示前 50 行")
                render_auto_chart(df)
                st.caption(f"⏱ 执行耗时 {res.elapsed:.2f}s")

            st.session_state.history.append((q, ans.engine, ans.sql, res))
            st.session_state.log.append((q, ans.engine, ans.sql, res.ok))

# ---------- 历史对话 ----------
if st.session_state.history:
    st.divider()
    st.subheader("🕘 历史对话")
    for i, (hq, heng, hsql, hres) in enumerate(reversed(st.session_state.history[:-1]), 1):
        with st.expander(f"{i}. {hq}（{heng} 引擎）"):
            st.code(hsql.strip(), language="sql")
            if hres.ok:
                st.markdown(hres.to_markdown(8))
            else:
                st.error(hres.error)


# ---------- 自动图表推荐 ----------
def render_auto_chart(df: pd.DataFrame):
    """识别列语义，2 列以上数值型数据自动选图。"""
    num_cols = [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().all()
                and df[c].nunique() > 3]
    cat_cols = [c for c in df.columns if c not in num_cols]
    if not num_cols or len(df) < 2:
        return

    y = num_cols[0]
    try:
        import plotly.express as px

        # 日期列 + 数值列 → 折线
        date_col = next((c for c in cat_cols if _is_date(df[c])), None)
        if date_col:
            fig = px.line(df, x=date_col, y=y, markers=True)
            fig.update_layout(height=380, template="plotly_dark",
                              title=f"{y} 随 {date_col} 趋势")
            st.plotly_chart(fig, use_container_width=True)
            return

        # 类别列 + 数值列 → 条形（≤20 行）或 饼图（占比 ≤6 行）
        if cat_cols and len(df) <= 6:
            fig = px.pie(df, names=cat_cols[0], values=y, hole=0.45)
            fig.update_layout(height=380, template="plotly_dark",
                              title=f"{y} 构成（{cat_cols[0]}）")
            st.plotly_chart(fig, use_container_width=True)
        elif cat_cols:
            d = df.head(15)
            fig = px.bar(d, x=cat_cols[0], y=y)
            fig.update_layout(height=380, template="plotly_dark",
                              title=f"{y}（按 {cat_cols[0]}，Top 15）")
            st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass  # 图表渲染失败不影响表格展示


def _is_date(s: pd.Series) -> bool:
    try:
        pd.to_datetime(s.head(5))
        return s.head(5).astype(str).str.match(r"^\d{4}-\d{2}-\d{2}").all()
    except Exception:
        return False
