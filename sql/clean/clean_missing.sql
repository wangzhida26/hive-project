-- ============================================================
-- 云购生活新零售数仓 · 数据清洗（一）缺失值诊断与处理
-- 目标表：ydsh_dwd.dwd_user（用户表）、ydsh_dwd.dwd_product（商品表）
-- 策略记录（写入质量报告素材）：
--   1. ods_user.age        空值/负值/>120 → 均值填充（仅统计 1~120 的合理年龄）
--   2. ods_user.email      空值 → 保留并统一标记为 'unknown@'（不臆造数据）
--   3. ods_product.launch_date 空值 → 按品类规则补全（此处用同品类最早
--      上架日期填充；无法判定时标记 'unknown'）
-- 注意：Hive 默认普通表不支持 UPDATE ... SET，统一用 CTAS 生成 DWD 表。
-- ============================================================

CREATE DATABASE IF NOT EXISTS ydsh_dwd;

-- ------------------------------------------------------------
-- 步骤 0：缺失值诊断（执行前先记录各字段缺失数量，作为清洗前基线）
-- ------------------------------------------------------------
SELECT COUNT(*) AS total,
  SUM(CASE WHEN age IS NULL OR age < 0 OR age > 120 THEN 1 ELSE 0 END) AS age_missing,
  SUM(CASE WHEN email IS NULL OR email='' THEN 1 ELSE 0 END) AS email_missing
FROM ydsh_ods.ods_user;

SELECT COUNT(*) AS total,
  SUM(CASE WHEN launch_date IS NULL OR launch_date='' THEN 1 ELSE 0 END) AS launch_missing
FROM ydsh_ods.ods_product;

-- ------------------------------------------------------------
-- 步骤 1：计算年龄填充均值（仅用合理区间 1~120 的数据）
-- ------------------------------------------------------------
SELECT ROUND(AVG(age)) AS age_avg
FROM ydsh_ods.ods_user
WHERE age BETWEEN 1 AND 120;
-- 将查得的均值代入下方 <age_avg>（例如结果为 30 就写 30）。
-- 也可两步合并：直接在 CTAS 里用子查询计算均值，见步骤 2 写法 A。

-- ------------------------------------------------------------
-- 步骤 2：生成 dwd_user（年龄均值填充 + 邮箱标记）
-- ------------------------------------------------------------
-- 写法 A（推荐）：均值在子查询中自动计算，无需手工代入
CREATE TABLE ydsh_dwd.dwd_user AS
SELECT user_id, user_name, gender,
       COALESCE(
         CASE WHEN age BETWEEN 1 AND 120 THEN age END,
         (SELECT ROUND(AVG(age)) FROM ydsh_ods.ods_user WHERE age BETWEEN 1 AND 120)
       ) AS age,
       city, province, register_date, member_level, phone,
       CASE WHEN email IS NULL OR email='' THEN 'unknown@' ELSE email END AS email
FROM ydsh_ods.ods_user;

-- 写法 B：手工代入均值（写法 A 在低版本 Hive 不支持标量子查询时使用）
-- CREATE TABLE ydsh_dwd.dwd_user AS
-- SELECT user_id, user_name, gender,
--        COALESCE(CASE WHEN age BETWEEN 1 AND 120 THEN age END, 30) AS age,  -- 30 替换为实测均值
--        city, province, register_date, member_level, phone,
--        CASE WHEN email IS NULL OR email='' THEN 'unknown@' ELSE email END AS email
-- FROM ydsh_ods.ods_user;

-- ------------------------------------------------------------
-- 步骤 3：生成 dwd_product（上架日期按品类规则补全）
-- ------------------------------------------------------------
CREATE TABLE ydsh_dwd.dwd_product AS
SELECT p.product_id, p.product_name, p.category, p.brand, p.price,
       COALESCE(
         NULLIF(p.launch_date, ''),
         MIN(NULLIF(p.launch_date,'')) OVER (PARTITION BY p.category)
       ) AS launch_date
FROM ydsh_ods.ods_product p;
-- 说明：同品类仍有全缺失时结果仍为 NULL，可再用 'unknown' 兜底：
-- SELECT product_id, ..., COALESCE(launch_date, 'unknown') AS launch_date FROM ydsh_dwd.dwd_product;

-- ------------------------------------------------------------
-- 步骤 4：清洗效果验证（验收标准：空值率显著下降）
-- ------------------------------------------------------------
-- dwd_user：age 不应再有 NULL / 负值 / 超 120
SELECT COUNT(*) AS age_abnormal FROM ydsh_dwd.dwd_user
WHERE age IS NULL OR age < 0 OR age > 120;   -- 预期 0

SELECT COUNT(*) AS total,
  SUM(CASE WHEN email='unknown@' THEN 1 ELSE 0 END) AS email_marked
FROM ydsh_dwd.dwd_user;                       -- email_marked = 清洗前 email_missing 数

-- dwd_product：launch_date 空值应显著减少
SELECT SUM(CASE WHEN launch_date IS NULL OR launch_date='' OR launch_date='unknown' THEN 1 ELSE 0 END)
FROM ydsh_dwd.dwd_product;
