# 第 3 周 AI 协同日志

- 团队：200A　成员：陈劲松、王志达、刘畅、刘正扬　填写日期：2026-11-10

---

## 一、使用的 AI 工具 / 模型

- WorkBuddy Agent（主力协同开发智能体）：SQL 生成、Python 建模、文档撰写、Git 操作
- 大模型 API（NL2SQL 引擎，DeepSeek / 任意 OpenAI 兼容接口）：自然语言转 SQL
- 规则引擎（自研，LLM 未配置密钥时的兜底与演示引擎）

---

## 二、AI 协同记录表（至少 5 条）

| 序号 | 提问 / 任务描述 | AI 产出摘要 | 人工修改与验证 | 是否采纳 |
|------|----------------|-------------|----------------|----------|
| 1 | 设计 DWS 汇总层：按天/品类/门店/渠道/用户五个粒度汇总，给出建表与装载脚本 | 产出 `sql/dws/create_dws.sql`、`load_dws.sql`（5 张 dws_*_1d 表 + dws_user_agg） | 人工核查发现 ads_user_value 初版用固定阈值分层，与实际消费分布脱节、区分度差；要求改为按四分位打分后重算，最终四层人数 286/214/286/214，分布均衡可用 | 是（修改后） |
| 2 | 设计 ADS 应用层 6 张表：KPI 总览/日度趋势/品类排行/门店排行/渠道交叉/用户价值 | 产出 `sql/ads/create_ads.sql`、`load_ads.sql`，含动态分区与窗口函数 | 人工发现初版重复 INSERT ads_kpi_overview、跨天 SUM 导致活跃用户重复计数，要求改为全期单次聚合 | 是（修改后） |
| 3 | 计算核心 KPI 并核对口径 | GMV 2480.56 万、订单 9803、客单价 2530.41、复购率 100%、人均 14.7 单 | 用 dwd_order 明细手工反算 GMV 与订单数，与 ADS 层一致；复购率 100% 的业务含义（全体用户均≥2单）经讨论保留并加注释 | 是 |

| 4 | 构建 NL2SQL：Schema 抽取 + Prompt 设计 + SQL 执行闭环 | 产出 schema_extractor.py（SHOW CREATE TABLE 注释解析）、nl2sql_core.py（LLM+规则双引擎、SQL 护栏）、nl2sql_langchain.py（LCEL 链路）、llm_ping.py（连通性验证） | 实测 12 问全部正确执行（out/nl2sql_run_log.md）；人工修正两个路由 bug：「品类名+每天」被趋势规则抢先、省份简称「浙江」匹配不到「浙江省」 | 是（修改后） |

> 记录 4 由 `feature/nl2sql-engine` 分支补充（NL2SQL 组）；记录 5-6 由 `feature/analytics-docs` 分支补充。
