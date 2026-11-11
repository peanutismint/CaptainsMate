# CaptainsMate boot v1: hides the USB drive unless dev_mode is on or switch 1 is held.
# boot.py: hide the USB drive (so the pedal can save its own config) unless
# dev_mode is on in config.json, or switch 1 is held while powering up.
import board
import digitalio
import storage
import json

dev = False
try:
    with open("/config.json") as f:
        dev = bool(json.load(f).get("dev_mode"))
except Exception:
    dev = True  # no/broken config: keep the drive visible so it can be fixed
try:
    sw = digitalio.DigitalInOut(board.GP1)
    sw.switch_to_input(pull=digitalio.Pull.UP)
    if not sw.value:
        dev = True
    sw.deinit()
except Exception:
    dev = True
if not dev:
    storage.disable_usb_drive()
