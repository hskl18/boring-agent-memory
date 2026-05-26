from __future__ import annotations

import re


def plain_snippet(content: str, query: str, max_chars: int = 220) -> str:
    if not content:
        return ""

    terms = [t for t in re.findall(r"[\w\u4e00-\u9fff]+", query, flags=re.UNICODE) if t]
    lower = content.lower()
    start = 0
    for term in terms:
        idx = lower.find(term.lower())
        if idx >= 0:
            start = max(0, idx - max_chars // 3)
            break

    snippet = content[start : start + max_chars].replace("\n", " ")
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if start > 0:
        snippet = "..." + snippet
    if start + max_chars < len(content):
        snippet += "..."
    return snippet

