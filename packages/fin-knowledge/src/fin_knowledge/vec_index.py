"""sqlite-vec int8 向量索引: 快路径(生产 Linux, ~38ms 分片) + 兜底(macOS/扩展不可用 → 流式暴力扫)。

背景: 2026-09-08 OOM 事故——全表 load float32 embedding 单查询 6G 致 4G 机僵死。
方案(spike 实证): int8 量化(召回中位100%)+ vec0 虚拟表(doc_type partition key)+ 分片过滤。
约束: 本机 macOS 系统 python 不支持 load_extension → 快路径仅生产可用, 本地自动兜底。
"""

import json
import sqlite3

EMBED_DIM = 1024
# 量化 scale: 全局固定, 存/查必须一致。text-embedding-v4 L2 归一, 分量幅度小。
# 由 backfill 从全量实测 max-abs 求得后写入 vec_meta; 缺省用 spike 实测值兜底。
_DEFAULT_SCALE = 420.0


def load_vec(conn: sqlite3.Connection) -> bool:
    """尝试加载 sqlite-vec 扩展。成功 True(生产), 失败 False(本地 macOS/未装)→调用方走兜底。"""
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return True
    except Exception:
        return False


def get_scale(conn: sqlite3.Connection) -> float:
    try:
        row = conn.execute("SELECT value FROM vec_meta WHERE key='scale'").fetchone()
        return float(row[0]) if row else _DEFAULT_SCALE
    except Exception:
        return _DEFAULT_SCALE


def quantize(vec, scale: float):
    """float32 向量 → int8 JSON(vec_int8 入参)。numpy 或 list 均可。"""
    import numpy as np
    a = np.asarray(vec, dtype=np.float32)
    q = np.clip(np.round(a * scale), -127, 127).astype("int8")
    return json.dumps(q.tolist())


def has_vec_table(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1 FROM chunk_vec LIMIT 1")
        return True
    except Exception:
        return False
