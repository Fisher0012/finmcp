#!/bin/bash
# 年报补漏循环: 重跑直到一轮零新增(自动收敛), 轮间隔 20 分钟避限速
cd /opt/workbench
for round in 1 2 3 4 5 6; do
  before=$(python3 -c "import sqlite3; print(sqlite3.connect('/opt/workbench/data/knowledge.db').execute('SELECT COUNT(*) FROM documents WHERE doc_type=\"annual_report\"').fetchone()[0])")
  python3 /opt/fin-knowledge/scripts/ingest_hs300.py 000905.SH >> logs/ingest_csi500_retry.log 2>&1
  after=$(python3 -c "import sqlite3; print(sqlite3.connect('/opt/workbench/data/knowledge.db').execute('SELECT COUNT(*) FROM documents WHERE doc_type=\"annual_report\"').fetchone()[0])")
  echo "[round $round] $before -> $after ($(date +%H:%M))" >> logs/retry_rounds.log
  if [ "$after" -eq "$before" ]; then echo "[收敛] 零新增, 停止" >> logs/retry_rounds.log; break; fi
  sleep 1200
done
