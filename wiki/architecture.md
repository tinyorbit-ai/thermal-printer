# Architecture — thermal-printer

Part of [[index]]. The 30-second version. Code is the *what*; this is the shape
and the central bet. Updated as phases land.

## Central bet

A single Python CLI (`thermal-print`) drives the Star TSP 100III over raw USB
with `python-escpos`. Every print is a **template** — a small function that
populates a shared `Receipt` builder with a fixed visual grammar. `/receipt` is
the first template; future rituals (morning intention, ship receipt, end-of-day)
are new files in the `templates/` directory. The slash command is a thin shim
that gathers Claude Code context and pipes it to the same CLI.

See [[decisions/0001-shape]] for *why Python*, [[decisions/0002-cli-and-packaging]]
for the install path, [[decisions/0003-template-plugin-mechanism]] for the
template plug, [[decisions/0004-receipt-layout-grammar]] for the visual grammar.

## Components & data flow

```
   ┌─────────────────┐
   │  /receipt slash │  (.claude/commands/receipt.md)
   │     command     │  gathers: session_id, cwd, project name
   └────────┬────────┘
            │  shells out
            ▼
   ┌─────────────────────────────────────────────────────┐
   │  thermal-print CLI  (src/thermal_print/)            │
   │                                                     │
   │   cli.py ──┬─▶ templates/<name>.py  (auto-discover) │
   │            │      └─ render(ctx, r: Receipt)        │
   │            │                                        │
   │            ├─▶ session.py  (parse JSONL → ctx)      │
   │            ├─▶ llm.py      (Haiku → 3-5 line text)  │
   │            ├─▶ state.py    (~/.thermal-printer/)    │
   │            │                                        │
   │            └─▶ receipt.py  (32-col grammar)         │
   │                    │                                │
   │                    ▼                                │
   │                printer.py  (pyusb → escpos bytes)   │
   └────────────────────┬────────────────────────────────┘
                        │  raw USB (libusb)
                        ▼
                 Star TSP 100III  (kachunk.)
```

## Module boundaries

- **`cli.py`** — argparse dispatch; loads templates; assembles `ctx` from args
  and environment; calls `render(ctx, r)`; flushes `r` to `printer.py`.
- **`templates/*.py`** — pure layout. Each module exposes `NAME` + `render`.
  Never imports `python-escpos`; only touches the `Receipt` builder + `ctx`.
- **`receipt.py`** — the only module that knows about the 32-char grid, font A,
  divider conventions, serial format. Emits escpos bytes via `python-escpos`.
- **`printer.py`** — opens the USB device (vendor/product ID constants), writes
  bytes, closes. The only module that talks to USB. **Does not emit the cut
  command** — the cut is exclusively a `Receipt.cut()` call inside the
  template's byte stream, so there is one cut per receipt and one cut emitter
  in the codebase. (Hardened 2026-05-26 — the previous shape, where both
  `printer.py` and `receipt.py` emitted cut bytes, risked two cuts per print.)
- **`session.py`** *(phase 4)* — reads
  `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`, extracts token totals,
  files touched, tool calls, wall time. Pure function — JSONL in, dict out.
- **`llm.py`** *(phase 5)* — calls Anthropic Haiku with a compact prompt;
  returns 3–5 lines of summary. Fails gracefully (template falls back to
  stats-only).
- **`state.py`** — read/write `~/.thermal-printer/state.json`, override via
  `THERMAL_PRINT_STATE` env var for tests.

## The one emitter of escpos bytes

Only **`receipt.py`** (layout, including cut) emits raw escpos. `printer.py`
moves bytes onto USB without composing them. Templates never compose escpos;
CLI never does. This keeps the layout grammar testable in isolation (render
to a byte stream → snapshot test, with a structural assertion that the stream
contains exactly one cut command) and the device adapter swappable if the
printer ever changes.

## Runtime deps

`python-escpos`, `pyusb`, `Pillow` (raster bitmap), `anthropic` (phase 5), plus
`libusb` from Homebrew. Python 3.11+, macOS only. See
[[decisions/0001-shape#consequences]] and
[[decisions/0002-cli-and-packaging#consequences]].
