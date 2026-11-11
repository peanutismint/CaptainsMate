# CaptainsMate

A friendly, browser-based editor and lightweight custom firmware for the **MIDI Captain 10 STD** foot controller (RP2040, CircuitPython). Design your pages and keys in a visual editor, press **Send**, and the pedal updates instantly. No ejecting drives, no rebooting, no hand-editing JSON.

> Unofficial community project. Not affiliated with or endorsed by Paint Audio or any other brand mentioned here. Use at your own risk, and keep a backup of your stock firmware.

## Features

**Editor (runs in Chrome or Edge, one HTML file, no install)**
- Visual 10-key grid with pages (add, duplicate, delete, rename), copy/paste keys
- Key types: **Momentary**, **Toggle**, **Counter** (up/down, wrap, named values), **Sequence** (multi-step), **Page up/down**
- Messages: Control Change, Program Change, Notes, preset/value up and down, and raw **SysEx**; per-message MIDI channel
- Short-press and long-press actions, per-state LED colors
- Big pop-up on the pedal screen showing counter values, preset numbers or value names
- Encoder wheel (changes pages or sends a CC) and two expression inputs
- Live screen preview, undo/redo, light/dark/auto theme, built-in MIDI basics and guide
- **Send / Receive over USB** with Web Serial, auto-receive on connect, and a log tab for troubleshooting

**Firmware**
- Reads one `config.json`; applies uploads live, no reboot
- Sends to USB MIDI and 5-pin DIN at the same time
- Battery indicator (voltage, percent, or icon) and optional NiMH charging (experimental)
- Optional "dev mode" keeps the USB drive visible; otherwise it is hidden for safety

## Quick start

1. Make sure your pedal runs CircuitPython (see [Installing on the pedal](#installing-on-the-pedal)), then copy `firmware/code.py`, `firmware/boot.py` and `firmware/config.json` to its USB drive.
2. Open `editor/captainsmate.html` in Chrome or Edge.
3. Click **Connect pedal** and choose the pedal's serial port. The editor reads its current config.
4. Edit keys, then click **Send**. Changes apply instantly and are saved on the pedal.

Want to see everything at once? Open `examples/example-config.json` in the editor. It's a three-page pro-style setup: stage pedals (drive, delay, momentary reverb, FX loop, tap tempo with tuner on long press, presets), a looper and scenes page, and an extras page (drum notes, sustain, song select, SysEx master volume, MIDI panic). Edit the CC numbers to match your own gear.

## How keys work

Every key has a **type**, and every type can do something different on a **tap** (short press) and on a **hold** (long press, default 600 to 700 ms, adjustable in settings). Messages can go out when you **press down** and when you **release**.

### Key types and when to use them

| Type | What it does | Use it for |
|---|---|---|
| **Momentary** | Sends one value while held, another on release | Reverb swell only while your foot is down, a temporary boost for a solo, a whammy or freeze effect, a sustain pedal |
| **Toggle** | Each tap flips ON / OFF (and the LED changes color) | Drive, delay, FX loop, compressor, anything you leave on |
| **Counter (up / down)** | Steps a value up or down, optionally wraps and shows names on screen | Scene or snapshot select (Verse / Chorus / Solo), amp or channel select, volume or level in steps, bank select |
| **Sequence** | Each tap moves to the next state; every state sends its own messages and has its own LED color | Clean / Crunch / Lead channel cycling, tap through delay subdivisions, step through a song's parts |
| **Page up / down** | Switches to the next or previous page of 10 keys | A "stage" page, a "looper" page, a "setlist" page: 10 keys is never enough |

### What a tap, a hold and a release are good for

- **Tap**: your everyday action (toggle the effect, next preset).
- **Hold (long press)**: a second function on the same key. For example, tap = tap tempo and hold = open the tuner; tap = next scene and hold = jump back to scene 1; tap = boost on and hold = force it off; tap = undo and hold = clear the loop.
- **Press down vs. release**: send on press for instant response (tap tempo, drum pads). Send on release to prevent accidental double-triggers, or pair the two for momentary behavior (value 127 on press, 0 on release).
- **Several messages on one key**: one key can send many messages at once, such as switching the amp channel and bypassing a pedal in a single press.

### Message types

- **Control Change (CC)**: knobs and switches on most gear, for example CC 64 as tap tempo or CC 11 for expression.
- **Program Change (PC)** and **preset up/down**: recall presets or songs.
- **Notes**: trigger drum pads, samplers and synths; velocity controls how hard.
- **SysEx**: raw hex messages for device-specific commands that CCs can't reach, like master volume or switching a specific effect module.
- **MIDI channel**: set one global channel, or override it on any single message so one pedal can control several devices.

### Other features

- **Pop-up display**: shows a large number or name on the pedal screen when you press a key, such as the preset number, the counter value or a state name ("Chorus", "-3 steps"). A zero point can be subtracted so a counter centered on 64 reads as 0.
- **Encoder wheel**: scroll through pages, or send a CC as you turn it (mix level, patch volume).
- **Expression inputs (EXP1 / EXP2)**: send a CC that follows a pedal position, like wah or volume. They're off by default to avoid stray signals.
- **Pages and key copy/paste**: duplicate a whole page or copy a single key to any other key.
- **Battery**: shows level as voltage, percent or an icon, and optionally charges rechargeable NiMH batteries (experimental, leave it off if you use alkaline).

## Installing on the pedal

CaptainsMate's firmware (`firmware/code.py`) runs on **CircuitPython 7.3.1** on the MIDI Captain 10 STD. It cannot be bundled in this repository, for two reasons: the pedal needs a CircuitPython build made for its own hardware, and it also depends on screen and LED drivers that live on the pedal's own drive.

**Where to get things**
- CircuitPython releases (7.3.1): [github.com/adafruit/circuitpython/releases/tag/7.3.1](https://github.com/adafruit/circuitpython/releases/tag/7.3.1) and general downloads at [circuitpython.org/downloads](https://circuitpython.org/downloads). There's a [Welcome to CircuitPython guide](https://learn.adafruit.com/welcome-to-circuitpython) if you're new to it.
- The [PySwitch project](https://github.com/Tunetown/PySwitch) (and its [fork](https://github.com/danmigdev/PySwitch)) documents how its users set up a MIDI Captain, including holding **switch 1** while powering on to mount the USB drive. PySwitch is a separate, GPL-licensed project and CaptainsMate does not include its code.

**Before you change anything**
1. Power the pedal on while holding switch 1 and copy everything from its USB drive (MIDICAPTAIN) to a safe folder. This is your backup.
2. Check what's on it. If you see `code.py`, a `lib` folder and a CircuitPython `boot_out.txt`, your pedal already runs CircuitPython and only needs our three files copied over. If not, your stock firmware may be compiled rather than CircuitPython-based, and you'd need to flash CircuitPython first. That is an advanced, riskier step: be sure you have your backup and the original firmware file.
3. Then copy `code.py`, `boot.py` and `config.json` from `firmware/` to the drive and restart the pedal.

After the first install you rarely need the drive again, because the editor sends updates over USB.

## Tips

- Counters remember their value on the pedal. The pedal cannot read the device it controls, so if you turn a knob on the device the numbers can drift apart. A long press can reset a counter.
- SysEx data is hex bytes, like `F0 7E 7F 06 01 F7`. The pedal adds `F0`/`F7` if you leave them out.
- Web Serial needs Chrome or Edge and a secure page (a local file or https).

## Contributing

Issues and pull requests are welcome, especially device-specific example configs and verified pin or battery information.

## Credits

Pin map cross-checked against the PySwitch project. Built with help from Claude.
