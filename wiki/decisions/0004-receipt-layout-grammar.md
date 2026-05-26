# ADR 0004 — Receipt layout grammar & builder API

**Status:** accepted (Planning) · part of [[index]]

## Context

[[brief]] calls out a **real receipt design spec** — 32-char grid, named
sections, double-height for headers, deliberate whitespace, a serial number
(`REC-#0042`), a footer divider — because the feel of the receipt as a designed
object matters as much as the data on it. The brief explicitly notes that this
is "the part most likely to be under-invested if I'm not careful." Locking the
grammar + helper API now means every template inherits the same look.

## Decision

### Layout constants

- **Grid width:** **32 characters** (Star TSP 100III default font A on 80mm
  paper).
- **Serial format:** `REC-#NNNN` — zero-padded, monotonically increasing,
  persisted to disk.
- **State file:** `~/.thermal-printer/state.json` — durable, human-editable,
  zero-deps. Override via env var `THERMAL_PRINT_STATE` (for tests).
- **Standard divider chars:** `-` (light), `=` (heavy), `·` (dotted spacer).
  Always full-width (32× the char).

### Receipt builder API (`thermal_print.receipt.Receipt`)

```python
r = Receipt()
r.logo("crab")                # raster PNG from assets/, centered
r.header("CLAUDE CODE")       # double-height, centered
r.subheader("session receipt")# single-height, centered, bold
r.divider("=")                # 32× '='
r.row("Tokens",  "4,221")     # left/right aligned, padded to 32
r.row("Time",    "47m")
r.spacer()                    # one blank line
r.text("matt was here.")      # left-aligned plain text
r.divider("-")
r.text("a sweet little summary line.")  # body paragraph, wrapped at 32
r.spacer()
r.footer("thermal-print")     # small, centered
r.serial()                    # 'REC-#0042', right-aligned, pulls + bumps state
r.cut()                       # partial cut
r.send(printer)               # flushes the accumulated escpos to USB
```

### Convention (not enforced)

Standard receipt structure: **logo → header → divider → body (rows/text) →
divider → footer → serial → cut.** Templates are free to deviate (a morning
card may skip the row table), but the primitives stay the same.

## Why

- **Shared primitives = visual consistency.** Every template should look like it
  belongs to the same family. If each template re-implements alignment, the
  family drifts within three templates.
- **32 chars is the *design choice*, not the printer's hardware limit.** The
  TSP 100III at font A on 80mm paper permits more (typically ~48 chars; the
  precise measurement is recorded in [[build-log]] from phase 1). 32 was
  picked for legibility at arm's length, not for density. Locking it in code
  means templates write strings, not pixels — and a string fitting the grid
  is a contract the helper can enforce.
  *(Hardened 2026-05-26: the original wording "32 chars is the printer's
  truth" was misleading.)*
- **`state.json` over SQLite / env / `/tmp`.** Durable, inspectable with `cat`,
  trivial to back up, no dep. Personal tool, single host — no concurrency
  concern.
- **A single emitter for layout.** `Receipt` is the only module that calls
  `python-escpos` for visual concerns. `printer.py` calls it only for device
  open / cut / final flush. Two emitters, clean boundary.

## Alternatives considered

- **Raw `python-escpos` calls inside each template.** Rejected — guarantees
  drift, undermines the "designed object" commitment from the brief.
- **YAML/markdown template DSL.** Captured in [[improvements]] — revisit if
  template count >5. For now, code is more flexible than data.
- **42-char grid (font B / condensed).** TSP 100III supports it. Rejected as
  default — font A reads better at arm's length, and the design intent is
  legible-from-the-fridge, not dense-as-possible. Templates can opt into font B
  if a specific layout needs the width.
- **Serial = UUID / timestamp.** Rejected — the brief specifies `REC-#NNNN`,
  which feels like a real POS receipt. Sequential serials are part of the feel.
- **XDG path `~/.local/state/thermal-printer/state.json`.** Tempting but
  ceremonial for a single-host personal tool. `~/.thermal-printer/` is shorter,
  more discoverable.

## Consequences

- The helper is the **only** place that knows about font-A width, alignment
  rules, and the standard structure. Templates never import `python-escpos`
  directly (enforced by lint convention, not by code).
- Adding a new visual primitive (barcode, QR, table) means extending
  `Receipt` — a deliberate friction that preserves consistency.
- `~/.thermal-printer/` and `state.json` are created lazily on first run; the
  directory must be writable. `THERMAL_PRINT_STATE=/tmp/...` env var makes
  tests hermetic.
- Snapshot tests of layout primitives (in phase 2) and of individual templates
  (in phase 3+) become possible — render `Receipt` to a byte stream, compare to
  a fixture. This is how we catch regressions in design without paper waste.
- **Serial-counter race is accepted, not fixed.** The read–modify–write inside
  `state.bump_serial()` is not locked. On a single-host, single-user personal
  tool, two `/receipt` invocations colliding in the same millisecond is
  effectively impossible; adding `fcntl.flock` would be ceremony with no
  payoff. *(Hardened 2026-05-26: Codex called this HIGH severity in the
  review; we kept it as a deferred accept — LOW for this deployment
  context. Revisit if the tool ever gets a second user or a background
  printer process.)*
