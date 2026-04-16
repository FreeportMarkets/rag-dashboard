"""Tweet Flow tab — what signals we put on the app today and how they break down."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from data.tweet_flow import aggregate_flow, load_signals_for_date


def _summary_row(summary: dict) -> None:
    cols = st.columns(5)
    cols[0].metric("Signals", summary["total_signals"])
    cols[1].metric("Avg confidence", f"{summary['avg_confidence']:.2f}")
    cols[2].metric("Avg novelty", f"{summary['avg_novelty']:.2f}")
    cols[3].metric("Catalysts", summary["catalyst_count"])
    cols[4].metric("Engagement", f"{summary['engagement_total']:,}")


def _hourly_chart(summary: dict) -> None:
    df = pd.DataFrame(summary["hourly"])
    df["hour_label"] = df["hour"].astype(str) + ":00"
    fig = px.bar(df, x="hour_label", y="count", title="Signals by hour (UTC)",
                 color_discrete_sequence=["#6366f1"])
    fig.update_layout(
        paper_bgcolor="#0e1117", plot_bgcolor="#151a24",
        font=dict(color="#e6e8ee"), height=280, margin=dict(l=8, r=8, t=40, b=8),
        xaxis=dict(gridcolor="#26304a"), yaxis=dict(gridcolor="#26304a"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _action_and_category(summary: dict) -> None:
    col1, col2 = st.columns(2)
    with col1:
        actions = summary["by_action"]
        if actions:
            df = pd.DataFrame([{"action": k, "count": v} for k, v in actions.items()])
            fig = px.bar(df, x="action", y="count", title="By action",
                         color="action",
                         color_discrete_map={"BUY": "#22c55e", "SELL": "#ef4444", "HOLD": "#eab308"})
            fig.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#151a24",
                              font=dict(color="#e6e8ee"), height=260, showlegend=False,
                              margin=dict(l=8, r=8, t=40, b=8),
                              xaxis=dict(gridcolor="#26304a"), yaxis=dict(gridcolor="#26304a"))
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        cats = summary["by_category"]
        if cats:
            df = pd.DataFrame([{"category": k, "count": v} for k, v in cats.items()])
            fig = px.bar(df, x="category", y="count", title="By category",
                         color_discrete_sequence=["#6366f1"])
            fig.update_layout(paper_bgcolor="#0e1117", plot_bgcolor="#151a24",
                              font=dict(color="#e6e8ee"), height=260,
                              margin=dict(l=8, r=8, t=40, b=8),
                              xaxis=dict(gridcolor="#26304a"), yaxis=dict(gridcolor="#26304a"))
            st.plotly_chart(fig, use_container_width=True)


def _top_tables(summary: dict) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Top tickers")
        if summary["by_ticker"]:
            rows = []
            for t in summary["by_ticker"]:
                acts = t["actions"]
                rows.append({
                    "ticker": t["ticker"],
                    "count": t["count"],
                    "BUY": acts.get("BUY", 0),
                    "SELL": acts.get("SELL", 0),
                    "HOLD": acts.get("HOLD", 0),
                    "avg_conf": t["avg_confidence"],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No data.")
    with col2:
        st.markdown("### Top handles")
        if summary["by_handle"]:
            rows = [{"handle": "@" + h["handle"], "count": h["count"], "top tickers": ", ".join(h["top_tickers"])}
                    for h in summary["by_handle"]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No data.")


def render():
    st.markdown("## Tweet Flow")
    st.caption(
        "Signals written to `freeport-tweets` with `flag=\"Y\"` — everything we surface to "
        "the Latest feed. (Recommender re-ranks but doesn't exclude rows.)"
    )

    col_date, _ = st.columns([1, 3])
    with col_date:
        picked = st.date_input("Date (UTC)", value=date.today(), key="flow_date",
                               min_value=date.today() - timedelta(days=30), max_value=date.today())

    try:
        rows = load_signals_for_date(picked.isoformat())
    except Exception as exc:
        st.error(f"Could not load signals: {exc}")
        return

    if not rows:
        st.info(f"No signals for {picked.isoformat()} yet.")
        return

    summary = aggregate_flow(rows)
    _summary_row(summary)
    st.divider()
    _hourly_chart(summary)
    _action_and_category(summary)
    _top_tables(summary)
