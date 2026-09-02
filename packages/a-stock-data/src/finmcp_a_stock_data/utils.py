"""工具函数"""

import os

from finmcp_common.errors import AuthRequiredError
from finmcp_common.logging import get_logger

from .data_sources.base import StockDataSource

logger = get_logger(__name__)


def get_data_source() -> StockDataSource:
    """根据环境变量获取数据源实例

    当前仅支持 tushare（AkshareSource 全部方法未实现，不再假装可用作默认，
    见 SPEC F0 / F-R3 裁定）。无 TUSHARE_TOKEN 时直接报可读错误，而非
    返回一个调用即抛 NotImplementedError 的空壳。
    """
    source_name = os.getenv("FINMCP_DATA_SOURCE", "auto")
    tushare_token = os.getenv("TUSHARE_TOKEN", "")

    if source_name in ("tushare", "auto") and tushare_token:
        from .data_sources.tushare_src import TushareSource

        logger.info("使用数据源: tushare")
        return TushareSource(token=tushare_token)

    if source_name == "akshare":
        raise AuthRequiredError(
            "akshare 数据源尚未实现（AkshareSource 全部方法为 NotImplementedError），"
            "当前仅支持 tushare：请设置 TUSHARE_TOKEN 环境变量"
        )

    raise AuthRequiredError("当前仅支持 tushare 数据源：请设置 TUSHARE_TOKEN 环境变量（https://tushare.pro 注册获取）")
