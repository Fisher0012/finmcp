"""Tushare Pro 数据源适配

需要环境变量 TUSHARE_TOKEN。
"""

from typing import Any

from finmcp_common.errors import AuthRequiredError

from .base import StockDataSource


class TushareSource(StockDataSource):
    """Tushare Pro 数据源（付费，需要 token）"""

    def __init__(self, token: str) -> None:
        if not token:
            raise AuthRequiredError(
                "Tushare 数据源需要 TUSHARE_TOKEN 环境变量，"
                "请到 https://tushare.pro 注册并获取 token"
            )
        # Stage 2 实现：import tushare as ts; self.pro = ts.pro_api(token)
        self._token = token

    @property
    def name(self) -> str:
        return "tushare"

    def search_stocks(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        raise NotImplementedError("Stage 2 实现")

    def get_basic_info(self, stock_code: str) -> dict[str, Any]:
        raise NotImplementedError("Stage 2 实现")

    def get_daily_price(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        period: str = "daily",
        adjust: str = "qfq",
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Stage 2 实现")

    def get_latest_quote(self, stock_code: str) -> dict[str, Any]:
        raise NotImplementedError("Stage 2 实现")

    def get_index_price(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
        period: str = "daily",
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Stage 2 实现")

    def get_industry_constituents(
        self,
        industry_code: str | None = None,
        industry_name: str | None = None,
        level: int = 1,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Stage 2 实现")

    def get_financial_indicator(
        self,
        stock_code: str,
        indicators: list[str] | None = None,
        years: int = 5,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Stage 2 实现")

    def get_financial_report(
        self,
        stock_code: str,
        report_period: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("Stage 2 实现")
