"""财报全文采集: 定期报告(年报/半年报)全文 → 入库。

三级源(2026-09-09 实测定型, 替换原纯巨潮PDF方案):
1. 主源=新浪财经(vip.stock.finance.sina.com.cn, gb18030, id=content 后全<p>拼接):
   ndbg/zqbg 定期报告专页定位100%可靠、单请求拿全文、独立源。实测5样本(沪深/年报半年报)
   35K-141K字, 风险/募资/管理层讨论章节全覆盖。chunked 偶发 IncompleteRead 用 partial 兜底。
2. fallback=东财 content API(np-cnotice-stock, 分页纯文本): 新浪失败时补。局限: 东财公告
   列表 page_size 上限100 且按时间倒序, 年报披露数月后沉到100条外定位不到(实测宁德2025年报)。
3. 兜底=巨潮 cninfo PDF + pdfplumber(前两者都拿不到时, 最全但最慢)。
字数闸门 _MIN_FULLTEXT: 正文 < 阈值判定残缺, 降级取更长的源。_consider 取各源最长文本。
"""

import json
import logging
import re
import tempfile

from ..ingest import ingest_document
from ._http import get_bytes

logger = logging.getLogger("fin_knowledge")

_MAX_PAGES = 400  # 年报正文规模上限, 防异常大 PDF 拖死
_MIN_FULLTEXT = 10000  # 定期报告正文字数下限; 低于视为抽取残缺, 触发 fallback

_EM_HEADERS = {"Referer": "https://data.eastmoney.com/"}
_EM_ANN_LIST = (
    "https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=50"
    "&page_index=1&ann_type=A&client_source=web&stock_list={code}&f_node=0&s_node=0"
)
_EM_CONTENT = "https://np-cnotice-stock.eastmoney.com/api/content/ann?art_code={art}&client_source=web&page_index={pg}"

# kind → 各源的标题关键词/排除词、新浪路径、doc_type
_KIND_META = {
    "annual": {
        "kw": "年度报告",
        "not_kw": "半年度",  # "半年度报告"含"年度报告"子串, 年报须排除
        "sina_path": "vCB_Bulletin",
        "sina_type": "ndbg",
        "doc_type": "annual_report",
        "label": "年度报告",
    },
    "semiannual": {
        "kw": "半年度报告",
        "not_kw": None,
        "sina_path": "vCB_BulletinZhong",
        "sina_type": "zqbg",
        "doc_type": "semiannual_report",
        "label": "半年度报告",
    },
}
_TITLE_EXCLUDE = ("摘要", "英文", "English", "已取消", "更正", "问询", "补充", "提示性")


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


# ────────────────────────── 源1: 东财 content API ──────────────────────────
def _em_find_report(stock_code: str, kind: str) -> dict | None:
    """东财公告列表里定位最新定期报告, 返回 {art_code, title, date}。"""
    meta = _KIND_META[kind]
    code = stock_code.split(".")[0]
    data = json.loads(get_bytes(_EM_ANN_LIST.format(code=code), headers=_EM_HEADERS))
    items = (data.get("data") or {}).get("list") or []
    for it in items:
        title = it.get("title", "")
        if meta["kw"] not in title or any(x in title for x in _TITLE_EXCLUDE):
            continue
        if meta["not_kw"] and meta["not_kw"] in title:
            continue
        return {
            "art_code": it.get("art_code"),
            "title": title,
            "date": (it.get("notice_date") or "")[:10],
        }
    return None


def _em_fulltext(art_code: str) -> str:
    """东财 content 分页拼接全文。page_size=总页数, 每页 notice_content≈5000字。"""
    first = json.loads(get_bytes(_EM_CONTENT.format(art=art_code, pg=1), headers=_EM_HEADERS)).get("data") or {}
    pages = int(first.get("page_size") or 1)
    parts = [first.get("notice_content") or ""]
    for pg in range(2, min(pages, _MAX_PAGES) + 1):
        try:
            d = json.loads(get_bytes(_EM_CONTENT.format(art=art_code, pg=pg), headers=_EM_HEADERS)).get("data") or {}
            parts.append(d.get("notice_content") or "")
        except Exception as e:
            logger.warning("东财 content 分页失败 %s pg=%s: %s", art_code, pg, e)
            break
    return "\n".join(p for p in parts if p)


# ────────────────────────── 源2: 新浪财经 ──────────────────────────
_SINA_BASE = "http://vip.stock.finance.sina.com.cn"
_SINA_DETAIL_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})&nbsp;<a[^>]*href='(/corp/view/vCB_AllBulletinDetail\.php\?stockid=\d+&id=\d+)'>([^<]+)</a>"
)


def _get_tolerant(url: str, timeout: int = 30) -> bytes:
    """容错 GET: 新浪年报大页面 chunked 传输偶发 IncompleteRead, 用已读 partial 兜底。"""
    import http.client

    try:
        return get_bytes(url, timeout=timeout)
    except http.client.IncompleteRead as e:
        logger.warning("新浪 IncompleteRead, 用 partial %d 字节: %s", len(e.partial), url)
        return e.partial


def _sina_clean(p: str) -> str:
    p = re.sub(r"<[^>]+>", "", p)
    p = p.replace("&nbsp;", " ").replace("&amp;", "&")
    return p.strip()


def _sina_find(stock_code: str, kind: str) -> dict | None:
    """轻量: 仅请求新浪列表页, 定位最新一份定期报告 {url, title, date}(不抓正文)。

    供调度层做水位判断(最新披露日期 vs 已入库), 避免每周重抓全文。
    """
    meta = _KIND_META[kind]
    num = stock_code.split(".")[0]
    lst_url = f"{_SINA_BASE}/corp/go.php/{meta['sina_path']}/stockid/{num}/page_type/{meta['sina_type']}.phtml"
    html = _get_tolerant(lst_url, timeout=20).decode("gb18030", "ignore")
    m = re.search(r"datelist", html)
    seg = html[m.start():] if m else html
    for date, href, ttl in _SINA_DETAIL_RE.findall(seg):
        if any(x in ttl for x in _TITLE_EXCLUDE):
            continue
        if meta["kw"] not in ttl:
            continue
        if meta["not_kw"] and meta["not_kw"] in ttl:
            continue
        return {"url": _SINA_BASE + href, "title": ttl.strip(), "date": date}
    return None


def _sina_fetch(stock_code: str, kind: str) -> dict | None:
    """新浪列表两跳取全文: _sina_find 定位 → 详情页 id=content 后全<p>拼接。"""
    target = _sina_find(stock_code, kind)
    if not target:
        return None
    det = _get_tolerant(target["url"], timeout=30).decode("gb18030", "ignore")
    start = re.search(r'id=["\']?content["\']?', det)
    tail = det[start.start():] if start else det
    ps = re.findall(r"<p[^>]*>(.*?)</p>", tail, re.S)
    text = "\n".join(t for t in (_sina_clean(p) for p in ps) if t)
    target["text"] = text
    return target


# ────────────────────────── 源3: 巨潮 PDF 兜底 ──────────────────────────
_PERIODIC_CATEGORIES = {
    "annual": ("category_ndbg_szsh", "年度报告"),
    "semiannual": ("category_bndbg_szsh", "半年度报告"),
}


def latest_periodic_report(stock_code: str, kind: str = "annual") -> dict | None:
    """巨潮最新定期报告(年报/半年报), 排除标题变体(摘要/英文版等)。"""
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


def _cninfo_fetch(stock_code: str, kind: str) -> dict | None:
    """巨潮 PDF 下载 + pdfplumber 抽文本(最慢, 仅兜底)。"""
    from finmcp_a_stock_data.cninfo import download

    ann = latest_periodic_report(stock_code, kind)
    if not ann:
        return None
    pdf = download(ann["url"], timeout=120)
    text = _pdf_to_text(pdf)
    date_ms = ann.get("date_ms")
    date = ""
    if isinstance(date_ms, (int, float)):
        from datetime import datetime

        date = datetime.fromtimestamp(date_ms / 1000).strftime("%Y-%m-%d")
    return {"title": ann.get("title"), "url": ann["url"], "date": date, "text": text}


# ────────────────────────── 主入口: 三级源级联 ──────────────────────────
def ingest_periodic_report(stock_code: str, kind: str = "semiannual") -> dict:
    """抓取并入库该股最新定期报告全文。东财主源→字数闸门→新浪→巨潮PDF兜底。

    doc_type: annual_report / semiannual_report。返回含 source(命中源)+chars(正文字数)。
    """
    meta = _KIND_META[kind]
    best = {"text": "", "title": None, "date": "", "url": "", "source": "none"}

    def _consider(src: str, cand: dict | None) -> None:
        if cand and len(cand.get("text") or "") > len(best["text"]):
            best.update({
                "text": cand["text"], "title": cand.get("title"),
                "date": cand.get("date") or "", "url": cand.get("url") or "", "source": src,
            })

    # 源1: 新浪(主源, ndbg/zqbg 定期报告专页定位100%可靠 + 单请求全文 + 独立源)
    try:
        _consider("sina", _sina_fetch(stock_code, kind))
    except Exception as e:
        logger.warning("新浪定期报告失败 %s %s: %s", stock_code, kind, e)

    # 源2: 东财 content(新浪不足时补; 列表定位受限——年报披露数月后沉到100条外定位不到)
    if len(best["text"]) < _MIN_FULLTEXT:
        try:
            em = _em_find_report(stock_code, kind)
            if em and em.get("art_code"):
                text = _em_fulltext(em["art_code"])
                _consider("eastmoney", {
                    "text": text, "title": em["title"], "date": em["date"],
                    "url": f"https://np-cnotice-stock.eastmoney.com/api/content/ann?art_code={em['art_code']}",
                })
        except Exception as e:
            logger.warning("东财定期报告失败 %s %s: %s", stock_code, kind, e)

    # 源3: 巨潮 PDF 兜底(仍不足时)
    if len(best["text"]) < _MIN_FULLTEXT:
        try:
            _consider("cninfo", _cninfo_fetch(stock_code, kind))
        except Exception as e:
            logger.warning("巨潮定期报告失败 %s %s: %s", stock_code, kind, e)

    if not best["text"]:
        return {"status": "not_found", "stock_code": stock_code, "kind": kind}

    result = ingest_document(
        doc_type=meta["doc_type"],
        title=best["title"] or f"{stock_code} {meta['label']}",
        text=best["text"],
        stock_code=stock_code,
        source_url=best["url"],
        published_at=str(best["date"]),
    )
    result.update({"title": best["title"], "source": best["source"], "chars": len(best["text"])})
    return result


def ingest_annual_report(stock_code: str) -> dict:
    """抓取并入库该股最新年报全文(三级源级联, 见 ingest_periodic_report)。"""
    return ingest_periodic_report(stock_code, kind="annual")
