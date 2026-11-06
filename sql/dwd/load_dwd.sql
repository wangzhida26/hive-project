-- ============================================================
-- 云购生活新零售数仓 · DWD/DIM 层 ETL 加载脚本（子任务6）
-- 输入：清洗管道产物（ydsh_dwd.stg3_* 拆分合并层、stg2_* 异常格式层、ydsh_ods.ods_store）
-- 输出：星型模型 4 张维度表 + 2 张事实表
-- 关键点：
--   1. 事实表加载时过滤异常大额订单（pay_amount≥10000 共 312 条，断档判定见
--      clean_abnormal_format.sql 头注），并记录过滤后行数供质量对比报告；
--   2. 明细表 unit_price 空值（798 条）用商品维表价格回填；
--   3. 动态分区加载 dwd_order，加载后 show partitions 验证分区裁剪可用。
-- ============================================================

SET hive.exec.dynamic.partition = true;
SET hive.exec.dynamic.partition.mode = nonstrict;
-- 全年 366 个日期分区，需调高动态分区上限（默认 100）
SET hive.exec.max.dynamic.partitions = 1000;
SET hive.exec.max.dynamic.partitions.pernode = 1000;

-- ------------------------------------------------------------
-- 1. 维度表加载
-- ------------------------------------------------------------
-- 用户维度（来自 stg3 拆分合并层，含 region）
INSERT OVERWRITE TABLE ydsh_dwd.dim_user
SELECT user_id, user_name, gender, age, region, register_date, member_level, phone, email
FROM ydsh_dwd.stg3_user;

-- 商品维度
INSERT OVERWRITE TABLE ydsh_dwd.dim_product
SELECT product_id, product_name, category, sub_category, brand, price, cost, stock, status, launch_date
FROM ydsh_dwd.stg2_product;

-- 门店维度（ods_store 已干净，直接加工 region）
INSERT OVERWRITE TABLE ydsh_dwd.dim_store
SELECT store_id, store_name, province, city, concat(province, city) AS region,
       district, address, open_date, area, manager
FROM ydsh_ods.ods_store;

-- 时间维度（生成 2024-01-01 ~ 2024-12-31 日历，366 天）
-- 注：本镜像无 sequence() 函数，用 split(space(n)) + posexplode 生成序列
INSERT OVERWRITE TABLE ydsh_dwd.dim_date
SELECT d                                                  AS date_key,
       YEAR(d)                                            AS year,
       MONTH(d)                                           AS month,
       DAY(d)                                             AS day,
       QUARTER(d)                                         AS quarter,
       WEEKOFYEAR(d)                                      AS week_of_year,
       DAYOFWEEK(d)                                       AS day_of_week
FROM (
  SELECT date_add('2024-01-01', CAST(pos AS INT)) AS d
  FROM (SELECT 1 x) t LATERAL VIEW posexplode(split(space(365), ' ')) v AS pos, val
) dates;

-- ------------------------------------------------------------
-- 2. 订单事实表加载（动态分区 + 异常大额过滤）
--    加载前行数 15000（去重后），过滤大额 312 条 → 预期 14688
-- ------------------------------------------------------------
INSERT OVERWRITE TABLE ydsh_dwd.dwd_order PARTITION (order_dt)
SELECT order_id, user_id, store_id, order_timestamp,
       pay_amount, discount_amount, pay_type, order_status, channel,
       order_dt
FROM ydsh_dwd.stg3_order
WHERE pay_amount IS NOT NULL AND pay_amount < 10000;

-- ------------------------------------------------------------
-- 3. 明细行事实表加载（unit_price 空值按商品价格回填，派生行金额）
-- ------------------------------------------------------------
INSERT OVERWRITE TABLE ydsh_dwd.dwd_order_item
SELECT i.item_id, i.order_id, i.product_id,
       i.quantity,
       COALESCE(i.unit_price, p.price)                      AS unit_price,
       i.discount,
       ROUND(i.quantity * COALESCE(i.unit_price, p.price) * COALESCE(i.discount, 1), 2) AS item_amount
FROM ydsh_dwd.stg2_order_item i
LEFT JOIN ydsh_dwd.dim_product p ON i.product_id = p.product_id;

-- ------------------------------------------------------------
-- 4. 加载效果验证
-- ------------------------------------------------------------
-- ① 分区验证：应出现 2024 全年日期分区
SHOW PARTITIONS ydsh_dwd.dwd_order;
-- ② 行数：dim 1000/600/60/366；fact 14688；item 37549
SELECT 'dim_user' t, COUNT(*) c FROM ydsh_dwd.dim_user
UNION ALL SELECT 'dim_product', COUNT(*) FROM ydsh_dwd.dim_product
UNION ALL SELECT 'dim_store', COUNT(*) FROM ydsh_dwd.dim_store
UNION ALL SELECT 'dim_date', COUNT(*) FROM ydsh_dwd.dim_date
UNION ALL SELECT 'dwd_order', COUNT(*) FROM ydsh_dwd.dwd_order
UNION ALL SELECT 'dwd_order_item', COUNT(*) FROM ydsh_dwd.dwd_order_item;
-- ③ 分区裁剪生效（执行计划应显示只扫一个分区）
EXPLAIN SELECT COUNT(*) FROM ydsh_dwd.dwd_order WHERE order_dt = '2024-06-01';
-- ④ 引用完整性抽查：明细 order_id 应全部能在事实表命中（因大额过滤会少量失配，观察量级）
SELECT COUNT(*) AS item_unmatched
FROM ydsh_dwd.dwd_order_item i
LEFT JOIN ydsh_dwd.dwd_order o ON i.order_id = o.order_id
WHERE o.order_id IS NULL;
