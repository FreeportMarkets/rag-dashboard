"""Extract LLM prompts from Twitter_scraper's config/prompts.py into a JSON snapshot.

Usage:
    python3 scripts/extract_prompts.py \
        --source ../Twitter_scraper/config/prompts.py \
        --out data/prompts_snapshot.json

Idempotent — run whenever prompts.py changes. Commit the resulting JSON.

Why a snapshot and not a live DDB read:
- prompts.py is in a private repo, no public raw URL
- Prompts rarely change; a checked-in snapshot is the simplest truthful state
- Upgrade path: swap the JSON for a DDB read once prompts are live-edited
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path


# Minimum length to consider a string constant a "prompt" (filters out short helpers).
MIN_PROMPT_LEN = 60


# Map constant-name suffix / pattern → role.
ROLE_SUFFIX = {
    "SYSTEM_PROMPT": "system",
    "SYSTEM": "system",
    "DEV": "developer",
    "USER": "user",
    "TEMPLATE": "user",
}


def _infer_role(name: str) -> str:
    for suffix, role in ROLE_SUFFIX.items():
        if name.endswith(suffix):
            return role
    return "other"


def _infer_agent(name: str) -> str:
    """Strip role suffix to infer the agent/use-case."""
    for suffix in sorted(ROLE_SUFFIX, key=len, reverse=True):
        if name.endswith(suffix):
            base = name[: -len(suffix)].rstrip("_")
            if base:
                return base.lower()
            return "main"
    return "other"


_PURPOSE_MAP = {
    # Standalone (monitor.py — main tweet analysis)
    "SYSTEM_PROMPT":              "Main tweet analysis — formatting + ticker rules + output constraints",
    "FAST_DEV":                   "Fast-path tweet analysis (wire accounts + keyword hit)",
    "SLOW_DEV":                   "Slow-path tweet analysis (with web_search_preview tool)",
    "USER_TEMPLATE":              "Tweet payload template — evaluation framework + tweet text",
    "HUMOR_DEV":                  "Humor/culture tweet analysis",
    "HUMOR_USER":                 "Humor/culture user template",
    # News agent
    "NEWS_SYSTEM_PROMPT":         "News agent — guides headline ingestion + structuring",
    "NEWS_ENRICHMENT_DEV":        "News enrichment — extract catalysts from headlines",
    "NEWS_ENRICHMENT_USER":       "News enrichment user payload",
    "NEWS_DESCRIPTION_REWRITE_DEV": "Rewrites symbol descriptions using fresh headlines",
    # Research agent
    "RESEARCH_SYSTEM_PROMPT":     "Research agent — deep research rules",
    "RESEARCH_SYMBOL_DEV":        "Research agent — per-symbol research prompt",
    "RESEARCH_THEME_DEV":         "Research agent — per-theme research prompt",
    "RESEARCH_MACRO_DEV":         "Research agent — per-macro research prompt",
    "MANUAL_THESIS_DEV":          "Manual research watcher — convert thesis doc to structured context",
    # Merger agent
    "MERGER_SYSTEM_PROMPT":       "Merger agent — approve/reject merges of live layer into static config",
    "MERGER_DEV":                 "Merger agent — merge decision prompt",
    # Keyword + curator
    "KEYWORD_GEN_SYSTEM":         "Keyword generator — produces stock keywords for a ticker",
    "CURATOR_SYSTEM_PROMPT":      "Curator agent — smart pruning / dedup of live entries",
}


def _cleanup_name(name: str) -> str:
    return name.replace("_", " ").title()


def extract(source: Path) -> list[dict]:
    """AST-parse ``source`` and return every top-level str constant >= MIN_PROMPT_LEN chars.

    Two-pass: first resolve ALL str assignments (including private ``_SHARED_*``
    building blocks) into ``resolved``. Then build the output list, skipping
    private names but resolving public names that reference them.
    """
    src = source.read_text()
    tree = ast.parse(src)
    resolved: dict[str, str] = {}
    out: list[dict] = []

    # Pass 1: resolve every str-valued assign into the cache.
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        value = _resolve_str(node.value, resolved)
        if value is not None:
            resolved[node.targets[0].id] = value

    # Pass 2: emit public prompts only.
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name.startswith("_"):
            continue  # private helpers already folded into public prompts
        value = resolved.get(name)
        if value is None or len(value) < MIN_PROMPT_LEN:
            continue
        out.append({
            "name": name,
            "display_name": _cleanup_name(name),
            "agent": _infer_agent(name),
            "role": _infer_role(name),
            "purpose": _PURPOSE_MAP.get(name, ""),
            "line": node.lineno,
            "char_count": len(value),
            "text": value,
        })

    return out


def _resolve_str(node: ast.expr, resolved: dict[str, str]) -> str | None:
    """Resolve AST expression to a literal string if possible."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _resolve_str(node.left, resolved)
        right = _resolve_str(node.right, resolved)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.Name) and node.id in resolved:
        return resolved[node.id]
    return None


def build_github_urls(entries: list[dict], repo: str, branch: str, path: str) -> None:
    base = f"https://github.com/{repo}/blob/{branch}/{path}"
    for e in entries:
        e["github_url"] = f"{base}#L{e['line']}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Path to prompts.py")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--repo", default="FreeportMarkets/Twitter_scraper", help="GitHub repo for URL links")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--repo-path", default="config/prompts.py", help="Path of the file within the repo (for URLs)")
    args = parser.parse_args()

    src = Path(args.source).resolve()
    entries = extract(src)
    build_github_urls(entries, args.repo, args.branch, args.repo_path)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "source_file": args.repo_path,
        "source_repo": args.repo,
        "source_branch": args.branch,
        "extracted_count": len(entries),
        "prompts": entries,
    }, indent=2))
    print(f"Extracted {len(entries)} prompts → {out}")
    for e in entries:
        print(f"  {e['agent']:<14} {e['role']:<10} {e['name']:<30} {e['char_count']:>5} chars  L{e['line']}")


if __name__ == "__main__":
    main()
