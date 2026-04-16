"""Build a standalone tree-viz prototype HTML with real DynamoDB tree data embedded.

Run:
    python3 build.py

Output:
    tree_prototype.html — open in browser.

Pulls from /tmp/rag_tree_unwrapped.json (produced by /tmp/inspect_tree.py).
Computes freshness and a clean graph payload the JS consumes directly.

Two views wired together via a toggle:
  - Tree (default): hierarchical sidebar + detail pane
  - Graph: D3 force-directed
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
SRC = Path("/tmp/rag_tree_unwrapped.json")


def _dec(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, dict):
        return {k: _dec(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_dec(x) for x in v]
    return v


def freshness(updated_at: str | None) -> str:
    if not updated_at:
        return "static"
    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - ts).days
        if age <= 1:
            return "fresh"
        if age <= 7:
            return "aging"
        return "stale"
    except Exception:
        return "static"


def build_payload() -> dict:
    raw = _dec(json.loads(SRC.read_text()))
    symbols = raw["symbols"]
    themes = raw["themes"]
    macros = raw["macros"]
    relations = raw["relations"]
    s2t: dict[str, list[str]] = relations.get("symbol_to_themes", {})
    s2m: dict[str, list[str]] = relations.get("symbol_to_macros", {})
    t2m: dict[str, list[str]] = relations.get("theme_to_macros", {})

    # Build reverse: theme/macro -> [symbols]
    theme_to_syms: dict[str, list[str]] = {t: [] for t in themes}
    macro_to_syms: dict[str, list[str]] = {m: [] for m in macros}
    for sym, tlist in s2t.items():
        for t in tlist:
            theme_to_syms.setdefault(t, []).append(sym)
    for sym, mlist in s2m.items():
        for m in mlist:
            macro_to_syms.setdefault(m, []).append(sym)

    branches = []
    for t, td in themes.items():
        branches.append({
            "id": f"theme::{t}",
            "name": t.replace("_", " "),
            "kind": "theme",
            "description": td.get("description", ""),
            "keywords": td.get("keywords", []),
            "tailwinds": td.get("tailwinds", []),
            "headwinds": td.get("headwinds", []),
            "children": theme_to_syms.get(t, []),
            "linked_macros": t2m.get(t, []),
        })
    for m, md in macros.items():
        branches.append({
            "id": f"macro::{m}",
            "name": m.replace("_", " "),
            "kind": "macro",
            "description": md.get("description", ""),
            "keywords": md.get("keywords", []),
            "tailwinds": md.get("tailwinds", []),
            "headwinds": md.get("headwinds", []),
            "children": macro_to_syms.get(m, []),
            "linked_themes": [t for t, ms in t2m.items() if m in ms],
        })

    leaves = []
    for sym, sd in symbols.items():
        leaves.append({
            "id": f"sym::{sym}",
            "name": sym,
            "kind": "symbol",
            "freshness": freshness(sd.get("updated_at")),
            "description": sd.get("description", ""),
            "keywords": sd.get("keywords", []),
            "upside_catalysts": sd.get("upside_catalysts", []),
            "downside_catalysts": sd.get("downside_catalysts", []),
            "updated_at": sd.get("updated_at"),
            "updated_by": sd.get("updated_by"),
            "context_source": sd.get("context_source"),
            "themes": s2t.get(sym, []),
            "macros": s2m.get(sym, []),
        })

    return {
        "branches": branches,
        "leaves": leaves,
        "t2m": t2m,
        "snapshot_at": raw.get("snapshot_at"),
        "freshness_counts": raw.get("freshness", {}),
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>RAG Tree — Prototype</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  :root {
    --bg: #0e1117;
    --panel: #151a24;
    --panel2: #1c2233;
    --border: #26304a;
    --text: #e6e8ee;
    --muted: #8893a5;
    --theme: #3b82f6;
    --macro: #f59e0b;
    --fresh: #22c55e;
    --aging: #eab308;
    --stale: #ef4444;
    --static: #64748b;
    --edge: #2f3b5a;
    --accent: #6366f1;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; height: 100%; overflow: hidden; }
  #app { display: grid; grid-template-columns: 1fr 360px; height: 100vh; }
  #main { position: relative; display: flex; flex-direction: column; overflow: hidden; }
  #toolbar {
    display: flex; gap: 12px; align-items: center;
    padding: 10px 14px; border-bottom: 1px solid var(--border);
    background: var(--panel);
    flex-shrink: 0;
  }
  .toggle {
    display: inline-flex; background: var(--panel2); border: 1px solid var(--border); border-radius: 6px; overflow: hidden;
  }
  .toggle button {
    background: transparent; color: var(--muted); border: 0; padding: 6px 14px;
    font-size: 12px; font-weight: 600; cursor: pointer; letter-spacing: 0.3px;
  }
  .toggle button.active { background: var(--accent); color: #fff; }
  .toolbar-title { font-weight: 600; font-size: 14px; }
  .toolbar-meta { color: var(--muted); font-size: 11px; }
  #search {
    flex: 1; max-width: 320px;
    background: #0b0f18; color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 10px; font-size: 12px;
  }
  #filter {
    background: #0b0f18; color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 8px; font-size: 12px;
  }
  #view-container { flex: 1; position: relative; overflow: hidden; }

  /* Tree view (sidebar list) */
  #tree-view { padding: 8px 0 40px; overflow-y: auto; height: 100%; }
  .tree-section-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 18px; font-size: 11px; letter-spacing: 0.8px; text-transform: uppercase;
    color: var(--muted); border-bottom: 1px solid var(--border);
    background: var(--panel); position: sticky; top: 0; z-index: 1;
  }
  .tree-row {
    cursor: pointer; border-bottom: 1px solid rgba(38,48,74,0.4);
    transition: background 0.1s;
  }
  .tree-row:hover { background: rgba(99,102,241,0.08); }
  .tree-row.active { background: rgba(99,102,241,0.16); }
  .row-summary {
    display: flex; align-items: center; gap: 10px; padding: 10px 18px;
  }
  .caret {
    display: inline-block; width: 10px; color: var(--muted);
    transition: transform 0.15s; flex-shrink: 0;
  }
  .tree-row.expanded .caret { transform: rotate(90deg); }
  .kind-badge {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  }
  .kind-theme { background: var(--theme); }
  .kind-macro { background: var(--macro); }
  .row-name { font-weight: 600; font-size: 13px; flex: 1; }
  .row-meta { color: var(--muted); font-size: 11px; white-space: nowrap; }
  .freshness-bar {
    display: inline-flex; gap: 2px; align-items: center; margin-left: 8px;
  }
  .freshness-bar .seg {
    width: 4px; height: 10px; border-radius: 1px;
  }
  .seg-fresh { background: var(--fresh); }
  .seg-aging { background: var(--aging); }
  .seg-stale { background: var(--stale); }
  .seg-static { background: var(--static); }
  .row-children {
    display: none; padding: 2px 18px 14px 40px; background: rgba(11,15,24,0.4);
  }
  .tree-row.expanded .row-children { display: block; }
  .ticker-chip {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--panel2); border: 1px solid var(--border);
    border-radius: 14px; padding: 3px 10px 3px 6px; margin: 3px 4px 3px 0;
    font-size: 11px; color: var(--text); cursor: pointer;
    transition: border-color 0.1s;
  }
  .ticker-chip:hover { border-color: var(--accent); }
  .ticker-chip.active { border-color: var(--accent); background: rgba(99,102,241,0.2); }
  .chip-dot {
    width: 7px; height: 7px; border-radius: 50%;
  }
  .dot-fresh { background: var(--fresh); }
  .dot-aging { background: var(--aging); }
  .dot-stale { background: var(--stale); }
  .dot-static { background: var(--static); }

  .unlinked-chip-grid {
    display: flex; flex-wrap: wrap; padding: 10px 18px;
    max-height: 300px; overflow-y: auto;
  }

  /* Graph view */
  #graph-view { position: relative; width: 100%; height: 100%; background: var(--bg); }
  #graph-view.hidden { display: none; }
  #tree-view.hidden { display: none; }
  svg { width: 100%; height: 100%; cursor: grab; display: block; }
  svg:active { cursor: grabbing; }
  #legend {
    position: absolute; bottom: 12px; left: 12px;
    background: rgba(21,26,36,0.92);
    border: 1px solid var(--border); border-radius: 8px;
    padding: 10px 12px; font-size: 12px; z-index: 10;
    display: flex; flex-direction: column; gap: 4px;
  }
  .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
  .row { display: flex; align-items: center; }
  .node-label { font-size: 10px; fill: var(--text); pointer-events: none; }
  .node-label.branch { font-size: 12px; font-weight: 600; }
  #tooltip {
    position: absolute; pointer-events: none; z-index: 20;
    background: rgba(21,26,36,0.97); border: 1px solid var(--border);
    padding: 6px 10px; border-radius: 6px; font-size: 11px;
    max-width: 280px; display: none;
  }

  /* Detail pane */
  #detail {
    background: var(--panel);
    border-left: 1px solid var(--border);
    padding: 16px 18px 40px;
    overflow-y: auto;
    font-size: 13px;
  }
  .detail-badge {
    display: inline-block; padding: 2px 8px; border-radius: 99px;
    font-size: 11px; font-weight: 600; margin-right: 4px;
  }
  .badge-theme { background: rgba(59,130,246,0.2); color: var(--theme); border: 1px solid rgba(59,130,246,0.4); }
  .badge-macro { background: rgba(245,158,11,0.2); color: var(--macro); border: 1px solid rgba(245,158,11,0.4); }
  .badge-fresh { background: rgba(34,197,94,0.2); color: var(--fresh); border: 1px solid rgba(34,197,94,0.4); }
  .badge-aging { background: rgba(234,179,8,0.2); color: var(--aging); border: 1px solid rgba(234,179,8,0.4); }
  .badge-stale { background: rgba(239,68,68,0.2); color: var(--stale); border: 1px solid rgba(239,68,68,0.4); }
  .badge-static { background: rgba(100,116,139,0.2); color: var(--static); border: 1px solid rgba(100,116,139,0.4); }
  .detail h2 { font-size: 18px; margin: 4px 0 8px; }
  .detail h3 { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); margin: 16px 0 6px; }
  .detail p { margin: 0 0 6px; line-height: 1.5; }
  .kw-tag {
    display: inline-block; background: var(--panel2); border: 1px solid var(--border);
    padding: 2px 6px; margin: 2px 3px 2px 0; border-radius: 4px; font-size: 11px;
  }
  .catalyst-list { list-style: none; padding: 0; margin: 0; }
  .catalyst-list li { margin: 3px 0; padding-left: 14px; position: relative; line-height: 1.4; }
  .catalyst-list.up li::before { content: "↑"; color: var(--fresh); position: absolute; left: 0; }
  .catalyst-list.down li::before { content: "↓"; color: var(--stale); position: absolute; left: 0; }
  .link-btn {
    display: inline-block; margin: 2px 4px 2px 0; padding: 3px 9px; border-radius: 4px;
    background: var(--panel2); border: 1px solid var(--border); color: var(--text);
    font-size: 11px; cursor: pointer;
  }
  .link-btn:hover { border-color: var(--accent); }
  .meta-line { color: var(--muted); font-size: 11px; margin-top: 2px; }
</style>
</head>
<body>
<div id="app">
  <div id="main">
    <div id="toolbar">
      <div class="toolbar-title">RAG Context Tree</div>
      <div class="toolbar-meta" id="snapshot-meta"></div>
      <div class="toggle">
        <button id="btn-tree" class="active">Tree</button>
        <button id="btn-graph">Graph</button>
      </div>
      <input id="search" placeholder="Search ticker, theme, macro, keyword..." />
      <select id="filter">
        <option value="all">All</option>
        <option value="themes">Themes only</option>
        <option value="macros">Macros only</option>
        <option value="stale">Stale only</option>
      </select>
    </div>
    <div id="view-container">
      <div id="tree-view"></div>
      <div id="graph-view" class="hidden">
        <svg id="svg"></svg>
        <div id="legend">
          <div class="row"><span class="swatch" style="background: var(--theme)"></span>Theme</div>
          <div class="row"><span class="swatch" style="background: var(--macro)"></span>Macro</div>
          <div class="row"><span class="swatch" style="background: var(--fresh)"></span>Symbol · fresh (≤1d)</div>
          <div class="row"><span class="swatch" style="background: var(--aging)"></span>Symbol · aging (≤7d)</div>
          <div class="row"><span class="swatch" style="background: var(--stale)"></span>Symbol · stale (>7d)</div>
          <div class="row"><span class="swatch" style="background: var(--static)"></span>Symbol · never updated</div>
        </div>
        <div id="tooltip"></div>
      </div>
    </div>
  </div>
  <div id="detail" class="detail">
    <p class="meta-line">Click a node for detail.</p>
  </div>
</div>
<script>
const DATA = __DATA__;
const COLORS = { theme: "#3b82f6", macro: "#f59e0b", fresh: "#22c55e", aging: "#eab308", stale: "#ef4444", static: "#64748b" };

const branchById = new Map(DATA.branches.map(b => [b.id, b]));
const leafByName = new Map(DATA.leaves.map(l => [l.name, l]));
const leafById = new Map(DATA.leaves.map(l => [l.id, l]));
const symId = name => `sym::${name}`;

const themes = DATA.branches.filter(b => b.kind === "theme");
const macros = DATA.branches.filter(b => b.kind === "macro");

// Unlinked symbols = symbols with no theme or macro
const linkedSyms = new Set();
DATA.branches.forEach(b => b.children.forEach(c => linkedSyms.add(c)));
const unlinked = DATA.leaves.filter(l => !linkedSyms.has(l.name));

document.getElementById("snapshot-meta").textContent =
  `${DATA.branches.length} branches · ${DATA.leaves.length} symbols · snapshot ${DATA.snapshot_at || "(unknown)"}`;

// State
let view = "tree";                   // "tree" | "graph"
let filterMode = "all";              // all / themes / macros / stale
let searchTerm = "";
let selectedId = null;
const expandedBranches = new Set();  // branch ids expanded in the tree OR graph view

// -------- Freshness summary helpers ---------
function freshSummary(branch) {
  const counts = { fresh: 0, aging: 0, stale: 0, static: 0 };
  branch.children.forEach(sym => {
    const leaf = leafByName.get(sym);
    if (!leaf) return;
    counts[leaf.freshness] = (counts[leaf.freshness] || 0) + 1;
  });
  return counts;
}
function totalFresh(branch) {
  const c = freshSummary(branch);
  return c.fresh;
}

function matchesSearch(text) {
  if (!searchTerm) return true;
  return (text || "").toLowerCase().includes(searchTerm);
}
function branchMatches(b) {
  if (filterMode === "themes" && b.kind !== "theme") return false;
  if (filterMode === "macros" && b.kind !== "macro") return false;
  if (!searchTerm) return filterMode !== "stale" || freshSummary(b).stale + freshSummary(b).static > 0;
  if (matchesSearch(b.name)) return true;
  if ((b.keywords || []).some(k => matchesSearch(k))) return true;
  if (b.children.some(c => matchesSearch(c))) return true;
  return false;
}
function symbolMatches(sym) {
  const leaf = leafByName.get(sym);
  if (!leaf) return false;
  if (filterMode === "stale" && !(leaf.freshness === "stale" || leaf.freshness === "static")) return false;
  if (!searchTerm) return true;
  if (matchesSearch(sym)) return true;
  if ((leaf.keywords || []).some(k => matchesSearch(k))) return true;
  return false;
}

// -------- Tree view -------------------------
function renderTreeView() {
  const root = document.getElementById("tree-view");
  const sections = [];

  if (filterMode !== "macros") sections.push(renderSection("THEMES", themes));
  if (filterMode !== "themes") sections.push(renderSection("MACROS", macros));
  if (filterMode === "all" && !searchTerm) sections.push(renderUnlinked());

  root.innerHTML = sections.join("");
  attachTreeHandlers();
  if (selectedId) markSelectedInTree(selectedId);
}

function renderSection(title, list) {
  const visible = list.filter(branchMatches);
  if (!visible.length) return "";
  const rows = visible.map(b => renderBranchRow(b)).join("");
  return `<div>
    <div class="tree-section-header"><span>${title} (${visible.length})</span></div>
    ${rows}
  </div>`;
}

function renderBranchRow(b) {
  const counts = freshSummary(b);
  const tot = b.children.length;
  const fresh = counts.fresh;
  const bar = `<span class="freshness-bar">
    ${counts.fresh ? `<span class="seg seg-fresh" title="${counts.fresh} fresh"></span>` : ""}
    ${counts.aging ? `<span class="seg seg-aging" title="${counts.aging} aging"></span>` : ""}
    ${counts.stale ? `<span class="seg seg-stale" title="${counts.stale} stale"></span>` : ""}
    ${counts.static ? `<span class="seg seg-static" title="${counts.static} never updated"></span>` : ""}
  </span>`;

  const isExpanded = expandedBranches.has(b.id) || (searchTerm && b.children.some(c => symbolMatches(c)));
  const chips = b.children
    .filter(c => filterMode === "stale" ? (leafByName.get(c)?.freshness === "stale" || leafByName.get(c)?.freshness === "static") : true)
    .filter(c => !searchTerm || symbolMatches(c) || matchesSearch(b.name))
    .map(sym => renderChip(sym))
    .join("");

  return `<div class="tree-row ${isExpanded ? "expanded" : ""}" data-branch="${b.id}">
    <div class="row-summary" data-action="toggle">
      <span class="caret">▸</span>
      <span class="kind-badge kind-${b.kind}"></span>
      <span class="row-name">${b.name}</span>
      ${bar}
      <span class="row-meta">${fresh}/${tot} fresh</span>
    </div>
    <div class="row-children">
      ${chips || "<span class='meta-line'>no symbols matching</span>"}
    </div>
  </div>`;
}

function renderChip(sym) {
  const leaf = leafByName.get(sym);
  if (!leaf) return "";
  return `<span class="ticker-chip" data-sym="${sym}">
    <span class="chip-dot dot-${leaf.freshness}"></span>${sym}
  </span>`;
}

function renderUnlinked() {
  const visible = unlinked.filter(l => symbolMatches(l.name));
  if (!visible.length) return "";
  const chips = visible.map(l => renderChip(l.name)).join("");
  return `<div>
    <div class="tree-section-header"><span>UNLINKED SYMBOLS (${visible.length})</span></div>
    <div class="unlinked-chip-grid">${chips}</div>
  </div>`;
}

function attachTreeHandlers() {
  document.querySelectorAll(".tree-row .row-summary").forEach(el => {
    el.addEventListener("click", (e) => {
      const row = el.closest(".tree-row");
      const bid = row.dataset.branch;
      if (expandedBranches.has(bid)) expandedBranches.delete(bid);
      else expandedBranches.add(bid);
      row.classList.toggle("expanded");
      selectedId = bid;
      showDetail(bid);
      markSelectedInTree(bid);
    });
  });
  document.querySelectorAll(".ticker-chip").forEach(el => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      const sym = el.dataset.sym;
      selectedId = symId(sym);
      showDetail(selectedId);
      markSelectedInTree(selectedId);
    });
  });
}

function markSelectedInTree(id) {
  document.querySelectorAll(".tree-row.active").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".ticker-chip.active").forEach(el => el.classList.remove("active"));
  if (!id) return;
  if (id.startsWith("sym::")) {
    const sym = id.slice(5);
    document.querySelectorAll(`.ticker-chip[data-sym="${CSS.escape(sym)}"]`).forEach(el => el.classList.add("active"));
  } else {
    const row = document.querySelector(`.tree-row[data-branch="${CSS.escape(id)}"]`);
    if (row) row.classList.add("active");
  }
}

function scrollIntoViewInTree(id) {
  if (!id) return;
  let el;
  if (id.startsWith("sym::")) {
    const sym = id.slice(5);
    // Ensure any parent branch containing this sym is expanded
    DATA.branches.forEach(b => {
      if (b.children.includes(sym)) expandedBranches.add(b.id);
    });
    renderTreeView();
    el = document.querySelector(`.ticker-chip[data-sym="${CSS.escape(sym)}"]`);
  } else {
    expandedBranches.add(id);
    renderTreeView();
    el = document.querySelector(`.tree-row[data-branch="${CSS.escape(id)}"]`);
  }
  if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  markSelectedInTree(id);
}

// -------- Graph view (D3 force) ------------
let simulation;
const svg = d3.select("#svg");
const g = svg.append("g");
const zoom = d3.zoom().scaleExtent([0.2, 3]).on("zoom", e => g.attr("transform", e.transform));
svg.call(zoom);

function buildGraphData() {
  const nodes = [];
  const links = [];
  const seen = new Set();

  const activeBranches = DATA.branches.filter(b => {
    if (filterMode === "themes" && b.kind !== "theme") return false;
    if (filterMode === "macros" && b.kind !== "macro") return false;
    return true;
  });

  activeBranches.forEach(b => {
    nodes.push({ id: b.id, kind: b.kind, name: b.name, size: 22, childCount: b.children.length });
    seen.add(b.id);
  });

  for (const [t, ms] of Object.entries(DATA.t2m || {})) {
    const tId = `theme::${t}`;
    if (!seen.has(tId)) continue;
    ms.forEach(m => {
      const mId = `macro::${m}`;
      if (seen.has(mId)) links.push({ source: tId, target: mId, kind: "cross" });
    });
  }

  const leafSet = new Set();
  activeBranches.forEach(b => {
    if (!expandedBranches.has(b.id)) return;
    b.children.forEach(sym => leafSet.add(sym));
  });

  if (filterMode === "stale") {
    activeBranches.forEach(b => {
      b.children.forEach(sym => {
        const leaf = leafByName.get(sym);
        if (leaf && (leaf.freshness === "stale" || leaf.freshness === "static")) {
          leafSet.add(sym);
          expandedBranches.add(b.id);
        }
      });
    });
  }

  if (searchTerm) {
    activeBranches.forEach(b => {
      if (matchesSearch(b.name) || (b.keywords || []).some(k => matchesSearch(k))) {
        expandedBranches.add(b.id);
        b.children.forEach(sym => leafSet.add(sym));
      } else {
        const kids = b.children.filter(sym => symbolMatches(sym));
        if (kids.length) {
          expandedBranches.add(b.id);
          kids.forEach(sym => leafSet.add(sym));
        }
      }
    });
  }

  leafSet.forEach(sym => {
    const leaf = leafByName.get(sym);
    if (!leaf || seen.has(leaf.id)) return;
    nodes.push({ id: leaf.id, kind: "symbol", name: leaf.name, freshness: leaf.freshness, size: 7, keywords: leaf.keywords });
    seen.add(leaf.id);
  });

  activeBranches.forEach(b => {
    if (!expandedBranches.has(b.id)) return;
    b.children.forEach(sym => {
      const lid = symId(sym);
      if (seen.has(lid)) links.push({ source: b.id, target: lid, kind: "parent" });
    });
  });

  return { nodes, links };
}

function nodeColor(n) {
  if (n.kind === "theme") return COLORS.theme;
  if (n.kind === "macro") return COLORS.macro;
  return COLORS[n.freshness] || COLORS.static;
}

function renderGraph() {
  const { nodes, links } = buildGraphData();
  const width = svg.node().clientWidth || 900;
  const height = svg.node().clientHeight || 700;
  g.selectAll("*").remove();

  const link = g.append("g").attr("class", "links")
    .selectAll("line").data(links).join("line")
    .attr("stroke", d => d.kind === "cross" ? "#5a6484" : "#2f3b5a")
    .attr("stroke-dasharray", d => d.kind === "cross" ? "3 3" : null)
    .attr("stroke-width", d => d.kind === "cross" ? 1 : 1.2)
    .attr("stroke-opacity", 0.75);

  const node = g.append("g").attr("class", "nodes")
    .selectAll("g").data(nodes, d => d.id).join("g")
    .attr("class", "node")
    .style("cursor", "pointer")
    .call(d3.drag()
      .on("start", (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
      .on("end", (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

  node.append("circle")
    .attr("r", d => d.size)
    .attr("fill", d => nodeColor(d))
    .attr("stroke", d => d.id === selectedId ? "#fff" : "#0b0f18")
    .attr("stroke-width", d => d.id === selectedId ? 3 : 1.5);

  node.append("text")
    .attr("class", d => "node-label" + (d.kind !== "symbol" ? " branch" : ""))
    .attr("dy", d => d.kind === "symbol" ? -10 : 4)
    .attr("text-anchor", "middle")
    .text(d => d.kind === "symbol" ? d.name.replace(/on$/, "") : d.name + (d.childCount ? ` (${d.childCount})` : ""));

  node.on("click", (event, d) => {
    event.stopPropagation();
    selectedId = d.id;
    if (d.kind !== "symbol") {
      if (expandedBranches.has(d.id)) expandedBranches.delete(d.id);
      else expandedBranches.add(d.id);
      renderGraph();
    } else {
      highlightGraphConnected(d.id);
    }
    showDetail(d.id);
  });

  const tooltip = d3.select("#tooltip");
  node.on("mouseover", (event, d) => {
    const [x, y] = d3.pointer(event, document.body);
    let html;
    if (d.kind === "symbol") {
      const leaf = leafById.get(d.id);
      const kws = (leaf.keywords || []).slice(0, 8).join(", ");
      html = `<strong>${leaf.name}</strong> · ${leaf.freshness}<br><span style="color:var(--muted)">${kws}${leaf.keywords.length > 8 ? "..." : ""}</span>`;
    } else {
      const br = branchById.get(d.id);
      html = `<strong>${br.name}</strong> · ${br.kind}<br><span style="color:var(--muted)">${br.children.length} linked symbols</span>`;
    }
    tooltip.html(html).style("left", (x + 14) + "px").style("top", (y + 14) + "px").style("display", "block");
  }).on("mousemove", event => {
    const [x, y] = d3.pointer(event, document.body);
    tooltip.style("left", (x + 14) + "px").style("top", (y + 14) + "px");
  }).on("mouseout", () => tooltip.style("display", "none"));

  const nExpanded = expandedBranches.size;
  const branchCharge = nExpanded === 0 ? -180 : -320;

  simulation = d3.forceSimulation(nodes)
    .velocityDecay(0.5)
    .force("link", d3.forceLink(links).id(d => d.id)
      .distance(d => d.kind === "cross" ? 90 : 55)
      .strength(d => d.kind === "cross" ? 0.2 : 0.7))
    .force("charge", d3.forceManyBody().strength(d => d.kind === "symbol" ? -60 : branchCharge))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("x", d3.forceX(width / 2).strength(0.07))
    .force("y", d3.forceY(height / 2).strength(0.07))
    .force("collide", d3.forceCollide().radius(d => d.size + 4))
    .on("tick", () => {
      link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
          .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
      node.attr("transform", d => `translate(${d.x}, ${d.y})`);
    });
}

function highlightGraphConnected(id) {
  g.selectAll(".links line")
    .attr("stroke", d => (d.source.id === id || d.target.id === id) ? "#e6e8ee" : "#2f3b5a")
    .attr("stroke-opacity", d => (d.source.id === id || d.target.id === id) ? 1 : 0.25);
  g.selectAll(".node circle")
    .attr("stroke", n => n.id === id ? "#fff" : "#0b0f18")
    .attr("stroke-width", n => n.id === id ? 3 : 1.5);
}

// -------- Detail pane (shared) --------------
function showDetail(id) {
  const det = document.getElementById("detail");
  if (id.startsWith("sym::")) {
    const l = leafById.get(id);
    if (!l) return;
    const badges = [];
    badges.push(`<span class="detail-badge badge-${l.freshness}">${l.freshness.toUpperCase()}</span>`);
    if (l.context_source) badges.push(`<span class="detail-badge badge-static">${l.context_source.toUpperCase()}</span>`);
    const themes = (l.themes || []).map(t => `<span class="link-btn" data-nav="theme::${t}">theme: ${t.replace(/_/g,' ')}</span>`).join("");
    const macros = (l.macros || []).map(m => `<span class="link-btn" data-nav="macro::${m}">macro: ${m.replace(/_/g,' ')}</span>`).join("");
    det.innerHTML = `
      <h2>${l.name}</h2>
      <div>${badges.join(" ")}</div>
      <div class="meta-line">Updated ${l.updated_at || "never"}${l.updated_by ? " · by " + l.updated_by : ""}</div>
      <h3>Description</h3><p>${l.description || "—"}</p>
      ${l.upside_catalysts?.length ? `<h3>Upside catalysts</h3><ul class="catalyst-list up">${l.upside_catalysts.map(c => `<li>${c}</li>`).join("")}</ul>` : ""}
      ${l.downside_catalysts?.length ? `<h3>Downside catalysts</h3><ul class="catalyst-list down">${l.downside_catalysts.map(c => `<li>${c}</li>`).join("")}</ul>` : ""}
      <h3>Keywords (${l.keywords.length})</h3><div>${(l.keywords || []).map(k => `<span class="kw-tag">${k}</span>`).join("")}</div>
      ${themes || macros ? `<h3>Also appears in</h3><div>${themes}${macros}</div>` : ""}
    `;
  } else {
    const b = branchById.get(id);
    if (!b) return;
    const badge = b.kind === "theme" ? "badge-theme" : "badge-macro";
    const counts = freshSummary(b);
    const children = (b.children || []).map(sym => {
      const leaf = leafByName.get(sym);
      const cls = leaf ? `dot-${leaf.freshness}` : "dot-static";
      return `<span class="ticker-chip" data-nav="sym::${sym}"><span class="chip-dot ${cls}"></span>${sym}</span>`;
    }).join("");
    const linked = [
      ...(b.linked_themes || []).map(t => `<span class="link-btn" data-nav="theme::${t}">theme: ${t.replace(/_/g,' ')}</span>`),
      ...(b.linked_macros || []).map(m => `<span class="link-btn" data-nav="macro::${m}">macro: ${m.replace(/_/g,' ')}</span>`)
    ].join("");
    det.innerHTML = `
      <h2>${b.name}</h2>
      <div><span class="detail-badge ${badge}">${b.kind.toUpperCase()}</span></div>
      <div class="meta-line">${counts.fresh} fresh · ${counts.aging} aging · ${counts.stale} stale · ${counts.static} never updated</div>
      <h3>Description</h3><p>${b.description || "—"}</p>
      ${b.tailwinds?.length ? `<h3>Tailwinds</h3><ul class="catalyst-list up">${b.tailwinds.map(c => `<li>${c}</li>`).join("")}</ul>` : ""}
      ${b.headwinds?.length ? `<h3>Headwinds</h3><ul class="catalyst-list down">${b.headwinds.map(c => `<li>${c}</li>`).join("")}</ul>` : ""}
      <h3>Keywords (${b.keywords.length})</h3><div>${(b.keywords || []).map(k => `<span class="kw-tag">${k}</span>`).join("")}</div>
      ${children ? `<h3>Linked symbols (${b.children.length})</h3><div>${children}</div>` : ""}
      ${linked ? `<h3>Related branches</h3><div>${linked}</div>` : ""}
    `;
  }
  // Wire up navigation links in the detail pane
  det.querySelectorAll("[data-nav]").forEach(el => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      const nav = el.dataset.nav;
      selectedId = nav;
      if (view === "tree") scrollIntoViewInTree(nav);
      else {
        if (!nav.startsWith("sym::")) expandedBranches.add(nav);
        else DATA.branches.forEach(b => { if (b.children.includes(nav.slice(5))) expandedBranches.add(b.id); });
        renderGraph();
      }
      showDetail(nav);
    });
  });
}

// -------- View switching --------------------
function setView(v) {
  view = v;
  document.getElementById("btn-tree").classList.toggle("active", v === "tree");
  document.getElementById("btn-graph").classList.toggle("active", v === "graph");
  document.getElementById("tree-view").classList.toggle("hidden", v !== "tree");
  document.getElementById("graph-view").classList.toggle("hidden", v !== "graph");
  if (v === "tree") renderTreeView();
  else renderGraph();
}

document.getElementById("btn-tree").addEventListener("click", () => setView("tree"));
document.getElementById("btn-graph").addEventListener("click", () => setView("graph"));
document.getElementById("search").addEventListener("input", e => {
  searchTerm = e.target.value.trim().toLowerCase();
  if (view === "tree") renderTreeView(); else renderGraph();
});
document.getElementById("filter").addEventListener("change", e => {
  filterMode = e.target.value;
  if (view === "tree") renderTreeView(); else renderGraph();
});

setView("tree");
</script>
</body>
</html>
"""


def main():
    payload = build_payload()
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(payload, default=str))
    out = HERE / "tree_prototype.html"
    out.write_text(html)
    print(f"Wrote {out} ({out.stat().st_size/1024:.1f} KB)")
    print(f"Branches: {len(payload['branches'])}  Leaves: {len(payload['leaves'])}")


if __name__ == "__main__":
    main()
