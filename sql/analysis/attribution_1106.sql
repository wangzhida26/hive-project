-- ============================================================================
-- 异常归因分析：2024-11-06 GMV 环比骤降归因
-- 口径：有效订单（已支付 / 已完成）
-- 对比基准：2024-10-30 ~ 2024-11-05 共 7 日的日均值
-- ============================================================================

-- 1. 当日整体表现
SELECT '总体' AS dim, order_dt AS k, ROUND(gmv,2) AS gmv, orders, ROUND(aov,2) AS aov
FROM ydsh_ads.ads_gmv_daily
WHERE order_dt IN ('2024-11-05','2024-11-06')
ORDER BY order_dt;

-- 2. 品类维度：当日 vs 前 7 日均值
SELECT p.category,
       ROUND(SUM(CASE WHEN o.order_dt = '2024-11-06' THEN i.item_amount ELSE 0 END), 2) AS gmv_1106,
       ROUND(SUM(CASE WHEN o.order_dt BETWEEN '2024-10-30' AND '2024-11-05'
                      THEN i.item_amount ELSE 0 END) / 7, 2) AS gmv_avg7,
       ROUND(SUM(CASE WHEN o.order_dt = '2024-11-06' THEN i.item_amount ELSE 0 END)
             - SUM(CASE WHEN o.order_dt BETWEEN '2024-10-30' AND '2024-11-05'
                        THEN i.item_amount ELSE 0 END) / 7, 2) AS diff
FROM ydsh_dwd.dwd_order_item i
JOIN ydsh_dwd.dwd_order o ON i.order_id = o.order_id
JOIN ydsh_dwd.dim_product p ON i.product_id = p.product_id
WHERE o.order_status IN ('已支付','已完成')
  AND o.order_dt BETWEEN '2024-10-30' AND '2024-11-06'
GROUP BY p.category
ORDER BY diff ASC;

-- 3. 门店维度：当日 vs 前 7 日均值（跌幅 Top8）
SELECT s.store_name,
       ROUND(SUM(CASE WHEN o.order_dt = '2024-11-06' THEN o.pay_amount ELSE 0 END), 2) AS gmv_1106,
       ROUND(SUM(CASE WHEN o.order_dt BETWEEN '2024-10-30' AND '2024-11-05'
                      THEN o.pay_amount ELSE 0 END) / 7, 2) AS gmv_avg7,
       ROUND(SUM(CASE WHEN o.order_dt = '2024-11-06' THEN o.pay_amount ELSE 0 END)
             - SUM(CASE WHEN o.order_dt BETWEEN '2024-10-30' AND '2024-11-05'
                        THEN o.pay_amount ELSE 0 END) / 7, 2) AS diff
FROM ydsh_dwd.dwd_order o
JOIN ydsh_dwd.dim_store s ON o.store_id = s.store_id
WHERE o.order_status IN ('已支付','已完成')
  AND o.order_dt BETWEEN '2024-10-30' AND '2024-11-06'
GROUP BY s.store_name
ORDER BY diff ASC
LIMIT 8;

-- 4. 渠道 / 支付方式维度
SELECT o.channel,
       ROUND(SUM(CASE WHEN o.order_dt = '2024-11-06' THEN o.pay_amount ELSE 0 END), 2) AS gmv_1106,
       ROUND(SUM(CASE WHEN o.order_dt BETWEEN '2024-10-30' AND '2024-11-05'
                      THEN o.pay_amount ELSE 0 END) / 7, 2) AS gmv_avg7
FROM ydsh_dwd.dwd_order o
WHERE o.order_status IN ('已支付','已完成')
  AND o.order_dt BETWEEN '2024-10-30' AND '2024-11-06'
GROUP BY o.channel
ORDER BY gmv_avg7 DESC;

-- 5. 订单状态结构对比（判断是否为「少卖」还是「订单被取消/未支付」）
SELECT order_dt, order_status, COUNT(*) AS orders, ROUND(SUM(pay_amount),2) AS amount
FROM ydsh_dwd.dwd_order
WHERE order_dt IN ('2024-11-05','2024-11-06')
GROUP BY order_dt, order_status
ORDER BY order_dt, orders DESC;

-- 6. 客单价结构：当日是否存在小额订单集中
SELECT order_dt, COUNT(*) AS orders,
       ROUND(AVG(pay_amount),2) AS avg_amt,
       ROUND(MAX(pay_amount),2) AS max_amt,
       SUM(CASE WHEN pay_amount < 1000 THEN 1 ELSE 0 END) AS lt_1000,
       SUM(CASE WHEN pay_amount >= 5000 THEN 1 ELSE 0 END) AS ge_5000
FROM ydsh_dwd.dwd_order
WHERE order_dt IN ('2024-11-05','2024-11-06') AND order_status IN ('已支付','已完成')
GROUP BY order_dt ORDER BY order_dt;
