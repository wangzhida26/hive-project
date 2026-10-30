-- ============================================================
-- 云购生活新零售数仓 · ODS 贴源层建表脚本
-- 数据库：ydsh_ods
-- 字段依据：《项目总说明与模拟数据字典》4.2 节（已逐字段核对 CSV 表头）
-- 说明：
--   1. 所有表英文逗号分隔、跳过 1 行表头（CSV 带 UTF-8 BOM，跳表头后无影响）；
--   2. 贴源层脏数据（空值/负值/异常值/格式不一致）原样保留，清洗在 DWD 层做；
--   3. 数值字段按数据字典用 double/int，脏数据（如 -626.74、999999）不会导致类型转换失败。
-- 使用：beeline -u jdbc:hive2://localhost:10000 -f sql/ods/create_ods.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS ydsh_ods;

-- ------------------------------------------------------------
-- 1. 用户信息表（预期 1000 行）
--    脏数据：age 空/200/-3；gender 中英文混用；register_date 格式不一致；
--            member_level 中英文混用；phone 格式不一致；email 部分缺失
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ydsh_ods.ods_user (
  user_id        string,       -- 用户编号（主键）U000001
  user_name      string,       -- 用户姓名
  gender         string,       -- 性别（含异常值：男/女/M/F/未知）
  age            int,          -- 年龄（含缺失、异常：空/200/-3）
  city           string,
  province       string,
  register_date  string,       -- 注册日期（格式不一致：2023-11-25/2023/11/25）
  member_level   string,       -- 会员等级（中英文混用：金卡会员/gold）
  phone          string,       -- 手机号（格式不一致：138-9212-7520）
  email          string        -- 邮箱（部分缺失）
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
TBLPROPERTIES ('skip.header.line.count'='1');

-- ------------------------------------------------------------
-- 2. 商品信息表（预期 600 行）
--    脏数据：category 大小写/空格；brand 大小写；price 负数/异常高；launch_date 缺失
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ydsh_ods.ods_product (
  product_id    string,       -- 商品编号（主键）P00001
  product_name  string,       -- 商品名称
  category      string,       -- 一级类目（大小写/空格不一致）
  sub_category  string,       -- 二级类目
  brand         string,       -- 品牌（大小写异常）
  price         double,       -- 售价（含负数、异常高：-626.74/999999）
  cost          double,       -- 成本价
  stock         int,          -- 库存数量
  status        string,       -- 状态（在售/下架/缺货）
  launch_date   string        -- 上架日期（部分缺失）
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
TBLPROPERTIES ('skip.header.line.count'='1');

-- ------------------------------------------------------------
-- 3. 门店信息表（预期 60 行）
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ydsh_ods.ods_store (
  store_id    string,       -- 门店编号（主键）S001
  store_name  string,       -- 门店名称
  province    string,       -- 省份
  city        string,       -- 城市
  district    string,       -- 区县
  address     string,       -- 详细地址
  open_date   string,       -- 开业日期
  area        int,          -- 营业面积（㎡）
  manager     string        -- 店长姓名
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
TBLPROPERTIES ('skip.header.line.count'='1');

-- ------------------------------------------------------------
-- 4. 订单主表（预期 15600 行，含约 600 条重复订单 → DWD 去重）
--    脏数据：order_id 重复；order_date 格式不一致；pay_amount 负数/异常高；
--            pay_type 中英文混用；order_status 取值不规范（已完成/1/cancelled）；
--            channel 大小写混用
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ydsh_ods.ods_order (
  order_id         string,      -- 订单编号（应唯一，含重复）
  user_id          string,
  store_id         string,
  order_date       string,      -- 下单日期（格式不一致）
  order_time       string,      -- 下单时间
  pay_amount       double,      -- 实付金额（含负数、异常高）
  discount_amount  double,      -- 优惠金额
  pay_type         string,      -- 支付方式（中英文混用：微信支付/wechat/货到付款）
  order_status     string,      -- 订单状态（取值不规范：已完成/1/cancelled）
  channel          string       -- 下单渠道（大小写混用：APP/app/门店）
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
TBLPROPERTIES ('skip.header.line.count'='1');

-- ------------------------------------------------------------
-- 5. 订单明细表（预期 37549 行）
--    脏数据：quantity 含 0/负数/99 异常
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ydsh_ods.ods_order_item (
  item_id     string,        -- 明细编号（主键）I20250000001
  order_id    string,        -- 所属订单编号
  product_id  string,        -- 商品编号
  quantity    int,           -- 购买数量（含 0、负数）
  unit_price  double,        -- 商品单价
  discount    double         -- 折扣率（0～1）
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
TBLPROPERTIES ('skip.header.line.count'='1');

-- ------------------------------------------------------------
-- 6. 用户行为日志表（预期 60000 行）
--    脏数据：behavior_type 中英文混用；behavior_time 格式不一致
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ydsh_ods.ods_user_behavior (
  behavior_id    string,      -- 行为编号（主键）B00000001
  user_id        string,
  product_id     string,
  behavior_type  string,      -- 行为类型（中英文混用：pv/cart/fav/buy/浏览）
  behavior_time  string,      -- 行为发生时间（格式不一致）
  session_id     string       -- 会话编号 SES123456
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
TBLPROPERTIES ('skip.header.line.count'='1');
