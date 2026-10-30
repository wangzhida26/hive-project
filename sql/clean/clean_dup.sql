-- ============================================================
-- 云购生活新零售数仓 · 数据清洗（一）重复值检测与去重
-- 目标：ods_order 重复订单 → ydsh_dwd.dwd_order
-- 两类重复区分（验收要求）：
--   A. 整行完全重复：所有字段一致，任意保留一条即可；
--   B. 主键重复但内容不同：按业务规则保留最新一条
--      （按 order_date + order_time 取最新，金额相同再按 pay_amount 兜底）。
-- ============================================================

-- ------------------------------------------------------------
-- 步骤 1：重复订单检测（记录重复 order_id 数量，与质量预评估阶段结果核对）
-- ------------------------------------------------------------
SELECT order_id, COUNT(*) AS c
FROM ydsh_ods.ods_order
GROUP BY order_id
HAVING COUNT(*) > 1;

-- 重复订单总数（重复的 order_id 有多少个）
SELECT COUNT(*) AS dup_order_ids FROM (
  SELECT order_id FROM ydsh_ods.ods_order GROUP BY order_id HAVING COUNT(*) > 1
) t;

-- 多余行数 = 去重将减少的行数 = 15600 - 去重后行数
SELECT COUNT(*) AS total_rows,
       COUNT(DISTINCT order_id) AS distinct_ids,
       COUNT(*) - COUNT(DISTINCT order_id) AS redundant_rows
FROM ydsh_ods.ods_order;

-- 判断重复属于哪一类：
-- A 类（整行完全重复）：
SELECT order_id, user_id, store_id, order_date, order_time, pay_amount,
       discount_amount, pay_type, order_status, channel, COUNT(*) AS c
FROM ydsh_ods.ods_order
GROUP BY order_id, user_id, store_id, order_date, order_time, pay_amount,
         discount_amount, pay_type, order_status, channel
HAVING COUNT(*) > 1;

-- ------------------------------------------------------------
-- 步骤 2：ROW_NUMBER 去重，生成 dwd_order（保留每单最新一条）
-- ------------------------------------------------------------
CREATE TABLE ydsh_dwd.dwd_order AS
SELECT order_id, user_id, store_id, order_date, order_time,
       pay_amount, discount_amount, pay_type, order_status, channel
FROM (
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY order_id
           ORDER BY order_date DESC, order_time DESC, pay_amount DESC
         ) AS rn
  FROM ydsh_ods.ods_order
) t
WHERE rn = 1;

-- ------------------------------------------------------------
-- 步骤 3：去重效果验证
--   ① 行数差 = 步骤 1 的 redundant_rows（与预评估阶段发现的重复数一致）
--   ② dwd_order 中 order_id 不再有重复
-- ------------------------------------------------------------
SELECT
  (SELECT COUNT(*) FROM ydsh_ods.ods_order)    AS before_cnt,
  (SELECT COUNT(*) FROM ydsh_dwd.dwd_order)    AS after_cnt,
  (SELECT COUNT(*) FROM ydsh_ods.ods_order) -
  (SELECT COUNT(*) FROM ydsh_dwd.dwd_order)    AS removed_rows;

SELECT order_id, COUNT(*) AS c
FROM ydsh_dwd.dwd_order
GROUP BY order_id
HAVING COUNT(*) > 1;   -- 预期 0 行

-- ------------------------------------------------------------
-- 附：其他表主键去重（如 user/behavior 出现重复可复用同一模式）
-- ------------------------------------------------------------
-- CREATE TABLE ydsh_dwd.dwd_user_behavior AS
-- SELECT * FROM (
--   SELECT *, ROW_NUMBER() OVER (PARTITION BY behavior_id ORDER BY behavior_time DESC) rn
--   FROM ydsh_ods.ods_user_behavior) t
-- WHERE rn = 1;
