#!/usr/bin/env python3
"""Validate CSV, split partitions, render idempotent LOAD DATA statements."""
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
import re
import sys

source, target = map(Path, sys.argv[1:])
target.mkdir(parents=True, exist_ok=True)
groups, ids = {}, set()
with source.open(newline='') as f:
    for row in csv.DictReader(f):
        oid = int(row['order_id'])
        if oid in ids:
            raise ValueError('Duplicate order_id')
        ids.add(oid)
        dt = date.fromisoformat(row['dt']).isoformat()
        country = row['country']
        if not re.fullmatch('[A-Z]{2}', country):
            raise ValueError('country must be two uppercase letters')
        product = row['product']
        if not re.fullmatch('[a-zA-Z0-9_ -]+', product):
            raise ValueError('Unsupported product characters')
        amount = Decimal(row['amount'])
        if not amount.is_finite() or amount < 0 or amount > Decimal('99999999.99') or amount != amount.quantize(Decimal('0.01')):
            raise ValueError('Invalid DECIMAL(10,2) amount')
        groups.setdefault((dt, country), []).append([oid, product, f'{amount:.2f}'])
if not groups:
    raise ValueError('CSV contains no rows')
statements = []
for (dt, country), rows in sorted(groups.items()):
    name = f'{dt}_{country}.csv'
    with (target/name).open('w', newline='') as f:
        csv.writer(f, lineterminator='\n').writerows(rows)
    statements.append(f"LOAD DATA LOCAL INPATH '/tmp/hive-load/{name}' OVERWRITE INTO TABLE practical3.orders PARTITION (dt='{dt}', country='{country}');")
(target/'load.sql').write_text('\n'.join(statements)+'\n')
print(f'Prepared {len(ids)} rows in {len(groups)} partitions')
