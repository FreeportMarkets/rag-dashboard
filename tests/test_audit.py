"""Tests for data/audit.py."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.audit import find_collisions, find_gaps  # noqa: E402


SAMPLE_TREE = {
    "symbols": {
        "NVDA": {"keywords": ["nvidia", "gpu", "ai chip", "blackwell"]},
        "AMD": {"keywords": ["amd", "gpu", "ai chip", "epyc"]},
        "AVGO": {"keywords": ["broadcom", "ai chip", "networking"]},
        "TCOM": {"keywords": ["china travel", "trip.com"]},
        "TSLA": {"keywords": ["tesla", "ev"]},
    },
    "relations": {
        "symbol_to_themes": {"NVDA": ["ai_infra"], "AMD": ["ai_infra"], "AVGO": ["ai_infra"]},
        "symbol_to_macros": {"TCOM": ["china_macro"]},
    },
}


def test_collision_gpu():
    out = find_collisions(SAMPLE_TREE, min_tickers=2)
    kws = {c["keyword"]: c for c in out}
    assert "gpu" in kws
    assert kws["gpu"]["count"] == 2
    assert kws["gpu"]["tickers"] == ["AMD", "NVDA"]


def test_collision_3way():
    out = find_collisions(SAMPLE_TREE, min_tickers=3)
    kws = [c["keyword"] for c in out]
    # "ai chip" appears in NVDA, AMD, AVGO → 3-way
    assert "ai chip" in kws
    assert "gpu" not in kws  # only 2 tickers, excluded at min=3


def test_collisions_empty():
    assert find_collisions({}, min_tickers=2) == []
    assert find_collisions({"symbols": {}}, min_tickers=2) == []


def test_collisions_case_insensitive():
    tree = {"symbols": {
        "A": {"keywords": ["GPU", "AI"]},
        "B": {"keywords": ["gpu", "ai"]},
    }}
    out = find_collisions(tree, min_tickers=2)
    assert len(out) == 2  # gpu + ai, both collide after lowercasing


def test_find_gaps_basic():
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    recent = [
        {"ticker": "NVDA", "timestamp": "2026-04-16T02:00:00Z"},
        {"ticker": "NVDA", "timestamp": "2026-04-15T10:00:00Z"},
        {"ticker": "TSLA", "timestamp": "2026-04-14T09:00:00Z"},
        # TCOM, AMD, AVGO have no recent tweets
    ]
    gaps = find_gaps(SAMPLE_TREE, recent, days=7, now=now)
    symbols_with_gaps = {g["symbol"] for g in gaps}
    assert "TCOM" in symbols_with_gaps
    assert "AMD" in symbols_with_gaps
    assert "AVGO" in symbols_with_gaps
    assert "NVDA" not in symbols_with_gaps
    assert "TSLA" not in symbols_with_gaps


def test_gaps_keyword_count_ordering():
    """Gaps with most keywords come first (biggest waste of coverage)."""
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    gaps = find_gaps(SAMPLE_TREE, [], days=7, now=now)
    # All 5 symbols have no recent tweets → all gaps
    # NVDA has 4 keywords, AMD has 4, AVGO has 3, TCOM has 2, TSLA has 2
    assert gaps[0]["keyword_count"] >= gaps[-1]["keyword_count"]
    assert gaps[0]["symbol"] in {"NVDA", "AMD"}  # tie at 4 keywords


def test_gaps_respects_time_window():
    """Tweets older than ``days`` don't count."""
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    old = [{"ticker": "NVDA", "timestamp": "2026-04-01T00:00:00Z"}]  # 15 days ago
    gaps = find_gaps(SAMPLE_TREE, old, days=7, now=now)
    symbols_with_gaps = {g["symbol"] for g in gaps}
    assert "NVDA" in symbols_with_gaps


def test_gaps_tolerates_bad_timestamps():
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)
    rows = [
        {"ticker": "NVDA", "timestamp": ""},       # bad
        {"ticker": "NVDA", "timestamp": "nope"},   # bad
        {"ticker": "AMD", "timestamp": "2026-04-16T00:00:00Z"},  # good
    ]
    gaps = find_gaps(SAMPLE_TREE, rows, days=7, now=now)
    symbols_with_gaps = {g["symbol"] for g in gaps}
    assert "NVDA" in symbols_with_gaps  # timestamps unparseable → counted as gap
    assert "AMD" not in symbols_with_gaps


if __name__ == "__main__":
    import traceback
    tests = [
        test_collision_gpu, test_collision_3way, test_collisions_empty,
        test_collisions_case_insensitive, test_find_gaps_basic,
        test_gaps_keyword_count_ordering, test_gaps_respects_time_window,
        test_gaps_tolerates_bad_timestamps,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
            traceback.print_exc()
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
