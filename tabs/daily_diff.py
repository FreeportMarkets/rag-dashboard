"""Daily Diff tab — what changed in the tree from one day to the next."""

from __future__ import annotations

import streamlit as st

from data.tree_diff import diff_trees
from data.tree_history import list_snapshot_dates, load_snapshot


def _metric_row(summary: dict) -> None:
    cols = st.columns(6)
    items = [
        ("Symbols added", summary["symbols_added"]),
        ("Symbols removed", summary["symbols_removed"]),
        ("Symbols changed", summary["symbols_changed"]),
        ("Themes changed", summary["themes_changed"]),
        ("Macros changed", summary["macros_changed"]),
        ("Relations Δ", summary["relations_added"] + summary["relations_removed"]),
    ]
    for col, (label, value) in zip(cols, items):
        col.metric(label, value)

    cols = st.columns(4)
    cols[0].metric("Keywords added (symbols)", summary["symbol_keywords_added"])
    cols[1].metric("Keywords removed (symbols)", summary["symbol_keywords_removed"])
    cols[2].metric("Upside catalysts added", summary["upside_catalysts_added"])
    cols[3].metric("Downside catalysts added", summary["downside_catalysts_added"])


def _render_list(title: str, items: list[str]) -> None:
    if not items:
        return
    with st.expander(f"{title} ({len(items)})"):
        st.write(", ".join(items))


def _render_changed_entities(title: str, changed: list[dict], kind: str) -> None:
    if not changed:
        return
    with st.expander(f"{title} ({len(changed)})"):
        for entry in changed:
            entity_id = entry.pop("id")
            st.markdown(f"**{entity_id}** _{kind}_")
            if "description" in entry:
                st.markdown("*Description*")
                st.markdown(f":red[−] {entry['description']['old'] or '_(empty)_'}")
                st.markdown(f":green[+] {entry['description']['new'] or '_(empty)_'}")
            for list_field in ("keywords", "tailwinds", "headwinds", "upside_catalysts", "downside_catalysts"):
                change = entry.get(list_field)
                if not change:
                    continue
                if change.get("added"):
                    st.markdown(f":green[+ {list_field}:] {', '.join(change['added'])}")
                if change.get("removed"):
                    st.markdown(f":red[− {list_field}:] {', '.join(change['removed'])}")
            for scalar in ("context_source", "updated_by"):
                if scalar in entry:
                    st.markdown(f"*{scalar}:* `{entry[scalar]['old']}` → `{entry[scalar]['new']}`")
            st.divider()


def _render_relation_diff(title: str, rel: dict) -> None:
    if not rel["added"] and not rel["removed"]:
        return
    with st.expander(f"{title}  (+{len(rel['added'])} / -{len(rel['removed'])})"):
        if rel["added"]:
            st.markdown("**Added edges**")
            for edge in rel["added"][:200]:
                st.markdown(f"- `{edge[0]}` → `{edge[1]}`")
        if rel["removed"]:
            st.markdown("**Removed edges**")
            for edge in rel["removed"][:200]:
                st.markdown(f"- `{edge[0]}` → `{edge[1]}`")


def render():
    st.markdown("## Daily Diff")
    st.caption(
        "What changed in the RAG context tree from one day's snapshot to the next. "
        "The merger agent writes a dated snapshot at 06:00 UTC daily."
    )

    dates = list_snapshot_dates()
    if len(dates) < 1:
        st.info("No daily snapshots yet. First archive writes at the next merger run (06:00 UTC / 2 AM EDT).")
        return
    if len(dates) < 2:
        st.info(
            f"Only one daily snapshot available ({dates[0]}). Need at least two to diff. "
            "Tomorrow's run will produce the first comparison."
        )
        return

    col_a, col_b = st.columns(2)
    with col_a:
        new_date = st.selectbox("New snapshot", dates, index=0, key="diff_new")
    with col_b:
        # Default: the snapshot right before the selected `new`
        older = [d for d in dates if d < new_date]
        default_idx = 0 if older else 0
        old_date = st.selectbox("Compare to", older or dates[1:], index=default_idx, key="diff_old")

    old_tree = load_snapshot(old_date)
    new_tree = load_snapshot(new_date)
    if not old_tree or not new_tree:
        st.error("One of the selected snapshots is empty.")
        return

    d = diff_trees(old_tree, new_tree)
    _metric_row(d["summary"])
    st.divider()

    _render_list("Symbols added", d["symbols"]["added"])
    _render_list("Symbols removed", d["symbols"]["removed"])
    _render_changed_entities("Symbols changed", d["symbols"]["changed"], "symbol")
    _render_list("Themes added", d["themes"]["added"])
    _render_list("Themes removed", d["themes"]["removed"])
    _render_changed_entities("Themes changed", d["themes"]["changed"], "theme")
    _render_list("Macros added", d["macros"]["added"])
    _render_list("Macros removed", d["macros"]["removed"])
    _render_changed_entities("Macros changed", d["macros"]["changed"], "macro")

    st.markdown("### Relation changes")
    _render_relation_diff("Symbol → Theme", d["relations"]["symbol_to_themes"])
    _render_relation_diff("Symbol → Macro", d["relations"]["symbol_to_macros"])
    _render_relation_diff("Theme → Macro", d["relations"]["theme_to_macros"])
