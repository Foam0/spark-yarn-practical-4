#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T -e HADOOP_CLIENT_OPTS='-Xmx192m -Duser.home=/tmp' hiveserver2 /opt/hive/bin/beeline \
  -u jdbc:hive2://10.27.0.12:10000/default -n "${HIVE_CLIENT_USER:-student}" \
  --silent=true --showHeader=false --outputformat=tsv2 --force=false "$@"
