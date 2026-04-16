"""Context Tree tab — interactive graph + node detail + agent health."""

import streamlit as st

from components.agent_health import render_agent_health
from components.node_detail import render_node_detail
from components.tree_graph import render_tree_graph
from data.tree_loader import load_tree


def render():
    """Render the Context Tree tab."""
    tree = load_tree()

    if not tree:
        st.warning("No tree data found. Check that freeport-rag-tree has a snapshot.")
        return

    # Stats caption
    stats = tree.get("stats", {})
    total_sym = stats.get("total_symbols", len(tree.get("symbols", {})))
    total_kw = stats.get("total_keywords", 0)
    total_themes = len(tree.get("themes", {}))
    total_macros = len(tree.get("macros", {}))
    st.caption(
        f"{total_sym} symbols | {total_kw} keywords | "
        f"{total_themes} themes | {total_macros} macros"
    )

    # Filter + search controls
    col_filter, col_search = st.columns([1, 2])
    with col_filter:
        filter_mode = st.selectbox(
            "Filter",
            ["all", "themes", "macros", "stale"],
            index=0,
            key="tree_filter",
        )
    with col_search:
        search_query = st.text_input(
            "Search nodes",
            placeholder="ticker, keyword, or theme name...",
            key="tree_search",
        )

    # Main layout: 70% graph, 30% detail
    col_graph, col_detail = st.columns([7, 3])

    with col_graph:
        try:
            selected = render_tree_graph(tree, filter_mode=filter_mode, search_query=search_query)
        except Exception as e:
            st.error(f"Tree render error: {e}")
            selected = None

    with col_detail:
        render_node_detail(selected, tree)

    # Agent health at bottom
    render_agent_health(tree)
