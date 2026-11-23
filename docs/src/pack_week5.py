# -*- coding: utf-8 -*-
"""第 5 周（收官）交付压缩包"""
import os
import zipfile

BASE = r"C:\Users\21553\WorkBuddy\2026-10-28-17-01-13\ydsh-dw"
OUT = r"C:\Users\21553\Desktop\第5周_提交.zip"

ITEMS = [
    # (仓库内路径, 压缩包内路径)
    # —— 五大项目文档 ——
    ("docs/需求文档.docx",              "第5周_王志达/01_项目文档/需求文档.docx"),
    ("docs/数据质量清洗报告.docx",      "第5周_王志达/01_项目文档/数据质量清洗报告.docx"),
    ("docs/数仓架构设计文档.docx",      "第5周_王志达/01_项目文档/数仓架构设计文档.docx"),
    ("docs/部署手册.docx",              "第5周_王志达/01_项目文档/部署手册.docx"),
    ("docs/API配置指南.docx",           "第5周_王志达/01_项目文档/API配置指南.docx"),
    # —— 英文 README 与国际化 ——
    ("README_EN.md",                    "第5周_王志达/02_英文README/README_EN.md"),
    ("README.md",                       "第5周_王志达/02_英文README/README_中文对照.md"),
    # —— Git 审查与提交历史 ——
    ("docs/第5周_Git提交历史审查报告.md","第5周_王志达/03_Git审查/第5周_Git提交历史审查报告.md"),
    ("docs/Git提交历史.txt",            "第5周_王志达/03_Git审查/Git提交历史.txt"),
    ("docs/第3周_Issue与CodeReview记录.md","第5周_王志达/03_Git审查/第3周_Issue与CodeReview记录.md"),
    # —— 答辩材料 ——
    ("docs/答辩演示/综合答辩演示.pptx", "第5周_王志达/04_答辩/综合答辩演示.pptx"),
    # —— 联调核对 ——
    ("docs/第5周_数据一致性核对报告.md","第5周_王志达/05_联调核对/第5周_数据一致性核对报告.md"),
    ("sql/analysis/week5_consistency_check.sql","第5周_王志达/05_联调核对/week5_consistency_check.sql"),
    ("rebuild_pipeline.sh",             "第5周_王志达/05_联调核对/rebuild_pipeline.sh"),
    # —— 反思与协同日志 ——
    ("docs/第5周_个人反思日志.md",      "第5周_王志达/06_日志/第5周_个人反思日志.md"),
    ("docs/第5周_AI协同日志.md",        "第5周_王志达/06_日志/第5周_AI协同日志.md"),
]

README = """第 5 周（收官）交付说明（王志达 · 200A）
=====================================

本压缩包对应《第 5 周任务书》最终交付物清单：

  1. 五大项目文档 ...... 01_项目文档/
     需求文档（业务背景/需求分析/指标体系定义）
     数据质量清洗报告 v2.0（五类脏数据 100% 修复率 + 行数对账）
     数仓架构设计文档 v2.0（四层架构/星型模型/技术选型/部署架构）
     部署手册 + API 配置指南（第 4 周产出，一并归档为完整文档体系）

  2. 英文 README ........ 02_英文README/
     README_EN.md（项目简介/架构/功能/快速开始/技术栈/团队）

  3. Git 审查报告 ...... 03_Git审查/
     40+ 提交全部符合约定式规范、PR/Issue 留痕整理、敏感信息检查通过

  4. 答辩 PPT .......... 04_答辩/
     综合答辩演示.pptx（16 页，10 分钟演示脚本结构）

  5. 联调核对报告 ...... 05_联调核对/
     ODS→DWD→DWS→ADS 逐层实跑核对（指标三方对照一致）
     含联调 Bug 修复：重建脚本幂等性（外部表 CASCADE+LOAD 追加致翻倍）
     全链路重建实测 3 分 25 秒，数据自愈验证通过

  6. 反思与协同日志 .... 06_日志/
     个人反思日志（技术/协作/表达三维度）+ AI 协同日志（8 条记录）

Git 仓库：git@github.com:wangzhida26/hive-project.git（main 分支）
里程碑标签：v1.0-week2 / v2.0-week3 / v3.0-week4 / v4.0-week5
"""


def main():
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("第5周_王志达/交付说明.txt", README)
        for repo_path, zip_path in ITEMS:
            src = os.path.join(BASE, repo_path)
            assert os.path.exists(src), f"缺失: {src}"
            z.write(src, zip_path)
    size = os.path.getsize(OUT)
    print(f"OK -> {OUT} ({size/1024:.0f} KB, {len(ITEMS)+1} 项)")


if __name__ == "__main__":
    main()
