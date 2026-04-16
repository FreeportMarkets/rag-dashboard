"""Load the extracted prompt snapshot.

The snapshot is a checked-in JSON file produced by ``scripts/extract_prompts.py``.
Re-run that script whenever Twitter_scraper's ``config/prompts.py`` changes and
commit the updated snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st


_SNAPSHOT_PATH = Path(__file__).resolve().parent / "prompts_snapshot.json"


@st.cache_data(ttl=3600)
def load_prompts() -> dict:
    """Return the snapshot dict: {source_file, extracted_count, prompts: [...]}."""
    if not _SNAPSHOT_PATH.exists():
        return {"source_file": "", "extracted_count": 0, "prompts": []}
    return json.loads(_SNAPSHOT_PATH.read_text())


def group_by_agent(prompts: list[dict]) -> dict[str, list[dict]]:
    """Group prompt entries by their ``agent`` field, preserving registry order."""
    out: dict[str, list[dict]] = {}
    for p in prompts:
        out.setdefault(p.get("agent", "other"), []).append(p)
    return out
