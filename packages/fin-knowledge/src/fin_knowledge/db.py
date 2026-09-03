"""SQLite 知识库: 路径解析(env FIN_KNOWLEDGE_DB) + 建表。

路径策略沿用 fin-news 教训: 只认环境变量, 未设置显式报错, 不猜默认路径。
向量存储: chunks.emb 为 float32 BLOB(numpy 余弦检索); 万级 chunk 毫秒级,
sqlite-vec 索引推迟到规模需要时(本机 macOS 系统 python 不支持扩展加载)。
"""

import os
import sqlite3
from pathlib import Path

_initialized_paths: set[str] = set()


def db_path() -> str:
    path = os.getenv("FIN_KNOWLEDGE_DB", "").strip()
    if not path:
        raise RuntimeError(
            "FIN_KNOWLEDGE_DB 环境变量未设置: fin-knowledge 不猜数据库路径, "
            "请显式指定(如 /opt/workbench/data/knowledge.db)"
        )
    return path


def connect() -> sqlite3.Connection:
    path = db_path()
    if path not in _initialized_paths:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_hash TEXT NOT NULL UNIQUE,
                doc_type TEXT NOT NULL,
                title TEXT NOT NULL,
                stock_code TEXT,
                source_url TEXT,
                published_at TEXT,
                ingested_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL REFERENCES documents(id),
                seq INTEGER NOT NULL,
                section TEXT,
                text TEXT NOT NULL,
                emb BLOB
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_stock ON documents(stock_code, doc_type)")
        conn.commit()
        conn.close()
        _initialized_paths.add(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
