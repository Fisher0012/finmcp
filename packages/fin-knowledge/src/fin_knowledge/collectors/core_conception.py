"""产业链/题材按需采集: 东财 F10 核心题材 → 结构化返回 + 要点正文入库。

数据层 2.0 L3 按需增量方案(SPEC §5 修订, Donnie 批): 不做全市场一次性蒸馏。
问题命中某股时拉该股 F10(本身已结构化): ssbk=板块归属, hxtc=题材要点正文
(含上下游/供应链/客户描述)。要点正文入 L2 知识库供语义检索, 结构化部分直接
返回; LLM 关系归一由消费侧深度分析自然完成(自由分析架构下无需预蒸馏)。
哈希去重=内容变更(季报更新)自动成新文档, 未变则秒过, 成本随使用摊薄。
"""

import json
import logging

from ..ingest import ingest_document
from ._http import get_bytes

logger = logging.getLogger("fin_knowledge")

# 非产业链信息的板块噪声(风格/技术面标签), 过滤后再返回
_SECTOR_NOISE = ("风格", "股", "首亏", "预增", "预减", "扭亏", "昨日", "连板", "涨停")


def _em_code(stock_code: str) -> str:
    code, suffix = stock_code.split(".")
    return f"{suffix.upper()}{code}"


def fetch_core_conception(stock_code: str) -> dict:
    """→ {sectors: [板块], themes: [{keyword, content}]}; 网络失败抛异常不静默。"""
    url = (
        "https://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax"
        f"?code={_em_code(stock_code)}"
    )
    data = json.loads(get_bytes(url, timeout=30))
    sectors = [
        b.get("BOARD_NAME")
        for b in (data.get("ssbk") or [])
        if b.get("BOARD_NAME") and not any(x in b["BOARD_NAME"] for x in _SECTOR_NOISE)
    ]
    themes = [
        {"keyword": t.get("KEYWORD") or "", "content": (t.get("MAINPOINT_CONTENT") or "").strip()}
        for t in (data.get("hxtc") or [])
        if t.get("MAINPOINT_CONTENT")
    ]
    return {"stock_code": stock_code, "sectors": sectors, "themes": themes}


def ingest_core_conception(stock_code: str, stock_name: str = "") -> dict:
    """拉取并入库该股题材要点正文, 返回结构化数据 + 入库状态。"""
    cc = fetch_core_conception(stock_code)
    if not cc["themes"]:
        return {**cc, "status": "not_found"}
    body = "\n\n".join(f"【{t['keyword']}】{t['content']}" for t in cc["themes"])
    text = f"所属板块: {', '.join(cc['sectors'])}\n\n{body}"
    r = ingest_document(
        doc_type="core_conception",
        title=f"{stock_name or stock_code} 核心题材与产业链要点",
        text=text,
        stock_code=stock_code,
        source_url=f"https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?code={_em_code(stock_code)}&type=web#/hxtc",
        published_at=None,
    )
    return {**cc, "status": r["status"], "chunks": r["chunks"]}
