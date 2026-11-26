"""云购生活 · 智能经营问答（Streamlit + NL2SQL + 图表引擎）

链路：提问 → 引擎生成 SQL（护栏校验）→ 执行 Hive/MySQL → 结构化结果 → 意图感知选图 → 图表/指标卡

运行：
  宿主机：NL2SQL_BACKEND=hive streamlit run app/app.py
  容器内：docker compose up -d app        （NL2SQL_BACKEND=mysql，查报表镜像库）
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(APP_DIR.parent / "nl2sql"))

import chart_engine as ce  # noqa: E402
from nl2sql_core import NL2SQL  # noqa: E402

BACKEND = os.environ.get("NL2SQL_BACKEND", "hive")

KIND_LABEL = {
    "kpi": "指标卡", "line": "折线", "bar_v": "柱状",
    "bar_h": "条形", "donut": "环形", "map": "地图",
    "grouped": "分组柱", "table": "表格",
}
MANUAL = {
    "自动（推荐）": None, "折线": "line", "柱状": "bar_v", "条形": "bar_h",
    "环形": "donut", "地图": "map", "分组柱": "grouped", "仅表格": "table",
}

st.set_page_config(page_title="云购生活 · 智能经营问答", page_icon="🛒", layout="wide")

CSS = """
<style>
  .block-container { padding-top: 2.2rem; max-width: 1180px; }
  .q-head { font-size: 13px; color: #6B7C93; letter-spacing: .04em; }
  .why {
    display: inline-block; font-size: 12.5px; color: #2A4A78; background: #EDF3FC;
    border-left: 3px solid #1E4FA8; padding: 6px 12px; border-radius: 0 6px 6px 0;
    margin: 2px 0 10px 0;
  }
  .insight { font-size: 13px; color: #3D5064; margin-top: -6px; }
  div[data-testid="stMetric"] {
    background: #F7F9FD; border: 1px solid #E3EAF5; border-radius: 10px;
    padding: 14px 18px;
  }
  div[data-testid="stMetricValue"] { color: #1E4FA8; font-weight: 700; }
</style>
"""


@st.cache_resource(show_spinner=False)
def get_engine() -> NL2SQL:
    return NL2SQL()


def engine_status() -> str:
    try:
        return get_engine().status()
    except Exception as exc:
        return f"未就绪（{exc}）"


# ---------------------------------------------------------------------------
# 渲染：指标卡
# ---------------------------------------------------------------------------
def kpi_value(col: str, v) -> str:
    """比率类指标按百分数展示：0.0542 → 5.42%，15.33 已经是百分数则原样加 %。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if re.search(r"rate|pct|share|率|占比", str(col), re.I):
        return f"{f * 100:.2f}%" if 0 <= f <= 1.5 else f"{f:.2f}%"
    return ce.fmt_num(f)


def render_kpi(df: pd.DataFrame):
    nums = ce.numeric_cols(df)
    if not nums:
        return
    for start in range(0, min(len(nums), 8), 4):     # 超过 4 个指标换行，不硬挤
        chunk = nums[start:start + 4]
        cols = st.columns(len(chunk))
        for i, c in enumerate(chunk):
            cols[i].metric(label=str(c), value=kpi_value(c, df.iloc[0][c]))


# ---------------------------------------------------------------------------
# 渲染：图表区
# ---------------------------------------------------------------------------
def render_result(df: pd.DataFrame, question: str, sql: str, key: str):
    spec = ce.infer(df, question, sql)

    if spec.kind == "kpi":
        render_kpi(df)
    else:
        _, right = st.columns([3, 1.15])
        with right:
            pick = st.selectbox("图表类型", list(MANUAL.keys()), index=0, key=f"kind-{key}")
        kind = MANUAL[pick]
        if kind:
            spec = ce.ChartSpec(kind=kind, x=spec.x, y=spec.y, series=spec.series,
                                title=spec.title, reason=spec.reason)
        if spec.kind != "table":
            st.markdown(f'<div class="why">📊 自动选择 <b>{KIND_LABEL.get(spec.kind, spec.kind)}</b>'
                        f' · {spec.reason}</div>', unsafe_allow_html=True)
            fig = ce.build_figure(spec, df)
            if fig is not None:
                st.plotly_chart(fig, width="stretch", theme=None,
                                config={"displayModeBar": False, "responsive": True})
        note = ce.caption(spec, df)
        if note:
            st.markdown(f'<div class="insight">🔎 {note}</div>', unsafe_allow_html=True)

    with st.expander(f"📋 数据明细（{len(df)} 行）", expanded=(spec.kind in ("kpi", "table"))):
        show = df.copy()
        for c in show.columns:
            if pd.api.types.is_datetime64_any_dtype(show[c]):
                show[c] = show[c].dt.strftime("%Y-%m-%d")
        st.dataframe(show, width="stretch", hide_index=True, height=min(420, 38 + 35 * len(show)))
        st.download_button(
            "⬇️ 下载 CSV", data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"query_{time.strftime('%H%M%S')}.csv", mime="text/csv",
            key=f"dl-{key}",
        )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    st.markdown(CSS, unsafe_allow_html=True)

    if "history" not in st.session_state:
        st.session_state.history = []       # [(question, engine, sql, df)]
    if "turn" not in st.session_state:
        st.session_state.turn = 0

    # ---------------- 侧边栏 ----------------
    with st.sidebar:
        st.title("🛒 云购生活")
        st.caption("数据仓库 NL2SQL 智能问答 · 第 3 周引擎 + 第 4 周界面")

        st.markdown(f"**查询后端** `{BACKEND}`  \n**引擎** {engine_status()}")

        st.subheader("💬 试试这些")
        examples = [
            "整体经营大盘怎么样",
            "最近一个月 GMV 趋势如何",
            "各省份销售额排名",
            "各支付方式占比",
            "卖得最好的品类是哪个",
            "销售额最高的门店排名",
            "各渠道各品类的销售额对比",
        ]
        for e in examples:
            if st.button(e, key=f"ex-{e}", width="stretch"):
                st.session_state.pending = e

        st.divider()
        st.caption("**图表怎么来的**\n\n先看结果集形状（几行几列、有没有日期/省份），"
                   "再看问题意图（趋势/排名/占比），两者决定图形。可手动改。")
        if st.button("🗑️ 清空对话", width="stretch"):
            st.session_state.history = []
            st.session_state.turn = 0
            st.rerun()

    # ---------------- 主区 ----------------
    st.markdown('<div class="q-head">智能经营问答 · NL2SQL</div>', unsafe_allow_html=True)
    st.title("问一句话，出 SQL、出图、出结论")
    st.caption("读的是 ADS 汇总层，不是明细表 —— 所以和 Superset、数据大屏是同一个数。")

    if not st.session_state.history:
        c1, c2, c3 = st.columns(3)
        c1.info("**① 问**\n\n自然语言提问，如「各省份销售额排名」")
        c2.info("**② 译**\n\n双引擎生成 SQL，只读护栏校验")
        c3.info("**③ 画**\n\n按结果形状自动选折线/地图/环形/指标卡")

    q = st.chat_input("请输入你的问题，例如：广东省上月销售额是多少？")
    if st.session_state.get("pending"):
        q, st.session_state.pending = st.session_state.pop("pending"), None

    if q:
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            t0 = time.time()
            with st.spinner("正在理解问题并生成 SQL …"):
                try:
                    ans = get_engine().ask(q, verbose=False)
                except Exception as exc:
                    st.error(f"查询链路异常：{exc}")
                    ans = None

            if ans is None:
                return

            badge = "🧠 LLM 引擎" if ans.engine == "LLM" else "📏 规则引擎"
            head = f"{badge} · 生成 {ans.result.elapsed:.2f}s"
            if ans.fallback_note:
                st.info(f"{head} · {ans.fallback_note}")
            else:
                st.caption(head)

            with st.expander("查看生成的 SQL", expanded=True):
                st.code(ans.sql.strip(), language="sql")

            res = ans.result
            if not res.ok:
                st.error(f"❌ SQL 执行失败：{res.error}")
                st.session_state.history.append((q, ans.engine, ans.sql, pd.DataFrame()))
            elif not res.rows:
                st.warning("查询成功，但没有返回数据。")
                st.session_state.history.append((q, ans.engine, ans.sql, pd.DataFrame()))
            else:
                df = ce.clean_frame(res.columns, res.rows)
                st.session_state.turn += 1
                render_result(df, q, ans.sql, key=str(st.session_state.turn))
                st.session_state.history.append((q, ans.engine, ans.sql, df))
                st.caption(f"⏱ 端到端 {time.time() - t0:.2f}s · {len(df)} 行")

    # ---------------- 历史 ----------------
    if st.session_state.history:
        st.divider()
        st.subheader("🕘 历史提问")
        for i, (hq, heng, hsql, hdf) in enumerate(reversed(st.session_state.history[:-1]), 1):
            with st.expander(f"{i}. {hq}　（{heng} 引擎 · {len(hdf)} 行）"):
                st.code(hsql.strip(), language="sql")
                if not hdf.empty:
                    st.dataframe(hdf, width="stretch", hide_index=True,
                                 height=min(300, 38 + 35 * len(hdf)))


main()
