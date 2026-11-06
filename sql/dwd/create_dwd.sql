-- ============================================================
-- 云购生活新零售数仓 · DWD/DIM 层维度建模建表脚本（子任务5/6）
-- 架构：星型模型 —— 订单事实表为核心，外键关联用户/商品/门店/时间维度表
-- 存储优化：
--   1. 全部 ORC 列式存储（压缩比高、谓词下推）；
--   2. 事实表 dwd_order 按 order_dt（下单日期）分区 → 分区裁剪；
--   3. 明细表 dwd_order_item 按 order_id 分 8 桶 → 与事实表 join 时桶级关联；
--   4. 维度表 dim_user 按 user_id 分 4 桶。
-- 命名规范：ods_/dwd_/dws_/ads_ 业务表前缀；维度表统一 dim_ 前缀。
-- ============================================================

CREATE DATABASE IF NOT EXISTS ydsh_dwd;

-- ------------------------------------------------------------
-- 1. 维度表
-- ------------------------------------------------------------
-- 用户维度（分桶）
DROP TABLE IF EXISTS ydsh_dwd.dim_user PURGE;
CREATE TABLE ydsh_dwd.dim_user (
  user_id        string COMMENT '用户编号（主键/SCD 维度键）',
  user_name      string,
  gender         string COMMENT '男/女/未知（标准化后）',
  age            int    COMMENT '清洗填充后年龄',
  region         string COMMENT '省市合并：province+city',
  register_date  string COMMENT 'yyyy-MM-dd（格式统一后）',
  member_level   string COMMENT '金卡/银卡/普通/钻石会员/未知',
  phone          string COMMENT '11 位纯数字',
  email          string
)
CLUSTERED BY (user_id) INTO 4 BUCKETS
STORED AS ORC;

-- 商品维度
DROP TABLE IF EXISTS ydsh_dwd.dim_product PURGE;
CREATE TABLE ydsh_dwd.dim_product (
  product_id    string COMMENT '商品编号（主键）',
  product_name  string,
  category      string COMMENT '一级类目（去空格）',
  sub_category  string,
  brand         string,
  price         double COMMENT '修正后售价',
  cost          double,
  stock         int,
  status        string COMMENT '在售/下架/缺货',
  launch_date   string
)
STORED AS ORC;

-- 门店维度
DROP TABLE IF EXISTS ydsh_dwd.dim_store PURGE;
CREATE TABLE ydsh_dwd.dim_store (
  store_id    string COMMENT '门店编号（主键）',
  store_name  string,
  province    string,
  city        string,
  region      string COMMENT '省市合并',
  district    string,
  address     string,
  open_date   string,
  area        int,
  manager     string
)
STORED AS ORC;

-- 时间维度（由程序生成 2024 全年日历）
DROP TABLE IF EXISTS ydsh_dwd.dim_date PURGE;
CREATE TABLE ydsh_dwd.dim_date (
  date_key    string COMMENT 'yyyy-MM-dd（与事实表 order_dt 关联）',
  year        int,
  month       int,
  day         int,
  quarter     int,
  week_of_year int,
  day_of_week int COMMENT '1=周日 … 7=周六（Hive dayofweek 口径）'
)
STORED AS ORC;

-- ------------------------------------------------------------
-- 2. 事实表：订单明细事实（按日分区）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.dwd_order PURGE;
CREATE TABLE ydsh_dwd.dwd_order (
  order_id         string COMMENT '订单编号（主键，已去重）',
  user_id          string COMMENT '外键 → dim_user',
  store_id         string COMMENT '外键 → dim_store',
  order_timestamp  string COMMENT '下单时间 yyyy-MM-dd HH:mm:ss（date+time 合并）',
  pay_amount       double COMMENT '实付金额（负值已修正，大额异常已过滤）',
  discount_amount  double COMMENT '优惠金额',
  pay_type         string COMMENT '微信支付/支付宝/银行卡/货到付款',
  order_status     string COMMENT '待支付/已支付/已完成/已取消/退款中',
  channel          string COMMENT 'APP/PC官网/小程序/门店'
)
PARTITIONED BY (order_dt string COMMENT '下单日期 yyyy-MM-dd（分区键）')
STORED AS ORC;

-- ------------------------------------------------------------
-- 3. 事实表：订单明细行事实（分桶，支持与订单事实桶级 join）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dwd.dwd_order_item PURGE;
CREATE TABLE ydsh_dwd.dwd_order_item (
  item_id     string COMMENT '明细编号（主键）',
  order_id    string COMMENT '外键 → dwd_order',
  product_id  string COMMENT '外键 → dim_product',
  quantity    int    COMMENT '购买数量（≤0 已置空）',
  unit_price  double COMMENT '成交单价（空值已按商品维表价格回填）',
  discount    double COMMENT '折扣率 0~1',
  item_amount double COMMENT '行金额 = 数量×单价×折扣率（派生度量）'
)
CLUSTERED BY (order_id) INTO 8 BUCKETS
STORED AS ORC;
