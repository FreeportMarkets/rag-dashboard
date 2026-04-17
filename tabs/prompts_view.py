"""Prompts tab — view every LLM prompt used by the Twitter_scraper agents."""

from __future__ import annotations

import streamlit as st

from data.prompts_loader import group_by_agent, load_prompts


ROLE_BADGE = {
    "system": ("#3b82f6", "SYSTEM"),
    "developer": ("#a855f7", "DEV"),
    "user": ("#22c55e", "USER"),
    "other": ("#64748b", "OTHER"),
}


def _render_prompt(prompt: dict) -> None:
    color, label = ROLE_BADGE.get(prompt["role"], ROLE_BADGE["other"])
    st.markdown(
        f"### {prompt['display_name']}  "
        f"<span style='background:{color}33;color:{color};border:1px solid {color}66;"
        f"padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600;margin-left:8px;'>"
        f"{label}</span>",
        unsafe_allow_html=True,
    )
    if prompt.get("purpose"):
        st.caption(prompt["purpose"])
    meta = f"**agent:** `{prompt['agent']}` · **line:** L{prompt['line']} · **chars:** {prompt['char_count']:,}"
    if prompt.get("github_url"):
        meta += f" · [View on GitHub ↗]({prompt['github_url']})"
    st.markdown(meta)
    st.code(prompt["text"], language="text")


def render():
    st.markdown("## Prompts")
    data = load_prompts()
    if not data.get("prompts"):
        st.warning("Prompts snapshot missing. Run `scripts/extract_prompts.py` to generate `data/prompts_snapshot.json`.")
        return

    st.caption(
        f"Extracted from `{data.get('source_repo', '?')}:{data.get('source_file', '?')}` "
        f"(branch `{data.get('source_branch', '?')}`) — {data['extracted_count']} prompts. "
        "Snapshot is checked in; regenerate via `scripts/extract_prompts.py` when prompts change."
    )

    groups = group_by_agent(data["prompts"])
    agent_names = list(groups.keys())
    selected_agent = st.selectbox("Agent", agent_names, key="prompts_agent")
    prompts = groups[selected_agent]

    st.divider()
    for p in prompts:
        _render_prompt(p)
        st.divider()
