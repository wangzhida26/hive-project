-- ============================================================
-- 云购生活新零售数仓 · 数据质量五维度预评估 SQL（ODS 层）
-- 五维度：完整性（空值率）/ 唯一性（主键重复）/ 有效性（枚举合法）
--         一致性（格式统一）/ 准确性（取值合理）
-- 字段依据：《项目总说明与模拟数据字典》4.2 节；结果填写《数据质量预评估表.xlsx》
-- ============================================================

-- ============================================================
-- 一、ods_user（用户信息表）
-- ============================================================
-- ① 完整性：关键字段空值率
SELECT COUNT(*) AS total,
  SUM(CASE WHEN user_id IS NULL OR user_id='' THEN 1 ELSE 0 END)  AS user_id_null,
  SUM(CASE WHEN age IS NULL THEN 1 ELSE 0 END)                    AS age_null,
  SUM(CASE WHEN email IS NULL OR email='' THEN 1 ELSE 0 END)      AS email_null,
  SUM(CASE WHEN phone IS NULL OR phone='' THEN 1 ELSE 0 END)      AS phone_null,
  SUM(CASE WHEN register_date IS NULL OR register_date='' THEN 1 ELSE 0 END) AS regdate_null
FROM ydsh_ods.ods_user;

-- ② 唯一性：主键重复
SELECT user_id, COUNT(*) AS c FROM ydsh_ods.ods_user GROUP BY user_id HAVING COUNT(*) > 1;

-- ③ 有效性：枚举字段取值分布（gender 应只有男/女，member_level 中英文混用）
SELECT gender, COUNT(*) FROM ydsh_ods.ods_user GROUP BY gender;
SELECT member_level, COUNT(*) FROM ydsh_ods.ods_user GROUP BY member_level;

-- ④ 一致性：注册日期格式是否统一（YYYY-MM-DD 长度应为 10，混有 2023/11/25 等斜杠格式）
SELECT LENGTH(register_date) AS len, COUNT(*) FROM ydsh_ods.ods_user GROUP BY LENGTH(register_date);
SELECT SUM(CASE WHEN register_date LIKE '%/%' THEN 1 ELSE 0 END) AS slash_format_cnt FROM ydsh_ods.ods_user;

-- ⑤ 准确性：年龄异常（<0 或 >120，如 200、-3）
SELECT COUNT(*) AS age_abnormal FROM ydsh_ods.ods_user WHERE age IS NOT NULL AND (age < 0 OR age > 120);

-- 附加（一致性）：手机号格式（应 11 位纯数字，混有 138-9212-7520）
SELECT SUM(CASE WHEN phone NOT REGEXP '^1[0-9]{10}$' THEN 1 ELSE 0 END) AS phone_bad_format
FROM ydsh_ods.ods_user;

-- ============================================================
-- 二、ods_product（商品信息表）
-- ============================================================
-- ① 完整性
SELECT COUNT(*) AS total,
  SUM(CASE WHEN product_id IS NULL OR product_id='' THEN 1 ELSE 0 END) AS pid_null,
  SUM(CASE WHEN product_name IS NULL OR product_name='' THEN 1 ELSE 0 END) AS pname_null,
  SUM(CASE WHEN category IS NULL OR category='' THEN 1 ELSE 0 END) AS category_null,
  SUM(CASE WHEN launch_date IS NULL OR launch_date='' THEN 1 ELSE 0 END) AS launch_null
FROM ydsh_ods.ods_product;

-- ② 唯一性：主键重复
SELECT product_id, COUNT(*) AS c FROM ydsh_ods.ods_product GROUP BY product_id HAVING COUNT(*) > 1;

-- ③ 有效性：类目/状态分布（category 有大小写/空格不一致）
SELECT category, COUNT(*) FROM ydsh_ods.ods_product GROUP BY category;
SELECT status, COUNT(*) FROM ydsh_ods.ods_product GROUP BY status;

-- ④ 一致性：上架日期格式统一性
SELECT LENGTH(launch_date) AS len, COUNT(*) FROM ydsh_ods.ods_product GROUP BY LENGTH(launch_date);

-- ⑤ 准确性：价格为负或异常高（>10000）、成本异常
SELECT COUNT(*) FROM ydsh_ods.ods_product WHERE price IS NOT NULL AND (price <= 0 OR price > 10000);
SELECT COUNT(*) FROM ydsh_ods.ods_product WHERE cost IS NOT NULL AND cost < 0;
SELECT COUNT(*) FROM ydsh_ods.ods_product WHERE price IS NOT NULL AND cost IS NOT NULL AND cost > price;

-- ============================================================
-- 三、ods_store（门店信息表）
-- ============================================================
-- ① 完整性
SELECT COUNT(*) AS total,
  SUM(CASE WHEN store_id IS NULL OR store_id='' THEN 1 ELSE 0 END) AS sid_null,
  SUM(CASE WHEN store_name IS NULL OR store_name='' THEN 1 ELSE 0 END) AS sname_null,
  SUM(CASE WHEN manager IS NULL OR manager='' THEN 1 ELSE 0 END) AS manager_null
FROM ydsh_ods.ods_store;

-- ② 唯一性：主键重复
SELECT store_id, COUNT(*) AS c FROM ydsh_ods.ods_store GROUP BY store_id HAVING COUNT(*) > 1;

-- ③ 有效性：省份分布（应覆盖全国 15 个省份/直辖市）
SELECT province, COUNT(*) FROM ydsh_ods.ods_store GROUP BY province;

-- ④ 一致性：省市取值口径与用户表对比
SELECT DISTINCT province FROM ydsh_ods.ods_store ORDER BY province;

-- ⑤ 准确性：开业日期晚于当前日期、营业面积异常（<=0 或 >10000㎡）
SELECT COUNT(*) FROM ydsh_ods.ods_store WHERE open_date > '2026-10-30';
SELECT COUNT(*) FROM ydsh_ods.ods_store WHERE area IS NOT NULL AND (area <= 0 OR area > 10000);

-- ============================================================
-- 四、ods_order（订单主表）★ 本周清洗重点（约 600 条重复）
-- ============================================================
-- ① 完整性：pay_amount 空值
SELECT COUNT(*) AS total,
  SUM(CASE WHEN pay_amount IS NULL OR pay_amount='' THEN 1 ELSE 0 END) AS pay_null,
  SUM(CASE WHEN user_id IS NULL OR user_id='' THEN 1 ELSE 0 END) AS user_null,
  SUM(CASE WHEN store_id IS NULL OR store_id='' THEN 1 ELSE 0 END) AS store_null
FROM ydsh_ods.ods_order;

-- ② 唯一性：主键重复（区分两类：
--    整行完全重复 → 所有字段一致；主键重复但内容不同 → 按业务规则保留一条）
SELECT order_id, COUNT(*) AS c FROM ydsh_ods.ods_order GROUP BY order_id HAVING COUNT(*) > 1;
-- 整行完全重复数：
SELECT COUNT(*) FROM (
  SELECT order_id, user_id, store_id, order_date, order_time, pay_amount,
         discount_amount, pay_type, order_status, channel, COUNT(*) AS c
  FROM ydsh_ods.ods_order GROUP BY order_id, user_id, store_id, order_date, order_time,
         pay_amount, discount_amount, pay_type, order_status, channel
  HAVING COUNT(*) > 1) t;

-- ③ 有效性：枚举字段分布（pay_type 中英文混用；order_status 不规范：已完成/1/cancelled）
SELECT pay_type, COUNT(*) FROM ydsh_ods.ods_order GROUP BY pay_type;
SELECT order_status, COUNT(*) FROM ydsh_ods.ods_order GROUP BY order_status;
SELECT channel, COUNT(*) FROM ydsh_ods.ods_order GROUP BY channel;

-- ④ 一致性：订单日期格式统一性（混有斜杠格式）
SELECT LENGTH(order_date) AS len, COUNT(*) FROM ydsh_ods.ods_order GROUP BY LENGTH(order_date);
SELECT SUM(CASE WHEN order_date LIKE '%/%' THEN 1 ELSE 0 END) AS slash_format_cnt FROM ydsh_ods.ods_order;

-- ⑤ 准确性：金额异常（负数、异常高 >100000）
SELECT COUNT(*) FROM ydsh_ods.ods_order WHERE pay_amount < 0;
SELECT COUNT(*) FROM ydsh_ods.ods_order WHERE pay_amount > 100000;
SELECT COUNT(*) FROM ydsh_ods.ods_order WHERE discount_amount < 0;

-- ============================================================
-- 五、ods_order_item（订单明细表）
-- ============================================================
-- ① 完整性
SELECT COUNT(*) AS total,
  SUM(CASE WHEN order_id IS NULL OR order_id='' THEN 1 ELSE 0 END) AS order_null,
  SUM(CASE WHEN product_id IS NULL OR product_id='' THEN 1 ELSE 0 END) AS pid_null,
  SUM(CASE WHEN quantity IS NULL THEN 1 ELSE 0 END) AS qty_null
FROM ydsh_ods.ods_order_item;

-- ② 唯一性：明细主键
SELECT item_id, COUNT(*) AS c FROM ydsh_ods.ods_order_item GROUP BY item_id HAVING COUNT(*) > 1;

-- ③ 有效性：数量取值（含 0、负数）与折扣率范围（0～1）
SELECT COUNT(*) FROM ydsh_ods.ods_order_item WHERE quantity IS NOT NULL AND quantity <= 0;
SELECT COUNT(*) FROM ydsh_ods.ods_order_item WHERE discount IS NOT NULL AND (discount < 0 OR discount > 1);

-- ④ 一致性：明细 order_id 是否都能在订单表找到（引用一致性）
SELECT COUNT(*) FROM ydsh_ods.ods_order_item i
LEFT JOIN ydsh_ods.ods_order o ON i.order_id = o.order_id
WHERE o.order_id IS NULL;

-- ⑤ 准确性：unit_price 异常（<=0 或与商品表 price 偏差过大抽样）
SELECT COUNT(*) FROM ydsh_ods.ods_order_item WHERE unit_price IS NOT NULL AND unit_price <= 0;

-- ============================================================
-- 六、ods_user_behavior（用户行为日志表）
-- ============================================================
-- ① 完整性
SELECT COUNT(*) AS total,
  SUM(CASE WHEN user_id IS NULL OR user_id='' THEN 1 ELSE 0 END) AS user_null,
  SUM(CASE WHEN behavior_type IS NULL OR behavior_type='' THEN 1 ELSE 0 END) AS type_null,
  SUM(CASE WHEN session_id IS NULL OR session_id='' THEN 1 ELSE 0 END) AS session_null
FROM ydsh_ods.ods_user_behavior;

-- ② 唯一性：行为记录主键
SELECT behavior_id, COUNT(*) AS c FROM ydsh_ods.ods_user_behavior GROUP BY behavior_id HAVING COUNT(*) > 1;

-- ③ 有效性：行为类型枚举（中英文混用：pv/cart/fav/buy/浏览/收藏/加购/购买）
SELECT behavior_type, COUNT(*) FROM ydsh_ods.ods_user_behavior GROUP BY behavior_type;

-- ④ 一致性：行为时间格式（应为 'YYYY-MM-DD HH:MM:SS'，长度 19，混有斜杠格式）
SELECT LENGTH(behavior_time) AS len, COUNT(*) FROM ydsh_ods.ods_user_behavior GROUP BY LENGTH(behavior_time);
SELECT SUM(CASE WHEN behavior_time LIKE '%/%' THEN 1 ELSE 0 END) AS slash_format_cnt FROM ydsh_ods.ods_user_behavior;

-- ⑤ 准确性：user_id 引用准确性（行为日志中出现不存在用户）
SELECT COUNT(*) FROM ydsh_ods.ods_user_behavior b
LEFT JOIN ydsh_ods.ods_user u ON b.user_id = u.user_id
WHERE u.user_id IS NULL;
