"""7-step activation timeline for a RAG-enriched trade signal."""

import streamlit as st


STEP_COLORS = {
    1: "#3b82f6",
    2: "#a855f7",
    3: "#f59e0b",
    4: "#06b6d4",
    5: "#ec4899",
    6: "#22c55e",
    7: "#fafafa",
}


def _step_header(number: int, title: str, subtitle: str = ""):
    colour = STEP_COLORS.get(number, "#6b7280")
    sub_html = (
        f'<span style="color:#94a3b8;font-size:0.82rem;margin-left:10px;">{subtitle}</span>'
        if subtitle else ""
    )
    st.markdown(
        f"""<div style="display:flex;align-items:center;gap:10px;margin-top:16px;">
            <div style="width:28px;height:28px;border-radius:50%;background:{colour};
                        display:flex;align-items:center;justify-content:center;
                        font-weight:700;font-size:0.85rem;color:#0e1117;flex-shrink:0;">{number}</div>
            <div style="font-weight:600;font-size:1rem;color:{colour};">{title}{sub_html}</div>
        </div>
        <div style="border-left:2px solid {colour};margin-left:14px;padding-left:18px;padding-bottom:4px;">""",
        unsafe_allow_html=True,
    )


def _step_footer():
    st.markdown("</div>", unsafe_allow_html=True)


def _info_box(title: str, body: str, new: bool = True):
    prefix = '<span style="color:#60a5fa;font-weight:600;margin-right:4px;">NEW</span>' if new else ""
    st.markdown(
        f"""<div style="background:#0c1829;border:1px solid #1e3a5f;border-left:3px solid #3b82f6;
                       border-radius:6px;padding:8px 12px;margin:6px 0;font-size:0.8rem;">
            {prefix}<span style="color:#60a5fa;font-weight:600;">ⓘ {title}</span>
            <span style="color:#94a3b8;margin-left:6px;">— {body}</span>
        </div>""",
        unsafe_allow_html=True,
    )


def _dropped_box(text: str):
    st.markdown(
        f"""<div style="background:#120e04;border:1px solid #3d2f0a;border-left:3px solid #f59e0b;
                       border-radius:6px;padding:8px 12px;margin:6px 0;font-size:0.8rem;color:#94a3b8;">
            {text}
        </div>""",
        unsafe_allow_html=True,
    )


def _catalyst_text_score(item):
    """Return (text, score) from a catalyst that may be a str or dict."""
    if isinstance(item, dict):
        return item.get("text", item.get("catalyst", str(item))), item.get("score")
    return str(item), None


def render_activation_timeline(signal: dict):
    if not signal:
        st.info("Select a signal to see the activation trace.")
        return

    ctx = signal.get("context_match_parsed") or {}
    chain = signal.get("causal_chain_parsed") or {}

    # ── Step 1: Source Tweet ──────────────────────────────────────────────────
    _step_header(1, "Source Tweet")

    handle = signal.get("handle", "unknown")
    timestamp = signal.get("timestamp", "")
    content = signal.get("content", "")
    source_type = signal.get("source_type", signal.get("type", "twitter"))
    handle_prior = signal.get("handle_prior")
    novelty = signal.get("novelty", 0)

    meta_parts = []
    if handle_prior is not None:
        meta_parts.append(f"handle prior: {handle_prior:.2f}")
    if novelty:
        meta_parts.append(f"novelty: {novelty:.2f}")
    meta_html = (
        f'<br><span style="color:#94a3b8;font-size:0.8rem;">{" · ".join(meta_parts)}</span>'
        if meta_parts else ""
    )

    st.markdown(
        f"""<div style="background:#1a1a2e;border-radius:8px;padding:12px;margin:8px 0;">
        <strong>@{handle}</strong>
        <span style="color:#64748b;margin-left:8px;">{timestamp[:19]}</span>
        <span style="background:#334155;color:#94a3b8;padding:1px 6px;border-radius:4px;
               font-size:0.7rem;margin-left:8px;">{source_type}</span>
        {meta_html}
        <p style="margin-top:8px;color:#e2e8f0;line-height:1.5;">{content}</p>
        </div>""",
        unsafe_allow_html=True,
    )

    if handle_prior is not None:
        category = signal.get("category", "")
        ctx_str = f" on {category} signals" if category else ""
        _info_box(
            "Handle reputation",
            f"why we should trust this source. "
            f"{handle.lstrip('@')} has {handle_prior:.0%} historical accuracy{ctx_str}.",
        )

    _step_footer()

    # ── Step 2: Keyword Matching ──────────────────────────────────────────────
    _step_header(2, "Keyword Matching")

    matched_tickers = ctx.get("matched_tickers", [])
    dropped_keywords = ctx.get("dropped_keywords", [])

    has_conf = any("match_confidence" in m or "score" in m for m in matched_tickers)
    if matched_tickers:
        for match in matched_tickers:
            ticker_sym = match.get("ticker", "?")
            keyword = match.get("keyword_hit", "?")
            source = match.get("source", "static")
            conf = match.get("match_confidence", match.get("score"))
            pill_bg = "#052e16" if source == "live" else "#1a2035"
            pill_color = "#86efac" if source == "live" else "#94a3b8"
            pill_border = "#166534" if source == "live" else "#2d3748"
            conf_html = (
                f'<span style="color:#94a3b8;margin-left:8px;">{conf:.2f}</span>'
                if conf is not None else ""
            )
            st.markdown(
                f"""<div style="margin:6px 0;display:flex;align-items:center;gap:8px;">
                <span style="background:{pill_bg};color:{pill_color};border:1px solid {pill_border};
                       padding:2px 10px;border-radius:99px;font-size:0.8rem;font-weight:500;">{keyword}</span>
                <span style="color:#64748b;">→</span>
                <strong style="color:#e2e8f0;">{ticker_sym}</strong>
                {conf_html}
                </div>""",
                unsafe_allow_html=True,
            )
        if has_conf:
            _info_box(
                "Match confidence",
                "1.00 = exact match, &lt;1.00 = fuzzy. Lets you spot weak matches.",
            )
    else:
        st.caption("No keyword matches recorded.")

    if dropped_keywords:
        short_list = ", ".join(
            f"{d.get('keyword','?')} ({d.get('reason','?')})"
            for d in dropped_keywords
        )
        _dropped_box(
            f"• {len(dropped_keywords)} keyword{'s' if len(dropped_keywords) > 1 else ''} "
            f"dropped: {short_list}"
        )
        explanations = [d for d in dropped_keywords[:2] if d.get("explanation")]
        if explanations:
            ex = " ".join(
                f"{d['keyword']} {d['explanation']}" for d in explanations
            )
            _info_box(
                "Dropped items",
                f"what almost matched but didn't, with the reason. {ex}",
            )

    _step_footer()

    # ── Step 3: Context Lookup ────────────────────────────────────────────────
    _step_header(3, "Context Lookup")

    catalysts_injected = ctx.get("catalysts_injected", {})
    catalysts_dropped = ctx.get("catalysts_dropped", [])

    if catalysts_injected:
        for ticker_sym, cats in catalysts_injected.items():
            total_retrieved = cats.get("total_retrieved")
            upside = cats.get("upside", [])
            downside = cats.get("downside", [])
            n_shown = len(upside) + len(downside)

            header = ticker_sym
            if total_retrieved:
                header += f" · top {n_shown} of {total_retrieved} retrieved"
            st.markdown(f"**{header}**")

            scored_items = []
            for item in upside:
                text, score = _catalyst_text_score(item)
                scored_items.append((text, score))
                score_html = (
                    f'<span style="color:#94a3b8;margin-left:6px;">{score:.2f}</span>'
                    if score is not None else ""
                )
                st.markdown(
                    f'<div style="margin:2px 0;"><span style="color:#22c55e;">↑</span>'
                    f' {text}{score_html}</div>',
                    unsafe_allow_html=True,
                )
            for item in downside:
                text, score = _catalyst_text_score(item)
                scored_items.append((text, score))
                score_html = (
                    f'<span style="color:#94a3b8;margin-left:6px;">{score:.2f}</span>'
                    if score is not None else ""
                )
                st.markdown(
                    f'<div style="margin:2px 0;"><span style="color:#ef4444;">↓</span>'
                    f' {text}{score_html}</div>',
                    unsafe_allow_html=True,
                )

            # Relevance info box when scores are present
            with_scores = [(t, s) for t, s in scored_items if s is not None]
            if len(with_scores) >= 2:
                top2 = sorted(with_scores, key=lambda x: x[1], reverse=True)[:2]
                _info_box(
                    "Relevance scores",
                    f"how strongly each catalyst matched. "
                    f"{top2[0][0]} ({top2[0][1]:.2f}) drove this signal, "
                    f"not the {top2[1][0]} angle ({top2[1][1]:.2f}).",
                )
    else:
        st.caption("No catalysts injected.")

    if catalysts_dropped:
        threshold = (
            catalysts_dropped[0].get("threshold", 0.65)
            if isinstance(catalysts_dropped[0], dict) else 0.65
        )
        preview = []
        for d in catalysts_dropped[:3]:
            text, score = _catalyst_text_score(d)
            preview.append(f"{text} ({score:.2f})" if score is not None else text)
        suffix = "..." if len(catalysts_dropped) > 3 else ""
        _dropped_box(
            f"• {len(catalysts_dropped)} catalyst{'s' if len(catalysts_dropped) > 1 else ''} "
            f"dropped (score &lt; {threshold:.2f}): {', '.join(preview)}{suffix}"
        )

    _step_footer()

    # ── Step 4: Theme + Expansion ─────────────────────────────────────────────
    _step_header(4, "Theme + Expansion")

    direct_themes = ctx.get("matched_themes", [])
    direct_macros = ctx.get("matched_macros", [])
    expanded = ctx.get("expanded_relations", {})
    added_themes = expanded.get("added_themes", [])
    added_macros = expanded.get("added_macros", [])
    expansion_rules = expanded.get("rules", {})
    rejected_expansions = expanded.get("rejected", [])

    def _theme_chip(name: str) -> str:
        return (
            f'<span style="background:#1e3a5f;color:#3b82f6;border:1px solid #2d5a8e;'
            f'padding:2px 8px;border-radius:4px;font-size:0.8rem;">{name}</span>'
        )

    def _macro_chip(name: str) -> str:
        return (
            f'<span style="background:#2d1f0a;color:#f59e0b;border:1px solid #5a3d0a;'
            f'padding:2px 8px;border-radius:4px;font-size:0.8rem;">{name}</span>'
        )

    shown_rules: set[str] = set()

    for t in direct_themes:
        st.markdown(
            f'<div style="margin:3px 0;">{_theme_chip(t)}'
            f' <span style="color:#64748b;font-size:0.8rem;">· direct hit</span></div>',
            unsafe_allow_html=True,
        )
    for m in direct_macros:
        st.markdown(
            f'<div style="margin:3px 0;">{_macro_chip(m)}'
            f' <span style="color:#64748b;font-size:0.8rem;">· direct hit</span></div>',
            unsafe_allow_html=True,
        )
    for t in added_themes:
        rule = expansion_rules.get(t, {}) if expansion_rules else {}
        rule_id = rule.get("rule_id", "")
        label = f"· expanded via rule {rule_id}" if rule_id else "· expanded"
        st.markdown(
            f'<div style="margin:3px 0;">{_theme_chip(t)}'
            f' <span style="color:#64748b;font-size:0.8rem;">{label}</span></div>',
            unsafe_allow_html=True,
        )
        if rule_id and rule_id not in shown_rules:
            shown_rules.add(rule_id)
            prov = rule.get("provenance", "")
            if prov:
                _info_box("Provenance", f'why this expansion fired. Rule {rule_id} = "{prov}"')
    for m in added_macros:
        rule = expansion_rules.get(m, {}) if expansion_rules else {}
        rule_id = rule.get("rule_id", "")
        label = f"· expanded via rule {rule_id}" if rule_id else "· expanded"
        st.markdown(
            f'<div style="margin:3px 0;">{_macro_chip(m)}'
            f' <span style="color:#64748b;font-size:0.8rem;">{label}</span></div>',
            unsafe_allow_html=True,
        )
        if rule_id and rule_id not in shown_rules:
            shown_rules.add(rule_id)
            prov = rule.get("provenance", "")
            if prov:
                _info_box("Provenance", f'why this expansion fired. Rule {rule_id} = "{prov}"')

    if not any([direct_themes, direct_macros, added_themes, added_macros]):
        st.caption("No theme/macro context.")

    if rejected_expansions:
        parts = []
        for r in rejected_expansions:
            if not isinstance(r, dict):
                parts.append(str(r))
                continue
            name = r.get("name", "?")
            co_occ = r.get("co_occurrence")
            threshold = r.get("threshold")
            reason = r.get("reason", "")
            if co_occ is not None and threshold is not None:
                parts.append(f"{name} rejected — co-occurrence {co_occ:.2f} below threshold {threshold:.2f}")
            elif reason:
                parts.append(f"{name} rejected — {reason}")
            else:
                parts.append(f"{name} rejected")
        _dropped_box(f"• {len(rejected_expansions)} considered: {'; '.join(parts)}")

    _step_footer()

    # ── Step 5: Dynamic Context ───────────────────────────────────────────────
    headlines_kept = ctx.get("headlines_kept", ctx.get("headlines_total_kept"))
    headlines_total = ctx.get("headlines_total")
    tokens_used = ctx.get("tokens_used")

    sub_parts = []
    if headlines_kept is not None and headlines_total is not None:
        sub_parts.append(f"{headlines_kept} of {headlines_total} kept")
    if tokens_used is not None:
        sub_parts.append(f"{tokens_used:,} tokens used")

    _step_header(5, "Dynamic Context", " · ".join(sub_parts))

    prices_used = ctx.get("prices_used", {})
    headlines_used = ctx.get("headlines_used", [])
    headlines_dropped = ctx.get("headlines_dropped", [])

    if prices_used:
        st.markdown("**Prices**")
        for ticker_sym, pdata in prices_used.items():
            price = pdata.get("price", "?")
            change = pdata.get("change_pct", 0)
            colour = "#22c55e" if change >= 0 else "#ef4444"
            st.markdown(
                f'&nbsp;&nbsp;{ticker_sym}: **${price}** '
                f'<span style="color:{colour}">{change:+.1f}%</span>',
                unsafe_allow_html=True,
            )

    if headlines_used:
        top, rest = headlines_used[:2], headlines_used[2:]

        def _headline_row(hl: dict) -> str:
            source = hl.get("source", "?")
            headline = hl.get("headline", "")
            score = hl.get("score", hl.get("relevance"))
            short = (headline[:22] + "...") if len(headline) > 22 else headline
            score_html = (
                f'<span style="color:#94a3b8;margin-left:6px;">{score:.2f}</span>'
                if score is not None else ""
            )
            return (
                f'<div style="margin:3px 0;font-size:0.85rem;">'
                f'<span style="color:#64748b;">{source}</span>'
                f' <span style="color:#475569;">·</span>'
                f' <span style="color:#cbd5e1;">{short}</span>'
                f'{score_html}</div>'
            )

        for hl in top:
            st.markdown(_headline_row(hl), unsafe_allow_html=True)

        if rest:
            with st.expander(f"+{len(rest)} more headlines kept"):
                for hl in rest:
                    st.markdown(_headline_row(hl), unsafe_allow_html=True)

    if not prices_used and not headlines_used:
        st.caption("No dynamic context recorded.")

    if headlines_dropped:
        items = []
        for d in headlines_dropped[:4]:
            if not isinstance(d, dict):
                items.append(str(d))
                continue
            source = d.get("source", "?")
            headline = d.get("headline", "")
            reason = d.get("reason", "")
            rank = d.get("rank")
            short = (headline[:28] + "...") if len(headline) > 28 else headline
            label = f"{source} {short}".strip() if short else source
            detail_parts = []
            if rank:
                detail_parts.append(f"rank {rank}")
            if reason:
                detail_parts.append(reason)
            if detail_parts:
                label += f" ({', '.join(detail_parts)})"
            items.append(label)
        _dropped_box(
            f"• {len(headlines_dropped)} headline{'s' if len(headlines_dropped) > 1 else ''} "
            f"dropped: {', '.join(items)}"
        )
        token_drops = [
            d for d in headlines_dropped
            if isinstance(d, dict) and "token" in d.get("reason", "").lower()
        ]
        if token_drops:
            example = token_drops[0]
            name = (example.get("source", "") + " " + example.get("headline", "")[:20]).strip()
            _info_box(
                "Why this matters",
                f"{name} might have changed the signal but lost to token budget. "
                "Now you can spot context-window pressure.",
                new=False,
            )

    _step_footer()

    # ── Step 6: GPT-5.2 Output ────────────────────────────────────────────────
    _step_header(6, "GPT-5.2 Output")

    ticker = signal.get("ticker", "?")
    action = signal.get("action", "?")
    confidence = signal.get("confidence", 0)
    novelty_val = signal.get("novelty", 0)
    is_catalyst = signal.get("is_catalyst", False)
    horizon = signal.get("horizon", "?")
    reasoning = signal.get("reasoning", "")
    analysis = signal.get("analysis", "")

    action_colour = "#22c55e" if action == "BUY" else "#ef4444" if action == "SELL" else "#eab308"

    short_reasoning = ""
    if reasoning:
        short_reasoning = (reasoning[:120] + "...") if len(reasoning) > 120 else reasoning

    st.markdown(
        f"""<div style="background:#1a1a2e;border-radius:8px;padding:12px;margin:8px 0;">
        <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center;">
            <strong style="color:{action_colour};font-size:1.1rem;">{action} {ticker}</strong>
            <span>conf {confidence:.0%}</span>
            <span>novelty {novelty_val:.0%}</span>
            <span>catalyst: {'Yes' if is_catalyst else 'No'}</span>
            <span>horizon: {horizon}</span>
        </div>
        {f'<p style="margin:8px 0 0;color:#94a3b8;font-size:0.85rem;">{short_reasoning}</p>' if short_reasoning else ""}
        </div>""",
        unsafe_allow_html=True,
    )

    if chain:
        st.markdown("**Causal Chain**")
        for label, key in [
            ("Event", "event"), ("Mechanism", "mechanism"),
            ("Asset Impact", "asset_impact"), ("Uncertainty", "uncertainty"),
        ]:
            text = chain.get(key, "")
            if text:
                st.markdown(
                    f"""<div style="border-left:2px solid #22c55e;padding:4px 10px;margin:4px 0;">
                    <small style="color:#94a3b8">{label}</small><br>{text}
                    </div>""",
                    unsafe_allow_html=True,
                )

    if analysis:
        with st.expander("Full Analysis"):
            st.write(analysis)

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    _info_box("Sandbox controls", "change inputs and re-run without touching production")
    col1, col2 = st.columns(2)
    with col1:
        st.button(
            "Edit prompt + re-run ↗",
            key=f"sandbox_edit_{signal.get('tweet_id', '')}",
            use_container_width=True,
        )
    with col2:
        st.button(
            "Compare signals ↗",
            key=f"sandbox_compare_{signal.get('tweet_id', '')}",
            use_container_width=True,
        )

    _step_footer()

    # ── Step 7: Written to DynamoDB ───────────────────────────────────────────
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
