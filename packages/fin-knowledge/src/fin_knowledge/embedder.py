"""百炼 text-embedding-v4 客户端（2026-09-03 Donnie 定案）。

官方限制: 单请求≤10 条, 单条≤8192 token, 单批合计≤33000 token。
纯 urllib + ProxyHandler({}) —— 国内 API 必须绕过进程代理（部署铁律）。
"""

import json
import logging
import os
import urllib.request

logger = logging.getLogger("fin_knowledge")

EMBED_MODEL = "text-embedding-v4"
EMBED_DIM = 1024
_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
_BATCH_LIMIT = 10

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _api_key() -> str:
    key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DASHSCOPE_API_KEY 未设置, embedding 不可用")
    return key


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化。>10 条自动分批; 失败抛异常(调用方决定重试/降级, 不静默)。"""
    if not texts:
        return []
    out: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_LIMIT):
        batch = [t[:8000] for t in texts[i : i + _BATCH_LIMIT]]
        payload = {
            "model": EMBED_MODEL,
            "input": {"texts": batch},
            "parameters": {"dimension": EMBED_DIM},
        }
        req = urllib.request.Request(
            _API_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
            },
        )
        with _opener.open(req, timeout=60) as resp:
            body = json.loads(resp.read())
        embs = body.get("output", {}).get("embeddings")
        if not embs or len(embs) != len(batch):
            raise RuntimeError(f"embedding 返回异常: {str(body)[:200]}")
        out.extend([e["embedding"] for e in sorted(embs, key=lambda x: x["text_index"])])
    return out


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
