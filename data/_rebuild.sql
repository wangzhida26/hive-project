-- ============ 第5周 数据一致性核对（逐层实跑） ============
-- 1. ODS 六表行数
select 'ODS' layer, 'ods_order' tbl, count(*) rows_cnt from ydsh_ods.ods_order
union all select 'ODS','ods_order_item',count(*) from ydsh_ods.ods_order_item
union all select 'ODS','ods_user',count(*) from ydsh_ods.ods_user
union all select 'ODS','ods_product',count(*) from ydsh_ods.ods_product
union all select 'ODS','ods_store',count(*) from ydsh_ods.ods_store
union all select 'ODS','ods_user_behavior',count(*) from ydsh_ods.ods_user_behavior;

-- 2. DWD 事实与维表
select 'DWD' layer, 'dwd_order' tbl, count(*) rows_cnt from ydsh_dwd.dwd_order
union all select 'DWD','dwd_order_item',count(*) from ydsh_dwd.dwd_order_item
union all select 'DWD','dim_user',count(*) from ydsh_dwd.dim_user
union all select 'DWD','dim_product',count(*) from ydsh_dwd.dim_product
union all select 'DWD','dim_store',count(*) from ydsh_dwd.dim_store
union all select 'DWD','dim_date',count(*) from ydsh_dwd.dim_date;

-- 3. DWD 直接聚合（有效口径）
select 'DWD_AGGR' layer, 'valid_orders_gmv' tbl,
       concat('orders=',cast(count(*) as string),';gmv=',cast(round(sum(pay_amount),2) as string),';aov=',cast(round(sum(pay_amount)/count(*),2) as string),';users=',cast(count(distinct user_id) as string)) rows_cnt
from ydsh_dwd.dwd_order where order_status in ('已支付','已完成');

-- 4. DWS 汇总对账（日汇总合计应等于 DWD 有效口径）
select 'DWS' layer, 'dws_order_1d_total' tbl,
       concat('days=',cast(count(*) as string),';gmv=',cast(round(sum(gmv),2) as string),';orders=',cast(sum(orders) as string)) rows_cnt
from ydsh_dws.dws_order_1d;

-- 5. ADS 大盘指标
select 'ADS' layer, 'ads_kpi_overview' tbl,
       concat('gmv=',cast(round(gmv,2) as string),';orders=',cast(orders as string),';aov=',cast(round(aov,2) as string),';active_users=',cast(active_users as string),';repurchase=',cast(round(repurchase_rate,4) as string),';refund_rate=',cast(round(refund_rate,4) as string),';top_cat=',category_top,';top_store=',store_top) rows_cnt
from ydsh_ads.ads_kpi_overview;

-- 6. 分区数核对
select 'DWD_PARTS' layer, 'dwd_order_partitions' tbl, cast(count(distinct order_dt) as string) rows_cnt from ydsh_dwd.dwd_order;
