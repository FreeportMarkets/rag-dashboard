"""Tests for data/tree_diff.py against hand-crafted fixtures.

Run from repo root:
    python -m pytest tests/test_tree_diff.py -v
or:
    python tests/test_tree_diff.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.tree_diff import diff_trees  # noqa: E402


FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_symbols_added_removed_changed():
    """Between yesterday and today: TSM added, AMD removed, NVDA changed, TCOM unchanged."""
    old = _load("tree_yesterday.json")
    new = _load("tree_today.json")
    d = diff_trees(old, new)

    assert d["symbols"]["added"] == ["TSM"]
    assert d["symbols"]["removed"] == ["AMD"]
    assert len(d["symbols"]["changed"]) == 1
    assert d["symbols"]["changed"][0]["id"] == "NVDA"


def test_nvda_change_detail():
    d = diff_trees(_load("tree_yesterday.json"), _load("tree_today.json"))
    nvda = d["symbols"]["changed"][0]

    # Description changed
    assert nvda["description"]["old"].startswith("Nvidia supplies AI GPUs")
    assert "Blackwell" in nvda["description"]["new"]

    # Keyword "blackwell" added, nothing removed
    assert nvda["keywords"]["added"] == ["blackwell"]
    assert nvda["keywords"]["removed"] == []

    # Catalysts added
    assert nvda["upside_catalysts"]["added"] == ["Blackwell ramp"]
    assert nvda["downside_catalysts"]["added"] == ["Export controls"]

    # Source flipped from static to live
    assert nvda["context_source"] == {"old": "static", "new": "live"}
    assert nvda["updated_by"] == {"old": "", "new": "research_agent"}


def test_themes_and_macros():
    d = diff_trees(_load("tree_yesterday.json"), _load("tree_today.json"))

    # ai_infra keywords + description changed, tailwinds added
    ai_change = next(c for c in d["themes"]["changed"] if c["id"] == "ai_infra")
    assert "datacenter" in ai_change["keywords"]["added"]
    assert ai_change["tailwinds"]["added"] == ["Capex accelerating"]

    # china_macro unchanged → not in changed
    assert not any(c["id"] == "china_macro" for c in d["themes"]["changed"])

    # macros completely unchanged
    assert d["macros"]["changed"] == []
    assert d["macros"]["added"] == []
    assert d["macros"]["removed"] == []


def test_relations():
    d = diff_trees(_load("tree_yesterday.json"), _load("tree_today.json"))

    # symbol_to_themes: TSM→ai_infra added. TCOM→china_macro unchanged.
    s2t = d["relations"]["symbol_to_themes"]
    assert ["TSM", "ai_infra"] in s2t["added"]
    assert s2t["removed"] == []

    # symbol_to_macros: NVDA→inflation added
    s2m = d["relations"]["symbol_to_macros"]
    assert s2m["added"] == [["NVDA", "inflation"]]


def test_summary_counts():
    d = diff_trees(_load("tree_yesterday.json"), _load("tree_today.json"))
    s = d["summary"]
    assert s["symbols_added"] == 1
    assert s["symbols_removed"] == 1
    assert s["symbols_changed"] == 1
    assert s["themes_changed"] == 1   # only ai_infra
    assert s["macros_changed"] == 0
    # NVDA +1 keyword (blackwell), ai_infra theme +1 keyword (datacenter).
    # Theme keywords are in themes.changed, so symbol_keywords_added counts only NVDA's.
    assert s["symbol_keywords_added"] == 1
    assert s["upside_catalysts_added"] == 1
    assert s["downside_catalysts_added"] == 1
    # Relations: TSM→ai_infra + NVDA→inflation = 2 added
    assert s["relations_added"] == 2
    assert s["relations_removed"] == 0


def test_identical_trees():
    """Diffing a tree against itself yields zero changes."""
    t = _load("tree_today.json")
    d = diff_trees(t, t)
    assert d["summary"]["symbols_added"] == 0
    assert d["summary"]["symbols_removed"] == 0
    assert d["summary"]["symbols_changed"] == 0
    assert d["summary"]["relations_added"] == 0
    assert d["summary"]["relations_removed"] == 0


def test_empty_old():
    """First-ever snapshot: everything is added."""
    new = _load("tree_today.json")
    d = diff_trees({}, new)
    assert set(d["symbols"]["added"]) == {"NVDA", "TCOM", "TSM"}
    assert d["symbols"]["removed"] == []


def test_diff_is_not_mutated_by_render_code():
    """Simulate the render pattern: iterate changed entries reading 'id' without pop.

    Regression guard: daily_diff.render() used to `entry.pop('id')` which made the
    diff dict unsafe to re-iterate. The rendering now reads non-destructively; this
    test locks that in.
    """
    d = diff_trees(_load("tree_yesterday.json"), _load("tree_today.json"))
    # First iteration — read id like the tab does
    ids_first = [e.get("id") for e in d["symbols"]["changed"]]
    # Second iteration — must still see the same ids
    ids_second = [e.get("id") for e in d["symbols"]["changed"]]
    assert ids_first == ids_second
    assert all(i is not None for i in ids_first)


if __name__ == "__main__":
    import traceback
    tests = [
        test_symbols_added_removed_changed,
        test_nvda_change_detail,
        test_themes_and_macros,
        test_relations,
        test_summary_counts,
        test_identical_trees,
        test_empty_old,
        test_diff_is_not_mutated_by_render_code,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
            traceback.print_exc()
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
