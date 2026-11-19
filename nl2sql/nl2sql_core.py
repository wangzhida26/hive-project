"""
NL2SQL 引擎（双引擎架构）
==================================================
Engine A  LLMEngine  —— OpenAI 兼容接口（DeepSeek / 通义 / 智谱 / OpenAI），
                        Schema 注入 + Few-shot + 严格约束，把自然语言翻译成 Hive SQL
Engine B  RuleEngine —— 离线规则引擎，关键词 + 实体抽取匹配查询模板，
                        无需任何网络与密钥，用于现场演示与 LLM 不可用时的兜底

两者共用 Executor（beeline 执行 + CSV 解析）与 Guard（SQL 安全校验）。

密钥管理：.env 文件中 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL，
         代码不硬编码任何密钥，.env 不入版本库（已写入 .gitignore）。
"""
from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
SCHEMA_FILE = BASE / "schema_prompt.txt"

load_dotenv(BASE / ".env")

BEELINE = [
    "docker", "exec", "hive-server", "beeline",
    "-u", "jdbc:hive2://localhost:10000", "-n", "hive",
    "--silent=true", "--outputformat=csv2",
]


# ----------------------------------------------------------------------------
# 1. SQL 安全护栏
# ----------------------------------------------------------------------------
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|load|overwrite|grant|revoke)\b",
    re.IGNORECASE,
)


class SQLGuardError(ValueError):
    pass


def guard_sql(sql: str) -> str:
    """只允许单条只读 SELECT，禁止任何写操作，强制补 LIMIT。"""
    s = sql.strip().rstrip(";").strip()
    s = re.sub(r"^```(?:sql)?|```$", "", s, flags=re.MULTILINE).strip()
    if not s:
        raise SQLGuardError("生成结果为空")
    if ";" in s:
        raise SQLGuardError("只允许单条 SQL（检测到分号分隔的多语句）")
    head = s.split(None, 1)[0].upper()
    if head not in ("SELECT", "WITH"):
        raise SQLGuardError(f"只允许 SELECT 查询，实际为 {head}")
    hit = FORBIDDEN.search(s)
    if hit:
        raise SQLGuardError(f"检测到禁止的关键字：{hit.group(0)}")
    if not re.search(r"\blimit\b", s, re.IGNORECASE):
        s += "\nLIMIT 200"
    return s


# ----------------------------------------------------------------------------
# 2. 执行器
# ----------------------------------------------------------------------------
_SCI = re.compile(r"^-?\d+(\.\d+)?[eE]\+?\d+$")


def fmt_cell(v: str) -> str:
    """把 Hive double 的科学计数法还原成可读小数。"""
    t = str(v).strip()
    if _SCI.match(t):
        try:
            f = float(t)
            return f"{f:,.2f}" if abs(f) >= 1000 else f"{f:.4f}".rstrip("0").rstrip(".")
        except ValueError:
            return t
    return t


@dataclass
class QueryResult:
    sql: str
    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    elapsed: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_markdown(self, max_rows: int = 10) -> str:
        if not self.ok:
            return f"执行失败：{self.error}"
        if not self.rows:
            return "_（查询成功但无数据）_"
        head = "| " + " | ".join(self.columns) + " |"
        sep = "| " + " | ".join(["---"] * len(self.columns)) + " |"
        body = [
            "| " + " | ".join(fmt_cell(c) for c in r) + " |"
            for r in self.rows[:max_rows]
        ]
        tail = "" if len(self.rows) <= max_rows else f"\n\n_（共 {len(self.rows)} 行，仅展示前 {max_rows} 行）_"
        return "\n".join([head, sep, *body]) + tail


def run_hive(sql: str, timeout: int = 180) -> QueryResult:
    t0 = time.time()
    try:
        proc = subprocess.run(
            BEELINE + ["-e", sql],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
            env={**os.environ, "MSYS_NO_PATHCONV": "1", "MSYS2_ARG_CONV_EXCL": "*"},
        )
    except subprocess.TimeoutExpired:
        return QueryResult(sql=sql, error=f"查询超时（>{timeout}s）", elapsed=time.time() - t0)

    raw = "\n".join(
        ln for ln in (proc.stdout or "").splitlines()
        if not re.search(r"SLF4J|^\s*$|WARN|INFO\s", ln)
    )
    elapsed = time.time() - t0

    if proc.returncode != 0 and not raw:
        msg = (proc.stderr or "").strip().splitlines()
        return QueryResult(sql=sql, error=msg[-1] if msg else "beeline 返回非零", elapsed=elapsed)

    rows = list(csv.reader(io.StringIO(raw)))
    if not rows:
        return QueryResult(sql=sql, error="无返回内容（可能是 SQL 语法错误）", elapsed=elapsed)
    cols = [c.strip().split(".")[-1] for c in rows[0]]
    vals = [[c.strip() for c in r] for r in rows[1:] if r and any(x.strip() for x in r)]
    return QueryResult(sql=sql, columns=cols, rows=vals, elapsed=elapsed)


def run_mysql(sql: str, timeout: int = 180) -> QueryResult:
    """MySQL 后端（报表镜像库）：容器内 Streamlit App / 无 Docker CLI 环境使用。"""
    import pymysql

    t0 = time.time()
    try:
        conn = pymysql.connect(
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("MYSQL_PORT", "3307")),
            user=os.environ.get("MYSQL_USER", "root"),
            password=os.environ.get("MYSQL_PASSWORD", "root"),
            charset="utf8mb4", connect_timeout=10,
        )
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
        conn.close()
        # 与 Hive 侧统一：数值列格式化为字符串（保持 fmt_cell 兼容）
        vals = [[("" if v is None else f"{v:.6g}" if isinstance(v, float) else str(v)) for v in r]
                for r in rows]
        return QueryResult(sql=sql, columns=cols, rows=vals, elapsed=time.time() - t0)
    except Exception as exc:
        return QueryResult(sql=sql, error=f"{type(exc).__name__}: {exc}", elapsed=time.time() - t0)


# 执行后端：hive（默认，docker exec beeline）| mysql（报表镜像库）
EXEC_BACKEND = os.environ.get("NL2SQL_BACKEND", "hive")


def run_query(sql: str, timeout: int = 180) -> QueryResult:
    return run_mysql(sql, timeout) if EXEC_BACKEND == "mysql" else run_hive(sql, timeout)


# ----------------------------------------------------------------------------
# 3. 域值清单（供 Prompt 与实体抽取使用）
# ----------------------------------------------------------------------------
DOMAIN_QUERIES = {
    "category": "SELECT DISTINCT category FROM ydsh_ads.ads_category_sales ORDER BY category",
    "province": "SELECT DISTINCT province FROM ydsh_ads.ads_store_sales ORDER BY province",
    "store": "SELECT DISTINCT store_name FROM ydsh_ads.ads_store_sales ORDER BY store_name",
    "channel": "SELECT DISTINCT channel FROM ydsh_ads.ads_channel_sales ORDER BY channel",
}
_domain_cache: dict[str, list[str]] = {}


def domains(refresh: bool = False) -> dict[str, list[str]]:
    if _domain_cache and not refresh:
        return _domain_cache
    for k, sql in DOMAIN_QUERIES.items():
        r = run_query(sql, timeout=60)
        _domain_cache[k] = [row[0] for row in r.rows if row] if r.ok else []
    return _domain_cache


# ----------------------------------------------------------------------------
# 4. Engine A：大模型
# ----------------------------------------------------------------------------
SYSTEM_PROMPT = """你是资深数据仓库工程师，负责把业务人员的自然语言问题翻译成 Apache Hive SQL。

严格规则：
1. 只能输出一条 SELECT 语句，禁止任何写操作（INSERT/UPDATE/DELETE/DROP/ALTER/CREATE）。
2. 只能使用下面 Schema 中出现的库名、表名、列名，不得臆造字段。
3. 优先查询已聚合好的 ADS/DWS 表，只有需要明细维度时才查 DWD 表。
4. Hive 语法要点：日期是 string 类型，用 'yyyy-MM-dd' 字面量比较；分页用 LIMIT；不能用 MySQL 的 DATE_FORMAT 之外的非 Hive 函数。
5. 除 SQL 外不要输出任何解释文字，不要用 markdown 代码块包裹。

【数据库 Schema】
{schema}

【业务口径】
- 有效订单 = order_status IN ('已支付','已完成')；有效 GMV 同理。
- 客单价 = 有效GMV / 有效订单量。
- week_day 采用 Hive dayofweek：1=周日 … 7=周六。
- RFM 基准日固定为 2024-12-31。
- “大额异常”订单已在 DWD 层过滤，无需再处理。

【示例】
问：整体经营大盘怎么样？
答：SELECT * FROM ydsh_ads.ads_kpi_overview;

问：GMV最高的5天是哪几天？
答：SELECT order_dt, gmv, orders, aov FROM ydsh_ads.ads_gmv_daily ORDER BY gmv DESC LIMIT 5;

问：各品类销售额排名
答：SELECT rk, category, gmv, share_pct FROM ydsh_ads.ads_category_sales ORDER BY rk;

问：浙江和广东哪个省卖得好
答：SELECT province, SUM(gmv) AS gmv, SUM(orders) AS orders FROM ydsh_dws.dws_store_1d WHERE province IN ('浙江','广东') GROUP BY province ORDER BY gmv DESC;
"""


class LLMEngine:
    name = "LLM"

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        self.model = os.getenv("OPENAI_MODEL", "deepseek-chat").strip()
        self.schema = SCHEMA_FILE.read_text(encoding="utf-8")
        self.available = bool(self.api_key) and not self.api_key.startswith("sk-your")

    def status(self) -> str:
        if self.available:
            return f"已启用（model={self.model}, base={self.base_url or '默认'}）"
        return "未配置密钥（将回退规则引擎）"

    def to_sql(self, question: str) -> str:
        if not self.available:
            raise RuntimeError("LLM 未配置")
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        resp = client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=600,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(schema=self.schema)},
                {"role": "user", "content": question},
            ],
        )
        return (resp.choices[0].message.content or "").strip()


# ----------------------------------------------------------------------------
# 5. Engine B：规则引擎（离线兜底）
# ----------------------------------------------------------------------------
class RuleEngine:
    name = "Rule"

    def __init__(self) -> None:
        self._dom = domains()

    # ---- 实体抽取 ----
    _GEO_SUFFIX = re.compile(r"(维吾尔自治区|壮族自治区|回族自治区|特别行政区|自治区|省|市)$")

    def _alias(self, v: str) -> str:
        """省份全称 → 常用简称：浙江省 → 浙江，广西壮族自治区 → 广西。"""
        return self._GEO_SUFFIX.sub("", v)

    def _pick_all(self, q: str, kind: str) -> list[str]:
        """返回问题中出现的全部实体（支持「浙江和广东」这类多实体对比）。"""
        hits: list[str] = []
        for v in self._dom.get(kind, []):
            if not v:
                continue
            keys = {v, self._alias(v)}
            if any(k and k in q for k in keys):
                hits.append(v)
        # 长名优先，避免「北京」与「北京二店」这类包含关系误配
        return sorted(hits, key=len, reverse=True)

    def _pick(self, q: str, kind: str) -> str | None:
        hits = self._pick_all(q, kind)
        return hits[0] if hits else None

    def _topn(self, q: str, default: int = 10) -> int:
        m = re.search(r"(?:前|top\s*)(\d+)", q, re.IGNORECASE)
        return int(m.group(1)) if m else default

    def _month(self, q: str) -> str | None:
        m = re.search(r"(20\d{2})\s*[-年/]\s*(\d{1,2})", q)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}"
        m = re.search(r"(\d{1,2})\s*月", q)
        if m:
            return f"2024-{int(m.group(1)):02d}"
        return None

    def _recent_days(self, q: str) -> int | None:
        """识别「最近N天 / 近一周 / 近一个月 / 近一季度」时间窗口。"""
        m = re.search(r"(?:最近|近|last)\s*(\d+)\s*天", q)
        if m:
            return int(m.group(1))
        if re.search(r"(?:最近|近)\s*(?:一|1)?\s*周|近7天", q):
            return 7
        if re.search(r"(?:最近|近)\s*(?:一|1)?\s*(?:个)?月|近30天", q):
            return 30
        if re.search(r"(?:最近|近)\s*(?:一|1)?\s*(?:个)?季度|近90天", q):
            return 90
        return None

    # ---- 规则匹配 ----
    def to_sql(self, question: str) -> str:
        q = question.strip()
        ql = q.lower()

        # 1) 大盘 / 核心 KPI
        if re.search(r"大盘|总览|概览|核心指标|kpi|整体(表现|经营|情况)|经营(情况|状况)", ql):
            return "SELECT * FROM ydsh_ads.ads_kpi_overview"

        # 2) 用户价值 / RFM 分层
        if re.search(r"rfm|用户价值|分层|重要价值|流失预警|高价值用户", ql):
            return (
                "SELECT segment, COUNT(*) AS users, "
                "ROUND(AVG(recency),1) AS avg_r, ROUND(AVG(frequency),1) AS avg_f, "
                "ROUND(AVG(monetary),2) AS avg_m, ROUND(SUM(monetary),2) AS gmv "
                "FROM ydsh_ads.ads_user_value GROUP BY segment ORDER BY gmv DESC"
            )

        # 3) 复购
        if re.search(r"复购|重复购买|二次购买", ql):
            return (
                "SELECT repurchase_flag, COUNT(*) AS users, "
                "ROUND(AVG(orders),1) AS avg_orders, ROUND(AVG(gmv),2) AS avg_gmv "
                "FROM ydsh_dws.dws_user_agg GROUP BY repurchase_flag ORDER BY repurchase_flag DESC"
            )

        # 4) 骤降 / 最低 / 异常
        if re.search(r"骤降|暴跌|下降最多|跌幅|最低|最差|异常", ql):
            return (
                "SELECT order_dt, gmv, orders, aov, ROUND(dod_pct,2) AS dod_pct "
                "FROM ydsh_ads.ads_gmv_daily ORDER BY dod_pct ASC LIMIT 5"
            )

        # 5) 峰值 / 最高
        if re.search(r"最高|峰值|最好|最多.*(天|日)|top", ql) and re.search(r"(天|日|日期)", q):
            return (
                "SELECT order_dt, gmv, orders, aov FROM ydsh_ads.ads_gmv_daily "
                "ORDER BY gmv DESC LIMIT 5"
            )

        # 5.5) 点名了具体实体（品类/省份/门店）→ 优先查该实体，避免被「每天/趋势」抢走
        cat = self._pick(q, "category")
        if cat:
            month = self._month(q)
            cond = f" AND order_dt LIKE '{month}%'" if month else ""
            return (
                "SELECT order_dt, ROUND(gmv,2) AS gmv, qty, orders FROM ydsh_dws.dws_category_1d "
                f"WHERE category='{cat}'{cond} ORDER BY order_dt DESC LIMIT 60"
            )
        provs = self._pick_all(q, "province")
        if provs:
            lst = ",".join(f"'{p}'" for p in provs)
            return (
                "SELECT province, ROUND(SUM(gmv),2) AS gmv, SUM(orders) AS orders, "
                "ROUND(SUM(gmv)/(SELECT SUM(gmv) FROM ydsh_dws.dws_store_1d)*100,2) AS share_pct "
                f"FROM ydsh_dws.dws_store_1d WHERE province IN ({lst}) "
                "GROUP BY province ORDER BY gmv DESC"
            )
        store = self._pick(q, "store")
        if store:
            return (
                "SELECT order_dt, ROUND(gmv,2) AS gmv, orders, users FROM ydsh_dws.dws_store_1d "
                f"WHERE store_name='{store}' ORDER BY order_dt DESC LIMIT 30"
            )

        # 6) 趋势 / 日度（全站口径）
        if re.search(r"趋势|走势|逐日|每天|日均|日度|月度|按月|每月", ql):
            month = self._month(q)
            if re.search(r"月度|按月|每月", ql):
                return (
                    "SELECT SUBSTR(order_dt,1,7) AS ym, ROUND(SUM(gmv),2) AS gmv, "
                    "SUM(orders) AS orders, ROUND(SUM(gmv)/SUM(orders),2) AS aov "
                    "FROM ydsh_ads.ads_gmv_daily GROUP BY SUBSTR(order_dt,1,7) ORDER BY ym"
                )
            if month:
                return (
                    "SELECT order_dt, gmv, orders, aov, ROUND(ma7,2) AS ma7, ROUND(dod_pct,2) AS dod_pct "
                    f"FROM ydsh_ads.ads_gmv_daily WHERE order_dt LIKE '{month}%' ORDER BY order_dt"
                )
            days = self._recent_days(q)
            if days:
                return (
                    "SELECT order_dt, gmv, orders, aov, ROUND(ma7,2) AS ma7, ROUND(dod_pct,2) AS dod_pct "
                    f"FROM (SELECT * FROM ydsh_ads.ads_gmv_daily ORDER BY order_dt DESC LIMIT {days}) t "
                    "ORDER BY order_dt"
                )
            return (
                "SELECT order_dt, gmv, orders, aov, ROUND(ma7,2) AS ma7, ROUND(dod_pct,2) AS dod_pct "
                "FROM ydsh_ads.ads_gmv_daily ORDER BY order_dt"
            )

        # 7) 品类排名
        if re.search(r"品类|类目|分类|商品类|哪个类", ql):
            return "SELECT rk, category, gmv, qty, orders, share_pct FROM ydsh_ads.ads_category_sales ORDER BY rk"

        # 8) 渠道 / 支付方式
        if re.search(r"渠道|支付方式|付款方式", ql):
            return (
                "SELECT channel, pay_type, gmv, orders, share_pct "
                "FROM ydsh_ads.ads_channel_sales ORDER BY gmv DESC"
            )

        # 9) 省份 / 区域排行
        if re.search(r"省份|省|地区|区域|地域|哪个城市", ql):
            return (
                "SELECT province, ROUND(SUM(gmv),2) AS gmv, SUM(orders) AS orders, "
                f"ROUND(SUM(gmv)/(SELECT SUM(gmv) FROM ydsh_dws.dws_store_1d)*100,2) AS share_pct "
                "FROM ydsh_dws.dws_store_1d GROUP BY province ORDER BY gmv DESC"
            )

        # 10) 门店排行
        if re.search(r"门店|店铺|哪个店", ql):
            n = self._topn(q, 10)
            return (
                "SELECT rk, store_name, province, city, gmv, orders, users "
                f"FROM ydsh_ads.ads_store_sales ORDER BY rk LIMIT {n}"
            )

        # 11) 客单价
        if re.search(r"客单价|单价|平均每单|件单价", ql):
            return (
                "SELECT order_dt, ROUND(aov,2) AS aov, orders, ROUND(gmv,2) AS gmv "
                "FROM ydsh_dws.dws_order_1d ORDER BY order_dt DESC LIMIT 30"
            )

        # 12) 取消率 / 退款
        if re.search(r"取消|退款", ql):
            return (
                "SELECT order_dt, orders, refund_orders, ROUND(cancel_rate,4) AS cancel_rate, "
                "ROUND(gmv,2) AS gmv FROM ydsh_dws.dws_order_1d ORDER BY cancel_rate DESC LIMIT 10"
            )

        # 13) 兜底：给可行的问法提示
        return (
            "SELECT '未能识别该问题，请换一种问法' AS hint, "
            "'可问：大盘怎么样 / GMV趋势 / 品类排名 / 门店排名 / 渠道占比 / 用户价值分层 / GMV骤降日' AS examples"
        )


# ----------------------------------------------------------------------------
# 6. 统一入口
# ----------------------------------------------------------------------------
@dataclass
class Answer:
    question: str
    engine: str
    sql: str
    result: QueryResult
    fallback_note: str = ""

    def render(self) -> str:
        parts = [
            f"### 问：{self.question}",
            f"**引擎**：{self.engine}" + (f"（{self.fallback_note}）" if self.fallback_note else ""),
            "",
            "```sql",
            self.sql.strip(),
            "```",
            "",
            self.result.to_markdown(),
            "",
            f"_耗时 {self.result.elapsed:.2f}s_",
        ]
        return "\n".join(parts)


class NL2SQL:
    def __init__(self, prefer: str = "auto") -> None:
        self.llm = LLMEngine()
        self.rule = RuleEngine()
        self.prefer = prefer

    def status(self) -> str:
        return f"LLM {self.llm.status()}；规则引擎已加载（品类/省份/门店/渠道域值已缓存）"

    def ask(self, question: str, verbose: bool = True) -> Answer:
        note = ""
        engine = "Rule"
        sql = ""

        if self.prefer in ("auto", "llm") and self.llm.available:
            engine = "LLM"
            try:
                sql = guard_sql(self.llm.to_sql(question))
            except Exception as exc:  # 网络/额度/格式任一异常都回退
                note = f"LLM 调用或校验失败：{type(exc).__name__}，已回退规则引擎"
                engine = "Rule"
                sql = ""

        if not sql:
            sql = guard_sql(self.rule.to_sql(question))

        res = run_query(sql)
        if verbose:
            print(f"[{engine}] {question}\n{'=' * 70}\n{sql}\n{'-' * 70}")
            print(res.to_markdown() if res.ok else f"ERROR: {res.error}")
            print()
        return Answer(question=question, engine=engine, sql=sql, result=res, fallback_note=note)


if __name__ == "__main__":
    import sys

    nl = NL2SQL()
    print("引擎状态：", nl.status())
    q = " ".join(sys.argv[1:]) or "整体经营大盘怎么样"
    nl.ask(q).render()
