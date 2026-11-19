# -*- coding: utf-8 -*-
"""第 4 周交付压缩包"""
import os
import zipfile

BASE = r"C:\Users\21553\WorkBuddy\2026-10-28-17-01-13\ydsh-dw"
OUT = r"C:\Users\21553\Desktop\第4周_提交.zip"

ITEMS = [
    # (仓库内路径, 压缩包内路径)
    ("docker-compose.yml",           "第4周_王志达/04_部署/docker-compose.yml"),
    (".env.example",                 "第4周_王志达/04_部署/.env.example"),
    (".dockerignore",                "第4周_王志达/04_部署/.dockerignore"),
    ("app/app.py",                   "第4周_王志达/04_部署/app/app.py"),
    ("app/Dockerfile",               "第4周_王志达/04_部署/app/Dockerfile"),
    ("app/requirements.txt",         "第4周_王志达/04_部署/app/requirements.txt"),
    ("analysis/mirror_to_mysql.py",  "第4周_王志达/04_部署/scripts/mirror_to_mysql.py"),
    ("analysis/superset_setup.py",   "第4周_王志达/04_部署/scripts/superset_setup.py"),
    ("analysis/stress_test.py",      "第4周_王志达/04_部署/scripts/stress_test.py"),
    ("analysis/out/stress_test.json","第4周_王志达/04_部署/scripts/stress_test.json"),
    ("rebuild_pipeline.sh",          "第4周_王志达/04_部署/rebuild_pipeline.sh"),
    ("sql/analysis/screen_export.sql","第4周_王志达/04_部署/sql/screen_export.sql"),
    ("screen/云购生活数据大屏.html",  "第4周_王志达/01_ECharts大屏/云购生活数据大屏.html"),
    ("screen/build_screen.py",       "第4周_王志达/01_ECharts大屏/build_screen.py"),
    ("screen/screen_template.html",  "第4周_王志达/01_ECharts大屏/screen_template.html"),
    ("screen/大屏截图.png",          "第4周_王志达/01_ECharts大屏/大屏截图.png"),
    ("screen/vendor/echarts.min.js", "第4周_王志达/01_ECharts大屏/vendor/echarts.min.js"),
    ("screen/vendor/china.json",     "第4周_王志达/01_ECharts大屏/vendor/china.json"),
    ("docs/部署手册.docx",           "第4周_王志达/02_文档/部署手册.docx"),
    ("docs/API配置指南.docx",        "第4周_王志达/02_文档/API配置指南.docx"),
    ("docs/第4周_压力测试记录.md",   "第4周_王志达/02_文档/第4周_压力测试记录.md"),
    ("docs/第4周_AI协同日志.md",     "第4周_王志达/03_日志/第4周_AI协同日志.md"),
]

README = """第 4 周交付说明（王志达 · 200A）
=====================================

本压缩包对应《第 4 周任务书》交付物清单：

  1. Superset 仪表板 ...... 仪表板已在本地 Superset 实例配置完成
     （http://localhost:8088/superset/dashboard/1/ ，6 图表 + 日期筛选器），
     一键复现脚本见 04_部署/scripts/superset_setup.py（配合 mirror_to_mysql.py）。
  2. ECharts 数据大屏 ...... 01_ECharts大屏/云购生活数据大屏.html
     （单文件、离线可用；大屏截图.png 为实测渲染截图）。
  3. Streamlit 问答应用 ... 04_部署/app/（宿主机 streamlit run app/app.py，
     或 docker compose up -d app）。
  4. docker-compose.yml ... 04_部署/（6 服务一键部署，healthcheck+depends_on，
     密钥经 .env 注入；使用方法见部署手册）。
  5. 部署手册 / API 配置指南 ... 02_文档/。
  6. 压力测试记录 ......... 02_文档/第4周_压力测试记录.md（原始数据 stress_test.json）。

全部指标与数字均来自 Hive/MySQL/ClickHouse 实测，未使用估算值。
Git 仓库：github.com/wangzhida26/hive-project（main 分支，tag: v3.0-week4）。
"""


def main():
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo("第4周_王志达/提交说明.txt")
        zi.flag_bits |= 0x800  # UTF-8 文件名
        zi.external_attr = 0o644 << 16
        z.writestr(zi, README)
        count += 1
        for src, dst in ITEMS:
            full = os.path.join(BASE, src)
            if not os.path.exists(full):
                print("缺失:", src)
                continue
            zi = zipfile.ZipInfo(dst)
            zi.flag_bits |= 0x800
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(full, "rb") as f:
                z.writestr(zi, f.read())
            count += 1
    print(f"OK: {OUT}  共 {count} 项  {os.path.getsize(OUT)//1024} KB")


if __name__ == "__main__":
    main()
