"""RGB profile manager for the RedSquare Keyrox TKL Classic (RSQ20020).

Usage:
    kb-poc apply <profile>       apply a named profile
    kb-poc brightness <0-100>    set brightness (keeps current profile)
    kb-poc off                   turn backlight off
    kb-poc on                    turn backlight on (last profile)
    kb-poc list                  list available profiles

Profiles are defined in the PROFILES dict below. Colors are (R, G, B)
triples in 0..255. Keys are key names (see LED_KEY_MAP); "*" is the default
color for unmapped LEDs.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import usb.core

# ─────────────────────────────────────────────────────────────────────
# PROFILES
# ─────────────────────────────────────────────────────────────────────
PROFILES: dict[str, dict] = {
    # Example: personal profile with purple F-row
    "mine": {
        "*": (255, 0, 0),
        "ESC": (128, 0, 255),
        "F1": (128, 0, 255),
        "F2": (128, 0, 255),
        "F3": (128, 0, 255),
        "F4": (128, 0, 255),
        "F5": (128, 0, 255),
        "F6": (128, 0, 255),
        "F7": (128, 0, 255),
        "F8": (128, 0, 255),
        "F9": (128, 0, 255),
        "F10": (128, 0, 255),
        "F11": (128, 0, 255),
        "F12": (128, 0, 255),
        "PRTSC": (128, 0, 255),
        "SCRLK": (128, 0, 255),
        "PAUSE": (128, 0, 255),
        "LWIN": (128, 0, 255),
    },
    # Single-color examples
    "red": {"*": (255, 0, 0)},
    "green": {"*": (0, 255, 0)},
    "blue": {"*": (0, 0, 255)},
    "white": {"*": (255, 255, 255)},
    # WASD and arrows highlighted
    "gaming": {
        "*": (20, 20, 20),
        "W": (255, 200, 0),
        "A": (255, 200, 0),
        "S": (255, 200, 0),
        "D": (255, 200, 0),
        "UP": (255, 200, 0),
        "LEFT": (255, 200, 0),
        "DOWN": (255, 200, 0),
        "RIGHT": (255, 200, 0),
        "SPACE": (0, 150, 255),
        "LSHIFT": (0, 150, 255),
        "LCTRL": (0, 150, 255),
        "ESC": (255, 0, 0),
        "1": (200, 100, 0),
        "2": (200, 100, 0),
        "3": (200, 100, 0),
        "4": (200, 100, 0),
    },
    # Rainbow by rows
    "rainbow": {
        "*": (255, 0, 0),
        "F1": (255, 100, 0),
        "F2": (255, 100, 0),
        "F3": (255, 100, 0),
        "F4": (255, 100, 0),
        "F5": (255, 200, 0),
        "F6": (255, 200, 0),
        "F7": (255, 200, 0),
        "F8": (255, 200, 0),
        "F9": (200, 255, 0),
        "F10": (200, 255, 0),
        "F11": (200, 255, 0),
        "F12": (200, 255, 0),
        "`": (255, 150, 0),
        "1": (255, 200, 0),
        "2": (200, 255, 0),
        "3": (100, 255, 0),
        "4": (0, 255, 0),
        "5": (0, 255, 100),
        "6": (0, 255, 200),
        "7": (0, 200, 255),
        "8": (0, 100, 255),
        "9": (0, 0, 255),
        "0": (100, 0, 255),
        "-": (200, 0, 255),
        "=": (255, 0, 200),
        "BACKSPACE": (255, 0, 100),
        "TAB": (255, 50, 0),
        "Q": (200, 255, 0),
        "W": (0, 255, 0),
        "E": (0, 255, 150),
        "R": (0, 150, 255),
        "T": (0, 0, 255),
        "Y": (100, 0, 255),
        "U": (255, 0, 200),
        "I": (255, 0, 100),
        "O": (255, 50, 0),
        "P": (200, 200, 0),
        "CAPS": (0, 200, 255),
        "A": (0, 0, 255),
        "S": (100, 0, 255),
        "D": (200, 0, 200),
        "F": (255, 0, 100),
        "G": (255, 50, 0),
        "H": (200, 200, 0),
        "J": (0, 255, 0),
        "K": (0, 255, 200),
        "L": (0, 150, 255),
        "ENTER": (0, 0, 255),
        "LSHIFT": (255, 0, 0),
        "Z": (200, 0, 100),
        "X": (150, 0, 200),
        "C": (0, 0, 255),
        "V": (0, 150, 255),
        "B": (0, 255, 150),
        "N": (0, 255, 0),
        "M": (150, 255, 0),
        "RSHIFT": (255, 100, 0),
        "LCTRL": (100, 100, 100),
        "LALT": (100, 100, 100),
        "SPACE": (50, 50, 255),
        "RALT": (100, 100, 100),
        "RCTRL": (100, 100, 100),
    },
}

DEFAULT_PROFILE = "mine"

# ─────────────────────────────────────────────────────────────────────
# LED -> key name (reverse-engineered, see PROTOCOL.md)
# ─────────────────────────────────────────────────────────────────────
LED_KEY_MAP: dict[int, str] = {
    0: "ESC",
    2: "F1",
    3: "F2",
    4: "F3",
    5: "F4",
    7: "F5",
    8: "F6",
    9: "F7",
    10: "F8",
    11: "F9",
    12: "F10",
    13: "F11",
    14: "F12",
    15: "PRTSC",
    16: "SCRLK",
    17: "PAUSE",
    22: "`",
    23: "1",
    24: "2",
    25: "3",
    26: "4",
    27: "5",
    28: "6",
    29: "7",
    30: "8",
    31: "9",
    32: "0",
    33: "-",
    34: "=",
    35: "BACKSPACE",
    36: "BACKSPACE",
    37: "INS",
    38: "HOME",
    39: "PGUP",
    44: "TAB",
    45: "Q",
    46: "W",
    47: "E",
    48: "R",
    49: "T",
    50: "Y",
    51: "U",
    52: "I",
    53: "O",
    54: "P",
    55: "[",
    56: "]",
    57: "\\",
    58: "\\",
    59: "DEL",
    60: "END",
    61: "PGDN",
    66: "CAPS",
    67: "CAPS",
    68: "A",
    69: "S",
    70: "D",
    71: "F",
    72: "G",
    73: "H",
    74: "J",
    75: "K",
    76: "L",
    77: ";",
    78: "'",
    79: "ENTER",
    80: "ENTER",
    88: "LSHIFT",
    89: "LSHIFT",
    90: "Z",
    91: "X",
    92: "C",
    93: "V",
    94: "B",
    95: "N",
    96: "M",
    97: ",",
    98: ".",
    99: "/",
    100: "RSHIFT",
    102: "RSHIFT",
    104: "UP",
    110: "LCTRL",
    111: "LWIN",
    112: "LALT",
    113: "SPACE",
    114: "SPACE",
    115: "SPACE",
    116: "SPACE",
    117: "SPACE",
    118: "SPACE",
    119: "SPACE",
    120: "RALT",
    121: "RWIN",
    122: "MENU",
    123: "RCTRL",
    125: "LEFT",
    126: "DOWN",
    127: "RIGHT",
}

VID, PID = 0x0416, 0xB23C
EP_OUT = 0x04
LED_COUNT = 132


def _state_dir() -> Path:
    """Return (and create) the directory for mutable state files."""
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    d = Path(base) / "keyboard-tools"
    d.mkdir(parents=True, exist_ok=True)
    return d


STATE_FILE = _state_dir() / "kb_state.json"


# ─────────────────────────────────────────────────────────────────────
# USB primitives
# ─────────────────────────────────────────────────────────────────────
def get_device():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("keyboard not found (USB 0416:b23c)", file=sys.stderr)
        sys.exit(1)

    for iface in dev.get_active_configuration():
        for ep in iface:
            if ep.bEndpointAddress == EP_OUT:
                try:
                    if dev.is_kernel_driver_active(iface.bInterfaceNumber):
                        dev.detach_kernel_driver(iface.bInterfaceNumber)
                except Exception:
                    pass
                return dev
    return dev


def send(dev, data) -> None:
    dev.write(EP_OUT, bytes(data) + bytes(64 - len(data)), timeout=2000)


def send_rgb(dev, leds_rgb) -> None:
    """Send a list of LED_COUNT (R, G, B) triples as 8 HID chunks."""
    flat: list[int] = []
    for r, g, b in leds_rgb:
        flat += [r, g, b]
    for chunk in range(7):
        payload = flat[chunk * 54 : chunk * 54 + 54]
        send(dev, [0x01, 0x09, 0x00, 0x00, chunk, 0x36] + payload)
    payload = flat[7 * 54 : 7 * 54 + 18]
    send(dev, [0x01, 0x09, 0x00, 0x00, 0x07, 0x12] + payload)


def commit(dev, level: int = 4) -> None:
    """Send APPLY command with hardware brightness level 0..4."""
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
            level,
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


# ─────────────────────────────────────────────────────────────────────
# Profile -> LED colors
# ─────────────────────────────────────────────────────────────────────
def profile_to_leds(profile: dict, brightness: float = 1.0):
    default = profile.get("*", (0, 0, 0))
    leds = []
    for i in range(LED_COUNT):
        key = LED_KEY_MAP.get(i)
        if key and key in profile:
            color = profile[key]
        else:
            color = default if key else (0, 0, 0)
        r = min(255, int(color[0] * brightness))
        g = min(255, int(color[1] * brightness))
        b = min(255, int(color[2] * brightness))
        leds.append((r, g, b))
    return leds


def apply_profile(dev, profile_name: str, brightness: float = 1.0) -> None:
    if profile_name not in PROFILES:
        print(
            f"profile '{profile_name}' not found; available: {', '.join(PROFILES)}",
            file=sys.stderr,
        )
        sys.exit(1)
    leds = profile_to_leds(PROFILES[profile_name], brightness)
    send_rgb(dev, leds)
    commit(dev, 4)


# ─────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"profile": DEFAULT_PROFILE, "brightness": 100, "on": True}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────
def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0].lower()

    if cmd == "list":
        state = load_state()
        print("Available profiles:")
        for name in PROFILES:
            marker = "  (current)" if name == state.get("profile") else ""
            print(f"  {name}{marker}")
        return

    dev = get_device()
    state = load_state()

    if cmd == "apply":
        if len(args) < 2:
            print("usage: kb-poc apply <profile>", file=sys.stderr)
            sys.exit(1)
        name = args[1]
        brightness = state.get("brightness", 100) / 100.0
        apply_profile(dev, name, brightness)
        state["profile"] = name
        state["on"] = True
        save_state(state)
        print(f"profile '{name}' applied (brightness {int(brightness * 100)}%)")

    elif cmd == "brightness":
        if len(args) < 2:
            print(f"current brightness: {state.get('brightness', 100)}%")
            return
        level = int(args[1])
        if not 0 <= level <= 100:
            print("brightness must be 0..100", file=sys.stderr)
            sys.exit(1)
        name = state.get("profile", DEFAULT_PROFILE)
        apply_profile(dev, name, level / 100.0)
        state["brightness"] = level
        state["on"] = level > 0
        save_state(state)
        print(f"brightness {level}% (profile '{name}')")

    elif cmd == "off":
        send_rgb(dev, [(0, 0, 0)] * LED_COUNT)
        commit(dev, 0)
        state["on"] = False
        save_state(state)
        print("backlight off")

    elif cmd == "on":
        name = state.get("profile", DEFAULT_PROFILE)
        brightness = state.get("brightness", 100) / 100.0
        apply_profile(dev, name, brightness)
        state["on"] = True
        save_state(state)
        print(f"profile '{name}' on")

    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
