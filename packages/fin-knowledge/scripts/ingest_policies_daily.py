"""政策原文每日增量入库(数据层 2.0 批次二)。cron: 工作日 18:10。哈希去重, 已入库秒过。"""

import os

with open("/opt/workbench/.env") as _f:
    for line in _f:
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
os.environ["FIN_KNOWLEDGE_DB"] = "/opt/workbench/data/knowledge.db"

from fin_knowledge.collectors.policy import ingest_latest_policies  # noqa: E402  # env 注入必须先于 import(运行时配置)
from fin_knowledge.collectors.ministry_policy import ingest_latest_ministry_policies  # noqa: E402

print("gov:", ingest_latest_policies(limit=30), flush=True)
# T84 部委扩展: gov.cn 政策文件库·部门文件(工信部/发改委/央行/证监会/财政部等)。
# URL 预查去重, 增量日常仅新发文产生下载; 40 条 > 部委日均发文量, 无漏采。
print("ministry:", ingest_latest_ministry_policies(limit=40), flush=True)
