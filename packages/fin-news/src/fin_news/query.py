"""查询 API（SPEC F4 §4.2 / 姊妹规格 §6.2-C）。

- get_recent / get_recent_diverse / count_rows: 兼容 API, 与 workbench 旧实现同 SQL
  同返回形态（裸 list/int）, 供四个既有消费方零改动切换。
- search_news / search_announcements: 新封套 API（三态封套 + staleness_warning）。

staleness（§6.2-C）: 最后采集时间距今 > 2 个刷新周期（60 分钟）时,
封套 meta 必须携带 staleness_warning, 由产品侧决定是否告知用户。
"""

import time
from typing import Any

from finmcp_common.responses import EMPTY_CONFIRMED_ABSENT, ok_response

from .collector import COLLECT_INTERVAL
from .db import connect, count_rows, last_collected_at

_STALE_AFTER = 2 * COLLECT_INTERVAL  # 60 分钟


def get_recent(limit: int = 50, hours: int = 24) -> list[dict]:
    """读最近 N 小时的新闻，按 fetched_at 倒序。（兼容 API, 裸返回）"""
    since = int(time.time()) - hours * 3600
    conn = connect()
    rows = conn.execute(
        "SELECT source, title, content, url, published_at, fetched_at "
        "FROM news WHERE fetched_at >= ? ORDER BY fetched_at DESC LIMIT ?",
        (since, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_diverse(per_source: int = 12, hours: int = 24) -> list[dict]:
    """分源均匀采样：每个源取最新 per_source 条。（兼容 API, 裸返回）"""
    since = int(time.time()) - hours * 3600
    conn = connect()
    rows = conn.execute(
        "SELECT source, title, content, url, published_at, fetched_at FROM ("
        "  SELECT *, ROW_NUMBER() OVER (PARTITION BY source ORDER BY fetched_at DESC) AS rn"
        "  FROM news WHERE fetched_at >= ?"
        ") WHERE rn <= ? ORDER BY fetched_at DESC",
        (since, per_source),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# 旧名别名（workbench lib/fin_news 以 count 暴露; 实现在 db.count_rows）
count = count_rows


def _staleness_meta() -> dict[str, Any] | None:
    last = last_collected_at()
    now = int(time.time())
    if last is None or now - last > _STALE_AFTER:
        return {
            "last_collected_at": last,
            "minutes_ago": round((now - last) / 60) if last else None,
        }
    return None


def _with_staleness(resp: dict[str, Any]) -> dict[str, Any]:
    warn = _staleness_meta()
    if warn is not None:
        resp["meta"]["staleness_warning"] = warn
    return resp


def search_news(
    query: str,
    days: int = 7,
    sources: list[str] | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    """按关键词检索新闻（title/content LIKE）, 三态封套返回。

    items: [{id, source, title, content, url, published_at, fetched_at}]
    """
    q = (query or "").strip()
    days = max(1, min(int(days or 7), 365))
    limit = max(1, min(int(limit or 30), 200))
    since = int(time.time()) - days * 86400
    sql = "SELECT id, source, title, content, url, published_at, fetched_at FROM news WHERE fetched_at >= ?"
    params: list[Any] = [since]
    if q:
        sql += " AND (title LIKE ? OR content LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if sources:
        placeholders = ",".join("?" * len(sources))
        sql += f" AND source IN ({placeholders})"
        params += list(sources)
    sql += " ORDER BY fetched_at DESC LIMIT ?"
    params.append(limit)
    conn = connect()
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return _with_staleness(
        ok_response(
            data={"items": rows},
            source="local_db",
            empty_reason=None if rows else EMPTY_CONFIRMED_ABSENT,
        )
    )


def search_announcements(
    entity: str,
    keywords: str = "",
    days: int = 30,
    limit: int = 30,
) -> dict[str, Any]:
    """公告检索（限 source=巨潮资讯）, 供事件流一手来源候选。三态封套返回。"""
    e = (entity or "").strip()
    kw = (keywords or "").strip()
    days = max(1, min(int(days or 30), 365))
    limit = max(1, min(int(limit or 30), 200))
    since = int(time.time()) - days * 86400
    sql = (
        "SELECT id, source, title, content, url, published_at, fetched_at "
        "FROM news WHERE fetched_at >= ? AND source = '巨潮资讯'"
    )
    params: list[Any] = [since]
    if e:
        sql += " AND title LIKE ?"
        params.append(f"%{e}%")
    if kw:
        sql += " AND (title LIKE ? OR content LIKE ?)"
        params += [f"%{kw}%", f"%{kw}%"]
    sql += " ORDER BY fetched_at DESC LIMIT ?"
    params.append(limit)
    conn = connect()
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return _with_staleness(
        ok_response(
            data={"items": rows},
            source="local_db",
            empty_reason=None if rows else EMPTY_CONFIRMED_ABSENT,
        )
    )
