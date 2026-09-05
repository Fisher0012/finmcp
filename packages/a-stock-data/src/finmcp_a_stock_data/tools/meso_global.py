"""中观景气与外部环境 tools（数据层 2.0 批次三）。

来源 2026-09-03/04 实测:
- akshare: car_market_total_cpca(乘联会车市) / index_hog_spot_price(生猪现货) /
  macro_china_commodity_price_index(大宗商品指数); 水泥/挖掘机无源(实测确认缺失, 显式不提供)
- 新浪行情: int_dji/int_nasdaq/int_sp500(美三大指数) gb_nvda(个股) fx_susdcnh(离岸人民币)
  DINIW(美元指数), 需 Referer 头, GBK 编码, 绕代理
- akshare bond_zh_us_rate: 美债收益率(T+1 滞后, 当日行可能 NaN)
"""

import logging
import re
import urllib.request
from typing import Any

from finmcp_common.responses import error_response, ok_response

from ..cache import CacheManager
from ..errors import handle_tool_error

logger = logging.getLogger(__name__)
_cache = CacheManager()

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# 指标注册表: indicator → (取数函数名, 参数, 取尾行数, 是否倒序(最新在前需 head), 描述)
# 全部 2026-09-05 实测可用(akshare v1.18.54); 缺口: 30城商品房成交/白酒价/半导体销售额无接口
_MESO_TABLE = {
    "car": ("car_market_total_cpca", {"symbol": "狭义乘用车", "indicator": "产量"}, 13, False, "乘联会狭义乘用车月度产销"),
    "hog": ("index_hog_spot_price", {}, 30, False, "生猪现货价格指数"),
    "commodity": ("macro_china_commodity_price_index", {}, 30, False, "中国大宗商品价格指数"),
    "battery_solar": ("futures_spot_price_daily", {"vars_list": ["SI", "LC", "PS"]}, 30, False, "工业硅/碳酸锂/多晶硅日频现货价(光伏锂电上游)"),
    "shipping": ("macro_shipping_bdi", {}, 30, False, "波罗的海干散货指数 BDI(日频)"),
    "electricity": ("macro_china_society_electricity", {}, 13, False, "全社会用电量月度(含一二三产分项, 最硬工业景气)"),
    "logistics": ("macro_china_lpi_index", {}, 13, False, "物流业景气指数(月频荣枯线)"),
    "house": ("macro_china_new_house_price", {}, 13, False, "70城新房/二手房价格指数(月频)"),
    "semiconductor": ("macro_global_sox_index", {}, 30, False, "费城半导体指数(日频, 半导体景气市场化替代)"),
    "goods_price": ("macro_china_qyspjg", {}, 13, True, "企业商品价格指数(月频, 含农产品/矿产品分项)"),
}
_MESO_SOURCES = {k: v[4] for k, v in _MESO_TABLE.items()}


def get_meso_indicator(indicator: str) -> dict[str, Any]:
    """中观行业景气数据: indicator ∈ car/hog/commodity/battery_solar(硅锂现货)/
    shipping(BDI)/electricity(用电量)/logistics/house(70城房价)/semiconductor(费半)/goods_price。

    行业景气先行指标, 按所问行业选取; 水泥/挖掘机/白酒价/30城成交无公开源(实测确认)。
    """
    ind = (indicator or "").strip().lower()
    if ind not in _MESO_TABLE:
        return error_response(
            code="INVALID_PARAM",
            message=f"indicator 必须是 {list(_MESO_TABLE)} 之一; 水泥/挖掘机/白酒价/30城成交无公开数据源(实测确认)",
        )
    cache_key = _cache.make_key("akshare", "meso", ind)
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="akshare", cache_hit=True)
    try:
        import akshare as ak

        fn_name, kwargs, tail_n, newest_first, _desc = _MESO_TABLE[ind]
        if ind == "battery_solar":
            # 该接口默认仅查当天, 非交易日返回空——改查近14天区间(2026-09-05 周六实测暴露)
            from datetime import datetime as _dt, timedelta as _td

            kwargs = {**kwargs,
                      "start_day": (_dt.now() - _td(days=14)).strftime("%Y%m%d"),
                      "end_day": _dt.now().strftime("%Y%m%d")}
        df = getattr(ak, fn_name)(**kwargs)
        rows = (df.head(tail_n) if newest_first else df.tail(tail_n)).to_dict("records")
        # 统一序列化(值转 str 防 numpy 类型泄漏)
        series = [{str(k): (None if v != v else str(v)) for k, v in r.items()} for r in rows]
        data = {
            "indicator": ind,
            "source_desc": _MESO_SOURCES[ind],
            "series": series,
            "note": "原始口径透传, 字段名与单位见各来源; 用于行业景气趋势判断",
        }
        if series:  # 空序列不缓存(避免瞬时空结果被钉一天)
            _cache.set(cache_key, data, ttl_category="daily")
            return ok_response(data=data, source="akshare")
        return error_response(code="DATA_NOT_FOUND",
                              message=f"{ind} 本次未取得数据(上游返回空), 未缓存可稍后重试", source="akshare")
    except Exception as e:
        return handle_tool_error(e)


_SINA_FIELDS = {
    "int_dji": ("道琼斯", 1, 3),
    "int_nasdaq": ("纳斯达克", 1, 3),
    "int_sp500": ("标普500", 1, 3),
    "gb_nvda": ("英伟达(AI映射锚)", 1, 2),
    "fx_susdcnh": ("离岸人民币", 2, None),
    "DINIW": ("美元指数", 1, None),
}


def get_global_context() -> dict[str, Any]:
    """外部环境快照: 美三大指数/英伟达/离岸人民币/美元指数(实时) + 美债10Y/30Y(T+1)。

    A 股映射链与流动性环境判断: 美股科技(尤其英伟达)→A股算力链情绪;
    美元与人民币汇率→外资流向环境; 美债收益率→全球风险资产定价锚。
    """
    cache_key = _cache.make_key("sina", "global_ctx")
    cached = _cache.get(cache_key)
    if cached is not None:
        return ok_response(data=cached, source="sina+akshare", cache_hit=True)
    quotes: dict[str, Any] = {}
    try:
        url = "https://hq.sinajs.cn/list=" + ",".join(_SINA_FIELDS)
        req = urllib.request.Request(
            url,
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
        )
        with _opener.open(req, timeout=15) as resp:
            body = resp.read().decode("gbk", "ignore")
        for key, (label, val_idx, chg_idx) in _SINA_FIELDS.items():
            m = re.search(rf'hq_str_{key}="([^"]*)"', body)
            if not m or not m.group(1):
                quotes[label] = None  # 缺失显式标注, 不静默跳过
                continue
            parts = m.group(1).split(",")
            try:
                item = {"value": float(parts[val_idx])}
                if chg_idx is not None:
                    item["change_pct"] = float(parts[chg_idx])
                quotes[label] = item
            except (ValueError, IndexError):
                quotes[label] = None
    except Exception as e:
        return handle_tool_error(e)
    us_bond = None
    try:
        import akshare as ak

        bond = ak.bond_zh_us_rate(start_date="20260801").dropna(
            subset=["美国国债收益率10年"]
        )
        if not bond.empty:
            last = bond.iloc[-1]
            us_bond = {
                "date": str(last["日期"]),
                "us10y": float(last["美国国债收益率10年"]),
                "us30y": float(last.get("美国国债收益率30年"))
                if last.get("美国国债收益率30年") == last.get("美国国债收益率30年")
                else None,
            }
    except Exception:
        us_bond = None  # 美债缺失不拖垮整体, 字段留 None 显式可见
    data = {
        "quotes": quotes,
        "us_treasury": us_bond,
        "note": "美股指数/汇率为新浪实时; 美债为 T+1 日度(us_treasury=None 表示当日未取得); "
        "change_pct 为涨跌幅(%); 仅作外部环境参考, 不构成 A 股方向判断",
    }
    _cache.set(cache_key, data, ttl_category="realtime")
    return ok_response(data=data, source="sina+akshare")
