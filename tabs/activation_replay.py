"""Activation Replay tab — select a signal and see the 7-step RAG trace."""

import streamlit as st

from components.activation_timeline import render_activation_timeline
from data.signal_loader import load_recent_signals


def render():
    """Render the Activation Replay tab."""
    # Time range selector
    hours = st.selectbox(
        "Time range",
        options=[6, 12, 24, 48, 72],
        index=2,
        format_func=lambda h: f"Last {h}h",
        key="replay_hours",
    )

    signals = load_recent_signals(hours=hours)

    if not signals:
        st.info(f"No RAG-enriched signals found in the last {hours} hours.")
        return

    st.caption(f"{len(signals)} signals with RAG context")

    # Build display labels for the selectbox
    def _label(sig: dict) -> str:
        action = sig.get("action", "?")
        ticker = sig.get("ticker", "?")
        handle = sig.get("handle", "?")
        ts = sig.get("timestamp", "")[:16]
        conf = sig.get("confidence", 0)
        return f"{action} {ticker} | @{handle} | {ts} | conf={conf:.0%}"

    labels = [_label(s) for s in signals]

    # Track selected index in session state for prev/next buttons
    if "replay_idx" not in st.session_state:
        st.session_state.replay_idx = 0

    # Clamp index to valid range
    if st.session_state.replay_idx >= len(signals):
        st.session_state.replay_idx = 0

    col_select, col_prev, col_next = st.columns([6, 1, 1])

    with col_select:
        selected_label = st.selectbox(
            "Signal",
            labels,
            index=st.session_state.replay_idx,
            key="replay_select",
        )
        # Sync index back from selectbox
        if selected_label in labels:
            st.session_state.replay_idx = labels.index(selected_label)

    with col_prev:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Prev", key="replay_prev", use_container_width=True):
            st.session_state.replay_idx = max(0, st.session_state.replay_idx - 1)
            st.rerun()

    with col_next:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Next", key="replay_next", use_container_width=True):
            st.session_state.replay_idx = min(
                len(signals) - 1, st.session_state.replay_idx + 1
            )
            st.rerun()

    st.divider()

    # Render the selected signal's timeline
    signal = signals[st.session_state.replay_idx]
    render_activation_timeline(signal)
