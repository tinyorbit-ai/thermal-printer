"""USB transport for the Star TSP 100III.

Only this module talks to the USB device. It opens the printer by
vendor/product ID, writes raw bytes, and closes. In phase 1 it also emits
the cut command directly — phase 2 moves cut ownership into the Receipt
builder (see [[plan]] phase 2 gate 5).
"""

from __future__ import annotations

import sys
from typing import Final

from escpos.exceptions import DeviceNotFoundError, USBNotFoundError
from escpos.printer import Usb
from usb.core import NoBackendError, USBError

# Star Micronics. VID is stable across the line.
VENDOR_ID: Final[int] = 0x0519
# TSP 100III family. Verified on hardware during phase 1 (system_profiler).
PRODUCT_ID: Final[int] = 0x0017


def open_printer() -> Usb:
    """Open the TSP 100III over raw USB.

    python-escpos 3.x defers `open()` until first I/O; we force it here so a
    missing printer / missing libusb / permission error surfaces with a
    clear message instead of a deep traceback on first write.
    """
    try:
        p = Usb(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        p.open()
        return p
    except NoBackendError:
        print(
            "error: libusb backend not found. Install with `brew install libusb`.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except (DeviceNotFoundError, USBNotFoundError, ValueError):
        print(
            f"error: no USB device with VID 0x{VENDOR_ID:04x} PID 0x{PRODUCT_ID:04x}. "
            "Confirm the printer is plugged in and powered, then run "
            "`system_profiler SPUSBDataType | grep -A 10 Star` to verify IDs.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except USBError as e:
        if getattr(e, "errno", None) == 13:
            print(
                "error: USB permission denied. macOS holds the device via CUPS — "
                "remove the printer from System Settings > Printers, then retry.",
                file=sys.stderr,
            )
        else:
            print(f"error: USB error: {e}", file=sys.stderr)
        raise SystemExit(1)


def print_hello() -> None:
    """Print 'hello, matt' and fire the cutter. Phase-1 smoke."""
    p = open_printer()
    try:
        p.textln("hello, matt")
        p.cut()
    finally:
        p.close()
