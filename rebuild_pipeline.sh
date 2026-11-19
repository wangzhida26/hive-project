#!/bin/bash
# 第 4 周部署验证：一键重建全链路（ODS→STG→DWD→DWS→ADS）
set -u
cd "$(dirname "$0")"
LOG=/tmp/rebuild.log
: > $LOG
B() { MSYS_NO_PATHCONV=1 docker exec hive-server beeline -u "jdbc:hive2://localhost:10000" -n hive --silent=true --showHeader=false --outputformat=tsv2 -f "$1" 2>&1; }

STEPS="sql/ods/create_ods.sql sql/ods/load_ods.sql sql/clean/clean_missing.sql sql/clean/clean_dup.sql sql/clean/clean_enum.sql sql/clean/clean_abnormal_format.sql sql/clean/clean_split_merge.sql sql/dwd/create_dwd.sql sql/dwd/load_dwd.sql sql/dws/create_dws.sql sql/dws/load_dws.sql sql/ads/create_ads.sql sql/ads/load_ads.sql"

for s in $STEPS; do
  name=$(basename $s)
  echo "[$(date +%H:%M:%S)] >>> $name" >> $LOG
  cp "$s" data/_rebuild.sql
  OUT=$(B /data/_rebuild.sql)
  if echo "$OUT" | grep -qE "FAILED:|Error while|SemanticException|RuntimeException|Error: "; then
    echo "FAILED: $name" >> $LOG
    echo "$OUT" | grep -iE "Error|FAILED" | head -5 >> $LOG
    echo "REBUILD_FAILED" >> $LOG
    exit 1
  fi
  echo "OK: $name" >> $LOG
done
echo "REBUILD_DONE" >> $LOG
