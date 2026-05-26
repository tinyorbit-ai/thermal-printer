# ADR 0001 — Shape: Python CLI + python-escpos + raw USB

**Status:** accepted (Discovery) · part of [[index]]

## Context

thermal-printer is a personal CLI driving a Star TSP 100III over USB on macOS, with a Claude Code `/receipt` slash command as the primary use case. The project's feel is "tactile, satisfying — a real POS receipt" and the work touches three roughly-equal axes: printer integration, Claude Code wiring, and receipt design.

The first real fork was the language + transport for the CLI. Choosing wrong here cascades: ESC/POS libraries, raster-bitmap pipelines, macOS USB permissions, and the slash-command shim all depend on this.

## Decision

- **Language/runtime:** Python 3.
- **ESC/POS library:** `python-escpos` (mature; supports Star printers; built-in raster bitmap encoding for the crab logo; image conversion via Pillow).
- **Transport:** raw USB via `pyusb` + `libusb` (installed via Homebrew). No CUPS in the path.
- **Architecture:** template-driven. The CLI exposes `print <template> [args]`; `/receipt` is the first template implementation. Future templates (morning, ship-receipt, end-of-day) plug in via a templates module without forking the tool.

## Why

- **Speed-to-MVP.** `python-escpos` already handles ESC/POS, raster bitmaps, and Star TSP support. Most of the printer-integration plumbing is solved on day one.
- **Three-axis project.** Receipt design and Claude Code wiring need attention too. Picking the language with the lightest plumbing leaves more time for those.
- **macOS USB ergonomics.** PyUSB + libusb on macOS is well-trodden. No CUPS filter quirks blocking raw ESC/POS bytes.
- **Tactile-feel alignment.** Raw USB gives full control over raster bitmaps (crab logo) and cut commands. CUPS would obscure these.
- **Template architecture** matches the ambition decision to make this a system of printable rituals rather than a one-shot `/receipt` command.

## Alternatives considered

- **Node/TypeScript + escpos-buffer + USB.** Matches my daily React Native muscle memory. Rejected: Node escpos libs are thinner; macOS USB permissions from Node are fiddlier; bitmap pipeline is more glue. Wrong fit for fastest path to a working v1.
- **Rust + `escpos` crate.** Single static binary, fastest runtime, most satisfying tactile feel as a tool. Rejected for now: slowest to MVP — escpos crate is solid but more glue, and the prototype-first ethos (per CLAUDE.personal.md) means MVP first, polish later. A future "rewrite in Rust" is captured as a possibility, not a plan.
- **Shell + macOS `lp`/CUPS.** Minimal code — add the printer once in System Settings, then `lp file.escpos`. Rejected: CUPS filters can mangle raw ESC/POS escapes; raster bitmap pipeline is harder; loses the direct relationship with the device that makes the tactile feel real.
- **No template system — just `/receipt`.** Considered and rejected in the ambition check. Cost is small (~1 phase) and unlocks a system of printable rituals rather than a one-shot command.

## Consequences

- Hard runtime dep on Python 3, `python-escpos`, `pyusb`, `Pillow`, plus `libusb` from Homebrew. README/CLAUDE.md must document the install path.
- macOS-only by virtue of `libusb` install path and lack of Windows/Linux testing — already a non-goal.
- The TSP 100III's USB vendor/product IDs are encoded somewhere (config or constants). If I ever buy a different printer, that constant changes.
- Slash-command shim lives at `.claude/commands/receipt.md` and calls into the CLI. Slash command and CLI evolve together but are decoupled — the CLI works standalone, and the slash command is a thin layer that gathers Claude Code context and pipes it in.
- A "template" is a first-class concept from day one. Adding new printable rituals means adding a template, not editing the CLI's command-dispatch layer.
- Print is fire-and-forget for this release; no log/replay (see [[improvements]]).
