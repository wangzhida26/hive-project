-- ============================================================
-- 云购生活新零售数仓 · 探索性数据分析（子任务7）
-- 基于 DWD 星型模型：事实表 dwd_order / dwd_order_item + 四张维度表
-- 产出：《探索性分析简报》全部数据
-- ============================================================

-- ------------------------------------------------------------
-- 一、核心 KPI：总订单量、总用户数、总 GMV、客单价
-- ------------------------------------------------------------
SELECT COUNT(DISTINCT order_id)                          AS total_orders,
       COUNT(DISTINCT user_id)                           AS total_users,
       ROUND(SUM(pay_amount), 2)                         AS total_gmv,
       ROUND(SUM(pay_amount) / COUNT(DISTINCT order_id), 2) AS avg_order_value
FROM ydsh_dwd.dwd_order
WHERE order_status IN ('已支付','已完成');

-- ------------------------------------------------------------
-- 二、订单状态分布
-- ------------------------------------------------------------
SELECT order_status, COUNT(*) AS orders, ROUND(SUM(pay_amount),2) AS amount
FROM ydsh_dwd.dwd_order GROUP BY order_status ORDER BY orders DESC;

-- ------------------------------------------------------------
-- 三、品类销售分布（明细行金额按类目汇总 Top）
-- ------------------------------------------------------------
SELECT p.category,
       COUNT(DISTINCT i.order_id) AS orders,
       SUM(i.quantity)            AS qty,
       ROUND(SUM(i.item_amount), 2) AS gmv
FROM ydsh_dwd.dwd_order_item i
JOIN ydsh_dwd.dim_product p ON i.product_id = p.product_id
GROUP BY p.category
ORDER BY gmv DESC;

-- ------------------------------------------------------------
-- 四、省份销售分布
-- ------------------------------------------------------------
SELECT s.province,
       COUNT(DISTINCT o.order_id)   AS orders,
       ROUND(SUM(o.pay_amount), 2)  AS gmv
FROM ydsh_dwd.dwd_order o
JOIN ydsh_dwd.dim_store s ON o.store_id = s.store_id
GROUP BY s.province
ORDER BY gmv DESC;

-- ------------------------------------------------------------
-- 五、门店销售 Top 10
-- ------------------------------------------------------------
SELECT s.store_name, s.city,
       COUNT(DISTINCT o.order_id)  AS orders,
       ROUND(SUM(o.pay_amount), 2) AS gmv
FROM ydsh_dwd.dwd_order o
JOIN ydsh_dwd.dim_store s ON o.store_id = s.store_id
GROUP BY s.store_name, s.city
ORDER BY gmv DESC
LIMIT 10;

-- ------------------------------------------------------------
-- 六、渠道与支付方式分布
-- ------------------------------------------------------------
SELECT channel, COUNT(*) AS orders, ROUND(SUM(pay_amount),2) AS amount
FROM ydsh_dwd.dwd_order GROUP BY channel ORDER BY orders DESC;
SELECT pay_type, COUNT(*) AS orders, ROUND(SUM(pay_amount),2) AS amount
FROM ydsh_dwd.dwd_order GROUP BY pay_type ORDER BY orders DESC;

-- ------------------------------------------------------------
-- 七、月度 GMV 趋势与环比（窗口函数 lag）
-- ------------------------------------------------------------
SELECT month, gmv,
       ROUND((gmv - LAG(gmv) OVER (ORDER BY month)) /
             LAG(gmv) OVER (ORDER BY month) * 100, 2) AS mom_pct
FROM (
  SELECT SUBSTR(order_dt, 1, 7) AS month, ROUND(SUM(pay_amount),2) AS gmv
  FROM ydsh_dwd.dwd_order
  WHERE order_status IN ('已支付','已完成')
  GROUP BY SUBSTR(order_dt, 1, 7)
) t;

-- ------------------------------------------------------------
-- 八、会员等级分布及其消费力
-- ------------------------------------------------------------
SELECT u.member_level,
       COUNT(DISTINCT u.user_id)     AS users,
       COUNT(DISTINCT o.order_id)    AS orders,
       ROUND(SUM(o.pay_amount), 2)   AS gmv,
       ROUND(SUM(o.pay_amount) / COUNT(DISTINCT u.user_id), 2) AS gmv_per_user
FROM ydsh_dwd.dwd_order o
JOIN ydsh_dwd.dim_user u ON o.user_id = u.user_id
GROUP BY u.member_level
ORDER BY gmv DESC;

-- ------------------------------------------------------------
-- 九、用户累计消费（窗口函数 sum over）与消费 Top 10
-- ------------------------------------------------------------
SELECT user_id, order_dt, pay_amount,
       ROUND(SUM(pay_amount) OVER (PARTITION BY user_id ORDER BY order_dt), 2) AS cum_amount
FROM ydsh_dwd.dwd_order
WHERE user_id IN ('U000001','U000002','U000003')
ORDER BY user_id, order_dt
LIMIT 9;

SELECT user_id, ROUND(SUM(pay_amount),2) AS total_amount, COUNT(*) AS orders
FROM ydsh_dwd.dwd_order
GROUP BY user_id
ORDER BY total_amount DESC
LIMIT 10;

-- ------------------------------------------------------------
-- 十、订单金额分层（RFM 前置观察）
-- ------------------------------------------------------------
SELECT CASE WHEN pay_amount < 1000 THEN 'a.1000元以下'
            WHEN pay_amount < 2000 THEN 'b.1000-2000元'
            WHEN pay_amount < 3000 THEN 'c.2000-3000元'
            WHEN pay_amount < 5000 THEN 'd.3000-5000元'
            ELSE 'e.5000元以上' END AS amount_bucket,
       COUNT(*) AS orders
FROM ydsh_dwd.dwd_order
GROUP BY CASE WHEN pay_amount < 1000 THEN 'a.1000元以下'
              WHEN pay_amount < 2000 THEN 'b.1000-2000元'
              WHEN pay_amount < 3000 THEN 'c.2000-3000元'
              WHEN pay_amount < 5000 THEN 'd.3000-5000元'
              ELSE 'e.5000元以上' END
ORDER BY amount_bucket;
