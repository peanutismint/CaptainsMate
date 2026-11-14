# Captain firmware v0.3 for MIDI Captain STD10 (CircuitPython 7.3.1)
# Reads /config.json (same format the Captain Editor writes). Pins taken from the PySwitch STD10 map.
# Staged log() lines print to the serial console so a stall shows exactly where it happened.
import time
T0 = time.monotonic()


LOGS = []


def log(m):
    t = "[%.2f] %s" % (time.monotonic() - T0, m)
    print(t)
    LOGS.append(t[:110])
    if len(LOGS) > 14:
        LOGS.pop(0)


log("start")
import gc
try:
    import io
except ImportError:
    io = None
import json
import sys
import os
import supervisor
import microcontroller
import board
import usb_midi
import displayio
from digitalio import DigitalInOut, Direction, Pull
from analogio import AnalogIn
from busio import UART, SPI
supervisor.disable_autoreload()
log("core imports ok")
from adafruit_midi import MIDI
from adafruit_midi.control_change import ControlChange
from adafruit_midi.program_change import ProgramChange
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
log("midi imports ok")
from adafruit_misc.neopixel import NeoPixel
from adafruit_misc.adafruit_st7789 import ST7789
log("neopixel + st7789 imports ok")
from adafruit_bitmap_font import bitmap_font
log("bitmap_font import ok")
from adafruit_display_text.label import Label
log("label import ok")

try:
    from fourwire import FourWire
except ImportError:
    from displayio import FourWire

# ---------------------------------------------------------------- config
COLORS = {
    "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 80, 255), "yellow": (255, 190, 0),
    "magenta": (255, 0, 200), "cyan": (0, 220, 255), "white": (255, 255, 255),
    "orange": (255, 90, 0), "purple": (150, 0, 255), "off": (0, 0, 0),
}
CFG_ERR = None
try:
    with open("/config.json") as _f:
        cfg = json.load(_f)
    if not cfg.get("pages"):
        raise ValueError("no pages")
except Exception as e:
    CFG_ERR = str(e)
    cfg = {"pages": [{"buttons": []}]}
    print("CONFIG ERROR:", e)
gc.collect()
log("config loaded, free=%d" % gc.mem_free())

MIDI_CH = int(cfg.get("midi_channel") or 1) - 1
SPI_HZ = int(float(cfg.get("spi_mhz") or 24) * 1000000)
HOLD = cfg.get("long_press_threshold_ms", 700) / 1000.0
PAGES = cfg["pages"]
page = int(cfg.get("active_page", 0))
if page >= len(PAGES):
    page = 0


def rgb(name):
    return COLORS.get(name, (255, 255, 255))


def dim(c, f):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))


# ---------------------------------------------------------------- hardware
KEY_PINS = [board.GP1, board.GP25, board.GP24, board.GP23, board.GP20,
            board.GP9, board.GP10, board.GP11, board.GP18, board.GP19]
keys = []
for p in KEY_PINS:
    d = DigitalInOut(p)
    d.direction = Direction.INPUT
    d.pull = Pull.UP
    keys.append(d)

neo = NeoPixel(board.GP7, 30, brightness=0.5, auto_write=False)
neo.fill((0, 0, 0))
neo.show()

exp_in = [AnalogIn(board.GP27), AnalogIn(board.GP28)]

outs = []
_u = None
try:
    outs.append(MIDI(midi_out=usb_midi.ports[1], out_channel=MIDI_CH))
except Exception as e:
    log("usb midi unavailable: " + str(e))
try:
    _u = UART(board.GP16, board.GP17, baudrate=31250, timeout=0.001)
    outs.append(MIDI(midi_out=_u, out_channel=MIDI_CH))
except Exception as e:
    log("din midi unavailable: " + str(e))
log("hardware ok, midi outs=%d" % len(outs))

displayio.release_displays()
spi = SPI(board.GP14, MOSI=board.GP15)
while not spi.try_lock():
    pass
spi.configure(baudrate=SPI_HZ)
spi.unlock()
bus = FourWire(spi, command=board.GP12, chip_select=board.GP13, reset=None)
tft = ST7789(bus, width=240, height=240, rowstart=80, rotation=180)
tft.auto_refresh = False
log("display ok")

# ---------------------------------------------------------------- ui
root = displayio.Group()


def rect(x, y, w, h, color):
    bm = displayio.Bitmap(w, h, 2)
    pal = displayio.Palette(2)
    pal[0] = color
    pal[1] = color
    root.append(displayio.TileGrid(bm, pixel_shader=pal, x=x, y=y))
    return pal


f_small = bitmap_font.load_font("/fonts/H15.pcf")
f_med = bitmap_font.load_font("/fonts/H20.pcf")
f_big = bitmap_font.load_font("/fonts/PTSans-NarrowBold-40.pcf")
log("fonts ok, free=%d" % gc.mem_free())


def lab(font, x, y, ax, text=" ", color=0xFFFFFF):
    l = Label(font, text=text, color=color)
    l.anchor_point = (ax, 0.5)
    l.anchored_position = (x, y)
    root.append(l)
    return l


rect(0, 0, 240, 40, 0x15181E)
pal_c = rect(0, 40, 240, 160, 0x000000)
rect(0, 200, 240, 40, 0x15181E)
hdr_l = lab(f_med, 8, 20, 0.0)
hdr_r = lab(f_med, 232, 20, 1.0)
hdr_m = lab(f_small, 120, 20, 0.5, color=0x8A909C)
title = lab(f_big, 120, 100, 0.5)
sub = lab(f_med, 120, 155, 0.5, color=0x9FD0FF)
cell_n = [lab(f_small, 30 + 60 * i, 210, 0.5, color=0x8A909C) for i in range(4)]
cell_v = [lab(f_small, 30 + 60 * i, 229, 0.5) for i in range(4)]
dirty = False


def st(l, t):
    global dirty
    if l.text != t:
        l.text = t
        dirty = True


tft.show(root)
tft.refresh()
log("ui ok, free=%d" % gc.mem_free())

# ---------------------------------------------------------------- state
pc_val = 0
counters = {}      # cc number -> value
vals = {}          # footer values
step_idx = {}      # (page, key) -> next short state
long_idx = {}
led_col = [(255, 255, 255)] * 10
led_lit = [False] * 10
cells = []
popup_until = 0


def btns():
    return PAGES[page].get("buttons", [])


def is_page_btn(b):
    return str(b.get("type", "")).startswith("page")


def counter_get(b):
    c = b.get("cc")
    if c not in counters:
        counters[c] = b.get("initial", b.get("cc_min", 0))
    return counters[c]


def build_cells():
    global cells
    cells = []
    seen = []
    for i, b in enumerate(btns()):
        if is_page_btn(b) or len(cells) >= 4:
            continue
        if b.get("cc") is not None:
            k = ("c", b["cc"])
        elif len(b.get("short") or []) > 1:
            k = ("s", i)
        else:
            continue
        if k in seen:
            continue
        seen.append(k)
        n = b.get("label", "")
        if n.endswith(" UP") or n.endswith(" DN"):
            n = n[:-3]
        if k[0] == "c":
            vals[k] = counter_get(b)
        cells.append((k, n[:7], b))


def refresh_cells():
    for i in range(4):
        if i < len(cells):
            k, n, cb = cells[i]
            st(cell_n[i], n or " ")
            nt = name_text(cb) if cb.get("cc") is not None else None
            st(cell_v[i], (nt if nt else str(vals.get(k, "-")))[:7])
        else:
            st(cell_n[i], " ")
            st(cell_v[i], " ")
    st(hdr_l, "PG %d/%d" % (page + 1, len(PAGES)))
    st(hdr_r, "PC %d" % pc_val)


def paint_leds(pressed=-1):
    for i in range(10):
        if i < len(btns()):
            c = led_col[i]
        else:
            c = (0, 0, 0)
        c = c if (i == pressed or led_lit[i]) else dim(c, cfg.get("led_idle", 12) / 100.0)
        for j in range(3):
            neo[i * 3 + j] = c
    neo.show()


def load_page():
    global led_col, led_lit
    led_col = []
    led_lit = [False] * 10
    for i in range(10):
        b = btns()[i] if i < len(btns()) else None
        led_col.append(rgb(b.get("color")) if b else (0, 0, 0))
    build_cells()
    refresh_cells()
    paint_leds()


def popup(t, s):
    global popup_until
    st(title, (t or " ")[:10])
    st(sub, (s or " ")[:18])
    popup_until = time.monotonic() + 1.4


def big_text(b, sh):
    try:
        src = sh.get("src")
        if src == "pc":
            v = pc_val
        elif src == "cc":
            v = counter_get(b)
        else:
            return None
        v = v - (sh.get("zero") or 0)
        if sh.get("signed") and v > 0:
            return "+%d" % v
        return str(v)
    except Exception:
        return None


def names_owner(b):
    if b.get("names"):
        return b
    c = b.get("cc")
    if c is None:
        return None
    for o in btns():
        if o.get("cc") == c and o.get("names"):
            return o
    return None


def name_text(b):
    try:
        ow = names_owner(b)
        if ow is None:
            return None
        nm = ow["names"]
        i = (counter_get(b) - b.get("cc_min", 0)) // (b.get("cc_step") or 1)
        if 0 <= i < len(nm) and nm[i]:
            return str(nm[i])
    except Exception:
        pass
    return None


def show_popup(b, label, r):
    sh = b.get("show")
    if sh and sh.get("src") in ("cc", "pc"):
        big = big_text(b, sh)
        if big is not None:
            popup(big, sh.get("caption") or label or b.get("label"))
            return
    nt = name_text(b)
    if nt is not None:
        ow = names_owner(b)
        cap = (sh.get("caption") if sh else None) or (ow.get("show") or {}).get("caption") or b.get("label")
        popup(nt, cap)
        return
    popup(label, r)


def popup_clear():
    st(title, " ")
    st(sub, " ")


cur_ch = MIDI_CH


def chan(c):
    # per-message channel override (1-16), else the global channel
    try:
        return int(c) - 1 if c else MIDI_CH
    except Exception:
        return MIDI_CH


mon = [False]


def mon_tx(raw):
    if mon[0]:
        try:
            print("@TX " + " ".join("%02X" % x for x in raw))
        except Exception:
            pass


def tx(msg):
    for o in outs:
        try:
            o.out_channel = cur_ch
            o.send(msg)
        except Exception as e:
            log("tx error: " + str(e))
    if mon[0]:
        try:
            r = msg.__bytes__()
            r = bytes([(r[0] & 0xF0) | cur_ch]) + bytes(r[1:]) if r[0] < 0xF0 else r
            mon_tx(r)
        except Exception:
            pass


# MIDI through: bytes arriving on DIN in go to DIN out and USB out, USB in goes to DIN out.
THRU = bool(cfg.get("midi_through"))


def thru_poll():
    try:
        if _u is not None and _u.in_waiting:
            d = _u.read(min(_u.in_waiting, 64))
            if d:
                _u.write(d)
                try:
                    usb_midi.ports[1].write(d)
                except Exception:
                    pass
        n = usb_midi.ports[0].read(64)
        if n and _u is not None:
            _u.write(n)
    except Exception as e:
        log("thru error: " + str(e))


# 2.4G wireless (blue/gold Pro models only, pairs with a MIDI Mate). Reverse-engineered from the stock
# FW5.16 image and NOT tested on hardware: the radio module shares the DIN UART and is configured by
# holding GP5 and GP4 low, sending an 18-byte packet at 9600 baud, then returning to 31250 baud.
# Only touched when "wireless" is true in the config, so black STD units are never affected.
wl_done = [None]
wl_pins = []  # kept open so the pins hold their level


def wireless_apply():
    if not cfg.get("wireless"):
        wl_done[0] = None
        return
    wid = max(1, min(100, int(cfg.get("wireless_id") or 8)))
    wdb = max(0, min(7, int(cfg.get("wireless_db") if cfg.get("wireless_db") is not None else 6)))
    if wl_done[0] == (wid, wdb) or _u is None:
        return
    try:
        if not wl_pins:
            for pn in (board.GP5, board.GP4):
                d = DigitalInOut(pn)
                d.direction = Direction.OUTPUT
                wl_pins.append(d)
        p5, p4 = wl_pins
        pk = bytearray([0xAA, 0x5A, wid, 0x44, 0x11, 0x33, 0x00, wdb, 0x00, 0x05, 0x00, 0x64, 0x00, 0x00, 0x00, 0x12, 0x00, 0])
        pk[17] = sum(pk[:17]) & 0xFF
        _u.baudrate = 9600
        time.sleep(0.01)
        p5.value = False
        p4.value = False
        time.sleep(0.03)
        _u.write(bytes(pk))
        time.sleep(0.1)
        p5.value = True
        p4.value = False
        _u.baudrate = 31250
        wl_done[0] = (wid, wdb)
        log("wireless set: id=%d power=%d" % (wid, wdb))
    except Exception as e:
        log("wireless error: " + str(e))
        try:
            _u.baudrate = 31250
        except Exception:
            pass


# ---------------------------------------------------------------- battery
# Charge enable = GP6 (found in the stock FW5.16 code: gpio_put(6, BATTERY_CHARGE)).
# Level sense pin is NOT confirmed: default GP29 (VSYS/3 on Pico-style boards), use @BATT probe.
chg_pin = None
try:
    chg_pin = DigitalInOut(board.GP6)
    chg_pin.direction = Direction.OUTPUT
    chg_pin.value = False
except Exception as e:
    log("charge pin: " + str(e))
batt_in = None
batt_err = ""
batt_v = None
batt_t = -10.0


def set_charge():
    if chg_pin is not None:
        chg_pin.value = bool(cfg.get("battery_charge", False))


def pin_of(n):
    try:
        return getattr(board, n)
    except AttributeError:
        return getattr(microcontroller.pin, "GPIO" + n[2:])


# ---------------------------------------------------------------- screen brightness
# Backlight is PWM on GP8 (found in the stock FW5.16 code). Only touched if the config asks for it.
bl = None
bl_cur = [-1.0]
bl_act = [0.0]
bl_clk = [0.0]


def bl_setup():
    global bl
    want = cfg.get("screen_brightness") is not None or cfg.get("screen_idle_brightness") is not None
    if bl is None and want:
        try:
            import pwmio
            bl = pwmio.PWMOut(pin_of(cfg.get("backlight_pin") or "GP8"), frequency=2000, duty_cycle=65535)
        except Exception as e:
            log("backlight pwm failed: " + str(e))
            return
    bl_cur[0] = -1.0
    bl_act[0] = time.monotonic()


def bl_poll(now):
    if bl is None:
        return
    full = cfg.get("screen_brightness")
    full = 100 if full is None else full
    idle = cfg.get("screen_idle_brightness")
    t = full
    if idle is not None and idle < full and (now - bl_act[0]) >= (cfg.get("screen_idle_seconds") or 10):
        t = idle
    cur = bl_cur[0]
    if cur < 0 or t > cur:
        cur = t
    elif t < cur:
        cur = max(t, cur - 100.0 * (now - bl_clk[0]))
    bl_clk[0] = now
    if cur != bl_cur[0]:
        bl_cur[0] = cur
        v = cur / 100.0
        bl.duty_cycle = int(65535 * v * v)


def batt_setup():
    global batt_in, batt_err, batt_v
    if batt_in is not None:
        try:
            batt_in.deinit()
        except Exception:
            pass
        batt_in = None
    batt_err = ""
    batt_v = None
    global batt_key
    batt_key = None
    if cfg.get("battery_display", True):
        try:
            batt_in = AnalogIn(pin_of(str(cfg.get("battery_pin", "GP29"))))
        except Exception as e:
            batt_err = str(e)[:40]
            log("battery pin: " + str(e))


NIMH = ((1.0, 0), (1.1, 5), (1.15, 15), (1.2, 30), (1.25, 60), (1.3, 90), (1.4, 100))
ALK = ((1.0, 0), (1.1, 5), (1.2, 15), (1.3, 30), (1.4, 50), (1.5, 75), (1.6, 100))


def batt_pct(v):
    c = v / 2.0
    t = ALK if cfg.get("battery_type") == "alkaline" else NIMH
    if c <= t[0][0]:
        return 0
    for i in range(1, len(t)):
        if c <= t[i][0]:
            x0, y0 = t[i - 1]
            x1, y1 = t[i]
            return int(y0 + (y1 - y0) * (c - x0) / (x1 - x0))
    return 100


bat_grp = displayio.Group()
root.append(bat_grp)
bat_seg = []


def brect(x, y, w, h, color):
    bm = displayio.Bitmap(w, h, 2)
    pal = displayio.Palette(2)
    pal[0] = color
    pal[1] = color
    bat_grp.append(displayio.TileGrid(bm, pixel_shader=pal, x=x, y=y))
    return pal


brect(103, 12, 34, 16, 0x8A909C)
brect(137, 17, 3, 6, 0x8A909C)
brect(105, 14, 30, 12, 0x15181E)
for _i in range(5):
    bat_seg.append(brect(106 + 6 * _i, 16, 5, 8, 0x15181E))
bat_grp.hidden = True
batt_pc = 0
batt_key = None


def batt_poll(now):
    global batt_t, batt_in, batt_err, batt_v, batt_pc, batt_key, dirty
    if not cfg.get("battery_display", True):
        st(hdr_m, " ")
        if not bat_grp.hidden:
            bat_grp.hidden = True
            dirty = True
        return
    if batt_in is None:
        st(hdr_m, "BAT ?")
        if not bat_grp.hidden:
            bat_grp.hidden = True
            dirty = True
        return
    if now - batt_t >= 2.0:
        batt_t = now
        try:
            raw = 0
            for _ in range(8):
                raw += batt_in.value
            ratio = cfg.get("battery_ratio")
            ratio = 3.0 if ratio is None else float(ratio)
            v = (raw // 8) * 3.3 / 65535 * ratio
            if batt_v is None or abs(v - batt_v) >= 0.08:
                batt_v = v
            batt_pc = batt_pct(batt_v)
        except Exception as e:
            batt_err = str(e)[:40]
            log("battery read failed, display off: " + str(e))
            batt_in = None
            return
    if batt_v is None:
        return
    chg = cfg.get("battery_charge", False)
    style = cfg.get("battery_style", "voltage")
    if style == "icon":
        st(hdr_m, " ")
        if bat_grp.hidden:
            bat_grp.hidden = False
            dirty = True
        lit = (batt_pc + 19) // 20
        if chg and int(now) % 2:
            lit = 5
        col = 0x34C759 if batt_pc >= 25 else 0xFF3B30
        key = (lit, col)
        if key != batt_key:
            batt_key = key
            for i in range(5):
                bat_seg[i][0] = col if i < lit else 0x15181E
                bat_seg[i][1] = bat_seg[i][0]
            dirty = True
    else:
        if not bat_grp.hidden:
            bat_grp.hidden = True
            dirty = True
        if style == "percent":
            t = "%d%%" % batt_pc
        else:
            t = "%.1fV" % batt_v
        st(hdr_m, t + ("+" if chg else ""))


def batt_probe():
    out = "@BATT"
    for n in ("GP26", "GP29"):
        try:
            a = AnalogIn(pin_of(n))
            r = 0
            for _ in range(8):
                r += a.value
            a.deinit()
            out += " %s=%.2fV" % (n, (r // 8) * 3.3 / 65535)
        except Exception as e:
            out += " %s=err" % n
    out += " GP6=%d" % (1 if (chg_pin is not None and chg_pin.value) else 0)
    print(out)


set_charge()
batt_setup()


# ---------------------------------------------------------------- encoder
enc = None
enc_last = 0
enc_vals = {}
try:
    import rotaryio

    try:
        enc = rotaryio.IncrementalEncoder(board.GP2, board.GP3, divisor=4)
    except TypeError:
        enc = rotaryio.IncrementalEncoder(board.GP2, board.GP3)
    enc_last = enc.position
except Exception as e:
    log("encoder: " + str(e))


def poll_enc(now):
    global enc_last, page, cur_ch
    if enc is None:
        return
    pos = enc.position
    d = pos - enc_last
    if d == 0:
        return
    enc_last = pos
    bl_act[0] = now
    e = PAGES[page].get("encoder") or {}
    if not e.get("enabled"):
        return
    if e.get("reverse"):
        d = -d
    if e.get("action") == "page":
        page = (page + (1 if d > 0 else -1)) % len(PAGES)
        load_page()
        popup("PAGE %d" % (page + 1), PAGES[page].get("name") or "of %d" % len(PAGES))
        return
    lo = e.get("min") or 0
    hi = e.get("max")
    hi = 127 if hi is None else hi
    v = enc_vals.get(page)
    if v is None:
        v = e.get("initial")
        v = lo if v is None else v
    v = max(lo, min(hi, v + d * (e.get("steps") or 1)))
    enc_vals[page] = v
    cc = e.get("cc", 11)
    cur_ch = chan(e.get("channel"))
    tx(ControlChange(cc, v))
    cur_ch = MIDI_CH
    popup(e.get("label") or "ENC", "CC %d = %d" % (cc, v))


# ---------------------------------------------------------------- messages
def run_msg(m, b, direction):
    global cur_ch
    cur_ch = chan(m.get("channel"))
    try:
        return run_msg2(m, b, direction)
    finally:
        cur_ch = MIDI_CH


fire_depth = [0]


def fire_keys(m):
    # Emulates tapping (or long-pressing) other keys, so one key can drive several.
    if fire_depth[0] >= 3:
        log("press: too many nested presses, stopped")
        return "LOOP"
    fire_depth[0] += 1
    out = None
    try:
        pg = int(m.get("page") or (page + 1)) - 1
        if pg < 0 or pg >= len(PAGES):
            return None
        which = "long" if m.get("press") == "long" else "short"
        store = long_idx if which == "long" else step_idx
        bl = PAGES[pg].get("buttons") or []
        for tok in str(m.get("keys", "")).replace(" ", "").split(","):
            if not tok:
                continue
            i = int(tok) - 1
            if i < 0 or i >= len(bl):
                continue
            b = bl[i]
            lst = b.get(which) or []
            if is_page_btn(b) or not lst:
                continue
            s = lst[store.get((pg, i), 0) % len(lst)]
            r1 = run_list(s.get("down"), b, "down")
            r2 = run_list(s.get("up"), b, "up")
            if which == "short" and len(lst) > 1 and pg == page:
                vals[("s", i)] = s.get("label") or str(store.get((pg, i), 0))
            if s.get("color") and pg == page:
                led_lit[i] = s.get("dim") is False or bool(s.get("lit"))
                led_col[i] = rgb(s["color"] if (led_lit[i] or len(lst) > 1) else b.get("color"))
                radio_off(i, b)
            store[(pg, i)] = store.get((pg, i), 0) + 1
            out = r2 or r1 or out
    finally:
        fire_depth[0] -= 1
    return out or "PRESS " + str(m.get("keys", ""))


def radio_off(i, b):
    # Keys sharing the same "radio" group name act like radio buttons: lighting one dims the rest.
    g = b.get("radio")
    if g:
        bl = btns()
        for j in range(len(bl)):
            if j != i and bl[j].get("radio") == g:
                led_lit[j] = False
                if len(bl[j].get("short") or []) < 2:
                    led_col[j] = rgb(bl[j].get("color"))


def run_msg2(m, b, direction):
    global pc_val
    t = m.get("type")
    if t == "cc":
        v = m.get("value", 0)
        tx(ControlChange(m["cc"], v))
        if m["cc"] in counters or b.get("cc") == m["cc"]:
            counters[m["cc"]] = v
            vals[("c", m["cc"])] = v
        return "CC %d = %d" % (m["cc"], v)
    if t == "pc":
        pc_val = m.get("program", 0)
        tx(ProgramChange(pc_val))
        return "PC %d" % pc_val
    if t == "pc_inc" or t == "pc_dec":
        pc_val = (pc_val + (1 if t == "pc_inc" else -1)) % 128
        tx(ProgramChange(pc_val))
        return "PC %d" % pc_val
    if t == "cc_inc" or t == "cc_dec":
        lo = b.get("cc_min", 0)
        hi = b.get("cc_max", 127)
        v = counter_get(b) + (1 if t == "cc_inc" else -1) * b.get("cc_step", 1)
        if v > hi:
            v = lo if b.get("cc_wrap") else hi
        if v < lo:
            v = hi if b.get("cc_wrap") else lo
        counters[b["cc"]] = v
        vals[("c", b["cc"])] = v
        tx(ControlChange(b["cc"], v))
        return "CC %d = %d" % (b["cc"], v)
    if t == "sysex":
        if not m.get("data"):
            return None
        d = m["data"].replace(" ", "")
        b2 = bytes(int(d[i:i + 2], 16) for i in range(0, len(d) - 1, 2))
        if not b2 or b2[0] != 0xF0:
            b2 = b"\xf0" + b2
        if b2[-1] != 0xF7:
            b2 = b2 + b"\xf7"
        mon_tx(b2)
        for o in outs:
            try:
                p = getattr(o, "_outport", None) or o._midi_out
                try:
                    p.write(b2, len(b2))
                except TypeError:
                    p.write(b2)
            except Exception as e:
                log("sysex error: " + str(e))
        return "SYSEX %d" % len(b2)
    if t == "press":
        return fire_keys(m)
    if t == "note":
        if direction == "down":
            tx(NoteOn(m.get("note", 60), m.get("velocity", 127)))
        else:
            tx(NoteOff(m.get("note", 60), 0))
        return "NOTE %d" % m.get("note", 60)
    return None


def run_list(lst, b, direction):
    out = None
    for m in lst or []:
        try:
            r = run_msg(m, b, direction)
            if r:
                out = r
        except Exception as e:
            log("msg error: " + str(e))
    return out


class KeyState:
    def __init__(self):
        self.down = False
        self.raw = False
        self.t_edge = 0
        self.t_down = 0
        self.state = None   # state dict chosen at press
        self.is_long = False
        self.fired_down = False


ks = [KeyState() for _ in range(10)]


def pick(b, name, i, store):
    lst = b.get(name) or []
    if not lst:
        return None
    n = store.get((page, i), 0) % len(lst)
    return lst[n], n, len(lst)


def on_down(i, now):
    b = btns()[i] if i < len(btns()) else None
    k = ks[i]
    if b is None:
        return
    global page
    if is_page_btn(b):
        page = (page + (1 if b["type"] == "page_inc" else -1)) % len(PAGES)
        load_page()
        popup(b.get("label"), "PAGE %d" % (page + 1))
        return
    paint_leds(i)
    k.fired_down = False
    k.is_long = False
    k.state = None
    p = pick(b, "short", i, step_idx)
    if p:
        k.state = p[0]
        if not (b.get("long") or []):
            r = run_list(p[0].get("down"), b, "down")
            k.fired_down = True
            if r:
                show_popup(b, p[0].get("label") or b.get("label"), r)


def on_up(i, now):
    b = btns()[i] if i < len(btns()) else None
    k = ks[i]
    if b is None or is_page_btn(b):
        return
    if k.is_long:
        s = k.state
        r = run_list(s.get("up"), b, "up")
        if r:
            show_popup(b, s.get("label") or b.get("label"), r)
        long_idx[(page, i)] = long_idx.get((page, i), 0) + 1
    elif k.state is not None:
        s = k.state
        r1 = None
        if not k.fired_down:
            r1 = run_list(s.get("down"), b, "down")
        r2 = run_list(s.get("up"), b, "up")
        r = r2 or r1
        if len(b.get("short") or []) > 1:
            vals[("s", i)] = s.get("label") or str(step_idx.get((page, i), 0))
        if s.get("color"):
            led_lit[i] = s.get("dim") is False or bool(s.get("lit"))
            led_col[i] = rgb(s["color"] if (led_lit[i] or len(b.get("short") or []) > 1) else b.get("color"))
            radio_off(i, b)
        step_idx[(page, i)] = step_idx.get((page, i), 0) + 1
        if r:
            show_popup(b, s.get("label") or b.get("label"), r)
    refresh_cells()
    paint_leds()


def check_long(i, now):
    k = ks[i]
    if k.down and not k.is_long and (now - k.t_down) >= HOLD:
        b = btns()[i] if i < len(btns()) else None
        if b is None or is_page_btn(b):
            return
        p = pick(b, "long", i, long_idx)
        if p:
            k.is_long = True
            k.state = p[0]
            r = run_list(p[0].get("down"), b, "down")
            refresh_cells()
            if r:
                show_popup(b, p[0].get("label") or b.get("label"), r)


# ---------------------------------------------------------------- expression
exp_last = [None, None]
exp_t = 0


def poll_exp(now):
    global exp_t
    if now - exp_t < 0.02:
        return
    exp_t = now
    ex = PAGES[page].get("expression") or {}
    for n, name in ((0, "exp1"), (1, "exp2")):
        e = ex.get(name)
        if not e or not e.get("enabled"):
            continue
        raw = 0
        for _ in range(4):
            raw += exp_in[n].value
        v = (raw // 4) * 127 // 65535
        if e.get("polarity") == "reversed":
            v = 127 - v
        mn = e.get("min", 0)
        mx = e.get("max", 127)
        v = mn + (v * (mx - mn)) // 127
        if exp_last[n] is None or abs(v - exp_last[n]) >= e.get("threshold", 2):
            exp_last[n] = v
            global cur_ch
            cur_ch = chan(e.get("channel"))
            tx(ControlChange(e.get("cc", 12 + n), v))
            cur_ch = MIDI_CH
            popup(e.get("label", name.upper()), "CC %d = %d" % (e.get("cc", 12 + n), v))


# ---------------------------------------------------------------- live config over USB serial
# The editor talks to this on the same USB serial port as the console. Lines start with "@".
HAS_SER = hasattr(supervisor.runtime, "serial_bytes_available")
rx_line = ""
rx_buf = None
rx_pos = 0
rx_boot = False


def boot_kind():
    try:
        with open("/boot.py") as f:
            return "ours" if "CaptainsMate boot" in f.readline() else "other"
    except Exception:
        return "none"


def save_cfg(text, final="/config.json", tmp="/config.tmp"):
    try:
        with open(tmp, "wb") as f:
            f.write(text)
        os.rename(tmp, final)
        return True
    except Exception as e:
        log("save failed: " + str(e))
        return False


def apply_cfg(new, text):
    global cfg, PAGES, HOLD, MIDI_CH, page, CFG_ERR, batt_t, THRU
    if not new.get("pages"):
        raise ValueError("no pages")
    cfg = new
    THRU = bool(new.get("midi_through"))
    PAGES = new["pages"]
    HOLD = new.get("long_press_threshold_ms", 700) / 1000.0
    MIDI_CH = int(new.get("midi_channel") or 1) - 1
    global cur_ch
    cur_ch = MIDI_CH
    CFG_ERR = None
    counters.clear()
    vals.clear()
    step_idx.clear()
    long_idx.clear()
    exp_last[0] = None
    exp_last[1] = None
    enc_vals.clear()
    page = int(new.get("active_page", 0))
    if page >= len(PAGES):
        page = 0
    set_charge()
    batt_setup()
    bl_setup()
    wireless_apply()
    batt_t = -10.0
    load_page()
    popup("CONFIG", "applied")
    gc.collect()
    return save_cfg(text)


def handle_line(l):
    global rx_buf, rx_pos, rx_boot
    if l == "@PING":
        print("@PONG 0.3 free=%d" % gc.mem_free())
    elif l.startswith("@MON"):
        mon[0] = l.strip().endswith("1")
        print("@OK")
    elif l.startswith("@TX "):
        try:
            r = run_msg(json.loads(l[4:]), {}, "up")
            print("@TXOK " + str(r))
        except Exception as e:
            print("@ERR tx: " + str(e))
    elif l.startswith("@BEGIN"):
        rx_buf = None
        gc.collect()
        try:
            rx_boot = l.startswith("@BEGINB")
            rx_buf = bytearray(int(l[(7 if rx_boot else 6):].strip()))
            rx_pos = 0
            print("@OK")
        except Exception as e:
            rx_buf = None
            print("@ERR begin: " + str(e) + " free=" + str(gc.mem_free()))
    elif l.startswith("@D") and rx_buf is not None:
        c = l[2:]
        if rx_boot:
            c = c.replace("`", "\n")
        c = c.encode()
        n = len(c)
        if rx_pos + n > len(rx_buf):
            rx_buf = None
            print("@ERR overflow")
        else:
            rx_buf[rx_pos:rx_pos + n] = c
            rx_pos += n
            print("@OK")
    elif l == "@END" and rx_buf is not None:
        buf = rx_buf
        rx_buf = None
        try:
            if rx_pos != len(buf):
                raise ValueError("short %d/%d" % (rx_pos, len(buf)))
            gc.collect()
            if rx_boot:
                ok = save_cfg(buf, "/boot.py", "/boot.tmp")
                print("@APPLIED boot saved=%d" % (1 if ok else 0))
                buf = None
                return
            if io is not None:
                new = json.load(io.BytesIO(buf))
            else:
                new = json.loads(buf.decode())
            saved = apply_cfg(new, buf)
            print("@APPLIED saved=%d free=%d" % (1 if saved else 0, gc.mem_free()))
        except Exception as e:
            print("@ERR " + str(e) + " free=" + str(gc.mem_free()))
        buf = None
        gc.collect()
    elif l == "@LOG":
        for t in LOGS:
            print("@LOG " + t)
    elif l == "@INFO":
        print("@INFO v0.3 free=%d page=%d/%d batt_in=%s batt_err=%s chg=%s boot=%s" % (gc.mem_free(), page + 1, len(PAGES), batt_in is not None, batt_err, bool(cfg.get("battery_charge", False)), boot_kind()))
    elif l == "@BATT":
        batt_probe()
    elif l == "@REBOOT":
        print("@OK")
        time.sleep(0.2)
        microcontroller.reset()
    elif l == "@GET":
        gc.collect()
        s = json.dumps(cfg)
        print("@CBEGIN")
        for i in range(0, len(s), 100):
            print("@C" + s[i:i + 100])
        print("@CEND")


def serial_poll():
    global rx_line
    n = 0
    while supervisor.runtime.serial_bytes_available and n < 200:
        c = sys.stdin.read(1)
        n += 1
        if c == "\n" or c == "\r":
            if rx_line:
                line = rx_line
                rx_line = ""
                handle_line(line)
        elif len(rx_line) < 300:
            rx_line += c


# ---------------------------------------------------------------- run
load_page()
if CFG_ERR:
    popup("CONFIG ERR", CFG_ERR)
    popup_until = time.monotonic() + 60
else:
    popup("READY", "page %d/%d" % (page + 1, len(PAGES)))
log("running v0.3, serial link=%s, free=%d" % (HAS_SER, gc.mem_free()))

bl_setup()
wireless_apply()
gc_t = [0]
while True:
    try:
        now = time.monotonic()
        if now - gc_t[0] > 4:
            gc_t[0] = now
            gc.collect()
        for i in range(10):
            raw = not keys[i].value
            k = ks[i]
            if raw != k.raw:
                k.raw = raw
                k.t_edge = now
            elif raw != k.down and (now - k.t_edge) > 0.02:
                k.down = raw
                bl_act[0] = now
                if raw:
                    k.t_down = now
                    on_down(i, now)
                else:
                    on_up(i, now)
            check_long(i, now)
        if HAS_SER:
            serial_poll()
        if THRU:
            thru_poll()
        try:
            poll_exp(now)
        except Exception as e:
            log("exp error: " + str(e))
        try:
            poll_enc(now)
        except Exception as e:
            log("enc error: " + str(e))
        try:
            bl_poll(now)
        except Exception as e:
            log("bl error: " + str(e))
        try:
            batt_poll(now)
        except Exception as e:
            log("batt error: " + str(e))
        if popup_until and now > popup_until:
            popup_until = 0
            popup_clear()
            refresh_cells()
        if dirty:
            dirty = False
            tft.refresh()
    except Exception as e:
        log("loop error: " + str(e))
        time.sleep(0.2)
