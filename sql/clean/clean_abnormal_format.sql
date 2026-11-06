-- ============================================================
-- 云购生活新零售数仓 · 数据清洗（二）子任务2：异常值与格式标准化
-- 输入：stg1_* 枚举标准化层 → 输出：stg2_* 异常与格式标准化层（清洗管道第 2 站）
-- 清洗管道：stg1_*（枚举）→ stg2_*（本脚本）→ dwd_*（clean_split_merge.sql）
-- 注意：本镜像开启 Hadoop 回收站，同名重建表必须用 DROP ... PURGE
--       （普通 DROP 后同目录残留会读到旧数据，已实测踩坑，详见环境笔记）。
-- 清洗策略（阈值均来自 ODS 实测分布，2026-11-02）：
--   1. pay_amount：负值 310 条（-25.19 ~ -4994.73，与正常区间一致，
--      且各订单状态均有分布 → 判定为录入符号错误）→ 取绝对值修正；
--      大额 ≥10000 共 312 条（实测 ≥100000，主体分布 0~5000、中位数 2494，
--      5000~100000 完全断档）→ 无法可信还原，加载 DWD 事实表时过滤（见 sql/dwd/load_dwd.sql）；
--   2. discount_amount：负优惠 769 条 → 符号错误，取绝对值修正；
--   3. price：≤0 共 20 条、异常大 ≥10000 共 16 条（主体 <10000、中位数 4593）
--      → 按同品类中位价修正（共 36 条）；
--   4. quantity：≤0 共 718 条 → 置 NULL（无法还原，报告列为遗留问题）；
--      unit_price：≤0 共 798 条 → 置 NULL，DWD 加载时用商品维表价格回填；
--   5. 日期格式：register_date 斜杠格式 100 条、8 位紧凑格式 25 条；order_date
--      斜杠格式 1902 条 → 统一 yyyy-MM-dd；
--   6. phone：带 '-' 分隔符 102 条 → 去分隔符统一 11 位；
--   7. behavior_time：16 位 'yyyy/MM/dd HH:mm' 共 6088 条 → 统一 'yyyy-MM-dd HH:mm:ss'。
-- ============================================================

-- ------------------------------------------------------------
-- 步骤 1：stg2_user（日期 + 手机号格式标准化）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg2_user PURGE;
CREATE TABLE ydsh_dwd.stg2_user AS
SELECT user_id, user_name, gender, age, city, province,
       CASE WHEN register_date LIKE '%/%'           THEN regexp_replace(register_date, '/', '-')
            WHEN LENGTH(register_date) = 8          THEN concat(substr(register_date,1,4),'-',
                                                                substr(register_date,5,2),'-',
                                                                substr(register_date,7,2))
            ELSE register_date
       END                                          AS register_date,
       member_level,
       regexp_replace(phone, '-', '')               AS phone,
       email
FROM ydsh_dwd.stg1_user;
-- 说明：gender/age/member_level/email 已在第 1 站处理，此处仅改格式字段。

-- ------------------------------------------------------------
-- 步骤 2：stg2_order（金额异常修正 + 日期格式统一）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg2_order PURGE;
CREATE TABLE ydsh_dwd.stg2_order AS
SELECT order_id, user_id, store_id,
       regexp_replace(order_date, '/', '-')         AS order_date,
       order_time,
       CASE WHEN pay_amount < 0   THEN ABS(pay_amount)   -- 符号错误修正
            ELSE pay_amount
       END                                          AS pay_amount,
       CASE WHEN discount_amount < 0 THEN ABS(discount_amount)
            ELSE discount_amount
       END                                          AS discount_amount,
       pay_type, order_status, channel
FROM ydsh_dwd.stg1_order;
-- 注：异常大额（pay_amount ≥ 10000，共 312 条）不在本步删除，
--     统一在 DWD 事实表加载时过滤，保证清洗分层可追溯（报告"处理策略"栏）。

-- ------------------------------------------------------------
-- 步骤 3：stg2_product（价格异常按同品类中位价修正）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.tmp_med PURGE;
CREATE TABLE ydsh_dwd.tmp_med AS
SELECT category, percentile_approx(price, 0.5) AS med_price
FROM ydsh_dwd.stg1_product
WHERE price > 0 AND price < 10000
GROUP BY category;

DROP TABLE IF EXISTS ydsh_dwd.stg2_product PURGE;
CREATE TABLE ydsh_dwd.stg2_product AS
SELECT p.product_id, p.product_name, p.category, p.sub_category, p.brand,
       CASE WHEN p.price IS NULL OR p.price <= 0 OR p.price >= 10000
            THEN m.med_price
            ELSE p.price
       END                                          AS price,
       p.cost, p.stock, p.status, p.launch_date
FROM ydsh_dwd.stg1_product p
JOIN ydsh_dwd.tmp_med m ON p.category = m.category;

-- ------------------------------------------------------------
-- 步骤 4：stg2_order_item（数量/单价异常置 NULL，单价在 DWD 加载时回填）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg2_order_item PURGE;
CREATE TABLE ydsh_dwd.stg2_order_item AS
SELECT item_id, order_id, product_id,
       CASE WHEN quantity > 0 THEN quantity END     AS quantity,
       CASE WHEN unit_price > 0 THEN unit_price END AS unit_price,
       discount
FROM ydsh_dwd.stg1_order_item;

-- ------------------------------------------------------------
-- 步骤 5：stg2_user_behavior（行为时间格式统一为 yyyy-MM-dd HH:mm:ss）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg2_user_behavior PURGE;
CREATE TABLE ydsh_dwd.stg2_user_behavior AS
SELECT behavior_id, user_id, product_id, behavior_type,
       CASE WHEN LENGTH(behavior_time) = 16          -- 'yyyy/MM/dd HH:mm'
            THEN concat(regexp_replace(substr(behavior_time,1,10), '/', '-'), ' ',
                        substr(behavior_time,12,5), ':00')
            ELSE regexp_replace(behavior_time, '/', '-')
       END                                           AS behavior_time,
       session_id
FROM ydsh_dwd.stg1_user_behavior;

-- ------------------------------------------------------------
-- 步骤 6：清洗效果验证
-- ------------------------------------------------------------
-- ① 金额无负值、大额仅剩待过滤的 304 条（去重后口径，下一步在事实表加载过滤）
SELECT 'pay_neg' item, COUNT(*) cnt FROM ydsh_dwd.stg2_order WHERE pay_amount < 0
UNION ALL SELECT 'pay_ge10000', COUNT(*) FROM ydsh_dwd.stg2_order WHERE pay_amount >= 10000
UNION ALL SELECT 'disc_neg', COUNT(*) FROM ydsh_dwd.stg2_order WHERE discount_amount < 0
UNION ALL SELECT 'price_bad', COUNT(*) FROM ydsh_dwd.stg2_product WHERE price IS NULL OR price <= 0 OR price >= 10000
UNION ALL SELECT 'qty_le0', COUNT(*) FROM ydsh_dwd.stg2_order_item WHERE quantity IS NOT NULL AND quantity <= 0
UNION ALL SELECT 'unitp_le0', COUNT(*) FROM ydsh_dwd.stg2_order_item WHERE unit_price IS NOT NULL AND unit_price <= 0;
-- ② 格式收敛：日期长度、手机号、行为时间
SELECT 'reg_date_len' item, CAST(LENGTH(register_date) AS string) fmt, COUNT(*) cnt
FROM ydsh_dwd.stg2_user GROUP BY LENGTH(register_date);
SELECT 'phone_bad' item, COUNT(*) cnt FROM ydsh_dwd.stg2_user WHERE phone NOT REGEXP '^1[0-9]{10}$';
SELECT 'order_slash' item, COUNT(*) cnt FROM ydsh_dwd.stg2_order WHERE order_date LIKE '%/%';
SELECT 'btime_len' item, CAST(LENGTH(behavior_time) AS string) fmt, COUNT(*) cnt
FROM ydsh_dwd.stg2_user_behavior GROUP BY LENGTH(behavior_time);
