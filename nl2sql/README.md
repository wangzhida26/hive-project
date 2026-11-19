# NL2SQL 自然语言查询接口

把「业务人员的一句话提问」翻译成 Hive SQL，执行后返回结果表格。对应第 3 周子任务 3、4。

## 1. 目录结构

| 文件 | 作用 |
| --- | --- |
| `schema_extractor.py` | 自动抽取 Hive 表结构 + 中文注释，产出 `schema_prompt.txt` 与 `schema_snapshot.json` |
| `nl2sql_core.py` | 核心引擎：LLM 引擎 + 规则引擎（双引擎）、SQL 安全护栏、beeline 执行器、结果格式化 |
| `nl2sql_langchain.py` | LangChain LCEL 版本链路（Prompt → ChatOpenAI → StrOutputParser → 护栏 → 执行） |
| `llm_ping.py` | 大模型连通性最小化验证（子任务 3），密钥掩码输出 |
| `test_nl2sql.py` | 12 个典型问题批量实测，产出 `out/nl2sql_run_log.md` |
| `schema_prompt.txt` | 供 Prompt 注入的 Schema 文本（16 张表、带中文注释与业务口径） |
| `.env.example` | 密钥配置模板（复制为 `.env` 使用，`.env` 已被 `.gitignore` 忽略） |
| `out/nl2sql_run_log.md` | 实测运行日志：12 问的问题、SQL、结果、耗时与汇总 |

## 2. 快速开始

```bash
# 1) 安装依赖
pip install openai python-dotenv langchain-core langchain-openai

# 2) 配置密钥（可选；不配置也能用规则引擎完整演示）
cp .env.example .env      # 填入 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
python llm_ping.py        # 验证连通性

# 3) 重新抽取 Schema（表结构变化后执行）
python schema_extractor.py

# 4) 单问
python nl2sql_core.py "各品类销售额排名"

# 5) 批量实测并生成日志
python test_nl2sql.py

# 6) LangChain 链路
python nl2sql_langchain.py "最近一个月每天的 GMV 走势"
```

## 3. 双引擎设计（为什么不是一个引擎）

| 引擎 | 何时使用 | 优点 | 风险 |
| --- | --- | --- | --- |
| **LLM 引擎**（OpenAI 兼容） | 配置了密钥且网络可用 | 能理解开放表达，可组合多表多条件 | 可能幻觉字段、语法偶发不合法、依赖网络与额度 |
| **规则引擎**（离线） | 无密钥 / 断网 / LLM 调用异常 | 零依赖、毫秒级路由、SQL 100% 可预期 | 只覆盖 13 类常见意图，表达变化大时命中率下降 |

调度逻辑：`prefer="auto"` 时优先 LLM，**任一异常（网络、额度、格式、护栏校验不通过）自动回退规则引擎**，保证答辩现场"提问 → SQL → 结果"闭环不会因为网络挂掉。

## 4. Prompt 设计要点

1. **Schema 注入**：16 张表逐列给出「列名 类型 -- 中文注释」，让模型知道 `paid_gmv` 与 `gmv` 的区别，避免把全状态 GMV 当有效 GMV。
2. **口径固化**：把「有效订单 = 已支付 + 已完成」「客单价 = 有效GMV/有效订单」「RFM 基准日 2024-12-31」「大额异常已在 DWD 过滤」写进 system prompt —— 这是本项目踩过的坑（AI 曾用全状态口径导致与 ADS 层对不上）。
3. **Few-shot 4 例**：覆盖「总览 / TopN / 分组排行 / 带过滤条件」四种典型形态，示例均取自 ADS/DWS 表。
4. **输出约束**：只输出单条 SELECT、不用 markdown 代码块、不解释 —— 降低解析成本与格式失败率。

## 5. SQL 安全护栏（`guard_sql`）

```python
只允许 SELECT / WITH 开头        # 拒绝 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/LOAD...
拒绝多语句（含分号）
关键字黑名单二次校验
无 LIMIT 时强制追加 LIMIT 200    # 防全表扫描拖垮 HiveServer2
```

## 6. Schema 抽取的两个坑

1. `DESC 表名` 的中文注释在 beeline 输出层被替换为 `?`（终端编码），MySQL 元数据库 `COLUMNS_V2.COMMENT` 也被连接字符集吃成 `?`。
   **解法**：从 `SHOW CREATE TABLE` 的 DDL 文本中正则解析 `COMMENT '...'`，与 `information_schema.columns` 的结构合并。
2. Hive `DESC` 会同时输出分区列与表列，`dwd_order` 的 `order_dt` 出现两次。
   **处理**：不影响生成质量，已在抽取器注释中标注为 Known Issue。

## 7. 实测结果

12 个典型问题全部命中并正确执行（详见 `out/nl2sql_run_log.md`）：

| # | 问题 | 命中引擎 | 结果 |
| --- | --- | --- | --- |
| 1 | 整体经营大盘怎么样 | Rule | GMV 2,480.56 万 / 9,803 单 / 客单价 2,530.41 |
| 2 | GMV 最高的五天是哪几天 | Rule | 2024-03-16 居首 113,424.59 |
| 3 | 按月的 GMV 趋势如何 | Rule | 12 个月，5 月峰值 219.85 万 |
| 4 | 最近一个月每天的 GMV 走势 | Rule | 时间窗识别 → 末 30 天 |
| 5 | 各品类销售额排名 | Rule | 8 品类，运动户外第一 |
| 6 | 运动户外这个品类每天卖多少 | Rule | 实体优先路由 → 品类日明细 |
| 7 | 门店销售排行前十名 | Rule | Top10，开封社区店第一 |
| 8 | 浙江和广东哪个省卖得好 | Rule | 别名匹配 + 多省 IN 对比 |
| 9 | 各个渠道和支付方式的销售占比 | Rule | 16 组合 |
| 10 | 用户价值分层（RFM）各层有多少人 | Rule | 286/214/286/214 |
| 11 | 复购用户和单次用户有什么区别 | Rule | 全员复购（100%） |
| 12 | 哪几天 GMV 出现了骤降 | Rule | 11-06 -61.25% 居首 |

> 本次实测运行于未配置大模型密钥的环境，因此 12 问全部由规则引擎命中；LLM 链路代码已完整实现（`nl2sql_core.LLMEngine`、`nl2sql_langchain.py`），配置密钥后即可切换，`NL2SQL(prefer="llm")` 可强制走大模型。

## 8. 已知限制

- 规则引擎覆盖 13 类意图，超出范围的提问会返回引导式提示而非强行生成 SQL（宁可拒答不猜）；
- 不支持多轮上下文（同一会话中的"那上个月呢"这类指代无法解析）；
- SQL 未做代价估算，复杂明细查询可能触发 Hive 长查询，需配合 `LIMIT` 与超时（默认 180s）。
