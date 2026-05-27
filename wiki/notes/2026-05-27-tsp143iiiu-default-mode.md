# 2026-05-27 — TSP143IIIU ships in Star Raster mode (not ESC/POS)

Part of [[index]]. Incident write-up for the phase 1 hardware verification.

## Timeline

- **Phase 1 (code-only).** Wrote `printer.py` against `python-escpos` with
  assumed VID 0x0519 / PID 0x0017 and python-escpos's default endpoints.
  Code-level gate green; hardware verification deferred.
- **2026-05-27, hardware probe.** Plugged in the Star TSP143IIIU. `ioreg`
  reports VID 0x0519 / **PID 0x0003** (the assumed 0x0017 was wrong).
- **First print attempt** failed with `Invalid endpoint address 0x1` —
  python-escpos defaults to `out_ep=0x01`, but the real device has its
  bulk OUT on `0x02` (IN on `0x81`). Fixed by passing explicit
  `interface=0 / in_ep=0x81 / out_ep=0x02` to the `Usb(...)`
  constructor.
- **Second attempt** succeeded over USB (write returned the right byte
  count, no errors) — **but no paper came out.**
- Tried plain ASCII with line feeds: no paper.
- Tried full ESC/POS sequence (`ESC @` init + text + `\n` feeds + `GS V
  0` full cut): no paper.
- Self-test (FEED button + power-cycle) printed cleanly. Firmware
  reports model `TSP100IIIU`, Print Area 72mm, Cutter Enabled,
  `<2>8 = Print Start Control: Page`, PID `TSP100IIU Compatible`.
- Tried Star Line Mode (`ESC FF` page-eject + `ESC d` feed + `ESC i`
  partial cut): no paper.

## Root cause

The Star **TSP100 family** (including TSP143IIIU) ships in **Star
Raster / futurePRNT mode by default** — not ESC/POS, not even Star Line
Mode. In Raster mode the firmware expects bitmap raster data
(`ESC GS S 1`, raster lines, `ESC FF`) and silently drops any
character-stream payload. That's why every text-based byte stream we
sent succeeded at the USB layer (`dev.write` returned non-zero) and
produced no paper.

The self-test's `<2>8 = Print Start Control: Page` is a hint that the
firmware is in Page mode (buffered until page-eject), but the Page-mode
buffering is downstream of the Raster protocol entry point — flushing
the page doesn't help when the buffer never accepted the bytes in the
first place.

## What this demonstrates

The hardened plan called this exact risk out:

> **The TSP 100III's command dialect is the single unproven dependency
> the whole project rests on.** The printer ships configurable between
> ESC/POS and Star Line Mode; `python-escpos` will not drive it
> correctly in the wrong mode, and nothing else in the plan matters if
> Phase 1 doesn't get paper out.

The review was almost right — the failure mode is even worse than
expected. The default mode is not even Star Line Mode; it's the
proprietary Raster mode, which Star Line Mode commands *also* don't
drive.

## The protocol that actually works

Star Quick Setup Utility is App Store-only and not available on Apple
Silicon. Instead, we dug through Star's open-source CUPS filter
(`rastertostar.c`, GPLv2) on a third-party GitHub mirror and
reverse-engineered the exact byte sequence. Verified on hardware
2026-05-27: paper out with `hello, matt` and the partial cutter fires.

The TSP143IIIU only accepts **Star Graphic raster** — a bitmap-per-page
protocol, **not** character data. python-escpos's ESC/POS byte stream
is invisible to this printer. The byte sequence below is the minimum
that works:

```
# jobSetup
ESC @                                        — printer init
ESC GS 0x03 0x03 0x00 0x00                   — clear-data-start (TSP143-specific)
ESC * r R ESC * r A                          — *** ENTER RASTER MODE *** (load-bearing)
ESC * r P 0x30 0x00                          — page type = receipt
ESC * r E '1' '3' 0x00                       — doc cut type = partial cut

# pageSetup
0x00                                         — start page

# per scan line (one or the other)
'b' wLow wHigh <data...>                     — raster line, data is 1-bit packed, MSB first
ESC * r Y <n_ascii_digits> 0x00              — skip N blank lines

# endPage
ESC * r Y '1' 0x00 ESC FF                    — feed-and-eject

# endJob
ESC GS 0x03 0x04 0x00 0x00                   — clear-data-finish (TSP143-specific)
0x04 ESC * r B                               — EOT + end raster job
```

The **load-bearing piece** is `ESC * r R ESC * r A`. Without it the
printer accepts every byte, reports no error, returns clean port
status (online, paper present, no error) — and silently drops the
entire job. With it, paper comes out.

## What this means for the codebase

The project's current `printer.py` + `Receipt` + every template are
built on `python-escpos`, which composes ESC/POS character-stream
bytes. **None of those bytes drive this printer.** The Star Graphic
raster path is purely bitmap-based: every character, divider, row,
and logo must be rendered into a PIL `Image` and then emitted as
raster lines.

The architecture in [[architecture]] still holds — single device
adapter, single layout module, templates compose into a builder —
but the *internals* of `Receipt` and `printer.py` need a rewrite:

- `Receipt` accumulates a PIL `Image` (a 576-pixel-wide, growing-tall
  monochrome canvas) instead of a `Dummy` byte buffer. Methods
  (`header`, `row`, `divider`, `text`, `logo`, `serial`, `footer`,
  `cut`) draw onto it.
- `Receipt.send(printer)` encodes the image as Star Graphic raster
  lines and emits the full jobSetup → pageSetup → lines → endPage →
  endJob sequence to USB.
- `printer.py` no longer wraps `python-escpos`'s `Usb`; it opens
  the device with raw `pyusb` and exposes `_raw(bytes)` / `close()`.
- Tests' snapshot fixtures regenerate against the new byte stream.
- ADR 0001 needs an amendment note: "raw USB via pyusb" still holds,
  but `python-escpos` no longer drives the actual output — we use it
  only for offline rendering tricks (or drop it entirely).
- ADR 0004's "32 chars at font A" is now a **rendering choice** in
  the bitmap, not a property of any character-stream printer.

## Hardware constants verified

The constants this incident locked into the codebase
(`src/thermal_print/printer.py`):

| Constant       | Value  | How verified                                            |
|----------------|--------|---------------------------------------------------------|
| VENDOR_ID      | 0x0519 | `ioreg -p IOUSB -l`                                     |
| PRODUCT_ID     | 0x0003 | `ioreg` (assumed 0x0017 was wrong)                       |
| USB_INTERFACE  | 0      | descriptor dump (`pyusb`)                                |
| USB_IN_EP      | 0x81   | descriptor dump                                          |
| USB_OUT_EP     | 0x02   | descriptor dump (python-escpos's default 0x01 was wrong)|
| IEEE 1284 ID   | `MFG:Star;CMD:STAR;MDL:TSP143 (STR_T-001);CLS:PRINTER;` | USB Printer Class GET_DEVICE_ID |
| Printable area | 72mm / 576px | self-test print + Star CUPS filter `TSP100_MAX_WIDTH 72` |
| Command set    | Star Graphic raster (NOT ESC/POS, NOT Star Line Mode) | hardware verification 2026-05-27 |
| Cut command    | `ESC * r E '1' '3' 0x00` (partial cut, set during jobSetup) | rastertostar.c + hardware |

The constants this incident locked into the codebase
(`src/thermal_print/printer.py`):

| Constant       | Value  | How verified                                            |
|----------------|--------|---------------------------------------------------------|
| VENDOR_ID      | 0x0519 | `ioreg -p IOUSB -l`                                     |
| PRODUCT_ID     | 0x0003 | `ioreg` (assumed 0x0017 was wrong)                       |
| USB_INTERFACE  | 0      | descriptor dump (`pyusb`)                                |
| USB_IN_EP      | 0x81   | descriptor dump                                          |
| USB_OUT_EP     | 0x02   | descriptor dump (python-escpos's default 0x01 was wrong)|
| Printable area | 72mm   | self-test print                                          |
