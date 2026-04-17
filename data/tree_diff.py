"""Pure diff between two RAG tree snapshots.

Input: two tree dicts with the same shape tree_loader.load_tree() returns —
``{symbols, themes, macros, relations}``.

Output: a structured ``TreeDiff`` dict describing what was added / removed /
changed between ``old`` and ``new``. Pure function, no I/O — feed it fixtures
and it's fully testable.
"""

from __future__ import annotations

from typing import Any


def _dict_diff_list(old: list, new: list) -> dict:
    """Return {added: [...], removed: [...]} for order-insensitive list diff."""
    old_set = {str(x) for x in (old or [])}
    new_set = {str(x) for x in (new or [])}
    return {
        "added": sorted(new_set - old_set),
        "removed": sorted(old_set - new_set),
    }


def _scalar_changed(old: Any, new: Any) -> dict | None:
    """Return {old, new} if they differ, else None.

    Treats None as "absent" (normalized to empty string) so a field that
    transitions between missing and empty-string is a no-op. Other falsy
    values (0, False, []) are preserved verbatim — critical if scalar_fields
    ever includes a numeric or boolean field, since ``old or ""`` would
    otherwise silently coerce a real ``0`` or ``False`` to ``""``.
    """
    a = "" if old is None else old
    b = "" if new is None else new
    if a == b:
        return None
    return {"old": a, "new": b}


def _diff_entity(
    old: dict | None,
    new: dict | None,
    scalar_fields: tuple[str, ...],
    list_fields: tuple[str, ...],
) -> dict | None:
    """Return a diff for one entity, or None if nothing changed."""
    if old is None and new is None:
        return None
    if old is None or new is None:
        # Caller handles added/removed at the container level
        return None

    changes: dict = {}
    for field in scalar_fields:
        scalar = _scalar_changed(old.get(field), new.get(field))
        if scalar:
            changes[field] = scalar
    for field in list_fields:
        ld = _dict_diff_list(old.get(field, []), new.get(field, []))
        if ld["added"] or ld["removed"]:
            changes[field] = ld

    if not changes:
        return None
    return changes


SYMBOL_SCALARS = ("description", "context_source", "updated_by")
SYMBOL_LISTS = ("keywords", "upside_catalysts", "downside_catalysts")
BRANCH_SCALARS = ("description",)
BRANCH_LISTS = ("keywords", "tailwinds", "headwinds")


def _diff_collection(
    old: dict,
    new: dict,
    scalar_fields: tuple[str, ...],
    list_fields: tuple[str, ...],
) -> dict:
    """Diff a {id: entity} collection (symbols, themes, or macros)."""
    old_ids = set(old.keys())
    new_ids = set(new.keys())

    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    changed = []
    for entity_id in sorted(old_ids & new_ids):
        d = _diff_entity(old.get(entity_id), new.get(entity_id), scalar_fields, list_fields)
        if d:
            changed.append({"id": entity_id, **d})

    return {"added": added, "removed": removed, "changed": changed}


def _diff_relation_map(old: dict, new: dict) -> dict:
    """Diff a {source_id: [target_ids]} relation map.

    Returns added/removed as list of [source, target] pairs.
    """
    old_edges = {(s, t) for s, ts in (old or {}).items() for t in (ts or [])}
    new_edges = {(s, t) for s, ts in (new or {}).items() for t in (ts or [])}
    return {
        "added": sorted([list(e) for e in (new_edges - old_edges)]),
        "removed": sorted([list(e) for e in (old_edges - new_edges)]),
    }


def diff_trees(old: dict, new: dict) -> dict:
    """Produce a structured diff between two tree snapshots.

    Returns:
        {
          "symbols":   {"added": [...], "removed": [...], "changed": [{"id": ..., <field>: <change>}]},
          "themes":    <same shape>,
          "macros":    <same shape>,
          "relations": {"symbol_to_themes": {"added": [[sym, theme], ...], "removed": [...]}, ...},
          "summary":   {aggregate counts},
          "old_snapshot_at": str, "new_snapshot_at": str,
        }
    """
    old = old or {}
    new = new or {}

    symbols = _diff_collection(
        old.get("symbols", {}) or {},
        new.get("symbols", {}) or {},
        SYMBOL_SCALARS,
        SYMBOL_LISTS,
    )
    themes = _diff_collection(
        old.get("themes", {}) or {},
        new.get("themes", {}) or {},
        BRANCH_SCALARS,
        BRANCH_LISTS,
    )
    macros = _diff_collection(
        old.get("macros", {}) or {},
        new.get("macros", {}) or {},
        BRANCH_SCALARS,
        BRANCH_LISTS,
    )

    old_rel = old.get("relations", {}) or {}
    new_rel = new.get("relations", {}) or {}
    relations = {
        "symbol_to_themes": _diff_relation_map(old_rel.get("symbol_to_themes", {}), new_rel.get("symbol_to_themes", {})),
        "symbol_to_macros": _diff_relation_map(old_rel.get("symbol_to_macros", {}), new_rel.get("symbol_to_macros", {})),
        "theme_to_macros": _diff_relation_map(old_rel.get("theme_to_macros", {}), new_rel.get("theme_to_macros", {})),
    }

    # Summary counts
    def _count_kw_added(changed_list, field="keywords"):
        return sum(len(c.get(field, {}).get("added", [])) for c in changed_list if isinstance(c.get(field), dict))

    def _count_kw_removed(changed_list, field="keywords"):
        return sum(len(c.get(field, {}).get("removed", [])) for c in changed_list if isinstance(c.get(field), dict))

    summary = {
        "symbols_added": len(symbols["added"]),
        "symbols_removed": len(symbols["removed"]),
        "symbols_changed": len(symbols["changed"]),
        "themes_changed": len(themes["changed"]) + len(themes["added"]) + len(themes["removed"]),
        "macros_changed": len(macros["changed"]) + len(macros["added"]) + len(macros["removed"]),
        "symbol_keywords_added": _count_kw_added(symbols["changed"], "keywords"),
        "symbol_keywords_removed": _count_kw_removed(symbols["changed"], "keywords"),
        "upside_catalysts_added": _count_kw_added(symbols["changed"], "upside_catalysts"),
        "downside_catalysts_added": _count_kw_added(symbols["changed"], "downside_catalysts"),
        "relations_added": sum(len(r["added"]) for r in relations.values()),
        "relations_removed": sum(len(r["removed"]) for r in relations.values()),
    }

    return {
        "symbols": symbols,
        "themes": themes,
        "macros": macros,
        "relations": relations,
        "summary": summary,
        "old_snapshot_at": old.get("snapshot_at", ""),
        "new_snapshot_at": new.get("snapshot_at", ""),
    }
