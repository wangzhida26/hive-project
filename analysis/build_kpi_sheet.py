"""
导出「KPI 指标结果表」Excel（第 3 周交付物 2）
==================================================
直接从 Hive 实跑取数，写入 docs/KPI指标结果表.xlsx，多 sheet 组织：
  1. 核心KPI总览    ads_kpi_overview
  2. 日度趋势       ads_gmv_daily（366 天）
  3. 月度汇总       按 SUBSTR(order_dt,1,7) 聚合
  4. 品类排行       ads_category_sales
  5. 门店排行       ads_store_sales（60 家全量）
  6. 渠道支付       ads_channel_sales
  7. 用户价值分层   ads_user_value 按 segment 聚合
  8. 口径说明       指标定义与取数 SQL 摘要

用法：python analysis/build_kpi_sheet.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent / "nl2sql"))
from nl2sql_core import run_hive  # noqa: E402

OUT = BASE.parent / "docs" / "KPI指标结果表.xlsx"

QUERIES = {
    "1_核心KPI总览": "SELECT * FROM ydsh_ads.ads_kpi_overview",
    "2_日度趋势": (
        "SELECT order_dt, ROUND(gmv,2) AS gmv, orders, ROUND(aov,2) AS aov, "
        "ROUND(ma7,2) AS ma7, ROUND(dod_pct,2) AS dod_pct, weekday, is_weekend "
        "FROM ydsh_ads.ads_gmv_daily ORDER BY order_dt"
    ),
    "3_月度汇总": (
        "SELECT SUBSTR(order_dt,1,7) AS ym, ROUND(SUM(gmv),2) AS gmv, SUM(orders) AS orders, "
        "ROUND(SUM(gmv)/SUM(orders),2) AS aov, ROUND(AVG(users),1) AS avg_daily_users "
        "FROM ydsh_dws.dws_order_1d GROUP BY SUBSTR(order_dt,1,7) ORDER BY ym"
    ),
    "4_品类排行": (
        "SELECT rk, category, ROUND(gmv,2) AS gmv, qty, orders, share_pct "
        "FROM ydsh_ads.ads_category_sales ORDER BY rk"
    ),
    "5_门店排行": (
        "SELECT rk, store_name, province, city, ROUND(gmv,2) AS gmv, orders, users "
        "FROM ydsh_ads.ads_store_sales ORDER BY rk"
    ),
    "6_渠道支付": (
        "SELECT channel, pay_type, ROUND(gmv,2) AS gmv, orders, share_pct "
        "FROM ydsh_ads.ads_channel_sales ORDER BY gmv DESC"
    ),
    "7_用户价值分层": (
        "SELECT segment, COUNT(*) AS users, ROUND(AVG(recency),1) AS avg_r, "
        "ROUND(AVG(frequency),1) AS avg_f, ROUND(AVG(monetary),2) AS avg_m, "
        "ROUND(SUM(monetary),2) AS gmv, "
        "ROUND(SUM(monetary)/(SELECT SUM(monetary) FROM ydsh_ads.ads_user_value)*100,2) AS gmv_share_pct "
        "FROM ydsh_ads.ads_user_value GROUP BY segment ORDER BY gmv DESC"
    ),
}

CALIBER = [
    ("指标", "定义 / 口径"),
    ("有效订单", "order_status IN ('已支付','已完成')"),
    ("有效 GMV", "有效订单的 pay_amount 之和；负值已在清洗层修正，≥10万异常单已在 DWD 过滤"),
    ("客单价 AOV", "有效 GMV / 有效订单量"),
    ("活跃用户", "当期有下单行为的去重 user_id 数"),
    ("复购率", "下单≥2 次的用户数 / 下单用户数（本数据集 1,000 用户人均 14.7 单，故为 100%）"),
    ("退款率", "退款中订单量 / 全部状态订单量"),
    ("品类 GMV", "dwd_order_item.item_amount 按 dim_product.category 汇总（明细行口径）"),
    ("门店 GMV", "dwd_order.pay_amount 按 store_id 汇总（订单口径）"),
    ("RFM", "R=距 2024-12-31 天数，F=累计订单数，M=累计 GMV；四分位打分 1-4，R/F 双高为重要价值"),
]


def main() -> None:
    sheets = {}
    for name, sql in QUERIES.items():
        r = run_hive(sql)
        if not r.ok:
            raise RuntimeError(f"{name} 取数失败：{r.error}")
        df = pd.DataFrame(r.rows, columns=r.columns)
        # 数值列尽量转成数字，便于 Excel 排序与作图
        for c in df.columns:
            try:
                df[c] = pd.to_numeric(df[c])
            except (ValueError, TypeError):
                pass
        sheets[name] = df
        print(f"{name:<14} {len(df):>4} 行  {r.elapsed:.1f}s")

    sheets["8_口径说明"] = pd.DataFrame(CALIBER[1:], columns=list(CALIBER[0]))

    with pd.ExcelWriter(OUT, engine="openpyxl") as w:
        for name, df in sheets.items():
            df.to_excel(w, sheet_name=name, index=False)
            ws = w.sheets[name]
            for i, col in enumerate(df.columns, 1):
                width = max(len(str(col)) * 2 + 4, 12)
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(width, 28)
            ws.freeze_panes = "A2"

    print(f"\n已生成：{OUT}")


if __name__ == "__main__":
    main()
