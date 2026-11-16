---
name: map-query
description: Section-level search over a project's markdown knowledge base (AGENTS.md, project maps, docs, session summaries). Use before reading large .md files wholesale — returns file:line pointers so you open only the relevant section. Trigger on "what did we decide about X", "what's the state of project Y", or when a knowledge/map .md is too long to read.
argument-hint: "[search query]"
allowed-tools:
  - exec
  - read
---

# map-query — markdown knowledge search

`map_query.py` indexes every `.md` in a project by section (heading → next
heading) and answers keyword queries with `file:line` pointers.
**Search first, then open only what matters** — do not read multi-thousand-line
map/state files end-to-end when a query can point at the 30 relevant lines.

## Usage

```bash
python map_query.py <query>          # section search → file:line + preview
python map_query.py open <substr> [a-b]   # print the file / line range
python map_query.py reindex          # rebuild after editing .md files (fast)
python map_query.py status           # index age + files changed since
python map_query.py files            # list indexed files
```

Search for the concept, not exact wording — scoring favors section titles.
Multiple hits are pointers, not answers: `open` (or read) the top section and
verify before reporting back.

## Setup in a project

```bash
cp map_query.py <project>/           # single file, stdlib only
cd <project> && python map_query.py reindex
```

Optional `.mapquery.json` in the project root controls extra roots, excludes,
walk depth, index and TOC paths — see README.

## Rules

- Reindex after writing or heavily editing `.md` files (the tool warns on stale
  hits automatically).
- Results are ranked pointers — always open the cited section before treating
  it as fact.
