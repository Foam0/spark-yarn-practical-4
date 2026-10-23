#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
python3 scripts/prepare-data.py "${1:-data/orders.csv}" "$work"
docker compose exec -T hiveserver2 mkdir -p /tmp/hive-load
docker compose cp "$work/." hiveserver2:/tmp/hive-load/
scripts/beeline.sh -f /workspace/sql/create-table.sql
scripts/beeline.sh -f /tmp/hive-load/load.sql
echo 'Loaded partitions (OVERWRITE keeps a repeated load free of duplicates)'
