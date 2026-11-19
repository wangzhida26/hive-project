# 云购生活新零售企业——企业级数据仓库与经营分析可视化系统

> 企业项目实战实训 · 已完成第 1~4 周：环境搭建 · 数据清洗 · 分层建模 · KPI · 预测建模 · NL2SQL · 可视化（Superset/ECharts/Streamlit）· Docker 一键部署

## 一、团队信息
- **队名**：___200A_____（请填写你的队名）
- **口号**：___加油_____
- **成员**：____陈劲松 王志达 刘畅 刘正扬____（3～4 人）

## 二、角色分工

| 角色 | 职责 | 成员 |
|------|------|------|
| 项目经理 | 进度管理、任务拆分、答辩汇报、Git 仓库管理 | _陈劲松_______ |
| 数据工程师 | 环境搭建（Docker/Hive/MySQL）、ODS 建表与数据导入、数据清洗 | __王志达______ |
| 数据分析师 | 数据质量五维度预评估、清洗策略制定、质量报告素材 | ___刘畅_____ |
| 可视化工程师 | 后续指标看板设计、环境搭建笔记与文档整理 | __刘正扬______ |

> 允许一人多岗，请按实际情况填写。

## 三、项目目标

围绕「云购生活」新零售企业的 6 张模拟业务数据（用户、商品、门店、订单、订单明细、用户行为），搭建企业级数据仓库：

1. **数仓分层**：ODS 贴源层 → DWD 明细层 →（后续）DWS 汇总层 → ADS 应用层；
2. **数据治理**：从完整性、唯一性、有效性、一致性、准确性五个维度评估数据质量，完成缺失值处理与重复值去重；
3. **经营分析**：（后续周次）构建经营分析指标体系，通过 Superset 等工具实现可视化看板。

## 四、阶段计划

| 周次 | 主题 | 关键产出 |
|------|------|----------|
| 第 1 周 | 项目启动 · 环境搭建 · Git 基础 · 数据导入 · 数据清洗（一） | README、环境笔记、ODS 6 张表、质量预评估表、缺失值/去重脚本、AI 协同日志 |
| 第 2 周 | 数据清洗（二）· 数仓分层建模 · 探索性分析 | STG 三层清洗管道、DWD 星型模型（14,696 单 / 366 分区）、质量对比报告、架构设计文档、EDA 简报 |
| 第 3 周 | DWS/ADS · KPI · 预测建模 · AI 协同（NL2SQL）· Git 协同 | DWS 五粒度汇总、ADS 六张应用表、KPI 结果表、预测建模报告、NL2SQL 双引擎、AI 洞察与反思、PR/Review/Issue 记录 |
| 第 4 周 | 可视化（Superset + ECharts）· Streamlit 问答 · Docker 一键部署 · 压测 | Superset 仪表板（6 图表+筛选器）、ECharts 数据大屏（scale 自适应）、Streamlit NL2SQL 闭环、6 服务 compose 编排、部署手册/API 指南、压力测试记录 |

## 五、技术栈

- **容器化**：Docker Desktop（WSL 2 backend）+ docker compose
- **大数据组件**：Apache Hive 4.0.0（Metastore + HiveServer2）、MySQL 8.0（Metastore 元数据库）
- **版本管理**：Git + GitHub/Gitee（Conventional Commits 规范：`feat:` / `fix:` / `docs:`）
- **数据处理**：Hive SQL（ODS 建表导入、质量评估、缺失值填充、ROW_NUMBER 去重）
- **可视化**（后续）：Superset

## 六、仓库结构

```
ydsh-dw/
├── README.md                        # 本文件
├── .gitignore                       # 忽略数据/密钥/日志文件
├── docker-compose.yml               # Hive + MySQL 编排
├── data/                            # 模拟数据 CSV（不入库）
├── docs/
│   ├── 环境搭建笔记.docx             # 环境搭建过程、问题与解决
│   ├── 数据质量对比报告.docx         # 第2周：清洗前后五维对比
│   ├── 数仓架构设计文档.docx         # 第2周：四层架构与星型模型
│   ├── 探索性分析简报.docx           # 第2周：EDA 十组查询结论
│   ├── 预测建模分析报告.docx         # 第3周：3 模型 + 2 基线，MAE/MAPE 与边界
│   ├── AI智能洞察与反思.docx         # 第3周：11-06 骤降归因、自动摘要、AI 反思
│   ├── KPI指标结果表.xlsx            # 第3周：8 个 sheet 的核心指标结果
│   ├── 第2周_AI协同日志.md
│   ├── 第3周_AI协同日志.md
│   ├── 第4周_AI协同日志.md
│   ├── 第4周_压力测试记录.md
│   ├── 部署手册.docx / API配置指南.docx
│   ├── 第3周_Issue与CodeReview记录.md # 第3周：PR / Review / Issue / 冲突解决留痕
│   └── Git提交历史.txt
├── sql/
│   ├── ods/        create_ods.sql / load_ods.sql
│   ├── quality/    quality_check.sql / quality_compare.sql
│   ├── clean/      clean_missing.sql / clean_dup.sql
│   │               clean_enum.sql / clean_abnormal_format.sql / clean_split_merge.sql
│   ├── dwd/        create_dwd.sql / load_dwd.sql（星型模型 + 366 动态分区）
│   ├── dws/        create_dws.sql / load_dws.sql（五粒度汇总）
│   ├── ads/        create_ads.sql / load_ads.sql（六张应用表）
│   └── analysis/   eda.sql / attribution_1106.sql
├── app/                             # 第4周 Streamlit 问答应用（容器化）
│   ├── app.py                       # 提问→SQL→表格+自动图表
│   ├── Dockerfile / requirements.txt
├── screen/                          # 第4周 ECharts 数据大屏
│   ├── 云购生活数据大屏.html        # 单文件成品（含实测截图 大屏截图.png）
│   ├── build_screen.py              # 数据装配脚本
│   └── vendor/                      # echarts + 合规中国地图 GeoJSON
├── analysis/                        # 第3/4周 Python 建模与部署工具
│   ├── forecast_gmv.py              # 时间序列预测（3 模型 + 2 基线）
│   ├── build_kpi_sheet.py           # 导出 KPI 结果表 Excel
│   ├── mirror_to_mysql.py           # Hive→MySQL 报表镜像（12 表+省份坐标）
│   ├── superset_setup.py            # Superset REST 自动配置
│   ├── stress_test.py               # 查询优化对比与并发压测
│   ├── data/                        # 从 Hive 导出的取数快照
│   └── out/                         # 图表、metrics.json、7 天预测
└── nl2sql/                          # 第3周 NL2SQL 接口
    ├── schema_extractor.py          # 自动抽取表结构与中文注释
    ├── nl2sql_core.py               # LLM + 规则双引擎、SQL 护栏、执行器
    ├── nl2sql_langchain.py          # LangChain LCEL 链路
    ├── llm_ping.py                  # 大模型连通性验证
    ├── test_nl2sql.py               # 12 问批量实测
    └── out/nl2sql_run_log.md        # 实测运行日志
```
