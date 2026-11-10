"""
NL2SQL 典型问题实测脚本
==================================================
跑 12 个业务人员真实会问的问题，逐条记录：问题 / 命中引擎 / 生成 SQL / 结果表 / 耗时，
输出到 out/nl2sql_run_log.md，作为《NL2SQL 实测运行日志》交付。

用法：
    python test_nl2sql.py           # auto：优先大模型，未配密钥则规则引擎
    python test_nl2sql.py rule      # 强制规则引擎（离线演示）
    python test_nl2sql.py llm       # 强制大模型（无密钥会报错）
"""
from __future__ import annotations

import io
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nl2sql_core import NL2SQL  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

QUESTIONS = [
    "整体经营大盘怎么样",
    "GMV 最高的五天是哪几天",
    "按月的 GMV 趋势如何",
    "最近一个月每天的 GMV 走势",
    "各品类销售额排名",
    "运动户外这个品类每天卖多少",
    "门店销售排行前十名",
    "浙江和广东哪个省卖得好",
    "各个渠道和支付方式的销售占比",
    "用户价值分层（RFM）各层有多少人",
    "复购用户和单次用户有什么区别",
    "哪几天 GMV 出现了骤降",
]


def main() -> None:
    prefer = sys.argv[1] if len(sys.argv) > 1 else "auto"
    nl = NL2SQL(prefer=prefer)
    started = datetime.now()

    lines = [
        "# NL2SQL 实测运行日志",
        "",
        f"- 运行时间：{started:%Y-%m-%d %H:%M:%S}",
        f"- 引擎状态：{nl.status()}",
        f"- 运行模式：{prefer}",
        f"- 问题数：{len(QUESTIONS)}",
        "",
        "---",
        "",
    ]

    head_len = len(lines)
    stats = {"ok": 0, "fail": 0, "llm": 0, "rule": 0, "elapsed": 0.0}
    for i, q in enumerate(QUESTIONS, 1):
        ans = nl.ask(q, verbose=False)
        stats["elapsed"] += ans.result.elapsed
        stats[ans.engine.lower()] = stats.get(ans.engine.lower(), 0) + 1
        if ans.result.ok:
            stats["ok"] += 1
        else:
            stats["fail"] += 1
        print(f"[{i:02d}/{len(QUESTIONS)}] {ans.engine:<4} {'OK ' if ans.result.ok else 'FAIL'} {ans.result.elapsed:5.2f}s  {q}")
        lines.append(f"## {i}. {q}")
        lines.append("")
        lines.append(f"**引擎**：{ans.engine}" + (f"（{ans.fallback_note}）" if ans.fallback_note else ""))
        lines.append("")
        lines.append("```sql")
        lines.append(ans.sql.strip())
        lines.append("```")
        lines.append("")
        lines.append(ans.result.to_markdown(max_rows=8))
        lines.append("")
        lines.append(f"_耗时 {ans.result.elapsed:.2f}s_")
        lines.append("")

    total = (datetime.now() - started).total_seconds()
    summary = [
        "---",
        "",
        "## 汇总",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 问题总数 | {len(QUESTIONS)} |",
        f"| 执行成功 | {stats['ok']} |",
        f"| 执行失败 | {stats['fail']} |",
        f"| 大模型命中 | {stats['llm']} |",
        f"| 规则引擎命中 | {stats['rule']} |",
        f"| SQL 平均耗时 | {stats['elapsed'] / len(QUESTIONS):.2f}s |",
        f"| 端到端总耗时 | {total:.1f}s |",
        "",
    ]
    lines = lines[:head_len] + summary + lines[head_len:]

    path = OUT / "nl2sql_run_log.md"
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print(f"\n日志已写入：{path}")


if __name__ == "__main__":
    main()
