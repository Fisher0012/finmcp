"""巨潮资讯网公开接口访问助手

供两处复用（SPEC F3）:
- tushare_src._fetch_announcements: 个股公告检索（tushare anns_d 无权限, B 方案换源）
- tools/profile.get_annual_report_mdna: 最新年报 PDF 定位与下载

国内接口直连（忽略系统代理, 服务器进程可能带境外 socks 代理, 走代理会超时）。
失败一律向上抛异常, 由调用方按 F1 三态封套记录, 本模块不吞异常。
"""

import json
import urllib.parse
import urllib.request
from typing import Any

from finmcp_common.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT = 15
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}
# 强制直连, 忽略系统代理（巨潮为国内站点）
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# ts_code 简码 → orgId 进程内缓存
_ORG_CACHE: dict[str, str] = {}


def _post_json(url: str, params: dict[str, Any], timeout: int = _TIMEOUT) -> Any:
    """POST 表单并解析 JSON, 失败抛异常"""
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers=_HEADERS)
    with _opener.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search_org_id(stock_code: str) -> str | None:
    """巨潮搜公司 orgId（topSearch 接口）, 命中进程缓存。

    返回 None = 接口正常响应但未匹配到该代码（确认无）; 网络/解析失败抛异常。
    """
    code_simple = stock_code.split(".")[0]
    if code_simple in _ORG_CACHE:
        return _ORG_CACHE[code_simple]
    arr = _post_json(
        "http://www.cninfo.com.cn/new/information/topSearch/query",
        {"keyWord": code_simple, "maxNum": 3},
        timeout=10,
    )
    for item in arr or []:
        if item.get("code") == code_simple and item.get("orgId"):
            _ORG_CACHE[code_simple] = str(item["orgId"])
            return _ORG_CACHE[code_simple]
    return None


def _column_plate(stock_code: str) -> tuple[str, str]:
    """按交易所后缀映射巨潮检索的 column/plate 参数。

    北交所(.BJ)的参数映射【真实调用未验证】, 按巨潮前端惯例取 bse/bj。
    """
    if stock_code.endswith(".SZ"):
        return "szse", "sz"
    if stock_code.endswith(".BJ"):
        return "bse", "bj"
    return "sse", "sh"


def query_announcements(
    stock_code: str,
    se_date: str,
    category: str = "",
    page_size: int = 30,
) -> list[dict[str, Any]]:
    """巨潮公告检索（hisAnnouncement/query）, 返回原始 announcements 列表。

    Args:
        stock_code: 带后缀代码（如 600519.SH）
        se_date: 日期范围, 格式 "YYYY-MM-DD~YYYY-MM-DD"
        category: 巨潮公告分类（如 "category_ndbg_szsh" 年报）, 空 = 全部
        page_size: 单页条数

    orgId 未匹配到返回空列表（上游确认无此公司）; 网络失败抛异常。
    """
    org_id = search_org_id(stock_code)
    if not org_id:
        return []
    code_simple = stock_code.split(".")[0]
    column, plate = _column_plate(stock_code)
    d = _post_json(
        "http://www.cninfo.com.cn/new/hisAnnouncement/query",
        {
            "stock": f"{code_simple},{org_id}",
            "tabName": "fulltext",
            "pageSize": page_size,
            "pageNum": 1,
            "column": column,
            "category": category,
            "plate": plate,
            "seDate": se_date,
            "isHLtitle": "true",
        },
    )
    anns = d.get("announcements") if isinstance(d, dict) else None
    return list(anns) if anns else []


def latest_annual_report(stock_code: str) -> dict[str, Any] | None:
    """巨潮搜最新年报 PDF（非摘要）。返回 {title, url, date_ms} 或 None（确认未找到）。"""
    anns = query_announcements(
        stock_code,
        se_date="2023-01-01~2027-12-31",
        category="category_ndbg_szsh",
        page_size=10,
    )
    for ann in anns:
        title = ann.get("announcementTitle", "")
        if "年度报告" in title and "摘要" not in title:
            return {
                "title": title,
                "url": f"http://static.cninfo.com.cn/{ann.get('adjunctUrl', '')}",
                "date_ms": ann.get("announcementTime"),
            }
    return None


def download(url: str, timeout: int = 30) -> bytes:
    """下载巨潮静态资源（年报 PDF 等）, 失败抛异常"""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _opener.open(req, timeout=timeout) as resp:
        return bytes(resp.read())
