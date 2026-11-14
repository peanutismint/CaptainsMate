# CaptainsMate project notes

Shared context for anyone (or any Claude chat) working on CaptainsMate. Last updated 2026-11-14 (late).

## What it is

A browser editor plus custom CircuitPython 7.3.1 firmware for the PaintAudio MIDI Captain 10 STD foot controller (RP2040, 240x240 screen, 10 keys, encoder wheel, 2 expression inputs, USB MIDI and DIN MIDI).

- Repo: https://github.com/peanutismint/CaptainsMate
- Test emulator (the editor, no pedal needed): https://peanutismint.github.io/CaptainsMate/editor/captainsmate.html
- `editor/captainsmate.html`: single-file editor. Web Serial (Chrome or Edge) talks to the pedal. It has an Examples picker, per-message test buttons, Web MIDI output and a pedal monitor.
- `firmware/code.py`, `boot.py`, `config.json`: what runs on the pedal.
- `examples/`: `example-config.json` (generic 3-page starter), `AT200-counters.json`, `waza-air-config.json`.
- `tools/embed_examples.py`: re-embeds `examples/` into the editor. Run it after editing any example.
- Commits made by Claude carry a `Co-Authored-By` trailer. Pushing needs the Claude GitHub App installed on the repo.

## Working agreements

- After any firmware change, attach the updated `code.py` in the chat.
- Hardware tests go one small step at a time, pausing for answers.
- Written copy uses commas, not em dashes.
- Be explicit about what is verified on hardware and what is not.

## Installing firmware on the pedal

Copy `code.py` (and `boot.py` if it changed) onto the pedal's USB drive, then it restarts. When Dev mode is off, `boot.py` hides the USB drive so the pedal can save its own config and the charge timer. Send and Receive in the editor go over the serial link, and the serial line protocol uses `@PING`, `@INFO`, `@GET`, `@BEGIN`, `@D`, `@END`, `@MON` and `@TX`. `@PONG` and `@INFO` lines report `free=` memory. Large configs can run the pedal out of RAM, so the editor shows a size chip.

## Config model (short version)

`pages[]` each with `buttons[10]`, `encoder`, `expression`. Keys 5 and 10 are usually page keys (`page_inc`, `page_dec`). A key has a base `color` (dim when idle) and `short` and `long` lists of states, each with its own `color`, optional `label`, `dim` (false means stay lit after firing) and `down` and `up` message lists. Message types: cc, pc, pc_inc, pc_dec, cc_inc, cc_dec, note, sysex, press (a macro that taps other keys). Counters use `cc`, `cc_min`, `cc_max`, `cc_step`, `cc_wrap`, `initial` and `names`. `radio` puts keys in an exclusive group. `show` controls the pop-up. Top-level keys include `midi_channel`, `long_press_threshold_ms`, `led_idle`, `screen_brightness`, `screen_idle_brightness`, `screen_idle_seconds`, `dev_mode`, `midi_through`, `sysex_preamble`, `battery_*`, `charge_max_hours`, `charge_need_usb`, `wireless`, `wireless_id`, `wireless_db`.

## Hardware facts

Verified on the pedal unless marked otherwise.

| Thing | Pin or value | Status |
|---|---|---|
| Keys | GP1, GP25, GP24, GP23, GP20, GP9, GP10, GP11, GP18, GP19 | working |
| NeoPixels | GP7 | working |
| DIN MIDI | UART TX GP16, RX GP17, 31250 baud | output working |
| Encoder | GP2, GP3 | in firmware, from stock |
| Expression | GP27, GP28 | in firmware |
| Display | SPI GP14, GP15, DC GP12, CS GP13 | working |
| Backlight | PWM on GP8 | from the stock firmware, not yet confirmed on hardware |
| Charge enable | GP6, high means charging on | working: voltage rises while on, controlled test still to finish |
| Battery sense | GP29, divider 3 | confirmed: reads the cells with or without USB. The CircuitPython build is plain `raspberry_pi_pico`, which has no `board.GP29`, so open it with `pin_of("GP29")` (falls back to `microcontroller.pin.GPIO29`) |
| GP26 | supply rail | reads about 4.6 V when USB is plugged in |
| Wireless radio (blue and gold Pro only) | GP4 and GP5 plus an 18-byte config packet | decoded from stock, untested, black STD has no radio |

Source of the stock facts: disassembly of the stock FW5.16 image. The stock firmware also has keys for `WIRELESS_2.4G`, `WIRELESS_ID`, `WIRELESS_dB`, `midithrough`, `externalmidicontrol` and `externalmidicontrolch`.

## Battery and charging

- The battery sense is hard-coded to GP29 with divider 3, so there is nothing to configure. Measured: cells about 2.8 V total at rest (multimeter), display 2.5 V on battery and 2.8 V on USB.
- Percent is a rough estimate (NiMH voltage is flat). Readings with nothing drawing from the cells (on USB) are about 0.3 V higher than when the cells run the pedal, so 0.3 V is taken off first. While charging, the charge current pushes the voltage up, so every 60 s charging pauses for 3 s and the reading is taken at the end of the pause.
- Charging is off by default. GP6 only goes high when charging is on in the config and the battery type is not alkaline and USB is connected (unless `charge_need_usb` is false) and the on-time is under `charge_max_hours` (default 8, at most 12). The on-time is saved about every 5 minutes so reboots do not restart the clock, but only when Dev mode is off. It resets when charging is switched off.
- While charging a yellow bolt shows beside the reading (blinking in percent and voltage styles). The icon keeps whole segments solid, blinks the next one, and blinks the outline green when full.
- Status: GP6 high and cool cells seen once, but the first test was not clean because the timer restarted on reboots. A controlled test (1 hour limit, no reboots, measure each cell before and after) is still to do.

## boot.py (v4, working on hardware 2026-11-14)

- Shows the drive when `dev_mode` is true, the config cannot be read, or key 1 (GP1) is held at power-up. Otherwise it hides the drive and remounts `/` writable, so the pedal can save. Hiding alone is not enough: without `storage.remount("/", readonly=False)` code.py still gets "Read-only filesystem".
- GP1 reads low for a moment after the pull-up is enabled, so boot.py waits 0.15 s and needs 5 low reads in a row to count key 1 as held. Hold key 1 until the screen comes on to get the drive.
- It prints its reasoning to `boot_out.txt`, for example `CaptainsMate boot: config ok, dev_mode=False; switch 1 not held (reads 11111); drive hidden; writable`.
- boot.py only runs on a real restart (Restart pedal in the editor, or the power switch). With batteries fitted, unplugging USB does not restart the pedal.
- Repeated large config pushes fragment RAM (allocation of about 16 KB fails with 30 KB or more free). Restart before pushing again.

## Waza-Air (Boss headphones)

- Control is Roland SysEx, device ID 00. Config: `examples/waza-air-config.json`, 4 pages, about 10.5 KB.
- Route: pedal DIN out, CME WIDI Master (Bluetooth MIDI), headphones. Working as of 2026-11-13. The WIDI Master had been pairing to a phone and a PC instead of the headphones. With the PC Bluetooth off it goes solid turquoise and the pedal controls the headphones.
- `sysex_preamble` (a list of hex strings in the config) is sent before the first SysEx after boot, so the session setup no longer needs the CONNECT key.
- Open item: the top-left key labelled 1 sends the patch 5 SysEx, so the key rows look swapped compared with the config.

## AT-200 (Peavey)

Known CCs: capo CC11 (range 52 to 76, centre 64), model CC14 (11 names), doubler CC27 (10 names), tune CC7 (13 names), expression CC12 and CC13. Preset recall by program change. The AT-200 complete pack can hold 64 presets, about 15 saved. The preset bank on page 2 of the example assumes PC 0 to 7, so it needs adjusting to the presets actually used. The rest of the AT-200 CC table is not yet collected.

## Not verified on hardware

Sysex through the private `_outport`, the GP8 backlight, MIDI through, the wireless packet, the `chg_state.txt` timer file. The charging rest readings and bolt work on the pedal (87% shown while charging, 2026-11-14).

## Backlog

- Charging test (above).
- Possible external-power detection from GP26 compared with GP29, which would also cover wall chargers.
- Stock config import (geekmode text files), external MIDI control, per-expression MIDI channel, config warnings, share links.
- Page-on-demand loading to cut RAM use, AT-200 acoustic sub-model key (CC22), shared expression and encoder across pages.
- Wireless: needs a tester with a blue or gold unit.
