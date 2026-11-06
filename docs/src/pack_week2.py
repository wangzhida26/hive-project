# -*- coding: utf-8 -*-
"""打包第 2 周提交物 -> 桌面/第2周_提交.zip"""
import os, zipfile

ROOT = r"C:\Users\21553\WorkBuddy\2026-10-28-17-01-13\ydsh-dw"
OUT = r"C:\Users\21553\Desktop\第2周_提交.zip"
BASE = "第2周_王志达"

items = [
    # (zip 内相对路径, 磁盘绝对路径)
    (f"{BASE}/01_代码/sql/clean/clean_enum.sql",
     ROOT + r"\sql\clean\clean_enum.sql"),
    (f"{BASE}/01_代码/sql/clean/clean_abnormal_format.sql",
     ROOT + r"\sql\clean\clean_abnormal_format.sql"),
    (f"{BASE}/01_代码/sql/clean/clean_split_merge.sql",
     ROOT + r"\sql\clean\clean_split_merge.sql"),
    (f"{BASE}/01_代码/sql/dwd/create_dwd.sql",
     ROOT + r"\sql\dwd\create_dwd.sql"),
    (f"{BASE}/01_代码/sql/dwd/load_dwd.sql",
     ROOT + r"\sql\dwd\load_dwd.sql"),
    (f"{BASE}/01_代码/sql/analysis/eda.sql",
     ROOT + r"\sql\analysis\eda.sql"),
    (f"{BASE}/01_代码/sql/quality/quality_compare.sql",
     ROOT + r"\sql\quality\quality_compare.sql"),
    (f"{BASE}/02_文档/数据质量对比报告.docx",
     ROOT + r"\docs\数据质量对比报告.docx"),
    (f"{BASE}/02_文档/数仓架构设计文档.docx",
     ROOT + r"\docs\数仓架构设计文档.docx"),
    (f"{BASE}/02_文档/探索性分析简报.docx",
     ROOT + r"\docs\探索性分析简报.docx"),
    (f"{BASE}/03_日志/第2周_AI协同日志.md",
     ROOT + r"\docs\第2周_AI协同日志.md"),
]

missing = [p for _, p in items if not os.path.exists(p)]
if missing:
    raise SystemExit("missing: " + "; ".join(missing))

if os.path.exists(OUT):
    os.remove(OUT)

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for arc, src in items:
        z.write(src, arc)
    # 提交说明
    readme = (
        "第 2 周作业提交说明（团队 200A · 王志达）\n\n"
        "01_代码/sql/clean/   子任务1-3 枚举标准化、异常值与格式、拆分合并与编码映射脚本\n"
        "01_代码/sql/dwd/     子任务6 DWD 星型模型建表与 ETL 装载脚本\n"
        "01_代码/sql/analysis/eda.sql            子任务7 探索性分析查询（简报数据来源）\n"
        "01_代码/sql/quality/quality_compare.sql 清洗前后五类脏数据量化对比（报告数据来源）\n"
        "02_文档/             子任务4 数据质量对比报告 / 子任务5 数仓架构设计文档 / 子任务7 探索性分析简报\n"
        "03_日志/             第 2 周 AI 协同日志（6 条记录）\n\n"
        "全部指标均由 Hive 实跑得出，运行环境见第 1 周《环境搭建笔记》。\n"
    )
    z.writestr(f"{BASE}/提交说明.txt", readme.encode("utf-8"))

print("OK ->", OUT, os.path.getsize(OUT), "bytes")
