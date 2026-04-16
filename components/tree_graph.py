"""Interactive force-directed graph of the RAG context tree."""

from datetime import datetime, timezone
from typing import Optional

import streamlit as st
from streamlit_agraph import Config, Edge, Node, agraph


# -- colour constants --------------------------------------------------------

COLOR_THEME = "#3b82f6"   # blue
COLOR_MACRO = "#f59e0b"   # amber
COLOR_FRESH = "#22c55e"   # green  (updated <= 24h ago)
COLOR_WARM = "#eab308"    # yellow (2-7d)
COLOR_STALE = "#ef4444"   # red    (7d+)
COLOR_DEFAULT = "#6b7280" # grey   (no timestamp)
COLOR_EDGE = "#4b5563"
COLOR_CROSS = "#6366f1"   # indigo for cross-links


def _ticker_color(updated_at: Optional[str]) -> str:
    """Return a hex colour based on how fresh the symbol data is."""
    if not updated_at:
        return COLOR_DEFAULT
    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        if age.days <= 1:
            return COLOR_FRESH
        if age.days <= 7:
            return COLOR_WARM
        return COLOR_STALE
    except (ValueError, TypeError):
        return COLOR_DEFAULT


def _freshness_bucket(updated_at: Optional[str]) -> str:
    if not updated_at:
        return "stale"
    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        if age.days <= 1:
            return "fresh"
        if age.days <= 7:
            return "warm"
        return "stale"
    except (ValueError, TypeError):
        return "stale"


def _node_size(keywords: list) -> int:
    """Scale node size by keyword count (clamped 15-50)."""
    base = 15
    extra = min(len(keywords) * 0.5, 35)
    return int(base + extra)


def render_tree_graph(
    tree: dict,
    filter_mode: str = "all",
    search_query: str = "",
) -> Optional[str]:
    """Build and render an agraph from the tree dict.

    Parameters
    ----------
    tree : dict
        The full tree snapshot (symbols, themes, macros, relations).
    filter_mode : str
        One of "all", "themes", "macros", "stale".
    search_query : str
        Case-insensitive substring to highlight/filter nodes.

    Returns
    -------
    str or None
        The node ID selected by the user, or None.
    """
    symbols = tree.get("symbols", {})
    themes = tree.get("themes", {})
    macros = tree.get("macros", {})
    relations = tree.get("relations", {})
    sym_to_themes = relations.get("symbol_to_themes", {})
    sym_to_macros = relations.get("symbol_to_macros", {})

    nodes: list[Node] = []
    edges: list[Edge] = []
    search_lower = search_query.lower().strip()

    # Track which nodes pass the filter so we can prune edges
    visible_ids: set[str] = set()

    # -- Theme nodes ---------------------------------------------------------
    if filter_mode in ("all", "themes"):
        for tid, tdata in themes.items():
            label = tid.replace("_", " ").title()
            if search_lower and search_lower not in label.lower() and search_lower not in tid.lower():
                continue
            nid = f"theme_{tid}"
            kw = tdata.get("keywords", [])
            nodes.append(Node(
                id=nid,
                label=label,
                size=_node_size(kw),
                color=COLOR_THEME,
                shape="diamond",
            ))
            visible_ids.add(nid)

    # -- Macro nodes ---------------------------------------------------------
    if filter_mode in ("all", "macros"):
        for mid, mdata in macros.items():
            label = mid.replace("_", " ").title()
            if search_lower and search_lower not in label.lower() and search_lower not in mid.lower():
                continue
            nid = f"macro_{mid}"
            kw = mdata.get("keywords", [])
            nodes.append(Node(
                id=nid,
                label=label,
                size=_node_size(kw),
                color=COLOR_MACRO,
                shape="diamond",
            ))
            visible_ids.add(nid)

    # -- Symbol (ticker) nodes -----------------------------------------------
    for sym, sdata in symbols.items():
        updated_at = sdata.get("updated_at")
        freshness = _freshness_bucket(updated_at)

        if filter_mode == "stale" and freshness != "stale":
            continue
        if filter_mode == "themes" or filter_mode == "macros":
            # Only include symbols linked to visible themes/macros
            linked_themes = sym_to_themes.get(sym, [])
            linked_macros = sym_to_macros.get(sym, [])
            has_link = False
            if filter_mode == "themes":
                has_link = any(f"theme_{t}" in visible_ids for t in linked_themes)
            else:
                has_link = any(f"macro_{m}" in visible_ids for m in linked_macros)
            if not has_link and not search_lower:
                continue

        if search_lower and search_lower not in sym.lower():
            # Also check keywords
            kw_match = any(search_lower in k.lower() for k in sdata.get("keywords", []))
            if not kw_match:
                continue

        nid = f"sym_{sym}"
        kw = sdata.get("keywords", [])
        nodes.append(Node(
            id=nid,
            label=sym,
            size=_node_size(kw),
            color=_ticker_color(updated_at),
            shape="dot",
        ))
        visible_ids.add(nid)

    # -- Edges: theme/macro -> symbol (solid) --------------------------------
    for sym, theme_list in sym_to_themes.items():
        sym_nid = f"sym_{sym}"
        if sym_nid not in visible_ids:
            continue
        for tid in theme_list:
            theme_nid = f"theme_{tid}"
            if theme_nid in visible_ids:
                edges.append(Edge(
                    source=theme_nid,
                    target=sym_nid,
                    color=COLOR_EDGE,
                    width=1,
                ))

    for sym, macro_list in sym_to_macros.items():
        sym_nid = f"sym_{sym}"
        if sym_nid not in visible_ids:
            continue
        for mid in macro_list:
            macro_nid = f"macro_{mid}"
            if macro_nid in visible_ids:
                edges.append(Edge(
                    source=macro_nid,
                    target=sym_nid,
                    color=COLOR_EDGE,
                    width=1,
                ))

    # -- Edges: cross-links between themes/macros (dashed) -------------------
    # If a symbol links to both a theme and a macro that are visible,
    # draw a dashed cross-link between them.
    for sym in symbols:
        linked_themes = sym_to_themes.get(sym, [])
        linked_macros = sym_to_macros.get(sym, [])
        for tid in linked_themes:
            for mid in linked_macros:
                t_nid = f"theme_{tid}"
                m_nid = f"macro_{mid}"
                if t_nid in visible_ids and m_nid in visible_ids:
                    edges.append(Edge(
                        source=t_nid,
                        target=m_nid,
                        color=COLOR_CROSS,
                        width=1,
                        dashes=True,
                    ))

    if not nodes:
        st.info("No nodes match the current filter / search.")
        return None

    config = Config(
        width="100%",
        height=600,
        directed=False,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor=COLOR_THEME,
        collapsible=False,
        node={"labelProperty": "label"},
        link={"highlightColor": COLOR_CROSS},
    )

    selected = agraph(nodes=nodes, edges=edges, config=config)
    return selected
