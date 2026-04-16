"""Aggregate tweet signal rows into dashboard-ready summaries.

All rows in ``freeport-tweets`` have ``flag="Y"`` — that's the single display
marker. Both Latest and For You feeds show every row (Recommender re-ranks
but doesn't exclude). So "signals we put on the app today" ≡ rows in the
table for that day.

The loader is a thin DDB wrapper. The aggregator is a pure function — feed
it a list of row dicts and it returns the summary. Testable with fixtures.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any


def _as_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _hour_of(ts: str) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H")
    except (ValueError, TypeError):
        return None


def aggregate_flow(rows: list[dict], top_ticker_n: int = 30, top_handle_n: int = 20) -> dict:
    """Reduce a list of signal rows to a flow summary.

    Expected row fields (per monitor.py write_to_dynamodb):
        tweet_id, timestamp, handle, ticker, action, confidence,
        category, flag, media, likes, retweets, replies,
        novelty, is_catalyst   (post-instrumentation)
    """
    by_ticker_count: Counter = Counter()
    by_ticker_action: dict[str, Counter] = defaultdict(Counter)
    by_ticker_conf: dict[str, list[float]] = defaultdict(list)

    by_handle_count: Counter = Counter()
    by_handle_tickers: dict[str, Counter] = defaultdict(Counter)

    by_action: Counter = Counter()
    by_category: Counter = Counter()
    hourly: dict[str, Counter] = defaultdict(Counter)

    confidences: list[float] = []
    novelties: list[float] = []
    catalysts = 0
    with_media = 0
    engagement_total = 0

    for row in rows:
        ticker = (row.get("ticker") or "").strip() or "UNKNOWN"
        handle = (row.get("handle") or "").strip().lstrip("@") or "unknown"
        action = (row.get("action") or "").strip().upper() or "UNKNOWN"
        category = (row.get("category") or "").strip().lower() or "unknown"
        conf = _as_float(row.get("confidence"))
        novelty = _as_float(row.get("novelty"))
        hour = _hour_of(row.get("timestamp", ""))

        by_ticker_count[ticker] += 1
        by_ticker_action[ticker][action] += 1
        if conf:
            by_ticker_conf[ticker].append(conf)

        by_handle_count[handle] += 1
        by_handle_tickers[handle][ticker] += 1

        by_action[action] += 1
        by_category[category] += 1
        if hour is not None:
            hourly[hour][ticker] += 1

        if conf:
            confidences.append(conf)
        if novelty:
            novelties.append(novelty)
        if row.get("is_catalyst"):
            catalysts += 1
        if row.get("media"):
            with_media += 1
        engagement_total += int(_as_float(row.get("likes"))) + int(_as_float(row.get("retweets"))) + int(_as_float(row.get("replies")))

    # Top N tickers
    top_tickers = []
    for ticker, count in by_ticker_count.most_common(top_ticker_n):
        confs = by_ticker_conf.get(ticker, [])
        top_tickers.append({
            "ticker": ticker,
            "count": count,
            "actions": dict(by_ticker_action[ticker]),
            "avg_confidence": round(sum(confs) / len(confs), 3) if confs else 0.0,
        })

    # Top N handles
    top_handles = []
    for handle, count in by_handle_count.most_common(top_handle_n):
        tops = [t for t, _ in by_handle_tickers[handle].most_common(3)]
        top_handles.append({
            "handle": handle,
            "count": count,
            "top_tickers": tops,
        })

    # Hourly: flat list with top ticker that hour
    hourly_list = []
    for h in (f"{i:02d}" for i in range(24)):
        bucket = hourly.get(h, Counter())
        total = sum(bucket.values())
        top = bucket.most_common(1)[0][0] if total else None
        hourly_list.append({"hour": h, "count": total, "top_ticker": top})

    return {
        "total_signals": len(rows),
        "by_ticker": top_tickers,
        "by_handle": top_handles,
        "by_action": dict(by_action),
        "by_category": dict(by_category),
        "hourly": hourly_list,
        "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
        "avg_novelty": round(sum(novelties) / len(novelties), 3) if novelties else 0.0,
        "catalyst_count": catalysts,
        "with_media_count": with_media,
        "engagement_total": engagement_total,
    }


# ---------------------------------------------------------------------------
# DDB loader (thin I/O wrapper — not unit-tested; smoke-tested against real DDB)
# ---------------------------------------------------------------------------

def _get_table():
    import boto3
    import streamlit as st
    aws = st.secrets["aws"]
    kwargs = {
        "aws_access_key_id": aws["aws_access_key_id"],
        "aws_secret_access_key": aws["aws_secret_access_key"],
        "region_name": aws.get("region", "us-east-1"),
    }
    if aws.get("aws_session_token"):
        kwargs["aws_session_token"] = aws["aws_session_token"]
    return boto3.resource("dynamodb", **kwargs).Table("freeport-tweets")


def load_signals_for_date(date: str) -> list[dict]:
    """Fetch all flag=Y signals for a given UTC date (YYYY-MM-DD).

    Uses the ``flag-timestamp-index`` GSI: PK=flag, SK=timestamp.
    """
    from boto3.dynamodb.conditions import Key

    table = _get_table()
    start = f"{date}T00:00:00"
    end = f"{date}T23:59:59.999999"

    items: list[dict] = []
    kwargs = {
        "IndexName": "flag-timestamp-index",
        "KeyConditionExpression": Key("flag").eq("Y") & Key("timestamp").between(start, end),
    }
    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last
    return items
