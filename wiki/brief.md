# Brief — thermal-printer

Part of [[index]].

## What it is

A personal CLI for the Star TSP 100III thermal printer, connected via USB to this MacBook. It prints structured "receipts" from Claude Code sessions and other rituals. The first and primary use: a Claude Code slash command `/receipt` that prints a physical receipt of the current session — Claude Code crab logo banner, project header, deterministic facts (tokens, time, files, tools, commits), an LLM-generated 3–5 line summary, and a footer.

The CLI itself is general: `print <thing>` accepts anything and renders it through a named **template**. `/receipt` is the first template; future templates (morning intention card, per-commit ship receipt, end-of-day summary) plug in without forking the tool.

## Who & when

Just me, Matt. Two moments:

- **End of a Claude Code session.** I invoke `/receipt`. ~2 seconds later, paper comes out. I tear it off and either pin it to the wall or file it. The act of receiving the receipt is the close of the session.
- **Ad-hoc, from the terminal.** I pipe text or invoke a named template. Same printer, same aesthetic.

## How it should feel

**Tactile and satisfying — a real POS receipt.** Snappy, instant, the kachunk-of-the-cutter at the end. Tight monospace layout, dense info, a little nostalgic. The receipt is a physical artifact of intangible work; the feel of getting one matters as much as the data on it.

This drives:
- A real **receipt design spec** (see [[decisions/0001-shape]] and forthcoming layout ADR): 32-char grid, named sections, double-height for headers, deliberate whitespace, a serial number (`REC-#0042`), a footer divider.
- Sub-second latency from invocation to first byte to the printer.
- Zero ceremony at the CLI — `print` and `/receipt` Just Work.

## The hard/interesting part

All three roughly equally:

1. **Printer integration.** Speaking ESC/POS (or Star Line Mode) to the TSP 100III over raw USB on macOS. Raster bitmap encoding for the crab logo. Cut commands. Getting reliable behavior across cold-start / paper-out / cover-open.
2. **Claude Code wiring.** Reading the current session's JSONL transcript from `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` to pull deterministic stats. Wiring the `/receipt` slash command so it passes live context to the CLI. Calling Claude (Haiku) for the 3–5 line summary.
3. **Receipt design.** A typography & layout spec that makes the receipt feel right — not "stats on paper" but a small, designed object. This is the part most likely to be under-invested if I'm not careful.

## Constraints

- macOS only, this specific MacBook.
- USB only. Printer is Star TSP 100III (USB connection confirmed).
- Python 3 + `python-escpos` + PyUSB + `libusb` (via Homebrew).
- The CLI is a CLI — no daemon, no background process; one invocation, one print, exit.
- Slash-command integration uses Claude Code's `.claude/commands/` mechanism.
- Don't run servers locally without asking ([[personal-claude-rules]]).

## Non-goals

- **Not a general-purpose ESC/POS library.** Hardcoding TSP 100III assumptions is fine.
- **Not network / AirPrint / Bluetooth.** USB only, even if "easy to add later."
- **Not a daemon or service.** Per-invocation. No tray icon, no menu bar, no socket.
- **Not cross-platform.** macOS only. No Windows / Linux / homebrew tap / installer.
- **Not a print log / replay system** (this release). Captured as a deliberate scope cut in [[improvements]] — revisit when I have a concrete reason.
- **Never asks "is it worth printing?"** No throttling, no rate limits, no "are you sure you want to print again". Receipts are cheap; the joy is the point.

## Shape chosen

**Python CLI + `python-escpos` + raw USB (libusb).** Single executable command (`tp` or similar) plus a `.claude/commands/receipt.md` slash-command wrapper. Internally organized around a **template** concept so `/receipt` is the first of many printable rituals, not the only one.

Why this shape over the alternatives:

- vs **Node/TS**: matches my muscle memory less, but Node ESC/POS libs are thinner and macOS USB permissions are fiddlier from Node. Python's libs are mature.
- vs **Rust**: a single static binary would be satisfying but slows the MVP. Defer the rewrite-in-Rust temptation; the wiki captures it if I want to.
- vs **Shell + `lp`/CUPS**: simplest code but worst control over raster bitmaps (crab logo) and ESC/POS escapes. Wrong trade for a tactile aesthetic.

See [[decisions/0001-shape]] for the full reasoning and alternatives weighed.

## Ambition register

- **Adopted:** template system (multiple printable rituals, `/receipt` is the first); real receipt design spec (32-char grid, double-height headers, serials, intentional typography).
- **Deferred:** lossless print log + replay (see [[improvements]]).
- **Held:** USB-only, macOS-only, no daemon, no library — these stay tight on purpose.
