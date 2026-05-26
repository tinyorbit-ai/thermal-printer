# thermal-printer — Engineering Wiki

Obsidian-style wiki. **Source of truth for the _why_.** Code says what; this says why.

## What this is (one line)

A CLI to drive my USB Star TSP 100III thermal printer, wired into Claude Code so `/receipt` prints a summary of the current session — tokens used and interesting bits — as a physical receipt of work.

## Map of content

- [[brief]] — what we're building, for whom, the feel, non-goals
- [[plan]] — the phased build plan; each phase has a verifiable gate + branch
- [[architecture]] — the 30-second version (filled in as phases land)
- [[build-log]] — one entry per phase: the gate met before merge
- [[learnings]] — review lessons + the rule-to-remember (running)
- [[retro]] — build retrospectives, synthesis across phases (running)
- [[improvements]] — what I'd do with more time / deliberate scope cuts (running)

### Decisions (ADRs)

- [[decisions/0001-shape]] — Python CLI + python-escpos + raw USB; template-driven architecture.
- [[decisions/0002-cli-and-packaging]] — `thermal-print` command, `uv` + `pyproject.toml`, single entry point.
- [[decisions/0003-template-plugin-mechanism]] — auto-discovery of `templates/*.py` files.
- [[decisions/0004-receipt-layout-grammar]] — 32-char grid, `Receipt` builder API, `~/.thermal-printer/state.json`.
- [[decisions/0005-session-stats-schema]] — what JSONL fields the receipt surfaces, partial-line robustness, encoded-cwd resolution.

### Incident notes

_None yet — root-cause writeups land here as they happen._

## Reading order

1. [[brief]] — what and why
2. [[plan]] — how, in phases
3. [[architecture]] — the shape of it
