from __future__ import annotations

from typing import Iterable


def extract_text_blocks(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, Iterable):
        return ""

    parts = []
    for block in content:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "".join(parts)
