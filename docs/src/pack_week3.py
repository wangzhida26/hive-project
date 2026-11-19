# -*- coding: utf-8 -*-
"""第 3 周交付物打包（UTF-8 文件名，Windows 解压不乱码）"""
import os
import zipfile
from pathlib import Path

ROOT = Path(r"C:\Users\21553\WorkBuddy\2026-10-28-17-01-13\ydsh-dw")
OUT = Path(r"C:\Users\21553\Desktop\第3周_提交.zip")
PREFIX = "第3周_王志达"

FILES = [
    # 01 代码：SQL
    ("sql/dws/create_dws.sql", "01_代码/sql/dws/create_dws.sql"),
    ("sql/dws/load_dws.sql", "01_代码/sql/dws/load_dws.sql"),
    ("sql/ads/create_ads.sql", "01_代码/sql/ads/create_ads.sql"),
    ("sql/ads/load_ads.sql", "01_代码/sql/ads/load_ads.sql"),
    ("sql/analysis/eda.sql", "01_代码/sql/analysis/eda.sql"),
    ("sql/analysis/attribution_1106.sql", "01_代码/sql/analysis/attribution_1106.sql"),
    # 01 代码：Python 分析
    ("analysis/forecast_gmv.py", "01_代码/analysis/forecast_gmv.py"),
    ("analysis/build_kpi_sheet.py", "01_代码/analysis/build_kpi_sheet.py"),
    ("analysis/out/metrics.json", "01_代码/analysis/out/metrics.json"),
    ("analysis/out/forecast_7d.csv", "01_代码/analysis/out/forecast_7d.csv"),
    # 01 代码：NL2SQL
    ("nl2sql/schema_extractor.py", "01_代码/nl2sql/schema_extractor.py"),
    ("nl2sql/nl2sql_core.py", "01_代码/nl2sql/nl2sql_core.py"),
    ("nl2sql/nl2sql_langchain.py", "01_代码/nl2sql/nl2sql_langchain.py"),
    ("nl2sql/llm_ping.py", "01_代码/nl2sql/llm_ping.py"),
    ("nl2sql/test_nl2sql.py", "01_代码/nl2sql/test_nl2sql.py"),
    ("nl2sql/schema_prompt.txt", "01_代码/nl2sql/schema_prompt.txt"),
    ("nl2sql/.env.example", "01_代码/nl2sql/.env.example"),
    ("nl2sql/README.md", "01_代码/nl2sql/README.md"),
    # 02 文档
    ("docs/KPI指标结果表.xlsx", "02_文档/KPI指标结果表.xlsx"),
    ("docs/预测建模分析报告.docx", "02_文档/预测建模分析报告.docx"),
    ("docs/AI智能洞察与反思.docx", "02_文档/AI智能洞察与反思.docx"),
    ("docs/src/04_预测建模分析报告.md", "02_文档/源文件/04_预测建模分析报告.md"),
    ("docs/src/05_AI智能洞察与反思.md", "02_文档/源文件/05_AI智能洞察与反思.md"),
    # 03 日志与留痕
    ("docs/第3周_AI协同日志.md", "03_日志/第3周_AI协同日志.md"),
    ("docs/第3周_Issue与CodeReview记录.md", "03_日志/第3周_Issue与CodeReview记录.md"),
    ("nl2sql/out/nl2sql_run_log.md", "03_日志/NL2SQL实测运行日志.md"),
    # 04 图表
    ("analysis/out/fig_gmv_trend.png", "04_图表/GMV日度趋势.png"),
    ("analysis/out/fig_test_fit.png", "04_图表/测试集拟合对比.png"),
    ("analysis/out/fig_weekday.png", "04_图表/星期效应.png"),
    ("analysis/out/fig_importance.png", "04_图表/特征重要性.png"),
]

README_TXT = """第 3 周提交说明（团队 200A / 王志达）
==================================================

一、交付清单对照（任务书第五部分）
1. DWS / ADS 建模与 ETL 脚本 ............ 01_代码/sql/dws、01_代码/sql/ads
2. KPI 指标结果表 ...................... 02_文档/KPI指标结果表.xlsx（8 个 sheet）
3. 预测建模分析报告 ..................... 02_文档/预测建模分析报告.docx（含模型评估与边界说明）
4. NL2SQL 接口代码 ..................... 01_代码/nl2sql（含 Prompt 与 Schema 抽取逻辑）
5. AI 智能洞察 / 反思文档 ............... 02_文档/AI智能洞察与反思.docx
6. PR / Code Review / Issue 记录 ........ 03_日志/第3周_Issue与CodeReview记录.md

二、可复核的实跑证据
- KPI：GMV 2,480.56 万元 / 有效订单 9,803 单 / 客单价 2,530.41 元（ydsh_ads.ads_kpi_overview）
- 预测：线性回归 MAPE 17.42%（vs 昨日值基线 24.66%），未来 7 天合计 474,497.33 元
- 异常：2024-11-06 GMV 环比 -61.25%，六视角归因（总量/品类/渠道/门店/状态/客单价）
- NL2SQL：12 个典型问题全部命中并正确执行，日志见 03_日志/NL2SQL实测运行日志.md

三、环境与复现
- Docker Compose 启动 Hive 4.0.0 + MySQL 8.0（docker-compose.yml 在仓库根目录）
- 数据链路：ODS → STG 三层清洗 → DWD 星型模型（366 分区）→ DWS 五粒度 → ADS 六表
- 建模：python analysis/forecast_gmv.py；KPI 表：python analysis/build_kpi_sheet.py
- NL2SQL：python nl2sql/test_nl2sql.py（未配密钥时自动走规则引擎，仍可完整演示）

四、说明
- 大模型密钥未随包提交（.env 已被 .gitignore 忽略），仅提供 .env.example 模板；
- 本次 NL2SQL 实测运行于无密钥环境，12 问由规则引擎命中；LLM 链路代码已完整实现，配置密钥后可用
  NL2SQL(prefer="llm") 切换。
"""


def main() -> None:
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for src, dst in FILES:
            p = ROOT / src
            if not p.exists():
                print(f"[缺失] {src}")
                continue
            zi = zipfile.ZipInfo(f"{PREFIX}/{dst}", date_time=(2026, 11, 10, 9, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.flag_bits |= 0x800  # UTF-8 文件名标记
            with open(p, "rb") as f:
                z.writestr(zi, f.read())
        zi = zipfile.ZipInfo(f"{PREFIX}/提交说明.txt", date_time=(2026, 11, 10, 9, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.flag_bits |= 0x800
        z.writestr(zi, README_TXT.encode("utf-8"))

    with zipfile.ZipFile(OUT) as z:
        names = z.namelist()
        bad = z.testzip()
    print(f"已生成：{OUT}")
    print(f"条目数：{len(names)}　大小：{OUT.stat().st_size / 1024:.1f} KB　损坏：{bad}")
    for n in names:
        print("  ", n)


if __name__ == "__main__":
    main()
