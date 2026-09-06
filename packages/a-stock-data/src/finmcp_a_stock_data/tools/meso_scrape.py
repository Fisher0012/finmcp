"""中观景气自建抓取 tools（数据缺口补源, 对应 workbench docs/DATA_GAP_SOURCES.md）。

来源 2026-09-05 实测:
- 水泥: 中国水泥网 index.ccement.com POST /index/priceindex/cementkline
  (免登录, 返回周频 K 线 bar, 非清单所述日频——实测每 bar 间隔 7 天)
- 挖掘机: 工程机械协会 www.cncma.org 首页"销售快报"文章正则抽取(次月 8 日左右发布)
- 集成电路: 国家统计局 www.stats.gov.cn/sj/zxfb/ 规模以上工业增加值月度稿附表
- 白酒批价: mffb.com.cn(裸域, 注意 www.mffb.com.cn 是另一个不相关 B2B 站)
  首页"酒价参考"转载稿(约周频, 数据日期以稿内标题为准)
"""

import html as _html
import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from finmcp_common.responses import error_response, ok_response

from ..cache import CacheManager
from ..errors import handle_tool_error

logger = logging.getLogger(__name__)
_cache = CacheManager()

# 绕过环境代理(国内站点走代理会失败)
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
_CST = timezone(timedelta(hours=8))


def _http_get(url: str, extra_headers: dict[str, str] | None = None, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={**_UA, **(extra_headers or {})})
    with _opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def _http_post_form(
    url: str, form: dict[str, Any], extra_headers: dict[str, str] | None = None, timeout: int = 25
) -> str:
    payload = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=payload, headers={**_UA, **(extra_headers or {})})
    with _opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def _strip_tags(raw: str) -> str:
    """去标签+压缩空白, 用于正文正则抽取"""
    text = re.sub(r"<[^>]+>", "", raw)
    return re.sub(r"\s+", "", _html.unescape(text))


def _table_rows(raw: str) -> list[list[str]]:
    """解析 HTML 中所有 <tr> 为去标签后的单元格列表(空单元格剔除)"""
    rows: list[list[str]] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", raw, re.S):
        cells = [_strip_tags(td) for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    return rows


# ---------------------------------------------------------------- 1. 水泥价格指数


def get_cement_price() -> dict[str, Any]:
    """全国水泥价格指数(CEMPI, 2009年=100点)近 30 期序列。

    来源: 中国水泥网 index.ccement.com, 周频 K 线(每期约隔 7 天), 免登录。
    水泥是基建/地产链最硬的量价景气指标之一。
    """
    cache_key = _cache.make_key("scrape", "cement_price")
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="ccement", cache_hit=True)
    try:
        end = datetime.now(_CST).date()
        start = end - timedelta(days=365)
        body = _http_post_form(
            "https://index.ccement.com/index/priceindex/cementkline",
            {
                "start_time": start.strftime("%Y-%m-%d"),
                "end_time": end.strftime("%Y-%m-%d"),
                "areaV": "country",
                "timeType": 3,
            },
            extra_headers={
                "Referer": "https://index.ccement.com/",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        resp = json.loads(body)
        if resp.get("Code") != 200:
            return error_response(
                code="UPSTREAM_ERROR", message=f"水泥指数接口返回 Code={resp.get('Code')}", source="ccement"
            )
        inner = resp.get("Data")
        bars = json.loads(inner) if isinstance(inner, str) else (inner or [])
        # bar 格式实测: [毫秒时间戳, open, high, low, close, prev_close, change, change_pct]
        series = []
        for bar in bars[-30:]:
            if not isinstance(bar, list) or len(bar) < 8:
                continue
            dt = datetime.fromtimestamp(bar[0] / 1000, _CST)
            series.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "index": bar[4],
                    "change": bar[6],
                    "change_pct": bar[7],
                }
            )
        if not series:
            return error_response(
                code="DATA_NOT_FOUND", message="水泥指数本次未取得数据(上游返回空), 未缓存可稍后重试", source="ccement"
            )
        data = {
            "name": "全国水泥价格指数(CEMPI)",
            "series": series,
            "note": "index 为指数点位(2009年=100点), change 为环比变动点数, change_pct 为环比%; "
            "周频 K 线收盘值(每期约隔7天), 来源中国水泥网 index.ccement.com",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="ccement")
    except Exception as e:
        return handle_tool_error(e, source="ccement")


# ---------------------------------------------------------------- 2. 挖掘机销量

_CNCMA_BASE = "http://www.cncma.org/"


def get_excavator_sales() -> dict[str, Any]:
    """挖掘机月度销量最新一期(总量/国内/出口/同比 + 年累计)。

    来源: 中国工程机械工业协会 cncma.org 月度销售快报(次月 8 日左右发布)。
    挖掘机销量是基建/地产开工端最经典的先行指标。
    """
    cache_key = _cache.make_key("scrape", "excavator_sales")
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="cncma", cache_hit=True)
    try:
        home = _http_get(_CNCMA_BASE)
        # 首页资讯列表匹配"销售快报", 文章 id 越大越新
        links = re.findall(r'href="/?(article/(\d+))"[^>]*>([^<]*销售快报[^<]*)</a>', home)
        candidates = sorted({(int(aid), path, title.strip()) for path, aid, title in links}, reverse=True)
        if not candidates:
            return error_response(
                code="DATA_NOT_FOUND", message="cncma 首页未找到'销售快报'文章, 未缓存可稍后重试", source="cncma"
            )
        # 快报分一/二两篇, 挖掘机在其一; 逐篇尝试直到正则命中
        for _aid, path, title in candidates[:4]:
            url = _CNCMA_BASE + path
            text = _strip_tags(_http_get(url))
            m = re.search(r"(\d{4})年(\d{1,2})月销售各类挖掘机(\d+)台[，,]同比(增长|下降)([\d.]+)%", text)
            if not m:
                continue
            sign = 1 if m.group(4) == "增长" else -1
            result: dict[str, Any] = {
                "period": f"{m.group(1)}-{int(m.group(2)):02d}",
                "total_units": int(m.group(3)),
                "total_yoy_pct": sign * float(m.group(5)),
                "article_title": title,
                "article_url": url,
            }
            md = re.search(r"国内销量(\d+)台(?:（[^）]*）)?[，,]同比(增长|下降)([\d.]+)%", text)
            if md:
                result["domestic_units"] = int(md.group(1))
                result["domestic_yoy_pct"] = (1 if md.group(2) == "增长" else -1) * float(md.group(3))
            me = re.search(r"出口(\d+)台(?:（[^）]*）)?[，,]同比(增长|下降)([\d.]+)%", text)
            if me:
                result["export_units"] = int(me.group(1))
                result["export_yoy_pct"] = (1 if me.group(2) == "增长" else -1) * float(me.group(3))
            my = re.search(r"(\d{4})年1[-—](\d{1,2})月[，,]共销售挖掘机(\d+)台[，,]同比(增长|下降)([\d.]+)%", text)
            if my:
                result["ytd_period"] = f"{my.group(1)}-01~{int(my.group(2)):02d}"
                result["ytd_units"] = int(my.group(3))
                result["ytd_yoy_pct"] = (1 if my.group(4) == "增长" else -1) * float(my.group(5))
            result["note"] = (
                "单位: 台; *_yoy_pct 为同比%(负数=下降); 含电动挖掘机; "
                "来源中国工程机械工业协会月度销售快报, 次月8日左右发布"
            )
            _cache.set(cache_key, result, ttl_category="daily")
            return ok_response(data=result, source="cncma")
        return error_response(
            code="DATA_NOT_FOUND",
            message="销售快报文章中未匹配到挖掘机销量段落(正文结构可能变更), 未缓存",
            source="cncma",
        )
    except Exception as e:
        return handle_tool_error(e, source="cncma")


# ---------------------------------------------------------------- 3. 集成电路产量

_NBS_LIST_URL = "https://www.stats.gov.cn/sj/zxfb/"


def get_chip_output() -> dict[str, Any]:
    """集成电路月度产量(当月亿块/同比/累计, 国家统计局口径)。

    来源: 国家统计局最新发布列表 → 规模以上工业增加值月度稿附表(次月中旬发布)。
    国产半导体产出端最权威的官方月度数据。
    """
    cache_key = _cache.make_key("scrape", "chip_output")
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="stats.gov.cn", cache_hit=True)
    try:
        listing = _http_get(_NBS_LIST_URL)
        # 列表页最新一条"规模以上工业增加值"月度稿(列表按时间倒序)
        m = re.search(r'href="\.?/?([^"]+\.html)"[^>]*>\s*((\d{4})年(\d{1,2})月份?规模以上工业增加值[^<]*)<', listing)
        if not m:
            return error_response(
                code="DATA_NOT_FOUND",
                message="统计局发布列表未找到'规模以上工业增加值'月度稿, 未缓存",
                source="stats.gov.cn",
            )
        article_url = urllib.parse.urljoin(_NBS_LIST_URL, m.group(1))
        title = re.sub(r"\s+", "", m.group(2))
        period = f"{m.group(3)}-{int(m.group(4)):02d}"
        article = _http_get(article_url)
        ic_row: list[str] | None = None
        for cells in _table_rows(article):
            if cells and "集成电路" in cells[0]:
                ic_row = cells
                break
        # 附表行实测格式: [集成电路（亿块）, 当月产量, 当月同比%, 累计产量, 累计同比%]
        if not ic_row or len(ic_row) < 5:
            return error_response(
                code="DATA_NOT_FOUND",
                message=f"工业增加值稿附表未解析到集成电路行(稿件: {article_url}), 未缓存",
                source="stats.gov.cn",
            )
        try:
            data = {
                "period": period,
                "output_100m_units": float(ic_row[1]),
                "yoy_pct": float(ic_row[2]),
                "ytd_output_100m_units": float(ic_row[3]),
                "ytd_yoy_pct": float(ic_row[4]),
                "article_title": title,
                "article_url": article_url,
                "note": "单位: 亿块(当月/累计产量), yoy_pct 为同比%; "
                "来源国家统计局规模以上工业增加值月度稿附表, 次月中旬发布",
            }
        except ValueError:
            return error_response(
                code="DATA_NOT_FOUND", message=f"集成电路行数值解析失败: {ic_row}, 未缓存", source="stats.gov.cn"
            )
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="stats.gov.cn")
    except Exception as e:
        return handle_tool_error(e, source="stats.gov.cn")


# ---------------------------------------------------------------- 4. 白酒批价

# 注意: 必须用裸域 mffb.com.cn; www.mffb.com.cn 是另一个不相关的 destoon B2B 站(实测确认)
_MFFB_BASE = "https://mffb.com.cn/"


def get_liquor_price() -> dict[str, Any]:
    """茅台飞天批价表(各年份原箱/散瓶, 元/瓶)。

    来源: mffb.com.cn 转载"今日酒价"行情稿, 约周频转载, 数据日期以稿内为准(有时效滞后)。
    飞天批价是高端白酒景气与商务需求的市场化温度计。
    """
    cache_key = _cache.make_key("scrape", "liquor_price")
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="mffb", cache_hit=True)
    try:
        home = _http_get(_MFFB_BASE)
        links = re.findall(r'<a[^>]+href="(?:https?://mffb\.com\.cn)?/a/(\d+)\.html"[^>]*>([^<]*)</a>', home)
        # 优先"酒价参考"系列(全年份批价表最全), 退而求"茅台行情"; id 越大越新
        candidates = sorted(
            {(int(aid), t.strip()) for aid, t in links if "酒价参考" in t or "茅台行情" in t},
            reverse=True,
        )
        pref = [c for c in candidates if "酒价参考" in c[1]] or candidates
        if not pref:
            return error_response(
                code="DATA_NOT_FOUND", message="mffb 首页未找到酒价行情稿, 未缓存可稍后重试", source="mffb"
            )
        aid, title = pref[0]
        article_url = f"{_MFFB_BASE}a/{aid}.html"
        article = _http_get(article_url)
        # 稿内数据日期取标题"M月D日"; 年份取稿件发布年(转载稿, 跨年边界可能偏差)
        pub = re.search(r"(\d{4})-\d{2}-\d{2}\s+\d{2}:\d{2}", article)
        pub_year = pub.group(1) if pub else str(datetime.now(_CST).year)
        dm = re.search(r"(\d{1,2})月(\d{1,2})日", title)
        data_date = f"{pub_year}-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}" if dm else None
        # 批价表: 取"飞天/15年/30年"行, 格式实测 [品名, 参数, 价格]
        items = []
        for cells in _table_rows(article):
            if len(cells) < 3 or "飞天" not in cells[0]:
                continue
            mprice = re.match(r"^\d+(\.\d+)?$", cells[-1])
            if not mprice:
                continue
            name = cells[0].replace("(整", "(原箱").replace("(散", "(散瓶")
            items.append({"name": name, "spec": cells[1], "price_yuan": float(cells[-1])})
        if not items:
            return error_response(
                code="DATA_NOT_FOUND", message=f"酒价稿未解析到飞天批价表(稿件: {article_url}), 未缓存", source="mffb"
            )
        data = {
            "data_date": data_date,
            "article_title": title,
            "article_url": article_url,
            "prices": items,
            "note": "price_yuan 为批价(元/瓶), 原箱=整箱拆算单瓶价, 散瓶=单瓶流通价; "
            "来源 mffb.com.cn 约周频转载今日酒价, 数据日期以稿内为准(data_date), 有时效滞后; "
            "转载渠道报价仅供参考",
        }
        _cache.set(cache_key, data, ttl_category="daily")
        return ok_response(data=data, source="mffb")
    except Exception as e:
        return handle_tool_error(e, source="mffb")
