"""Tests for the prompts extractor + loader."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.extract_prompts import extract, _infer_agent, _infer_role  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = REPO_ROOT / "data" / "prompts_snapshot.json"


def test_role_inference():
    assert _infer_role("RESEARCH_SYSTEM_PROMPT") == "system"
    assert _infer_role("MERGER_DEV") == "developer"
    assert _infer_role("USER_TEMPLATE") == "user"
    assert _infer_role("NEWS_ENRICHMENT_USER") == "user"
    assert _infer_role("KEYWORD_GEN_SYSTEM") == "system"
    assert _infer_role("BOGUS_NAME") == "other"


def test_agent_inference():
    assert _infer_agent("RESEARCH_SYMBOL_DEV") == "research_symbol"
    assert _infer_agent("NEWS_ENRICHMENT_DEV") == "news_enrichment"
    assert _infer_agent("SYSTEM_PROMPT") == "main"
    assert _infer_agent("HUMOR_USER") == "humor"


def test_extract_on_synthetic_source(tmp_path):
    src = tmp_path / "prompts.py"
    src.write_text(
        '"""doc"""\n'
        '_SHARED = "shared block, long enough to count as a prompt when combined"\n'
        'FAST_DEV = _SHARED + "\\nfast-specific tail content — more words to pass length threshold"\n'
        'SLOW_DEV = _SHARED + "\\nslow-specific content — even more words for the minimum-length check"\n'
        'USER_TEMPLATE = """This is the user template body with enough characters to count."""\n'
        'TINY_STR = "skip me"\n'
    )
    entries = extract(src)
    names = [e["name"] for e in entries]
    assert "FAST_DEV" in names
    assert "SLOW_DEV" in names
    assert "USER_TEMPLATE" in names
    assert "_SHARED" not in names       # private, excluded
    assert "TINY_STR" not in names      # too short
    fast = next(e for e in entries if e["name"] == "FAST_DEV")
    assert "shared block" in fast["text"]
    assert "fast-specific tail" in fast["text"]


def test_snapshot_has_expected_shape():
    """The committed snapshot must exist and have the documented shape."""
    assert SNAPSHOT.exists(), "prompts_snapshot.json missing — run scripts/extract_prompts.py"
    data = json.loads(SNAPSHOT.read_text())
    assert "prompts" in data
    assert isinstance(data["prompts"], list)
    assert data["extracted_count"] == len(data["prompts"])
    for p in data["prompts"]:
        assert {"name", "agent", "role", "line", "text", "github_url"} <= p.keys()
        assert p["github_url"].startswith("https://github.com/")
        assert p["text"].strip()


def test_snapshot_covers_key_prompts():
    """Sanity check: the real snapshot must contain the well-known prompts."""
    data = json.loads(SNAPSHOT.read_text())
    names = {p["name"] for p in data["prompts"]}
    # These must always be in prompts.py — if one disappears, either it was
    # genuinely removed or the extractor regressed.
    for essential in ("SYSTEM_PROMPT", "FAST_DEV", "SLOW_DEV", "USER_TEMPLATE", "MERGER_SYSTEM_PROMPT"):
        assert essential in names, f"expected prompt {essential!r} missing from snapshot"


if __name__ == "__main__":
    import traceback
    import tempfile, types
    tests = [
        test_role_inference, test_agent_inference, test_snapshot_has_expected_shape,
        test_snapshot_covers_key_prompts,
    ]
    # tmp_path test needs a directory
    def _run_tmp():
        with tempfile.TemporaryDirectory() as d:
            test_extract_on_synthetic_source(Path(d))
    tests.append(_run_tmp)

    failed = 0
    for t in tests:
        name = getattr(t, "__name__", str(t))
        try:
            t()
            print(f"PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}: {e}")
            traceback.print_exc()
        except Exception as e:
            failed += 1
            print(f"ERROR {name}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
