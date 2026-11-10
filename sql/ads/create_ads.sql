-- ============================================================
-- 云购生活新零售数仓 · ADS 应用层建表（子任务1）
-- 输入：ydsh_dws 汇总层 → 输出：ydsh_ads 应用集市（一表一看板主题）
-- 命名：ads_<主题>[_粒度]
-- ============================================================

-- 1. 核心 KPI 总览（一行，供答辩首页）
DROP TABLE IF EXISTS ydsh_ads.ads_kpi_overview PURGE;
CREATE TABLE ydsh_ads.ads_kpi_overview (
  stat_period     string COMMENT '统计周期',
  gmv             double COMMENT '有效GMV（已支付+已完成）',
  orders          bigint COMMENT '有效订单量',
  aov             double COMMENT '客单价 = GMV/订单量',
  active_users    bigint COMMENT '活跃用户数（有下单行为）',
  repurchase_rate double COMMENT '复购率 = 下单≥2次用户/下单用户',
  avg_orders_user double COMMENT '人均下单次数',
  category_top    string COMMENT 'GMV 第一品类',
  category_share  double COMMENT '第一品类GMV占比',
  store_top       string COMMENT 'GMV 第一门店',
  refund_rate     double COMMENT '退款率 = 退款中订单/全部订单'
)
STORED AS ORC;

-- 2. 日度 GMV 趋势（含 7 日移动平均、环比、周末标记）
DROP TABLE IF EXISTS ydsh_ads.ads_gmv_daily PURGE;
CREATE TABLE ydsh_ads.ads_gmv_daily (
  order_dt   string COMMENT '日期',
  gmv        double COMMENT '当日GMV',
  orders     bigint COMMENT '当日订单量',
  aov        double COMMENT '当日客单价',
  ma7        double COMMENT '7日移动平均GMV',
  dod_pct    double COMMENT '日环比（%）',
  weekday    int    COMMENT '星期几（Hive dayofweek：1=周日 … 7=周六）',
  is_weekend int    COMMENT '是否周末'
)
STORED AS ORC;

-- 3. 品类销售排行（TopN + 占比）
DROP TABLE IF EXISTS ydsh_ads.ads_category_sales PURGE;
CREATE TABLE ydsh_ads.ads_category_sales (
  rk        int    COMMENT '排名',
  category  string COMMENT '品类',
  gmv       double COMMENT 'GMV',
  qty       bigint COMMENT '销量',
  orders    bigint COMMENT '订单数',
  share_pct double COMMENT 'GMV占比（%）'
)
STORED AS ORC;

-- 4. 门店销售排行
DROP TABLE IF EXISTS ydsh_ads.ads_store_sales PURGE;
CREATE TABLE ydsh_ads.ads_store_sales (
  rk         int    COMMENT '排名',
  store_name string COMMENT '门店',
  province   string COMMENT '省份',
  city       string COMMENT '城市',
  gmv        double COMMENT 'GMV',
  orders     bigint COMMENT '订单量',
  users      bigint COMMENT '下单用户数'
)
STORED AS ORC;

-- 5. 渠道 × 支付方式交叉销售
DROP TABLE IF EXISTS ydsh_ads.ads_channel_sales PURGE;
CREATE TABLE ydsh_ads.ads_channel_sales (
  channel   string COMMENT '渠道',
  pay_type  string COMMENT '支付方式',
  gmv       double COMMENT 'GMV',
  orders    bigint COMMENT '订单量',
  share_pct double COMMENT 'GMV占比（%）'
)
STORED AS ORC;

-- 6. 用户价值分层（RFM）
DROP TABLE IF EXISTS ydsh_ads.ads_user_value PURGE;
CREATE TABLE ydsh_ads.ads_user_value (
  user_id     string COMMENT '用户ID',
  recency     int    COMMENT 'R：距最后下单天数（基准日 2024-12-31）',
  frequency   bigint COMMENT 'F：累计订单数',
  monetary    double COMMENT 'M：累计GMV',
  r_score     int    COMMENT 'R 得分 1-4（越大越近）',
  f_score     int    COMMENT 'F 得分 1-4（越大越频繁）',
  m_score     int    COMMENT 'M 得分 1-4（越大越高价值）',
  segment     string COMMENT '价值分层：重要价值/重要保持/一般价值/流失预警'
)
STORED AS ORC;
