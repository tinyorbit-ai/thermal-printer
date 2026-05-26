# Build log

Part of [[index]]. One entry per phase: the verifiable gate that was met before
merge. Newest on top. Appended by `forge-ship`.

---

## Phase 1 — Hello: USB to paper (2026-05-26)

**Branch:** `phase/1-hello` → squashed onto `main`.

**What was done.** A minimal `thermal-print` CLI with one subcommand `hello`.
`src/thermal_print/printer.py` opens the Star TSP 100III over raw USB by
constant VID 0x0519 / PID 0x0017, forces `open()` eagerly so missing libusb,
missing device, and permission-denied surface as clean single-line errors,
writes `hello, matt`, fires a partial cut, and closes. `cli.py` is an
argparse dispatcher; `README.md` documents the `brew install libusb` +
`uv tool install .` install path plus the CUPS-removal gotcha.

**Why these choices.**
- VID/PID constants are the only printer-specific constants in the project;
  surfaced at the top of `printer.py` so a future hardware swap is one edit.
- Eager `p.open()` because python-escpos 3.1 defers it to first I/O — without
  forcing it, a missing device produces a deep traceback at the first text
  call rather than a clean error at startup.
- `printer.py` still emits the cut in phase 1; phase 2 moves cut ownership
  into `Receipt.cut()` and adds a snapshot assertion of "exactly one cut per
  receipt" (per the hardened plan, gate 5 of phase 2).

**Verifiable gate — status.**
- ✅ `uv sync && uv run thermal-print --help` parses; `thermal-print hello`
  exits 1 with the expected "no USB device" message when the printer is
  unplugged, confirming the error path.
- ⏳ **Hardware verification deferred to the end of the build loop** (per
  user instruction). Once the printer is connected, the following gate items
  must be observed and recorded back into this entry:
    1. `uv tool install . && thermal-print hello` exits 0 **and** paper reads
       `hello, matt`.
    2. Cutter fires audibly.
    3. **Unproven-dependency receipts** to fill in below.

**Unproven-dependency receipts** (the artifact this phase exists to produce —
fill these in after first successful physical print):
- **VID / PID:** assumed `0x0519` / `0x0017` (Star Micronics / TSP 100III
  family). Verify with `system_profiler SPUSBDataType | grep -A 10 Star`.
- **USB interface + endpoint:** python-escpos `Usb` defaults
  (interface 0, in_ep `0x82`, out_ep `0x01`). Record actual.
- **`detach_kernel_driver` / CUPS removal needed?** Record yes/no and what
  step (e.g. "removed Star from System Settings > Printers").
- **Command mode:** ESC/POS vs Star Line Mode (TSP 100III ships configurable;
  this is the project's biggest "what if it doesn't work" risk). Record
  what worked.
- **Working cut-command bytes:** record what `python-escpos`'s `cut()`
  produced on this unit (e.g. `b"\x1b\x69"` for ESC/POS partial cut).
- **Measured printable width at font A:** `___` chars. ADR 0004 calls the
  *design* grid 32 chars; the *hardware* maximum is typically wider on an
  80mm TSP 100III. Phase 3 updates ADR 0004 with this measurement.
- **Photograph of the receipt** attached.
