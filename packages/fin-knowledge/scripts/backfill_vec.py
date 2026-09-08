"""P0-MEM-C 一次性回填: chunks.emb float32 → int8 灌 chunk_vec(vec0)。

仅生产 Linux 运行(需 sqlite-vec 扩展)。建 vec_meta(全局 scale)+chunk_vec(vec0,
doc_type partition key, id=chunks.id)。幂等: 重跑先 drop 重建。
用法: FIN_KNOWLEDGE_DB=/opt/workbench/data/knowledge.db python3 scripts/backfill_vec.py
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from fin_knowledge.db import connect  # noqa: E402
from fin_knowledge import vec_index  # noqa: E402


def main():
    conn = connect()
    if not vec_index.load_vec(conn):
        print("sqlite-vec 扩展加载失败(本机不支持?), 回填仅限生产 Linux")
        return 1
    samp = conn.execute(
        "SELECT emb FROM chunks WHERE emb IS NOT NULL LIMIT 50000").fetchall()
    se = np.frombuffer(b"".join(r["emb"] for r in samp), dtype=np.float32).reshape(
        len(samp), vec_index.EMBED_DIM)
    scale = float(127.0 / np.abs(se).max())
    print("全局量化 scale = %.2f" % scale)
    conn.execute("CREATE TABLE IF NOT EXISTS vec_meta(key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR REPLACE INTO vec_meta(key,value) VALUES('scale',?)", (str(scale),))
    conn.execute("DROP TABLE IF EXISTS chunk_vec")
    conn.execute(
        "CREATE VIRTUAL TABLE chunk_vec USING vec0("
        "id integer primary key, doc_type text partition key, emb int8[1024])")
    conn.commit()
    t0 = time.time()
    total = 0
    cur = conn.execute(
        "SELECT c.id, c.emb, d.doc_type FROM chunks c JOIN documents d ON c.doc_id=d.id"
        " WHERE c.emb IS NOT NULL")
    while True:
        batch = cur.fetchmany(20000)
        if not batch:
            break
        e = np.frombuffer(b"".join(r["emb"] for r in batch), dtype=np.float32).reshape(
            len(batch), vec_index.EMBED_DIM)
        q8 = np.clip(np.round(e * scale), -127, 127).astype(np.int8)
        conn.executemany(
            "INSERT INTO chunk_vec(id,doc_type,emb) VALUES(?,?,vec_int8(?))",
            [(batch[i]["id"], batch[i]["doc_type"], json.dumps(q8[i].tolist()))
             for i in range(len(batch))])
        total += len(batch)
        if total % 200000 == 0:
            print("  已灌 %d, %.0fs" % (total, time.time() - t0))
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM chunk_vec").fetchone()[0]
    print("回填完成: chunk_vec %d 条, %.0fs" % (n, time.time() - t0))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
