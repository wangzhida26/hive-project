-- ============================================================
-- 云购生活新零售数仓 · DWS 汇总层建表（子任务1）
-- 输入：ydsh_dwd 明细层 → 输出：ydsh_dws 汇总层
-- 设计原则：
--   1. 只做「轻度汇总」，保留可下钻维度（日期/品类/门店/渠道），不做跨主题宽表；
--   2. 指标口径与《指标定义说明》一致：GMV 默认取有效订单（已支付/已完成）；
--   3. 统一 ORC 存储，按 order_dt 分区便于增量重跑。
-- 注意：本镜像开启 Hadoop 回收站，同名重建必须 DROP ... PURGE。
-- ============================================================

CREATE DATABASE IF NOT EXISTS ydsh_dws;

-- ------------------------------------------------------------
-- 1. 日粒度全站汇总：dws_order_1d
--    一行 = 一个订单日期，承载 GMV/订单量/用户数/客单价/有效订单/退款单
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dws.dws_order_1d PURGE;
CREATE TABLE ydsh_dws.dws_order_1d (
  order_dt        string  COMMENT '订单日期 yyyy-MM-dd',
  gmv             double  COMMENT '全站GMV（全部状态实付金额之和）',
  orders          bigint  COMMENT '订单量（去重 order_id）',
  paid_gmv        double  COMMENT '有效GMV（已支付+已完成）',
  paid_orders     bigint  COMMENT '有效订单量',
  refund_orders   bigint  COMMENT '退款中订单量',
  users           bigint  COMMENT '下单用户数（去重）',
  aov             double  COMMENT '客单价 = paid_gmv / paid_orders',
  cancel_rate     double  COMMENT '取消率 = 已取消订单 / 订单量'
)
STORED AS ORC;

-- ------------------------------------------------------------
-- 2. 日 × 品类汇总：dws_category_1d
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dws.dws_category_1d PURGE;
CREATE TABLE ydsh_dws.dws_category_1d (
  order_dt   string COMMENT '订单日期',
  category   string COMMENT '商品一级品类',
  gmv        double COMMENT '品类GMV（明细行金额口径）',
  qty        bigint COMMENT '销量（件）',
  orders     bigint COMMENT '涉及订单数'
)
STORED AS ORC;

-- ------------------------------------------------------------
-- 3. 日 × 门店汇总：dws_store_1d（同时带出省市，便于区域下钻）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dws.dws_store_1d PURGE;
CREATE TABLE ydsh_dws.dws_store_1d (
  order_dt    string COMMENT '订单日期',
  store_id    string COMMENT '门店ID',
  store_name  string COMMENT '门店名称',
  province    string COMMENT '省份',
  city        string COMMENT '城市',
  gmv         double COMMENT '门店GMV',
  orders      bigint COMMENT '门店订单量',
  users       bigint COMMENT '门店下单用户数'
)
STORED AS ORC;

-- ------------------------------------------------------------
-- 4. 日 × 渠道 × 支付方式汇总：dws_channel_1d
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dws.dws_channel_1d PURGE;
CREATE TABLE ydsh_dws.dws_channel_1d (
  order_dt  string COMMENT '订单日期',
  channel   string COMMENT '下单渠道',
  pay_type  string COMMENT '支付方式',
  gmv       double COMMENT 'GMV',
  orders    bigint COMMENT '订单量'
)
STORED AS ORC;

-- ------------------------------------------------------------
-- 5. 用户粒度累计汇总：dws_user_agg（复购/RFM 的底座）
-- ------------------------------------------------------------
DROP TABLE IF EXISTS ydsh_dws.dws_user_agg PURGE;
CREATE TABLE ydsh_dws.dws_user_agg (
  user_id         string COMMENT '用户ID',
  first_order_dt  string COMMENT '首单日期',
  last_order_dt   string COMMENT '末单日期',
  orders          bigint COMMENT '累计订单量',
  gmv             double COMMENT '累计GMV',
  aov             double COMMENT '用户客单价',
  repurchase_flag int    COMMENT '复购标记：1=下单≥2次，0=单次'
)
STORED AS ORC;

-- ------------------------------------------------------------
-- 6. ADS 层库（应用集市）
-- ------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS ydsh_ads;
