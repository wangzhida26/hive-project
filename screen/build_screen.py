"""装配数据大屏：echarts + 中国地图 GeoJSON + 实跑数据 → 单文件 HTML。

用法：
  1. docker exec beeline 跑 sql/analysis/screen_export.sql 导出 4 个 CSV 到 analysis/data/
     (province.csv / heat.csv / storetop.csv / pay.csv)
  2. python build_screen.py  → screen/云购生活数据大屏.html
"""
import csv
import io
import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parent.parent
DATA = BASE / "analysis" / "data"
SCREEN = BASE / "screen"


def read_csv(name: str) -> list[list[str]]:
    p = DATA / name
    with io.open(p, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return rows[1:] if rows and rows[0] and not rows[0][0][:1].isdigit() else rows


def fnum(v):
    v = str(v).strip()
    try:
        return float(v)
    except ValueError:
        return 0.0


def build() -> None:
    kpi_rows = read_csv("kpi.csv")
    # 按表头名取列，避免列序变化
    with io.open(DATA / "kpi.csv", encoding="utf-8-sig", newline="") as f:
        hdr = next(csv.reader(f))
    kpi = dict(zip(hdr, kpi_rows[0]))
    kpi_get = lambda k: fnum(kpi.get(k, 0))
    daily = read_csv("gmv_daily.csv")
    cats = read_csv("cat.csv")
    provs = read_csv("province.csv")
    heats = read_csv("heat.csv")
    tops = read_csv("storetop.csv")
    pays = read_csv("pay.csv")

    categories = [r[1] for r in cats]  # 按 GMV 降序
    heat = [{"hr": int(fnum(r[0])), "category": r[1], "gmv": fnum(r[2])} for r in heats]
    heat_max = max([h["gmv"] for h in heat] or [0])

    data = {
        "kpi": {
            "gmv": kpi_get("gmv"), "orders": int(kpi_get("orders")), "aov": kpi_get("aov"),
            "users": int(kpi_get("active_users")), "repurchase_rate": kpi_get("repurchase_rate"),
            "avg_orders_user": kpi_get("avg_orders_user"),
            "refund_rate": kpi_get("refund_rate"),
        },
        "daily": [{"dt": r[0], "gmv": fnum(r[1]), "ma7": fnum(r[4])} for r in daily],
        "category": [{"name": r[1], "gmv": fnum(r[2]), "share": fnum(r[5])} for r in cats],
        "province": [{"name": r[0], "gmv": fnum(r[1]), "orders": int(fnum(r[2])),
                      "stores": int(fnum(r[3]))} for r in provs],
        "categories": categories,
        "heat": heat,
        "heatMax": heat_max,
        "storeTop": [{"name": r[0], "province": r[1], "city": r[2], "gmv": fnum(r[3])} for r in tops],
        "pay": [{"name": r[0], "gmv": fnum(r[1]), "orders": int(fnum(r[2]))} for r in pays],
    }

    echarts_js = io.open(SCREEN / "vendor" / "echarts.min.js", encoding="utf-8").read()
    china_json = io.open(SCREEN / "vendor" / "china.json", encoding="utf-8").read()
    tpl = io.open(SCREEN / "screen_template.html", encoding="utf-8").read()

    def esc(js: str) -> str:
        # 防止 JS 源码中的 "</script>" 提前终止内联标签
        return js.replace("</script>", "<\\/script>")

    data_js = json.dumps(data, ensure_ascii=False).replace("</script>", "<\\/script>")

    html = (tpl
            .replace("<!--ECHARTS_JS-->", "<script>" + esc(echarts_js) + "</script>")
            .replace("<!--CHINA_JSON-->", "<script>window.CHINA_GEO=" + esc(china_json) + ";</script>")
            .replace("<!--DATA_JS-->", "<script>window.SCREEN_DATA=" + data_js + ";</script>"))

    out = SCREEN / "云购生活数据大屏.html"
    io.open(out, "w", encoding="utf-8").write(html)
    print("OK:", out, f"{out.stat().st_size/1024:.0f} KB  daily={len(data['daily'])}  province={len(data['province'])}  heat={len(data['heat'])}")


if __name__ == "__main__":
    sys.exit(build())
