# thermal-printer

A CLI to drive a Star TSP 100III thermal printer over raw USB. The
foundation for `/receipt` — a Claude Code slash command that prints a
physical receipt of a coding session (see `wiki/brief.md`).

## Install

macOS only. Requires Python 3.11+, [`uv`](https://docs.astral.sh/uv/),
and `libusb` from Homebrew.

```sh
brew install libusb
uv tool install .
```

If the Star is already paired in **System Settings → Printers**, remove it
first — macOS will otherwise hold the device via CUPS and `pyusb` cannot
claim the interface.

## Daily use

```sh
thermal-print print demo                           # the visual showcase
thermal-print print session --session-id $SID --cwd $PWD   # deterministic stats
thermal-print print receipt --session-id $SID --cwd $PWD   # stats + Haiku narrative
```

…or, from inside Claude Code, type `/receipt` — the slash command shim
at `.claude/commands/receipt.md` does the right thing.

Set `ANTHROPIC_API_KEY` in your environment to activate the narrative
summary on `print receipt`; without it the receipt prints with
`(summary unavailable)` and the stats unchanged.

## Templates

`thermal-print print <name>` dispatches to any module in
`src/thermal_print/templates/`. Each module exposes `NAME: str` and
`render(ctx, r: Receipt)`. Drop a new file there, run the CLI — done.
The shipped set:

- `hello` — `hello, matt`, smoke test.
- `demo` — exercises every primitive in the receipt grammar.
- `session` — deterministic session stats (tokens, time, files, tools).
- `receipt` — `session` + a 3-5 line Haiku narrative.

## Development

From a checkout:

```sh
uv sync
uv run thermal-print hello
```

## Troubleshooting

- **`libusb backend not found`** → `brew install libusb`.
- **`no USB device with VID … PID …`** → confirm the printer is plugged in
  and powered. Run `system_profiler SPUSBDataType | grep -A 10 Star` to
  see the actual VID/PID; if they don't match `src/thermal_print/printer.py`,
  update the constants and file a wiki note.
- **`USB permission denied`** → remove the Star from System Settings →
  Printers, unplug/replug the USB cable, retry.
