# 第 4 周 AI 协同日志

> 项目：云购生活新零售企业——企业级数据仓库与经营分析可视化系统
> 团队：200A（陈劲松 / 王志达 / 刘畅 / 刘正扬）· 记录人：王志达
> 工具：WorkBuddy（Claude）· 主题：可视化实现（Superset + ECharts）· 项目部署（Docker）

## 一、协同记录表

| 序号 | 任务描述 | AI 产出 | 人工干预与修正 | 是否修改后采纳 |
| --- | --- | --- | --- | --- |
| 1 | Docker Compose 一键部署编排：在 Hive 栈基础上增加 Superset/ClickHouse/Streamlit 三服务 | 产出 docker-compose.yml（6 服务、全链路 healthcheck + depends_on）、.env.example、.dockerignore、app/Dockerfile | 人工要求 metastore 健康检查改 TCP 探测（beeline 无法探测 Thrift 9083 会误判不健康）；修正 app 构建上下文（nl2sql 在项目根，build context 必须为根目录） | 是（修改后） |
| 2 | Superset 连接数据源与仪表板（≥5 图表 + 联动） | 产出 mirror_to_mysql.py（Hive→MySQL 12 表镜像 + 省份省会坐标表）与 superset_setup.py（REST API 建库连接/5 数据集/6 图表/Dashboard/日期筛选器） | 实踩 4 个坑人工逐一纠偏：① 写接口 CSRF 需表单会话+每次刷新 token；② Superset 6.1 硬编码 `import MySQLdb`，pymysql 环境查询报错，容器内 sed 改为 pymysql；③ 初版容器重建丢数据（补 mysql_data 卷）；④ chart-dashboards 关联新版 API 只能逐图 PUT | 是（修改后） |
| 3 | ECharts 数据大屏（折线/柱状/地图/热力/散点/饼图/TopN + 自适应） | 产出 screen/（模板 + build_screen.py 装配脚本 + 合规的中国地图 GeoJSON），1920×1080 scale 缩放方案 | 地图数据选型人工把关：选用阿里 DataV 国家标准矢量（无境外瓦片、无密钥）；AI 初版把数据脚本注入 `</body>` 字符串替换，被 echarts 源码内含的 `'</body>'` 截断脚本导致大屏渲染成源码文本，人工定位后改为独立占位符注入；KPI 卡两处取列错误（人均订单/退款率）人工核对 CSV 表头后修正 | 是（修改后） |
| 4 | Streamlit 对话式问答（NL2SQL 闭环） | 产出 app/app.py（提问→SQL→表格+plotly 自动图表，历史对话/加载状态/错误提示）与容器化 Dockerfile | 人工要求 nl2sql_core 增加 NL2SQL_BACKEND 双后端（hive/mysql），使同一套问答代码宿主机连 Hive、容器内查 MySQL 镜像库 | 是（修改后） |
| 5 | 查询优化与压力测试 | 产出 stress_test.py（优化前后对比 + 并发 1/2/4/8 压测）与《第4周_压力测试记录.md》 | 人工指出初版脚本表名错误（ods_order_info→ods_order）；要求如实记录小数据量下收益有限（8.8%~11.2%）并给出瓶颈分析（beeline 启动基线 ~4s），不得夸大优化效果 | 是（修改后） |
| 6 | 部署手册与 API 配置指南 | 产出《部署手册.docx》（含大屏实测截图、6 条实踩问题）、《API配置指南.docx》（密钥清单/轮换/权限最小化） | 人工要求文档区分「实测通过」与「校验通过」两种状态，不虚构未执行的验证；editor_sdk 本周行为变化（create 后必须 open_file）由人工提示后修正构建脚本 | 是（修改后） |

## 二、数据自愈演练（本周重要里程碑）

部署验证时发现容器重建导致 Hive 元数据丢失（仅剩 default 库）。团队将事故转为演练：
`bash rebuild_pipeline.sh` 一键全链路重建（ODS→STG 三层清洗→DWD 星型模型→DWS→ADS），
**实测 3 分 22 秒恢复 366 分区，GMV 24,805,594.44 与重建前完全一致**，
并写入《部署手册》3.4 节第 6 条作为标准运维流程。

## 三、本周协同反思

1. **容器环境的"隐式状态"是本周最大风险源**：元数据无卷丢失、Superset 引擎缓存、
   pid 自锁三类问题都与容器生命周期有关，最终全部固化为「脚本可重跑」的解决路径；
2. **AI 生成代码的字符串注入类 bug 靠人工看渲染结果才发现**（大屏渲染出源码文本），
   说明可视化交付必须截图验证，不能只看"程序退出码为 0"；
3. 文档写作上人工坚持「数字必须来自实跑、状态必须区分实测/校验」，
   避免了周报式夸大（如未做连接池就声称"查询显著提速"）。

## 四、遗留事项

- Streamlit 网页截图因 WebSocket 加载时序未能在无头浏览器中完成，以实测记录替代，答辩现场演示；
- Superset 内嵌的 pandas 版本与 MySQL 8 认证缓存插件存在偶发重连延迟，已在手册中注明重启容器即可恢复；
- 生产化建议（连接池、HiveServer2 HA、ClickHouse 承接高频查询）见压力测试记录第三节。
