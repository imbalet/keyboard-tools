"""Interactive LED-to-key mapping tool for the RedSquare Keyrox TKL Classic.

Run:
    kb-map             start/continue mapping
    kb-map --show      dump current map
    kb-map --test      preview current map on hardware
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import usb.core
import usb.util

VID, PID = 0x0416, 0xB23C
EP_OUT = 0x04
EP_KEYS = 0x81
LED_COUNT = 132

# HID keycode -> key name (USB HID Usage Tables, Keyboard/Keypad page 0x07)
HID_NAMES: dict[int, str] = {
    0x29: "ESC",
    0x3A: "F1",
    0x3B: "F2",
    0x3C: "F3",
    0x3D: "F4",
    0x3E: "F5",
    0x3F: "F6",
    0x40: "F7",
    0x41: "F8",
    0x42: "F9",
    0x43: "F10",
    0x44: "F11",
    0x45: "F12",
    0x46: "PRTSC",
    0x47: "SCRLK",
    0x48: "PAUSE",
    0x35: "`",
    0x1E: "1",
    0x1F: "2",
    0x20: "3",
    0x21: "4",
    0x22: "5",
    0x23: "6",
    0x24: "7",
    0x25: "8",
    0x26: "9",
    0x27: "0",
    0x2D: "-",
    0x2E: "=",
    0x2A: "BACKSPACE",
    0x2B: "TAB",
    0x14: "Q",
    0x1A: "W",
    0x08: "E",
    0x15: "R",
    0x17: "T",
    0x1C: "Y",
    0x18: "U",
    0x0C: "I",
    0x12: "O",
    0x13: "P",
    0x2F: "[",
    0x30: "]",
    0x31: "\\",
    0x39: "CAPS",
    0x04: "A",
    0x16: "S",
    0x07: "D",
    0x09: "F",
    0x0A: "G",
    0x0B: "H",
    0x0D: "J",
    0x0E: "K",
    0x0F: "L",
    0x33: ";",
    0x34: "'",
    0x28: "ENTER",
    0xE1: "LSHIFT",
    0x1D: "Z",
    0x1B: "X",
    0x06: "C",
    0x19: "V",
    0x05: "B",
    0x11: "N",
    0x10: "M",
    0x36: ",",
    0x37: ".",
    0x38: "/",
    0xE5: "RSHIFT",
    0xE0: "LCTRL",
    0xE3: "LWIN",
    0xE2: "LALT",
    0x2C: "SPACE",
    0xE6: "RALT",
    0xE7: "RWIN",
    0x65: "MENU",
    0xE4: "RCTRL",
    0x49: "INS",
    0x4A: "HOME",
    0x4B: "PGUP",
    0x4C: "DEL",
    0x4D: "END",
    0x4E: "PGDN",
    0x52: "UP",
    0x50: "LEFT",
    0x51: "DOWN",
    0x4F: "RIGHT",
}

# LEDs to probe during mapping. Expand to cover more of the keyboard.
SAMPLE_LEDS = [101]


def _data_dir() -> Path:
    """Return (and create) the directory for user LED map data."""
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    d = Path(base) / "keyboard-tools"
    d.mkdir(parents=True, exist_ok=True)
    return d


MAP_FILE = _data_dir() / "kb_led_map.json"


def send(dev, data) -> None:
    dev.write(EP_OUT, bytes(data) + bytes(64 - len(data)), timeout=2000)


def _apply(dev) -> None:
    """Send APPLY command with user profile at full brightness."""
    send(
        dev,
        [
            0x01,
            0x07,
            0x00,
            0x00,
            0x00,
            0x0E,
            0x0A,
            0x04,
            0x03,
            0x80,
            0x00,
            0xFF,
            0x00,
            0x00,
            0x00,
            0x01,
        ],
    )


def _send_leds(dev, leds) -> None:
    """Send LED_COUNT (R, G, B) triples as 8 chunks."""
    flat: list[int] = []
    for r, g, b in leds:
        flat += [r, g, b]
    for chunk in range(7):
        payload = flat[chunk * 54 : chunk * 54 + 54]
        send(dev, [0x01, 0x09, 0x00, 0x00, chunk, 0x36] + payload)
    payload = flat[7 * 54 : 7 * 54 + 18]
    send(dev, [0x01, 0x09, 0x00, 0x00, 0x07, 0x12] + payload)


def light_single(dev, led_idx: int, r: int = 255, g: int = 255, b: int = 255) -> None:
    """Light one LED and turn the rest off."""
    leds = [(0, 0, 0)] * LED_COUNT
    leds[led_idx] = (r, g, b)
    _send_leds(dev, leds)
    _apply(dev)


def lights_off(dev) -> None:
    _send_leds(dev, [(0, 0, 0)] * LED_COUNT)
    _apply(dev)


def read_keypress(dev, timeout_ms: int = 10000):
    """Wait for a key press on EP_KEYS. Return HID keycode or None on timeout."""
    deadline = time.time() + timeout_ms / 1000
    last = bytes(8)

    while time.time() < deadline:
        try:
            data = bytes(dev.read(EP_KEYS, 8, timeout=100))
        except usb.core.USBTimeoutError:
            continue

        if data == last:
            continue
        if data == bytes(8):  # key release
            last = data
            continue

        last = data
        modifier = data[0]
        keycodes = [data[i] for i in range(2, 8) if data[i] != 0]

        # Handle modifier keys as standalone presses
        mod_map = {
            0x01: 0xE0,
            0x02: 0xE1,
            0x04: 0xE2,
            0x08: 0xE3,
            0x10: 0xE4,
            0x20: 0xE5,
            0x40: 0xE6,
            0x80: 0xE7,
        }
        mod_keys = [code for bit, code in mod_map.items() if modifier & bit]

        all_keys = mod_keys + keycodes
        if all_keys:
            return all_keys[0]

    return None


def load_map() -> dict[int, str]:
    if MAP_FILE.exists():
        with open(MAP_FILE) as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items()}
    return {}


def save_map(m: dict[int, str]) -> None:
    with open(MAP_FILE, "w") as f:
        json.dump({str(k): v for k, v in sorted(m.items())}, f, indent=2)


def get_device():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("keyboard not found (USB 0416:b23c)", file=sys.stderr)
        sys.exit(1)

    cfg = dev.get_active_configuration()

    # Detach kernel driver from interfaces owning the endpoints we use.
    for target_ep in (EP_OUT, EP_KEYS):
        for iface in cfg:
            for ep in iface:
                if ep.bEndpointAddress == target_ep:
                    try:
                        if dev.is_kernel_driver_active(iface.bInterfaceNumber):
                            dev.detach_kernel_driver(iface.bInterfaceNumber)
                    except Exception:
                        pass
                    break

    return dev


def cmd_show() -> None:
    m = load_map()
    if not m:
        print("LED map is empty. Run without arguments to start mapping.")
        return
    print(f"Map: {len(m)} LEDs assigned\n")
    for led, key in sorted(m.items()):
        print(f"  LED {led:3d}  ->  {key}")


def cmd_test(dev) -> None:
    m = load_map()
    if not m:
        print("LED map is empty.")
        return
    print("Lighting all mapped LEDs...")
    palette = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
        (255, 128, 0),
        (128, 0, 255),
    ]
    leds = [(0, 0, 0)] * LED_COUNT
    for i, (led, _key) in enumerate(sorted(m.items())):
        leds[led] = palette[i % len(palette)]

    _send_leds(dev, leds)
    _apply(dev)
    print("Done. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def cmd_map(dev) -> None:
    current_map = load_map()
    already_mapped = set(current_map.keys())
    to_probe = [i for i in SAMPLE_LEDS if i not in already_mapped]

    if not to_probe:
        print(f"All {len(SAMPLE_LEDS)} sample LEDs already mapped.")
        print("Add more LEDs to SAMPLE_LEDS or run --show to inspect.")
        return

    print(f"Already mapped: {len(already_mapped)} LEDs")
    print(f"Remaining to probe: {len(to_probe)} LEDs")
    print()
    print("Controls:")
    print("  Press the key that lights up")
    print("  Space - skip this LED (not a key / not visible)")
    print("  Ctrl+C - save and exit")
    print()
    input("Press Enter to start...")
    print()

    mapped_now = 0
    skipped = 0

    try:
        for led_idx in to_probe:
            print(
                f"LED {led_idx:3d}/{LED_COUNT - 1}  "
                f"[{mapped_now} mapped, {skipped} skipped]",
                end="  ",
                flush=True,
            )
            light_single(dev, led_idx)

            keycode = read_keypress(dev, timeout_ms=15000)

            if keycode is None:
                print("- timeout, skipping")
                skipped += 1
                continue
            if keycode == 0x2C:  # Space = skip
                print("- skipped")
                skipped += 1
                continue

            key_name = HID_NAMES.get(keycode, f"KEY_{keycode:#04x}")
            print(f"-> {key_name}")

            current_map[led_idx] = key_name
            mapped_now += 1
            save_map(current_map)
            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n\nInterrupted.")

    lights_off(dev)
    print(f"\nSaved to {MAP_FILE}")
    print(f"Total: {len(current_map)} LEDs mapped")
    print(f"\nNext step: kb-map --show")


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""

    if arg == "--show":
        cmd_show()
        return

    dev = get_device()

    if arg == "--test":
        cmd_test(dev)
    else:
        cmd_map(dev)


if __name__ == "__main__":
    main()
