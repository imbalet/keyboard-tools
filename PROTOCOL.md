# Keyboard backlight protocol (reverse-engineered)

Notes reconstructed from a `usbmon` capture and the existing `backlight/cli.py` / `reverse/probe.py` code. This document describes the parts of the protocol that have been verified, plus the fields that remain unknown.

> **Disclaimer:** the protocol below is reverse-engineered. Values may change with firmware revisions of the keyboard. Confirmed fields were verified against the packet capture; unverified fields are marked accordingly.

## Device and transport

- Keyboard: RedSquare Keyrox TKL Classic (RSQ20020)
- USB VID:PID: `0416:b23c`
- Transport: USB HID (captured via `usbmon`)
- Device address in the reference capture: `1.30`
- OUT endpoint: `0x04`
- IN endpoint: `0x83` (also `0x81` for key events — not used by the backlight protocol)
- HID report size: 64 bytes; short commands are zero-padded.

The reference capture contains 474 USB packets. Most of the background traffic is periodic empty/service HID reports. Commands of interest go from the host to endpoint `0x04`.

## Brightness command (APPLY, opcode `0x07`)

This is the only command needed for brightness control. Confirmed report layout, padded to 64 bytes:

```text
01 07 00 00 00 0E 0A LL 03 80 00 FF 00 00 00 01
```

|   Offset | Value      | Purpose                  | Status               |
| -------: | ---------- | ------------------------ | -------------------- |
|      `0` | `01`       | HID report ID            | confirmed            |
|      `1` | `07`       | opcode / APPLY           | confirmed            |
|   `2..4` | `00 00 00` | reserved                 | probably reserved    |
|      `5` | `0E`       | sub-opcode               | confirmed            |
|      `6` | `0A`       | user profile selector    | confirmed by capture |
|      `7` | `LL`       | brightness level         | confirmed            |
|      `8` | `03`       | unknown fixed field      | not decoded          |
|      `9` | `80`       | unknown fixed field      | not decoded          |
|     `10` | `00`       | reserved                 | probably reserved    |
|     `11` | `FF`       | unknown, possibly a mask | not decoded          |
| `12..14` | `00 00 00` | reserved                 | probably reserved    |
|     `15` | `01`       | unknown terminator/flag  | not decoded          |

Observed `LL` values map linearly to brightness percentages:

| `LL`   | Brightness |
| ------ | ---------- |
| `0x00` | 0 %        |
| `0x01` | 25 %       |
| `0x02` | 50 %       |
| `0x03` | 75 %       |
| `0x04` | 100 %      |

In the reference capture the host cycles through:

```text
0x03 → 0x02 → 0x01 → 0x00 → 0x04
75%  → 50%  → 25%  → 0%   → 100%
```

This strongly confirms that offset `7` is the brightness byte.

## RGB profile transmission (opcode `0x09`)

Before an APPLY command, the host typically sends 8 reports of type `0x09`, each carrying a slice of the LED color map.

Chunk layout:

```text
01 09 00 00 NN SIZE [RGB DATA ...]
```

- `NN` — chunk index `0..7`.
- `SIZE` — payload size in bytes.
- Chunks `0..6`: `SIZE = 0x36` = 54 bytes = 18 RGB triples.
- Chunk `7`: `SIZE = 0x12` = 18 bytes = 6 RGB triples.
- Total: `7 * 18 + 6 = 132` LEDs.
- Each LED is a 3-byte `R G B` triple.

Example headers:

```text
01 09 00 00 00 36 ...  # chunk 0
01 09 00 00 01 36 ...  # chunk 1
...
01 09 00 00 07 12 ...  # chunk 7
```

### RGB and brightness interplay

In the capture, RGB batches and the APPLY command are sent together whenever brightness changes. Two models are consistent with the data:

1. **Host-side scaling:** the host pre-multiplies RGB values by the new brightness and re-sends the whole profile.
2. **Hardware scaling:** the host re-sends the unchanged profile and the APPLY command sets a hardware brightness level.

A single capture cannot distinguish between them. The current implementation of `kbd-backlight` assumes **model 2** and sends only the APPLY command on brightness change — this preserves whatever profile is currently stored in the keyboard, without re-sending 132 LEDs every time.

## Full protocol sequence (experimental, see `probe.py`)

The `kb-probe` tool wraps a longer sequence that the original vendor software appears to use. It has not been fully verified against the reference capture:

```text
GET_VERSION   → 0x01 0x0D
GET_SERIAL    → 0x01 0x15
GET_PROFILES  → 0x01 0x0A
GET_CONFIG    → 0x01 0x02
APPLY         → 0x01 0x07 ... (see above)
COMMIT        → 0x01 0x17 0x00 0x00 0x00 0x01
FINALIZE      → 0x01 0x08 ... (see probe.py)
```

The APPLY command emitted by `probe.py` is shorter than the confirmed one (missing profile `0x0A`, field `0x80`, and the tail). It is kept as-is for historical experiments — see the docstring in `probe.py` for details.

## Known unknowns

The following are not fully decoded and would require additional targeted captures:

- Exact purpose of bytes `0x03`, `0x80`, `0x00`, `0xFF` and trailing `0x01` in the APPLY command.
- Whether brightness is applied in hardware or pre-scaled by the host (see "RGB and brightness interplay" above).
- Whether the full RGB profile must be re-sent for a pure brightness change.
- Format of the `0x01` service report after APPLY.
- Purpose of the periodic `0x01` reports and incoming reports on `0x83`.
- Whether `COMMIT` (`0x17`) and `FINALIZE` (`0x08`) are required in any flow.
- Whether brightness persists across power cycles (flash) or resets on unplug.
- Whether additional profiles beyond `0x0A` exist.

## How to continue research

To confirm the remaining fields, capture **one isolated action per session**:

1. Change brightness without touching colors.
2. Change one RGB channel of one specific LED.
3. Turn backlight on/off only.
4. Save profile, then power-cycle the keyboard.
5. Read back current configuration and profile.

Record both initial and final state for each experiment, and avoid chaining multiple actions in one capture — otherwise variable bytes cannot be uniquely attributed to protocol functions.
