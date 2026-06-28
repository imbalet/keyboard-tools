"""Brightness, on/off, and status for the RedSquare Keyrox TKL Classic.

The keyboard supports 5 discrete hardware brightness levels (0, 25, 50, 75,
100 %). This CLI sends only the APPLY command (0x07) with the brightness byte,
so the RGB profile stored in the keyboard firmware is preserved.
"""

from __future__ import annotations

import argparse
import sys

import usb.core

VID, PID = 0x0416, 0xB23C
EP_OUT = 0x04

# Percentage -> hardware level byte (see PROTOCOL.md)
LEVELS = {0: 0, 25: 1, 50: 2, 75: 3, 100: 4}

# APPLY command template. Byte 7 is the brightness level (0..4), filled at
# runtime. Byte 6 (0x0A) selects the user profile.
_APPLY_TEMPLATE = [
    0x01,
    0x07,
    0x00,
    0x00,
    0x00,
    0x0E,
    0x0A,
    0x00,
    0x03,
    0x80,
    0x00,
    0xFF,
    0x00,
    0x00,
    0x00,
    0x01,
]


def _send(dev, data) -> None:
    """Write a short HID report zero-padded to 64 bytes."""
    dev.write(EP_OUT, bytes(data) + bytes(64 - len(data)), timeout=2000)


def _apply_level(dev, level: int) -> None:
    """Send APPLY command with hardware brightness level (0..4)."""
    cmd = _APPLY_TEMPLATE.copy()
    cmd[7] = level
    _send(dev, cmd)


def _find_interface(dev) -> int | None:
    """Find the interface number that owns the OUT endpoint."""
    for iface in dev.get_active_configuration():
        for ep in iface:
            if ep.bEndpointAddress == EP_OUT:
                return iface.bInterfaceNumber
    return None


def _open_device():
    """Open the keyboard and detach the kernel HID driver if necessary."""
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("error: keyboard not found (USB 0416:b23c)", file=sys.stderr)
        sys.exit(2)

    iface = _find_interface(dev)
    if iface is not None:
        try:
            if dev.is_kernel_driver_active(iface):
                dev.detach_kernel_driver(iface)
        except Exception:
            # Some usb backends don't support detaching; not fatal.
            pass
    return dev


def _cmd_on(_args) -> None:
    _apply_level(_open_device(), 4)
    print("backlight: on")


def _cmd_off(_args) -> None:
    _apply_level(_open_device(), 0)
    print("backlight: off")


def _cmd_set(args) -> None:
    _apply_level(_open_device(), LEVELS[args.level])
    print(f"backlight: {args.level}%")


def _cmd_status(_args) -> None:
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    print("connected" if dev is not None else "not connected")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kbd-backlight",
        description=(
            "Control the backlight of the RedSquare Keyrox TKL Classic "
            "(RSQ20020, USB 0416:b23c)."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("on", help="turn backlight on").set_defaults(func=_cmd_on)
    sub.add_parser("off", help="turn backlight off").set_defaults(func=_cmd_off)

    p = sub.add_parser("set", help="set brightness, keeping current RGB profile")
    p.add_argument(
        "level",
        type=int,
        choices=sorted(LEVELS),
        metavar="{0,25,50,75,100}",
        help="brightness percentage",
    )
    p.set_defaults(func=_cmd_set)

    sub.add_parser("status", help="check if keyboard is connected").set_defaults(
        func=_cmd_status
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
