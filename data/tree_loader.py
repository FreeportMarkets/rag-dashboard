"""Loader for the RAG context tree from DynamoDB."""

import streamlit as st
import boto3


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


@st.cache_data(ttl=300)
def load_tree() -> dict:
    """Fetch the latest context tree snapshot from freeport-rag-tree.

    The snapshot stores the live context under a ``tree`` key.  This function
    flattens it so callers get ``{symbols, themes, macros, relations,
    agent_state, stats, snapshot_at}`` at the top level.
    """
    dynamodb = _get_dynamodb()
    table = dynamodb.Table("freeport-rag-tree")
    resp = table.get_item(Key={"PK": "TREE", "SK": "latest"})
    item = resp.get("Item", {})
    raw = item.get("data", {})
    if not raw:
        return {}

    # The merger agent writes: {tree: {symbols,themes,macros,relations,...}, agent_state, freshness, static_keyword_count, snapshot_at}
    # Dashboard expects: {symbols, themes, macros, relations, agent_state, stats, snapshot_at}
    tree_inner = raw.get("tree", {})
    freshness = raw.get("freshness", {})

    return {
        "symbols": tree_inner.get("symbols", {}),
        "themes": tree_inner.get("themes", {}),
        "macros": tree_inner.get("macros", {}),
        "relations": tree_inner.get("relations", {}),
        "agent_state": raw.get("agent_state", {}),
        "stats": {
            "total_symbols": len(tree_inner.get("symbols", {})),
            "total_keywords": raw.get("static_keyword_count", 0),
            "total_themes": len(tree_inner.get("themes", {})),
            "total_macros": len(tree_inner.get("macros", {})),
            "fresh_count": freshness.get("updated_within_1d", 0),
            "aging_count": freshness.get("updated_within_7d", 0),
            "stale_count": freshness.get("older_than_7d", 0),
        },
        "snapshot_at": raw.get("snapshot_at", ""),
    }
