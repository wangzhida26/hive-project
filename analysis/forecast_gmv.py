# -*- coding: utf-8 -*-
"""
云购生活 · 日度 GMV 时间序列分析与 7 日预测（子任务2）

输入：analysis/data/gmv_daily.csv（由 Hive ydsh_ads.ads_gmv_daily 导出）
输出：analysis/out/ 下的图表、预测结果与 metrics.json

方法：
  1) 趋势与季节性观察：7 日移动平均、周内效应（星期均值）、月度汇总；
  2) 特征工程：lag1/lag2/lag7、ma7、星期哑变量；
  3) 模型：线性回归（基线）、岭回归、梯度提升树（GBDT），并与两种朴素基线对比；
  4) 评估：时间序列切分（前 336 天训练、后 30 天测试），指标 MAE / RMSE / MAPE；
  5) 预测：用最优模型递归预测未来 7 天 GMV。
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data", "gmv_daily.csv")
OUT = os.path.join(BASE, "out")
os.makedirs(OUT, exist_ok=True)

plt.rcParams["font.family"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

df = pd.read_csv(DATA, encoding="utf-8-sig", parse_dates=["order_dt"])
df = df.sort_values("order_dt").reset_index(drop=True)
df = df[["order_dt", "gmv", "orders", "aov", "weekday"]].copy()
df["weekday"] = df["order_dt"].dt.dayofweek  # 0=周一
print(f"样本区间 {df.order_dt.min().date()} ~ {df.order_dt.max().date()}，共 {len(df)} 天")
print(f"日均 GMV {df.gmv.mean():,.0f} 元，标准差 {df.gmv.std():,.0f}，变异系数 {df.gmv.std()/df.gmv.mean():.3f}")

# ---------- 1. 描述性分析 ----------
df["ma7"] = df["gmv"].rolling(7).mean()
df["ma30"] = df["gmv"].rolling(30).mean()
weekday_mean = df.groupby("weekday")["gmv"].mean()
month_mean = df.set_index("order_dt")["gmv"].resample("ME").mean()

# 周内效应：周末 vs 工作日
wk = df.assign(is_weekend=(df.weekday >= 5).astype(int)).groupby("is_weekend")["gmv"].mean()
print("周末日均 %.0f 元 / 工作日日均 %.0f 元，差异 %.1f%%"
      % (wk[1], wk[0], (wk[1] / wk[0] - 1) * 100))

# 波动来源：日环比分布
dod = df["gmv"].pct_change().dropna()
print("日环比：均值 %.2f%%，标准差 %.2f%%，最大单日跌幅 %.2f%%"
      % (dod.mean() * 100, dod.std() * 100, dod.min() * 100))

# ---------- 2. 特征工程 ----------
def build_features(frame, target_col="gmv"):
    f = frame.copy()
    f["lag1"] = f[target_col].shift(1)
    f["lag2"] = f[target_col].shift(2)
    f["lag7"] = f[target_col].shift(7)
    f["ma7"] = f[target_col].shift(1).rolling(7).mean()
    f["weekday"] = f["order_dt"].dt.dayofweek
    f["is_weekend"] = (f["weekday"] >= 5).astype(int)
    f["month"] = f["order_dt"].dt.month
    return f.dropna().reset_index(drop=True)

feat = build_features(df)
FEATURES = ["lag1", "lag2", "lag7", "ma7", "weekday", "is_weekend", "month"]

# 时间序列切分：后 30 天做测试集
TEST_DAYS = 30
train, test = feat.iloc[:-TEST_DAYS], feat.iloc[-TEST_DAYS:]
X_train, y_train = train[FEATURES], train["gmv"]
X_test, y_test = test[FEATURES], test["gmv"]
print(f"训练集 {len(train)} 天，测试集 {len(test)} 天")

# ---------- 3. 模型与基线 ----------
models = {
    "线性回归": LinearRegression(),
    "岭回归(alpha=1)": Ridge(alpha=1.0),
    "梯度提升树": GradientBoostingRegressor(
        n_estimators=300, learning_rate=0.05, max_depth=3,
        subsample=0.8, random_state=42),
}

def mape(y_true, y_pred):
    return float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)

results, preds = {}, {}
for name, model in models.items():
    model.fit(X_train, y_train)
    p = model.predict(X_test)
    preds[name] = p
    results[name] = {
        "MAE": round(mean_absolute_error(y_test, p), 2),
        "RMSE": round(float(np.sqrt(mean_squared_error(y_test, p))), 2),
        "MAPE": round(mape(y_test.values, p), 2),
    }

# 朴素基线
naive_lag1 = test["lag1"].values                     # 用昨天预测今天
naive_ma7 = test["ma7"].values                       # 用前 7 日均值
results["基线-昨日值"] = {
    "MAE": round(mean_absolute_error(y_test, naive_lag1), 2),
    "RMSE": round(float(np.sqrt(mean_squared_error(y_test, naive_lag1))), 2),
    "MAPE": round(mape(y_test.values, naive_lag1), 2),
}
results["基线-7日均值"] = {
    "MAE": round(mean_absolute_error(y_test, naive_ma7), 2),
    "RMSE": round(float(np.sqrt(mean_squared_error(y_test, naive_ma7))), 2),
    "MAPE": round(mape(y_test.values, naive_ma7), 2),
}

print("\n模型评估（测试集 30 天）：")
for k, v in results.items():
    print(f"  {k:14s} MAE={v['MAE']:>9,.0f}  RMSE={v['RMSE']:>9,.0f}  MAPE={v['MAPE']:>5.2f}%")

# 选优：MAPE 最低
best_name = min(results, key=lambda k: results[k]["MAPE"])
print(f"最优模型：{best_name}（MAPE {results[best_name]['MAPE']}%）")

# ---------- 4. 未来 7 天递归预测 ----------
if best_name in models:
    model = models[best_name]
    hist = df["gmv"].tolist()
    last_date = df["order_dt"].max()
    future = []
    for step in range(1, 8):
        d = last_date + pd.Timedelta(days=step)
        row = {
            "lag1": hist[-1], "lag2": hist[-2], "lag7": hist[-7],
            "ma7": float(np.mean(hist[-7:])),
            "weekday": d.dayofweek, "is_weekend": int(d.dayofweek >= 5),
            "month": d.month,
        }
        yhat = float(model.predict(pd.DataFrame([row])[FEATURES])[0])
        hist.append(yhat)
        future.append({"date": d.strftime("%Y-%m-%d"), "pred_gmv": round(yhat, 2)})
else:  # 若朴素基线胜出，则用 7 日均值外推
    future = []
    hist = df["gmv"].tolist()
    for step in range(1, 8):
        d = last_date + pd.Timedelta(days=step)
        yhat = float(np.mean(hist[-7:]))
        hist.append(yhat)
        future.append({"date": d.strftime("%Y-%m-%d"), "pred_gmv": round(yhat, 2)})

fdf = pd.DataFrame(future)
print("\n未来 7 天预测：")
print(fdf.to_string(index=False))
fdf.to_csv(os.path.join(OUT, "forecast_7d.csv"), index=False, encoding="utf-8-sig")

# ---------- 5. 图表 ----------
fig, ax = plt.subplots(figsize=(11, 4.2))
ax.plot(df.order_dt, df.gmv, color="#B0B7C3", linewidth=0.9, label="日 GMV")
ax.plot(df.order_dt, df.ma7, color="#C00000", linewidth=1.4, label="7 日移动平均")
fut_dates = pd.to_datetime(fdf.date)
ax.plot(fut_dates, fdf.pred_gmv, color="#1F3864", marker="o", linewidth=1.6, label="未来 7 天预测")
ax.set_title("2024 年日度 GMV 走势与未来 7 天预测")
ax.set_ylabel("GMV（元）")
ax.legend(loc="upper left", frameon=False)
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_gmv_trend.png"), dpi=150, facecolor="white")

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(test.order_dt, y_test, color="#333333", marker="o", markersize=3, label="真实 GMV")
if best_name in preds:
    ax.plot(test.order_dt, preds[best_name], color="#C00000", marker="o", markersize=3,
            label=f"{best_name} 预测")
ax.plot(test.order_dt, naive_ma7, color="#7F7F7F", linestyle="--", linewidth=1,
        label="基线：7 日均值")
ax.set_title(f"测试集（后 {TEST_DAYS} 天）拟合对比 · 最优模型 {best_name}")
ax.set_ylabel("GMV（元）")
ax.legend(frameon=False)
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_test_fit.png"), dpi=150, facecolor="white")

fig, ax = plt.subplots(figsize=(8, 3.6))
labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
ax.bar(labels, weekday_mean.values, color="#4472C4")
ax.set_title("周内效应：各星期日均 GMV")
ax.set_ylabel("日均 GMV（元）")
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_weekday.png"), dpi=150, facecolor="white")

# 特征重要性（GBDT）
gb = models["梯度提升树"]
imp = pd.Series(gb.feature_importances_, index=FEATURES).sort_values()
fig, ax = plt.subplots(figsize=(7, 3.4))
imp.plot(kind="barh", ax=ax, color="#70AD47")
ax.set_title("梯度提升树特征重要性")
ax.grid(axis="x", alpha=0.25)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_importance.png"), dpi=150, facecolor="white")

# ---------- 6. 指标落盘 ----------
summary = {
    "period": [str(df.order_dt.min().date()), str(df.order_dt.max().date())],
    "n_days": int(len(df)),
    "mean_gmv": round(float(df.gmv.mean()), 2),
    "std_gmv": round(float(df.gmv.std()), 2),
    "cv": round(float(df.gmv.std() / df.gmv.mean()), 4),
    "weekend_mean": round(float(wk[1]), 2),
    "weekday_mean": round(float(wk[0]), 2),
    "weekend_lift_pct": round(float((wk[1] / wk[0] - 1) * 100), 2),
    "weekday_mean_gmv": {labels[int(k)]: round(float(v), 2) for k, v in weekday_mean.items()},
    "dod_std_pct": round(float(dod.std() * 100), 2),
    "max_drop_pct": round(float(dod.min() * 100), 2),
    "max_drop_date": str(df.loc[dod.idxmin(), "order_dt"].date()),
    "test_days": TEST_DAYS,
    "metrics": results,
    "best_model": best_name,
    "best_mape": results[best_name]["MAPE"],
    "forecast": future,
    "forecast_total": round(float(fdf.pred_gmv.sum()), 2),
}
with open(os.path.join(OUT, "metrics.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False, indent=2)
print("\n结果已写入 analysis/out/（metrics.json + 4 张图 + forecast_7d.csv）")
