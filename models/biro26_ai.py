"""Biro26 AI helper — draft source descriptions and suggest column mappings.

Wraps ai_helper.ask_llm_via_selenium (browser LLM). Any failure/timeout/absence
falls back to a deterministic name-similarity heuristic so the wizard always works.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

try:
    from ai_helper import ask_llm_via_selenium, is_ai_available
except Exception:  # ai_helper optional
    ask_llm_via_selenium = None
    def is_ai_available() -> bool:  # type: ignore
        return False

# target g_col_* params that bind to a SOURCE column (constants handled elsewhere)
_TARGET_PARAMS = ["col_key", "col_articol", "col_denumire",
                  "col_retail", "col_angro", "col_ionline", "col_brand"]

# heuristic keyword hints per target param (first match wins)
_HINTS = {
    "col_key":      ["cod_univers", "cod_un", "key", "guid", "id"],
    "col_articol":  ["articol", "artic", "sku", "mpn", "cod", "code", "art"],
    "col_denumire": ["denumire", "denum", "name", "nume", "title", "titlu"],
    "col_retail":   ["retail", "pret", "price", "raft"],
    "col_angro":    ["angro", "whole", "opt"],
    "col_ionline":  ["ionline", "online", "web", "internet"],
    "col_brand":    ["brand", "marca", "marka", "producator"],
}


def is_available() -> bool:
    try:
        return bool(is_ai_available())
    except Exception:
        return False


def heuristic_mapping(columns: List[str]) -> Dict[str, str]:
    low = {c.lower(): c for c in columns}
    used = set()
    out: Dict[str, str] = {}
    for param, hints in _HINTS.items():
        for h in hints:
            hit = next((orig for lc, orig in low.items()
                        if h in lc and orig not in used), None)
            if hit:
                out[param] = hit
                used.add(hit)
                break
    return out


def extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _ask(prompt: str, timeout: int = 40) -> Optional[str]:
    if not (is_available() and ask_llm_via_selenium):
        return None
    try:
        return ask_llm_via_selenium(prompt, timeout=timeout)
    except Exception:
        return None


def draft_source_md(name: str, columns: List[str], samples: List[List[Any]]) -> str:
    sample_md = "\n".join(
        "| " + " | ".join(str(v) for v in row[:len(columns)]) + " |"
        for row in samples[:5])
    header = "| " + " | ".join(columns) + " |\n| " + " | ".join("---" for _ in columns) + " |"
    table = header + ("\n" + sample_md if sample_md else "")
    prompt = (f"Source '{name}'. Columns: {columns}. Sample rows:\n{table}\n"
              "Write a short Markdown description: for each column give its likely "
              "business meaning and type. RO + EN only, no Russian. Output Markdown only.")
    ai = _ask(prompt)
    if ai:
        return ai
    return (f"# Source: {name}\n\n## Columns / Coloane\n\n{table}\n")


def suggest_mapping(columns: List[str], samples: List[List[Any]], md: str) -> Dict[str, Any]:
    if is_available():
        prompt = (
            "Map source columns to target import params. "
            f"Target params: {_TARGET_PARAMS}. Source columns: {columns}. "
            f"Description:\n{md[:1500]}\n"
            "Return ONLY a JSON object mapping each target param to the best source "
            "column name (or omit if none). Example: "
            '{"col_articol":"ART","col_denumire":"NAME"}')
        parsed = extract_json(_ask(prompt) or "")
        if parsed:
            mapping = {k: v for k, v in parsed.items()
                       if k in _TARGET_PARAMS and v in columns}
            if mapping:
                return {"success": True, "mapping": mapping, "source": "ai"}
    return {"success": True, "mapping": heuristic_mapping(columns), "source": "heuristic"}
