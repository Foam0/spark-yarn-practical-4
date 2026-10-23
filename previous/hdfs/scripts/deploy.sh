#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Запуск HDFS-кластера"
docker compose up -d --wait

echo "==> Ожидание регистрации трёх DataNode"
"$ROOT_DIR/scripts/verify.sh"

echo
echo "Кластер готов. Интерфейс NameNode: http://localhost:9870"

