-- ============================================================
-- 云购生活新零售数仓 · ADS 应用层 ETL（子任务1）
-- 输入：ydsh_dws 汇总层 / ydsh_dwd 明细层 → 输出：ydsh_ads 应用表
-- 说明：涉及「去重用户数」的指标必须回到 DWD 计算，
--       DWS 日汇总的用户数跨天相加会重复计数（实测踩坑，已修正）。
-- ============================================================

-- 1. 核心 KPI 总览（单行）
INSERT OVERWRITE TABLE ydsh_ads.ads_kpi_overview
SELECT '2024-01-01 ~ 2024-12-31' AS stat_period,
       o.gmv, o.orders, o.aov, o.active_users,
       u.repurchase_rate, u.avg_orders_user,
       c.category_top, c.category_share,
       s.store_top, o.refund_rate
FROM (
  SELECT ROUND(SUM(CASE WHEN order_status IN ('已支付','已完成') THEN pay_amount ELSE 0 END), 2) AS gmv,
         COUNT(DISTINCT CASE WHEN order_status IN ('已支付','已完成') THEN order_id END)          AS orders,
         ROUND(SUM(CASE WHEN order_status IN ('已支付','已完成') THEN pay_amount ELSE 0 END)
               / COUNT(DISTINCT CASE WHEN order_status IN ('已支付','已完成') THEN order_id END), 2) AS aov,
         COUNT(DISTINCT user_id)                                                         AS active_users,
         ROUND(COUNT(DISTINCT CASE WHEN order_status = '退款中' THEN order_id END)
               / COUNT(DISTINCT order_id), 4)                                            AS refund_rate
  FROM ydsh_dwd.dwd_order
) o
CROSS JOIN (
  SELECT ROUND(SUM(repurchase_flag) / COUNT(*), 4) AS repurchase_rate,
         ROUND(SUM(orders) / COUNT(*), 2)          AS avg_orders_user
  FROM ydsh_dws.dws_user_agg
) u
CROSS JOIN (
  SELECT '运动户外' AS category_top,
         ROUND(SUM(CASE WHEN p.category = '运动户外' THEN i.item_amount ELSE 0 END)
               / SUM(i.item_amount) * 100, 2) AS category_share
  FROM ydsh_dwd.dwd_order_item i
  JOIN ydsh_dwd.dim_product p ON i.product_id = p.product_id
) c
CROSS JOIN (
  SELECT store_name AS store_top FROM ydsh_dws.dws_store_1d
  GROUP BY store_name ORDER BY SUM(gmv) DESC LIMIT 1
) s;

-- 2. 日度 GMV 趋势（7 日移动平均 + 日环比 + 周末标记）
INSERT OVERWRITE TABLE ydsh_ads.ads_gmv_daily
SELECT order_dt, gmv, orders, aov,
       ROUND(AVG(gmv) OVER (ORDER BY order_dt ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS ma7,
       ROUND((gmv - LAG(gmv) OVER (ORDER BY order_dt)) / LAG(gmv) OVER (ORDER BY order_dt) * 100, 2) AS dod_pct,
       CAST(dayofweek(order_dt) AS int)                           AS weekday,
       CASE WHEN dayofweek(order_dt) IN (1, 7) THEN 1 ELSE 0 END AS is_weekend
FROM (
  SELECT order_dt, paid_gmv AS gmv, paid_orders AS orders, aov
  FROM ydsh_dws.dws_order_1d
  WHERE paid_orders > 0
) t;

-- 3. 品类销售排行 + GMV 占比
INSERT OVERWRITE TABLE ydsh_ads.ads_category_sales
SELECT rk, category, gmv, qty, orders,
       ROUND(gmv / SUM(gmv) OVER () * 100, 2) AS share_pct
FROM (
  SELECT ROW_NUMBER() OVER (ORDER BY SUM(gmv) DESC) AS rk,
         category, ROUND(SUM(gmv), 2) AS gmv,
         SUM(qty) AS qty, SUM(orders) AS orders
  FROM ydsh_dws.dws_category_1d
  GROUP BY category
) t;

-- 4. 门店销售排行（去重用户数回 DWD 计算）
INSERT OVERWRITE TABLE ydsh_ads.ads_store_sales
SELECT ROW_NUMBER() OVER (ORDER BY SUM(o.pay_amount) DESC) AS rk,
       s.store_name, s.province, s.city,
       ROUND(SUM(o.pay_amount), 2) AS gmv,
       COUNT(DISTINCT o.order_id)  AS orders,
       COUNT(DISTINCT o.user_id)   AS users
FROM ydsh_dwd.dwd_order o
JOIN ydsh_dwd.dim_store s ON o.store_id = s.store_id
GROUP BY s.store_name, s.province, s.city;

-- 5. 渠道 × 支付方式
INSERT OVERWRITE TABLE ydsh_ads.ads_channel_sales
SELECT channel, pay_type, gmv, orders,
       ROUND(gmv / SUM(gmv) OVER () * 100, 2) AS share_pct
FROM (
  SELECT channel, pay_type, ROUND(SUM(gmv), 2) AS gmv, SUM(orders) AS orders
  FROM ydsh_dws.dws_channel_1d
  GROUP BY channel, pay_type
) t;

-- 6. 用户价值分层（RFM，基准日 2024-12-31）
--    打分改用 NTILE(4) 分位法：固定阈值在本数据集下全部落同一档（人均 14.7 单），无区分度
INSERT OVERWRITE TABLE ydsh_ads.ads_user_value
SELECT user_id, recency, frequency, monetary, r_score, f_score, m_score,
       CASE WHEN r_score >= 3 AND f_score >= 3 THEN '重要价值'
            WHEN r_score <  3 AND f_score >= 3 THEN '重要保持'
            WHEN r_score >= 3 AND f_score <  3 THEN '一般价值'
            ELSE '流失预警' END AS segment
FROM (
  SELECT user_id, recency, frequency, monetary,
         NTILE(4) OVER (ORDER BY recency DESC)  AS r_score,  -- 越久未下单分越低
         NTILE(4) OVER (ORDER BY frequency)     AS f_score,
         NTILE(4) OVER (ORDER BY monetary)      AS m_score
  FROM (
    SELECT user_id,
           DATEDIFF('2024-12-31', last_order_dt) AS recency,
           orders AS frequency,
           gmv    AS monetary
    FROM ydsh_dws.dws_user_agg
  ) t0
) t;

-- 7. 校验
SELECT 'ads_kpi_overview'  t, COUNT(*) c FROM ydsh_ads.ads_kpi_overview
UNION ALL SELECT 'ads_gmv_daily',     COUNT(*) FROM ydsh_ads.ads_gmv_daily
UNION ALL SELECT 'ads_category_sales',COUNT(*) FROM ydsh_ads.ads_category_sales
UNION ALL SELECT 'ads_store_sales',   COUNT(*) FROM ydsh_ads.ads_store_sales
UNION ALL SELECT 'ads_channel_sales', COUNT(*) FROM ydsh_ads.ads_channel_sales
UNION ALL SELECT 'ads_user_value',    COUNT(*) FROM ydsh_ads.ads_user_value;
