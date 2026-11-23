#!/bin/bash
# 第 4 周部署验证：一键重建全链路（ODS→STG→DWD→DWS→ADS）
set -u
cd "$(dirname "$0")"
LOG=/tmp/rebuild.log
: > $LOG
B() { MSYS_NO_PATHCONV=1 docker exec hive-server beeline -u "jdbc:hive2://localhost:10000" -n hive --silent=true --showHeader=false --outputformat=tsv2 -f "$1" 2>&1; }

STEPS="sql/ods/create_ods.sql sql/ods/load_ods.sql sql/clean/clean_missing.sql sql/clean/clean_dup.sql sql/clean/clean_enum.sql sql/clean/clean_abnormal_format.sql sql/clean/clean_split_merge.sql sql/dwd/create_dwd.sql sql/dwd/load_dwd.sql sql/dws/create_dws.sql sql/dws/load_dws.sql sql/ads/create_ads.sql sql/ads/load_ads.sql"

# --- 第5周联调修复：使脚本可重复执行 ---
# 根因：ODS 六表为外部表，DROP DATABASE CASCADE 不删除数据文件，而 LOAD DATA 为追加语义，
#      重复重建会把 CSV 再追加一份导致行数翻倍（实测 ods_order 15600 → 31200）。
# 对策：重建前先清空四库元数据，并物理删除 warehouse 中残留的库目录。
echo "[reset] drop databases & purge warehouse dirs" >> $LOG
printf "drop database if exists ydsh_ods cascade;\ndrop database if exists ydsh_dwd cascade;\ndrop database if exists ydsh_dws cascade;\ndrop database if exists ydsh_ads cascade;\n" > data/_reset.sql
cp data/_reset.sql data/_rebuild.sql
OUT=$(B /data/_reset.sql)
if echo "$OUT" | grep -qE "FAILED:|Error while|SemanticException|RuntimeException|Error: "; then
  echo "FAILED: reset" >> $LOG; echo "REBUILD_FAILED" >> $LOG; exit 1
fi
MSYS_NO_PATHCONV=1 docker exec hive-server bash -c \
  "rm -rf /opt/hive/data/warehouse/ydsh_ods.db /opt/hive/data/warehouse/ydsh_dwd.db /opt/hive/data/warehouse/ydsh_dws.db /opt/hive/data/warehouse/ydsh_ads.db"
echo "OK: reset" >> $LOG

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
