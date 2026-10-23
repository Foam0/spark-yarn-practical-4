#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

EXPECTED_DATANODES=3
ATTEMPTS=60
REPORT=""

echo "==> Проверка процессов контейнеров"
for service in namenode secondarynamenode datanode1 datanode2 datanode3; do
  container_id="$(docker compose ps -q "$service")"
  if [[ -z "$container_id" ]] || [[ "$(docker inspect -f '{{.State.Running}}' "$container_id")" != "true" ]]; then
    echo "ОШИБКА: сервис $service не запущен" >&2
    docker compose ps >&2
    exit 1
  fi
done

echo "==> Проверка регистрации DataNode в NameNode"
for ((attempt = 1; attempt <= ATTEMPTS; attempt++)); do
  REPORT="$(docker compose exec -T namenode hdfs dfsadmin -report 2>/dev/null || true)"
  if grep -q "Live datanodes (${EXPECTED_DATANODES}):" <<<"$REPORT"; then
    break
  fi

  if (( attempt == ATTEMPTS )); then
    echo "ОШИБКА: за ${ATTEMPTS} попыток не зарегистрировались три живых DataNode" >&2
    printf '%s\n' "$REPORT" >&2
    exit 1
  fi
  sleep 2
done

if grep -Eq "Dead datanodes \([1-9][0-9]*\):" <<<"$REPORT"; then
  echo "ОШИБКА: NameNode сообщает о мёртвых DataNode" >&2
  printf '%s\n' "$REPORT" >&2
  exit 1
fi

echo "==> Проверка SecondaryNameNode"
if ! docker compose exec -T secondarynamenode ps -eo args | grep -q '[S]econdaryNameNode'; then
  echo "ОШИБКА: процесс SecondaryNameNode не найден" >&2
  exit 1
fi

echo "==> Запись и чтение тестового файла с репликацией 3"
docker compose exec -T namenode bash -c '
  set -e
  printf "hdfs-cluster-ok\n" > /tmp/hdfs-healthcheck.txt
  hdfs dfs -mkdir -p /healthcheck
  hdfs dfs -put -f /tmp/hdfs-healthcheck.txt /healthcheck/hdfs-healthcheck.txt
  test "$(hdfs dfs -cat /healthcheck/hdfs-healthcheck.txt)" = "hdfs-cluster-ok"
  hdfs dfs -setrep -w 3 /healthcheck/hdfs-healthcheck.txt >/dev/null
'

FSCK="$(docker compose exec -T namenode hdfs fsck /healthcheck/hdfs-healthcheck.txt -files -blocks -locations 2>&1)"
if ! grep -q "Status: HEALTHY" <<<"$FSCK"; then
  echo "ОШИБКА: HDFS fsck не подтвердил целостность тестового файла" >&2
  printf '%s\n' "$FSCK" >&2
  exit 1
fi

echo
echo "Проверка пройдена:"
grep -E "Live datanodes|Dead datanodes" <<<"$REPORT"
if ! grep -q "Dead datanodes" <<<"$REPORT"; then
  echo "Dead datanodes (0):"
fi
grep -E "Status:|Number of data-nodes:" <<<"$FSCK" || true
echo "SecondaryNameNode: RUNNING"
