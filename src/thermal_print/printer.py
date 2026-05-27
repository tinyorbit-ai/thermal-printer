"""USB transport for the Star TSP143IIIU.

Only this module talks to the USB device. It opens the printer by
vendor/product ID, claims the interface, writes raw bytes, and closes.
No ESC/POS / python-escpos involvement — the device only accepts the
Star Graphic raster command set encoded by :mod:`star_raster`.
"""

from __future__ import annotations

import sys
from typing import Final

import usb.core
import usb.util
from usb.core import NoBackendError, USBError

# Verified on hardware 2026-05-27 via `ioreg -p IOUSB -l`:
# `Star TSP143IIIU`, idVendor=1305 (0x0519), idProduct=3 (0x0003).
VENDOR_ID: Final[int] = 0x0519
PRODUCT_ID: Final[int] = 0x0003

# Endpoints — discovered from a real device descriptor dump, NOT
# python-escpos defaults (which assume out=0x01 / in=0x82). For the
# TSP143IIIU on USB 2.0: interface 0 class 0x07 (Printer),
# bulk OUT on 0x02, bulk IN on 0x81.
USB_INTERFACE: Final[int] = 0
USB_OUT_EP: Final[int] = 0x02

# Wall-clock deadline for a single USB write. Receipts run ~1-3 KB —
# never close to this limit. Large enough to absorb a power cycle window.
WRITE_TIMEOUT_MS: Final[int] = 10_000


class StarUsbPrinter:
    """Thin wrapper around an opened pyusb device.

    Holds the claimed interface for the duration of one print job and
    releases it on :meth:`close`. Receipt.send() owns the open/close
    lifecycle.
    """

    def __init__(self, dev: usb.core.Device) -> None:
        self._dev = dev
        self._open = True

    def write(self, data: bytes) -> None:
        if not self._open:
            raise RuntimeError("printer is closed")
        self._dev.write(USB_OUT_EP, data, timeout=WRITE_TIMEOUT_MS)

    def close(self) -> None:
        if not self._open:
            return
        try:
            usb.util.release_interface(self._dev, USB_INTERFACE)
        finally:
            usb.util.dispose_resources(self._dev)
            self._open = False


def open_printer() -> StarUsbPrinter:
    """Open the TSP143IIIU over raw USB.

    Surfaces three failure modes the user can actually act on: libusb
    not installed, USB permission denied, device not found.
    """
    try:
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    except NoBackendError:
        print(
            "error: libusb backend not found. Install with `brew install libusb`.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if dev is None:
        print(
            f"error: no USB device with VID 0x{VENDOR_ID:04x} PID 0x{PRODUCT_ID:04x}. "
            "Confirm the printer is plugged in and powered, then run "
            "`ioreg -p IOUSB -l | grep -A2 Star` to verify IDs.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        try:
            dev.set_configuration()
        except USBError:
            # Already configured by macOS — non-fatal.
            pass
        usb.util.claim_interface(dev, USB_INTERFACE)
        return StarUsbPrinter(dev)
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
