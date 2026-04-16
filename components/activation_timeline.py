"""7-step activation timeline for a RAG-enriched trade signal."""

import streamlit as st


# Step colours (matching the spec)
STEP_COLORS = {
    1: "#3b82f6",  # blue   — Source Tweet
    2: "#a855f7",  # purple — Keyword Matching
    3: "#f59e0b",  # amber  — Context Lookup
    4: "#06b6d4",  # cyan   — Theme/Macro + Expansion
    5: "#ec4899",  # pink   — Dynamic Context
    6: "#22c55e",  # green  — GPT-5.2 Output
    7: "#fafafa",  # white  — Written to DDB
}


def _step_header(number: int, title: str):
    """Render a numbered circle + title for a timeline step."""
    colour = STEP_COLORS.get(number, "#6b7280")
    st.markdown(
        f"""<div style="display:flex;align-items:center;gap:10px;margin-top:16px;">
            <div style="width:28px;height:28px;border-radius:50%;background:{colour};
                        display:flex;align-items:center;justify-content:center;
                        font-weight:700;font-size:0.85rem;color:#0e1117;flex-shrink:0;">
                {number}
            </div>
            <div style="font-weight:600;font-size:1rem;color:{colour};">{title}</div>
        </div>
        <div style="border-left:2px solid {colour};margin-left:14px;padding-left:18px;padding-bottom:4px;">""",
        unsafe_allow_html=True,
    )


def _step_footer():
    """Close the timeline connector."""
    st.markdown("</div>", unsafe_allow_html=True)


def render_activation_timeline(signal: dict):
    """Render the full 7-step activation trace for a signal."""
    if not signal:
        st.info("Select a signal to see the activation trace.")
        return

    ctx = signal.get("context_match_parsed") or {}
    chain = signal.get("causal_chain_parsed") or {}

    # ── Step 1: Source Tweet ───────────────────────────────────────────
    _step_header(1, "Source Tweet")
    handle = signal.get("handle", "unknown")
    timestamp = signal.get("timestamp", "")
    content = signal.get("content", "")
    source_type = signal.get("source_type", signal.get("type", "twitter"))

    st.markdown(
        f"""<div style="background:#1a1a2e;border-radius:8px;padding:12px;margin:8px 0;">
        <strong>@{handle}</strong>
        <span style="color:#64748b;margin-left:8px;">{timestamp[:19]}</span>
        <span style="background:#334155;color:#94a3b8;padding:1px 6px;border-radius:4px;
               font-size:0.7rem;margin-left:8px;">{source_type}</span>
        <p style="margin-top:8px;color:#e2e8f0;line-height:1.5;">{content}</p>
        </div>""",
        unsafe_allow_html=True,
    )
    _step_footer()

    # ── Step 2: Keyword Matching ──────────────────────────────────────
    _step_header(2, "Keyword Matching")
    matched_tickers = ctx.get("matched_tickers", [])
    if matched_tickers:
        for match in matched_tickers:
            ticker = match.get("ticker", "?")
            keyword = match.get("keyword_hit", "?")
            source = match.get("source", "static")
            badge_bg = "#22c55e" if source == "live" else "#334155"
            st.markdown(
                f"""<div style="margin:4px 0;">
                <code>{keyword}</code> &rarr; <strong>{ticker}</strong>
                <span style="background:{badge_bg};color:#fff;padding:1px 6px;
                       border-radius:4px;font-size:0.7rem;margin-left:4px;">{source}</span>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No keyword matches recorded.")
    _step_footer()

    # ── Step 3: Context Lookup ────────────────────────────────────────
    _step_header(3, "Context Lookup")
    catalysts_injected = ctx.get("catalysts_injected", {})
    if catalysts_injected:
        for ticker, cats in catalysts_injected.items():
            upside = cats.get("upside", [])
            downside = cats.get("downside", [])
            st.markdown(f"**{ticker}**")
            for c in upside:
                st.markdown(f"- :green[^] {c}")
            for c in downside:
                st.markdown(f"- :red[v] {c}")
    else:
        st.caption("No catalysts injected.")
    _step_footer()

    # ── Step 4: Theme/Macro + Expansion ───────────────────────────────
    _step_header(4, "Theme/Macro + Expansion")

    direct_themes = ctx.get("matched_themes", [])
    direct_macros = ctx.get("matched_macros", [])
    expanded = ctx.get("expanded_relations", {})
    added_themes = expanded.get("added_themes", [])
    added_macros = expanded.get("added_macros", [])

    if direct_themes:
        st.markdown("**Direct themes:** " + ", ".join(
            f"`{t}`" for t in direct_themes
        ))
    if direct_macros:
        st.markdown("**Direct macros:** " + ", ".join(
            f"`{m}`" for m in direct_macros
        ))
    if added_themes:
        st.markdown(
            "**Expanded themes:** " + ", ".join(
                f'<span style="color:#06b6d4">{t}</span>' for t in added_themes
            ),
            unsafe_allow_html=True,
        )
    if added_macros:
        st.markdown(
            "**Expanded macros:** " + ", ".join(
                f'<span style="color:#06b6d4">{m}</span>' for m in added_macros
            ),
            unsafe_allow_html=True,
        )
    if not any([direct_themes, direct_macros, added_themes, added_macros]):
        st.caption("No theme/macro context.")
    _step_footer()

    # ── Step 5: Dynamic Context ───────────────────────────────────────
    _step_header(5, "Dynamic Context")

    prices_used = ctx.get("prices_used", {})
    headlines_used = ctx.get("headlines_used", [])

    if prices_used:
        st.markdown("**Prices**")
        for ticker, pdata in prices_used.items():
            price = pdata.get("price", "?")
            change = pdata.get("change_pct", 0)
            colour = "#22c55e" if change >= 0 else "#ef4444"
            st.markdown(
                f'&nbsp;&nbsp;{ticker}: **${price}** '
                f'<span style="color:{colour}">{change:+.1f}%</span>',
                unsafe_allow_html=True,
            )

    if headlines_used:
        st.markdown("**Headlines**")
        for hl in headlines_used:
            source = hl.get("source", "?")
            headline = hl.get("headline", "")
            age = hl.get("age_minutes", "?")
            assets = ", ".join(hl.get("matched_assets", []))
            st.markdown(
                f"""<div style="margin:4px 0;padding:4px 8px;background:#1a1a2e;border-radius:4px;">
                <small style="color:#64748b">{source} &middot; {age}m ago</small>
                <br>{headline}
                <br><small style="color:#94a3b8">Assets: {assets}</small>
                </div>""",
                unsafe_allow_html=True,
            )

    if not prices_used and not headlines_used:
        st.caption("No dynamic context recorded.")
    _step_footer()

    # ── Step 6: GPT-5.2 Output ────────────────────────────────────────
    _step_header(6, "GPT-5.2 Output")

    ticker = signal.get("ticker", "?")
    action = signal.get("action", "?")
    confidence = signal.get("confidence", 0)
    novelty = signal.get("novelty", 0)
    is_catalyst = signal.get("is_catalyst", False)
    horizon = signal.get("horizon", "?")
    reasoning = signal.get("reasoning", "")
    analysis = signal.get("analysis", "")

    action_colour = "#22c55e" if action == "BUY" else "#ef4444" if action == "SELL" else "#eab308"

    st.markdown(
        f"""<div style="background:#1a1a2e;border-radius:8px;padding:12px;margin:8px 0;">
        <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center;">
            <div><strong style="color:{action_colour};font-size:1.1rem;">{action} {ticker}</strong></div>
            <div>Confidence: <strong>{confidence:.0%}</strong></div>
            <div>Novelty: <strong>{novelty:.0%}</strong></div>
            <div>Catalyst: <strong>{'Yes' if is_catalyst else 'No'}</strong></div>
            <div>Horizon: <strong>{horizon}</strong></div>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Causal chain
    if chain:
        st.markdown("**Causal Chain**")
        steps = [
            ("Event", chain.get("event", "")),
            ("Mechanism", chain.get("mechanism", "")),
            ("Asset Impact", chain.get("asset_impact", "")),
            ("Uncertainty", chain.get("uncertainty", "")),
        ]
        for label, text in steps:
            if text:
                st.markdown(
                    f"""<div style="border-left:2px solid #22c55e;padding:4px 10px;margin:4px 0;">
                    <small style="color:#94a3b8">{label}</small><br>{text}
                    </div>""",
                    unsafe_allow_html=True,
                )

    # Reasoning
    if reasoning:
        st.markdown("**Reasoning**")
        st.markdown(
            f'<div style="color:#e2e8f0;background:#0e1117;padding:8px 12px;'
            f'border-radius:4px;font-size:0.9rem;">{reasoning}</div>',
            unsafe_allow_html=True,
        )

    # Analysis
    if analysis:
        with st.expander("Full Analysis"):
            st.write(analysis)

    _step_footer()

    # ── Step 7: Written to DynamoDB ───────────────────────────────────
    _step_header(7, "Written to DynamoDB")
    tweet_id = signal.get("tweet_id", signal.get("id", "?"))
    st.markdown(
        f"""<div style="background:#1a1a2e;border-radius:8px;padding:8px 12px;margin:8px 0;">
        <code>tweet_id: {tweet_id}</code>
        <span style="color:#22c55e;margin-left:8px;">Persisted</span>
        </div>""",
        unsafe_allow_html=True,
    )
    _step_footer()
