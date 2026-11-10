# -*- coding: utf-8 -*-
"""
Schema 抽取器：生成大模型可读的库表元信息（表名 / 字段名 / 类型 / 中文注释）。

数据来源：
  1) 字段结构：docker exec beeline DESC <table>（真实读取 Hive 元数据）；
  2) 字段中文注释：解析本仓库 sql/**/create_*.sql 建表 DDL 中的 COMMENT 子句。
     （踩坑记录：MySQL 元数据库 COLUMNS_V2.COMMENT 因 JDBC 连接字符集为 latin1，
       中文注释落库后被替换为 '?'，故注释以 DDL 为准、结构以 Hive 为准。）

用法：python schema_extractor.py
产物：schema_snapshot.json（结构化）、schema_prompt.txt（Prompt 用文本）
"""
import glob
import json
import os
import re
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(BASE)
DOCKER_EXEC = [
    "docker", "exec", "hive-server", "beeline",
    "-u", "jdbc:hive2://localhost:10000", "-n", "hive",
    "--silent=true", "--outputformat=csv2",
]

TABLE_DESC = {
    "ydsh_ads.ads_kpi_overview": "核心KPI总览，单行表：GMV/订单量/客单价/活跃用户/复购率等",
    "ydsh_ads.ads_gmv_daily": "日度GMV趋势，含7日移动平均ma7、日环比dod_pct、星期weekday",
    "ydsh_ads.ads_category_sales": "品类销售排行（GMV/销量/订单数/占比）",
    "ydsh_ads.ads_store_sales": "门店销售排行（GMV/订单数/去重用户数）",
    "ydsh_ads.ads_channel_sales": "渠道×支付方式销售交叉表",
    "ydsh_ads.ads_user_value": "用户RFM价值分层（重要价值/重要保持/一般价值/流失预警）",
    "ydsh_dws.dws_order_1d": "日粒度全站汇总（GMV/订单量/有效GMV/有效订单/用户数/客单价/取消率）",
    "ydsh_dws.dws_category_1d": "日×品类汇总（明细行金额口径）",
    "ydsh_dws.dws_store_1d": "日×门店汇总（含省市）",
    "ydsh_dws.dws_channel_1d": "日×渠道×支付方式汇总",
    "ydsh_dws.dws_user_agg": "用户累计汇总（首末单日期/订单数/GMV/复购标记）",
    "ydsh_dwd.dwd_order": "订单事实表（已过滤脏数据），按 order_dt 分区",
    "ydsh_dwd.dwd_order_item": "订单明细事实表（商品行级金额/数量）",
    "ydsh_dwd.dim_user": "用户维度（性别/年龄/地区/会员等级）",
    "ydsh_dwd.dim_product": "商品维度（品类/品牌/价格）",
    "ydsh_dwd.dim_store": "门店维度（省份/城市）",
}


def desc_columns(table: str):
    """从 Hive 读取列名与类型。"""
    r = subprocess.run(DOCKER_EXEC + ["-e", f"DESC {table};"],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise RuntimeError(f"DESC {table} failed: {r.stdout[-200:]}")
    cols = []
    for ln in lines[1:]:
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) < 2 or parts[0].startswith("#") or parts[0] == "":
            continue
        cols.append({"name": parts[0], "type": parts[1],
                     "comment": parts[2] if len(parts) > 2 else ""})
    return cols


def ddl_comments():
    """解析建表 DDL，得到 {表名: {字段: 注释}}。"""
    out = {}
    for path in glob.glob(os.path.join(REPO, "sql", "**", "create_*.sql"), recursive=True):
        text = open(path, encoding="utf-8").read()
        for m in re.finditer(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)\.(\w+)\s*\((.*?)\)\s*(?:PARTITIONED|STORED|ROW)",
                             text, re.S | re.I):
            tbl = m.group(2)
            body = m.group(3)
            cols = {}
            for line in body.splitlines():
                line = line.strip().rstrip(",")
                mm = re.match(r"(\w+)\s+[\w<>]+.*?COMMENT\s+'([^']*)'", line, re.I)
                if mm:
                    cols[mm.group(1)] = mm.group(2)
            out[tbl] = cols
    return out


def main():
    comments = ddl_comments()
    snapshot = {}
    for table in TABLE_DESC:
        short = table.split(".")[1]
        try:
            cols = desc_columns(table)
        except Exception as exc:
            print(f"[WARN] {table}: {exc}")
            continue
        cmap = comments.get(short, {})
        for c in cols:
            if c["name"] in cmap:
                c["comment"] = cmap[c["name"]]
            elif "?" in c["comment"]:
                c["comment"] = ""
        snapshot[table] = {"description": TABLE_DESC[table], "columns": cols}
        hit = sum(1 for c in cols if c["comment"])
        print(f"[OK] {table}: {len(cols)} 列，注释命中 {hit}")

    with open(os.path.join(BASE, "schema_snapshot.json"), "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, ensure_ascii=False, indent=2)

    lines = []
    for table, meta in snapshot.items():
        lines.append(f"### {table}  -- {meta['description']}")
        for c in meta["columns"]:
            cmt = f"  -- {c['comment']}" if c["comment"] else ""
            lines.append(f"  {c['name']} {c['type']}{cmt}")
        lines.append("")
    with open(os.path.join(BASE, "schema_prompt.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"\n完成：{len(snapshot)} 张表 → schema_snapshot.json / schema_prompt.txt")


if __name__ == "__main__":
    main()
