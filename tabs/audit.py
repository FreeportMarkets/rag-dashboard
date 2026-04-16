"""Audit tab — keyword collisions + coverage gaps."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from data.audit import find_collisions, find_gaps
from data.tree_loader import load_tree
from data.tweet_flow import load_signals_for_date


def _collision_section(tree: dict) -> None:
    st.markdown("### Keyword collisions")
    st.caption(
        "Keywords that appear on multiple tickers — higher counts mean higher risk of "
        "a tweet pulling in the wrong ticker's context."
    )
    min_tickers = st.slider("Minimum tickers per keyword", 2, 6, 3, key="audit_collision_min")
    coll = find_collisions(tree, min_tickers=min_tickers)
    if not coll:
        st.info("No collisions at this threshold.")
        return
    df = pd.DataFrame([{"keyword": c["keyword"], "count": c["count"], "tickers": ", ".join(c["tickers"])}
                       for c in coll])
    st.dataframe(df, use_container_width=True, hide_index=True, height=380)


def _coverage_section(tree: dict) -> None:
    st.markdown("### Coverage gaps")
    st.caption(
        "Tracked symbols with zero tweets in the last N days. Sort order: most keywords "
        "first (biggest wasted coverage)."
    )
    col_days, _ = st.columns([1, 3])
    with col_days:
        days = st.slider("Window (days)", 1, 30, 7, key="audit_gap_days")

    # Load all recent tweets in the window to check coverage.
    # Use UTC today() so the window matches find_gaps()'s UTC cutoff.
    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.date()
    all_rows: list[dict] = []
    failures: list[tuple[str, str]] = []
    for i in range(days):
        d = today_utc - timedelta(days=i)
        try:
            all_rows.extend(load_signals_for_date(d.isoformat()))
        except Exception as exc:
            failures.append((d.isoformat(), str(exc)))

    if failures and len(failures) == days:
        st.error(f"Could not load signals for any day in window. First failure: {failures[0][1]}")
        return
    if failures:
        st.warning(
            f"Could not load signals for {len(failures)}/{days} days — gap list may be incomplete. "
            f"First failure: {failures[0][0]} ({failures[0][1]})"
        )

    gaps = find_gaps(tree, all_rows, days=days, now=now_utc)
    if not gaps:
        st.success("Every tracked symbol saw a signal in the window.")
        return
    st.metric("Gaps", len(gaps))
    rows = []
    for g in gaps[:200]:
        rows.append({
            "symbol": g["symbol"],
            "keywords": g["keyword_count"],
            "themes": ", ".join(g["themes"]),
            "macros": ", ".join(g["macros"]),
            "description": g["description"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=400)


def render():
    st.markdown("## Audit")
    tree = load_tree()
    if not tree:
        st.warning("No tree data available.")
        return

    _collision_section(tree)
    st.divider()
    _coverage_section(tree)
