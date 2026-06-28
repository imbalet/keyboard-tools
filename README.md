# keyboard-tools

Backlight control and reverse-engineering tools for the **RedSquare Keyrox TKL Classic** keyboard (model **RSQ20020**, USB `0416:b23c`).

Reverse-engineered from a USB capture — see [PROTOCOL.md](PROTOCOL.md) for the full protocol notes.

## Features

| Command         | What it does                                       |
| --------------- | -------------------------------------------------- |
| `kbd-backlight` | Turn backlight on/off, set brightness level        |
| `kb-poc`        | Apply named RGB color profiles, save/restore state |
| `kb-map`        | Interactive tool to map LED indices to keys        |
| `kb-probe`      | Low-level protocol sequence for debugging          |

All commands are installed together — no extra flags or optional groups.

## Requirements

- Linux (udev-based USB access)
- Python ≥ 3.10
- `pyusb` (installed automatically)

## Install

```bash
# With uv
uv tool install git+https://github.com/<user>/keyboard-tools

# Or with pipx
pipx install git+https://github.com/<user>/keyboard-tools
```

## USB permissions (udev)

By default `/dev/bus/usb/*` requires root. Add a udev rule so the logged-in user can access the keyboard without `sudo`:

```bash
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0416", ATTR{idProduct}=="b23c", TAG+="uaccess"' \
    | sudo tee /etc/udev/rules.d/60-keyboard-tools.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Unplug and replug the keyboard once. Then verify with:

```bash
kbd-backlight status
```

You should see `connected`.

## Usage

### Basic backlight control

```bash
kbd-backlight on                 # full brightness, keeps current RGB profile
kbd-backlight off                # minimum level, keeps current RGB profile
kbd-backlight set 50             # 0 / 25 / 50 / 75 / 100
kbd-backlight status             # is the keyboard connected?
```

`kbd-backlight` only sends the APPLY command with a new brightness byte. It does **not** re-send RGB data, so any profile you set from the vendor software or via `kb-poc` stays intact.

### RGB profiles

```bash
kb-poc list                      # show available profiles
kb-poc apply rainbow             # apply a profile, scaled to state brightness
                                 # (hardware level is reset to 4 — see note below)
kb-poc brightness 25             # scale brightness of the current profile
kb-poc on                        # re-apply the last profile
kb-poc off                       # turn off (blanks all LEDs)
```

Profiles are defined in `keyboard_tools/reverse/kb.py` in the `PROFILES` dict. You can add your own — colors are `(R, G, B)` triples in `0..255`, keyed by key name (`"W"`, `"F1"`, `"SPACE"`, etc.), with `"*"` as the default for unmapped LEDs.

State (current profile and brightness) is saved in `$XDG_STATE_HOME/keyboard-tools/kb_state.json` (default: `~/.local/state/keyboard-tools/kb_state.json`).

> **Note on brightness:** `kbd-backlight` and `kb-poc brightness` control brightness at different levels:
>
> - `kbd-backlight set N` sets the **hardware** brightness byte (0..4).
> - `kb-poc brightness N` re-sends the RGB profile with values scaled to N% and commits the hardware byte to 4 (100%).
>
> If you use both, `kb-poc apply` / `kb-poc brightness` will reset the hardware level to 4. Re-run `kbd-backlight set N` afterwards if you want a specific hardware level.

### LED mapping

```bash
kb-map                           # interactive: press the key that lights up
kb-map --show                    # dump the current map
kb-map --test                    # light up all mapped LEDs (preview)
```

The LED map is stored in `$XDG_DATA_HOME/keyboard-tools/kb_led_map.json` (default: `~/.local/share/keyboard-tools/kb_led_map.json`).

### Low-level protocol probe

```bash
kb-probe 50                      # full GET/APPLY/COMMIT/FINALIZE sequence
kb-probe on
kb-probe off
```

Useful when experimenting with the protocol. **Note:** the command layout in `probe.py` is based on an older capture and differs slightly from the confirmed one in `PROTOCOL.md`. It's kept as a reference for further experiments, not as a replacement for `kbd-backlight`.

## Development

```bash
git clone https://github.com/<user>/keyboard-tools
cd keyboard-tools
uv sync --all-groups
uv tool install --editable .
```

The `dev` group brings `ruff`, `mypy`, and `pytest` for local checks.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

Reverse-engineered protocol. Use at your own risk — the author is not responsible for any damage to the keyboard firmware. Brightness commands are documented and confirmed by capture; other fields are still experimental.
