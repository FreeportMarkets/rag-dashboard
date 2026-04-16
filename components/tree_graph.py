"""Interactive treemap of the RAG context tree using plotly.express.

Hierarchy: Sector (theme/macro) → Ticker
Colored by freshness. Click a sector to drill in.
Uses px.treemap (not go.Treemap which has rendering bugs).
"""

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st

COLOR_MAP = {
    "fresh": "#22c55e",
    "aging": "#eab308",
    "stale": "#ef4444",
    "static": "#64748b",
}


def _freshness(updated_at: Optional[str]) -> str:
    if not updated_at:
        return "static"
    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - ts).days
        if age <= 1:
            return "fresh"
        if age <= 7:
            return "aging"
        return "stale"
    except (ValueError, TypeError):
        return "static"


def render_tree_graph(
    tree: dict,
    filter_mode: str = "all",
    search_query: str = "",
) -> Optional[str]:
    """Render a px.treemap and return selected node ID via selectbox."""

    symbols = tree.get("symbols", {})
    themes = tree.get("themes", {})
    macros = tree.get("macros", {})
    relations = tree.get("relations", {})
    s2t = relations.get("symbol_to_themes", {})
    s2m = relations.get("symbol_to_macros", {})
    search_lower = search_query.lower().strip()

    rows = []
    now = datetime.now(timezone.utc)

    for sym, sdata in symbols.items():
        # Determine parent sector
        lt = s2t.get(sym, [])
        lm = s2m.get(sym, [])
        if lt:
            parent = lt[0].replace("_", " ").title()
            parent_type = "theme"
        elif lm:
            parent = lm[0].replace("_", " ").title()
            parent_type = "macro"
        else:
            parent = "Unlinked"
            parent_type = "none"

        # Apply filters
        if filter_mode == "themes" and parent_type != "theme":
            continue
        if filter_mode == "macros" and parent_type != "macro":
            continue

        freshness = _freshness(sdata.get("updated_at"))
        if filter_mode == "stale" and freshness not in ("stale", "static"):
            continue

        # Apply search
        if search_lower:
            searchable = f"{sym} {' '.join(sdata.get('keywords', []))} {parent}".lower()
            if search_lower not in searchable:
                continue

        kw_count = len(sdata.get("keywords", []))
        display = sym.replace("on", "").replace("0", "")

        rows.append({
            "sector": parent,
            "ticker": display,
            "keywords": max(kw_count, 1),
            "freshness": freshness,
            "sym_id": f"sym_{sym}",
        })

    if not rows:
        st.info("No nodes match the current filter / search.")
        return None

    df = pd.DataFrame(rows)

    fig = px.treemap(
        df,
        path=["sector", "ticker"],
        values="keywords",
        color="freshness",
        color_discrete_map=COLOR_MAP,
    )
    fig.update_layout(
        height=650,
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#fafafa", size=13),
        margin=dict(l=4, r=4, t=8, b=4),
        showlegend=True,
        legend=dict(
            title="Freshness",
            bgcolor="#1a1a2e",
            font=dict(color="#fafafa"),
        ),
    )
    fig.update_traces(
        textfont=dict(size=13, color="white"),
        marker=dict(line=dict(width=1, color="#1e293b")),
    )

    st.plotly_chart(fig, key="treemap")

    # Node selection via selectbox
    all_sym_ids = [r["sym_id"] for r in rows]
    all_labels = [f"{r['ticker']} ({r['sector']})" for r in rows]

    # Also add theme/macro branch nodes
    branch_ids = []
    branch_labels = []
    seen_sectors = set()
    for r in rows:
        if r["sector"] not in seen_sectors:
            seen_sectors.add(r["sector"])
            # Find the original theme/macro id
            sector_lower = r["sector"].lower().replace(" ", "_")
            if sector_lower in themes:
                branch_ids.append(f"theme_{sector_lower}")
                branch_labels.append(f"🔷 {r['sector']}")
            elif sector_lower in macros:
                branch_ids.append(f"macro_{sector_lower}")
                branch_labels.append(f"🔶 {r['sector']}")

    combined_ids = branch_ids + all_sym_ids
    combined_labels = branch_labels + [f"📊 {l}" for l in all_labels]

    if combined_labels:
        selected_label = st.selectbox(
            "Select node for details",
            ["(none)"] + combined_labels,
            key="node_select",
        )
        if selected_label != "(none)":
            idx = combined_labels.index(selected_label)
            return combined_ids[idx]

    return None
