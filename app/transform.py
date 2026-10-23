"""YARN -> existing HDFS data -> Spark transformations -> partitioned SQL table."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
from pyspark.sql import SparkSession, functions as F, types as T

p = argparse.ArgumentParser()
p.add_argument('--input', default='hdfs://namenode:8020/user/hive/practical3/orders')
p.add_argument('--output', default='hdfs://namenode:8020/user/spark/practical4/daily_sales')
p.add_argument('--report', default='logs/spark-result.json')
args = p.parse_args()
spark = SparkSession.builder.appName('team-27-hw4-spark-yarn').getOrCreate()
spark.sparkContext.setLogLevel('WARN')
try:
    sc = spark.sparkContext
    assert sc.master == 'yarn', sc.master
    assert sc.applicationId.startswith('application_'), sc.applicationId
    assert args.input.startswith('hdfs://') and args.output.startswith('hdfs://')
    # This is the real table data loaded by homework 3, not a local replacement.
    # Partition columns are discovered from dt=.../country=... paths in HDFS.
    schema = T.StructType([
        T.StructField('order_id', T.IntegerType()),
        T.StructField('product', T.StringType()),
        T.StructField('amount', T.DecimalType(10, 2)),
    ])
    source = spark.read.schema(schema).option('basePath', args.input).csv(args.input)
    typed = (source.withColumn('dt', F.to_date('dt'))
             .withColumn('country', F.upper(F.trim('country')))
             .withColumn('product', F.lower(F.trim('product')))
             .withColumn('amount', F.col('amount').cast('decimal(10,2)')))
    valid = typed.filter(
        F.col('order_id').isNotNull() & F.col('product').isNotNull()
        & F.col('dt').isNotNull() & F.col('country').isin('RU', 'KZ')
        & (F.col('amount') > 0))
    metrics = typed.agg(F.count('*').alias('input_rows'),
                        F.sum('amount').alias('total_amount')).first()
    valid_rows = valid.count()
    assert metrics.input_rows == 8 and valid_rows == 8, (metrics, valid_rows)
    assert metrics.total_amount == Decimal('360.00'), metrics
    daily = (valid.groupBy('dt', 'country')
             .agg(F.count('*').alias('order_count'),
                  F.sum('amount').cast('decimal(18,2)').alias('gross_amount'),
                  F.avg('amount').cast('decimal(18,2)').alias('avg_amount'),
                  F.countDistinct('product').alias('product_count'))
             .withColumn('vat_amount', (F.col('gross_amount') * F.lit(Decimal('0.20'))).cast('decimal(18,2)')))
    # Spark creates a data source table and writes Hive-style partitioned Parquet.
    # Persistent shared metadata is registered via the real HiveServer2 in run.py.
    (daily.write.mode('overwrite').format('parquet')
     .option('path', args.output).partitionBy('dt', 'country').saveAsTable('daily_sales'))
    spark_rows = spark.sql('SELECT * FROM daily_sales ORDER BY dt,country').collect()
    expected = [
        ('2026-10-01','KZ',2,'70.00','35.00',2,'14.00'),
        ('2026-10-01','RU',2,'30.00','15.00',2,'6.00'),
        ('2026-10-02','KZ',2,'150.00','75.00',2,'30.00'),
        ('2026-10-02','RU',2,'110.00','55.00',2,'22.00'),
    ]
    actual = [(str(r.dt),r.country,r.order_count,str(r.gross_amount),str(r.avg_amount),r.product_count,str(r.vat_amount)) for r in spark_rows]
    assert actual == expected, actual
    physical = spark.read.parquet(args.output)
    assert physical.count() == 4
    partitions = [str(r[0]) for r in spark.sql('SHOW PARTITIONS daily_sales').collect()]
    assert len(partitions) == 4, partitions
    # Driver + at least one remote executor must exist; local mode cannot pass.
    executors = sc._jsc.sc().getExecutorMemoryStatus().toString()
    assert any(host in executors for host in ['172.18.','nodemanager']), executors
    report = {'application_id':sc.applicationId,'spark_version':spark.version,'master':sc.master,
              'deploy_mode':sc.getConf().get('spark.submit.deployMode'),
              'input':args.input,'output':args.output,'input_rows':metrics.input_rows,
              'valid_rows':valid_rows,'input_total':str(metrics.total_amount),
              'result_rows':actual,'partitions':partitions,'executor_memory_status':executors,
              'table_schema':spark.table('daily_sales').schema.simpleString()}
    Path(args.report).parent.mkdir(parents=True,exist_ok=True)
    Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('SPARK_RESULT '+json.dumps(report,ensure_ascii=False),flush=True)
finally:
    spark.stop()
