#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""map_query — index markdown knowledge bases and search them by section.

Point it at a directory of .md docs (AGENTS.md, project maps, changelogs,
session summaries...) and it builds a section-level index you can query
with plain keywords — file:line pointers, not hallucinated answers.

Usage:
    python map_query.py reindex              # (re)build index + TOC
    python map_query.py <query>              # section search (top hits)
    python map_query.py open <path> [a-b]    # print file/line range
    python map_query.py toc                  # regenerate the TOC file
    python map_query.py files                # list indexed files
    python map_query.py status               # index stats / staleness

Configuration — put .mapquery.json in the root you want indexed:
    {
      "roots": ["extra/dir", "C:/abs/path"],   # extra dirs beyond base
      "exclude_dirs": ["dist", "node_modules"],
      "max_depth": 3,                         # walk depth under base
      "index": ".mapindex.json",              # index file (relative to base)
      "toc": "MAP_INDEX.md"                   # TOC file ("" disables)
    }
No config needed: defaults index all .md under the current directory.

Zero dependencies — Python 3.9+ standard library only.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

DEFAULT_EXCLUDE = {
    "dist", "node_modules", ".git", "__pycache__", "build",
    ".venv", "venv", "site-packages", "out", "target", ".idea",
}
HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)")
EXT_MAX_TOC = 10  # external-root files shown in TOC (rest reachable via search)


def find_config(base: Path) -> dict:
    cfg_path = base / ".mapquery.json"
    if cfg_path.is_file():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def resolve_settings() -> tuple[Path, dict]:
    """(base_dir, config) — base is the dir holding .mapquery.json, else cwd."""
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        if (d / ".mapquery.json").is_file():
            return d, find_config(d)
    return cwd, {}


def settings_for(base: Path, cfg: dict) -> dict:
    roots = []
    for r in cfg.get("roots", []):
        p = Path(os.path.expandvars(r))
        roots.append(p if p.is_absolute() else (base / p).resolve())
    return {
        "base": base,
        "roots": [base] + roots,
        "exclude": DEFAULT_EXCLUDE | set(cfg.get("exclude_dirs", [])),
        "max_depth": int(cfg.get("max_depth", 0)),   # 0 = unlimited
        "index": base / cfg.get("index", ".mapindex.json"),
        "toc": (base / cfg["toc"]) if cfg.get("toc") else None,
        "ext_roots": set(roots),
    }


def iter_md_files(s: dict) -> list[Path]:
    seen, files = set(), []
    for root in s["roots"]:
        if not root.exists():
            continue
        is_base = root == s["base"]
        for dirpath, dirnames, filenames in os.walk(root):
            rel = Path(dirpath).relative_to(root)
            dirnames[:] = [d for d in dirnames if d not in s["exclude"]
                           and not d.startswith(".") or d == ".github"]
            if is_base and s["max_depth"] and len(rel.parts) >= s["max_depth"]:
                dirnames[:] = []
            for f in filenames:
                if f.endswith(".md"):
                    p = Path(dirpath) / f
                    if p not in seen:
                        seen.add(p)
                        files.append(p)
    return sorted(files)


def split_sections(lines: list[str]) -> list[dict]:
    """Split md into header-delimited sections."""
    sections = []
    cur = {"title": "(document start)", "level": 0, "line": 1, "buf": []}
    for i, ln in enumerate(lines, 1):
        m = HEADER_RE.match(ln)
        if m:
            if cur["buf"] or cur["title"] != "(document start)":
                cur["end"] = i - 1
                cur["text"] = "\n".join(cur.pop("buf"))
                sections.append(cur)
            cur = {"title": m.group(2).strip(), "level": len(m.group(1)),
                   "line": i, "buf": []}
        else:
            cur["buf"].append(ln)
    cur["end"] = len(lines)
    cur["text"] = "\n".join(cur.pop("buf"))
    sections.append(cur)
    return [s for s in sections if s["text"].strip() or s["title"] != "(document start)"]


def build_index(s: dict) -> dict:
    files = []
    for p in iter_md_files(s):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        try:
            rel = str(p.relative_to(s["base"]))
        except ValueError:
            rel = str(p)
        files.append({"path": rel, "abs": str(p), "mtime": p.stat().st_mtime,
                      "lines": len(lines), "sections": split_sections(lines)})
    return {"generated": time.time(), "files": files}


def load_index(s: dict) -> dict:
    if s["index"].is_file():
        try:
            return json.loads(s["index"].read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"generated": 0, "files": []}


def save_index(s: dict, idx: dict) -> None:
    s["index"].write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")


def write_toc(s: dict, idx: dict) -> None:
    if not s["toc"]:
        return
    out = ["# Map Index — markdown knowledge base TOC (generated by map_query.py)", "",
           f"> Generated {time.strftime('%Y-%m-%d %H:%M', time.localtime(idx['generated']))}"
           f" · {len(idx['files'])} files · refresh: `python map_query.py reindex`", "",
           "Search sections: `python map_query.py <query>`", ""]
    proj = sorted((f for f in idx["files"] if ":" not in f["path"]), key=lambda f: f["path"])
    ext = sorted((f for f in idx["files"] if ":" in f["path"]), key=lambda f: -f["mtime"])
    ext_total, ext_shown = len(ext), 0
    cur_dir = None
    for f in proj + ext:
        is_ext = ":" in f["path"]
        p = Path(f["path"])
        d = str(p.parent) if str(p.parent) != "." else "(root)"
        if is_ext:
            if d != cur_dir:
                out += ["", f"## {d}  _({ext_total} external files — newest {EXT_MAX_TOC} shown; search covers all)_", ""]
                cur_dir = d
            if ext_shown >= EXT_MAX_TOC:
                continue
            ext_shown += 1
        elif d != cur_dir:
            out += ["", f"## {d}", ""]
            cur_dir = d
        out.append(f"- **{p.name}** ({f['lines']} lines)")
        for s2 in [x for x in f["sections"] if x["level"] <= 2][:12]:
            out.append(f"  {'  ' if s2['level'] == 2 else ''}- {s2['title'][:80]} · L{s2['line']}")
    s["toc"].write_text("\n".join(out) + "\n", encoding="utf-8")


def search(idx: dict, query: str, top_k: int = 8) -> list[dict]:
    tokens = [t.lower() for t in re.split(r"\s+", query.strip()) if len(t) >= 2]
    if not tokens and query.strip():
        tokens = [query.strip().lower()]
    hits = []
    for f in idx["files"]:
        for s in f["sections"]:
            title_l, text_l = s["title"].lower(), s["text"].lower()
            score = sum(title_l.count(t) * 3 + text_l.count(t) for t in tokens)
            if score > 0:
                # dampen score for very long sections (raw dumps) — curated docs win
                slen = s["end"] - s["line"] + 1
                score = round(score * min(1.0, 300.0 / slen), 1)
                matched = [ln.strip() for ln in s["text"].splitlines()
                           if any(t in ln.lower() for t in tokens)][:3]
                hits.append({"file": f["path"], "line": s["line"], "end": s["end"],
                             "title": s["title"], "score": score, "preview": matched})
    hits.sort(key=lambda h: -h["score"])
    return hits[:top_k]


def staleness(s: dict, idx: dict) -> tuple[int, int]:
    changed = sum(1 for f in idx["files"]
                  if not Path(f["abs"]).is_file()
                  or Path(f["abs"]).stat().st_mtime > idx["generated"])
    return changed, len(idx["files"])


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 0
    base, cfg = resolve_settings()
    s = settings_for(base, cfg)
    cmd = args[0].lower()

    if cmd == "reindex":
        idx = build_index(s)
        save_index(s, idx)
        write_toc(s, idx)
        print(f"indexed {len(idx['files'])} files -> {s['index']}"
              + (f", TOC -> {s['toc']}" if s["toc"] else ""))
        return 0

    idx = load_index(s)
    if not idx["files"]:
        print("no index — run `map_query.py reindex` first", file=sys.stderr)
        return 1
    changed, total = staleness(s, idx)
    if changed:
        print(f"! {changed} file(s) changed since indexing — `reindex` recommended",
              file=sys.stderr)

    if cmd == "toc":
        if not s["toc"]:
            print("no toc path configured (set \"toc\" in .mapquery.json)", file=sys.stderr)
            return 1
        write_toc(s, idx)
        print(f"TOC regenerated -> {s['toc']}")
        return 0
    if cmd == "files":
        for f in idx["files"]:
            print(f"{f['lines']:>6}  {f['path']}")
        print(f"\n{total} files")
        return 0
    if cmd == "status":
        print(f"indexed: {time.strftime('%Y-%m-%d %H:%M', time.localtime(idx['generated']))}"
              f" | files: {total} | changed since: {changed}")
        return 0
    if cmd == "open":
        if len(args) < 2:
            print("usage: map_query.py open <path-substring> [start-end]", file=sys.stderr)
            return 1
        cand = [f for f in idx["files"] if args[1].lower() in f["path"].lower()]
        if not cand:
            print(f"no file matching '{args[1]}'", file=sys.stderr)
            return 1
        lo, hi = 1, 10**9
        if len(args) > 2 and "-" in args[2]:
            lo, hi = map(int, args[2].split("-", 1))
        f = cand[0]
        lines = Path(f["abs"]).read_text(encoding="utf-8", errors="replace").splitlines()
        print(f"=== {f['path']} ({len(lines)} lines) ===")
        for i, ln in enumerate(lines, 1):
            if lo <= i <= hi:
                print(f"{i:>5} {ln}")
        return 0

    hits = search(idx, " ".join(args))
    if not hits:
        print("no results")
        return 0
    for h in hits:
        print(f"* {h['file']}:{h['line']}-{h['end']}  [{h['score']}] {h['title']}")
        for ln in h["preview"]:
            print(f"    {ln[:110]}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
