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

    Returns the nested data dict (symbols, themes, macros, relations,
    agent_state, stats).  Cached for 5 minutes.
    """
    dynamodb = _get_dynamodb()
    table = dynamodb.Table("freeport-rag-tree")
    resp = table.get_item(Key={"PK": "TREE", "SK": "latest"})
    item = resp.get("Item", {})
    return item.get("data", {})
