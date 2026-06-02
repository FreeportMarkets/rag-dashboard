"""Substack Signals tab — browse and visualize trade pitches from research newsletters."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import boto3
import streamlit as st
from boto3.dynamodb.conditions import Attr

# ── DynamoDB ──────────────────────────────────────────────────────────────────

@st.cache_resource
def _get_table():
    aws = st.secrets["aws"]
    kwargs = {
        "aws_access_key_id": aws["aws_access_key_id"],
        "aws_secret_access_key": aws["aws_secret_access_key"],
        "region_name": aws.get("region", "us-east-1"),
    }
    if aws.get("aws_session_token"):
        kwargs["aws_session_token"] = aws["aws_session_token"]
    dynamodb = boto3.resource("dynamodb", **kwargs)
    return dynamodb.Table("freeport-tweets")


def _decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(v) for v in obj]
    return obj


@st.cache_data(ttl=300)
def load_substack_signals() -> list[dict]:
    """Scan freeport-tweets for source='substack' rows, sorted newest first."""
    table = _get_table()
    items: list[dict] = []
    kwargs = {"FilterExpression": Attr("source").eq("substack")}
    resp = table.scan(**kwargs)
    items.extend(resp["Items"])
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
        items.extend(resp["Items"])
    items = [_decimal_to_float(i) for i in items]
    items.sort(key=lambda r: r.get("published_at", r.get("timestamp", "")), reverse=True)
    return items


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_json(val):
    if isinstance(val, (dict, list)):
        return val
    if not val:
        return None
    try:
        return json.loads(val)
    except Exception:
        return None


def _fmt_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except Exception:
        return iso[:10] if iso else "—"


def _action_badge(action: str) -> str:
    color = "#16a34a" if action == "BUY" else "#dc2626" if action == "SELL" else "#6b7280"
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;">{action or "—"}</span>'


def _horizon_chip(horizon: str) -> str:
    colors = {"short": "#0ea5e9", "medium": "#f59e0b", "long": "#8b5cf6"}
    c = colors.get(horizon, "#6b7280")
    return f'<span style="background:{c}22;color:{c};border:1px solid {c}44;padding:1px 7px;border-radius:9px;font-size:0.72rem;">{horizon}</span>'


def _conf_bar(conf: float) -> str:
    pct = int(conf * 100)
    c = "#16a34a" if conf >= 0.8 else "#f59e0b" if conf >= 0.6 else "#dc2626"
    return (
        f'<div style="display:flex;align-items:center;gap:6px;">'
        f'<div style="flex:1;background:#1e293b;border-radius:4px;height:6px;">'
        f'<div style="width:{pct}%;background:{c};border-radius:4px;height:6px;"></div></div>'
        f'<span style="color:#94a3b8;font-size:0.75rem;min-width:28px;">{pct}%</span></div>'
    )


# ── Render ────────────────────────────────────────────────────────────────────

def render():
    st.markdown("## Substack Signals")
    st.caption("Paid research newsletter pitches · full article content · refreshes every 5 min")

    with st.spinner("Loading signals…"):
        all_items = load_substack_signals()

    if not all_items:
        st.info("No Substack signals found yet. The service runs the Substack poll once every 24h.")
        return

    # ── Filters ───────────────────────────────────────────────────────────────
    # publication = slug stored in item["publication"]; fallback to handle
    publications = sorted({
        i.get("publication") or i.get("handle", "")
        for i in all_items
        if i.get("publication") or i.get("handle")
    })
    actions = sorted({i.get("action", "") for i in all_items if i.get("action")})
    horizons = sorted({i.get("horizon", "") for i in all_items if i.get("horizon")})

    with st.expander("Filters", expanded=True):
        col1, col2, col3, col4, col5 = st.columns([2, 1.2, 1.2, 1.5, 1])
        with col1:
            sel_pubs = st.multiselect("Publication", publications, default=[],
                                      key="ss_pubs", placeholder="All publications")
        with col2:
            sel_action = st.selectbox("Action", ["All"] + actions, key="ss_action")
        with col3:
            sel_horizon = st.selectbox("Horizon", ["All"] + horizons, key="ss_horizon")
        with col4:
            min_conf = st.slider("Min confidence", 0.0, 1.0, 0.0, 0.05,
                                 key="ss_conf", format="%.0f%%")
        with col5:
            catalyst_only = st.checkbox("Catalyst only", key="ss_catalyst")

    # Apply filters
    items = all_items
    if sel_pubs:
        items = [i for i in items
                 if (i.get("publication") or i.get("handle", "")) in sel_pubs]
    if sel_action != "All":
        items = [i for i in items if i.get("action") == sel_action]
    if sel_horizon != "All":
        items = [i for i in items if i.get("horizon") == sel_horizon]
    if min_conf > 0:
        items = [i for i in items if i.get("confidence", 0) >= min_conf]
    if catalyst_only:
        items = [i for i in items if i.get("is_catalyst")]

    # ── Metric cards ──────────────────────────────────────────────────────────
    buy_n = sum(1 for i in items if i.get("action") == "BUY")
    sell_n = sum(1 for i in items if i.get("action") == "SELL")
    avg_conf = (sum(i.get("confidence", 0) for i in items) / len(items)) if items else 0
    pub_n = len({i.get("publication") or i.get("handle") for i in items})

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total signals", len(items))
    m2.metric("Publications", pub_n)
    m3.metric("BUY", buy_n)
    m4.metric("SELL", sell_n)
    m5.metric("Avg confidence", f"{avg_conf:.0%}")

    st.divider()

    # ── Charts ────────────────────────────────────────────────────────────────
    try:
        import plotly.graph_objects as go

        chart_col1, chart_col2 = st.columns([3, 2])

        with chart_col1:
            pub_buy: dict[str, int] = {}
            pub_sell: dict[str, int] = {}
            for i in items:
                p = i.get("publication") or i.get("handle", "unknown")
                if i.get("action") == "BUY":
                    pub_buy[p] = pub_buy.get(p, 0) + 1
                elif i.get("action") == "SELL":
                    pub_sell[p] = pub_sell.get(p, 0) + 1

            all_pubs = sorted(pub_buy.keys() | pub_sell.keys(),
                              key=lambda p: pub_buy.get(p, 0) + pub_sell.get(p, 0))

            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                y=all_pubs, x=[pub_buy.get(p, 0) for p in all_pubs],
                name="BUY", orientation="h", marker_color="#16a34a",
            ))
            fig_bar.add_trace(go.Bar(
                y=all_pubs, x=[pub_sell.get(p, 0) for p in all_pubs],
                name="SELL", orientation="h", marker_color="#dc2626",
            ))
            fig_bar.update_layout(
                barmode="stack", title="Signals by publication",
                paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
                font=dict(color="#94a3b8"), height=280,
                margin=dict(l=0, r=0, t=36, b=0),
                legend=dict(orientation="h", y=-0.15),
                xaxis=dict(gridcolor="#1e293b"),
                yaxis=dict(gridcolor="#1e293b"),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with chart_col2:
            confs = [i.get("confidence", 0) for i in items]
            buckets = {"<60%": 0, "60–70%": 0, "70–80%": 0, "80–90%": 0, "≥90%": 0}
            for c in confs:
                if c < 0.6:      buckets["<60%"] += 1
                elif c < 0.7:    buckets["60–70%"] += 1
                elif c < 0.8:    buckets["70–80%"] += 1
                elif c < 0.9:    buckets["80–90%"] += 1
                else:            buckets["≥90%"] += 1

            fig_hist = go.Figure(go.Bar(
                x=list(buckets.keys()), y=list(buckets.values()),
                marker_color=["#dc2626", "#f59e0b", "#f59e0b", "#16a34a", "#16a34a"],
            ))
            fig_hist.update_layout(
                title="Confidence distribution",
                paper_bgcolor="#0f172a", plot_bgcolor="#0f172a",
                font=dict(color="#94a3b8"), height=280,
                margin=dict(l=0, r=0, t=36, b=0),
                xaxis=dict(gridcolor="#1e293b"),
                yaxis=dict(gridcolor="#1e293b"),
                showlegend=False,
            )
            st.plotly_chart(fig_hist, use_container_width=True)

    except ImportError:
        st.info("Install plotly for charts: `pip install plotly`")

    st.divider()

    # ── Signal table ──────────────────────────────────────────────────────────
    st.markdown(f"**{len(items)} signals** · click any row to expand full reasoning")

    if not items:
        st.warning("No signals match the current filters.")
        return

    for item in items:
        pub = item.get("publication") or item.get("handle", "—")
        ticker = item.get("ticker") or "?"
        action = item.get("action", "")
        conf = item.get("confidence", 0.0)
        horizon = item.get("horizon", "")
        category = item.get("category", "")
        date_str = _fmt_date(item.get("published_at") or item.get("timestamp", ""))
        title = item.get("title") or item.get("content", "—")[:60]
        analysis = item.get("analysis", "")
        url = item.get("source_url", "#")

        row_label = (
            f"**{ticker}** · {date_str} · {pub} · "
            f"{action or '—'} · {conf:.0%} · {title[:55]}{'…' if len(title) > 55 else ''}"
        )

        with st.expander(row_label, expanded=False):
            meta_cols = st.columns([1.5, 1, 1, 1.5, 2])
            meta_cols[0].markdown(f"**Publication**  \n{pub}")
            meta_cols[1].markdown(f"**Date**  \n{date_str}")
            meta_cols[2].markdown(
                f"**Action**  \n" + _action_badge(action), unsafe_allow_html=True)
            meta_cols[3].markdown(
                f"**Horizon**  \n" + _horizon_chip(horizon), unsafe_allow_html=True)
            meta_cols[4].markdown(f"**Category**  \n{category or '—'}")

            st.markdown(_conf_bar(conf), unsafe_allow_html=True)
            st.markdown(f"**Article:** [{title}]({url})")

            st.markdown("**Summary**")
            st.markdown(f"> {analysis}")

            reasoning = item.get("reasoning", "")
            if reasoning:
                st.markdown("**Full reasoning**")
                st.markdown(reasoning)

            causal = _safe_json(item.get("causal_chain"))
            if causal and any(causal.values()):
                st.markdown("**Causal chain**")
                cc1, cc2, cc3, cc4 = st.columns(4)
                box = "background:#1e293b;border-radius:6px;padding:10px 12px;font-size:0.8rem;"
                cc1.markdown(
                    f'<div style="{box}"><div style="color:#6366f1;font-weight:700;margin-bottom:4px;">Event</div>'
                    f'{causal.get("event","—")}</div>', unsafe_allow_html=True)
                cc2.markdown(
                    f'<div style="{box}"><div style="color:#0ea5e9;font-weight:700;margin-bottom:4px;">Mechanism</div>'
                    f'{causal.get("mechanism","—")}</div>', unsafe_allow_html=True)
                cc3.markdown(
                    f'<div style="{box}"><div style="color:#16a34a;font-weight:700;margin-bottom:4px;">Asset Impact</div>'
                    f'{causal.get("asset_impact","—")}</div>', unsafe_allow_html=True)
                cc4.markdown(
                    f'<div style="{box}"><div style="color:#f59e0b;font-weight:700;margin-bottom:4px;">Uncertainty</div>'
                    f'{causal.get("uncertainty","—")}</div>', unsafe_allow_html=True)

            supplementals = _safe_json(item.get("supplemental_details"))
            if supplementals:
                st.markdown("**Supplemental tickers**")
                for sup in supplementals:
                    s_ticker = sup.get("ticker", "?")
                    s_imp = sup.get("importance", 0)
                    s_reason = sup.get("reasoning", "")
                    imp_color = "#16a34a" if s_imp >= 0.4 else "#f59e0b" if s_imp >= 0.25 else "#6b7280"
                    st.markdown(
                        f'<div style="background:#1e293b;border-left:3px solid {imp_color};'
                        f'padding:8px 12px;border-radius:4px;margin-bottom:4px;font-size:0.82rem;">'
                        f'<span style="color:#f8fafc;font-weight:700;">{s_ticker}</span>'
                        f'<span style="color:#94a3b8;margin-left:8px;">importance {s_imp:.0%}</span>'
                        f'<br><span style="color:#cbd5e1;">{s_reason}</span></div>',
                        unsafe_allow_html=True,
                    )

            st.caption(
                f"tweet_id={item.get('tweet_id')} · "
                f"novelty={item.get('novelty', 0):.0%} · "
                f"catalyst={'yes' if item.get('is_catalyst') else 'no'} · "
                f"words={item.get('word_count', '?')} · "
                f"audience={item.get('audience', '?')}"
            )
