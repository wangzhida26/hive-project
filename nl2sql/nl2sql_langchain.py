"""
NL2SQL —— LangChain LCEL 版本（子任务 4 要求）
==================================================
链路：问题 → Prompt(含 Schema + Few-shot) → ChatOpenAI → StrOutputParser
      → SQL 安全护栏 → Hive 执行器(RunnableLambda) → 结构化结果

说明：
1. 环境中的 Hive 不提供可用的 DBAPI 驱动（无 pyhive/thrift 侧连接），
   LangChain 内置的 SQLDatabase 工具无法直接接管执行环节，
   因此执行器用 RunnableLambda 封装 beeline，链路本身仍是标准 LCEL。
2. 若要切换到 MySQL 等有 DBAPI 的数据源，只需把 execute 换成 SQLDatabase.run，
   链的其余部分无需改动 —— 这是把执行器抽成独立 Runnable 的原因。

用法：
    python nl2sql_langchain.py "按月的 GMV 趋势如何"
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI

from nl2sql_core import SCHEMA_FILE, Answer, RuleEngine, domains, guard_sql, run_hive

load_dotenv(Path(__file__).resolve().parent / ".env")

# ---------------------------------------------------------------- Prompt
SYSTEM_TEMPLATE = """你是资深数据仓库工程师，把业务问题翻译成一条 Apache Hive SQL。

规则：
1. 只输出一条 SELECT，禁止 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE。
2. 只能使用下面 Schema 中真实存在的库名、表名、列名，不得臆造字段。
3. 优先用已聚合的 ADS/DWS 表；需要明细维度时才查 DWD。
4. 日期是 string 类型，用 'yyyy-MM-dd' 字面量比较；分页用 LIMIT。
5. 除 SQL 外不输出任何解释，不用 markdown 代码块。

【Schema】
{schema}

【业务口径】
- 有效订单 = order_status IN ('已支付','已完成')，有效 GMV 同理。
- 客单价 = 有效 GMV / 有效订单量。
- weekday 用 Hive dayofweek：1=周日 … 7=周六。
- RFM 基准日 2024-12-31。
"""

EXAMPLES = [
    {"question": "整体经营大盘怎么样",
     "answer": "SELECT * FROM ydsh_ads.ads_kpi_overview"},
    {"question": "GMV 最高的五天",
     "answer": "SELECT order_dt, gmv, orders FROM ydsh_ads.ads_gmv_daily ORDER BY gmv DESC LIMIT 5"},
    {"question": "各品类销售额排名",
     "answer": "SELECT rk, category, gmv, share_pct FROM ydsh_ads.ads_category_sales ORDER BY rk"},
    {"question": "广东省销售额是多少",
     "answer": "SELECT province, ROUND(SUM(gmv),2) AS gmv, SUM(orders) AS orders "
               "FROM ydsh_dws.dws_store_1d WHERE province='广东省' GROUP BY province"},
]

few_shot = FewShotChatMessagePromptTemplate(
    example_prompt=ChatPromptTemplate.from_messages(
        [("human", "{question}"), ("ai", "{answer}")]
    ),
    examples=EXAMPLES,
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_TEMPLATE),
        few_shot,
        ("human", "{question}"),
    ]
)


# ---------------------------------------------------------------- 执行器
def _execute(sql: str) -> dict:
    res = run_hive(sql)
    return {"sql": sql, "result": res}


def build_chain(api_key: str, base_url: str | None, model: str):
    """构建 LCEL 链：prompt → llm → 字符串 → 护栏 → 执行。"""
    llm = ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=0)
    return (
        RunnablePassthrough.assign(schema=lambda _: SCHEMA_FILE.read_text(encoding="utf-8"))
        | prompt
        | llm
        | StrOutputParser()
        | RunnableLambda(guard_sql)
        | RunnableLambda(_execute)
    )


class LangChainEngine:
    """与 nl2sql_core.LLMEngine 同接口，可直接替换进 NL2SQL 调度器。"""

    name = "LangChain"

    def __init__(self) -> None:
        import os

        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
        self.model = os.getenv("OPENAI_MODEL", "deepseek-chat").strip()
        self.available = bool(self.api_key) and not self.api_key.startswith("sk-your")
        self.chain = build_chain(self.api_key, self.base_url, self.model) if self.available else None

    def to_sql(self, question: str) -> str:
        """只取 SQL（不执行），便于复用 nl2sql_core.NL2SQL 的统一调度。"""
        if not self.chain:
            raise RuntimeError("LLM 未配置")
        # 复用同一条链，但只跑到生成 SQL 这一段
        gen = (
            RunnablePassthrough.assign(schema=lambda _: SCHEMA_FILE.read_text(encoding="utf-8"))
            | prompt
            | ChatOpenAI(model=self.model, api_key=self.api_key, base_url=self.base_url, temperature=0)
            | StrOutputParser()
            | RunnableLambda(guard_sql)
        )
        return gen.invoke({"question": question})


def demo(question: str) -> None:
    eng = LangChainEngine()
    if not eng.available:
        # 无密钥时用规则引擎跑通链路，证明「问题→SQL→结果」闭环可用
        print("[LangChain 未配置密钥] 回退规则引擎演示闭环\n")
        rule = RuleEngine()
        sql = guard_sql(rule.to_sql(question))
        ans = Answer(question=question, engine="Rule(through LCEL shell)",
                     sql=sql, result=run_hive(sql))
        print(ans.render())
        return
    out = eng.chain.invoke({"question": question})
    print("SQL:\n" + out["sql"])
    print(out["result"].to_markdown())


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "整体经营大盘怎么样"
    print("域值缓存：", {k: len(v) for k, v in domains().items()})
    demo(q)
