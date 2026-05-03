"""Shared geo tag normalization helpers."""

from __future__ import annotations

import json
import re


def normalize_geo_tags(value: object) -> list[str]:
    """Normalize custom geo input into unique lowercase tag names without #.

    Supports:
    - "#Lisboa, Sintra, Cascais"
    - "#Montijo#Setubal"
    - "Lisboa Sintra"
    """
    raw = str(value or "").strip()
    if not raw:
        return []

    tokens = re.split(r"[,\s]+|(?=#)", raw)
    out: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        clean = token.strip().lstrip("#").lower()
        if not clean:
            continue
        if clean not in seen:
            seen.add(clean)
            out.append(clean)

    return out


def normalize_geo_tags_json(value: object) -> str:
    return json.dumps(normalize_geo_tags(value), ensure_ascii=False)


def render_geo_tags(value: object) -> str:
    tags = normalize_geo_tags(value)
    return " ".join(f"#{tag}" for tag in tags)
