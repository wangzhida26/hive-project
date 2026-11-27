"""forecast_engine —— 经营数据未来预测（纯 numpy/pandas，无新增依赖）

模型：加法分解 线性趋势 + 周季节性 + 残差置信带
    y(t) = a + b·t + s(weekday) + ε
    - a, b：对历史序列做最小二乘拟合
    - s(weekday)：去趋势残差按星期几取均值（周一…周日各一个系数）
    - 置信带：残差标准差 σ，随预测步长轻微放大（√(1+h/n)）
回测：留出最后 holdout 天做 MAPE，验证模型可信度。

数据源：ADS 层 ads_gmv_daily（与大屏/仪表板同一口径）。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from nl2sql_core import run_query

HISTORY_SQL = "SELECT order_dt, gmv, orders FROM ydsh_ads.ads_gmv_daily ORDER BY order_dt"

INTENT_PAT = re.compile(r"预测|预报|未来|明天|接下来|以后|下个?周|下个?月|forecast", re.IGNORECASE)


@dataclass
class ForecastResult:
    ok: bool
    horizon: int = 0
    history: pd.DataFrame | None = None     # order_dt, gmv, orders
    forecast: pd.DataFrame | None = None    # order_dt, gmv, gmv_lo, gmv_hi, orders
    mape: float | None = None               # 回测 MAPE(%)
    total_gmv: float = 0.0
    daily_avg: float = 0.0
    hist_daily_avg: float = 0.0
    trend_note: str = ""
    error: str = ""


# ----------------------------------------------------------------------------
# 核心：拟合与预测
# ----------------------------------------------------------------------------
def _fit(history: pd.DataFrame) -> dict:
    """对日 GMV 做趋势 + 周季节性拟合，返回模型参数。"""
    y = history["gmv"].to_numpy(dtype=float)
    wd = history["order_dt"].dt.weekday.to_numpy()      # 0=周一 … 6=周日
    n = len(y)
    t = np.arange(n, dtype=float)

    # 线性趋势（最小二乘）
    b, a = np.polyfit(t, y, 1)
    trend = a + b * t

    # 周季节系数：去趋势残差按星期几均值
    resid = y - trend
    seas = np.zeros(7)
    for k in range(7):
        m = wd == k
        if m.any():
            seas[k] = resid[m].mean()

    sigma = float(resid.std(ddof=1)) if n > 10 else float(y.std() or 1.0)
    return {"a": float(a), "b": float(b), "seas": seas, "sigma": sigma, "n": n}


def _predict(model: dict, start_ts: pd.Timestamp, horizon: int) -> np.ndarray:
    hs = np.arange(model["n"], model["n"] + horizon, dtype=float)
    base = model["a"] + model["b"] * hs
    wds = [(start_ts + pd.Timedelta(days=i)).weekday() for i in range(horizon)]
    return np.maximum(base + np.array([model["seas"][w] for w in wds]), 0.0)


def _mape(history: pd.DataFrame, holdout: int) -> tuple[float | None, dict]:
    """留出最后 holdout 天回测；返回 (MAPE%, 可用于训练的前缀模型)。"""
    n = len(history)
    if n < holdout + 30:
        return None, _fit(history)
    train = history.iloc[:-holdout].reset_index(drop=True)
    test = history.iloc[-holdout:]
    m = _fit(train)
    preds = _predict(m, test["order_dt"].iloc[0], holdout)
    actual = test["gmv"].to_numpy(dtype=float)
    mask = actual > 0
    if not mask.any():
        return None, _fit(history)
    mape = float(np.mean(np.abs((preds[mask] - actual[mask]) / actual[mask])) * 100)
    return mape, _fit(history)      # 最终模型仍用全量数据


# ----------------------------------------------------------------------------
# 入口
# ----------------------------------------------------------------------------
def run(horizon: int = 7) -> ForecastResult:
    horizon = max(1, min(int(horizon), 30))
    res = run_query(HISTORY_SQL, timeout=120)
    if not res.ok or not res.rows:
        return ForecastResult(ok=False, error=res.error or "无历史数据")

    hist = pd.DataFrame(res.rows, columns=["order_dt", "gmv", "orders"])
    hist["order_dt"] = pd.to_datetime(hist["order_dt"], errors="coerce")
    for c in ("gmv", "orders"):
        hist[c] = pd.to_numeric(hist[c], errors="coerce")
    hist = hist.dropna().sort_values("order_dt").reset_index(drop=True)
    if len(hist) < 30:
        return ForecastResult(ok=False, error=f"历史数据不足（仅 {len(hist)} 天）")

    mape, model = _mape(hist, holdout=14)

    last_dt = hist["order_dt"].iloc[-1]
    fc_dates = pd.date_range(last_dt + pd.Timedelta(days=1), periods=horizon, freq="D")
    preds = _predict(model, fc_dates[0], horizon)

    # 置信带：σ 随步长轻微放大
    h_idx = np.arange(1, horizon + 1)
    band = model["sigma"] * np.sqrt(1 + h_idx / model["n"])
    # 订单预测：按 GMV 比例缩放近期客单价
    recent_aov = (hist["gmv"].tail(28) / hist["orders"].tail(28).replace(0, np.nan)).median()
    recent_aov = recent_aov if recent_aov and not math.isnan(recent_aov) else 2500.0
    fc_orders = np.maximum(preds / recent_aov, 0)

    fc = pd.DataFrame({
        "order_dt": fc_dates.strftime("%Y-%m-%d"),
        "gmv": np.round(preds, 2),
        "gmv_lo": np.round(np.maximum(preds - 1.96 * band, 0), 2),
        "gmv_hi": np.round(preds + 1.96 * band, 2),
        "orders": np.round(fc_orders).astype(int),
    })

    trend_note = (
        f"日均趋势{'上升' if model['b'] > 0 else '下降'}约 {abs(model['b']) / max(hist['gmv'].mean(), 1) * 100:.1f}%"
        if model["b"] != 0 else "趋势平稳"
    )
    return ForecastResult(
        ok=True, horizon=horizon,
        history=hist, forecast=fc,
        mape=mape,
        total_gmv=float(fc["gmv"].sum()),
        daily_avg=float(fc["gmv"].mean()),
        hist_daily_avg=float(hist["gmv"].tail(28).mean()),
        trend_note=trend_note,
    )
