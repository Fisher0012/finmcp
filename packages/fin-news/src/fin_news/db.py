"""SQLite 库访问: 路径解析(env FIN_NEWS_DB) + 建表 + 写入。

路径策略（SPEC F4 §4.2）: 只认 FIN_NEWS_DB 环境变量, 未设置显式报错——
不猜默认路径, 避免静默写错库（消费方/进程各自负责设置, workbench 薄代理会设默认）。
"""

import hashlib
import logging
import os
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger("fin_news")

_initialized_paths: set[str] = set()


def db_path() -> str:
    path = os.getenv("FIN_NEWS_DB", "").strip()
    if not path:
        raise RuntimeError(
            "FIN_NEWS_DB 环境变量未设置: fin-news 不猜数据库路径, 请显式指定(如 /opt/workbench/data/fin_news.db)"
        )
    return path


def connect() -> sqlite3.Connection:
    path = db_path()
    if path not in _initialized_paths:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                url TEXT,
                published_at TEXT,
                fetched_at INTEGER NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fetched_at ON news(fetched_at DESC)")
        conn.commit()
        conn.close()
        _initialized_paths.add(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def make_id(source: str, title: str, url: str) -> str:
    """优先用 URL 去重，URL 不稳就用标题 hash。（与旧实现逐字节一致, 保 id 兼容）"""
    key = (url or "") + "|" + source + "|" + title[:80]
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def save(items: list[dict]) -> int:
    """批量入库，返回新增条数（PRIMARY KEY 冲突的会被 IGNORE）。"""
    if not items:
        return 0
    now = int(time.time())
    conn = connect()
    cur = conn.cursor()
    inserted = 0
    for it in items:
        nid = make_id(it["source"], it["title"], it.get("url", ""))
        try:
            cur.execute(
                "INSERT OR IGNORE INTO news (id, source, title, content, url, published_at, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    nid,
                    it["source"],
                    it["title"],
                    it.get("content", ""),
                    it.get("url", ""),
                    it.get("published_at", ""),
                    now,
                ),
            )
            if cur.rowcount:
                inserted += 1
        except Exception as e:
            logger.warning("入库失败: %s | %s", e, it.get("title", "")[:30])
    conn.commit()
    conn.close()
    return inserted


def count_rows() -> int:
    """全库条数。"""
    conn = connect()
    try:
        return int(conn.execute("SELECT COUNT(*) FROM news").fetchone()[0])
    finally:
        conn.close()


def last_collected_at() -> int | None:
    """最后一次成功入库时间（staleness 判定用）。"""
    conn = connect()
    try:
        row = conn.execute("SELECT MAX(fetched_at) FROM news").fetchone()
        return int(row[0]) if row and row[0] else None
    finally:
        conn.close()
