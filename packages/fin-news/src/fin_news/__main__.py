"""独立采集进程入口（方案 A）: PM2 用 `python -m fin_news` 拉起。

要求 env FIN_NEWS_DB 指向数据库（生产: /opt/workbench/data/fin_news.db, 零拷贝切换）。
"""

import logging

from .collector import run_forever

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] %(levelname)s: %(message)s",
)

if __name__ == "__main__":
    run_forever()
