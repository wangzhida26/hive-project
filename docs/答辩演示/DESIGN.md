# DESIGN.md · 综合答辩演示（学术风）

## 全局视觉约定

- **画布**：1280×720，内容页 padding 左右 40、上下按学术母版（A3 页眉模式：深蓝顶条 + 低透明线稿区 y 0–72）
- **四区**：A 页眉 y 0–72（深蓝 #1E4FA8 顶条 + 白字页眉题）；C 内容区 y 80–660（背景 #FFFFFF / #F7F9FC）；D 页脚 y 660–700（左"云购生活数据仓库 · 200A"14px 灰，右页码 14px 深蓝）
- **配色**：主蓝 #1E4FA8（顶条/编号/强调）、藏蓝 #0E3F8C、浅蓝 #E8EFF8/#F0F5FC（卡底）、中蓝 #3D7BD9、警示红 #D9534F（≤3%）、数据黄 #FFC107（≤3%）、文本 #1A2230/#4A5568/#8B97A8、线框 #D6DCE5
- **字体**：思源黑体一套；封面中文主标 56px Bold、页面主标 32px Bold、卡内标题 24px Bold、正文 22px、表格 18–20px、注解/页脚 14px
- **视觉母题**：页面主标题下 1px 贯通细线（#D6DCE5），全篇仅主标题一处
- **配图**：全部真实系统截图/真实输出图（L1 统一为"真实系统证据"类）：大屏截图、架构图、预测拟合图、GMV 趋势图；不做营销插画

## 配图清单

| 文件 | 用途 | 使用页 |
| --- | --- | --- |
| assets/screen_shot.png | ECharts 数据大屏实测截图（1920×1080） | P12 可视化 |
| assets/architecture.png | 四层数仓架构图（make_arch.py 生成） | P6 全流程链路 |
| assets/fig_gmv_trend.png | GMV 趋势与 7 天预测图（真实输出） | P10 预测建模 |
| assets/fig_test_fit.png | 预测模型测试集拟合图（真实输出） | P10 预测建模 |

## 逐页设计（16 页）

| # | title | type | role | rhythm | layout | visual | anti_pattern | description |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 封面 | cover | hero | peak | 中央论文式标题+信息条 | 无图，深蓝顶条+浅蓝底纹 | 禁人物大头照、禁金装饰 | 项目中英文名、课程名、团队200A与四人分工、汇报人王志达、2026-11 |
| 2 | 目录 | catalog | supporting | valley | 左深蓝栏+右侧编号条目 | 无图 | 禁圆球编号 | 4 章：01 项目概览 / 02 数据治理与数仓建模 / 03 AI 分析与可视化 / 04 工程化与总结，各条目附一句摘要 |
| 3 | 01 项目概览 | section | transition | transition | 大数字+标题+要点 | 无图 | 禁四卡片预览 | 章节号01+业务痛点三连（数据孤岛/质量差/取数难） |
| 4 | 业务背景与需求 | content | supporting | valley | 双栏对照卡+底部结论条 | 无图 | 禁对称罗列N大优势 | 左卡四大痛点，右卡需求体系（7 BR/11 FR/5 NFR 摘要），底部结论：用统一数仓+AI问答解决 |
| 5 | 全流程数据链路 | content | supporting | valley | 横向节点串流程+底部指标锚点 | 无图（用流程组件） | 禁巨型架构图堆砌 | CSV→ODS→STG三站→DWD→DWS→ADS→三端应用，节点串+各层一句话职责，底部数字：15,600→14,696、366分区、6服务 |
| 6 | 系统总体架构 | content | supporting | valley | 大图配文 | architecture.png 占左55% | 禁文字压图 | 架构图+右侧文字：分层解耦/口径唯一/可复现三原则+技术栈摘要 |
| 7 | 02 数据治理与数仓建模 | section | transition | transition | 大数字+标题+要点 | 无图 | 禁四卡片预览 | 章节号02+五类脏数据/星型模型/分层规范要点 |
| 8 | 数据清洗成果 | content | supporting | valley | 表格页+结论条 | 无图 | 禁每卡各压结论 | 五类脏数据表（类别/规模/修复率100%），行数对账公式 15600-600=15000-304=14696，底部大额隔离口径说明 |
| 9 | 星型模型与分层 | content | supporting | valley | 左表格右要点 | 无图 | 禁表格铺满无结论 | DWD事实表+4维表设计（粒度/分区/ORC），DWS五粒度+ADS六集市一句话，分区裁剪4.90s vs 5.37s |
| 10 | 03 AI 分析与可视化 | section | transition | transition | 大数字+标题+要点 | 无图 | 禁四卡片预览 | 章节号03+预测/NL2SQL/三端可视化要点 |
| 11 | KPI 与预测建模 | content | supporting | peak | 双图横排+指标锚点 | fig_gmv_trend.png + fig_test_fit.png | 禁图表无洞察 | 11项KPI口径统一，3模型+2基线对比（ Holt 最优），7天预测与MAE/MAPE |
| 12 | NL2SQL 智能问答 | content | supporting | valley | 左流程右数据卡 | 无图 | 禁虚构演示数据 | 规则+LangChain双引擎、SQL护栏、双执行后端，12问实测通过，GMV 24,805,594.44 实测示例 |
| 13 | 三端可视化 | content | hero | peak | 大图配文 | screen_shot.png 占右58% | 禁空卡片 | Superset 6图表仪表板 / ECharts大屏合规地图 / Streamlit问答闭环，大屏截图为锚 |
| 14 | 04 工程化与总结 | section | transition | transition | 大数字+标题+要点 | 无图 | 禁四卡片预览 | 章节号04+一键部署/Git规范/文档体系要点 |
| 15 | 工程化实践与复盘 | content | supporting | valley | 三栏并列卡+底部结论条 | 无图 | 禁深蓝实色卡多张 | 一键部署（6服务healthcheck、3m22s重建）、Git规范（40+提交/2 PR/3标签/冲突留痕）、文档体系（5大文档+英文README），反思一句 |
| 16 | 感谢页 | ending | hero | peak | 中央致谢+问答引导 | 无图 | 禁烟花装饰 | 感谢聆听+恳请评审提问+团队署名 |

## 叙事节奏

transition(P3/7/10/14) → valley 内容页支撑 → P11/P13 两个 peak（真实图表与大屏截图高潮），符合学术答辩"证据驱动、全篇克制、局部高潮"。
