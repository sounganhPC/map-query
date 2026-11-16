# map-query

Section-level search for markdown knowledge bases — one file, zero dependencies.

Teams are piling knowledge into markdown: `AGENTS.md`, project maps, changelogs,
`docs/*.md`, session summaries, decision logs. The files work great as *sources
of truth* — until the map grows past ~1,500 lines and neither humans nor AI
agents want to read it whole. `map_query.py` indexes every `.md` under your
project by **section** and answers with `file:line` pointers, so an agent reads
the 30 relevant lines instead of the 1,500-line file.

## Why not just grep / RAG / Kafka?

- `grep` finds lines, not sections — you still have to open the file and figure
  out which heading owns the match. `map_query` returns the *section* (title +
  line range) and previews the matching lines in context.
- Embeddings need a model + a DB. This is TF scoring over sections — good enough
  for curated docs, and `pip install` is the whole setup.
- Long raw dumps (session transcripts, logs) get **dampened** so curated docs
  rank first.

## Quickstart

```bash
# drop the single file anywhere, or clone the repo
python map_query.py reindex        # indexes all .md under the current dir
python map_query.py hydrogen limit # section search
python map_query.py open tasks 57-98
```

```
* docs/decisions.md:42-78  [14.0] Chose SQLite over Postgres
* AGENTS.md:7-19           [9.0] Current state
```

## Commands

| Command | What it does |
|---|---|
| `reindex` | Rescan the tree, write the index + TOC file |
| `<query>` | Search sections; prints `file:line` + matched-line preview |
| `open <substr> [a-b]` | Print a file or line range |
| `toc` | Regenerate the TOC markdown file |
| `files` | List indexed files with line counts |
| `status` | Index age + files changed since last index |

## Configuration

Drop `.mapquery.json` in the directory you want indexed. The tool finds it by
walking up from the working directory.

```json
{
  "roots": ["extra/docs", "%APPDATA%\\devin\\cli\\summaries"],
  "exclude_dirs": ["dist", "node_modules"],
  "max_depth": 3,
  "index": ".mapindex.json",
  "toc": "MAP_INDEX.md"
}
```

| Key | Default | Meaning |
|---|---|---|
| `roots` | `[]` | Extra directories to index (relative to config dir or absolute; env vars expand) |
| `exclude_dirs` | common build/vcs dirs | Directory names to skip |
| `max_depth` | `0` (unlimited) | Walk depth under the base directory |
| `index` | `.mapindex.json` | Where the index lives |
| `toc` | off | TOC markdown path; generated on `reindex`/`toc` |

If no config exists, everything under the current directory is indexed.

## Agent skill

`SKILL.md` in this repo tells AI coding agents (Claude Code, Devin, Cursor via
`npx skills add <you>/map-query`) how to query the map before reading files
wholesale — the intended use is "find first, then open only what matters".

## How it works

1. Each `.md` is split into sections at every `#`–`######` heading.
2. Query tokens match section titles (×3) and bodies, scored by frequency.
3. Section-length normalization dampens giant raw dumps so curated docs win.
4. Output is pointers — always open the file to verify before answering.

Stale detection: `status`/search warn when files changed after indexing.

## License

MIT — see [LICENSE](LICENSE).

---

Built by **성안컴퓨터 (SeongAn Computer)** — a neighborhood computer shop in
South Korea that writes its own tools instead of buying them.
More of our work at [sounganh.com](https://sounganh.com).
