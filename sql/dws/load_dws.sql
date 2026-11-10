-- ============================================================
-- 云购生活新零售数仓 · DWS 汇总层 ETL（子任务1）
-- 输入：ydsh_dwd.dwd_order / dwd_order_item / dim_* → 输出：ydsh_dws.*
-- 全部 INSERT OVERWRITE 全量重算（数据量小，保证口径可复现）
-- ============================================================

-- 1. 日粒度全站汇总
INSERT OVERWRITE TABLE ydsh_dws.dws_order_1d
SELECT order_dt,
       ROUND(SUM(pay_amount), 2)                                        AS gmv,
       COUNT(DISTINCT order_id)                                         AS orders,
       ROUND(SUM(CASE WHEN order_status IN ('已支付','已完成') THEN pay_amount ELSE 0 END), 2) AS paid_gmv,
       COUNT(DISTINCT CASE WHEN order_status IN ('已支付','已完成') THEN order_id END)          AS paid_orders,
       COUNT(DISTINCT CASE WHEN order_status = '退款中' THEN order_id END)                     AS refund_orders,
       COUNT(DISTINCT user_id)                                          AS users,
       ROUND(SUM(CASE WHEN order_status IN ('已支付','已完成') THEN pay_amount ELSE 0 END)
             / COUNT(DISTINCT CASE WHEN order_status IN ('已支付','已完成') THEN order_id END), 2) AS aov,
       ROUND(COUNT(DISTINCT CASE WHEN order_status = '已取消' THEN order_id END)
             / COUNT(DISTINCT order_id), 4)                             AS cancel_rate
FROM ydsh_dwd.dwd_order
GROUP BY order_dt;

-- 2. 日 × 品类汇总
INSERT OVERWRITE TABLE ydsh_dws.dws_category_1d
SELECT o.order_dt,
       p.category,
       ROUND(SUM(i.item_amount), 2) AS gmv,
       SUM(i.quantity)              AS qty,
       COUNT(DISTINCT o.order_id)   AS orders
FROM ydsh_dwd.dwd_order_item i
JOIN ydsh_dwd.dwd_order   o ON i.order_id   = o.order_id
JOIN ydsh_dwd.dim_product p ON i.product_id = p.product_id
GROUP BY o.order_dt, p.category;

-- 3. 日 × 门店汇总
INSERT OVERWRITE TABLE ydsh_dws.dws_store_1d
SELECT o.order_dt,
       o.store_id,
       s.store_name,
       s.province,
       s.city,
       ROUND(SUM(o.pay_amount), 2)      AS gmv,
       COUNT(DISTINCT o.order_id)       AS orders,
       COUNT(DISTINCT o.user_id)        AS users
FROM ydsh_dwd.dwd_order o
JOIN ydsh_dwd.dim_store s ON o.store_id = s.store_id
GROUP BY o.order_dt, o.store_id, s.store_name, s.province, s.city;

-- 4. 日 × 渠道 × 支付方式汇总
INSERT OVERWRITE TABLE ydsh_dws.dws_channel_1d
SELECT order_dt, channel, pay_type,
       ROUND(SUM(pay_amount), 2) AS gmv,
       COUNT(DISTINCT order_id)  AS orders
FROM ydsh_dwd.dwd_order
GROUP BY order_dt, channel, pay_type;

-- 5. 用户粒度累计汇总
INSERT OVERWRITE TABLE ydsh_dws.dws_user_agg
SELECT user_id,
       MIN(order_dt)                AS first_order_dt,
       MAX(order_dt)                AS last_order_dt,
       COUNT(DISTINCT order_id)     AS orders,
       ROUND(SUM(pay_amount), 2)    AS gmv,
       ROUND(SUM(pay_amount) / COUNT(DISTINCT order_id), 2) AS aov,
       CASE WHEN COUNT(DISTINCT order_id) >= 2 THEN 1 ELSE 0 END AS repurchase_flag
FROM ydsh_dwd.dwd_order
GROUP BY user_id;

-- 6. 汇总结果校验
SELECT 'dws_order_1d'    t, COUNT(*) c FROM ydsh_dws.dws_order_1d
UNION ALL SELECT 'dws_category_1d', COUNT(*) FROM ydsh_dws.dws_category_1d
UNION ALL SELECT 'dws_store_1d',    COUNT(*) FROM ydsh_dws.dws_store_1d
UNION ALL SELECT 'dws_channel_1d',  COUNT(*) FROM ydsh_dws.dws_channel_1d
UNION ALL SELECT 'dws_user_agg',    COUNT(*) FROM ydsh_dws.dws_user_agg;
