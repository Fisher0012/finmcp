"""结构分块: 按章节标题切分, 段落聚合到目标块大小。

中文按字符估 token(≈1:1), 目标块 800 字, 上限 1600 字（<8192 token 硬限有充分余量）。
每块携带最近的章节标题作为 section 锚（检索结果可标注出处章节）。
"""

import re

TARGET_CHARS = 800
MAX_CHARS = 1600

# 章节标题: "第X节/一、/1.1/（一）" 等财报与研报常见层级行
_HEADING_RE = re.compile(
    r"^\s*(?:第[一二三四五六七八九十]+[节章]|[一二三四五六七八九十]+、|"
    r"\d{1,2}(?:\.\d{1,2}){0,2}[\s、.]|（[一二三四五六七八九十]+）|##+\s)"
)


def chunk_text(text: str) -> list[dict]:
    """→ [{seq, section, text}]; 空文本返回空表。"""
    if not text or not text.strip():
        return []
    chunks: list[dict] = []
    section = ""
    buf: list[str] = []
    buf_len = 0

    def flush():
        nonlocal buf, buf_len
        body = "\n".join(buf).strip()
        if body:
            chunks.append({"seq": len(chunks), "section": section, "text": body[:MAX_CHARS]})
        buf, buf_len = [], 0

    for rawline in text.splitlines():
        line = rawline.rstrip()
        if not line.strip():
            continue
        if _HEADING_RE.match(line) and len(line.strip()) < 60:
            flush()
            section = line.strip()[:80]
            buf.append(line.strip())
            buf_len = len(line)
            continue
        if buf_len + len(line) > TARGET_CHARS and buf_len > 0:
            flush()
            buf.append(section)  # 续块也带章节锚, 保证独立可读
            buf_len = len(section)
        buf.append(line)
        buf_len += len(line)
    flush()
    return chunks
