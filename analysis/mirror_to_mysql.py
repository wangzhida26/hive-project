"""把 Hive ADS/DWS 关键表镜像到 MySQL（ydsh_ads / ydsh_dws），供 Superset 与容器版问答 App 查询。

设计要点：
- 类型按值推断（日期 → DATE，数值 → DOUBLE/BIGINT，其余 VARCHAR），NULL 统一处理；
- 同时生成 ads_province_geo（省份省会经纬度，WGS84），供 Superset deck_scatter 区域图使用；
- 幂等：先 DROP 后重建。

用法：python analysis/mirror_to_mysql.py
"""
import csv
import datetime
import io
import os
import re
import subprocess
import sys

import pymysql

MYSQL = dict(host="127.0.0.1", port=3307, user="root", password="root", charset="utf8mb4")
HIVE_EXEC = ["docker", "exec", "hive-server", "beeline", "-u",
             "jdbc:hive2://localhost:10000", "-n", "hive", "--silent=true",
             "--showHeader=true", "--outputformat=csv2"]

TABLES = [
    ("ydsh_ads",   "ads_kpi_overview"),
    ("ydsh_ads",   "ads_gmv_daily"),
    ("ydsh_ads",   "ads_category_sales"),
    ("ydsh_ads",   "ads_store_sales"),
    ("ydsh_ads",   "ads_channel_sales"),
    ("ydsh_ads",   "ads_user_value"),
    ("ydsh_dws",   "dws_order_1d"),
    ("ydsh_dws",   "dws_category_1d"),
    ("ydsh_dws",   "dws_store_1d"),
    ("ydsh_dws",   "dws_channel_1d"),
    ("ydsh_dws",   "dws_user_agg"),
]

# 省份 → 省会坐标（WGS84，公开地理常识数据）
CAPITAL = {
    "浙江省": (30.27, 120.15), "江苏省": (32.06, 118.78), "广东省": (23.13, 113.26),
    "山东省": (36.67, 117.02), "河南省": (34.76, 113.62), "四川省": (30.57, 104.06),
    "湖北省": (30.59, 114.31), "湖南省": (28.23, 112.94), "福建省": (26.08, 119.30),
    "安徽省": (31.82, 117.23), "河北省": (38.04, 114.51), "陕西省": (34.27, 108.95),
    "辽宁省": (41.80, 123.43), "吉林省": (43.88, 125.32), "黑龙江省": (45.80, 126.53),
    "山西省": (37.87, 112.55), "云南省": (25.04, 102.71), "贵州省": (26.65, 106.63),
    "江西省": (28.68, 115.86), "广西壮族自治区": (22.82, 108.32), "海南省": (20.04, 110.34),
    "甘肃省": (36.06, 103.83), "青海省": (36.62, 101.78), "宁夏回族自治区": (38.49, 106.23),
    "新疆维吾尔自治区": (43.79, 87.62), "内蒙古自治区": (40.82, 111.65), "西藏自治区": (29.65, 91.14),
    "北京市": (39.90, 116.41), "上海市": (31.23, 121.47), "天津市": (39.13, 117.20),
    "重庆市": (29.56, 106.55), "香港特别行政区": (22.32, 114.17), "澳门特别行政区": (22.20, 113.55),
    "台湾省": (25.04, 121.51),
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
INT_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")


def hive_query(sql: str) -> tuple[list[str], list[list[str | None]]]:
    r = subprocess.run(HIVE_EXEC + ["-e", sql], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    lines = [l for l in r.stdout.splitlines()
             if l.strip() and not l.startswith(("SLF4J", "WARNING", "Log4j", "WARN"))]
    if not lines:
        raise RuntimeError(f"Hive 查询无输出：{sql[:80]}… stderr: {r.stderr[-300:]}")
    rows = list(csv.reader(io.StringIO("\n".join(lines))))
    return [c.strip().split(".")[-1] for c in rows[0]], rows[1:]


def clean(v: str | None):
    if v is None or v.strip().upper() in ("NULL", "\\N", ""):
        return None
    return v.strip()


def infer(cols, rows):
    types = []
    for i in range(len(cols)):
        vals = [clean(r[i]) for r in rows if clean(r[i]) is not None]
        if not vals:
            types.append("VARCHAR(255)")
            continue
        if all(DATE_RE.match(v) for v in vals):
            types.append("DATE")
        elif all(INT_RE.match(v) for v in vals):
            types.append("BIGINT")
        elif all(FLOAT_RE.match(v) for v in vals):
            types.append("DOUBLE")
        else:
            types.append("VARCHAR(255)")
    return types


def mirror_table(cur, db: str, table: str) -> int:
    cols, rows = hive_query(f"SELECT * FROM {db}.{table}")
    types = infer(cols, rows)
    cur.execute(f"DROP TABLE IF EXISTS `{db}`.`{table}`")
    col_defs = ", ".join(f"`{c}` {t}" for c, t in zip(cols, types))
    cur.execute(f"CREATE TABLE `{db}`.`{table}` ({col_defs}) DEFAULT CHARSET=utf8mb4")
    placeholders = ",".join(["%s"] * len(cols))
    sql = f"INSERT INTO `{db}`.`{table}` VALUES ({placeholders})"
    for r in rows:
        vals = [clean(v) for v in r]
        vals = [datetime.date.fromisoformat(v) if t == "DATE" and v else v
                for v, t in zip(vals, types)]
        cur.execute(sql, vals)
    return len(rows)


def build_province_geo(cur) -> int:
    cols, rows = hive_query(
        "SELECT province, ROUND(SUM(gmv),2) gmv, SUM(orders) orders, "
        "COUNT(DISTINCT store_id) stores FROM ydsh_dws.dws_store_1d GROUP BY province")
    cur.execute("DROP TABLE IF EXISTS ydsh_ads.ads_province_geo")
    cur.execute("""CREATE TABLE ydsh_ads.ads_province_geo (
        province VARCHAR(64), gmv DOUBLE, orders BIGINT, stores INT,
        lat DOUBLE, lng DOUBLE) DEFAULT CHARSET=utf8mb4""")
    n = 0
    for r in rows:
        prov = clean(r[0])
        coord = CAPITAL.get(prov)
        if not coord:
            print(f"  ⚠ 未知省份坐标：{prov}，跳过")
            continue
        cur.execute("INSERT INTO ydsh_ads.ads_province_geo VALUES (%s,%s,%s,%s,%s,%s)",
                    (prov, float(r[1]), int(float(r[2])), int(float(r[3])), coord[0], coord[1]))
        n += 1
    return n


def main():
    conn = pymysql.connect(database=None, **MYSQL)
    with conn.cursor() as cur:
        cur.execute("CREATE DATABASE IF NOT EXISTS ydsh_ads DEFAULT CHARSET utf8mb4")
        cur.execute("CREATE DATABASE IF NOT EXISTS ydsh_dws DEFAULT CHARSET utf8mb4")
        conn.commit()
        for db, table in TABLES:
            n = mirror_table(cur, db, table)
            print(f"✅ {db}.{table}: {n} 行")
            conn.commit()
        n = build_province_geo(cur)
        print(f"✅ ydsh_ads.ads_province_geo: {n} 行")
        conn.commit()
    conn.close()
    print("镜像完成")


if __name__ == "__main__":
    sys.exit(main())
