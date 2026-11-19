# API 配置指南（第 4 周）

> 原则：所有密钥经环境变量注入，代码与编排文件中**零硬编码**；`.env` 不入 Git。

## 一、密钥与凭据清单

| 变量 | 用途 | 注入位置 | 泄露风险控制 |
| --- | --- | --- | --- |
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码 | compose `${VAR:-root}` | 生产改强密码并限内网 |
| `SUPERSET_SECRET_KEY` | Superset 会话/加密密钥 | compose 环境变量 | 生产换 32+ 位随机值 |
| `CLICKHOUSE_PASSWORD` | ClickHouse 密码 | compose / .env | 仅本机端口映射 |
| `DEEPSEEK_API_KEY` | 大模型 API Key（可选） | .env → app 容器 | 不入 Git、可随时轮换 |
| `DEEPSEEK_BASE_URL` | OpenAI 兼容接口地址 | .env | — |

## 二、.env 使用规范

1. `cp .env.example .env` 后按需修改；`.gitignore` 已排除 `.env`（第 7 行），提交前 `git status` 确认；
2. compose 中一律写作 `${VAR:-默认值}`：无 .env 时以默认值兜底（便于教学环境一键启动），生产必须覆盖默认值；
3. **密钥轮换**：修改 .env 后 `docker compose up -d` 重建对应服务即可生效；Superset 换 SECRET_KEY 后所有会话失效需重新登录；
4. **权限最小化**：MySQL 业务账号建议只授予 `ydsh_ads`/`ydsh_dws` 的 SELECT；root 仅用于元数据初始化。

## 三、大模型（NL2SQL LLM 引擎）接入

nl2sql 引擎为「双引擎」设计：配置了 Key 自动走 LLM 生成 SQL（带护栏校验），未配置或调用失败自动回退规则引擎——**问答功能在无 Key 环境下依然完整可用**（本周实测即以规则引擎跑通 12 问）。

```env
DEEPSEEK_API_KEY=sk-xxxxxxxx        # 在 https://platform.deepseek.com 申请
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

验证连通性：`python nl2sql/llm_ping.py`（输出 OK 即可用）。
护栏说明：所有生成的 SQL 必须通过 `guard_sql()` 白名单校验（仅 SELECT、
限定 ydsh_ads/ydsh_dws/ydsh_dwd 库、禁止 DDL/DML）后才执行。

## 四、执行后端环境变量（nl2sql_core）

| 变量 | 取值 | 说明 |
| --- | --- | --- |
| `NL2SQL_BACKEND` | `hive`（默认） | docker exec beeline 查 Hive，宿主机调试用 |
|  | `mysql` | 查 MySQL 报表镜像库（容器内 App 用），依赖 `mirror_to_mysql.py` 已执行 |
| `MYSQL_HOST/PORT/USER/PASSWORD` | — | mysql 后端的连接参数 |

## 五、服务访问入口速查

| 入口 | 地址 | 凭据 |
| --- | --- | --- |
| Superset 仪表板 | http://localhost:8088/superset/dashboard/1/ | admin / admin |
| Streamlit 问答 | http://localhost:8501 | 无 |
| HiveServer2 (JDBC) | jdbc:hive2://localhost:10000 | hive / 空 |
| ClickHouse HTTP | http://localhost:8123 | default / 见 .env |
| MySQL | localhost:3307 | root / 见 .env |
