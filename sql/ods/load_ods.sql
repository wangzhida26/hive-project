-- ============================================================
-- 云购生活新零售数仓 · ODS 层数据导入与行数校验脚本
-- 前提：
--   1. 6 张 CSV 已放入宿主机 ./data 目录（docker-compose 已挂载为容器 /data）；
--   2. CSV 为英文逗号分隔、首行为表头；
--   3. 建表脚本 sql/ods/create_ods.sql 已执行。
-- 使用：beeline -u jdbc:hive2://localhost:10000 -f sql/ods/load_ods.sql
-- ============================================================

-- 1. 导入 6 张表（load 为追加语义，重复执行前先清空或 drop 重建，避免行数翻倍）
LOAD DATA LOCAL INPATH '/data/ods_user.csv'         INTO TABLE ydsh_ods.ods_user;
LOAD DATA LOCAL INPATH '/data/ods_product.csv'      INTO TABLE ydsh_ods.ods_product;
LOAD DATA LOCAL INPATH '/data/ods_store.csv'        INTO TABLE ydsh_ods.ods_store;
LOAD DATA LOCAL INPATH '/data/ods_order.csv'        INTO TABLE ydsh_ods.ods_order;
LOAD DATA LOCAL INPATH '/data/ods_order_item.csv'   INTO TABLE ydsh_ods.ods_order_item;
LOAD DATA LOCAL INPATH '/data/ods_user_behavior.csv' INTO TABLE ydsh_ods.ods_user_behavior;

-- 2. 行数校验（与数据字典预期行数对比，允许因脏数据少量偏差）
SELECT 'ods_user'          AS tbl, COUNT(*) AS cnt FROM ydsh_ods.ods_user
UNION ALL SELECT 'ods_product',       COUNT(*) FROM ydsh_ods.ods_product
UNION ALL SELECT 'ods_store',         COUNT(*) FROM ydsh_ods.ods_store
UNION ALL SELECT 'ods_order',         COUNT(*) FROM ydsh_ods.ods_order
UNION ALL SELECT 'ods_order_item',    COUNT(*) FROM ydsh_ods.ods_order_item
UNION ALL SELECT 'ods_user_behavior', COUNT(*) FROM ydsh_ods.ods_user_behavior;

-- 预期行数：
--   ods_user          1000
--   ods_product        600
--   ods_store           60
--   ods_order        15600
--   ods_order_item   37549
--   ods_user_behavior 60000

-- 3. 抽样预览（确认字段错位/中文乱码问题）
SELECT * FROM ydsh_ods.ods_user    LIMIT 5;
SELECT * FROM ydsh_ods.ods_order   LIMIT 5;
SELECT * FROM ydsh_ods.ods_product LIMIT 5;

-- ============================================================
-- 行数对不上速查：
--   多 1 行   → 漏了 TBLPROPERTIES ('skip.header.line.count'='1')
--   行数 = 1  → 分隔符写错（表被当成一行），确认 CSV 是英文逗号
--   行数翻倍  → load 重复执行，drop 表重建后再导
--   乱码/错位 → CSV 编码需为 UTF-8，字段与建表语句一一对应
-- ============================================================
