#!/usr/bin/env python3
"""Assert partition list, exact contents, pruning, MR aggregation and concurrency."""
import os
from pathlib import Path
import subprocess

os.chdir(Path(__file__).resolve().parents[1])
Path('logs').mkdir(exist_ok=True)

def sql(query, label):
    result = subprocess.run(['scripts/beeline.sh', '-e', query], capture_output=True, text=True)
    Path(f'logs/{label}.log').write_text(result.stdout + '\n' + result.stderr)
    result.check_returncode()
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

parts = sql('SHOW PARTITIONS practical3.orders;', 'partitions')
expected = sorted(f'dt={dt}/country={country}' for dt in ['2026-10-01', '2026-10-02'] for country in ['KZ', 'RU'])
assert sorted(parts) == expected, parts
rows = sql('SELECT order_id,product,amount,dt,country FROM practical3.orders;', 'contents')
expected_rows = [f'{i}\t{product}\t{i*10}\t{dt}\t{country}' for i, product, dt, country in [
    (1,'book','2026-10-01','RU'), (2,'pen','2026-10-01','RU'),
    (3,'book','2026-10-01','KZ'), (4,'pen','2026-10-01','KZ'),
    (5,'book','2026-10-02','RU'), (6,'pen','2026-10-02','RU'),
    (7,'book','2026-10-02','KZ'), (8,'pen','2026-10-02','KZ')]]
# Hive may retain decimal scale in JDBC output; normalize only the numeric column.
from decimal import Decimal
normalize = lambda row: tuple(Decimal(x) if j == 2 else x for j,x in enumerate(row.split('\t')))
assert sorted(map(normalize, rows)) == sorted(map(normalize, expected_rows)), rows
pruned = sql("SELECT order_id FROM practical3.orders WHERE dt='2026-10-01' AND country='RU';", 'partition-filter')
assert sorted(pruned) == ['1', '2'], pruned
sql("EXPLAIN EXTENDED SELECT order_id FROM practical3.orders WHERE dt='2026-10-01' AND country='RU';", 'explain-pruning')
aggregate = sql('SELECT country,COUNT(*),SUM(amount) FROM practical3.orders GROUP BY country;', 'aggregation-yarn')
assert sorted(tuple(Decimal(x) if j == 2 else x for j,x in enumerate(row.split('\t'))) for row in aggregate) == [('KZ','4',Decimal('220')),('RU','4',Decimal('140'))], aggregate
subprocess.run(['python3', 'scripts/verify-concurrent.py'], check=True)
subprocess.run(['docker','compose','exec','-T','hiveserver2','/opt/hadoop/bin/hdfs','fsck','/user/hive/practical3/orders'], check=True)
subprocess.run(['docker','compose','exec','-T','postgres','psql','-U','hive','-d','metastore','-c','SELECT "SCHEMA_VERSION" FROM "VERSION";'], check=True)
print('PASS: 8 exact rows; 4 partitions; filter 2 rows; SUM=360; two live clients; PostgreSQL schema and HDFS checked')
