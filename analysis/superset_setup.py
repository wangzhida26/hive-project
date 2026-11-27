"""Superset 一键配置：建库连接 → 数据集 → 6 个图表 → Dashboard + 日期筛选器。

前置：Superset 已启动并初始化 admin（见部署手册步骤 1）。
用法：python analysis/superset_setup.py [--host http://localhost:8088]
"""
import argparse
import json
import sys
import time

import requests

ADMIN = ("admin", "admin")

# 图表定义：标题 / 数据集 / viz_type / 参数
# 注意：本镜像前端仅注册 echarts_timeseries_line / pie / table / big_number(_total) 四类插件，
# echarts_bar / treemap / pivot_table 等虽在图库目录中列出但懒加载缺块（"not registered"）。
# 离线环境禁用 deck_*(依赖在线地图瓦片)；时间序列类(echarts_timeseries_*/big_number)
# 要求时间轴——非时间维度一律用 pie 或 table 呈现。
CHART_SPECS = [
    {
        "table": "ads_gmv_daily", "schema": "ydsh_ads",
        "name": "全年 GMV 销售趋势", "viz": "echarts_timeseries_line",
        "params": {
            "metrics": [{"expressionType": "SIMPLE", "column": {"column_name": "gmv"},
                         "aggregate": "SUM", "label": "GMV"}],
            "groupby": [], "x_axis": "order_dt",
            "time_grain_sqla": "P1D", "metrics_b": None,
            "color_scheme": "supersetColors", "show_legend": True,
        },
    },
    {
        "table": "ads_category_sales", "schema": "ydsh_ads",
        "name": "品类销售对比", "viz": "pie",
        "params": {
            "metric": {"expressionType": "SIMPLE", "column": {"column_name": "gmv"},
                       "aggregate": "SUM", "label": "GMV"},
            "groupby": ["category"], "pie_label_type": "auto",
            "donut": True, "show_legend": True, "color_scheme": "supersetColors",
        },
    },
    {
        "table": "ads_province_geo", "schema": "ydsh_ads",
        "name": "区域分布（省份 GMV 排行）", "viz": "table",
        "params": {
            "groupby": ["province"],
            "metrics": [{"expressionType": "SIMPLE", "column": {"column_name": "gmv"},
                         "aggregate": "SUM", "label": "GMV"}],
            "order_desc": True, "row_limit": 20, "page_length": 10,
            "table_timestamp_format": "%Y-%m-%d",
        },
    },
    {
        "table": "ads_channel_sales", "schema": "ydsh_ads",
        "name": "支付方式占比", "viz": "pie",
        "params": {
            "metric": {"expressionType": "SIMPLE", "column": {"column_name": "gmv"},
                       "aggregate": "SUM", "label": "GMV"},
            "groupby": ["pay_type"], "pie_label_type": "key_percent",
            "donut": True, "show_legend": True, "color_scheme": "supersetColors",
        },
    },
    {
        "table": "ads_store_sales", "schema": "ydsh_ads",
        "name": "门店 GMV Top10 排行", "viz": "table",
        "params": {
            "groupby": ["store_name", "province"],
            "metrics": [{"expressionType": "SIMPLE", "column": {"column_name": "gmv"},
                         "aggregate": "SUM", "label": "GMV"},
                        {"expressionType": "SIMPLE", "column": {"column_name": "orders"},
                         "aggregate": "SUM", "label": "订单数"}],
            "order_desc": True, "row_limit": 10, "page_length": 0,
            "table_timestamp_format": "%Y-%m-%d",
        },
    },
    {
        "table": "ads_gmv_daily", "schema": "ydsh_ads",
        "name": "年度 GMV 大数字", "viz": "big_number_total",
        "params": {
            "metric": {"expressionType": "SIMPLE", "column": {"column_name": "gmv"},
                       "aggregate": "SUM", "label": "GMV"},
            "y_axis_format": "SMART_NUMBER", "subheader": "2024 全年销售额",
        },
    },
]


class SupersetClient:
    """认证：表单登录拿会话+CSRF → 再拿 JWT。写请求需同时带会话 cookie 与 X-CSRFToken。"""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self.token = self._login()
        self.s.headers["Referer"] = self.base

    def _login(self) -> str:
        import re as _re

        r = self.s.get(self.base + "/login/")
        r.raise_for_status()
        m = _re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
        if not m:
            raise RuntimeError("登录页未找到 csrf_token")
        self._form_csrf = m.group(1)
        r = self.s.post(self.base + "/login/",
                        data={"username": ADMIN[0], "password": ADMIN[1],
                              "csrf_token": self._form_csrf})
        r.raise_for_status()
        r = self.s.post(self.base + "/api/v1/security/login",
                        json={"username": ADMIN[0], "password": ADMIN[1], "provider": "db"})
        r.raise_for_status()
        tok = r.json()["access_token"]
        self.s.headers["Authorization"] = f"Bearer {tok}"
        self.s.headers["X-CSRFToken"] = self._form_csrf
        return tok

    def _refresh_csrf(self) -> None:
        """Flask-WTF 每次成功写请求后轮换 token，写操作前必须重新获取。"""
        import re as _re

        r = self.s.get(self.base + "/login/")
        m = _re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
        if m:
            self.s.headers["X-CSRFToken"] = m.group(1)

    def get(self, path, **kw):
        r = self.s.get(self.base + path, **kw)
        r.raise_for_status()
        return r.json()

    def post(self, path, payload):
        self._refresh_csrf()
        r = self.s.post(self.base + path, json=payload)
        if r.status_code >= 300:
            raise RuntimeError(f"POST {path} {r.status_code}: {r.text[:300]}")
        return r.json()

    def put(self, path, payload):
        self._refresh_csrf()
        r = self.s.put(self.base + path, json=payload)
        if r.status_code >= 300:
            raise RuntimeError(f"PUT {path} {r.status_code}: {r.text[:300]}")
        return r.json() if r.text else {}

    def delete(self, path):
        self._refresh_csrf()
        r = self.s.delete(self.base + path)
        if r.status_code >= 300:
            raise RuntimeError(f"DELETE {path} {r.status_code}: {r.text[:200]}")
        return r.json() if r.text else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="http://localhost:8088")
    args = ap.parse_args()
    c = SupersetClient(args.host)
    print("✅ 登录成功")

    # 1) 建数据库连接（MySQL 报表镜像库）
    dbs = c.get("/api/v1/database/?q=(filters:!((col:database_name,opr:eq,value:ydsh_report)))")
    if dbs["count"]:
        db_id = dbs["result"][0]["id"]
    else:
        r = c.post("/api/v1/database/", {
            "database_name": "ydsh_report",
            "sqlalchemy_uri": "mysql+pymysql://root:root@metastore-mysql:3306/ydsh_ads?charset=utf8mb4",
            "expose_in_sqllab": True,
        })
        db_id = r["id"]
    print(f"✅ 数据库连接 id={db_id}")

    # 2) 创建/获取数据集
    ds_map = {}
    for spec in CHART_SPECS:
        key = (spec["schema"], spec["table"])
        if key in ds_map:
            continue
        found = c.get(f"/api/v1/dataset/?q=(filters:!((col:table_name,opr:eq,value:{spec['table']}"
                      f"),(col:schema,opr:eq,value:{spec['schema']})))")
        if found["count"]:
            ds_id = found["result"][0]["id"]
        else:
            r = c.post("/api/v1/dataset/", {"database": db_id, "schema": spec["schema"],
                                            "table_name": spec["table"]})
            ds_id = r["id"]
            time.sleep(1)
        ds_map[key] = ds_id
        print(f"✅ 数据集 {spec['schema']}.{spec['table']} → id={ds_id}")

    # 3) 创建图表（全新实例直接创建，不做查重）
    chart_ids = []
    for spec in CHART_SPECS:
        ds_id = ds_map[(spec["schema"], spec["table"])]
        params = {"datasource": f"{ds_id}__table", "viz_type": spec["viz"],
                  "query_mode": "aggregate", "row_limit": 10000, **spec["params"]}
        r = c.post("/api/v1/chart/", {
            "slice_name": spec["name"], "datasource_id": ds_id,
            "datasource_type": "table", "params": json.dumps(params),
            "viz_type": spec["viz"],
        })
        cid = r["id"]
        chart_ids.append(cid)
        print(f"✅ 图表 {spec['name']} → id={cid}")

    # 4) Dashboard：创建后逐图 PUT chart.dashboards 关联（新版 API 不支持 dashboard.slices）
    dash = c.get("/api/v1/dashboard/?q=(filters:!((col:dashboard_title,opr:eq,value:云购生活经营分析仪表板)))")
    if dash["count"]:
        dash_id = dash["result"][0]["id"]
    else:
        r = c.post("/api/v1/dashboard/", {
            "dashboard_title": "云购生活经营分析仪表板",
            "slug": "ydsh-biz-dashboard",
        })
        dash_id = r["id"]
    for cid in chart_ids:
        c.put(f"/api/v1/chart/{cid}", {"dashboards": [dash_id]})
    print(f"✅ Dashboard(id={dash_id}) 已挂载 {len(chart_ids)} 个图表")

    # 4.5) 清理重复图表（同名旧图）
    dups = c.get("/api/v1/chart/")
    for item in dups["result"]:
        if item["slice_name"] in [s["name"] for s in CHART_SPECS] and item["id"] not in chart_ids:
            try:
                c.delete(f"/api/v1/chart/{item['id']}")
                print(f"🧹 删除重复图表 id={item['id']} {item['slice_name']}")
            except Exception as exc:
                print(f"⚠ 清理失败 {item['id']}: {exc}")
    # 日期范围筛选器（作用于含 order_dt 的图表）
    try:
        d = c.get(f"/api/v1/dashboard/{dash_id}")
        meta = json.loads(d["result"].get("json_metadata") or "{}")
        meta["native_filter_configuration"] = [{
            "id": "date-filter-1",
            "name": "日期范围",
            "type": "NATIVE_FILTER_TYPE_DATE_RANGE",
            "targets": [{"datasetId": ds_map[("ydsh_ads", "ads_gmv_daily")],
                         "column": {"name": "order_dt"}}],
            "defaultDataRange": ["2024-01-01", "2024-12-31"],
            "controlValues": {"enableEmptyFilter": False},
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "isRequired": False,
        }]
        c.put(f"/api/v1/dashboard/{dash_id}", {"json_metadata": json.dumps(meta)})
        print("✅ 日期筛选器已配置")
    except Exception as exc:
        print(f"⚠ 筛选器配置失败（可在 UI 手动添加）：{exc}")

    print(f"\n🎉 Dashboard 完成：http://localhost:8088/superset/dashboard/{dash_id}/")
    print(f"   图表数：{len(chart_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
