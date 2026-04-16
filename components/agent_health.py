"""Agent health cards and tree stats overview."""

from datetime import datetime, timezone

import streamlit as st


def _time_ago(iso_str: str) -> str:
    """Convert an ISO timestamp to a human-readable 'X ago' string."""
    try:
        ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - ts
        if delta.total_seconds() < 60:
            return "just now"
        if delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)}m ago"
        if delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() / 3600)}h ago"
        return f"{delta.days}d ago"
    except (ValueError, TypeError):
        return "unknown"


def _status_dot(iso_str: str) -> str:
    """Return a coloured dot based on recency of last_run."""
    try:
        ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        if age.total_seconds() < 3600:
            return '<span style="color:#22c55e;font-size:1.2rem;">&#9679;</span>'
        if age.total_seconds() < 86400:
            return '<span style="color:#eab308;font-size:1.2rem;">&#9679;</span>'
        return '<span style="color:#ef4444;font-size:1.2rem;">&#9679;</span>'
    except (ValueError, TypeError):
        return '<span style="color:#6b7280;font-size:1.2rem;">&#9679;</span>'


def _render_agent_card(name: str, agent_data: dict, schedule: str):
    """Render a single agent health card."""
    last_run = agent_data.get("last_run", "")
    dot = _status_dot(last_run)
    ago = _time_ago(last_run)

    display_name = name.replace("_", " ").title()

    # Gather extra stats from agent data (varies per agent)
    extra_lines = []
    for key, val in agent_data.items():
        if key == "last_run":
            continue
        label = key.replace("_", " ").title()
        extra_lines.append(f"<small style='color:#94a3b8'>{label}: {val}</small>")

    extras_html = "<br>".join(extra_lines) if extra_lines else ""

    st.markdown(
        f"""<div style="background:#1a1a2e;border:1px solid #334155;border-radius:8px;padding:12px;margin:4px 0;">
        {dot} <strong>{display_name}</strong>
        <br><small style="color:#64748b">{schedule} &middot; {ago}</small>
        <br>{extras_html}
        </div>""",
        unsafe_allow_html=True,
    )


def _freshness_breakdown(symbols: dict) -> dict:
    """Count symbols by freshness bucket."""
    counts = {"live": 0, "static": 0, "stale": 0}
    for sym_data in symbols.values():
        updated_at = sym_data.get("updated_at")
        if not updated_at:
            counts["stale"] += 1
            continue
        try:
            ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - ts
            if age.days <= 1:
                counts["live"] += 1
            elif age.days <= 7:
                counts["static"] += 1
            else:
                counts["stale"] += 1
        except (ValueError, TypeError):
            counts["stale"] += 1
    return counts


def render_agent_health(tree: dict):
    """Render agent health cards and tree statistics."""
    agent_state = tree.get("agent_state", {})
    stats = tree.get("stats", {})
    symbols = tree.get("symbols", {})

    st.markdown("---")
    st.markdown("### Agent Health")

    # Daily agents
    daily_agents = {
        "news_agent": "Daily",
        "research_agent": "Daily",
        "curator_agent": "Daily",
        "merger_agent": "Daily",
    }

    # Continuous agents
    continuous_agents = {
        "price_agent": "Continuous",
        "manual_research_watcher": "Continuous",
    }

    cols = st.columns(4)
    for i, (agent_name, schedule) in enumerate(daily_agents.items()):
        with cols[i]:
            data = agent_state.get(agent_name, {})
            _render_agent_card(agent_name, data, schedule)

    cols2 = st.columns(4)
    for i, (agent_name, schedule) in enumerate(continuous_agents.items()):
        with cols2[i]:
            data = agent_state.get(agent_name, {})
            _render_agent_card(agent_name, data, schedule)

    # Stats
    st.markdown("### Tree Stats")

    freshness = _freshness_breakdown(symbols)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        total_sym = stats.get("total_symbols", len(symbols))
        st.markdown(
            f"""<div style="background:#1a1a2e;border-left:3px solid #6366f1;padding:12px;border-radius:4px;">
            <div style="color:#94a3b8;font-size:0.8rem;">Symbols</div>
            <div style="font-size:1.5rem;font-weight:700;">{total_sym}</div>
            <small style="color:#22c55e">{freshness['live']} live</small> &middot;
            <small style="color:#eab308">{freshness['static']} static</small> &middot;
            <small style="color:#ef4444">{freshness['stale']} stale</small>
            </div>""",
            unsafe_allow_html=True,
        )

    with c2:
        total_kw = stats.get("total_keywords", 0)
        st.markdown(
            f"""<div style="background:#1a1a2e;border-left:3px solid #6366f1;padding:12px;border-radius:4px;">
            <div style="color:#94a3b8;font-size:0.8rem;">Keywords</div>
            <div style="font-size:1.5rem;font-weight:700;">{total_kw}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c3:
        themes = tree.get("themes", {})
        macros = tree.get("macros", {})
        st.markdown(
            f"""<div style="background:#1a1a2e;border-left:3px solid #6366f1;padding:12px;border-radius:4px;">
            <div style="color:#94a3b8;font-size:0.8rem;">Themes + Macros</div>
            <div style="font-size:1.5rem;font-weight:700;">{len(themes)} + {len(macros)}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    with c4:
        snapshot_time = stats.get("snapshot_time", stats.get("last_updated", "unknown"))
        st.markdown(
            f"""<div style="background:#1a1a2e;border-left:3px solid #6366f1;padding:12px;border-radius:4px;">
            <div style="color:#94a3b8;font-size:0.8rem;">Snapshot</div>
            <div style="font-size:1rem;font-weight:700;">{str(snapshot_time)[:19]}</div>
            </div>""",
            unsafe_allow_html=True,
        )
