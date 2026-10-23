#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose config -q
network="$(docker compose config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["networks"]["hdfs"]["name"])')"
docker network inspect "$network" >/dev/null
# Создание каталогов на существующей HDFS; форматирование и удаление данных не выполняются.
docker compose run --rm --no-deps resourcemanager bash -ec '
  hdfs dfs -mkdir -p /mr-history/tmp /mr-history/done /yarn-logs
  hdfs dfs -chmod 1777 /mr-history/tmp /yarn-logs
  hdfs dfs -chmod 755 /mr-history/done
'
docker compose up -d --wait --wait-timeout 180
./scripts/verify.sh
