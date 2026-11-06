-- ============================================================
-- 云购生活新零售数仓 · 数据清洗（二）子任务3：字段拆分合并与编码映射
-- 输入：stg2_* 异常与格式标准化层 → 输出：stg3_* 拆分合并层（清洗管道第 3 站）
-- 清洗管道：stg1_*（枚举）→ stg2_*（异常与格式）→ stg3_*（本脚本）
--           → 星型模型加载（sql/dwd/load_dwd.sql 由 stg3_* 与 stg2_* 装载 dim_*/事实表）
-- 内容：
--   1. 订单表 order_date + order_time 合并为 order_timestamp（yyyy-MM-dd HH:mm:ss），
--      并派生 order_dt（日期部分，作为 DWD 事实表分区键）；
--   2. 用户表 province + city 合并为 region；
--   3. 建立编码映射维度表 dim_pay_type / dim_member_level（编码→中文标准名），
--      并与 case when 结果做交叉校验（join 不上的应为 0 行）；
-- 注意：本镜像开启 Hadoop 回收站，同名重建表必须用 DROP ... PURGE
--       （普通 DROP 后同目录残留会读到旧数据，已实测踩坑，详见环境笔记）。
-- ============================================================

-- ------------------------------------------------------------
-- 步骤 1：编码映射维度表（维度建模：编码类小维表）
--   code 存 ODS 原始编码，name 存标准中文名；dim 层关联时用 code → name
-- ------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS ydsh_dwd;

DROP TABLE IF EXISTS ydsh_dwd.dim_pay_type PURGE;
CREATE TABLE ydsh_dwd.dim_pay_type (
  code  string COMMENT '原始编码：wechat/alipay/cod/card',
  name  string COMMENT '标准中文名'
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE;

INSERT INTO ydsh_dwd.dim_pay_type VALUES
  ('wechat', '微信支付'),
  ('alipay', '支付宝'),
  ('card',   '银行卡'),
  ('cod',    '货到付款');

DROP TABLE IF EXISTS ydsh_dwd.dim_member_level PURGE;
CREATE TABLE ydsh_dwd.dim_member_level (
  code  string COMMENT '原始编码：gold/silver/normal/diamond',
  name  string COMMENT '标准中文名'
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE;

INSERT INTO ydsh_dwd.dim_member_level VALUES
  ('gold',    '金卡会员'),
  ('silver',  '银卡会员'),
  ('normal',  '普通会员'),
  ('diamond', '钻石会员');

-- ------------------------------------------------------------
-- 步骤 2：订单表合并 order_timestamp（最终 dwd_order）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg3_order PURGE;
CREATE TABLE ydsh_dwd.stg3_order AS
SELECT order_id, user_id, store_id,
       concat(order_date, ' ', order_time)         AS order_timestamp,
       substr(order_date, 1, 10)                   AS order_dt,
       pay_amount, discount_amount, pay_type, order_status, channel
FROM ydsh_dwd.stg2_order;

-- 映射校验：stg3_order.pay_type 与编码表口径核对（join 不上的应为 0 行）
SELECT CASE WHEN m.name IS NULL THEN '未映射' ELSE '已映射' END AS flag,
       o.pay_type, COUNT(*) AS cnt
FROM ydsh_dwd.stg3_order o
LEFT JOIN ydsh_dwd.dim_pay_type m ON o.pay_type = m.name
GROUP BY CASE WHEN m.name IS NULL THEN '未映射' ELSE '已映射' END, o.pay_type
ORDER BY flag DESC, cnt DESC;

-- ------------------------------------------------------------
-- 步骤 3：用户表合并 region（最终 dwd_user）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg3_user PURGE;
CREATE TABLE ydsh_dwd.stg3_user AS
SELECT user_id, user_name, gender, age,
       concat(province, city)                      AS region,
       register_date, member_level, phone, email
FROM ydsh_dwd.stg2_user;

-- 会员等级映射校验（stg3_user.member_level 应全部落在编码表 name 内）
SELECT CASE WHEN m.name IS NULL THEN '未映射' ELSE '已映射' END AS flag,
       COUNT(*) AS cnt
FROM ydsh_dwd.stg3_user u
LEFT JOIN ydsh_dwd.dim_member_level m ON u.member_level = m.name
GROUP BY CASE WHEN m.name IS NULL THEN '未映射' ELSE '已映射' END
ORDER BY cnt DESC;

-- ------------------------------------------------------------
-- 步骤 4：合并效果验证
-- ------------------------------------------------------------
-- order_timestamp 格式应为 yyyy-MM-dd HH:mm:ss（长度 19）
SELECT 'ts_len' item, CAST(LENGTH(order_timestamp) AS string) fmt, COUNT(*) cnt
FROM ydsh_dwd.stg3_order GROUP BY LENGTH(order_timestamp);
-- 样例
SELECT order_id, order_timestamp, order_dt FROM ydsh_dwd.stg3_order LIMIT 5;
SELECT user_id, region, register_date FROM ydsh_dwd.stg3_user LIMIT 5;
-- 行数校验（15000 / 1000）
SELECT 'stg3_order' t, COUNT(*) FROM ydsh_dwd.stg3_order
UNION ALL SELECT 'stg3_user', COUNT(*) FROM ydsh_dwd.stg3_user;
