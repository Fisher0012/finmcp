"""公司画像 tools: get_company_profile + get_annual_report_mdna

自 workbench routers/finmcp.py 下沉（SPEC F3 §3.3）。
data 内层字段与原实现保持一致, 外层升级为三态封套。

- get_company_profile: tushare stock_company 直调
- get_annual_report_mdna: 巨潮年报 PDF + pdfplumber（optional extras "disclosure"）,
  90 天缓存由本包 CacheManager（quarterly 档）承担, 替代原 sqlite 缓存。
"""

import importlib.util
from datetime import datetime, timezone
from typing import Any

from finmcp_common.responses import error_response, ok_response

from .. import cninfo
from ..cache import CacheManager

_cache = CacheManager()

# 年报 MD&A 战略关键词（与原实现一致）
_STRATEGY_KWS = [
    "算力",
    "智算",
    "AI",
    "人工智能",
    "大模型",
    "数据中心",
    "GPU",
    "云计算",
    "转型",
    "跨界",
    "进军",
    "布局",
    "战略升级",
    "第二曲线",
    "新业务",
    "并购",
    "重组",
    "收购",
    "战略合作",
    "定增",
    "投资",
    "新能源",
    "储能",
    "氢能",
    "创新药",
    "出海",
    "数字化",
    "智能化",
    "机器人",
    "智能驾驶",
    "低空经济",
]


def get_company_profile(stock_code: str) -> dict[str, Any]:
    """获取公司主营业务/经营范围/公司介绍 (tushare stock_company)。

    用于研判时识别公司战略叙事(转型/新业务方向), 避免被单条新闻误导。

    Args:
        stock_code: 股票代码（如 600519.SH）
    """
    if not stock_code or not stock_code.strip():
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    try:
        import tushare as ts

        pro = ts.pro_api()
        df = pro.stock_company(ts_code=stock_code, fields="ts_code,main_business,business_scope,introduction")
        if df is None or df.empty:
            # tushare 正常响应且无记录 → 确认无（原实现: ok:false "未查到公司信息"）
            return error_response(
                code="DATA_NOT_FOUND",
                message=f"未查到 {stock_code} 的公司信息",
                hint="请检查代码是否正确",
                source="tushare",
            )
        r = df.iloc[0].to_dict()
        # 限制 introduction 长度避免吃 token, 主营/经营范围保留全文
        intro = (r.get("introduction") or "")[:500]
        return ok_response(
            data={
                "stock_code": stock_code,
                "main_business": r.get("main_business") or "",
                "business_scope": (r.get("business_scope") or "")[:400],
                "introduction": intro,
            },
            source="tushare",
        )
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"tushare stock_company 调用失败: {str(e)[:200]}",
            source="tushare",
        )


def _extract_mdna_excerpt(pdf_bytes: bytes, max_chars: int = 5000) -> str:
    """从年报PDF抽取MD&A章节, 然后用关键词匹配抽含战略词的段落, 控制在 max_chars 内"""
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        all_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    # 跳过目录, 找"管理层讨论与分析"正文出现位置(目录通常前 10K 字)
    marker = "管理层讨论与分析"
    positions = []
    i = 0
    while True:
        j = all_text.find(marker, i)
        if j < 0:
            break
        positions.append(j)
        i = j + 1
    start = next((p for p in positions if p > 10000), positions[-1] if positions else -1)
    if start < 0:
        # 退路: 用"经营情况讨论与分析"
        start = all_text.find("经营情况讨论与分析")
        if start < 0:
            return ""
    # 找下一章作为结束
    end = len(all_text)
    for m in ["第四节 公司治理", "第四节  公司治理", "公司治理", "第四节"]:
        k = all_text.find(m, start + 500)
        if 0 < k < end:
            end = k
    mdna = all_text[start:end]
    # 按段切, 抽含战略关键词的段落, 上下文各保留若干段
    segments = []
    paragraphs = mdna.split("\n")
    for idx, para in enumerate(paragraphs):
        if any(kw in para for kw in _STRATEGY_KWS):
            seg = "\n".join(paragraphs[max(0, idx - 1) : min(len(paragraphs), idx + 3)])
            segments.append(seg)
    # 去重
    seen = set()
    deduped = []
    for s in segments:
        key = s[:80]
        if key not in seen:
            seen.add(key)
            deduped.append(s)
    excerpt = "\n---\n".join(deduped)
    if len(excerpt) > max_chars:
        excerpt = excerpt[:max_chars] + "...(已截断)"
    # 如果没抓到任何战略关键词, fallback: 取 MD&A 前 max_chars
    if not excerpt:
        excerpt = mdna[:max_chars]
    return excerpt


def _pdfplumber_available() -> bool:
    try:
        return importlib.util.find_spec("pdfplumber") is not None
    except ValueError:
        # 模块已在 sys.modules 但 __spec__=None（如注入的 stub）: 视为可导入
        return True


def get_annual_report_mdna(stock_code: str) -> dict[str, Any]:
    """年报MD&A战略抽取 (巨潮免费接口 + 90天缓存)。

    抓最新年报PDF → pdfplumber解析 → 切MD&A → 关键词匹配抽战略段落。
    这是识别公司长期战略叙事的根本数据源, 主营业务字段不够细。
    依赖 optional extras: pip install 'finmcp-a-stock-data[disclosure]'

    Args:
        stock_code: 股票代码（如 600519.SH）
    """
    if not stock_code or not stock_code.strip():
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    if not _pdfplumber_available():
        return error_response(
            code="NOT_SUPPORTED",
            message="get_annual_report_mdna 需要 pdfplumber, 请安装: pip install 'finmcp-a-stock-data[disclosure]'",
            source="cninfo",
        )

    cache_key = _cache.make_key("cninfo", "annual_mdna", stock_code)
    try:
        cached = _cache.get(cache_key)
    except Exception:
        cached = None
    if cached is not None:
        return ok_response(data={**cached, "from_cache": True}, source="cninfo", cache_hit=True)

    try:
        meta = cninfo.latest_annual_report(stock_code)
        if not meta:
            # 巨潮正常响应但未检索到年报（原实现: ok:false "巨潮未找到年报"）
            return error_response(
                code="DATA_NOT_FOUND",
                message=f"巨潮未找到 {stock_code} 的年报",
                source="cninfo",
            )
        title = meta["title"]
        # 推断年份
        report_year = "".join([c for c in title if c.isdigit()])[:4] or "unknown"
        pdf_bytes = cninfo.download(meta["url"])
        excerpt = _extract_mdna_excerpt(pdf_bytes, max_chars=2500)
        if not excerpt:
            return error_response(
                code="INTERNAL_ERROR",
                message="MD&A 抽取失败",
                hint="PDF 解析成功但未定位到管理层讨论与分析章节",
                source="cninfo",
            )
        ms = meta.get("date_ms")
        report_date = ""
        if ms:
            try:
                report_date = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                report_date = ""
        data = {
            "report_year": report_year,
            "report_date": report_date,
            "mdna_excerpt": excerpt,
        }
        # 90 天缓存（CACHE_TTL "quarterly" 档, 替代原 sqlite 时间戳逻辑）
        _cache.set(cache_key, data, ttl_category="quarterly")
        return ok_response(data={**data, "from_cache": False}, source="cninfo")
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"年报 MD&A 获取失败: {str(e)[:200]}",
            source="cninfo",
        )
