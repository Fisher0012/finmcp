# -*- coding: utf-8 -*-
"""沪深300 最新年报批量入库（数据层 2.0 批次一, 一次性+可重跑）。

幂等: 已入库文档 doc_hash 去重返回 duplicate, 中断后重跑自动跳过。
失败不静默: 逐股记录 ingested/duplicate/not_found/error, 结尾输出失败清单。
用法: 服务器上 cd /opt/workbench && nohup python3 /opt/fin-knowledge/scripts/ingest_hs300.py >> logs/ingest_hs300.log 2>&1 &
"""

import json
import os
import time
import urllib.request

for line in open("/opt/workbench/.env"):
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
os.environ["FIN_KNOWLEDGE_DB"] = "/opt/workbench/data/knowledge.db"

from fin_knowledge.collectors.annual_report import ingest_annual_report  # noqa: E402


INDEX_CODE = (len(__import__("sys").argv) > 1 and __import__("sys").argv[1]) or "399300.SZ"


def hs300_codes() -> list[str]:
    """指数成分(默认沪深300, argv[1] 可传其他如 000905.SH 中证500): tushare 优先, 失败退东财。"""
    try:
        import tushare as ts

        pro = ts.pro_api()
        df = pro.index_weight(index_code=INDEX_CODE)
        codes = sorted(set(df["con_code"].tolist()))
        if len(codes) >= 250:
            return codes
    except Exception as e:
        print(f"tushare index_weight 失败: {e}, 退东财", flush=True)
    # 东财沪深300成分(BK0500), 国内 API 绕代理
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=500&po=1&np=1"
        "&fltt=2&invt=2&fid=f3&fs=b:BK0500&fields=f12,f13"
    )
    with opener.open(url, timeout=30) as resp:
        data = json.loads(resp.read())
    rows = data.get("data", {}).get("diff", []) or []
    return sorted(f"{r['f12']}.{'SH' if r['f13'] == 1 else 'SZ'}" for r in rows)


def _already_ingested() -> set[str]:
    """库内已有年报的股票集合——重跑时跳过, 避免重复下载大 PDF(去重哈希在下载后才判定)。"""
    import sqlite3

    conn = sqlite3.connect(os.environ["FIN_KNOWLEDGE_DB"])
    try:
        rows = conn.execute(
            "SELECT DISTINCT stock_code FROM documents WHERE doc_type='annual_report'"
        ).fetchall()
        return {r[0] for r in rows if r[0]}
    finally:
        conn.close()


def main():
    codes = hs300_codes()
    done = _already_ingested()
    print(f"成分股 {len(codes)} 只, 库内已有 {len(done)} 只, 开始入库", flush=True)
    tally: dict[str, list[str]] = {}
    for i, code in enumerate(codes, 1):
        if code in done:
            tally.setdefault("skipped", []).append(code)
            continue
        try:
            r = ingest_annual_report(code)
            status = r.get("status", "error")
        except Exception as e:
            status = "error"
            print(f"[{i}/{len(codes)}] {code} 异常: {type(e).__name__} {str(e)[:120]}", flush=True)
        tally.setdefault(status, []).append(code)
        if status == "ingested":
            print(f"[{i}/{len(codes)}] {code} 入库 {r.get('chunks')} 块 《{r.get('title')}》", flush=True)
        time.sleep(2)
    print("==== 汇总 ====", flush=True)
    for status, lst in tally.items():
        print(f"{status}: {len(lst)}", flush=True)
    for status in ("not_found", "error", "empty"):
        if tally.get(status):
            print(f"{status} 清单: {tally[status]}", flush=True)


if __name__ == "__main__":
    main()
