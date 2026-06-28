"""Low-level protocol probe for the RedSquare Keyrox TKL Classic.

Sends the full initialization sequence:
    GET_VERSION -> GET_SERIAL -> GET_PROFILES -> GET_CONFIG
    -> APPLY -> COMMIT -> FINALIZE

Useful for experimenting with the protocol when the simple APPLY command
(used by kbd-backlight) isn't enough. The exact command layout in this file
is based on an older capture and may need adjustment - see PROTOCOL.md.
"""

from __future__ import annotations

import sys
import time

import usb.core
import usb.util

VID, PID = 0x0416, 0xB23C
BRIGHTNESS = {0: 0, 25: 1, 50: 2, 75: 3, 100: 4}


def find_out_endpoint(dev) -> int:
    for iface in dev.get_active_configuration():
        for ep in iface:
            if (
                usb.util.endpoint_direction(ep.bEndpointAddress)
                == usb.util.ENDPOINT_OUT
            ):
                return ep.bEndpointAddress
    raise RuntimeError("OUT endpoint not found")


def send(dev, ep_out: int, data) -> None:
    payload = bytes(data) + bytes(64 - len(data))
    dev.write(ep_out, payload, timeout=2000)


def recv(dev, ep_in: int):
    try:
        return bytes(dev.read(ep_in, 64, timeout=500))
    except usb.core.USBTimeoutError:
        return None


def init_and_set(dev, ep_out: int, brightness_level=None, backlight_on=None) -> None:
    # 1. GET_VERSION
    send(dev, ep_out, [0x01, 0x0D])
    recv(dev, ep_out)
    recv(dev, ep_out)
    time.sleep(0.2)

    # 2. GET_SERIAL
    send(dev, ep_out, [0x01, 0x15])
    recv(dev, ep_out)

    # 3. GET_PROFILES
    send(dev, ep_out, [0x01, 0x0A])
    recv(dev, ep_out)

    # 4. GET_CONFIG
    send(dev, ep_out, [0x01, 0x02])
    recv(dev, ep_out)
    time.sleep(0.3)

    # 5. APPLY
    if backlight_on is not None:
        send(
            dev,
            ep_out,
            [
                0x01,
                0x07,
                0x00,
                0x00,
                0x00,
                0x0E,
                0x00,
                0x04,
                0x03,
                0xFF,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x01,
                0x00 if backlight_on else 0x01,
            ],
        )
    elif brightness_level is not None:
        send(
            dev,
            ep_out,
            [
                0x01,
                0x07,
                0x00,
                0x00,
                0x00,
                0x0E,
                0x00,
                brightness_level,
                0x03,
                0xFF,
            ],
        )

    # 6. COMMIT
    time.sleep(0.01)
    send(dev, ep_out, [0x01, 0x17, 0x00, 0x00, 0x00, 0x01])
    recv(dev, ep_out)

    # 7. FINALIZE
    time.sleep(0.02)
    send(
        dev,
        ep_out,
        [
            0x01,
            0x08,
            0x00,
            0x00,
            0x00,
            0x0D,
            0x02,
            0x03,
            0x03,
            0xFF,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x01,
        ],
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: kb-probe 0|25|50|75|100 | on | off", file=sys.stderr)
        sys.exit(1)

    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("keyboard not found (USB 0416:b23c)", file=sys.stderr)
        sys.exit(1)

    # Do NOT detach kernel driver for this tool - historically the protocol
    # sequence worked without detaching. Revisit if needed.
    try:
        dev._ctx.managed_claim_interface = lambda *a, **k: None
    except AttributeError:
        pass  # older pyusb; claim_interface may still work
    dev.set_configuration()

    ep_out = find_out_endpoint(dev)

    # Claim a vendor-specific interface (everything except interface 0).
    vendor_if = None
    for intf in dev.get_active_configuration():
        if intf.bInterfaceNumber != 0:
            vendor_if = intf.bInterfaceNumber
            break
    usb.util.claim_interface(dev, vendor_if)

    arg = sys.argv[1].lower()

    if arg == "off":
        init_and_set(dev, ep_out, backlight_on=False)
        print("backlight off")
    elif arg == "on":
        init_and_set(dev, ep_out, backlight_on=True)
        print("backlight on")
    else:
        level = int(arg)
        if level not in BRIGHTNESS:
            print(f"allowed: {sorted(BRIGHTNESS)}", file=sys.stderr)
            sys.exit(1)
        init_and_set(dev, ep_out, brightness_level=BRIGHTNESS[level])
        print(f"brightness {level}%")


if __name__ == "__main__":
    main()
