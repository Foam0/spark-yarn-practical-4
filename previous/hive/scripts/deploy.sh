#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/configure.py
mkdir -p drivers logs
if [[ ! -s drivers/postgresql.jar ]]; then
  curl -fL --retry 3 https://repo.maven.apache.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar -o drivers/postgresql.jar
fi
docker compose up -d --force-recreate --wait --wait-timeout 300
for attempt in $(seq 1 30); do
  if scripts/beeline.sh -e 'SELECT 1;' >logs/readiness.log 2>&1; then
    scripts/load-data.sh
    exit 0
  fi
  sleep 3
done
cat logs/readiness.log >&2
exit 1
