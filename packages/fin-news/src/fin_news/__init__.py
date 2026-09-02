"""fin-news: 财经新闻自采集与检索包（SPEC F4, 自 workbench lib/fin_news 迁入）。

数据库路径由环境变量 FIN_NEWS_DB 指定（迁代码不迁数据）; 未设置时显式报错。
采集器以独立进程运行（方案 A, `python -m fin_news`）; 查询 API 供各消费方 import。
"""

from .collector import COLLECT_INTERVAL, run_collect_once
from .query import count, get_recent, get_recent_diverse, search_announcements, search_news

__all__ = [
    "COLLECT_INTERVAL",
    "run_collect_once",
    "count",
    "get_recent",
    "get_recent_diverse",
    "search_announcements",
    "search_news",
]
