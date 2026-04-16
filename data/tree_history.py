"""Historical tree snapshot reader.

The merger agent writes two items per run:
    PK=TREE, SK=latest        — always overwritten
    PK=TREE, SK=YYYY-MM-DD    — one per UTC day

This module lists available daily snapshots and loads a specific one, flattening
to the same shape ``tree_loader.load_tree()`` returns so the dashboard can diff
two days with a single code path.
"""

from __future__ import annotations

import re

import boto3
import streamlit as st


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@st.cache_resource
def _get_dynamodb():
    aws = st.secrets["aws"]
    kwargs = {
        "aws_access_key_id": aws["aws_access_key_id"],
        "aws_secret_access_key": aws["aws_secret_access_key"],
        "region_name": aws.get("region", "us-east-1"),
    }
    if aws.get("aws_session_token"):
        kwargs["aws_session_token"] = aws["aws_session_token"]
    return boto3.resource("dynamodb", **kwargs)


def _flatten_snapshot(raw: dict) -> dict:
    """Flatten the merger_agent snapshot format into the dashboard's flat shape."""
    if not raw:
        return {}
    tree_inner = raw.get("tree", {}) or {}
    freshness = raw.get("freshness", {}) or {}
    return {
        "symbols": tree_inner.get("symbols", {}) or {},
        "themes": tree_inner.get("themes", {}) or {},
        "macros": tree_inner.get("macros", {}) or {},
        "relations": tree_inner.get("relations", {}) or {},
        "agent_state": raw.get("agent_state", {}) or {},
        "stats": {
            "total_symbols": len(tree_inner.get("symbols", {}) or {}),
            "total_keywords": raw.get("static_keyword_count", 0),
            "total_themes": len(tree_inner.get("themes", {}) or {}),
            "total_macros": len(tree_inner.get("macros", {}) or {}),
            "fresh_count": freshness.get("updated_within_1d", 0),
            "aging_count": freshness.get("updated_within_7d", 0),
            "stale_count": freshness.get("older_than_7d", 0),
        },
        "snapshot_at": raw.get("snapshot_at", ""),
    }


@st.cache_data(ttl=300)
def list_snapshot_dates() -> list[str]:
    """Return sorted (desc) list of available YYYY-MM-DD snapshots in freeport-rag-tree."""
    table = _get_dynamodb().Table("freeport-rag-tree")
    resp = table.query(
        KeyConditionExpression="PK = :pk",
        ExpressionAttributeValues={":pk": "TREE"},
        ProjectionExpression="SK",
    )
    dates = [item["SK"] for item in resp.get("Items", []) if _DATE_RE.match(item.get("SK", ""))]
    return sorted(dates, reverse=True)


@st.cache_data(ttl=300)
def load_snapshot(date: str) -> dict:
    """Load a snapshot by SK. ``date`` is either 'latest' or a YYYY-MM-DD string."""
    table = _get_dynamodb().Table("freeport-rag-tree")
    resp = table.get_item(Key={"PK": "TREE", "SK": date})
    return _flatten_snapshot(resp.get("Item", {}).get("data", {}))
