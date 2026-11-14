# CaptainsMate boot v4: hides the USB drive unless dev_mode is on or switch 1 is held.
# boot.py: hide the USB drive (so the pedal can save its own config) unless
# dev_mode is on in config.json, or switch 1 is held while powering up.
# Everything printed here lands in boot_out.txt on the drive, so the reason for the choice can be checked.
import board
import digitalio
import storage
import json
import time

dev = False
why = []
try:
    with open("/config.json") as f:
        txt = f.read()
    if txt[:1] == "﻿":
        txt = txt[1:]
        why.append("config had a BOM (stripped)")
    d = bool(json.loads(txt).get("dev_mode"))
    txt = None
    why.append("config ok, dev_mode=%s" % d)
    if d:
        dev = True
except Exception as e:
    dev = True  # no/broken config: keep the drive visible so it can be fixed
    why.append("config read failed: %r" % e)
try:
    sw = digitalio.DigitalInOut(board.GP1)
    sw.switch_to_input(pull=digitalio.Pull.UP)
    # The key line needs a moment to rise after the pull-up is turned on (reading at once saw "held"),
    # so wait, then count it as held only if every one of 5 readings is low.
    time.sleep(0.15)
    reads = ""
    for _ in range(5):
        reads += "1" if sw.value else "0"
        time.sleep(0.02)
    sw.deinit()
    held = reads == "00000"
    why.append("switch 1 %s (reads %s)" % ("held" if held else "not held", reads))
    if held:
        dev = True
except Exception as e:
    dev = True
    why.append("switch 1 read failed: %r" % e)
if not dev:
    try:
        storage.disable_usb_drive()
        why.append("drive hidden")
        # Hiding the drive is not enough: code.py still sees the filesystem as read-only until it is
        # remounted writable here (only allowed in boot.py, and only while the computer cannot write).
        storage.remount("/", readonly=False)
        why.append("writable")
    except Exception as e:
        why.append("disable_usb_drive failed: %r" % e)
else:
    why.append("drive shown")
print("CaptainsMate boot: " + "; ".join(why))
