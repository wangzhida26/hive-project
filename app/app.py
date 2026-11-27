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
import forecast_engine as fe  # noqa: E402
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
# LLM Key：连接测试与引擎重建
# ---------------------------------------------------------------------------
def _llm_ready() -> bool:
    import os as _os
    return bool((_os.getenv("OPENAI_API_KEY") or _os.getenv("DEEPSEEK_API_KEY") or "").strip())


def _connect_llm(provider: str, key: str, base: str, model: str) -> str:
    """把 Key 写入进程环境并 ping 一次大模型，返回 'OK …' 或错误信息。"""
    if provider == "DeepSeek" and not base:
        base = "https://api.deepseek.com/v1"
    model = model or "deepseek-chat"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=base or None, timeout=20, max_retries=1)
        resp = client.chat.completions.create(
            model=model, temperature=0, max_tokens=8,
            messages=[{"role": "user", "content": "回复：OK"}],
        )
        reply = (resp.choices[0].message.content or "").strip()
        os.environ["OPENAI_API_KEY"] = key
        os.environ["OPENAI_BASE_URL"] = base
        os.environ["OPENAI_MODEL"] = model
        os.environ["DEEPSEEK_API_KEY"] = key          # 同步写，避免命名不一致
        get_engine.clear()                            # 重建引擎，启用 LLM 优先
        return f"OK 已连接 {model} · 模型应答：{reply[:40] or '正常'}"
    except Exception as exc:
        return f"{type(exc).__name__}: {str(exc)[:220]}"


# ---------------------------------------------------------------------------
# 预测：意图识别与渲染
# ---------------------------------------------------------------------------
def parse_forecast(q: str) -> int | None:
    """识别「预测未来 N 天」类问题，返回预测天数；非预测问题返回 None。"""
    if not fe.INTENT_PAT.search(q):
        return None
    m = re.search(r"(?:未来|接下来|后面|近来的?)\s*(\d+)\s*天", q)
    if m:
        return int(m.group(1))
    if re.search(r"下个?月|一个月|30\s*天", q):
        return 30
    if re.search(r"两周|14\s*天|半个月", q):
        return 14
    if re.search(r"(一|1)?\s*周|7\s*天", q):
        return 7
    return 7        # 有预测意图但未指明天数，默认 7 天


def render_forecast(fr: "fe.ForecastResult", days: int):
    """预测结果可视化：KPI 卡 + 历史/预测双线图 + 置信带 + 明细表。"""
    st.markdown(f'<div class="why">📈 <b>预测模式</b> · 线性趋势 + 周季节性分解模型 · '
                f'未来 {days} 天 · 回测 MAPE {fr.mape:.1f}%</div>' if fr.mape
                else f'<div class="why">📈 <b>预测模式</b> · 线性趋势 + 周季节性分解模型 · 未来 {days} 天</div>',
                unsafe_allow_html=True)

    chg = (fr.daily_avg / fr.hist_daily_avg - 1) * 100 if fr.hist_daily_avg else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"预测 {days} 天 GMV 合计", ce.fmt_num(fr.total_gmv))
    c2.metric("预测日均 GMV", ce.fmt_num(fr.daily_avg),
              f"{chg:+.1f}% vs 近28天", delta_color="normal")
    c3.metric("近 28 天日均（实际）", ce.fmt_num(fr.hist_daily_avg))
    c4.metric("回测误差 MAPE", f"{fr.mape:.1f}%" if fr.mape else "—",
              "近14天留出验证", delta_color="off")

    import plotly.graph_objects as go

    h = fr.history.tail(90)
    f = fr.forecast
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=h["order_dt"], y=h["gmv"], name="历史 GMV", mode="lines",
        line={"color": "#1E4FA8", "width": 1.6},
        hovertemplate="%{x|%m-%d}<br>历史 %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=pd.concat([h["order_dt"].iloc[[-1]], f["order_dt"]]),
        y=pd.concat([h["gmv"].iloc[[-1]], f["gmv"]]),
        name="预测 GMV", mode="lines",
        line={"color": "#E4572E", "width": 2.4, "dash": "dash"},
        hovertemplate="%{x|%m-%d}<br>预测 %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=pd.concat([f["order_dt"], f["order_dt"].iloc[::-1]]),
        y=pd.concat([f["gmv_hi"], f["gmv_lo"].iloc[::-1]]),
        name="95% 置信区间", fill="toself",
        fillcolor="rgba(228,87,46,.14)", line={"width": 0},
        hoverinfo="skip"))
    import numpy as _np
    lo = min(h["gmv"].min(), f["gmv_lo"].min())
    hi = max(h["gmv"].max(), f["gmv_hi"].max())
    ticks = list(_np.linspace(lo, hi, 6))
    fig.update_layout(
        template="plotly_white", height=420, hovermode="x unified",
        legend={"orientation": "h", "y": 1.06, "x": 0},
        xaxis={"title": None, "showgrid": False},
        yaxis={"title": None, "gridcolor": "#EDF1F7",
               "tickvals": ticks, "ticktext": [ce.fmt_num(t) for t in ticks]},
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
    )
    st.plotly_chart(fig, width="stretch", theme=None,
                    config={"displayModeBar": False, "responsive": True})
    st.markdown(f'<div class="insight">🔎 {fr.trend_note}；预测区间为 95% 置信带，'
                f'蓝线为近 90 天实际值，橙色虚线为预测。</div>', unsafe_allow_html=True)

    show = f.rename(columns={"order_dt": "日期", "gmv": "预测GMV",
                             "gmv_lo": "下界", "gmv_hi": "上界", "orders": "预测订单"})
    with st.expander(f"📋 预测明细（{len(show)} 天）", expanded=True):
        st.dataframe(show, width="stretch", hide_index=True,
                     height=min(420, 38 + 35 * len(show)))
        st.download_button(
            "⬇️ 下载预测 CSV", data=show.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"forecast_{days}d_{time.strftime('%H%M%S')}.csv",
            mime="text/csv", key=f"fc-dl-{days}")


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

        # ---- LLM Key 配置（即连即用） ----
        st.subheader("🔑 大模型连接")
        with st.expander("配置 API Key（可选）", expanded=not _llm_ready()):
            provider = st.selectbox(
                "平台", ["DeepSeek", "通义千问", "智谱 GLM", "Moonshot", "OpenAI 兼容"],
                key="llm-provider",
                format_func=lambda x: {"OpenAI 兼容": "OpenAI 兼容（自定义地址）"}.get(x, x))
            defaults = {
                "DeepSeek": ("https://api.deepseek.com/v1", "deepseek-chat"),
                "通义千问": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
                "智谱 GLM": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-plus"),
                "Moonshot": ("https://api.moonshot.cn/v1", "moonshot-v1-8k"),
                "OpenAI 兼容": ("", ""),
            }
            base_def, model_def = defaults[provider]
            key_in = st.text_input("API Key", type="password", key="llm-key",
                                   placeholder="sk-…")
            base_in = st.text_input("Base URL", value=base_def, key="llm-base",
                                    disabled=provider != "OpenAI 兼容")
            model_in = st.text_input("模型名", value=model_def, key="llm-model")
            if st.button("🔗 连接测试", width="stretch", disabled=not key_in.strip()):
                msg = _connect_llm(provider, key_in.strip(), base_in.strip(), model_in.strip())
                if msg.startswith("OK"):
                    st.success(msg[3:])
                    st.rerun()
                else:
                    st.error(msg)

        st.subheader("💬 试试这些")
        examples = [
            "整体经营大盘怎么样",
            "最近一个月 GMV 趋势如何",
            "预测未来 7 天 GMV",
            "预测未来 14 天销售额",
            "各省份销售额排名",
            "各支付方式占比",
            "卖得最好的品类是哪个",
            "销售额最高的门店排名",
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

            # ---- 预测意图：走本地预测引擎，不消耗 LLM ----
            fc_days = parse_forecast(q)
            if fc_days:
                with st.spinner(f"正在基于 {fc_days} 天历史数据拟合趋势并预测 …"):
                    fr = fe.run(fc_days)
                if fr.ok:
                    st.caption("📈 预测引擎 · 趋势 + 周季节性分解 · 本地计算")
                    st.session_state.turn += 1
                    render_forecast(fr, fc_days)
                    st.session_state.history.append(
                        (q, "Forecast", f"未来{fc_days}天预测（趋势+周季节性）", fr.forecast.rename(
                            columns={"order_dt": "日期", "gmv": "预测GMV"})))
                    return
                st.error(f"❌ 预测失败：{fr.error}")
                return

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
