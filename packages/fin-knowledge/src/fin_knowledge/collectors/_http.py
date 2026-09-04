"""采集器共享 HTTP 层: 绕代理 + gzip 自动解压。

2026-09-04 生产事故类修复: 东财接口在服务器环境返回 gzip(本机未压缩),
json.loads 直接炸。按响应字节魔数(1f 8b)判断解压, 覆盖全部采集器,
不依赖 Content-Encoding 头(部分接口不规范)。
"""

import gzip
import urllib.request

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

_DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _maybe_gunzip(data: bytes) -> bytes:
    if data[:2] == b"\x1f\x8b":
        return gzip.decompress(data)
    return data


def get_bytes(url: str, headers: dict | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={**_DEFAULT_HEADERS, **(headers or {})})
    with _opener.open(req, timeout=timeout) as resp:
        return _maybe_gunzip(resp.read())


def post_bytes(url: str, data: bytes, headers: dict | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, data=data, headers={**_DEFAULT_HEADERS, **(headers or {})})
    with _opener.open(req, timeout=timeout) as resp:
        return _maybe_gunzip(resp.read())
