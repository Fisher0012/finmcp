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

    # P0-MEM 止血(2026-09-08): 流式分批算余弦, 不再 fetchall 全表 load 进内存。
    # 根因=123万chunk无过滤查询单次load 5G+ embedding 矩阵致 4G 机器 OOM 僵死。
    # 改为 fetchmany 分批+running top-k: 内存恒定 ~BATCH×5KB(≈200MB), 全召回不丢能力。
    # (正解=磁盘型 ANN 索引 P0-MEM-B, 此为止血保服务器。)
    BATCH = 40000
    qv = np.asarray(embed_query(q), dtype=np.float32)
    qn = float(np.linalg.norm(qv)) + 1e-9
    best: list = []  # [(score, row_dict)] 保持 ≤ top_k
    conn = connect()
    try:
        cur = conn.execute(sql, params)
        while True:
            rows = cur.fetchmany(BATCH)
            if not rows:
                break
            mat = np.frombuffer(b"".join(r["emb"] for r in rows), dtype=np.float32).reshape(len(rows), EMBED_DIM)
            scores = mat @ qv / (np.linalg.norm(mat, axis=1) * qn + 1e-9)
            # 本批 top_k 候选并入全局 best, 只留 top_k, 及时释放 mat/scores
            k = min(top_k, len(rows))
            for i in np.argsort(-scores)[:k]:
                best.append((float(scores[i]), {
                    "text": rows[i]["text"],
                    "section": rows[i]["section"],
                    "score": round(float(scores[i]), 4),
                    "doc_title": rows[i]["title"],
                    "doc_type": rows[i]["doc_type"],
                    "stock_code": rows[i]["stock_code"],
                    "source_url": rows[i]["source_url"],
                    "published_at": rows[i]["published_at"],
                }))
            best.sort(key=lambda x: -x[0])
            del best[top_k:]
            del mat, scores
    finally:
        conn.close()
    return [d for _, d in best]


def knowledge_stats() -> dict:
    """库存量概览（运维与"数据边界"展示用）。"""
    conn = connect()
    try:
        docs = conn.execute("SELECT doc_type, COUNT(*) n FROM documents GROUP BY doc_type").fetchall()
        chunks = conn.execute("SELECT COUNT(*) n FROM chunks").fetchone()["n"]
        return {"docs_by_type": {r["doc_type"]: r["n"] for r in docs}, "total_chunks": chunks}
    finally:
        conn.close()
