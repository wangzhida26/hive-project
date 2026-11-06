-- ============================================================
-- 云购生活新零售数仓 · 数据清洗（二）子任务1：枚举字段标准化
-- 输入：ydsh_ods 贴源表 → 输出：stg1_* 枚举标准化层（清洗管道第 1 站）
-- 清洗管道：stg1_*（枚举）→ stg2_*（异常与格式，见 clean_abnormal_format.sql）
--           → dwd_*（拆分合并与最终明细，见 clean_split_merge.sql）
-- 标准值域（参照数据字典 + ODS 取值扫描，2026-11-02）：
--   gender         → 男 / 女 / 未知          （扫描到 8 种写法 + 空 84）
--   member_level   → 金卡会员/银卡会员/普通会员/钻石会员/未知（9 种写法 + 空 14）
--   pay_type       → 微信支付/支付宝/银行卡/货到付款（7 种写法，不规范 651）
--   order_status   → 待支付/已支付/已完成/已取消/退款中（7 种写法，不规范 1375）
--     数字编码映射：1=待支付 2=已支付 3=已完成 4=已取消（按业务顺序推断，已在报告注明）
--   channel        → APP/PC官网/小程序/门店（大小写混用，不规范 310）
--   behavior_type  → 浏览/加购/收藏/购买（12 种写法，不规范 57551）
--   status(商品)   → 在售/下架/缺货（已规范，无需处理）
-- 注意：本镜像开启 Hadoop 回收站，同名重建表必须用 DROP ... PURGE，
--       普通 DROP 后同目录残留会导致读到旧数据（已实测踩坑，详见环境笔记）。
-- 继承说明：年龄均值填充/邮箱标记/ROW_NUMBER 去重为第 1 周清洗逻辑，
--           本周随管道重建一并保留。
-- ============================================================

CREATE DATABASE IF NOT EXISTS ydsh_dwd;

-- ------------------------------------------------------------
-- 步骤 0：清洗前取值扫描（基线，写入质量对比报告）
-- ------------------------------------------------------------
SELECT gender, COUNT(*) AS c FROM ydsh_ods.ods_user GROUP BY gender;
SELECT member_level, COUNT(*) AS c FROM ydsh_ods.ods_user GROUP BY member_level;
SELECT pay_type, COUNT(*) AS c FROM ydsh_ods.ods_order GROUP BY pay_type;
SELECT order_status, COUNT(*) AS c FROM ydsh_ods.ods_order GROUP BY order_status;
SELECT channel, COUNT(*) AS c FROM ydsh_ods.ods_order GROUP BY channel;
SELECT behavior_type, COUNT(*) AS c FROM ydsh_ods.ods_user_behavior GROUP BY behavior_type;

-- ------------------------------------------------------------
-- 步骤 1：stg1_user（第1周：年龄均值填充+邮箱标记；本周新增：性别/会员等级标准化）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg1_user PURGE;
CREATE TABLE ydsh_dwd.stg1_user AS
SELECT user_id, user_name,
       CASE WHEN gender IN ('男','M','male','Male')                 THEN '男'
            WHEN gender IN ('女','F','female','Female')             THEN '女'
            ELSE '未知'
       END                                                        AS gender,
       COALESCE(
         CASE WHEN age BETWEEN 1 AND 120 THEN age END,
         (SELECT ROUND(AVG(age)) FROM ydsh_ods.ods_user WHERE age BETWEEN 1 AND 120)
       )                                                          AS age,
       city, province, register_date,
       CASE WHEN member_level IN ('金卡会员','金卡','gold')        THEN '金卡会员'
            WHEN member_level IN ('银卡会员','银卡','silver')      THEN '银卡会员'
            WHEN member_level IN ('普通会员','普通','normal')      THEN '普通会员'
            WHEN member_level IN ('钻石会员','钻石')               THEN '钻石会员'
            ELSE '未知'
       END                                                        AS member_level,
       phone,
       CASE WHEN email IS NULL OR email='' THEN 'unknown@' ELSE email END AS email
FROM ydsh_ods.ods_user;

-- ------------------------------------------------------------
-- 步骤 2：stg1_order（第1周 ROW_NUMBER 去重；本周新增：支付方式/状态/渠道标准化）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg1_order PURGE;
CREATE TABLE ydsh_dwd.stg1_order AS
SELECT order_id, user_id, store_id, order_date, order_time,
       pay_amount, discount_amount,
       CASE WHEN pay_type IN ('微信支付','微信','wechat')   THEN '微信支付'
            WHEN pay_type IN ('支付宝','alipay')            THEN '支付宝'
            WHEN pay_type = '银行卡'                        THEN '银行卡'
            WHEN pay_type = '货到付款'                      THEN '货到付款'
            ELSE '未知'
       END                                                 AS pay_type,
       CASE WHEN order_status IN ('已完成','完成','3')      THEN '已完成'
            WHEN order_status IN ('已支付','已付款','2')    THEN '已支付'
            WHEN order_status IN ('待支付','1')             THEN '待支付'
            WHEN order_status IN ('已取消','cancelled','4') THEN '已取消'
            WHEN order_status = '退款中'                    THEN '退款中'
            ELSE '未知'
       END                                                 AS order_status,
       CASE WHEN channel IN ('APP','app')   THEN 'APP'
            WHEN channel IN ('PC官网','pc')  THEN 'PC官网'
            WHEN channel = '小程序'          THEN '小程序'
            WHEN channel = '门店'            THEN '门店'
            ELSE '未知'
       END                                                 AS channel
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
-- 步骤 3：stg1_product（本周新增：类目去空格；状态已规范直接沿用）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg1_product PURGE;
CREATE TABLE ydsh_dwd.stg1_product AS
SELECT product_id, product_name,
       TRIM(category)                                              AS category,
       TRIM(sub_category)                                          AS sub_category,
       TRIM(brand)                                                 AS brand,
       price, cost, stock, status,
       COALESCE(
         NULLIF(launch_date, ''),
         MIN(NULLIF(launch_date,'')) OVER (PARTITION BY TRIM(category))
       )                                                           AS launch_date
FROM ydsh_ods.ods_product;

-- ------------------------------------------------------------
-- 步骤 4：stg1_user_behavior（本周新增：行为类型统一为中文标准值）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg1_user_behavior PURGE;
CREATE TABLE ydsh_dwd.stg1_user_behavior AS
SELECT behavior_id, user_id, product_id,
       CASE WHEN behavior_type IN ('浏览','pv','PV')    THEN '浏览'
            WHEN behavior_type IN ('加购','cart','Cart') THEN '加购'
            WHEN behavior_type IN ('收藏','fav','FAV')   THEN '收藏'
            WHEN behavior_type IN ('购买','buy','BUY')   THEN '购买'
            ELSE '未知'
       END                                              AS behavior_type,
       behavior_time, session_id
FROM ydsh_ods.ods_user_behavior;

-- ------------------------------------------------------------
-- 步骤 5：stg1_order_item（无枚举字段，透传；数量/单价格式处理在下一站）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.stg1_order_item PURGE;
CREATE TABLE ydsh_dwd.stg1_order_item AS
SELECT item_id, order_id, product_id, quantity, unit_price, discount
FROM ydsh_ods.ods_order_item;

-- ------------------------------------------------------------
-- 步骤 6：标准化效果验证（验收标准：各字段 distinct 收敛到规范值域）
-- ------------------------------------------------------------
SELECT gender, COUNT(*) FROM ydsh_dwd.stg1_user GROUP BY gender;
SELECT member_level, COUNT(*) FROM ydsh_dwd.stg1_user GROUP BY member_level;
SELECT pay_type, COUNT(*) FROM ydsh_dwd.stg1_order GROUP BY pay_type;
SELECT order_status, COUNT(*) FROM ydsh_dwd.stg1_order GROUP BY order_status;
SELECT channel, COUNT(*) FROM ydsh_dwd.stg1_order GROUP BY channel;
SELECT behavior_type, COUNT(*) FROM ydsh_dwd.stg1_user_behavior GROUP BY behavior_type;
SELECT category, COUNT(*) FROM ydsh_dwd.stg1_product GROUP BY category;
-- 行数校验（清洗不应丢行：15000/1000/600/60000/37549）
SELECT 'stg1_order' t, COUNT(*) FROM ydsh_dwd.stg1_order
UNION ALL SELECT 'stg1_user', COUNT(*) FROM ydsh_dwd.stg1_user
UNION ALL SELECT 'stg1_product', COUNT(*) FROM ydsh_dwd.stg1_product
UNION ALL SELECT 'stg1_user_behavior', COUNT(*) FROM ydsh_dwd.stg1_user_behavior
UNION ALL SELECT 'stg1_order_item', COUNT(*) FROM ydsh_dwd.stg1_order_item;
