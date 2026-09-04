# -*- coding: utf-8 -*-
"""政策原文每日增量入库(数据层 2.0 批次二)。cron: 工作日 18:10。哈希去重, 已入库秒过。"""
import os
for line in open("/opt/workbench/.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
os.environ["FIN_KNOWLEDGE_DB"] = "/opt/workbench/data/knowledge.db"
from fin_knowledge.collectors.policy import ingest_latest_policies
print(ingest_latest_policies(limit=30), flush=True)
