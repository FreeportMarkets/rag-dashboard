"""Context Tree tab — interactive tree + graph viz (with built-in detail pane) + agent health."""

import streamlit as st

from components.agent_health import render_agent_health
from components.tree_graph import render_tree_graph
from data.tree_loader import load_tree


def render():
    """Render the Context Tree tab."""
    tree = load_tree()

    if not tree:
        st.warning("No tree data found. Check that freeport-rag-tree has a snapshot.")
        return

    render_tree_graph(tree)
    render_agent_health(tree)
