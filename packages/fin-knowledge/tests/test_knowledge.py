# -*- coding: utf-8 -*-
"""fin-knowledge 单测: 分块 / 去重入库 / 余弦检索（embedding 全程 mock, 不触网）。"""

import numpy as np
import pytest

import fin_knowledge.ingest as ingest_mod
import fin_knowledge.query as query_mod
from fin_knowledge.chunker import MAX_CHARS, chunk_text
from fin_knowledge.ingest import ingest_document
from fin_knowledge.query import knowledge_stats, search_knowledge


def _fake_vec(text: str) -> list[float]:
    """确定性伪向量: 关键词命中维度置高值, 保证相关文本余弦更近。"""
    v = np.zeros(1024, dtype=np.float32)
    v[hash("base") % 1024] = 0.1
    for kw, dim in [("白酒", 3), ("营收", 7), ("锂电池", 11), ("政策", 13)]:
        if kw in text:
            v[dim] = 1.0
    return v.tolist()


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_KNOWLEDGE_DB", str(tmp_path / "knowledge.db"))
    monkeypatch.setattr(ingest_mod, "embed_texts", lambda ts: [_fake_vec(t) for t in ts])
    monkeypatch.setattr(query_mod, "embed_query", lambda t: _fake_vec(t))
    # db.py 记忆已初始化路径, tmp_path 每例不同, 无需清理


def test_chunker_sections_and_size():
    text = "第一节 公司概况\n" + "白酒业务稳定。" * 30 + "\n第二节 经营分析\n" + "营收增长明显。" * 200
    chunks = chunk_text(text)
    assert len(chunks) >= 3
    assert chunks[0]["section"].startswith("第一节")
    assert all(len(c["text"]) <= MAX_CHARS for c in chunks)
    # 续块携带章节锚
    later = [c for c in chunks if c["section"].startswith("第二节")]
    assert len(later) >= 2


def test_ingest_dedup_and_stats():
    r1 = ingest_document("annual_report", "某公司2025年报", "第一节 概况\n白酒营收稳定。", stock_code="600519.SH")
    assert r1["status"] == "ingested" and r1["chunks"] >= 1
    r2 = ingest_document("annual_report", "某公司2025年报", "第一节 概况\n白酒营收稳定。", stock_code="600519.SH")
    assert r2["status"] == "duplicate"
    assert ingest_document("report", "空文", "  ")["status"] == "empty"
    stats = knowledge_stats()
    assert stats["docs_by_type"]["annual_report"] == 1


def test_search_relevance_and_filters():
    ingest_document("annual_report", "白酒年报", "第一节\n白酒销售营收情况良好。", stock_code="600519.SH")
    ingest_document("annual_report", "锂电年报", "第一节\n锂电池产能扩张。", stock_code="300750.SZ")
    ingest_document("policy", "政策文件", "一、\n政策支持消费。")
    hits = search_knowledge("白酒行业营收", top_k=2)
    assert hits and "白酒" in hits[0]["text"]
    assert hits[0]["doc_title"] == "白酒年报" and hits[0]["score"] > hits[-1]["score"] - 1e-9
    # stock_code 过滤
    hits = search_knowledge("营收", stock_code="300750.SZ")
    assert all(h["stock_code"] == "300750.SZ" for h in hits)
    # doc_type 过滤
    hits = search_knowledge("政策", doc_types=["policy"])
    assert hits and all(h["doc_type"] == "policy" for h in hits)
    # 空查询/无命中
    assert search_knowledge("") == []
    assert search_knowledge("任意", stock_code="999999.SH") == []
