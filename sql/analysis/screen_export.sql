-- 大屏数据导出：省份汇总 / 时段×品类热力 / 门店Top / 支付方式汇总
-- 结果通过 beeline csv2 导出后由 export_screen_data.py 装配为 screen_data.js

-- 1) 省份汇总（地图 + 散点：GMV vs 订单数）
SELECT province,
       ROUND(SUM(gmv), 2)  AS gmv,
       SUM(orders)         AS orders,
       COUNT(DISTINCT store_id) AS stores
FROM ydsh_dws.dws_store_1d
GROUP BY province
ORDER BY gmv DESC;

-- 2) 时段×品类 热力（有效订单口径，GMV）
SELECT o.hour_of_day        AS hr,
       p.category           AS category,
       ROUND(SUM(i.item_amount), 2) AS gmv
FROM (
  SELECT order_id, order_dt, CAST(SUBSTR(order_timestamp, 12, 2) AS INT) AS hour_of_day
  FROM ydsh_dwd.dwd_order
  WHERE order_status IN ('已支付', '已完成')
) o
JOIN ydsh_dwd.dwd_order_item i ON i.order_id = o.order_id
JOIN ydsh_dwd.dim_product p    ON i.product_id = p.product_id
GROUP BY o.hour_of_day, p.category
ORDER BY o.hour_of_day, p.category;

-- 3) 门店 Top12
SELECT store_name, province, city, ROUND(gmv,2) AS gmv, orders, users
FROM ydsh_ads.ads_store_sales
ORDER BY rk
LIMIT 12;

-- 4) 支付方式汇总（饼图）
SELECT pay_type,
       ROUND(SUM(gmv), 2) AS gmv,
       SUM(orders)        AS orders
FROM ydsh_ads.ads_channel_sales
GROUP BY pay_type
ORDER BY gmv DESC;
