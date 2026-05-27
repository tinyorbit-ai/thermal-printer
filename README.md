# thermal-printer

A Python CLI that drives a **Star TSP143IIIU** thermal printer over raw
USB, plus a `/receipt` Claude Code slash command that prints a physical
receipt of a coding session — tokens, time, files touched, lines added,
cost, and a 3–5 line narrative written by the session's own Claude.

```
                            ┌──────────────┐
                            │   CLAUDE     │  (the actual logo)
                            │      session │
                            └──────┬───────┘
                                   │
                   Model   opus-4-7│
                   Wall time 1h 32m│
                   Turns       480 │
                   ────────────────│
                   Tokens in    568│
                   Tokens out 454K │
                   Cache hit   99M │
                   Cost      $45.54│
                   ────────────────│
                   Bash         154│
                   Write         42│
                   Edit          38│
                   Read          15│
                   Files          43│
                   Lines +1354 -381│
                   ────────────────│
                   five phases shipped.
                   reverse-engineered
                   star raster from cups.
                   the printer sings.
                                   │
                                   ▼ (cut)
```

## Install

macOS only. Requires Python 3.11+, [`uv`](https://docs.astral.sh/uv/),
and `libusb` from Homebrew.

```sh
brew install libusb
uv tool install .
```

If the Star is already paired in **System Settings → Printers**, remove
it first — macOS otherwise holds the device via CUPS and `pyusb` cannot
claim the interface.

## Daily use

From inside a Claude Code session, type:

```
/receipt
```

…and the slash command at `.claude/commands/receipt.md` writes the
narrative summary from its own context and shells out to the CLI.

From a terminal, manually:

```sh
thermal-print print demo                                        # visual showcase
thermal-print print session --session-id $SID --cwd $PWD        # stats only
thermal-print print receipt --session-id $SID --cwd $PWD \
  --summary "your 3-5 line narrative."                          # stats + narrative
thermal-print print playground                                  # layout test
thermal-print print mandala                                     # procedural art
```

The session-id mechanism is the `CLAUDE_CODE_SESSION_ID` env var (also
just `$PWD` for `--cwd`); inside a Claude Code session both are
available without any setup.

## Templates

`thermal-print print <name>` dispatches to any module in
`src/thermal_print/templates/`. Each module exposes `NAME: str` and
`render(ctx, r: Receipt)`. Drop a new file there, run the CLI — done.
The shipped set:

| Template     | What it does                                                       |
|--------------|--------------------------------------------------------------------|
| `hello`      | Smoke test. `hello, matt` + cut.                                   |
| `demo`       | Exercises every primitive — logo, header, dividers, rows, footer.  |
| `session`    | Deterministic session stats from a Claude Code JSONL.              |
| `receipt`    | `session` + narrative summary passed via `--summary`.              |
| `playground` | Layout test. Touches every Receipt method; useful after refactors. |
| `mandala`    | Procedural radial bitmap, unique each print. Pushes the raster path. |

## How it talks to the printer

The TSP143IIIU does **not** speak ESC/POS — it ships in Star Graphic
raster mode and silently drops character-stream commands. The protocol
was reverse-engineered from Star's open-source CUPS filter and is
encoded by `src/thermal_print/star_raster.py`. See
[`wiki/notes/2026-05-27-tsp143iiiu-default-mode.md`](wiki/notes/2026-05-27-tsp143iiiu-default-mode.md)
for the byte-by-byte derivation and the load-bearing
`ESC * r R / ESC * r A` quirk.

`Receipt` is a bitmap renderer: every primitive draws onto a 576-pixel-
wide growing PIL image; `send()` crops to actual content, encodes as
Star Graphic bytes via `star_raster.encode_job`, and writes one USB
transaction.

## Development

From a checkout:

```sh
uv sync
uv run pytest -q
uv run thermal-print print hello
```

Tests cover the bitmap byte stream (snapshot + structural assertions),
template auto-discovery, the persistent serial counter, the Claude
Code JSONL parser, and both new templates.

## Troubleshooting

- **`libusb backend not found`** → `brew install libusb`.
- **`no USB device with VID … PID …`** → confirm the printer is plugged
  in and powered. Run `ioreg -p IOUSB -l | grep -A2 Star` to see the
  actual VID/PID; if they don't match `src/thermal_print/printer.py`,
  update the constants and file a wiki note.
- **`USB permission denied`** → remove the Star from System Settings →
  Printers, unplug/replug the USB cable, retry.
- **Bytes accepted but no paper** → the printer is probably in a non-
  Star-Graphic command mode (StarPRNT, ESC/POS). See
  [`wiki/notes/2026-05-27-tsp143iiiu-default-mode.md`](wiki/notes/2026-05-27-tsp143iiiu-default-mode.md)
  for the discovery story; the working bytes are in `star_raster.py`.

## Project map

```
src/thermal_print/
  cli.py              # argparse + dispatch + flag plumbing
  printer.py          # raw pyusb device adapter (StarUsbPrinter)
  receipt.py          # Receipt — bitmap renderer (the 32-char grid lives here)
  star_raster.py      # Star Graphic encoder (PIL Image → bytes)
  session.py          # Claude Code JSONL parser + cost calc + line counting
  state.py            # ~/.thermal-printer/state.json — persistent serial counter
  templates/
    hello.py / demo.py / session.py / receipt.py / playground.py / mandala.py
  assets/
    claude.png        # 400x240 1-bit Claude logo, block-character derived

wiki/
  index.md            # map of content
  brief.md            # what we're building, for whom, the feel
  plan.md             # the locked, hardened phased plan
  architecture.md     # the 30-second version (kept current)
  build-log.md        # one entry per phase, the gate met before merge
  decisions/          # ADRs 0001-0006
  notes/              # incident write-ups (TSP143IIIU mode discovery lives here)

.claude/commands/
  receipt.md          # the /receipt slash command
```

## License

MIT — see [LICENSE](LICENSE).
