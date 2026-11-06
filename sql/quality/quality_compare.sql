-- ============================================================
-- 清洗前后五类脏数据量化对比（产出《数据质量对比报告》）
-- 前：ydsh_ods.ods_*   后：ydsh_dwd.stg3_*
-- ============================================================

-- ============ 第一部分：清洗前（ODS 基线） ============

-- 类1 重复记录：订单主键重复
SELECT 'pre_dup_order' item, CAST(COUNT(*)-COUNT(DISTINCT order_id) AS string) val
FROM ydsh_ods.ods_order;

-- 类2 金额异常：负金额
SELECT 'pre_neg_amount' item, CAST(COUNT(*) AS string) val
FROM ydsh_ods.ods_order WHERE pay_amount < 0;
-- 类2 金额异常：大额断档（>=10万）
SELECT 'pre_huge_amount' item, CAST(COUNT(*) AS string) val
FROM ydsh_ods.ods_order WHERE pay_amount >= 100000;

-- 类3 日期格式不统一：斜杠日期（订单）
SELECT 'pre_slash_order_date' item, CAST(COUNT(*) AS string) val
FROM ydsh_ods.ods_order WHERE order_date LIKE '%/%';
-- 类3 日期格式不统一：斜杠日期（用户注册日期）
SELECT 'pre_slash_reg_date' item, CAST(COUNT(*) AS string) val
FROM ydsh_ods.ods_user WHERE register_date LIKE '%/%';

-- 类4 手机号格式不统一（非 1 开头 11 位纯数字）
SELECT 'pre_phone_bad' item, CAST(COUNT(*) AS string) val
FROM ydsh_ods.ods_user WHERE phone NOT REGEXP '^1[0-9]{10}$';

-- 类5 枚举混乱：性别取值个数
SELECT 'pre_gender_kinds' item, CAST(COUNT(DISTINCT gender) AS string) val
FROM ydsh_ods.ods_user;
-- 类5 枚举混乱：支付方式取值个数（订单表存中文+英文编码混用）
SELECT 'pre_paytype_kinds' item, CAST(COUNT(DISTINCT pay_type) AS string) val
FROM ydsh_ods.ods_order;
-- 类5 枚举混乱：行为类型取值个数
SELECT 'pre_behavior_kinds' item, CAST(COUNT(DISTINCT behavior_type) AS string) val
FROM ydsh_ods.ods_user_behavior;
-- 类5 枚举混乱：会员等级取值个数
SELECT 'pre_member_kinds' item, CAST(COUNT(DISTINCT member_level) AS string) val
FROM ydsh_ods.ods_user;

-- ============ 第二部分：清洗后（stg3 管道末端） ============

-- 类1 重复记录
SELECT 'post_dup_order' item, CAST(COUNT(*)-COUNT(DISTINCT order_id) AS string) val
FROM ydsh_dwd.stg3_order;

-- 类2 金额异常
SELECT 'post_neg_amount' item, CAST(COUNT(*) AS string) val
FROM ydsh_dwd.stg3_order WHERE pay_amount < 0;
SELECT 'post_huge_amount' item, CAST(COUNT(*) AS string) val
FROM ydsh_dwd.stg3_order WHERE pay_amount >= 100000;

-- 类3 日期格式不统一：order_dt 非 yyyy-MM-dd
SELECT 'post_bad_order_dt' item, CAST(COUNT(*) AS string) val
FROM ydsh_dwd.stg3_order WHERE order_dt NOT REGEXP '^2[0-9]{3}-[0-9]{2}-[0-9]{2}$';
-- 时间戳非 19 位
SELECT 'post_bad_ts' item, CAST(COUNT(*) AS string) val
FROM ydsh_dwd.stg3_order WHERE LENGTH(order_timestamp) <> 19;

-- 类4 手机号格式不统一
SELECT 'post_phone_bad' item, CAST(COUNT(*) AS string) val
FROM ydsh_dwd.stg3_user WHERE phone NOT REGEXP '^1[0-9]{10}$';

-- 类5 枚举混乱：性别非法值
SELECT 'post_gender_bad' item, CAST(COUNT(*) AS string) val
FROM ydsh_dwd.stg3_user WHERE gender NOT IN ('男','女','未知');
-- 支付方式非法值
SELECT 'post_paytype_bad' item, CAST(COUNT(*) AS string) val
FROM ydsh_dwd.stg3_order WHERE pay_type NOT IN ('微信支付','支付宝','银行卡','货到付款');
-- 订单状态非法值
SELECT 'post_status_bad' item, CAST(COUNT(*) AS string) val
FROM ydsh_dwd.stg3_order WHERE order_status NOT IN ('待支付','已支付','已完成','已取消','退款中');
-- 会员等级非法值
SELECT 'post_member_bad' item, CAST(COUNT(*) AS string) val
FROM ydsh_dwd.stg3_user WHERE member_level NOT IN ('金卡会员','银卡会员','普通会员','钻石会员','未知');

-- 行数对账
SELECT 'stg3_order_rows' item, CAST(COUNT(*) AS string) val FROM ydsh_dwd.stg3_order;
SELECT 'stg3_user_rows' item, CAST(COUNT(*) AS string) val FROM ydsh_dwd.stg3_user;
SELECT 'dwd_order_rows' item, CAST(COUNT(*) AS string) val FROM ydsh_dwd.dwd_order;
