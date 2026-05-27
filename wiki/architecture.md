# Architecture — thermal-printer

Part of [[index]]. The 30-second version. Code is the *what*; this is the shape
and the central bet. Updated as phases land.

## Central bet

A single Python CLI (`thermal-print`) drives the Star TSP143IIIU over raw USB
using **Star Graphic raster** — the printer's proprietary bitmap protocol. Every
print is a **template** — a small function that populates a shared `Receipt`
builder, which accumulates onto a PIL image and flushes that image as a raster
print job. `/receipt` is the first template; future rituals (morning intention,
ship receipt, end-of-day) are new files in the `templates/` directory. The
slash command is a Claude Code prompt that writes the narrative summary
in-context and passes it to the CLI via `--summary`.

**The protocol pivot (2026-05-27).** The original plan assumed
`python-escpos` could drive the printer over ESC/POS. The TSP143IIIU actually
ships in Star Graphic raster mode and ignores ESC/POS entirely (see
[[notes/2026-05-27-tsp143iiiu-default-mode]]). `python-escpos` is no longer a
runtime dep; the project ships a small Star Graphic encoder (`star_raster.py`)
reverse-engineered from Star's own open-source CUPS filter.

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
- **`receipt.py`** — the only module that knows about the 32-char design grid,
  fonts, divider conventions, serial format. Internal state is a growing PIL
  monochrome image; primitives (`header`, `row`, `divider`, `text`, `logo`,
  `serial`, `footer`, `cut`) draw onto it. `send()` crops to actual content and
  calls `star_raster.encode_job` to emit the bitmap as Star Graphic bytes.
- **`star_raster.py`** — Star Graphic raster encoder (`ESC @` → enter raster
  mode → page-type/cut config → raster lines → end page → end job). The
  protocol was reverse-engineered from Star's GPLv2 CUPS filter; see
  [[notes/2026-05-27-tsp143iiiu-default-mode]] for the byte-by-byte
  derivation and the load-bearing `ESC * r R / ESC * r A` quirk.
- **`printer.py`** — opens the USB device (`StarUsbPrinter`) using raw `pyusb`
  (no `python-escpos`), writes bytes to bulk OUT endpoint 0x02, closes. The
  cut command is part of the Star Graphic job sequence emitted by
  `star_raster`, configured by `Receipt.cut()` setting a flag on the
  Receipt object.
- **`session.py`** *(phase 4)* — reads
  `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`, extracts token totals,
  files touched, tool calls, wall time. Pure function — JSONL in, dict out.
- **`state.py`** — read/write `~/.thermal-printer/state.json`, override via
  `THERMAL_PRINT_STATE` env var for tests.

The narrative summary is **not** a module. The `/receipt` slash command at
`.claude/commands/receipt.md` runs inside the parent Claude Code session
(which has the full transcript in context), writes the 3-5 line narrative
directly, and passes it to the CLI via `--summary`. No LLM API call, no
`anthropic` dep. See [[decisions/0006-llm-summary]] for the rationale.

## The one emitter of printer bytes

Only **`star_raster.py`** emits raw Star Graphic bytes. `receipt.py` composes
a PIL image; `printer.py` moves bytes onto USB without composing them.
Templates never touch the wire format; the CLI never does. This keeps the
layout grammar testable in isolation (render to bytes → snapshot test, with
a structural assertion that the byte stream contains the load-bearing "enter
raster mode" sequence) and the device adapter swappable if the printer ever
changes.

## Runtime deps

`pyusb`, `Pillow`, plus `libusb` from Homebrew. Python 3.11+, macOS only.
**`python-escpos` and `anthropic` were both dropped on 2026-05-27** —
`python-escpos` because the TSP143IIIU doesn't speak ESC/POS, `anthropic`
because the narrative summary now comes from the parent Claude Code session
via `--summary`.
