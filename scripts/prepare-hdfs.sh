#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export HADOOP_CONF_DIR="$PWD/config" HADOOP_USER_NAME=spark
mkdir -p logs
spark_home=$(.venv/bin/python -c 'import pathlib,pyspark;print(pathlib.Path(pyspark.__file__).parent)')
hdfs_cmd=("$JAVA_HOME/bin/java" -Xmx128m -cp "$spark_home/jars/*:$HADOOP_CONF_DIR" org.apache.hadoop.fs.FsShell)
"${hdfs_cmd[@]}" -test -d /user/hive/practical3/orders
"${hdfs_cmd[@]}" -mkdir -p /user/spark/practical4/events /user/spark/practical4/runtime /user/spark/practical4/staging
archive=/user/spark/practical4/runtime/spark-3.5.7-jars.zip
if ! "${hdfs_cmd[@]}" -test -e "$archive"; then
  .venv/bin/python - "$spark_home" <<'PY'
from pathlib import Path
import sys,zipfile
with zipfile.ZipFile('logs/spark-jars.zip','w',compression=zipfile.ZIP_STORED) as z:
    for p in sorted((Path(sys.argv[1])/'jars').glob('*.jar')):z.write(p,p.name)
PY
  "${hdfs_cmd[@]}" -put logs/spark-jars.zip "$archive"
fi
echo 'Existing HDFS input confirmed; Spark runtime archive and event directory ready'
