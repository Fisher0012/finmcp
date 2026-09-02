"""投资者互动问答 tool: get_investor_qa

自 workbench routers/finmcp.py 下沉（SPEC F3 §3.3）。
akshare 为 optional extras; 未安装返回 NOT_SUPPORTED 而非 ImportError。

失败语义修正（SPEC §3.3 已裁定）: 上证 e 互动接口失败必须显式失败
（strict 契约 ok:false / 非 strict ok:true + empty_reason=unknown），
禁止原实现的 `ok:true + note="上证e互动暂不可用"` 伪装成正常空结果。
"""

from typing import Any

from finmcp_common.responses import (
    EMPTY_CONFIRMED_ABSENT,
    EMPTY_UNKNOWN,
    error_response,
    ok_response,
    strict_contract,
)

_QA_COLUMNS = ["提问者", "提问者编号", "提问内容", "提问时间", "回答内容", "回答时间", "问题"]


def get_investor_qa(stock_code: str, limit: int = 15) -> dict[str, Any]:
    """投资者互动问答 (akshare 深交所互动易/上证 e 互动)。

    市场关注当下信号: 辟谣/确认订单等一手互动信息来源。
    深市走互动易(stock_irm_cninfo), 沪市走上证 e 互动(stock_sns_sseinfo)。

    Args:
        stock_code: 股票代码（如 000001.SZ）
        limit: 返回条数上限, 默认 15
    """
    if not stock_code or not stock_code.strip():
        return error_response(code="INVALID_PARAM", message="stock_code 不能为空")
    try:
        import akshare as ak
    except ImportError:
        return error_response(
            code="NOT_SUPPORTED",
            message="get_investor_qa 需要 akshare, 请安装: pip install 'finmcp-a-stock-data[akshare]'",
            source="akshare",
        )
    try:
        code_simple = stock_code.split(".")[0]
        # 深市互动易(深交所), 沪市 e 互动
        if stock_code.endswith(".SZ"):
            df = ak.stock_irm_cninfo(symbol=code_simple)
            qa_source = "akshare_irm_cninfo"
        else:
            try:
                df = ak.stock_sns_sseinfo(symbol=code_simple)
                qa_source = "akshare_sns_sseinfo"
            except Exception as e:
                # 上证 e 互动失败 = 未知, 不得伪装成"无问答"（SPEC F1/F3）
                attempts = [{"source": "akshare_sns_sseinfo", "outcome": "error", "detail": str(e)[:200]}]
                if strict_contract():
                    return error_response(
                        code="UPSTREAM_ERROR",
                        message=f"上证 e 互动接口失败: {str(e)[:200]}",
                        hint="该接口稳定性差, 稍后重试",
                        source="akshare",
                        attempts=attempts,
                    )
                return ok_response(
                    data={"qa": []},
                    source="akshare",
                    empty_reason=EMPTY_UNKNOWN,
                    attempts=attempts,
                    note="上证e互动暂不可用（失败非确认无问答）",
                )
        if df is None or df.empty:
            return ok_response(
                data={"qa": [], "note": "近期无投资者问答"},
                source=qa_source,
                empty_reason=EMPTY_CONFIRMED_ABSENT,
            )
        # 取最近 limit 条
        df = df.head(limit).fillna("")
        rows = []
        for _, r in df.iterrows():
            row = {}
            for col in _QA_COLUMNS:
                if col in df.columns:
                    v = str(r.get(col, ""))
                    if v and v != "nan":
                        row[col] = v[:300]
            if row:
                rows.append(row)
        return ok_response(data={"qa": rows[:limit]}, source=qa_source)
    except Exception as e:
        return error_response(
            code="UPSTREAM_ERROR",
            message=f"投资者问答获取失败: {str(e)[:200]}",
            source="akshare",
        )
