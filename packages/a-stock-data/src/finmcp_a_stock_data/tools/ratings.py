"""券商观点与回购 tools: get_broker_ratings + get_buyback

自 workbench routers/finmcp.py 下沉（SPEC F3 §3.3）。akshare 为 optional extras。

get_broker_ratings 含第三方观点字段（评级/目标价）: 按 SPEC §1 硬边界,
底座原样透传并在 data 顶层标注 third_party_opinion=true, 过滤责任归产品合规层。
"""

from typing import Any

from finmcp_common.responses import EMPTY_CONFIRMED_ABSENT, error_response, ok_response

_RATING_COLUMNS = ["报告名称", "东财评级", "机构", "目标价", "日期", "近一月个股研报数"]
_BUYBACK_COLUMNS = [
    "最新公告日期",
    "已回购股份数量",
    "已回购金额",
    "已回购股份价格区间-下限",
    "已回购股份价格区间-上限",
    "实施进度",
]


def _akshare_not_supported(tool_name: str) -> dict[str, Any]:
    return error_response(
        code="NOT_SUPPORTED",
        message=f"{tool_name} 需要 akshare, 请安装: pip install 'finmcp-a-stock-data[akshare]'",
        source="akshare",
    )


def get_broker_ratings(stock_code: str, limit: int = 10) -> dict[str, Any]:
    """券商研报评级 + 目标价 (akshare 东财研报)。

    注意: 评级与目标价为第三方机构观点（data.third_party_opinion=true 标注）,
    原样透传, 是否向用户展示由产品层合规过滤决定。

    Args:
        stock_code: 股票代码（如 600519.SH）
        limit: 返回条数上限, 默认 10
    """
    if not stock_code or not stock_code.strip():
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    try:
        import akshare as ak
    except ImportError:
        return _akshare_not_supported("get_broker_ratings")
    try:
        code_simple = stock_code.split(".")[0]
        df = ak.stock_research_report_em(symbol=code_simple)
        if df is None or df.empty:
            return ok_response(
                data={"reports": [], "note": "无券商研报", "third_party_opinion": True},
                source="akshare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        df = df.head(limit).fillna("")
        rows = []
        for _, r in df.iterrows():
            row = {}
            for col in _RATING_COLUMNS:
                if col in df.columns:
                    v = str(r.get(col, ""))
                    if v and v != "nan":
                        row[col] = v[:120]
            if row:
                rows.append(row)
        return ok_response(
            data={"reports": rows[:limit], "third_party_opinion": True},
            source="akshare",
        )
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"券商研报获取失败: {str(e)[:200]}",
            source="akshare",
        )


def get_buyback(stock_code: str) -> dict[str, Any]:
    """公司回购 (akshare 东财回购)。回购=偏多催化。

    注意: akshare 此接口返回全市场数据, 本地按代码过滤。

    Args:
        stock_code: 股票代码（如 600519.SH）
    """
    if not stock_code or not stock_code.strip():
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    try:
        import akshare as ak
    except ImportError:
        return _akshare_not_supported("get_buyback")
    try:
        code_simple = stock_code.split(".")[0]
        df = ak.stock_repurchase_em()
        if df is None or df.empty:
            return ok_response(
                data={"buybacks": [], "note": "近期无回购"},
                source="akshare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        # 本地过滤
        df = df[df["股票代码"].astype(str) == code_simple].head(5).fillna("")
        if df.empty:
            return ok_response(
                data={"buybacks": [], "note": "公司近期无回购公告"},
                source="akshare",
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        rows = []
        for _, r in df.iterrows():
            row = {}
            for col in _BUYBACK_COLUMNS:
                if col in df.columns:
                    v = str(r.get(col, ""))
                    if v and v != "nan":
                        row[col] = v[:80]
            if row:
                rows.append(row)
        return ok_response(data={"buybacks": rows}, source="akshare")
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"回购数据获取失败: {str(e)[:200]}",
            source="akshare",
        )
