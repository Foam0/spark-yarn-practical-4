#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export HADOOP_CONF_DIR="$PWD/config" YARN_CONF_DIR="$PWD/config"
export SPARK_CONF_DIR="$PWD/config" HADOOP_USER_NAME=spark
export PYSPARK_PYTHON="$PWD/.venv/bin/python"
mkdir -p logs
exec .venv/bin/spark-submit --master yarn --deploy-mode client \
  --properties-file config/spark-defaults.conf --driver-memory 768m \
  app/transform.py "$@"
