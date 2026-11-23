# Git 提交历史审查报告

**项目**：云购生活新零售企业——企业级数据仓库与经营分析可视化系统
**团队**：200A　|　**审查人**：王志达
**审查日期**：2026-11-23（第 5 周 · 综合冲刺）

## 一、审查方法

```bash
git log --oneline --graph --all     # 提交网络图
git branch -a                       # 分支结构
git log --pretty=format:"%h|%an|%ad|%s" --date=short   # 作者/日期/规范逐条核对
git log origin/main..main --oneline # 待推送提交
```

## 二、总体概况

| 维度 | 结果 |
| --- | --- |
| 总提交数 | 40+ 个（第 1~5 周，主干线性推进 + 2 次真实 PR 合并） |
| 分支结构 | main（主干）+ feature/nl2sql-engine + feature/analytics-docs（均已合并） |
| 标签 | v1.0-week2 / v2.0-week3 / v3.0-week4，里程碑清晰 |
| 提交规范 | Conventional Commits（feat/fix/docs/chore + scope），全量核对通过 |
| 合并留痕 | Merge PR #1（NL2SQL 引擎）、Merge PR #2（分析组报告，解决日志追加冲突） |

## 三、逐周审查结论

| 周次 | 提交范围 | 结论 |
| --- | --- | --- |
| 第 1 周 | a37a130 ~ beddeac（14 个） | 初始化→环境→ODS→质检→清洗→文档，每功能独立提交，符合规范 |
| 第 2 周 | 5849f83 ~ a7a627d（7 个） | 清洗进阶→DWD 建模→EDA→三份报告，feat/docs 分离清晰 |
| 第 3 周 | 798f2f2 ~ cd7d7d0（11 个） | 双 feature 分支开发 + 2 次真实 Merge PR，含真实合并冲突解决记录 |
| 第 4 周 | 6ef2048 ~ 2a748e1（7 个） | 部署/大屏/NL2SQL 后端/镜像/压测按模块独立提交 |
| 第 5 周 | （本次新增） | 联调核对报告、三大文档 v2.0、英文 README、Git 审查、答辩 PPT、反思日志 |

## 四、PR / Issue 记录整理

| 编号 | 类型 | 内容 | 留痕位置 |
| --- | --- | --- | --- |
| PR #1 | Merge | feature/nl2sql-engine → main，NL2SQL 双引擎（Code Review 通过） | Merge PR #1 提交 + docs/第3周_Issue与CodeReview记录.md |
| PR #2 | Merge | feature/analytics-docs → main，预测建模与 AI 反思报告；与 PR #1 在 AI 日志追加处产生真实冲突，保留双方记录并按序号排序解决 | Merge PR #2 提交 + 冲突解决说明 |
| Issue-1 | 记录 | 动态分区默认上限 100 导致 366 分区装载失败 | docs/环境搭建笔记.docx |
| Issue-2 | 记录 | Hadoop 回收站导致 DROP 后同名表读旧数据（改为 DROP PURGE） | docs/环境搭建笔记.docx + 数仓架构设计文档 |
| Issue-3 | 记录 | beeline 良性 WARN 干扰重建脚本错误检测（改为精确匹配） | rebuild_pipeline.sh 注释 + 部署手册 |

## 五、规范符合性核对

| 检查项 | 结果 |
| --- | --- |
| 约定式提交（type(scope): subject） | ✅ 全部符合（2 条 Merge 提交为 Git 原生合并提交，属正常） |
| 功能模块独立提交 | ✅ deploy/nl2sql/screen/analysis/kpi 按模块分开 |
| 分支命名规范（feature/xxx） | ✅ 两个 feature 分支均已合并后保留 |
| 合并冲突真实留痕 | ✅ PR #2 冲突解决过程记录完整 |
| 敏感信息检查 | ✅ .env 不入库（提供 .env.example）、驱动 jar 已移出、数据 CSV 被 .gitignore 忽略 |
| 提交信息语言统一 | ✅ 中文 subject + 英文 type，可读性好 |

## 六、结论

主干历史清晰线性、分支结构规范、PR/Issue 留痕完整、无敏感信息泄露。Git 工程化规范满足综合答辩评审要求；后续推送前将统一审查待推送提交（第 4 周 7 个 + 第 5 周新增）。
