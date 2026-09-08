"""向量检索: numpy 余弦, 支持 doc_type / stock_code 过滤。

返回块带文档锚（标题/类型/来源/章节）——消费侧数字审计要求"文档片段也算材料",
锚保证可溯源。
"""

import logging

import numpy as np

from .db import connect
from .embedder import EMBED_DIM, embed_query
from . import vec_index

logger = logging.getLogger("fin_knowledge")


def _search_vec_fast(q, doc_types, stock_code, top_k):
    """sqlite-vec int8 快路径。扩展不可用/无 chunk_vec 表 → 返回 None(调用方走流式兜底)。

    返回格式与流式路径逐字一致(text/section/score/doc_title/...)。
    分片过滤: doc_type 是 partition key(前过滤, spike 实证 2.6s→38ms); stock_code 走
    metadata 后过滤(放大 k 再截断, 保证召回)。
    """
    conn = connect()
    try:
        if not vec_index.load_vec(conn) or not vec_index.has_vec_table(conn):
            return None
        scale = vec_index.get_scale(conn)
        qv8 = vec_index.quantize(embed_query(q), scale)
        # stock_code 后过滤会削减命中, 放大候选 k
        kk = top_k * (8 if stock_code else 1)
        sql = "SELECT v.id FROM chunk_vec v WHERE v.emb MATCH vec_int8(?) AND k = ?"
        params: list = [qv8, kk]
        if doc_types:
            sql += f" AND v.doc_type IN ({','.join('?' * len(doc_types))})"
            params += list(doc_types)
        ids = [r[0] for r in conn.execute(sql, params).fetchall()]
        if not ids:
            return []
        # 用 chunk id 回捞完整锚(文本/标题/来源), 保持与流式路径同格式
        ph = ",".join("?" * len(ids))
        rows = conn.execute(
            "SELECT c.id, c.text, c.section, d.title, d.doc_type, d.stock_code,"
            " d.source_url, d.published_at"
            f" FROM chunks c JOIN documents d ON c.doc_id=d.id WHERE c.id IN ({ph})",
            ids,
        ).fetchall()
        by_id = {r["id"]: r for r in rows}
        out = []
        for cid in ids:  # 保持 KNN 距离序
            r = by_id.get(cid)
            if not r:
                continue
            if stock_code and r["stock_code"] != stock_code:
                continue
            out.append({
                "text": r["text"], "section": r["section"], "score": None,
                "doc_title": r["title"], "doc_type": r["doc_type"],
                "stock_code": r["stock_code"], "source_url": r["source_url"],
                "published_at": r["published_at"],
            })
            if len(out) >= top_k:
                break
        return out
    except Exception as e:
        logger.warning("vec 快路径失败, 回退流式: %s", e)
        return None
    finally:
        conn.close()


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

    # P0-MEM-C(2026-09-08): 优先走 sqlite-vec int8 快路径(生产 ~38ms 分片); 扩展不可用
    # (本机 macOS/未装)自动回退下方流式兜底。spike 实证: int8 召回中位100%, 内存1.3G。
    fast = _search_vec_fast(q, doc_types, stock_code, top_k)
    if fast is not None:
        return fast

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
