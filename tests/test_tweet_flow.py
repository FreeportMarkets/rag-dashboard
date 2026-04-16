"""Tests for data/tweet_flow.aggregate_flow against hand-crafted fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.tweet_flow import aggregate_flow  # noqa: E402


FIXTURES = Path(__file__).parent / "fixtures"


def _signals() -> list[dict]:
    return json.loads((FIXTURES / "signals_sample.json").read_text())


def test_total_count():
    assert aggregate_flow(_signals())["total_signals"] == 10


def test_by_ticker_ranking():
    out = aggregate_flow(_signals())
    # NVDA appears 4x, AMD 2x, TLT 1x, SPY 1x, BTC 1x, ETH 1x
    tickers = [t["ticker"] for t in out["by_ticker"]]
    assert tickers[0] == "NVDA"
    assert out["by_ticker"][0]["count"] == 4
    assert out["by_ticker"][0]["actions"] == {"BUY": 3, "SELL": 1}
    # NVDA average confidence: (0.72 + 0.78 + 0.55 + 0.70) / 4 = 0.6875
    assert abs(out["by_ticker"][0]["avg_confidence"] - 0.688) < 0.01


def test_by_handle():
    out = aggregate_flow(_signals())
    handles = {h["handle"]: h for h in out["by_handle"]}
    assert handles["GammaTrader"]["count"] == 3
    assert handles["zerohedge"]["count"] == 3
    assert "NVDA" in handles["GammaTrader"]["top_tickers"]


def test_action_category_totals():
    out = aggregate_flow(_signals())
    assert out["by_action"] == {"BUY": 6, "SELL": 3, "HOLD": 1}
    assert out["by_category"] == {"wire": 5, "culture": 3, "macro": 2}


def test_hourly_bucketing():
    out = aggregate_flow(_signals())
    # 02:xx has 2 (both NVDA), 09:xx has 2, 14:xx has 2, 18:xx has 2, 20:xx has 1, 23:xx has 1
    hours_by_count = {h["hour"]: h["count"] for h in out["hourly"]}
    assert hours_by_count["02"] == 2
    assert hours_by_count["09"] == 2
    assert hours_by_count["14"] == 2
    assert hours_by_count["18"] == 2
    assert hours_by_count["20"] == 1
    assert hours_by_count["23"] == 1
    assert hours_by_count["00"] == 0
    # Top ticker @ 09 was NVDA (1) and AMD (1) — tie, but most_common returns first seen
    h09 = next(h for h in out["hourly"] if h["hour"] == "09")
    assert h09["top_ticker"] in {"NVDA", "AMD"}


def test_aggregates():
    out = aggregate_flow(_signals())
    assert out["catalyst_count"] == 3
    assert out["with_media_count"] == 2  # t3 (photo) + t7 (video)
    # Engagement = sum of likes + retweets + replies across all 10
    assert out["engagement_total"] > 0
    assert 0 < out["avg_confidence"] <= 1
    assert 0 < out["avg_novelty"] <= 1


def test_empty_input():
    out = aggregate_flow([])
    assert out["total_signals"] == 0
    assert out["by_ticker"] == []
    assert out["by_action"] == {}
    assert out["avg_confidence"] == 0.0
    # Hourly still has 24 buckets, all zero
    assert len(out["hourly"]) == 24
    assert all(h["count"] == 0 for h in out["hourly"])


if __name__ == "__main__":
    import traceback
    tests = [test_total_count, test_by_ticker_ranking, test_by_handle, test_action_category_totals, test_hourly_bucketing, test_aggregates, test_empty_input]
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
