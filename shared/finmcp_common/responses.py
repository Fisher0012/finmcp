"""统一响应构造器

所有 FinMCP tool 的返回值必须通过本模块构造，确保结构一致。

契约版本（SPEC F1 · 三态封套）:
- v1（默认）: 保持历史行为（上游全挂可能返回 ok:true + 空 data），但 meta 无条件
  携带 contract_version / empty_reason / attempts / partial_fields 等诊断字段，
  消费方可以在不改行为的前提下感知失败。
- v2（FINMCP_CONTRACT=v2）: 严格三态——上游全挂必须 ok:false；
  ok:true + 空 data 仅允许 empty_reason="confirmed_absent"（上游正常响应且明确无记录）。
行为切换只影响调用方看到的 ok 值，由各 tool 在全挂路径上通过 strict_contract() 分支。
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any

# 北京时间（UTC+8）
_CST = timezone(timedelta(hours=8))

# 语义化契约版本: v1 = 旧行为 + 诊断元数据; v2 = 严格三态
CONTRACT_VERSION_V1 = "1.1"
CONTRACT_VERSION_V2 = "2.0"

# empty_reason 枚举
EMPTY_CONFIRMED_ABSENT = "confirmed_absent"  # 上游正常响应且明确无记录（唯一允许说"没有"的状态）
EMPTY_UNKNOWN = "unknown"  # 空但无法排除上游故障，产品侧必须按"未取到"处理


def contract_mode() -> str:
    """当前契约模式: 'v1'（默认, 旧行为）或 'v2'（严格三态）"""
    return "v2" if os.getenv("FINMCP_CONTRACT", "v1").strip().lower() == "v2" else "v1"


def strict_contract() -> bool:
    """是否启用严格三态行为（全挂 → ok:false）"""
    return contract_mode() == "v2"


def _contract_version() -> str:
    return CONTRACT_VERSION_V2 if strict_contract() else CONTRACT_VERSION_V1


def _now_cst() -> str:
    """返回当前北京时间的 ISO 8601 字符串"""
    return datetime.now(_CST).isoformat(timespec="seconds")


def ok_response(
    data: Any,
    source: str,
    cache_hit: bool = False,
    note: str | None = None,
    empty_reason: str | None = None,
    attempts: list[dict[str, Any]] | None = None,
    partial_fields: list[str] | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """构造成功响应

    Args:
        data: 实际数据（dict 或 list）
        source: 数据源标识（如 "akshare", "tushare"）
        cache_hit: 是否命中缓存
        note: 可选的补充说明
        empty_reason: data 为空时的语义——EMPTY_CONFIRMED_ABSENT（确认无记录）
            或 EMPTY_UNKNOWN（无法排除上游故障）。非空 data 传 None。
        attempts: 多级数据源瀑布的逐级尝试留痕 [{source, outcome, detail?}]
        partial_fields: 附属字段富化失败时被置 None 的字段名列表
        as_of: 数据时点（缺省用当前时间）
    """
    meta: dict[str, Any] = {
        "source": source,
        "fetched_at": _now_cst(),
        "cache_hit": cache_hit,
        "contract_version": _contract_version(),
        "empty_reason": empty_reason,
    }
    if note is not None:
        meta["note"] = note
    if attempts is not None:
        meta["attempts"] = attempts
    if partial_fields:
        meta["partial_fields"] = partial_fields
    if as_of is not None:
        meta["as_of"] = as_of

    return {
        "ok": True,
        "data": data,
        "meta": meta,
    }


def error_response(
    code: str,
    message: str,
    hint: str | None = None,
    source: str = "unknown",
    attempts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """构造失败响应

    Args:
        code: 机读错误码（如 INVALID_PARAM, DATA_NOT_FOUND, UPSTREAM_ERROR）
        message: 人读错误描述
        hint: LLM 可读的恢复建议
        source: 数据源标识
        attempts: 多级数据源瀑布的逐级尝试留痕
    """
    error: dict[str, str] = {
        "code": code,
        "message": message,
    }
    if hint is not None:
        error["hint"] = hint

    meta: dict[str, Any] = {
        "source": source,
        "fetched_at": _now_cst(),
        "contract_version": _contract_version(),
    }
    if attempts is not None:
        meta["attempts"] = attempts

    return {
        "ok": False,
        "error": error,
        "meta": meta,
    }
