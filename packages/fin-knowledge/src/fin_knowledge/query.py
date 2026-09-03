"""向量检索: numpy 余弦, 支持 doc_type / stock_code 过滤。

返回块带文档锚（标题/类型/来源/章节）——消费侧数字审计要求"文档片段也算材料",
锚保证可溯源。
"""

import logging

import numpy as np

from .db import connect
from .embedder import EMBED_DIM, embed_query

logger = logging.getLogger("fin_knowledge")


def search_knowledge(
    query: str,
    doc_types: list[str] | None = None,
    stock_code: str | None = None,
    top_k: int = 8,
) -> list[dict]:
    """→ [{text, section, score, doc_title, doc_type, stock_code, source_url, published_at}]

    库为空/无命中返回 []; embedding 失败抛异常（调用方显式处理, 不静默降级）。
    """
    q = (query or "").strip()
    if not q:
        return []
    top_k = max(1, min(int(top_k or 8), 30))

    sql = (
        "SELECT c.text, c.section, c.emb, d.title, d.doc_type, d.stock_code, d.source_url, d.published_at"
        " FROM chunks c JOIN documents d ON c.doc_id = d.id WHERE c.emb IS NOT NULL"
    )
    params: list = []
    if doc_types:
        sql += f" AND d.doc_type IN ({','.join('?' * len(doc_types))})"
        params += list(doc_types)
    if stock_code:
        sql += " AND d.stock_code = ?"
        params.append(stock_code)

    conn = connect()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    if not rows:
        return []

    mat = np.frombuffer(b"".join(r["emb"] for r in rows), dtype=np.float32).reshape(len(rows), EMBED_DIM)
    qv = np.asarray(embed_query(q), dtype=np.float32)
    scores = mat @ qv / (np.linalg.norm(mat, axis=1) * np.linalg.norm(qv) + 1e-9)
    order = np.argsort(-scores)[:top_k]
    return [
        {
            "text": rows[i]["text"],
            "section": rows[i]["section"],
            "score": round(float(scores[i]), 4),
            "doc_title": rows[i]["title"],
            "doc_type": rows[i]["doc_type"],
            "stock_code": rows[i]["stock_code"],
            "source_url": rows[i]["source_url"],
            "published_at": rows[i]["published_at"],
        }
        for i in order
    ]


def knowledge_stats() -> dict:
    """库存量概览（运维与"数据边界"展示用）。"""
    conn = connect()
    try:
        docs = conn.execute(
            "SELECT doc_type, COUNT(*) n FROM documents GROUP BY doc_type"
        ).fetchall()
        chunks = conn.execute("SELECT COUNT(*) n FROM chunks").fetchone()["n"]
        return {"docs_by_type": {r["doc_type"]: r["n"] for r in docs}, "total_chunks": chunks}
    finally:
        conn.close()
