#!/usr/bin/env python3
"""Run Spark on YARN, register its output in Hive, verify via standard Beeline."""
from decimal import Decimal
import json
from pathlib import Path
import shlex
import time
from remote_lib import remote

ROOT=Path(__file__).resolve().parents[1]
LOG=ROOT/'logs';LOG.mkdir(exist_ok=True)
start=time.time()
print('Starting Spark on existing YARN; waiting for driver and executors',flush=True)
output=remote('team-27-01','cd /opt/spark-yarn-practical-4 && scripts/run-spark.sh >logs/spark-submit.log 2>&1 && cat logs/spark-result.json')
result=json.loads(output)
(LOG/'spark-result.json').write_bytes(output)
print('Spark completed:',result['application_id'],flush=True)
sql=(ROOT/'sql/register.sql').read_text()
beeline='cd /opt/hive-cluster-practical-3 && sudo scripts/beeline.sh -e '
registered=remote('team-27-00',beeline+shlex.quote(sql))
(LOG/'hive-register.log').write_bytes(registered)

def query(sql,label):
    data=remote('team-27-00',beeline+shlex.quote(sql)).decode()
    (LOG/f'hive-{label}.tsv').write_text(data)
    return [line.strip() for line in data.splitlines() if line.strip()]

parts=query('SHOW PARTITIONS practical4.daily_sales;','partitions')
expected_parts=sorted(f'dt={dt}/country={country}' for dt in ['2026-10-01','2026-10-02'] for country in ['KZ','RU'])
assert sorted(parts)==expected_parts,parts
rows=query('SELECT dt,country,order_count,gross_amount,avg_amount,product_count,vat_amount FROM practical4.daily_sales;','rows')
expected={
 ('2026-10-01','KZ','2',Decimal('70'),Decimal('35'),'2',Decimal('14')),
 ('2026-10-01','RU','2',Decimal('30'),Decimal('15'),'2',Decimal('6')),
 ('2026-10-02','KZ','2',Decimal('150'),Decimal('75'),'2',Decimal('30')),
 ('2026-10-02','RU','2',Decimal('110'),Decimal('55'),'2',Decimal('22'))}
normalized={tuple(Decimal(v) if i in [3,4,6] else v for i,v in enumerate(line.split('\t'))) for line in rows}
assert normalized==expected,(rows,expected)
filtered=query("SELECT order_count,gross_amount FROM practical4.daily_sales WHERE dt='2026-10-02' AND country='RU';",'filter')
assert len(filtered)==1 and filtered[0].split('\t')[0]=='2' and Decimal(filtered[0].split('\t')[1])==Decimal('110'),filtered
query('DESCRIBE FORMATTED practical4.daily_sales;','describe')
aid=result['application_id']
app=json.loads(remote('team-27-nn',f'curl -fsS http://localhost:8088/ws/v1/cluster/apps/{aid}'))['app']
assert app['applicationType']=='SPARK' and app['state']=='FINISHED' and app['finalStatus']=='SUCCEEDED',app
(LOG/'yarn-application.json').write_text(json.dumps(app,ensure_ascii=False,indent=2))
fsck=remote('team-27-nn','sudo docker exec hdfs-lab-namenode-1 hdfs fsck /user/spark/practical4/daily_sales').decode()
(LOG/'hdfs-fsck.log').write_text(fsck)
assert "is HEALTHY" in fsck,fsck
listing=remote('team-27-nn','sudo docker exec hdfs-lab-namenode-1 hdfs dfs -ls -R /user/spark/practical4/daily_sales').decode()
(LOG/'hdfs-files.log').write_text(listing)
submit=remote('team-27-01','cat /opt/spark-yarn-practical-4/logs/spark-submit.log')
(LOG/'spark-submit.log').write_bytes(submit)
summary={'status':'PASS','application_id':aid,'yarn_state':app['state'],'yarn_final_status':app['finalStatus'],
         'input_rows':8,'hive_rows':4,'partitions':parts,'gross_total':'360.00','vat_total':'72.00',
         'hive_client':'Beeline via existing HiveServer2 4.0.0','hdfs':'HEALTHY','elapsed_seconds':round(time.time()-start,1)}
(LOG/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
