"""Loader for RAG-enriched trade signals from DynamoDB."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
import streamlit as st


@st.cache_resource
def _get_dynamodb():
    """Return a cached boto3 DynamoDB resource using Streamlit secrets."""
    aws = st.secrets["aws"]
    return boto3.resource(
        "dynamodb",
        aws_access_key_id=aws["aws_access_key_id"],
        aws_secret_access_key=aws["aws_secret_access_key"],
        region_name=aws.get("region", "us-east-1"),
    )


def _decimal_to_float(obj):
    """Recursively convert Decimal values to float for JSON-friendliness."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(v) for v in obj]
    return obj


def _safe_json_parse(value):
    """Parse a JSON string; return None if parsing fails or value is empty."""
    if not value:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


@st.cache_data(ttl=60)
def load_recent_signals(hours: int = 24, limit: int = 50) -> list[dict]:
    """Query recent trade signals that have RAG context attached.

    Uses the flag-timestamp-index GSI (flag='Y', timestamp >= cutoff).
    Only returns items where context_match is non-empty.
    Parses context_match and causal_chain JSON into *_parsed fields.
    """
    dynamodb = _get_dynamodb()
    table = dynamodb.Table("freeport-tweets")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()

    from boto3.dynamodb.conditions import Key

    resp = table.query(
        IndexName="flag-timestamp-index",
        KeyConditionExpression=(
            Key("flag").eq("Y") & Key("timestamp").gte(cutoff_iso)
        ),
        ScanIndexForward=False,
        Limit=limit,
    )

    signals = []
    for item in resp.get("Items", []):
        item = _decimal_to_float(item)

        # Only keep items with non-empty context_match
        raw_cm = item.get("context_match")
        if not raw_cm:
            continue

        item["context_match_parsed"] = _safe_json_parse(raw_cm)
        item["causal_chain_parsed"] = _safe_json_parse(
            item.get("causal_chain")
        )
        signals.append(item)

    return signals


def load_signals_for_ticker(ticker: str, hours: int = 24) -> list[dict]:
    """Return recent signals filtered by ticker symbol."""
    all_signals = load_recent_signals(hours=hours)
    return [s for s in all_signals if s.get("ticker") == ticker]
