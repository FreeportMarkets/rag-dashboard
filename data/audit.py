"""Tree-audit functions: keyword collisions + coverage gaps.

Pure functions on the tree dict + tweet rows. Feed fixtures, assert outputs.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone


def find_collisions(tree: dict, min_tickers: int = 3) -> list[dict]:
    """Return keywords that map to ``min_tickers`` or more different tickers.

    Potential false-positive risk: if "gpu" triggers NVDA + AMD + AVGO, a tweet
    about just Nvidia might over-pull AMD/AVGO context.
    """
    symbols = (tree or {}).get("symbols", {}) or {}
    kw_to_tickers: dict[str, set[str]] = defaultdict(set)
    for ticker, sym in symbols.items():
        for kw in sym.get("keywords", []) or []:
            kw_norm = str(kw).strip().lower()
            if kw_norm:
                kw_to_tickers[kw_norm].add(ticker)

    out = []
    for kw, tickers in kw_to_tickers.items():
        if len(tickers) >= min_tickers:
            out.append({
                "keyword": kw,
                "tickers": sorted(tickers),
                "count": len(tickers),
            })
    out.sort(key=lambda r: (-r["count"], r["keyword"]))
    return out


def find_gaps(tree: dict, recent_tweets: list[dict], days: int = 7, *, now: datetime | None = None) -> list[dict]:
    """Find tracked symbols with zero signals in the last ``days`` days.

    ``recent_tweets`` is a list of signal rows with at least ``ticker`` and
    ``timestamp`` fields. Only tweets newer than ``days`` ago are counted.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    symbols = (tree or {}).get("symbols", {}) or {}
    relations = (tree or {}).get("relations", {}) or {}
    s2t = relations.get("symbol_to_themes", {}) or {}
    s2m = relations.get("symbol_to_macros", {}) or {}

    recent_tickers: set[str] = set()
    for row in recent_tweets or []:
        ts = row.get("timestamp", "")
        try:
            row_dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if row_dt >= cutoff:
            t = (row.get("ticker") or "").strip()
            if t:
                recent_tickers.add(t)

    gaps = []
    for ticker, sym in symbols.items():
        if ticker in recent_tickers:
            continue
        gaps.append({
            "symbol": ticker,
            "keyword_count": len(sym.get("keywords", []) or []),
            "themes": s2t.get(ticker, []),
            "macros": s2m.get(ticker, []),
            "description": (sym.get("description") or "")[:120],
        })

    # Sort: highest keyword_count first (most wasteful coverage gaps), then alphabetical
    gaps.sort(key=lambda r: (-r["keyword_count"], r["symbol"]))
    return gaps
