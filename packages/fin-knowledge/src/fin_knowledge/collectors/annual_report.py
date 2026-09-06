"""财报全文采集: 巨潮最新年报 PDF → pdfplumber 抽文本 → 入库。

复用 finmcp-a-stock-data 的 cninfo 接口（同机已部署包）; pdfplumber 为运行环境
已有依赖（workbench 文件解读线在用）, 本包不重复声明。
"""

import logging
import tempfile

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


_PERIODIC_CATEGORIES = {
    "annual": ("category_ndbg_szsh", "年度报告"),
    "semiannual": ("category_bndbg_szsh", "半年度报告"),
}


def latest_periodic_report(stock_code: str, kind: str = "annual") -> dict | None:
    """巨潮最新定期报告(年报/半年报), 排除标题变体(摘要/英文版等, 同年报教训)。"""
    from finmcp_a_stock_data.cninfo import query_announcements

    category, _label = _PERIODIC_CATEGORIES[kind]
    anns = query_announcements(stock_code, se_date="2023-01-01~2027-12-31", category=category, page_size=10)
    _exclude_re = ("摘要", "英文", "English", "已取消", "提示性公告", "更正前")
    for ann in anns:
        title = ann.get("announcementTitle", "")
        if "报告" in title and not any(x in title for x in _exclude_re):
            return {
                "title": title,
                "url": f"http://static.cninfo.com.cn/{ann.get('adjunctUrl', '')}",
                "date_ms": ann.get("announcementTime"),
            }
    return None


def ingest_periodic_report(stock_code: str, kind: str = "semiannual") -> dict:
    """抓取并入库该股最新半年报(或年报)全文。doc_type 分别为 semiannual_report/annual_report。"""
    from finmcp_a_stock_data.cninfo import download

    ann = latest_periodic_report(stock_code, kind)
    if not ann:
        return {"status": "not_found", "stock_code": stock_code, "kind": kind}
    pdf = download(ann["url"], timeout=120)
    text = _pdf_to_text(pdf)
    result = ingest_document(
        doc_type="annual_report" if kind == "annual" else "semiannual_report",
        title=ann.get("title") or f"{stock_code} {_PERIODIC_CATEGORIES[kind][1]}",
        text=text,
        stock_code=stock_code,
        source_url=ann["url"],
        published_at=str(ann.get("date_ms") or ""),
    )
    result["title"] = ann.get("title")
    return result


def ingest_annual_report(stock_code: str) -> dict:
    """抓取并入库该股最新年报全文。

    Returns: ingest_document 结果 + title; 找不到年报时 {status: not_found}。
    """
    from finmcp_a_stock_data.cninfo import download, latest_annual_report

    ann = latest_annual_report(stock_code)
    if not ann:
        return {"status": "not_found", "stock_code": stock_code}
    pdf = download(ann["url"], timeout=120)  # 大年报 PDF 30s 不够(首轮 24 只超时, 2026-09-04 类修复)
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
