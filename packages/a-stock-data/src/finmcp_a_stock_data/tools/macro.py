"""宏观指标 tool: get_macro_indicator (SPEC F5)

接口存在性: 2026-09-02 带 token 实调验证 cn_gdp / cn_cpi / cn_pmi / shibor_lpr 均有真实返回。
字段口径: 全部为 tushare 官方字段名, 原值透传、不做单位换算; 字段含义已对 tushare 官方文档
逐一核实（cn_gdp doc_id=227 / cn_cpi doc_id=228 / cn_pmi doc_id=325 / shibor_lpr doc_id=151）。
cn_pmi 返回列为官方代码名（如 pmi010000），response 内附 field_glossary 给出已核实的含义映射。
"""

import math
from typing import Any

from finmcp_common.responses import EMPTY_CONFIRMED_ABSENT, error_response, ok_response

_SUPPORTED = ("gdp", "cpi", "pmi", "lpr")

# indicator → (tushare 接口名, 期标识列, 字段口径说明)
_INDICATOR_CONF: dict[str, tuple[str, str, str]] = {
    "gdp": (
        "cn_gdp",
        "quarter",
        "tushare cn_gdp 官方口径: gdp/pi/si/ti=累计值(亿元), *_yoy=同比增速(%); pi/si/ti=第一/二/三产业",
    ),
    "cpi": (
        "cn_cpi",
        "month",
        "tushare cn_cpi 官方口径: nt=全国/town=城市/cnt=农村; val=当月值, yoy=同比(%), mom=环比(%), accu=累计值",
    ),
    "pmi": (
        "cn_pmi",
        "month",
        "字段为 tushare cn_pmi 官方代码名, 已核实含义见 field_glossary; 未收录代码以 tushare 官方文档为准",
    ),
    "lpr": (
        "shibor_lpr",
        "date",
        "tushare shibor_lpr 官方口径: 1y=1年贷款利率(LPR), 5y=5年贷款利率(LPR)",
    ),
}

# cn_pmi 代码字段 → 含义（tushare 官方文档 doc_id=325, 2026-09-02 核实）
_PMI_FIELD_GLOSSARY: dict[str, str] = {
    "pmi010000": "制造业PMI",
    "pmi010100": "制造业PMI:企业规模/大型企业",
    "pmi010200": "制造业PMI:企业规模/中型企业",
    "pmi010300": "制造业PMI:企业规模/小型企业",
    "pmi010400": "制造业PMI:构成指数/生产指数",
    "pmi010401": "制造业PMI:构成指数/生产指数:大型企业",
    "pmi010402": "制造业PMI:构成指数/生产指数:中型企业",
    "pmi010403": "制造业PMI:构成指数/生产指数:小型企业",
    "pmi010500": "制造业PMI:构成指数/新订单指数",
    "pmi010501": "制造业PMI:构成指数/新订单指数:大型企业",
    "pmi010502": "制造业PMI:构成指数/新订单指数:中型企业",
    "pmi010503": "制造业PMI:构成指数/新订单指数:小型企业",
    "pmi010600": "制造业PMI:构成指数/供应商配送时间指数",
    "pmi010601": "制造业PMI:构成指数/供应商配送时间指数:大型企业",
    "pmi010602": "制造业PMI:构成指数/供应商配送时间指数:中型企业",
    "pmi010603": "制造业PMI:构成指数/供应商配送时间指数:小型企业",
    "pmi010700": "制造业PMI:构成指数/原材料库存指数",
    "pmi010701": "制造业PMI:构成指数/原材料库存指数:大型企业",
    "pmi010702": "制造业PMI:构成指数/原材料库存指数:中型企业",
    "pmi010703": "制造业PMI:构成指数/原材料库存指数:小型企业",
    "pmi010800": "制造业PMI:构成指数/从业人员指数",
    "pmi010801": "制造业PMI:构成指数/从业人员指数:大型企业",
    "pmi010802": "制造业PMI:构成指数/从业人员指数:中型企业",
    "pmi010803": "制造业PMI:构成指数/从业人员指数:小型企业",
    "pmi010900": "制造业PMI:其他/新出口订单",
    "pmi011000": "制造业PMI:其他/进口",
    "pmi011100": "制造业PMI:其他/采购量",
    "pmi011200": "制造业PMI:其他/主要原材料购进价格",
    "pmi011300": "制造业PMI:其他/出厂价格",
    "pmi011400": "制造业PMI:其他/产成品库存",
    "pmi011500": "制造业PMI:其他/在手订单",
    "pmi011600": "制造业PMI:其他/生产经营活动预期",
    "pmi011700": "制造业PMI:分行业/装备制造业",
    "pmi011800": "制造业PMI:分行业/高技术制造业",
    "pmi011900": "制造业PMI:分行业/基础原材料制造业",
    "pmi012000": "制造业PMI:分行业/消费品制造业",
    "pmi020100": "非制造业PMI:商务活动",
    "pmi020101": "非制造业PMI:商务活动:分行业/建筑业",
    "pmi020102": "非制造业PMI:商务活动:分行业/服务业",
    "pmi020200": "非制造业PMI:新订单指数",
    "pmi020201": "非制造业PMI:新订单指数:分行业/建筑业",
    "pmi020202": "非制造业PMI:新订单指数:分行业/服务业",
    "pmi020300": "非制造业PMI:投入品价格指数",
    "pmi020301": "非制造业PMI:投入品价格指数:分行业/建筑业",
    "pmi020302": "非制造业PMI:投入品价格指数:分行业/服务业",
    "pmi020400": "非制造业PMI:销售价格指数",
    "pmi020401": "非制造业PMI:销售价格指数:分行业/建筑业",
    "pmi020402": "非制造业PMI:销售价格指数:分行业/服务业",
    "pmi020500": "非制造业PMI:从业人员指数",
    "pmi020501": "非制造业PMI:从业人员指数:分行业/建筑业",
    "pmi020502": "非制造业PMI:从业人员指数:分行业/服务业",
    "pmi020600": "非制造业PMI:业务活动预期指数",
    "pmi020601": "非制造业PMI:业务活动预期指数:分行业/建筑业",
    "pmi020602": "非制造业PMI:业务活动预期指数:分行业/服务业",
    "pmi020700": "非制造业PMI:新出口订单",
    "pmi020800": "非制造业PMI:在手订单",
    "pmi020900": "非制造业PMI:存货",
    "pmi021000": "非制造业PMI:供应商配送时间",
    "pmi030000": "中国综合PMI产出指数",
}

_MAX_PERIODS = 120


def _num(v: Any) -> float | None:
    """数值清洗: NaN/None → None, 其余转 float 并保留 4 位"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 4)


def get_macro_indicator(indicator: str, periods: int = 12) -> dict[str, Any]:
    """宏观指标 (tushare 宏观接口): GDP / CPI / PMI / LPR 最近 N 期官方数据。

    字段为 tushare 官方口径原值透传（不换算）。GDP 按季度（quarter）、
    CPI/PMI 按月度（month）、LPR 按发布日（date）。

    Args:
        indicator: 指标类型, 支持 "gdp" / "cpi" / "pmi" / "lpr"
        periods: 返回最近期数, 默认 12, 最大 120
    """
    key = (indicator or "").strip().lower()
    if key not in _SUPPORTED:
        return error_response(
            code="INVALID_PARAM",
            message=f"不支持的 indicator: {indicator!r}, 支持: gdp / cpi / pmi / lpr",
        )
    if periods < 1:
        return error_response(code="INVALID_PARAM", message="periods 必须 >= 1")
    periods = min(periods, _MAX_PERIODS)

    api_name, period_col, note = _INDICATOR_CONF[key]
    try:
        import tushare as ts

        pro = ts.pro_api()
        df = getattr(pro, api_name)()
        if df is None or df.empty:
            return ok_response(
                data={"indicator": key, "periods": [], "note": f"tushare {api_name} 无数据"},
                source="tushare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        # 列名统一小写（实调 cn_pmi 返回大写代码列, 官方文档为小写）
        df.columns = [str(c).lower() for c in df.columns]
        # 期标识列: 配置列缺失时退化用首列, 保证每期都带期标识
        pcol = period_col if period_col in df.columns else str(df.columns[0])
        df = df.sort_values(pcol, ascending=False).head(periods)
        rows: list[dict[str, Any]] = []
        for _, r in df.iterrows():
            row: dict[str, Any] = {}
            for col in df.columns:
                row[col] = str(r[col]) if col == pcol else _num(r[col])
            rows.append(row)
        data: dict[str, Any] = {"indicator": key, "periods": rows, "note": note}
        if key == "pmi":
            present = {c for row in rows for c in row}
            data["field_glossary"] = {c: m for c, m in _PMI_FIELD_GLOSSARY.items() if c in present}
        return ok_response(data=data, source="tushare")
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"tushare {api_name} 调用失败: {str(e)[:200]}",
            source="tushare",
        )
