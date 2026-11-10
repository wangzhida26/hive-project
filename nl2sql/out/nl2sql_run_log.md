# NL2SQL 实测运行日志

- 运行时间：2026-11-10 08:48:56
- 引擎状态：LLM 未配置密钥（将回退规则引擎）；规则引擎已加载（品类/省份/门店/渠道域值已缓存）
- 运行模式：auto
- 问题数：12

---

---

## 汇总

| 指标 | 数值 |
| --- | --- |
| 问题总数 | 12 |
| 执行成功 | 12 |
| 执行失败 | 0 |
| 大模型命中 | 0 |
| 规则引擎命中 | 12 |
| SQL 平均耗时 | 4.43s |
| 端到端总耗时 | 53.2s |

## 1. 整体经营大盘怎么样

**引擎**：Rule

```sql
SELECT * FROM ydsh_ads.ads_kpi_overview
LIMIT 200
```

| stat_period | gmv | orders | aov | active_users | repurchase_rate | avg_orders_user | category_top | category_share | store_top | refund_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-01-01 ~ 2024-12-31 | 24,805,594.44 | 9803 | 2530.41 | 1000 | 1.0 | 14.7 | 运动户外 | 15.33 | 云购生活·开封社区店 | 0.0542 |

_耗时 3.65s_

## 2. GMV 最高的五天是哪几天

**引擎**：Rule

```sql
SELECT order_dt, gmv, orders, aov FROM ydsh_ads.ads_gmv_daily ORDER BY gmv DESC LIMIT 5
```

| order_dt | gmv | orders | aov |
| --- | --- | --- | --- |
| 2024-03-16 | 113424.59 | 46 | 2465.75 |
| 2024-03-31 | 111235.73 | 37 | 3006.37 |
| 2024-04-09 | 109330.6 | 33 | 3313.05 |
| 2024-04-19 | 103337.1 | 36 | 2870.48 |
| 2024-09-07 | 102458.38 | 35 | 2927.38 |

_耗时 4.25s_

## 3. 按月的 GMV 趋势如何

**引擎**：Rule

```sql
SELECT SUBSTR(order_dt,1,7) AS ym, ROUND(SUM(gmv),2) AS gmv, SUM(orders) AS orders, ROUND(SUM(gmv)/SUM(orders),2) AS aov FROM ydsh_ads.ads_gmv_daily GROUP BY SUBSTR(order_dt,1,7) ORDER BY ym
LIMIT 200
```

| ym | gmv | orders | aov |
| --- | --- | --- | --- |
| 2024-01 | 2164156.17 | 838 | 2582.53 |
| 2024-02 | 1930293.48 | 766 | 2519.97 |
| 2024-03 | 2066166.98 | 827 | 2498.39 |
| 2024-04 | 2114692.87 | 806 | 2623.69 |
| 2024-05 | 2198520.94 | 866 | 2538.71 |
| 2024-06 | 1929455.69 | 756 | 2552.19 |
| 2024-07 | 2006704.25 | 800 | 2508.38 |
| 2024-08 | 2150994.76 | 862 | 2495.35 |

_（共 12 行，仅展示前 8 行）_

_耗时 4.55s_

## 4. 最近一个月每天的 GMV 走势

**引擎**：Rule

```sql
SELECT order_dt, gmv, orders, aov, ROUND(ma7,2) AS ma7, ROUND(dod_pct,2) AS dod_pct FROM (SELECT * FROM ydsh_ads.ads_gmv_daily ORDER BY order_dt DESC LIMIT 30) t ORDER BY order_dt
```

| order_dt | gmv | orders | aov | ma7 | dod_pct |
| --- | --- | --- | --- | --- | --- |
| 2024-12-02 | 67301.58 | 29 | 2320.74 | 73735.33 | -9.55 |
| 2024-12-03 | 90755.12 | 35 | 2593.0 | 73999.95 | 34.85 |
| 2024-12-04 | 76400.4 | 29 | 2634.5 | 74215.28 | -15.82 |
| 2024-12-05 | 77081.26 | 27 | 2854.86 | 74185.93 | 0.89 |
| 2024-12-06 | 50322.43 | 19 | 2648.55 | 72747.47 | -34.72 |
| 2024-12-07 | 66694.0 | 26 | 2565.15 | 71851.51 | 32.53 |
| 2024-12-08 | 51289.02 | 22 | 2331.32 | 68549.12 | -23.1 |
| 2024-12-09 | 67537.32 | 29 | 2328.87 | 68582.79 | 31.68 |

_（共 30 行，仅展示前 8 行）_

_耗时 4.60s_

## 5. 各品类销售额排名

**引擎**：Rule

```sql
SELECT rk, category, gmv, qty, orders, share_pct FROM ydsh_ads.ads_category_sales ORDER BY rk
LIMIT 200
```

| rk | category | gmv | qty | orders | share_pct |
| --- | --- | --- | --- | --- | --- |
| 1 | 运动户外 | 14,962,627.56 | 21996 | 4730 | 15.38 |
| 2 | 数码家电 | 13,041,447.46 | 19279 | 4389 | 13.4 |
| 3 | 服饰鞋包 | 12,843,889.08 | 18122 | 4082 | 13.2 |
| 4 | 食品生鲜 | 12,145,261.83 | 17933 | 4028 | 12.48 |
| 5 | 图书文娱 | 11,649,353.10 | 17273 | 4066 | 11.97 |
| 6 | 家居生活 | 11,246,401.34 | 16869 | 3718 | 11.56 |
| 7 | 美妆个护 | 10,955,218.28 | 15891 | 3719 | 11.26 |
| 8 | 母婴玩具 | 10,445,053.29 | 15476 | 3625 | 10.74 |

_耗时 4.32s_

## 6. 运动户外这个品类每天卖多少

**引擎**：Rule

```sql
SELECT order_dt, ROUND(gmv,2) AS gmv, qty, orders FROM ydsh_dws.dws_category_1d WHERE category='运动户外' ORDER BY order_dt DESC LIMIT 60
```

| order_dt | gmv | qty | orders |
| --- | --- | --- | --- |
| 2024-12-31 | 20115.11 | 37 | 12 |
| 2024-12-30 | 38153.09 | 62 | 16 |
| 2024-12-29 | 35647.1 | 54 | 16 |
| 2024-12-28 | 43811.26 | 57 | 15 |
| 2024-12-27 | 121360.13 | 136 | 12 |
| 2024-12-26 | 18947.5 | 30 | 7 |
| 2024-12-25 | 10190.61 | 25 | 8 |
| 2024-12-24 | 30256.72 | 48 | 17 |

_（共 60 行，仅展示前 8 行）_

_耗时 4.47s_

## 7. 门店销售排行前十名

**引擎**：Rule

```sql
SELECT rk, store_name, province, city, gmv, orders, users FROM ydsh_ads.ads_store_sales ORDER BY rk LIMIT 10
```

| rk | store_name | province | city | gmv | orders | users |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 云购生活·开封社区店 | 河南省 | 开封 | 1333856.83 | 506 | 390 |
| 2 | 云购生活·北京二店 | 北京市 | 北京 | 1329027.0 | 538 | 414 |
| 3 | 云购生活·德阳购物中心店 | 四川省 | 德阳 | 1265316.05 | 512 | 395 |
| 4 | 云购生活·莆田旗舰店 | 福建省 | 莆田 | 1261525.94 | 481 | 380 |
| 5 | 云购生活·青岛二店 | 山东省 | 青岛 | 1257600.19 | 516 | 411 |
| 6 | 云购生活·重庆社区店 | 重庆市 | 重庆 | 1246829.38 | 479 | 374 |
| 7 | 云购生活·重庆一店 | 重庆市 | 重庆 | 1213881.41 | 494 | 406 |
| 8 | 云购生活·西安一店 | 陕西省 | 西安 | 1146103.31 | 470 | 362 |

_（共 10 行，仅展示前 8 行）_

_耗时 4.21s_

## 8. 浙江和广东哪个省卖得好

**引擎**：Rule

```sql
SELECT province, ROUND(SUM(gmv),2) AS gmv, SUM(orders) AS orders, ROUND(SUM(gmv)/(SELECT SUM(gmv) FROM ydsh_dws.dws_store_1d)*100,2) AS share_pct FROM ydsh_dws.dws_store_1d WHERE province IN ('广东省','浙江省') GROUP BY province ORDER BY gmv DESC
LIMIT 200
```

| province | gmv | orders | share_pct |
| --- | --- | --- | --- |
| 浙江省 | 4333233.52 | 1697 | 11.7 |
| 广东省 | 584275.43 | 222 | 1.58 |

_耗时 5.06s_

## 9. 各个渠道和支付方式的销售占比

**引擎**：Rule

```sql
SELECT channel, pay_type, gmv, orders, share_pct FROM ydsh_ads.ads_channel_sales ORDER BY gmv DESC
LIMIT 200
```

| channel | pay_type | gmv | orders | share_pct |
| --- | --- | --- | --- | --- |
| APP | 支付宝 | 2536816.47 | 1009 | 6.85 |
| 门店 | 微信支付 | 2530061.74 | 977 | 6.83 |
| PC官网 | 微信支付 | 2498590.14 | 968 | 6.75 |
| APP | 微信支付 | 2457868.32 | 990 | 6.64 |
| 小程序 | 微信支付 | 2457679.01 | 983 | 6.64 |
| 门店 | 支付宝 | 2429397.08 | 978 | 6.56 |
| 小程序 | 支付宝 | 2396638.69 | 928 | 6.47 |
| PC官网 | 支付宝 | 2345784.56 | 968 | 6.34 |

_（共 16 行，仅展示前 8 行）_

_耗时 4.40s_

## 10. 用户价值分层（RFM）各层有多少人

**引擎**：Rule

```sql
SELECT segment, COUNT(*) AS users, ROUND(AVG(recency),1) AS avg_r, ROUND(AVG(frequency),1) AS avg_f, ROUND(AVG(monetary),2) AS avg_m, ROUND(SUM(monetary),2) AS gmv FROM ydsh_ads.ads_user_value GROUP BY segment ORDER BY gmv DESC
LIMIT 200
```

| segment | users | avg_r | avg_f | avg_m | gmv |
| --- | --- | --- | --- | --- | --- |
| 重要价值 | 286 | 7.4 | 18.0 | 45117.95 | 12,903,733.03 |
| 重要保持 | 214 | 33.4 | 17.7 | 44540.17 | 9531597.39 |
| 流失预警 | 286 | 45.4 | 11.3 | 28985.96 | 8289984.48 |
| 一般价值 | 214 | 7.4 | 11.8 | 29451.13 | 6302542.77 |

_耗时 4.45s_

## 11. 复购用户和单次用户有什么区别

**引擎**：Rule

```sql
SELECT repurchase_flag, COUNT(*) AS users, ROUND(AVG(orders),1) AS avg_orders, ROUND(AVG(gmv),2) AS avg_gmv FROM ydsh_dws.dws_user_agg GROUP BY repurchase_flag ORDER BY repurchase_flag DESC
LIMIT 200
```

| repurchase_flag | users | avg_orders | avg_gmv |
| --- | --- | --- | --- |
| 1 | 1000 | 14.7 | 37027.86 |

_耗时 4.69s_

## 12. 哪几天 GMV 出现了骤降

**引擎**：Rule

```sql
SELECT order_dt, gmv, orders, aov, ROUND(dod_pct,2) AS dod_pct FROM ydsh_ads.ads_gmv_daily ORDER BY dod_pct ASC LIMIT 5
```

| order_dt | gmv | orders | aov | dod_pct |
| --- | --- | --- | --- | --- |
| 2024-11-06 | 36035.97 | 17 | 2119.76 | -61.25 |
| 2024-01-20 | 40486.77 | 16 | 2530.42 | -59.7 |
| 2024-05-17 | 41096.45 | 18 | 2283.14 | -59.22 |
| 2024-07-28 | 40608.71 | 16 | 2538.04 | -56.59 |
| 2024-06-15 | 35672.7 | 15 | 2378.18 | -55.06 |

_耗时 4.53s_
