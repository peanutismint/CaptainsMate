#!/usr/bin/env python3
"""Embed the files in examples/ into editor/captainsmate.html so the editor's
"Examples" button works from a single file (no server, no network).
Run from the repo root after editing any example:  python3 tools/embed_examples.py
"""
import json, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
EXAMPLES = [
    ("example-config.json", "Generic starter: 3 pages",
     "Guitar-effects stage page, a radio patch bank with a one-tap Home macro, and a looper page. Shows toggles, momentary keys, counters, sequences, long presses, notes and SysEx."),
    ("AT200-counters.json", "Peavey AT-200",
     "Preset, capo, model, doubler and tuning counters with names on the screen, plus an 8-key radio preset bank."),
    ("waza-air-config.json", "Boss Waza-Air headphones (SysEx)",
     "Patches as a radio bank, effects toggles, amp and EQ controls, and one-tap EQ presets. Needs a Bluetooth MIDI link to the headphones."),
]
items = [{"title": t, "desc": d, "cfg": json.loads((root / "examples" / f).read_text())} for f, t, d in EXAMPLES]
blob = "/*EXAMPLES_BEGIN*/const EXAMPLES=" + json.dumps(items, separators=(",", ":")) + ";/*EXAMPLES_END*/"
ed = root / "editor" / "captainsmate.html"
s = ed.read_text()
a, b = s.index("/*EXAMPLES_BEGIN*/"), s.index("/*EXAMPLES_END*/") + len("/*EXAMPLES_END*/")
ed.write_text(s[:a] + blob + s[b:])
print("embedded", len(items), "examples,", len(blob) // 1024, "KB")
