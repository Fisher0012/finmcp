"""财报全文采集: 巨潮最新年报 PDF → pdfplumber 抽文本 → 入库。

复用 finmcp-a-stock-data 的 cninfo 接口（同机已部署包）; pdfplumber 为运行环境
已有依赖（workbench 文件解读线在用）, 本包不重复声明。
"""

import logging
import tempfile
from pathlib import Path

from ..ingest import ingest_document

logger = logging.getLogger("fin_knowledge")

_MAX_PAGES = 400  # 年报正文规模上限, 防异常大 PDF 拖死


def _pdf_to_text(data: bytes) -> str:
    import pdfplumber

    texts: list[str] = []
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        with pdfplumber.open(f.name) as doc:
            for page in doc.pages[:_MAX_PAGES]:
                texts.append(page.extract_text() or "")
    return "\n".join(texts)


def ingest_annual_report(stock_code: str) -> dict:
    """抓取并入库该股最新年报全文。

    Returns: ingest_document 结果 + title; 找不到年报时 {status: not_found}。
    """
    from finmcp_a_stock_data.cninfo import download, latest_annual_report

    ann = latest_annual_report(stock_code)
    if not ann:
        return {"status": "not_found", "stock_code": stock_code}
    pdf = download(ann["url"])
    text = _pdf_to_text(pdf)
    result = ingest_document(
        doc_type="annual_report",
        title=ann.get("title") or f"{stock_code} 年度报告",
        text=text,
        stock_code=stock_code,
        source_url=ann["url"],
        published_at=str(ann.get("date") or ""),
    )
    result["title"] = ann.get("title")
    return result
