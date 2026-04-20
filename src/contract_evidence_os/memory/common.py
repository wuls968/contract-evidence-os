"""Shared helpers for AMOS memory services."""

from __future__ import annotations

import json
import re


def tokenize_memory_text(value: str) -> set[str]:
    lowered = value.lower()
    chunks = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", lowered)
    tokens = {chunk for chunk in chunks if chunk.strip()}
    for chunk in list(tokens):
        if len(chunk) > 4:
            tokens.add(chunk[:4])
            tokens.add(chunk[-4:])
    return tokens


def safe_memory_text(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        try:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(payload)
    return str(payload)


def truncate_memory_text(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else f"{text[: limit - 3]}..."
