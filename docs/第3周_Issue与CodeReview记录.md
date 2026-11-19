# 第 3 周 Git 协同实践记录

- 团队：200A　仓库：`git@github.com:wangzhida26/hive-project.git`（main 分支）
- 记录周期：第 3 周（DWS/ADS · 预测建模 · NL2SQL）
- 说明：本文件为课程要求的 **PR / Code Review / Issue 留痕**，所有记录均可通过 `git log --graph`、`git tag` 回溯验证。

---

## 一、工作流说明（如实记录环境约束）

任务书要求实践 Fork 工作流（Fork → Clone → PR → Review → Merge）。本课程环境为单机单账号（本地仓库直连自己的远程仓库，无第二位协作者账号），无法产生真实的跨仓库 Pull Request。因此采用**等效替代方案**，并保留完整可追溯的记录：

| Fork 工作流环节 | 本次替代做法 | 可追溯证据 |
| --- | --- | --- |
| Fork 主仓库 | 从 `main` 切出短生命周期的 `feature/*` 分支，视作隔离的开发副本 | `git branch` |
| 分支开发 + 多提交 | 两组任务各在自己的 feature 分支独立提交 | `git log --graph` |
| 发起 Pull Request | 用 `git merge --no-ff` 生成合并提交，提交信息即 PR 标题 | commit `b8d7437`、`3dbfb9f` |
| Code Review | 合并前逐文件评审，意见与响应记录于本文第三章 | 本文 + 后续修正提交 |
| 合并与冲突处理 | PR #2 合并时产生真实冲突并按规范解决 | 本文第四章 |
| 版本发布打 tag | `v1.0-week2`、`v2.0-week3` 两个附注标签 | `git tag -n` |

若需切换为真实 Fork 流程，操作路径为：GitHub 页面 Fork 仓库 → `git clone` 自己的副本 → 推 `feature/*` 分支 → 在源仓库发起 Pull Request → 评审通过后 Squash merge。本仓库的分支命名与提交粒度已按该流程的前置规范准备，可直接迁移。

---

## 二、Issue 清单

| ID | 类型 | 标题 | 标签 | 状态 | 关联提交 / 产物 |
| --- | --- | --- | --- | --- | --- |
| #1 | feature | DWS 汇总层与 ADS 应用层建模、核心 KPI 计算 | `feature` `dws` `ads` | Closed | `798f2f2`（sql/dws、sql/ads） |
| #2 | bug | 用户价值分层固定阈值区分度差，四层严重不均衡 | `bug` `ads` | Closed | `sql/ads/load_ads.sql` 改为四分位打分后重算 |
| #3 | feature | NL2SQL：Schema 抽取 + Prompt + 执行闭环 | `feature` `nl2sql` | Closed | `a00b8d4`（nl2sql/*） |
| #4 | bug | 规则引擎把「运动户外这个品类每天卖多少」误路由为全站趋势 | `bug` `nl2sql` `priority:high` | Closed | 实体分支前置，12 问复测全通过 |
| #5 | bug | 省份简称「浙江」匹配不到维度值「浙江省」 | `bug` `nl2sql` | Closed | 增加 `_alias()` 去行政区后缀 + `_pick_all()` 多实体 |
| #6 | feature | 时间序列预测建模与异常归因分析 | `feature` `analysis` | Closed | `c7fcbb7`（analysis/*） |
| #7 | bug | 归因报告中门店维度当日 GMV 全为 0，疑似关联失败 | `bug` `analysis` `invalid` | Closed（非缺陷） | 核查 `store_id` 关联命中率 100%，实为当日仅 17 单分散于 ~15 家门店的正常稀疏现象，归因口径改为「跌幅 Top N」 |
| #8 | docs | 第 3 周 AI 协同日志两分支同时追加导致合并冲突 | `docs` `conflict` | Closed | `3dbfb9f` 合并提交（解决过程见第四章） |
| #9 | tech-debt | 规则引擎 13 条 if-return 链式匹配，后续新增意图维护成本高 | `tech-debt` `nl2sql` | Open | 建议改造为「意图-正则-模板」字典路由表 |

> 标签体系：`feature` / `bug` / `docs` / `tech-debt` / `priority:high` / `invalid`。Issue #9 保持 Open 是刻意的——它是下一迭代的待办，不是本周交付缺陷。

---

## 三、Pull Request 与 Code Review 记录

### PR #1　feat(nl2sql): NL2SQL 双引擎与 LangChain 链路

- **来源分支**：`feature/nl2sql-engine` → `main`
- **改动规模**：10 文件 / +2118 行（含 Schema 快照与实测日志）
- **合并提交**：`b8d7437`（`--no-ff`，保留分支拓扑）
- **自检清单**：`nl2sql/out/nl2sql_run_log.md` 12 问 12 通过；`.env` 未入库；`.env.example` 提供模板

**Code Review 意见（评审人：分析组 / 王志达）**

| # | 文件:位置 | 意见 | 级别 | 处理结果 |
| --- | --- | --- | --- | --- |
| 1 | `nl2sql_core.py` `guard_sql()` | 仅做关键字黑名单不够，恶意/失控 SQL 可能全表扫描拖垮 HiveServer2，建议强制补 `LIMIT` | 必须修改 | **已修**：无 `LIMIT` 时自动追加 `LIMIT 200`；同时拒绝多语句（含分号） |
| 2 | `nl2sql_core.py` `RuleEngine.to_sql()` | 13 条 `if ... return` 顺序敏感，新增意图容易插错位置（Issue #4 就是这么出的） | 建议 | **部分采纳**：本周按优先级重排并加注释；字典化重构记入 Issue #9 |
| 3 | `nl2sql_core.py` 拼接 SQL 的品类/省份值 | 字符串拼接存在注入风险 | 必须确认 | **已评估接受**：取值来自 `domains()` 从 Hive 维度表读出的白名单，不含用户自由文本；已在代码注释说明该前提 |
| 4 | `nl2sql/schema_prompt.txt` | `dwd_order` 出现两次 `order_dt`（Hive `DESC` 输出含分区列与表列） | 建议 | **未修（Known Issue）**：属 Hive 元数据输出特性，重复列不影响生成质量，在 Schema 抽取器注释中说明 |
| 5 | `nl2sql/llm_ping.py` | 密钥打印需掩码 | 必须修改 | **已修**：`mask()` 只显示前 6 后 4 位；`.env` 已在 `.gitignore` |
| 6 | `nl2sql/out/nl2sql_run_log.md` | 需证明「提问→SQL→结果」闭环可现场演示 | 必须补充 | **已满足**：12 问全量日志含 SQL、结果表、耗时与汇总统计 |

**评审结论**：修改 #1、#5 后**通过**，允许合并。

### PR #2　feat(analysis): 时序预测建模与异常归因 + 两份报告

- **来源分支**：`feature/analytics-docs` → `main`
- **改动规模**：13 文件（脚本、4 张图、metrics.json、2 份 docx 与 md 源）
- **合并提交**：`3dbfb9f`（**合并时解决真实冲突**，见第四章）

**Code Review 意见（评审人：NL2SQL 组 / 陈劲松）**

| # | 文件:位置 | 意见 | 级别 | 处理结果 |
| --- | --- | --- | --- | --- |
| 1 | `forecast_gmv.py` 数据切分 | 时间序列不能用随机切分，否则未来信息泄漏 | 必须确认 | **已满足**：`feat.iloc[:-30]` / `iloc[-30:]` 时序切分 |
| 2 | `forecast_gmv.py` 模型评估 | 只看一个模型不够，需与朴素基线对比才有说服力 | 必须补充 | **已满足**：加入「昨日值」「7 日均值」两个基线，MAPE 17.42% vs 24.66% / 19.74% |
| 3 | `forecast_gmv.py` 可复现性 | 树模型需固定随机种子 | 必须修改 | **已满足**：`GradientBoostingRegressor(random_state=42, subsample=0.8)` |
| 4 | `04_预测建模分析报告.md` 第六章 | 必须写「模型适用边界」，AI 初稿的「可用于预算编制」属过度承诺 | 必须修改 | **已修**：明确「只适合 1~3 天资源预排，不适合预算承诺」，并披露递归预测误差累积 |
| 5 | `05_AI智能洞察与反思.md` | 摘要中的「广东消费力弱」「重要价值贡献 60%+」与数据不符 | 必须修改 | **已修**：广东仅 1 店（单店产出为均值 94.7%）、RFM 四层贡献 34.9%/25.7%/22.4%/17.0%，幻觉数字已更正并标注 ⚠ |
| 6 | `attribution_1106.sql` 门店维度 | 结果表出现大量 0 值，需确认是否关联失败 | 必须确认 | **已核查（Issue #7）**：`LEFT JOIN` 未命中数为 0，属当日订单稀疏；查询改为按跌幅排序取 Top N |

**评审结论**：修改 #4、#5 后**通过**，允许合并。

---

## 四、合并冲突的制造与解决（真实发生）

### 4.1 冲突成因

两个 feature 分支都从 `9097ed5`（主干日志只含记录 1-3）切出，并且**都向 `docs/第3周_AI协同日志.md` 的协同记录表末尾追加行**：

- `feature/nl2sql-engine`：追加记录 4（NL2SQL），并把分支说明写在表后；
- `feature/analytics-docs`：追加记录 5-6（建模与洞察），也把分支说明写在表后。

两条分支的修改落在同一文件、同一区段（表格末尾），Git 无法自动判定顺序，冲突必然发生。

### 4.2 冲突现场

```
$ git merge feature/analytics-docs
Auto-merging docs/第3周_AI协同日志.md
CONFLICT (content): Merge conflict in docs/第3周_AI协同日志.md
Automatic merge failed; fix conflicts and then commit the result.
```

冲突标记形态（节选）：

```
<<<<<<< HEAD
| 4 | 构建 NL2SQL：Schema 抽取 + Prompt 设计 + SQL 执行闭环 | ...
> 记录 4 由 feature/nl2sql-engine 分支补充（NL2SQL 组）；...
=======
| 5 | 时间序列建模：趋势/周期分析 + 未来 7 天 GMV 预测 | ...
| 6 | 生成自动经营摘要与 AI 反思文档 | ...
> 记录 5-6 由 feature/analytics-docs 分支补充（分析组）。
>>>>>>> feature/analytics-docs
```

### 4.3 解决决策与操作

**决策原则**：冲突双方内容并非互斥——一个是 NL2SQL 记录，一个是建模记录，业务上应当**并存**，且必须按序号 1→6 排列。因此不做"选一边"，而是**取并集 + 重排序**。

**操作步骤**：
1. `git status` 确认唯一冲突文件；
2. 逐段读取 `<<<<<<<` / `=======` / `>>>>>>>` 两侧内容，确认无相互否定的表述；
3. 按 "HEAD 侧（记录 4）→ 分支侧（记录 5-6）" 顺序拼接，删除两侧各自的分支说明行，替换为统一的合并说明；
4. 通读全文核对表格列数一致（5 列）、序号连续（1-6）；
5. `git add docs/第3周_AI协同日志.md` → `git commit` 生成合并提交 `3dbfb9f`；
6. 追加清理提交 `0ef62e7`，删除合并遗留的两条中间说明行，统一成一条合并说明（避免读者困惑）。

### 4.4 经验

- **粒度冲突优于语义冲突**：本次冲突纯粹是"追加位置"冲突，语义无矛盾，因此可以机械合并；若两分支修改同一段业务结论，就必须人工裁定而非取并集。
- **共享文件的追加应约定格式**：若事先约定"每人在表格末尾追加并用独立小节标注作者"，冲突仍会发生，但解决成本更低；更彻底的做法是把每人记录拆成独立文件（`logs/第3周_陈劲松.md`），从结构上消除冲突。
- **`--no-ff` 保留拓扑**：合并提交让"哪两支分支在何时合并"永久可查，是 PR 留痕的关键。

---

## 五、版本发布（tag）

| 标签 | 指向 | 状态 | 说明 |
| --- | --- | --- | --- |
| `v1.0-week2` | `9143e43` | 已打（本地） | 第 2 周交付：清洗管道、DWD 星型模型、三份报告 |
| `v2.0-week3` | 第 3 周合并后主干 | **待发布** | DWS/ADS 与 KPI、预测建模、NL2SQL、AI 洞察与反思、Git 协同记录；待团队检查完交付物后执行 `git tag -a v2.0-week3 -m "第3周交付"` |

查看命令：`git tag -n`、`git show v2.0-week3 --stat`。当前主干已包含第 3 周全部 7 个提交（含 2 个合并提交），**均未推送到远程**。

---

## 六、本周分支拓扑

```
*   3dbfb9f  Merge PR #2: 分析组报告与记录5-6（解决日志追加冲突）
|\
| * c7fcbb7  feat(analysis): 时序预测建模与异常归因，两份报告
* |   b8d7437  Merge PR #1: NL2SQL 引擎
|\ \
| * a00b8d4  feat(nl2sql): NL2SQL 双引擎与 LangChain 链路
|/
* 9097ed5  docs: 第3周 AI 协同日志（主干记录 1-3）
* 798f2f2  feat(dws,ads): DWS 五粒度汇总与 ADS 六张应用表
```

复核命令：`git log --graph --oneline --all -15`。
