"""
子任务 3：大模型连通性最小化验证脚本
==================================================
用途：确认 .env 中的密钥、Base URL、模型名三者匹配，能拿到符合预期的返回格式。

设计要点（密钥安全规范）：
1. 密钥只从环境变量读取，代码中不出现任何明文 Key；
2. 日志与异常信息中对 Key 做掩码（只保留前 6 位 + 后 4 位）；
3. .env 已被 .gitignore 忽略，仓库只提交 .env.example 模板。

用法：
    python llm_ping.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


def mask(key: str) -> str:
    if not key:
        return "(未设置)"
    if len(key) <= 10:
        return key[:2] + "***"
    return f"{key[:6]}...{key[-4:]}"


def main() -> int:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    print("=" * 62)
    print("大模型连通性验证")
    print("=" * 62)
    print(f"API Key   : {mask(key)}")
    print(f"Base URL  : {base}")
    print(f"Model     : {model}")

    if not key or key.startswith("sk-your"):
        print("\n[跳过] 未配置真实密钥。")
        print("操作步骤：")
        print("  1) cp .env.example .env")
        print("  2) 在 .env 里填入真实 OPENAI_API_KEY")
        print("  3) 重新运行本脚本")
        print("\n当前 NL2SQL 仍可用规则引擎完整演示（提问 → SQL → 结果）。")
        return 2

    from openai import OpenAI

    client = OpenAI(api_key=key, base_url=base)
    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=64,
            messages=[
                {"role": "system", "content": "你是 SQL 助手，只回答 SQL，不要解释。"},
                {"role": "user", "content": "查一张订单表里 GMV 最高的 3 天，用 Hive SQL。"},
            ],
        )
    except Exception as exc:
        print(f"\n[失败] {type(exc).__name__}: {str(exc)[:300]}")
        print("排查建议：Key 是否有效 / Base URL 是否漏了 /v1 / 模型名是否在该平台存在")
        return 1

    elapsed = time.time() - t0
    content = (resp.choices[0].message.content or "").strip()
    usage = resp.usage

    print(f"\n[成功] 耗时 {elapsed:.2f}s")
    print(f"返回模型 : {resp.model}")
    print(f"Token    : prompt={usage.prompt_tokens} completion={usage.completion_tokens} total={usage.total_tokens}")
    print("-" * 62)
    print(content[:400])
    print("-" * 62)

    ok = "select" in content.lower()
    print(f"格式校验 : {'通过（返回内容含 SELECT，符合预期）' if ok else '注意：返回内容不含 SELECT，请检查 Prompt'}")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
