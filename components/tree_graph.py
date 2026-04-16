"""Interactive treemap of the RAG context tree using Plotly.

Hierarchy: Root → Theme/Macro → Ticker
Colored by freshness (green/yellow/red).
Click a sector to drill in, click to select a node for the detail panel.
"""

from datetime import datetime, timezone
from typing import Optional

import plotly.graph_objects as go
import streamlit as st


COLOR_FRESH = "#22c55e"
COLOR_WARM = "#eab308"
COLOR_STALE = "#ef4444"
COLOR_STATIC = "#6b7280"
COLOR_THEME = "#3b82f6"
COLOR_MACRO = "#f59e0b"


def _freshness_color(updated_at: Optional[str]) -> str:
    if not updated_at:
        return COLOR_STATIC
    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        if age.days <= 1:
            return COLOR_FRESH
        if age.days <= 7:
            return COLOR_WARM
        return COLOR_STALE
    except (ValueError, TypeError):
        return COLOR_STATIC


def _freshness_label(updated_at: Optional[str]) -> str:
    if not updated_at:
        return "static"
    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        if age.days <= 1:
            return "fresh"
        if age.days <= 7:
            return "aging"
        return "stale"
    except (ValueError, TypeError):
        return "static"


def render_tree_graph(
    tree: dict,
    filter_mode: str = "all",
    search_query: str = "",
) -> Optional[str]:
    """Render a Plotly treemap and return the selected node ID."""

    symbols = tree.get("symbols", {})
    themes = tree.get("themes", {})
    macros = tree.get("macros", {})
    relations = tree.get("relations", {})
    sym_to_themes = relations.get("symbol_to_themes", {})
    sym_to_macros = relations.get("symbol_to_macros", {})

    search_lower = search_query.lower().strip()

    # Build parent mapping: ticker -> first theme or macro it belongs to
    ticker_parent: dict[str, str] = {}
    for sym in symbols:
        linked_themes = sym_to_themes.get(sym, [])
        linked_macros = sym_to_macros.get(sym, [])
        if linked_themes:
            ticker_parent[sym] = f"theme_{linked_themes[0]}"
        elif linked_macros:
            ticker_parent[sym] = f"macro_{linked_macros[0]}"
        else:
            ticker_parent[sym] = "Unlinked"

    # Build treemap data
    ids = []
    labels = []
    parents = []
    colors = []
    values = []
    hover_texts = []
    custom_ids = []  # our node IDs for selection

    # Root
    ids.append("RAG Tree")
    labels.append("RAG Context Tree")
    parents.append("")
    colors.append("#1a1a2e")
    values.append(0)
    hover_texts.append("")
    custom_ids.append("")

    # Theme branches
    visible_branches = set()
    for tid, tdata in themes.items():
        if filter_mode == "macros":
            continue
        branch_id = f"theme_{tid}"
        label = tid.replace("_", " ").title()
        if search_lower and search_lower not in label.lower() and search_lower not in tid.lower():
            # Still include if any child ticker matches
            child_tickers = [s for s, p in ticker_parent.items() if p == branch_id]
            if not any(search_lower in s.lower() for s in child_tickers):
                continue

        ids.append(branch_id)
        labels.append(f"🔷 {label}")
        parents.append("RAG Tree")
        colors.append(COLOR_THEME)
        values.append(0)
        kw_count = len(tdata.get("keywords", []))
        hover_texts.append(f"Theme: {tid}<br>Keywords: {kw_count}<br>{tdata.get('description', '')[:120]}")
        custom_ids.append(branch_id)
        visible_branches.add(branch_id)

    # Macro branches
    for mid, mdata in macros.items():
        if filter_mode == "themes":
            continue
        branch_id = f"macro_{mid}"
        label = mid.replace("_", " ").title()
        if search_lower and search_lower not in label.lower() and search_lower not in mid.lower():
            child_tickers = [s for s, p in ticker_parent.items() if p == branch_id]
            if not any(search_lower in s.lower() for s in child_tickers):
                continue

        ids.append(branch_id)
        labels.append(f"🔶 {label}")
        parents.append("RAG Tree")
        colors.append(COLOR_MACRO)
        values.append(0)
        kw_count = len(mdata.get("keywords", []))
        hover_texts.append(f"Macro: {mid}<br>Keywords: {kw_count}<br>{mdata.get('description', '')[:120]}")
        custom_ids.append(branch_id)
        visible_branches.add(branch_id)

    # Unlinked bucket (if needed)
    has_unlinked = any(p == "Unlinked" for p in ticker_parent.values())
    if has_unlinked and filter_mode == "all":
        ids.append("Unlinked")
        labels.append("Unlinked")
        parents.append("RAG Tree")
        colors.append("#374151")
        values.append(0)
        hover_texts.append("Tickers not linked to any theme or macro")
        custom_ids.append("")
        visible_branches.add("Unlinked")

    # Ticker leaves
    for sym, sdata in symbols.items():
        parent = ticker_parent.get(sym, "Unlinked")
        if parent not in visible_branches:
            continue

        updated_at = sdata.get("updated_at")
        freshness = _freshness_label(updated_at)

        if filter_mode == "stale" and freshness not in ("stale", "static"):
            continue
        if search_lower and search_lower not in sym.lower():
            kw_match = any(search_lower in k.lower() for k in sdata.get("keywords", []))
            if not kw_match:
                continue

        display_name = sym.replace("on", "").replace("0", "")
        kw_count = len(sdata.get("keywords", []))
        color = _freshness_color(updated_at)

        ids.append(f"sym_{sym}")
        labels.append(display_name)
        parents.append(parent)
        colors.append(color)
        values.append(max(kw_count, 1))  # size by keyword count
        desc = sdata.get("description", "")[:100]
        source = sdata.get("context_source", "static")
        hover_texts.append(
            f"<b>{sym}</b><br>"
            f"Source: {source} | Freshness: {freshness}<br>"
            f"Keywords: {kw_count}<br>"
            f"{desc}"
        )
        custom_ids.append(f"sym_{sym}")

    if len(ids) <= 1:
        st.info("No nodes match the current filter / search.")
        return None

    fig = go.Figure(go.Treemap(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        marker=dict(
            colors=colors,
            line=dict(width=1, color="#0e1117"),
        ),
        hovertext=hover_texts,
        hoverinfo="text",
        textinfo="label",
        textfont=dict(size=12, color="#fafafa"),
        branchvalues="total",
        maxdepth=2,
    ))

    fig.update_layout(
        margin=dict(l=0, r=0, t=30, b=0),
        height=620,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#fafafa"),
    )

    st.plotly_chart(fig, key="treemap")

    # Node selection via selectbox (more reliable than chart click events)
    all_node_ids = [cid for cid in custom_ids if cid]
    all_node_labels = []
    for cid in all_node_ids:
        if cid.startswith("sym_"):
            all_node_labels.append(f"📊 {cid[4:]}")
        elif cid.startswith("theme_"):
            all_node_labels.append(f"🔷 {cid[6:].replace('_', ' ').title()}")
        elif cid.startswith("macro_"):
            all_node_labels.append(f"🔶 {cid[6:].replace('_', ' ').title()}")

    if all_node_labels:
        selected_label = st.selectbox(
            "Select node for details",
            ["(none)"] + all_node_labels,
            key="node_select",
        )
        if selected_label != "(none)":
            idx = all_node_labels.index(selected_label)
            return all_node_ids[idx]

    return None
