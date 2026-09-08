"""文档入库: 哈希去重 → 分块 → 向量化 → 落库。增量更新的基本单元。"""

import hashlib
import logging
import time

import numpy as np

from .chunker import chunk_text
from .db import connect
from .embedder import embed_texts
from . import vec_index

logger = logging.getLogger("fin_knowledge")


def ingest_document(
    doc_type: str,
    title: str,
    text: str,
    stock_code: str | None = None,
    source_url: str | None = None,
    published_at: str | None = None,
) -> dict:
    """入库一篇文档。同内容(doc_hash)已存在则跳过（增量去重）。

    Returns: {status: ingested|duplicate|empty, doc_id, chunks}
    """
    body = (text or "").strip()
    if not body:
        return {"status": "empty", "doc_id": None, "chunks": 0}
    doc_hash = hashlib.sha256(f"{doc_type}|{title}|{body[:50000]}".encode()).hexdigest()

    conn = connect()
    try:
        row = conn.execute("SELECT id FROM documents WHERE doc_hash=?", (doc_hash,)).fetchone()
        if row:
            return {"status": "duplicate", "doc_id": row["id"], "chunks": 0}
        chunks = chunk_text(body)
        if not chunks:
            return {"status": "empty", "doc_id": None, "chunks": 0}
        embs = embed_texts([c["text"] for c in chunks])
        cur = conn.execute(
            "INSERT INTO documents(doc_hash, doc_type, title, stock_code, source_url, published_at, ingested_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (doc_hash, doc_type, title, stock_code, source_url, published_at, int(time.time())),
        )
        doc_id = cur.lastrowid
        chunk_ids = []
        for c, e in zip(chunks, embs, strict=False):
            cur2 = conn.execute(
                "INSERT INTO chunks(doc_id, seq, section, text, emb) VALUES(?,?,?,?,?)",
                (doc_id, c["seq"], c["section"], c["text"], np.asarray(e, dtype=np.float32).tobytes()),
            )
            chunk_ids.append(cur2.lastrowid)
        # P0-MEM-C: 新 chunk 同步写 vec0(生产扩展可用时), 保持 ANN 索引不落后。
        # 本机 macOS/扩展不可用则跳过(仅 chunks 表, 下次 backfill_vec 补齐)。
        if vec_index.load_vec(conn) and vec_index.has_vec_table(conn):
            try:
                scale = vec_index.get_scale(conn)
                conn.executemany(
                    "INSERT INTO chunk_vec(id,doc_type,emb) VALUES(?,?,vec_int8(?))",
                    [(chunk_ids[i], doc_type, vec_index.quantize(embs[i], scale))
                     for i in range(len(chunk_ids))],
                )
            except Exception as e:
                logger.warning("vec0 同步写失败(不阻断入库): %s", e)
        conn.commit()
        logger.info("入库 %s《%s》 %d 块", doc_type, title[:40], len(chunks))
        return {"status": "ingested", "doc_id": doc_id, "chunks": len(chunks)}
    finally:
        conn.close()
