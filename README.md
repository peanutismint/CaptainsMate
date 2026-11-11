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

1. Install CircuitPython and the required libraries on the pedal, then copy `firmware/code.py`, `firmware/boot.py` and `firmware/config.json` to its drive. (Details for your setup: see "Installing" below.)
2. Open `editor/captainsmate.html` in Chrome or Edge.
3. Click **Connect pedal** and choose the pedal's serial port. The editor reads its current config.
4. Edit keys, then click **Send**. Try `examples/example-config.json`, a three-page pro-style setup: stage pedals (drive, delay, momentary reverb, FX loop, tap tempo with tuner on long press, presets), a looper and scenes page (named scene counters, amp channel sequence, bank counter), and an extras page (drum notes on channel 10, sustain, song select, SysEx master volume, MIDI panic), plus both expression inputs. Edit the CC numbers to match your own gear.

## Installing on the pedal

The firmware targets **CircuitPython 7.3.1** on the MIDI Captain 10 STD and uses the same board pin map as the PySwitch project. It needs these libraries on the pedal: `adafruit_midi`, `adafruit_display_text`, `adafruit_bitmap_font`, plus the screen and NeoPixel drivers used by the stock MIDI Captain CircuitPython builds. Keep the original firmware file so you can restore it.

## Tips

- Counters remember their value on the pedal. The pedal cannot read the device it controls, so if you turn a knob on the device the numbers can drift apart. A long press can reset a counter.
- SysEx data is hex bytes, like `F0 7E 7F 06 01 F7`. The pedal adds `F0`/`F7` if you leave them out.
- Web Serial needs Chrome or Edge and a secure page (a local file or https).

## Contributing

Issues and pull requests are welcome, especially device-specific example configs and verified pin or battery information.

## Credits

Pin map cross-checked against the PySwitch project. Built with help from Claude.
