#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p results
for service in resourcemanager nodemanager1 nodemanager2 historyserver; do
  id="$(docker compose ps -q "$service")"
  test -n "$id"
  test "$(docker inspect -f '{{.State.Running}}' "$id")" = true
done
for attempt in $(seq 1 60); do
  curl -fsS http://127.0.0.1:8088/ws/v1/cluster/nodes > results/nodes.json
  if python3 -c 'import json; n=json.load(open("results/nodes.json"))["nodes"]["node"]; assert len(n)==2 and all(x["state"]=="RUNNING" and not x["healthReport"] for x in n)' 2>/dev/null; then break; fi
  if (( attempt == 60 )); then echo 'NodeManager не зарегистрировались.' >&2; exit 1; fi
  sleep 2
done
echo 'NodeManager: 2 RUNNING, healthy'
run="$(date -u +%Y%m%dT%H%M%S)-$$"
test_dir="/homework2/wordcount-$run"
docker compose exec -T resourcemanager bash -ec '
  printf "hadoop yarn yarn\nhdfs\n" > /tmp/hw2-input.txt
  hdfs dfs -mkdir -p "$1/input"
  hdfs dfs -put /tmp/hw2-input.txt "$1/input/text.txt"
' bash "$test_dir"
timeout 240 docker compose exec -T resourcemanager hadoop jar \
  /opt/hadoop/share/hadoop/mapreduce/hadoop-mapreduce-examples-3.4.1.jar \
  wordcount "$test_dir/input" "$test_dir/output" 2>&1 | tee results/wordcount.log
docker compose exec -T resourcemanager hdfs dfs -cat "$test_dir/output/part-r-00000" > results/wordcount.txt
printf 'hadoop\t1\nhdfs\t1\nyarn\t2\n' | diff -u - results/wordcount.txt
app_id="$(grep -oE 'application_[0-9]+_[0-9]+' results/wordcount.log | head -n 1)"
test -n "$app_id"
curl -fsS "http://127.0.0.1:8088/ws/v1/cluster/apps/$app_id" > results/application.json
python3 -c 'import json; a=json.load(open("results/application.json"))["app"]; assert a["state"]=="FINISHED" and a["finalStatus"]=="SUCCEEDED"; print("YARN:",a["id"],a["state"],a["finalStatus"])'
job_id="${app_id/application_/job_}"
for attempt in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:19888/ws/v1/history/mapreduce/jobs/$job_id" > results/history.json 2>/dev/null; then break; fi
  if (( attempt == 30 )); then echo 'Задание не появилось в JobHistoryServer.' >&2; exit 1; fi
  sleep 2
done
python3 -c 'import json; j=json.load(open("results/history.json"))["job"]; assert j["state"]=="SUCCEEDED"; print("JobHistory:",j["id"],j["state"])'
docker compose exec -T resourcemanager hdfs fsck "$test_dir" -files -blocks -locations > results/fsck.txt 2>&1
grep -q 'Status: HEALTHY' results/fsck.txt
echo 'HDFS: HEALTHY; WordCount: правильный результат; история задания сохранена.'
echo "Данные проверки: $test_dir; локальные отчёты: results/"
