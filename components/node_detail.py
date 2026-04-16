"""Detail panel for a selected node in the context tree."""

from datetime import datetime, timezone
from typing import Optional

import streamlit as st

from data.signal_loader import load_signals_for_ticker


def _freshness_badge(updated_at: Optional[str]) -> str:
    """Return an HTML badge indicating data freshness."""
    if not updated_at:
        return '<span style="background:#ef4444;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.75rem;">STALE</span>'
    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        if age.days <= 1:
            return '<span style="background:#22c55e;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.75rem;">LIVE</span>'
        return '<span style="background:#eab308;color:#000;padding:2px 8px;border-radius:4px;font-size:0.75rem;">STATIC</span>'
    except (ValueError, TypeError):
        return '<span style="background:#ef4444;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.75rem;">STALE</span>'


def _render_keyword_tags(keywords: list[str]):
    """Render keywords as inline coloured tags."""
    if not keywords:
        return
    tags_html = " ".join(
        f'<span style="background:#1e293b;border:1px solid #334155;color:#94a3b8;'
        f'padding:2px 8px;border-radius:12px;font-size:0.75rem;margin:2px;">{kw}</span>'
        for kw in keywords[:30]
    )
    remaining = len(keywords) - 30
    if remaining > 0:
        tags_html += f' <span style="color:#64748b;font-size:0.75rem;">+{remaining} more</span>'
    st.markdown(tags_html, unsafe_allow_html=True)


def _render_symbol_detail(sym_id: str, tree: dict):
    """Render detail panel for a symbol node."""
    symbols = tree.get("symbols", {})
    relations = tree.get("relations", {})
    sym_data = symbols.get(sym_id, {})

    if not sym_data:
        st.warning(f"No data found for symbol `{sym_id}`")
        return

    # Header with freshness badge
    badge = _freshness_badge(sym_data.get("updated_at"))
    st.markdown(
        f"### {sym_id} {badge}",
        unsafe_allow_html=True,
    )

    # Description
    desc = sym_data.get("description", "")
    if desc:
        st.caption(desc)

    # Updated info
    updated_at = sym_data.get("updated_at", "unknown")
    updated_by = sym_data.get("updated_by", "unknown")
    st.markdown(
        f"<small style='color:#64748b'>Last updated: {updated_at} by {updated_by}</small>",
        unsafe_allow_html=True,
    )

    st.divider()

    # Catalysts
    upside = sym_data.get("upside_catalysts", [])
    downside = sym_data.get("downside_catalysts", [])

    if upside or downside:
        st.markdown("**Catalysts**")
        for cat in upside:
            st.markdown(f"- :green[^] {cat}")
        for cat in downside:
            st.markdown(f"- :red[v] {cat}")

    st.divider()

    # Keywords
    keywords = sym_data.get("keywords", [])
    if keywords:
        st.markdown(f"**Keywords** ({len(keywords)})")
        _render_keyword_tags(keywords)

    st.divider()

    # Relations
    sym_themes = relations.get("symbol_to_themes", {}).get(sym_id, [])
    sym_macros = relations.get("symbol_to_macros", {}).get(sym_id, [])

    if sym_themes:
        st.markdown("**Themes**")
        for t in sym_themes:
            st.markdown(f"- {t.replace('_', ' ').title()}")

    if sym_macros:
        st.markdown("**Macros**")
        for m in sym_macros:
            st.markdown(f"- {m.replace('_', ' ').title()}")

    st.divider()

    # Recent activations
    st.markdown("**Recent Activations**")
    signals = load_signals_for_ticker(sym_id, hours=24)
    if signals:
        for sig in signals[:5]:
            action = sig.get("action", "?")
            confidence = sig.get("confidence", 0)
            handle = sig.get("handle", "unknown")
            ts = sig.get("timestamp", "")
            colour = "#22c55e" if action == "BUY" else "#ef4444" if action == "SELL" else "#eab308"
            st.markdown(
                f'<div style="border-left:3px solid {colour};padding:4px 8px;margin:4px 0;">'
                f'<strong style="color:{colour}">{action}</strong> '
                f'conf={confidence:.0%} &middot; @{handle} &middot; <span style="color:#64748b">{ts[:16]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No activations in the last 24h.")


def _render_theme_or_macro_detail(node_id: str, node_type: str, tree: dict):
    """Render detail for a theme or macro node."""
    collection = tree.get(f"{node_type}s", {})
    data = collection.get(node_id, {})

    if not data:
        st.warning(f"No data for {node_type} `{node_id}`")
        return

    label = node_id.replace("_", " ").title()
    colour = "#3b82f6" if node_type == "theme" else "#f59e0b"
    st.markdown(
        f'<h3 style="color:{colour}">{label}</h3>',
        unsafe_allow_html=True,
    )

    desc = data.get("description", "")
    if desc:
        st.caption(desc)

    st.divider()

    # Keywords
    keywords = data.get("keywords", [])
    if keywords:
        st.markdown(f"**Keywords** ({len(keywords)})")
        _render_keyword_tags(keywords)
        st.divider()

    # Related symbols
    related = data.get("related_symbols", [])
    if related:
        st.markdown(f"**Related Symbols** ({len(related)})")
        tags = " ".join(
            f'<span style="background:#1a1a2e;border:1px solid {colour};color:#fafafa;'
            f'padding:2px 8px;border-radius:4px;font-size:0.8rem;margin:2px;">{s}</span>'
            for s in related
        )
        st.markdown(tags, unsafe_allow_html=True)
        st.divider()

    # Tailwinds / Headwinds
    tailwinds = data.get("tailwinds", [])
    headwinds = data.get("headwinds", [])

    if tailwinds:
        st.markdown("**Tailwinds**")
        for tw in tailwinds:
            st.markdown(f"- :green[^] {tw}")

    if headwinds:
        st.markdown("**Headwinds**")
        for hw in headwinds:
            st.markdown(f"- :red[v] {hw}")


def render_node_detail(node_id: Optional[str], tree: dict):
    """Dispatch to the correct detail renderer based on node_id prefix.

    Prefixes: sym_, theme_, macro_
    """
    if not node_id:
        st.info("Click a node in the graph to see details.")
        return

    if node_id.startswith("sym_"):
        _render_symbol_detail(node_id[4:], tree)
    elif node_id.startswith("theme_"):
        _render_theme_or_macro_detail(node_id[6:], "theme", tree)
    elif node_id.startswith("macro_"):
        _render_theme_or_macro_detail(node_id[6:], "macro", tree)
    else:
        st.warning(f"Unknown node type: `{node_id}`")
