#!/usr/bin/env bash
set -euo pipefail
mkdir -p /tmp/hive-conf
cp /workspace/config/*.xml /tmp/hive-conf/
for file in /opt/hive/conf/*.properties /opt/hadoop/etc/hadoop/log4j.properties; do
  [[ ! -f "$file" ]] || cp -L "$file" /tmp/hive-conf/
done
export HIVE_CONF_DIR=/tmp/hive-conf HADOOP_CONF_DIR=/tmp/hive-conf
export HADOOP_CLASSPATH="${TEZ_HOME:-/opt/tez}/*:${TEZ_HOME:-/opt/tez}/lib/*:${HADOOP_CLASSPATH:-}"
if [[ "$SERVICE_NAME" == metastore ]]; then
  # PostgreSQL initOrUpgrade is safe on both a new and existing schema.
  /opt/hive/bin/schematool -dbType postgres -initOrUpgradeSchema
fi
exec /opt/hive/bin/hive --skiphadoopversion --skiphbasecp --service "$SERVICE_NAME"
