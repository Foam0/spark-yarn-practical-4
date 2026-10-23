CREATE DATABASE IF NOT EXISTS practical4;
CREATE EXTERNAL TABLE IF NOT EXISTS practical4.daily_sales (
  order_count BIGINT,
  gross_amount DECIMAL(18,2),
  avg_amount DECIMAL(18,2),
  product_count BIGINT,
  vat_amount DECIMAL(18,2)
)
PARTITIONED BY (dt DATE, country STRING)
STORED AS PARQUET
LOCATION 'hdfs://namenode:8020/user/spark/practical4/daily_sales';
MSCK REPAIR TABLE practical4.daily_sales SYNC PARTITIONS;
