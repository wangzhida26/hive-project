# -*- coding: utf-8 -*-
"""生成数仓四层架构图 PNG（用于《数仓架构设计文档》）"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams["font.family"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

fig, ax = plt.subplots(figsize=(11, 8.6), dpi=160)
ax.set_xlim(0, 11)
ax.set_ylim(0, 9.4)
ax.axis("off")

C_TITLE = "#1F3864"
C_ODS   = "#8FAADC"
C_STG   = "#A9C4EB"
C_DWD   = "#F4B183"
C_DWS   = "#C5E0B4"
C_ADS   = "#FFE699"
C_TXT   = "#1A1A1A"

def box(x, y, w, h, fc, title, sub="", ec="#4472C4", fs=11.5, subfs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
        boxstyle="round,pad=0.06,rounding_size=0.10",
        linewidth=1.2, edgecolor=ec, facecolor=fc))
    if sub:
        ax.text(x + w/2, y + h*0.62, title, ha="center", va="center",
                fontsize=fs, fontweight="bold", color=C_TXT)
        ax.text(x + w/2, y + h*0.26, sub, ha="center", va="center",
                fontsize=subfs, color="#444444")
    else:
        ax.text(x + w/2, y + h/2, title, ha="center", va="center",
                fontsize=fs, fontweight="bold", color=C_TXT)

def arrow(x, y1, y2, label=""):
    ax.add_patch(FancyArrowPatch((x, y1), (x, y2),
        arrowstyle="-|>", mutation_scale=16, linewidth=1.6, color="#C00000"))
    if label:
        ax.text(x + 0.12, (y1 + y2)/2, label, fontsize=8.2, color="#C00000",
                va="center")

# 标题
ax.text(5.5, 9.05, "云购生活新零售 · Hive 四层数仓架构", ha="center",
        fontsize=16, fontweight="bold", color=C_TITLE)

# 数据源
box(2.2, 8.05, 6.6, 0.62, "#E2EFDA", "业务数据源（CSV 原始文件：订单 / 订单明细 / 用户 / 商品 / 门店 / 用户行为）",
    ec="#70AD47", fs=10)

# ODS
box(2.2, 6.95, 6.6, 0.72, C_ODS, "ODS 贴源层（ods_ 前缀）",
    "6 张 ods_* 外部表 / TEXTFILE / 保留原始脏数据，不做修改", fs=12)
arrow(5.5, 8.05, 7.73, "Sqoop 风格 LOAD DATA 原样接入")

# STG 清洗管道
box(0.55, 5.55, 2.7, 0.95, C_STG, "STG 清洗管道", "stg1_ 枚举标准化", fs=10.5)
box(3.65, 5.55, 2.7, 0.95, C_STG, "（三站串联）", "stg2_ 异常与格式", fs=10.5)
box(6.75, 5.55, 2.7, 0.95, C_STG, "DROP PURGE 重建", "stg3_ 拆分合并/映射", fs=10.5)
ax.add_patch(FancyArrowPatch((3.28, 6.02), (3.62, 6.02), arrowstyle="-|>",
             mutation_scale=12, linewidth=1.3, color="#C00000"))
ax.add_patch(FancyArrowPatch((6.38, 6.02), (6.72, 6.02), arrowstyle="-|>",
             mutation_scale=12, linewidth=1.3, color="#C00000"))
arrow(5.5, 6.95, 6.56, "case when / ABS / regexp_replace / concat")

# DWD
ax.add_patch(FancyBboxPatch((0.9, 3.30), 9.2, 2.05,
    boxstyle="round,pad=0.06,rounding_size=0.10",
    linewidth=1.2, edgecolor="#4472C4", facecolor=C_DWD))
ax.text(5.5, 5.14, "DWD 明细层（dwd_ 前缀）—— 星型模型，本次实训落地",
        ha="center", va="center", fontsize=12.5, fontweight="bold", color=C_TXT)
box(1.25, 4.32, 2.15, 0.62, "#FBE5D6", "dwd_order 事实表", fs=10)
box(3.70, 4.32, 1.85, 0.62, "#FFF2CC", "dim_user", fs=9.5)
box(5.75, 4.32, 1.85, 0.62, "#FFF2CC", "dim_product", fs=9.5)
box(7.80, 4.32, 1.85, 0.62, "#FFF2CC", "dim_store", fs=9.5)
box(1.25, 3.52, 2.15, 0.62, "#FBE5D6", "366 个 order_dt 分区", fs=9)
box(3.70, 3.52, 1.85, 0.62, "#FFF2CC", "dim_date", fs=9.5)
box(5.75, 3.52, 1.85, 0.62, "#FBE5D6", "dwd_order_item", fs=10)
box(7.80, 3.52, 1.85, 0.62, "#FBE5D6", "ORC 明细事实", fs=9)
arrow(5.5, 5.55, 5.41, "INSERT OVERWRITE 动态分区")

# DWS
box(2.2, 2.15, 6.6, 0.72, C_DWS, "DWS 汇总层（dws_ 前缀，规划）",
    "dws_order_1d / dws_user_trade_1d 等按主题轻度汇总", fs=12)
arrow(5.5, 3.30, 2.93, "按主题粒度聚合")

# ADS
box(2.2, 1.05, 6.6, 0.72, C_ADS, "ADS 应用层（ads_ 前缀，规划）",
    "ads_gmv_daily / ads_category_rank 等直接供报表与可视化取数", fs=12)
arrow(5.5, 2.15, 1.83, "指标集市")

# 底部注释
ax.text(5.5, 0.55, "数据流向：业务源 → ODS（贴源不动）→ STG（清洗三站，全部 DROP PURGE 重建）→ DWD（星型模型，动态分区）",
        ha="center", fontsize=9.2, color="#333333")
ax.text(5.5, 0.22, "→ DWS（主题汇总）→ ADS（应用集市）→ 可视化（第 3 周）　　存储：ODS/STG TEXTFILE，DWD ORC",
        ha="center", fontsize=9.2, color="#333333")

out = r"C:\Users\21553\WorkBuddy\2026-10-28-17-01-13\ydsh-dw\docs\dw_architecture.png"
plt.savefig(out, bbox_inches="tight", facecolor="white")
print("saved:", out)
