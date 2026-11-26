"""意图感知的图表推荐与渲染引擎
================================================
输入 (问题, SQL, 结果 DataFrame) → ChartSpec → Plotly Figure。

设计原则：
1. **先看形状，再看意图**——结果集是 1 行还是 100 行、有没有日期列、有没有省份列，
   决定了可选的图形；问题里的"趋势/排名/占比/分布"再在其中挑一个。
2. **一张图只讲一件事**——不做双 Y 轴、不做堆叠堆到看不清。
3. **视觉统一**——所有图形共用一套配色与版式，和 ECharts 大屏、Superset 保持同一观感。

图形类型：
  kpi     单行结果            → 指标卡片（在 app 层用 st.metric 渲染）
  line    日期 + 数值          → 面积折线（点数够时叠加 7 日均线）
  map     省份 + 数值          → 中国地图（DataV GeoJSON，含南海诸岛，合规）
  bar_h   类别 + 数值（排名）   → 横向条形，自动降序
  donut   类别 + 数值（占比）   → 环形图，中心显示合计
  grouped 两个类别 + 数值       → 分组柱
  bar_v   类别 + 数值（默认）   → 纵向柱
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 视觉规范
# ---------------------------------------------------------------------------
PRIMARY = "#1E4FA8"
PRIMARY_LIGHT = "#5B8AD6"
ACCENT = "#E8833A"
INK = "#1B2A3A"
MUTED = "#6B7C93"
GRID = "#E8EDF5"
SERIES = ["#1E4FA8", "#3E7BD6", "#5FA8D3", "#2A9D8F", "#E9C46A", "#E8833A", "#8E7CC3", "#C0563F"]
FONT = '"Source Han Sans SC", "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif'

BASE = Path(__file__).resolve().parent
GEO_CANDIDATES = [
    BASE / "china.json",                        # 容器内（Dockerfile COPY）
    BASE.parent / "screen" / "vendor" / "china.json",  # 宿主机调试
    Path("/opt/app/app/china.json"),
]

# 省份 → 省会坐标（用于地图气泡；与 analysis/mirror_to_mysql.py 同源）
CAPITAL = {
    "浙江省": (30.27, 120.15), "江苏省": (32.06, 118.78), "广东省": (23.13, 113.26),
    "山东省": (36.67, 117.02), "河南省": (34.76, 113.62), "四川省": (30.57, 104.06),
    "湖北省": (30.59, 114.31), "湖南省": (28.23, 112.94), "福建省": (26.08, 119.30),
    "安徽省": (31.82, 117.23), "河北省": (38.04, 114.51), "陕西省": (34.27, 108.95),
    "辽宁省": (41.80, 123.43), "吉林省": (43.88, 125.32), "黑龙江省": (45.80, 126.53),
    "山西省": (37.87, 112.55), "云南省": (25.04, 102.71), "贵州省": (26.65, 106.63),
    "江西省": (28.68, 115.86), "广西壮族自治区": (22.82, 108.32), "海南省": (20.04, 110.34),
    "甘肃省": (36.06, 103.83), "青海省": (36.62, 101.78), "宁夏回族自治区": (38.49, 106.23),
    "新疆维吾尔自治区": (43.79, 87.62), "内蒙古自治区": (40.82, 111.65),
    "西藏自治区": (29.65, 91.14), "北京市": (39.90, 116.41), "上海市": (31.23, 121.47),
    "天津市": (39.13, 117.20), "重庆市": (29.56, 106.55), "香港特别行政区": (22.32, 114.17),
    "澳门特别行政区": (22.20, 113.55), "台湾省": (25.04, 121.51),
}
_SHORT = {k.rstrip("省市") if k.endswith("市") else k.replace("省", "").replace("自治区", "")
          .replace("壮族", "").replace("回族", "").replace("维吾尔", ""): k for k in CAPITAL}


@dataclass
class ChartSpec:
    kind: str
    x: str | None = None
    y: str | None = None
    series: str | None = None
    title: str = ""
    reason: str = ""      # 为什么选这个图，展示给用户（答辩时可讲）
    unit: str = ""


# ---------------------------------------------------------------------------
# 列语义识别
# ---------------------------------------------------------------------------
_DATE_PAT = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


def to_num(s: pd.Series) -> pd.Series:
    """字符串列转数值：容忍千分位逗号、百分号、空值占位。"""
    t = (s.astype(str)
          .str.replace(",", "", regex=False)
          .str.replace("%", "", regex=False)
          .str.strip()
          .replace({"": None, "NULL": None, "null": None, "None": None, "-": None, "\\N": None}))
    return pd.to_numeric(t, errors="coerce")


def is_date_col(name: str, s: pd.Series) -> bool:
    if re.search(r"(^|_)(dt|date|day|month)$|日期|时间|月份", str(name), re.I):
        return True
    vals = s.astype(str).head(20)
    return vals.str.match(_DATE_PAT).mean() >= 0.8


def is_province_col(name: str, s: pd.Series) -> bool:
    if re.search(r"province|省份|省$", str(name), re.I):
        return True
    vals = [str(v).strip() for v in s.dropna().head(40)]
    if not vals:
        return False
    hit = sum(1 for v in vals if v in CAPITAL or v.rstrip("市") + "市" in CAPITAL
              or re.fullmatch(r".{2,8}(省|市|自治区|特别行政区)", v) is not None)
    return hit / len(vals) >= 0.7


def numeric_cols(df: pd.DataFrame) -> list[str]:
    out = []
    single = len(df) <= 1          # 单行结果每列都只有 1 个值，不能按 nunique 过滤
    for c in df.columns:
        # 主键 / 序号 / 排名这类"看起来是数字、其实不是指标"的列要排除
        if re.search(r"(^|_)(id|no|code|key|rk|rank|idx|seq|rownum)$|编号|代码|排名|序号", str(c), re.I):
            continue
        n = to_num(df[c])
        if n.notna().mean() < 0.9:
            continue
        if not single and n.nunique(dropna=True) <= 1:   # 常量列没有信息量
            continue
        out.append(c)
    return out


def cat_cols(df: pd.DataFrame, nums: list[str]) -> list[str]:
    return [c for c in df.columns if c not in nums]


def clean_frame(columns: list[str], rows: list[list[str]]) -> pd.DataFrame:
    """统一把结果转成 DataFrame：数值列转数值，日期列转 datetime（便于排序）。"""
    df = pd.DataFrame(rows, columns=columns)
    df = df.replace({"NULL": None, "null": None, "None": None, "\\N": None})
    for c in list(df.columns):
        n = to_num(df[c])
        if n.notna().mean() >= 0.9 and n.nunique(dropna=True) > 1:
            df[c] = n
    for c in list(df.columns):
        if c in df.columns and df[c].dtype == object and is_date_col(c, df[c]):
            try:
                df[c] = pd.to_datetime(df[c], errors="ignore")
            except Exception:
                pass
    return df


# ---------------------------------------------------------------------------
# 图表推荐
# ---------------------------------------------------------------------------
TREND_WORDS = ("趋势", "走势", "变化", "增长", "下滑", "波动", "曲线", "每月", "每日", "按月", "按天")
RANK_WORDS = ("排名", "排行", "top", "最高", "最低", "最好", "最差", "前几", "前十", "靠前", "卖得最好", "哪个更")
SHARE_WORDS = ("占比", "构成", "比例", "分布", "结构", "份额", "百分比")


def infer(df: pd.DataFrame, question: str = "", sql: str = "") -> ChartSpec:
    """根据结果集形状 + 问题意图推荐图表。"""
    if df is None or df.empty:
        return ChartSpec("table", reason="结果为空，仅展示表格")

    nums = numeric_cols(df)
    cats = cat_cols(df, nums)
    q = (question or "").lower()

    # 1) 单行 → 指标卡
    if len(df) == 1 and nums:
        return ChartSpec("kpi", reason="单行结果，用指标卡比图表更直观")

    # 2) 无度量列 → 只能看表格（如"有哪些门店"）
    if not nums:
        return ChartSpec("table", reason="结果中没有数值列，表格就是最好的呈现")

    # 3) 日期 → 趋势
    date_col = next((c for c in cats if is_date_col(c, df[c])), None)
    if date_col and any(w in q for w in TREND_WORDS + ("",)):
        y = _pick_metric(df, nums, q)
        return ChartSpec("line", x=date_col, y=y,
                         title=f"{y} 随 {date_col} 的变化",
                         reason=f"结果含时间列「{date_col}」，用折线看趋势")

    # 4) 省份 → 地图（仅当问题真的在问地域，或省份是唯一的分类维度）
    #    否则"门店排名"这类结果会因为带了 province 列而被误画成地图
    prov_col = next((c for c in cats if is_province_col(c, df[c])), None)
    asks_geo = re.search(r"省份|各省|哪个省|地区|区域|地域|地图|华东|华南|华北", q)
    other_cats = [c for c in cats if c != prov_col and df[c].nunique() > 1]
    if prov_col and df[prov_col].nunique() >= 3 and (asks_geo or not other_cats):
        y = _pick_metric(df, nums, q)
        return ChartSpec("map", x=prov_col, y=y,
                         title=f"各省 {y} 分布",
                         reason="结果含省份维度，地图比柱状图更能体现地域差异")

    # 5) 两个类别列 + 度量 → 分组柱（如 省份 × 渠道 × GMV）
    if len(cats) >= 2 and df[cats[0]].nunique() <= 12 and df[cats[1]].nunique() <= 6:
        y = _pick_metric(df, nums, q)
        return ChartSpec("grouped", x=cats[0], y=y, series=cats[1],
                         title=f"{y}：{cats[0]} × {cats[1]}",
                         reason=f"两个维度「{cats[0]}」「{cats[1]}」，用分组柱便于横向对比")

    # 6) 单一类别 + 度量
    if cats:
        c0 = cats[0]
        y = _pick_metric(df, nums, q)
        n = df[c0].nunique()
        if any(w in q for w in SHARE_WORDS) and n <= 8:
            return ChartSpec("donut", x=c0, y=y, title=f"{y} 构成（按{c0}）",
                             reason=f"问题是看构成，且「{c0}」只有 {n} 类，环形图最清楚")
        if any(w in q for w in RANK_WORDS) or n >= 10:
            return ChartSpec("bar_h", x=c0, y=y, title=f"{y} 排名（按{c0}）",
                             reason=f"「{c0}」有 {n} 个取值，横向条形不怕标签挤")
        return ChartSpec("bar_v", x=c0, y=y, title=f"{y}（按{c0}）",
                         reason=f"单一维度「{c0}」，柱状图做对比")

    # 7) 只有多个度量 → 用第一度量对索引画柱
    return ChartSpec("bar_v", x=None, y=nums[0], title=f"{nums[0]}",
                     reason="结果只含度量列，按行序展示")


def _pick_metric(df: pd.DataFrame, nums: list[str], q: str) -> str:
    """多度量时选一个最像"主指标"的：优先问题里提到的，其次 gmv/金额/销售额。"""
    for c in nums:
        if str(c).lower() in q or str(c) in q:
            return c
    for kw in ("gmv", "销售额", "金额", "amount", "sales", "订单量", "orders", "数量", "qty"):
        for c in nums:
            if kw in str(c).lower():
                return c
    return nums[0]


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def china_geo() -> dict | None:
    """加载 DataV 中国 GeoJSON，并把环方向规范化为 RFC 7946（外环逆时针）。

    DataV 数据外环是顺时针，plotly.js 会把陆地判成"洞"、把洞判成陆地，
    渲染出来就是"整个视野被填充、省份反而镂空"——必须反转。
    """
    for p in GEO_CANDIDATES:
        try:
            if not p.exists():
                continue
            geo = json.loads(p.read_text(encoding="utf-8"))

            def fix_rings(coords):
                return [list(reversed(r)) for r in coords]

            for f in geo.get("features", []):
                g = f.get("geometry") or {}
                if g.get("type") == "Polygon":
                    g["coordinates"] = fix_rings(g["coordinates"])
                elif g.get("type") == "MultiPolygon":
                    g["coordinates"] = [fix_rings(pg) for pg in g["coordinates"]]
                # 南海诸岛 feature 的 name 是空字符串，choropleth 无法按 name 匹配，
                # 赋予显式名称，保证九段线与南海诸岛边界完整呈现
                props = f.setdefault("properties", {})
                if not str(props.get("name", "")).strip():
                    props["name"] = "南海诸岛"
            return geo
        except Exception:
            continue
    return None


def fmt_num(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    a = abs(f)
    if a >= 1e8:
        return f"{f / 1e8:,.2f} 亿"
    if a >= 1e4:
        return f"{f / 1e4:,.2f} 万".rstrip("0").rstrip(".").replace(".00 万", " 万")
    if a >= 1000:
        return f"{f:,.0f}"
    if a >= 10:
        return f"{f:,.1f}".rstrip("0").rstrip(".")
    return f"{f:,.2f}".rstrip("0").rstrip(".")


def cn_ticks(fig, vmax: float, axis: str = "y", pad: float = 1.0):
    """把数值轴刻度换成中文单位（2e5 → 20 万），避免出现 200k/2.5M。"""
    import math

    if not vmax or vmax <= 0 or math.isinf(vmax) or math.isnan(vmax):
        return
    raw = vmax / 4
    mag = 10 ** math.floor(math.log10(raw))
    step = math.ceil(raw / mag) * mag
    top = vmax * 1.02 * pad
    vals = [i * step for i in range(1, 6) if i * step < top]
    if not vals:
        return
    updater = fig.update_yaxes if axis == "y" else fig.update_xaxes
    updater(tickvals=vals, ticktext=[fmt_num(v) for v in vals])


def _base_layout(fig, title: str, height: int = 400):
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left",
                   font=dict(size=15, color="#0F2A52", family=FONT)),
        height=height,
        margin=dict(l=13, r=16, t=46, b=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12.5, color=INK),
        hoverlabel=dict(bgcolor="white", bordercolor=GRID,
                        font=dict(family=FONT, size=12, color=INK)),
        showlegend=False,
        dragmode=False,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=MUTED),
                     zeroline=False, showline=True)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, griddash="dot",
                     tickfont=dict(color=MUTED), zeroline=False, showline=False)
    return fig


def build_figure(spec: ChartSpec, df: pd.DataFrame):
    """返回 plotly Figure；kpi/table 返回 None（由界面层处理）。"""
    import plotly.graph_objects as go

    if spec.kind in ("kpi", "table"):
        return None

    if spec.kind == "line":
        return _line(spec, df)
    if spec.kind == "map":
        return _map(spec, df)
    if spec.kind == "donut":
        return _donut(spec, df)
    if spec.kind == "bar_h":
        return _bar(spec, df, horizontal=True)
    if spec.kind == "grouped":
        return _grouped(spec, df)
    return _bar(spec, df, horizontal=False)


def _line(spec: ChartSpec, df: pd.DataFrame):
    import plotly.graph_objects as go

    d = df[[spec.x, spec.y]].dropna().copy()
    d = d.sort_values(spec.x)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d[spec.x], y=d[spec.y], mode="lines+markers",
        line=dict(color=PRIMARY, width=2.6, shape="spline", smoothing=0.6),
        marker=dict(size=5, color=PRIMARY, line=dict(width=1.5, color="white")),
        fill="tozeroy", fillcolor="rgba(30,79,168,0.10)",
        name=spec.y,
        hovertemplate="%{x}<br><b>%{y:,.2f}</b><extra></extra>",
    ))
    # 点数够多时叠加 7 日均线，避免日波动干扰判断
    if len(d) >= 14:
        ma = d[spec.y].rolling(7, min_periods=3).mean()
        fig.add_trace(go.Scatter(
            x=d[spec.x], y=ma, mode="lines",
            line=dict(color=ACCENT, width=2, dash="dash"),
            name="7 日均线",
            hovertemplate="7 日均线 <b>%{y:,.2f}</b><extra></extra>",
        ))
        fig.update_layout(showlegend=True, legend=dict(
            orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)", font=dict(size=11.5, color=MUTED)))
    _base_layout(fig, spec.title, 400)
    cn_ticks(fig, float(d[spec.y].max()), axis="y")
    fig.update_yaxes(range=[0, float(d[spec.y].max()) * 1.12])
    return fig


def _bar(spec: ChartSpec, df: pd.DataFrame, horizontal: bool):
    import plotly.graph_objects as go

    xcol = spec.x
    d = df.copy()
    if xcol is None:                       # 无类别列：按行序号
        d["_序号"] = [f"第{i + 1}行" for i in range(len(d))]
        xcol = "_序号"
    d = d[[xcol, spec.y]].dropna()
    d = d.sort_values(spec.y, ascending=horizontal).tail(20) if horizontal else d.head(20)

    # 按数值深浅着色：越大越深，读者一眼看出高低
    v = d[spec.y].astype(float)
    lo, hi = float(v.min()), float(v.max())
    ratio = (v - lo) / (hi - lo) if hi > lo else pd.Series([0.5] * len(v), index=v.index)
    colors = [f"rgba(30,79,168,{0.35 + 0.6 * r:.2f})" for r in ratio]

    if horizontal:
        fig = go.Figure(go.Bar(
            x=d[spec.y], y=d[xcol].astype(str), orientation="h",
            marker=dict(color=colors, line=dict(width=0)),
            text=[fmt_num(vv) for vv in d[spec.y]],
            textposition="outside", textfont=dict(size=11.5, color=INK),
            hovertemplate="%{y}<br><b>%{x:,.2f}</b><extra></extra>",
            width=0.68,
        ))
        _base_layout(fig, spec.title, max(320, 34 * len(d) + 90))
        cn_ticks(fig, float(v.max()), axis="x")
        fig.update_xaxes(showgrid=True, gridcolor=GRID, griddash="dot",
                         showline=False, tickfont=dict(color=MUTED),
                         range=[0, float(v.max()) * 1.15])   # 留出数值标签的空间
        fig.update_yaxes(showgrid=False, showline=False, tickfont=dict(size=12, color=INK))
        fig.update_layout(margin=dict(l=13, r=70, t=46, b=13))
    else:
        fig = go.Figure(go.Bar(
            x=d[xcol].astype(str), y=d[spec.y],
            marker=dict(color=colors, line=dict(width=0)),
            text=[fmt_num(vv) for vv in d[spec.y]],
            textposition="outside", textfont=dict(size=11.5, color=INK),
            hovertemplate="%{x}<br><b>%{y:,.2f}</b><extra></extra>",
            width=0.6,
        ))
        _base_layout(fig, spec.title, 400)
        cn_ticks(fig, float(v.max()), axis="y")
        fig.update_yaxes(range=[0, float(v.max()) * 1.15])
        fig.update_layout(margin=dict(l=13, r=16, t=46, b=56))
    return fig


def _donut(spec: ChartSpec, df: pd.DataFrame):
    import plotly.graph_objects as go

    d = df[[spec.x, spec.y]].dropna().sort_values(spec.y, ascending=False).head(8)
    fig = go.Figure(go.Pie(
        labels=d[spec.x].astype(str), values=d[spec.y],
        hole=0.58, sort=False,
        marker=dict(colors=SERIES[: len(d)], line=dict(color="white", width=2)),
        textinfo="percent", textfont=dict(size=12, color="white"),
        hovertemplate="%{label}<br><b>%{value:,.2f}</b>（%{percent}）<extra></extra>",
    ))
    total = float(d[spec.y].sum())
    fig.add_annotation(text=f"<span style='font-size:12px;color:{MUTED}'>合计</span><br>"
                            f"<b style='font-size:18px;color:{PRIMARY}'>{fmt_num(total)}</b>",
                       x=0.5, y=0.5, showarrow=False, align="center")
    _base_layout(fig, spec.title, 400)
    fig.update_layout(showlegend=True,
                      legend=dict(orientation="v", x=1.02, y=0.5, yanchor="middle",
                                  bgcolor="rgba(0,0,0,0)", font=dict(size=11.5, color=INK)),
                      margin=dict(l=8, r=8, t=46, b=8))
    return fig


def _grouped(spec: ChartSpec, df: pd.DataFrame):
    import plotly.graph_objects as go

    d = df[[spec.x, spec.series, spec.y]].dropna()
    fig = go.Figure()
    for i, (name, g) in enumerate(d.groupby(spec.series, sort=False)):
        fig.add_trace(go.Bar(
            x=g[spec.x].astype(str), y=g[spec.y], name=str(name),
            marker=dict(color=SERIES[i % len(SERIES)], line=dict(width=0)),
            hovertemplate=f"{name}<br>%{{x}}<br><b>%{{y:,.2f}}</b><extra></extra>",
        ))
    _base_layout(fig, spec.title, 420)
    cn_ticks(fig, float(d[spec.y].max()), axis="y")
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.08,
                      showlegend=True,
                      legend=dict(orientation="h", yanchor="bottom", y=1.0,
                                  xanchor="right", x=1, bgcolor="rgba(0,0,0,0)",
                                  font=dict(size=11.5, color=MUTED)))
    return fig


def _map(spec: ChartSpec, df: pd.DataFrame):
    import plotly.graph_objects as go

    geo = china_geo()
    d = df[[spec.x, spec.y]].dropna().copy()
    d["_省"] = d[spec.x].astype(str).str.strip().map(_norm_province)
    d = d.dropna(subset=["_省"])
    if geo is None or d.empty:
        return _bar(spec, df, horizontal=True)      # 无地理数据时优雅降级

    all_names = [f["properties"].get("name", "") for f in geo["features"]]

    fig = go.Figure()
    # 底图 trace：全国所有省级区域统一浅色填充，未上榜的省份不空白
    fig.add_trace(go.Choropleth(
        geojson=geo, featureidkey="properties.name",
        locations=all_names, z=[0] * len(all_names),
        colorscale=[[0, "#DFE9F6"], [1, "#DFE9F6"]], showscale=False,
        marker=dict(line=dict(color="white", width=1)),
        hoverinfo="skip",
    ))
    # 南海诸岛专用 trace：岛小线细，用比底图更深的填充与描边保证九段线清晰可见
    fig.add_trace(go.Choropleth(
        geojson=geo, featureidkey="properties.name",
        locations=["南海诸岛"], z=[1],
        colorscale=[[0, "#C3D3EA"], [1, "#C3D3EA"]], showscale=False,
        marker=dict(line=dict(color="#8FA9CF", width=1.2)),
        hoverinfo="skip",
    ))
    fig.add_trace(go.Choropleth(
        geojson=geo, featureidkey="properties.name",
        locations=d["_省"], z=d[spec.y].astype(float),
        zmin=float(d[spec.y].min()) * 0.9, zmax=float(d[spec.y].max()),
        colorscale=[[0, "#B9CFEE"], [0.45, "#5E8FD4"], [0.75, "#2B62B8"], [1, "#123B80"]],
        marker=dict(line=dict(color="white", width=1)),
        colorbar=dict(thickness=10, len=0.6, x=0.93, outlinewidth=0,
                      tickfont=dict(size=11, color=MUTED)),
        hovertemplate="%{location}<br><b>%{z:,.2f}</b><extra></extra>",
        showscale=True,
    ))

    # 省会气泡：大小按数值开方比例，作为视觉锚点
    pts = d[d["_省"].isin(CAPITAL)].copy()
    if not pts.empty:
        v = pts[spec.y].astype(float)
        span = v.max() - v.min()
        size = 9 + 22 * ((v - v.min()) / span if span > 0 else 0.5)
        fig.add_trace(go.Scattergeo(
            lon=[CAPITAL[p][1] for p in pts["_省"]],
            lat=[CAPITAL[p][0] for p in pts["_省"]],
            text=pts["_省"], mode="markers",
            marker=dict(size=size, color=ACCENT, opacity=0.42,
                        line=dict(width=1.4, color="white")),
            hovertemplate="%{text}<br><b>%{customdata:,.2f}</b><extra></extra>",
            customdata=pts[spec.y], showlegend=False,
        ))

    _base_layout(fig, spec.title, 470)
    fig.update_geos(
        projection=dict(type="mercator"),
        # 以底图 trace（全部 35 个省级 feature，含南海诸岛）为视野基准：
        # 中国全境 + 九段线完整呈现，不会因数据缺省而裁切领土
        fitbounds="locations", visible=False,
        showland=False, showcountries=False, showcoastlines=False,
        showframe=False, showlakes=False, bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(margin=dict(l=6, r=6, t=46, b=6), showlegend=False)
    return fig


def _norm_province(v: str) -> str | None:
    v = str(v).strip()
    if v in CAPITAL:
        return v
    if v.endswith("市") or v.endswith("省") or v.endswith("自治区") or v.endswith("特别行政区"):
        return v if v in CAPITAL else None
    full = _SHORT.get(v)
    return full


def caption(spec: ChartSpec, df: pd.DataFrame) -> str:
    """图表下方的一句话结论，帮业务方读懂图。"""
    if spec.kind in ("kpi", "table") or not spec.y or df.empty:
        return ""
    try:
        s = df[spec.y].astype(float)
    except Exception:
        return ""
    if spec.kind == "line" and len(df) >= 2:
        first, last = s.iloc[0], s.iloc[-1]
        chg = (last - first) / first * 100 if first else 0
        arrow = "增长" if chg >= 0 else "下降"
        return f"首末对比{arrow} {abs(chg):.1f}%（{fmt_num(first)} → {fmt_num(last)}），峰值 {fmt_num(s.max())}"

    # 分组图按系列汇总，其余按 X 维度汇总（同一维度多行时先求和）
    if spec.kind == "grouped" and spec.series:
        g = df.groupby(spec.series, dropna=True)[spec.y].sum()
        label = f"按{spec.series}"
    elif spec.x:
        g = df.groupby(spec.x, dropna=True)[spec.y].sum()
        label = ""
    else:
        return ""
    if g.empty or not g.sum():
        return ""
    top = g.idxmax()
    return (f"{label}最高：{top}（{fmt_num(g.max())}，占 {g.max() / g.sum() * 100:.1f}%）"
            f"｜ 合计 {fmt_num(g.sum())}")
