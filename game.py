#!/usr/bin/env python3
"""GIO'S CIRCUIT GAME v18.0 - ESCAPE THE BLACKOUT

NEW IN 18.0: Canica, Gummy, Sofia and Lafufu live in Jaslyne's room, wizard robes + buddy overalls outfits,
yellow goggle-buddy decorations and pet plushies. Smoother rendering, volume sliders.

NEW IN 17.0: music + sound effects through a MAX98357A I2S amp, Animal Crossing-style character voices,
Wizard and Dogs furniture. NOTE: UP button moved to GPIO17 (pin 11), DOWN to GPIO27 (pin 13) - the amp uses pins 12, 35 and 40.

NEW IN z a n16.0: Design Mode - picture catalog, live green/red preview, place / move / erase / undo tools,
hold-to-glide cursor, hold CENTER to paint floors and walls, buy-as-you-place.

NEW IN 15.0: slide pot wired like the real kit (pin 1 power, pin 2 output, pin 3 ground), simpler circuits,
decorating can remove room objects, walls + floors, 200+ furniture pieces incl. kitchen/bedroom/bath/living.

NEW IN 14.0: every circuit checked against real 5V physics, Gio's tips say exactly where each leg goes
(series explained properly), full explanations only the first time, workbench follows real-world rules.

NEW IN 13.0: the game opens BEFORE the blackout - Silas and Dr. Vex give Jaslyne and Gio a hands-on tour of
the lit-up lab (teaching the basics), then the storm hits and the main game begins. Skippable.

NEW IN 12.0: Gio talks her through every step of every circuit (which leg is +, red/black wires, motor direction...),
and the part drawings show legs, +/- marks, ON labels and wire colours.

NEW IN 11.0: every circuit rebuilt from the real kit (LEDs, resistors, buttons, DIP switches, slide pots, fans,
vibe motors, DC motors, lasers), simpler step-by-step boards, cleaner store section names.

NEW IN 10.0: 137 furniture pieces in 19 themes (holidays + aesthetics), store sections, decorate EVERY room after the story.

NEW IN 9.0: Free Build workbench with a real circuit checker + endless jobs (Workshop), her own room to
decorate with furniture from Tess, daily gifts + streaks, weekly challenges, holiday events, labelled breadboards.

Pokemon-style tile RPG with an Escapists-style locked-facility story.
Target: ILI9341 320x240 on a Raspberry Pi, 5 buttons.

STORY: on a Saturday-night tour of VOLTA LABS, lightning hits the generator. The surge fries every circuit and
scrambles M.A.X., the building's AI, who panics and locks every door. Jaslyne and Gio repower the building zone
by zone; each zone wakes up more of MAX (his sight, then his memory) until he can lift the lockdown from the roof.
  * Opening + ending cutscenes, story scenes when entering and finishing each zone
  * Study Room: illustrated lesson books (7 chapters), flashcards on what you've read, Focus Lamp study timer

  * 7 zones, 21 quests built from the real kit: LEDs, resistors, buttons, DIP switches, slide pots,
    fans, vibe motors, DC motors and lasers (series, parallel, motors, lasers, generators...)
  * Pop quiz after every quest, trophies with pop-up alerts, 8 hidden notes from Gio to collect
  * Study Room (left door of the Workshop): flashcards + a Focus Lamp that pays Bolts for REAL studying
  * Puzzle Lab (upstairs in the Study Room): 40 pipe puzzles + 40 light-grid puzzles, 3 stars each, endless mode
  * Tile maps, smooth grid walking, wandering NPCs, Pokemon dialogue boxes
  * Lights come back on room by room as you fix circuits (flashlight in the dark!)
  * Escapists-style stashes: search desks, crates and shelves for hidden Bolts (and a secret note)
  * Locked zone doors, Tess's General Store (spend Bolts), wardrobe, tool upgrades
  * Pause menu (CENTER with nothing nearby): quests, bag, outfit, save
  * Ending cutscene when the facility is fully powered

CONTROLS  (same 5 buttons everywhere)
  UP/DOWN/LEFT/RIGHT  walk (hold to jog) / move cursor
  CENTER  talk, search, use terminal - works on anything right next to you, no need to aim
  Menus: LEFT = back.   Quest: LEFT/RIGHT = step back/forward, DOWN = zoom, UP = exit
"""
import datetime
import json
import math
import os
import random
import shutil
import signal
import subprocess
import sys
import threading
import time

SIM = os.environ.get("GIO_SIM") == "1"

# ---------------- DISPLAY SETTINGS (2.8" TPM408-2.8, ILI9341, 240x320 SPI) ----------------
# If the picture looks wrong, change ONE of these and restart the game:
FLIP_180 = False       # picture upside down?          -> True
MIRROR_LEFT_RIGHT = True   # picture mirrored left-to-right? -> True (needed for the TPM408-2.8)
SWAP_RED_BLUE = True   # red things look blue?         -> True (needed for the TPM408-2.8)
INVERT_COLORS = False  # colours look like a negative? -> True
DC_PIN, RST_PIN = 25, 24          # GPIO numbers for the screen's DC and RESET pins
SPI_BUS, SPI_DEVICE = 0, 1        # CS wired to CE1 (pin 26). Wired to CE0 (pin 24)? -> SPI_DEVICE = 0
SPI_SPEED = 32000000              # lower to 16000000 if the picture is glitchy/speckled
MADCTL = 0xE8 if FLIP_180 else 0x28   # landscape 320x240 (mirror + red/blue swap are done in push_image)

_early = None   # (gpio handle, spi) from the boot blackout, reused by hw_init
if not SIM:
    import lgpio
    import spidev

    def _boot_blackout():
        """Turn the screen black right away, before the slow numpy/PIL imports.
        The panel shows white until it gets data, so this cuts the white flash at boot to a moment."""
        hh = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(hh, DC_PIN, 0)
        lgpio.gpio_claim_output(hh, RST_PIN, 1)
        sp = spidev.SpiDev()
        sp.open(SPI_BUS, SPI_DEVICE)
        sp.max_speed_hz = SPI_SPEED
        sp.mode = 0

        def cmd(c, data=None):
            lgpio.gpio_write(hh, DC_PIN, 0)
            sp.writebytes([c])
            if data is not None:
                lgpio.gpio_write(hh, DC_PIN, 1)
                sp.writebytes2(data)
        lgpio.gpio_write(hh, RST_PIN, 0); time.sleep(0.02)
        lgpio.gpio_write(hh, RST_PIN, 1); time.sleep(0.12)
        cmd(0x01); time.sleep(0.12)                    # software reset
        cmd(0x11); time.sleep(0.12)                    # wake up
        cmd(0x3A, [0x55]); cmd(0x36, [MADCTL])         # 16-bit colour, landscape
        cmd(0x21 if INVERT_COLORS else 0x20)           # colour inversion on/off
        cmd(0x2A, [0, 0, 1, 0x3F]); cmd(0x2B, [0, 0, 0, 0xEF])
        cmd(0x2C, bytes(320 * 240 * 2))                # fill the screen with black...
        cmd(0x29)                                      # ...and only then switch the picture on
        return hh, sp
    try:
        _early = _boot_blackout()
    except Exception as e:
        print("Boot blackout skipped:", e)

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 320, 240
TS = 16                      # tile size
MW, MH = W // TS, H // TS    # 20 x 15 tiles per room

FPS = 20
POLL_DT = 0.004              # buttons are read every 4 ms between frames so short taps still count

# Button GPIO numbers (BCM). GPIO 18, 19, 20 and 21 (pins 12, 35, 38, 40) belong to the sound amp.
# UP = pin 11, DOWN = pin 13, LEFT = pin 36, RIGHT = pin 32, CENTER = pin 33. Change a number here to move a button.
DIGITAL_BUTTONS = {"up": 17, "down": 27, "left": 16, "right": 12, "click": 13}
DEBOUNCE = 0.03
# TESTING MODE: while True, nothing is ever saved or loaded - every launch is a brand-new game.
# Change to False when you're done testing so her progress saves again.
TESTING_MODE = False
# UNLOCK_ALL: start with EVERYTHING done and unlocked (all circuits, story finished, every outfit, tool and
# furniture piece, lots of Bolts). Handy for testing decorating etc. Set to False for the real game.
UNLOCK_ALL = False
JOBS_OPEN_EARLY = False  # True = job board works before the story is finished (for testing)
CIRCUIT_DIR = "/home/jasyne/circuits"
PROGRESS_FILE = os.path.join(CIRCUIT_DIR, "progress.json")

# ---------------- colors ----------------
BG = (8, 12, 18)
CYAN = (60, 200, 235)
CYAN_D = (20, 120, 150)
DOT = (30, 80, 100)
INK = (10, 40, 60)
WHITE = (255, 255, 255)
GREEN = (60, 220, 120)
YELLOW = (250, 220, 40)
RED = (240, 70, 70)
ORANGE = (245, 158, 11)
PURPLE = (180, 70, 240)
PANEL = (20, 60, 80)
CREAM = (248, 246, 232)
NAVY = (36, 40, 74)
TXT = (30, 30, 50)
WIRE = {"red": (220, 40, 40), "black": (25, 25, 30), "yellow": (240, 200, 30), "blue": (40, 80, 220)}
WIRE_GOLD = {"red": (240, 180, 40), "black": (130, 90, 20), "yellow": (255, 230, 90), "blue": (200, 160, 40)}
LED_COL = {"red": (255, 70, 70), "green": (70, 220, 90), "yellow": (250, 220, 50),
           "blue": (70, 110, 255), "white": (255, 255, 255), "orange": (255, 150, 40)}


def font(size, bold=False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else "")
    try:
        return ImageFont.truetype(p, size)
    except OSError:
        return ImageFont.load_default()


F_S, F_M, F_B, F_T, F_L = font(8), font(9), font(9, True), font(13, True), font(22, True)

# Speed-up: text is the slowest thing to draw on the Pi, and the same words get drawn every frame.
# Render each (text, font, colour) once, keep it, and just stamp it on afterwards.
_orig_text = ImageDraw.ImageDraw.text
_text_cache = {}


_orig_draw = ImageDraw.Draw


def _draw_with_image(im, mode=None):
    d = _orig_draw(im, mode)
    d._gio_img = im   # older Pillow (like on the Pi) doesn't remember the image itself
    return d


ImageDraw.Draw = _draw_with_image


def _cached_text(self, xy, text, fill=None, font=None, *args, **kwargs):
    img = getattr(self, "_image", None) or getattr(self, "_gio_img", None)
    if args or kwargs or font is None or img is None or img.mode != "RGB" or not isinstance(text, str) \
            or "\n" in text or not isinstance(fill, tuple):
        return _orig_text(self, xy, text, fill, font, *args, **kwargs)
    key = (text, id(font), fill)
    spr = _text_cache.get(key)
    if spr is None:
        if len(_text_cache) > 4000:
            _text_cache.clear()
        box = font.getbbox(text)
        if box[2] <= 0 or box[3] <= 0:
            return None
        mask = Image.new("L", (box[2] + 1, box[3] + 1), 0)
        _orig_text(ImageDraw.Draw(mask), (0, 0), text, 255, font)
        spr = _text_cache[key] = (Image.new("RGB", mask.size, fill), mask)
    img.paste(spr[0], (int(round(xy[0])), int(round(xy[1]))), spr[1])
    return None


ImageDraw.ImageDraw.text = _cached_text

# ---------------- hardware ----------------
h = None
spi = None
dig = {}
_raw, _stable, _since = {}, {}, {}
SIM_KEYS = set()   # in SIM mode, a test/keyboard hook can put button names here


def hw_init():
    global h, spi
    if SIM:
        return
    if _early:
        h, spi = _early   # screen is already set up (and black) from the boot blackout
    else:
        h = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(h, DC_PIN, 0)
        lgpio.gpio_claim_output(h, RST_PIN, 1)
        spi = spidev.SpiDev()
        spi.open(SPI_BUS, SPI_DEVICE)
        spi.max_speed_hz = SPI_SPEED
        spi.mode = 0
    for name, pin in DIGITAL_BUTTONS.items():
        try:
            lgpio.gpio_claim_input(h, pin, lgpio.SET_PULL_UP)
            dig[name] = pin
            _raw[name] = _stable[name] = 1
            _since[name] = 0.0
        except lgpio.error as e:
            print("Button %s GPIO%d unavailable: %s" % (name, pin, e))


def poll():
    out, t = [], time.time()
    for name, pin in dig.items():
        v = lgpio.gpio_read(h, pin)
        if v != _raw[name]:
            _raw[name] = v
            _since[name] = t
        elif v != _stable[name] and t - _since[name] >= DEBOUNCE:
            _stable[name] = v
            if v == 0:
                out.append(name)
    return out


def held(name):
    if SIM:
        return name in SIM_KEYS or web_held(name)
    return _stable.get(name, 1) == 0 or web_held(name)


# ---------------- play on a phone or laptop ----------------
# The Pi serves a web page that runs THIS game file right inside the phone's browser (Python in the browser),
# so she plays on her phone on its own. The page loads her save from the Pi when it opens and sends it back
# every time the game saves, so Bolts and progress are the same everywhere.  WEB_PORT = 0 turns it off.
#   /         the game, running on the phone
#   /remote   (old) remote control for the game running on the Pi's own screen
WEB_PORT = 8080
_web = dict(frame=b"", want=0.0, presses=[], held={}, lock=threading.Lock())
PLAY_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#2a1530">
<title>Jaslyne's Circuit Game</title>
<style>
  :root { --bg:#2a1530; --panel:#3b1f45; --pink:#ff7eb6; --pink2:#ffb3d4; --text:#fff3f8; --dim:#c9a7c0; }
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  html, body { margin:0; height:100%; background:var(--bg); color:var(--text);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif; overscroll-behavior:none; }
  body { display:flex; flex-direction:column; align-items:center; padding:12px 16px 20px;
    user-select:none; -webkit-user-select:none; touch-action:none; }
  h1 { font-size:18px; margin:4px 0 10px; letter-spacing:.5px; color:var(--pink2); }
  .wrap { width:100%; max-width:960px; display:flex; flex-direction:column; align-items:center; gap:16px; }
  .screen { width:100%; max-width:640px; aspect-ratio:4/3; background:#000; border-radius:14px;
    border:4px solid var(--pink); box-shadow:0 8px 24px rgba(0,0,0,.4); overflow:hidden; position:relative; }
  canvas { width:100%; height:100%; display:block; image-rendering:pixelated; image-rendering:crisp-edges; }
  .status { position:absolute; inset:0; display:flex; flex-direction:column; gap:10px; align-items:center;
    justify-content:center; text-align:center; padding:20px; font-size:15px; color:var(--dim); background:#140a18; }
  .status[hidden] { display:none; }
  .bar { width:70%; height:8px; border-radius:4px; background:#3b1f45; overflow:hidden; }
  .bar i { display:block; height:100%; width:0; background:var(--pink); transition:width .3s; }
  .sync { font-size:12px; color:var(--dim); min-height:16px; text-align:center; }
  .pad { width:100%; max-width:420px; display:flex; justify-content:space-between; align-items:center; gap:16px; }
  .dpad { display:grid; grid-template-columns:repeat(3,64px); grid-template-rows:repeat(3,64px); gap:6px; }
  button { font:inherit; color:var(--text); background:var(--panel); border:3px solid var(--pink);
    border-radius:14px; font-size:24px; touch-action:none; cursor:pointer; }
  button.on { background:var(--pink); color:var(--bg); }
  .up { grid-column:2; grid-row:1; } .left { grid-column:1; grid-row:2; }
  .right { grid-column:3; grid-row:2; } .down { grid-column:2; grid-row:3; }
  .center { width:104px; height:104px; border-radius:50%; font-size:16px; font-weight:700; letter-spacing:1px; }
  @media (orientation:landscape) and (max-height:520px) {
    body { padding:8px 16px; } h1, .sync { display:none; }
    .wrap { flex-direction:row; justify-content:center; align-items:center; height:100%; }
    .screen { height:calc(100vh - 24px); width:auto; max-width:none; }
    .pad { flex-direction:column; width:auto; }
  }
</style></head>
<body>
<h1>Jaslyne's Circuit Game</h1>
<div class="wrap">
  <div class="screen"><canvas id="c" width="320" height="240"></canvas>
    <div class="status" id="status"><div id="msg">Loading the game...</div><div class="bar"><i id="bar"></i></div></div></div>
  <div class="sync" id="sync"></div>
  <div class="pad">
    <div class="dpad">
      <button class="up" data-b="up" aria-label="up">&#9650;</button>
      <button class="left" data-b="left" aria-label="left">&#9664;</button>
      <button class="right" data-b="right" aria-label="right">&#9654;</button>
      <button class="down" data-b="down" aria-label="down">&#9660;</button>
    </div>
    <button class="center" data-b="click">OK</button>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js"></script>
<script>
const $ = id => document.getElementById(id);
const step = (txt, pct) => { $("msg").textContent = txt; $("bar").style.width = pct + "%"; };
const syncMsg = t => { $("sync").textContent = t; };
let py = null, api = null;

// every time the game saves, the save goes straight back to the Pi
let pending = null, sending = false;
window.gioSave = txt => { pending = txt; flush(); };
async function flush() {
  if (sending || pending === null) return;
  sending = true;
  const txt = pending; pending = null;
  try {
    const r = await fetch("/save", {method: "POST", body: txt, headers: {"Content-Type": "application/json"}, keepalive: true});
    syncMsg(r.ok ? "Progress saved to your game ✓" : "Couldn't save to your game - will try again");
    if (!r.ok && r.status !== 409) pending = pending ?? txt;   // 409 = the Pi already has a newer save
  } catch (e) { pending = pending ?? txt; syncMsg("Offline - progress will save when you're back online"); }
  sending = false;
  if (pending !== null) setTimeout(flush, $("sync").textContent.includes("✓") ? 0 : 3000);
}

const BOOT = `
import os, sys, time, json
os.environ["GIO_SIM"] = "1"
sys.path.insert(0, "/home/pyodide")
import game, js
HELD = game.SIM_KEYS
_write = game.write_progress
def _save_and_sync(s):
    _write(s)
    try:
        with open(game.PROGRESS_FILE) as f:
            js.gioSave(f.read())
    except OSError:
        pass
game.write_progress = _save_and_sync

class PhoneAudio(game.Audio):   # the game's own music + sound mixer, played by the phone's browser
    def __init__(self):
        game.Audio.__init__(self, False)   # sets everything up without starting the Pi's speaker
    def load(self):   # full range on phones/headphones, so no bass cut here
        self.sounds, self.tracks = game.build_sfx(), game.build_music()
        self.ok = True
AUD = PhoneAudio()
game.AUDIO = AUD
def audio_load():
    AUD.load()
def audio_chunk(n):
    return AUD.mix(n) if AUD.ok else bytes(2 * n)
g = game.Game()
_last = [time.time()]
def frame():
    now = time.time()
    dt = min(0.1, now - _last[0])
    _last[0] = now
    g.update(now, dt)
    return g.render(now).convert("RGBA").tobytes()
def press(b):
    g.on_press(b, time.time())
def hold(b, on):
    (HELD.add if on else HELD.discard)(b)
def save_now():
    if g.mode != "title":
        g.save()
`;

async function boot() {
  try {
    step("Loading the game engine (first time takes a bit)...", 10);
    py = await loadPyodide();
    step("Loading graphics...", 40);
    await py.loadPackage(["numpy", "pillow"]);
    step("Loading the game...", 70);
    const src = await (await fetch("/game.py", {cache: "no-store"})).text();
    py.FS.mkdirTree("/home/pyodide");
    py.FS.writeFile("/home/pyodide/game.py", src);
    py.FS.mkdirTree("/usr/share/fonts/truetype/dejavu");
    for (const f of ["DejaVuSans.ttf", "DejaVuSans-Bold.ttf"]) {
      const r = await fetch("/font/" + f);
      if (r.ok) py.FS.writeFile("/usr/share/fonts/truetype/dejavu/" + f, new Uint8Array(await r.arrayBuffer()));
    }
    step("Getting your progress...", 85);
    py.FS.mkdirTree("/home/jasyne/circuits");
    const s = await fetch("/save", {cache: "no-store"});
    if (s.ok) { const t = await s.text(); if (t.trim()) py.FS.writeFile("/home/jasyne/circuits/progress.json", t); }
    await py.runPythonAsync(BOOT);
    api = {frame: py.globals.get("frame"), press: py.globals.get("press"), hold: py.globals.get("hold"),
           save: py.globals.get("save_now"), chunk: py.globals.get("audio_chunk"), aload: py.globals.get("audio_load")};
    $("status").hidden = true;
    syncMsg("Your Bolts and progress are linked to your game ♥");
    run();
    setTimeout(() => { try { api.aload(); audioReady = true; } catch (e) {} }, 300);   // build the music after the first frames
  } catch (e) {
    step("Couldn't start the game. Is it turned on and online? (" + e + ")", 100);
  }
}

const ctx = $("c").getContext("2d"), img = ctx.createImageData(320, 240);
function run() {
  let next = performance.now();
  const tick = () => {
    const t = performance.now();
    if (t >= next) {
      next = t + 50;   // 20 frames a second, same as the real game
      const px = api.frame();
      img.data.set(px.toJs());
      px.destroy();
      ctx.putImageData(img, 0, 0);
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// ---- sound: ask the game for small chunks of mixed audio and queue them back to back
const RATE = 22050, CHUNK = 1024;
let actx = null, playAt = 0, audioReady = false;
function startAudio() {
  if (!actx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    actx = new AC();
    setInterval(pumpAudio, 30);
  }
  if (actx.state === "suspended") actx.resume();
}
function pumpAudio() {
  if (!api || !audioReady || !actx || actx.state !== "running") return;
  if (playAt < actx.currentTime + 0.02) playAt = actx.currentTime + 0.05;   // fell behind: restart a hair ahead
  while (playAt < actx.currentTime + 0.15) {
    const raw = api.chunk(CHUNK), bytes = raw.toJs(); raw.destroy();
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength >> 1);
    const buf = actx.createBuffer(1, pcm.length, RATE), out = buf.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) out[i] = pcm[i] / 32768;
    const src = actx.createBufferSource();
    src.buffer = buf; src.connect(actx.destination); src.start(playAt);
    playAt += pcm.length / RATE;
  }
}
addEventListener("pointerdown", startAudio, {capture: true});
addEventListener("keydown", startAudio, {capture: true});

const down = new Set();
function press(b, el) { if (!api || down.has(b)) return; down.add(b); el && el.classList.add("on"); api.hold(b, true); api.press(b); }
function release(b, el) { if (!down.has(b)) return; down.delete(b); el && el.classList.remove("on"); api && api.hold(b, false); }
document.querySelectorAll("button[data-b]").forEach(el => {
  const b = el.dataset.b;
  el.addEventListener("pointerdown", e => { e.preventDefault(); el.setPointerCapture(e.pointerId); press(b, el); });
  ["pointerup", "pointercancel", "lostpointercapture"].forEach(t => el.addEventListener(t, () => release(b, el)));
  el.addEventListener("contextmenu", e => e.preventDefault());
});
const KEYS = {ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", Enter: "click", " ": "click"};
const btn = b => document.querySelector('[data-b="' + b + '"]');
addEventListener("keydown", e => { const b = KEYS[e.key]; if (b) { e.preventDefault(); if (!e.repeat) press(b, btn(b)); } });
addEventListener("keyup", e => { const b = KEYS[e.key]; if (b) release(b, btn(b)); });
const releaseAll = () => [...down].forEach(b => release(b, btn(b)));
addEventListener("blur", releaseAll);
document.addEventListener("visibilitychange", () => {   // leaving the page = save + sync
  if (document.hidden) { releaseAll(); if (api) { api.save(); flush(); } if (actx) actx.suspend(); }
  else if (actx) actx.resume();
});
addEventListener("pagehide", () => { if (api) { api.save(); flush(); } });
boot();
</script>
</body></html>
"""
WEB_PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#2a1530">
<title>Jaslyne's Circuit Game</title>
<style>
  :root { --bg:#2a1530; --panel:#3b1f45; --pink:#ff7eb6; --pink2:#ffb3d4; --text:#fff3f8; --dim:#c9a7c0; }
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  html, body { margin:0; height:100%; background:var(--bg); color:var(--text);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif; overscroll-behavior:none; }
  body { display:flex; flex-direction:column; align-items:center; padding:12px 16px 20px;
    user-select:none; -webkit-user-select:none; touch-action:none; }
  h1 { font-size:18px; margin:4px 0 10px; letter-spacing:.5px; color:var(--pink2); }
  .wrap { width:100%; max-width:960px; display:flex; flex-direction:column; align-items:center; gap:16px; }
  .screen { width:100%; max-width:640px; aspect-ratio:4/3; background:#000; border-radius:14px;
    border:4px solid var(--pink); box-shadow:0 8px 24px rgba(0,0,0,.4); overflow:hidden; position:relative; }
  .screen img { width:100%; height:100%; display:block; image-rendering:pixelated; image-rendering:crisp-edges; }
  .status { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; text-align:center;
    padding:20px; font-size:15px; color:var(--dim); background:rgba(0,0,0,.75); }
  .status[hidden] { display:none; }
  .pad { width:100%; max-width:420px; display:flex; justify-content:space-between; align-items:center; gap:16px; }
  .dpad { display:grid; grid-template-columns:repeat(3,64px); grid-template-rows:repeat(3,64px); gap:6px; }
  button { font:inherit; color:var(--text); background:var(--panel); border:3px solid var(--pink);
    border-radius:14px; font-size:24px; touch-action:none; cursor:pointer; }
  button.on, button:active { background:var(--pink); color:var(--bg); }
  .up { grid-column:2; grid-row:1; } .left { grid-column:1; grid-row:2; }
  .right { grid-column:3; grid-row:2; } .down { grid-column:2; grid-row:3; }
  .center { width:104px; height:104px; border-radius:50%; font-size:16px; font-weight:700; letter-spacing:1px; }
  .hint { font-size:12px; color:var(--dim); text-align:center; line-height:1.5; }
  @media (orientation:landscape) and (max-height:520px) {
    body { padding:8px 16px; } h1 { display:none; }
    .wrap { flex-direction:row; justify-content:center; align-items:center; height:100%; }
    .screen { height:calc(100vh - 24px); width:auto; max-width:none; }
    .pad { flex-direction:column; width:auto; }
  }
</style></head>
<body>
<h1>Jaslyne's Circuit Game</h1>
<div class="wrap">
  <div class="screen"><img id="scr" alt="game screen"><div class="status" id="status">Connecting to the game...</div></div>
  <div class="pad">
    <div class="dpad">
      <button class="up" data-b="up" aria-label="up">&#9650;</button>
      <button class="left" data-b="left" aria-label="left">&#9664;</button>
      <button class="right" data-b="right" aria-label="right">&#9654;</button>
      <button class="down" data-b="down" aria-label="down">&#9660;</button>
    </div>
    <button class="center" data-b="click">OK</button>
  </div>
  <div class="hint">On a laptop: arrow keys to move, Enter or Space for OK.<br>Sound plays from the game itself.</div>
</div>
<script>
const scr = document.getElementById("scr"), status = document.getElementById("status");
const send = (s, b) => fetch("/k?s=" + s + "&b=" + b, {method: "POST", keepalive: true}).catch(() => {});
// ---- sound: ask the game for small chunks of mixed audio and queue them back to back
const RATE = 22050, CHUNK = 1024;
let actx = null, playAt = 0, audioReady = false;
function startAudio() {
  if (!actx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    actx = new AC();
    setInterval(pumpAudio, 30);
  }
  if (actx.state === "suspended") actx.resume();
}
function pumpAudio() {
  if (!api || !audioReady || !actx || actx.state !== "running") return;
  if (playAt < actx.currentTime + 0.02) playAt = actx.currentTime + 0.05;   // fell behind: restart a hair ahead
  while (playAt < actx.currentTime + 0.15) {
    const raw = api.chunk(CHUNK), bytes = raw.toJs(); raw.destroy();
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength >> 1);
    const buf = actx.createBuffer(1, pcm.length, RATE), out = buf.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) out[i] = pcm[i] / 32768;
    const src = actx.createBufferSource();
    src.buffer = buf; src.connect(actx.destination); src.start(playAt);
    playAt += pcm.length / RATE;
  }
}
addEventListener("pointerdown", startAudio, {capture: true});
addEventListener("keydown", startAudio, {capture: true});

const down = new Set();
function press(b, el) { if (down.has(b)) return; down.add(b); el && el.classList.add("on"); send("down", b); }
function release(b, el) { if (!down.has(b)) return; down.delete(b); el && el.classList.remove("on"); send("up", b); }
document.querySelectorAll("button[data-b]").forEach(el => {
  const b = el.dataset.b;
  el.addEventListener("pointerdown", e => { e.preventDefault(); el.setPointerCapture(e.pointerId); press(b, el); });
  ["pointerup", "pointercancel", "lostpointercapture"].forEach(t => el.addEventListener(t, () => release(b, el)));
  el.addEventListener("contextmenu", e => e.preventDefault());
});
const KEYS = {ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", Enter: "click", " ": "click"};
addEventListener("keydown", e => { const b = KEYS[e.key]; if (b) { e.preventDefault(); if (!e.repeat) press(b, document.querySelector('[data-b="' + b + '"]')); } });
addEventListener("keyup", e => { const b = KEYS[e.key]; if (b) release(b, document.querySelector('[data-b="' + b + '"]')); });
const releaseAll = () => [...down].forEach(b => release(b, document.querySelector('[data-b="' + b + '"]')));
addEventListener("blur", releaseAll);
document.addEventListener("visibilitychange", () => { if (document.hidden) releaseAll(); });
let last = null, fails = 0;
async function loop() {
  try {
    const r = await fetch("/frame.png?t=" + Date.now(), {cache: "no-store"});
    if (!r.ok) throw 0;
    const url = URL.createObjectURL(await r.blob());
    scr.src = url; if (last) URL.revokeObjectURL(last); last = url;
    fails = 0; status.hidden = true;
  } catch (e) {
    if (++fails > 3) { status.hidden = false; status.textContent = "Can't reach the game. Is it turned on and on the same Wi-Fi?"; }
    await new Promise(r => setTimeout(r, 800));
  }
  setTimeout(loop, 60);
}
loop();
</script>
</body></html>
"""


def save_rank(d):
    """How far along a save is - used to pick between the phone's save and the Pi's."""
    return (float(d.get("started_at", 0) or 0), len(d.get("done", [])), int(d.get("quests_done", 0) or 0),
            int(d.get("earned", 0) or 0), float(d.get("play", 0) or 0), float(d.get("saved_at", 0) or 0))


def web_held(name):
    with _web["lock"]:
        t = _web["held"].get(name)
    return t is not None and time.time() - t < 8.0   # safety: a lost "let go" message can't jam a button


def web_start():
    """Start the phone/laptop web page in the background. Never stops the game if it can't start."""
    if not WEB_PORT:
        return
    try:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from urllib.parse import parse_qs, urlparse
    except ImportError:
        return

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")   # the phone website lives at another address
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self._send(204, b"", "text/plain")

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html", "/play"):
                self._send(200, PLAY_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/remote":
                self._send(200, WEB_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/game.py":   # the phone runs this exact file, so it's always the same version
                with open(os.path.abspath(__file__), "rb") as f:
                    self._send(200, f.read(), "text/x-python; charset=utf-8")
            elif path.startswith("/font/") and path[6:] in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
                try:
                    with open("/usr/share/fonts/truetype/dejavu/" + path[6:], "rb") as f:
                        self._send(200, f.read(), "font/ttf")
                except OSError:
                    self._send(404, b"", "text/plain")
            elif path == "/save":
                try:
                    with open(PROGRESS_FILE, "rb") as f:
                        self._send(200, f.read(), "application/json")
                except OSError:
                    self._send(200, b"", "application/json")   # no save yet = brand-new game
            elif path in ("/frame.png", "/frame.jpg"):
                _web["want"] = time.time()
                frame = _web["frame"]
                self._send(200 if frame else 503, frame, "image/png")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):
            u = urlparse(self.path)
            if u.path == "/save":   # the phone saved: store it, and the Pi's game reloads it
                n = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(min(n, 2_000_000))
                try:
                    incoming = json.loads(body.decode("utf-8"))
                    try:
                        with open(PROGRESS_FILE) as f:
                            cur = f.read()
                        # keep whichever save is further ahead: the newer playthrough (NEW GAME), then story quests,
                        # then jobs, then Bolts ever earned,
                        # then play time, then newest. (Time alone lost progress: an empty Pi save looked "newer",
                        # and play time alone grows while the Pi just sits switched on.)
                        if save_rank(json.loads(cur)) > save_rank(incoming):
                            self._send(409, cur.encode("utf-8"), "application/json")
                            return
                    except (OSError, ValueError):
                        pass
                    os.makedirs(CIRCUIT_DIR, exist_ok=True)
                    tmp = PROGRESS_FILE + ".tmp"
                    with open(tmp, "wb") as f:
                        f.write(body)
                    os.replace(tmp, PROGRESS_FILE)
                    _web["reload"] = True
                    self._send(204, b"", "text/plain")
                except (ValueError, OSError):
                    self._send(400, b"bad save", "text/plain")
                return
            q = parse_qs(u.query)
            b, s = q.get("b", [""])[0], q.get("s", [""])[0]
            if u.path == "/k" and b in ("up", "down", "left", "right", "click"):
                with _web["lock"]:
                    if s == "down":
                        _web["held"][b] = time.time()
                        _web["presses"].append(b)
                    else:
                        _web["held"].pop(b, None)
            self._send(204, b"", "text/plain")

    try:
        srv = ThreadingHTTPServer(("", WEB_PORT), Handler)
    except OSError as e:
        print("Web page off:", e)
        return
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("Phone/laptop page on port %d" % WEB_PORT)


def web_frame(img):
    """Keep a PNG of the latest frame ready, but only while someone has the page open (saves the Pi's CPU).
    PNG keeps the pixel art perfectly sharp (JPEG smudged it), and pixel art compresses small anyway."""
    if WEB_PORT and time.time() - _web["want"] < 3.0:
        import io
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "PNG", compress_level=1)
        _web["frame"] = buf.getvalue()


def web_presses():
    with _web["lock"]:
        out, _web["presses"] = _web["presses"], []
    return out


def send_cmd(cmd):
    lgpio.gpio_write(h, DC_PIN, 0)
    spi.writebytes([cmd])


def send_data(data):
    lgpio.gpio_write(h, DC_PIN, 1)
    spi.writebytes2(data)


def init_display():
    if SIM or _early:   # already initialised by the boot blackout; a second reset would flash white
        return
    lgpio.gpio_write(h, RST_PIN, 1); time.sleep(0.05)
    lgpio.gpio_write(h, RST_PIN, 0); time.sleep(0.1)
    lgpio.gpio_write(h, RST_PIN, 1); time.sleep(0.15)
    send_cmd(0x01); time.sleep(0.15)
    send_cmd(0x11); time.sleep(0.15)
    send_cmd(0x3A); send_data([0x55])
    send_cmd(0x36); send_data([MADCTL])
    send_cmd(0x21 if INVERT_COLORS else 0x20)
    send_cmd(0x29); time.sleep(0.05)


def push_image(img):
    if SIM:
        img.save("/tmp/gio_frame.png")
        return
    send_cmd(0x2A); send_data([0x00, 0x00, 0x01, 0x3F])
    send_cmd(0x2B); send_data([0x00, 0x00, 0x00, 0xEF])
    a = np.asarray(img, dtype=np.uint16)
    if MIRROR_LEFT_RIGHT:
        a = a[:, ::-1]
    if SWAP_RED_BLUE:
        a = a[:, :, ::-1]
    v = ((a[:, :, 0] & 0xF8) << 8) | ((a[:, :, 1] & 0xFC) << 3) | (a[:, :, 2] >> 3)
    send_cmd(0x2C)
    send_data(v.astype(">u2").tobytes())


# ---------------- sound: MAX98357A I2S amp -> speaker ----------------
# Everything is synthesised here (chiptune style), mixed in a background thread and streamed to `aplay`,
# so music and sound effects can play at the same time. Turn it off with SOUND = False.
SOUND = True
AUDIO_DEVICE = os.environ.get("GIO_AUDIO", "plughw:CARD=MAX98357A,DEV=0")
AUDIO_RATE = 22050
MASTER_VOL = 0.32     # overall loudness (players fine-tune it in the SOUND menu)
SPEAKER_LOW_CUT = 200  # Hz - the little speaker can't play bass, it just buzzes, so it gets filtered out
SOUND_SLIDERS = [("ALL", "vol_all", "Everything at once"), ("MUSIC", "vol_music", "The calm background music"),
                 ("EFFECTS", "vol_fx", "Clicks, coins, doors, trophies"), ("VOICES", "vol_voice", "Character babble")]
MUSIC_VOL = 0.09      # music sits quietly under everything
_NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def _hz(name):
    return 440.0 * 2 ** ((12 * (int(name[-1]) + 1) + _NOTE[name[:-1]] - 69) / 12)


def tone(freq, dur, wave="square", vol=0.3, attack=0.004, release=0.04, duty=0.5, freq_end=None):
    n = max(1, int(AUDIO_RATE * dur))
    if freq <= 0:
        return np.zeros(n, np.float32)
    f = np.linspace(freq, freq_end, n) if freq_end else np.full(n, freq)
    ph = np.cumsum(f / AUDIO_RATE) % 1.0
    if wave == "square":   # rounded square: same chiptune feel, far less harsh fizz on a small speaker
        w = np.tanh(4 * (np.sin(2 * np.pi * ph) + np.cos(np.pi * duty))) / np.tanh(4)
    elif wave == "tri":
        w = 4 * np.abs(ph - 0.5) - 1
    elif wave == "sine":
        w = np.sin(2 * np.pi * ph)
    else:   # noise
        w = np.random.RandomState(7).uniform(-1, 1, n)
    env = np.ones(n)
    a, r = int(attack * AUDIO_RATE), int(release * AUDIO_RATE)
    if 0 < a < n:
        env[:a] = np.linspace(0, 1, a)
    if 0 < r < n:
        env[-r:] *= np.linspace(1, 0, r)
    return (w * env * vol).astype(np.float32)


def speaker_safe(x):
    """Take out the bass (makes small speakers rattle and distort) and smooth the top end a little."""
    n = max(3, int(AUDIO_RATE / SPEAKER_LOW_CUT))
    x = np.asarray(x, np.float32)
    y = x - np.convolve(x, np.ones(n, np.float32) / n, mode="same")
    return np.convolve(y, np.array([0.25, 0.5, 0.25], np.float32), mode="same").astype(np.float32)


def _seq(text, bpm, wave, vol, duty=0.5):
    """'E5:1 G5:1 -:2' -> notes (beats); '-' is a rest."""
    beat = 60.0 / bpm
    parts = []
    for tok in text.split():
        nm, beats = tok.split(":")
        dur = float(beats) * beat
        parts.append(np.zeros(int(AUDIO_RATE * dur), np.float32) if nm == "-" else
                     tone(_hz(nm), dur, wave, vol, release=min(0.07, dur * 0.4), duty=duty))
    return np.concatenate(parts)


def _layer(*tracks):
    out = np.zeros(max(len(t) for t in tracks), np.float32)
    for t in tracks:
        out[:len(t)] += t
    return out


def _arp(chords, bpm, vol):
    notes = []
    for ch in chords:
        for k in (0, 1, 2, 1, 0, 1, 2, 1):
            notes.append("%s:0.5" % ch[k])
    return _seq(" ".join(notes), bpm, "square", vol, duty=0.25)


def _pluck(freq, dur, vol):
    """Soft piano-like note: quick start, slow fade, a little warmth from quiet overtones."""
    n = int(AUDIO_RATE * dur)
    t = np.arange(n) / AUDIO_RATE
    w = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(4 * np.pi * freq * t) + 0.06 * np.sin(6 * np.pi * freq * t)
    env = np.exp(-t * 2.2) * (1 - np.exp(-t * 120))
    return (w * env * vol).astype(np.float32)


def _ambient(chords, scale, bpm, seed, vol, density=0.35):
    """Calm, sparse piano loop: one soft chord per bar, a few melody notes floating over it, then an echo."""
    r = random.Random(seed)
    beat = 60.0 / bpm
    bar = 4 * beat
    total = int(AUDIO_RATE * (bar * len(chords) + 4))
    out = np.zeros(total, np.float32)

    def put(note, start, dur, v):
        s = int(start * AUDIO_RATE)
        snd = _pluck(_hz(note), dur, v)
        out[s:s + len(snd)] += snd[:max(0, total - s)]
    for i, ch in enumerate(chords):
        t0 = i * bar
        for k, note in enumerate(ch):   # gently rolled chord, low and quiet
            put(note, t0 + k * 0.09, bar + 1.5, vol * 0.55)
        for b in range(4):
            if b and r.random() < density:
                put(r.choice(scale), t0 + b * beat + r.choice((0, 0, beat / 2)), 2.5, vol)
    d = int(0.38 * AUDIO_RATE)   # soft echo, like a big quiet room
    for k in (1, 2):
        out[d * k:] += out[:-d * k] * (0.28 / k)
    return out[:int(AUDIO_RATE * bar * len(chords))]


def build_music():
    """Original calm loops (Minecraft-style ambient piano) for each part of the game."""
    title = _ambient([("C3", "G3", "E4"), ("A2", "E3", "C4"), ("F2", "C3", "A3"), ("G2", "D3", "B3")] * 2,
                     ["E5", "G5", "C5", "D5", "A4", "G4"], 66, 1, MUSIC_VOL)
    world = _ambient([("A2", "E3", "C4"), ("F2", "C3", "A3"), ("D3", "A3", "F4"), ("E2", "B2", "G#3")] * 2,
                     ["A4", "C5", "E5", "D5", "B4", "G4"], 60, 2, MUSIC_VOL, density=0.3)
    build = _ambient([("D3", "A3", "F#4"), ("B2", "F#3", "D4"), ("G2", "D3", "B3"), ("A2", "E3", "C#4")] * 2,
                     ["F#5", "A5", "D5", "E5", "B4", "A4"], 72, 3, MUSIC_VOL, density=0.45)
    cozy = _ambient([("F2", "C3", "A3"), ("D3", "A3", "F4"), ("A#2", "F3", "D4"), ("C3", "G3", "E4")] * 2,
                    ["A4", "C5", "F5", "G5", "D5", "E5"], 58, 4, MUSIC_VOL, density=0.3)
    ending = _ambient([("C3", "G3", "E4"), ("F2", "C3", "A3"), ("A2", "E3", "C4"), ("G2", "D3", "B3")] * 2,
                      ["C5", "E5", "G5", "A5", "D5", "G4"], 70, 5, MUSIC_VOL, density=0.5)
    return dict(title=title, world=world, build=build, cozy=cozy, ending=ending)


def build_sfx():
    cat = lambda *p: np.concatenate(p)
    return dict(
        blip=tone(880, 0.035, vol=0.18),
        select=cat(tone(660, 0.04, vol=0.2), tone(990, 0.06, vol=0.2)),
        back=cat(tone(520, 0.04, vol=0.2), tone(390, 0.06, vol=0.2)),
        coin=cat(tone(988, 0.05, vol=0.22), tone(1319, 0.12, vol=0.22)),
        place=cat(tone(330, 0.03, "tri", 0.35), tone(660, 0.06, "tri", 0.35)),
        erase=tone(600, 0.12, vol=0.18, freq_end=200),
        error=tone(140, 0.16, vol=0.22),
        door=cat(tone(0, 0.01), tone(200, 0.08, "noise", 0.12), tone(260, 0.1, "tri", 0.3, freq_end=180)),
        power=cat(*[tone(_hz(n), 0.08, vol=0.2) for n in ("C5", "E5", "G5")], tone(_hz("C6"), 0.25, vol=0.2)),
        trophy=cat(*[tone(_hz(n), 0.09, vol=0.2) for n in ("G5", "C6", "E6")], tone(_hz("G6"), 0.3, vol=0.2)),
        pew=tone(1800, 0.18, vol=0.16, freq_end=300),
    )


VOICES = {   # Animal Crossing-style babble: (base pitch, wave)
    "jas": (520, "square"), "gio": (300, "square"), "silas": (190, "square"), "vex": (400, "square"),
    "master": (210, "square"), "pixel": (330, "tri"), "ada": (260, "square"), "flora": (560, "square"),
    "skye": (380, "square"), "tess": (600, "square"), "max": (150, "tri"), "page": (450, "square"),
    "riddle": (700, "tri"), "bolt": (640, "tri"),
    "canica": (950, "square"), "gummy": (230, "square"), "sofia": (820, "square"), "lafufu": (480, "sine"),
}
_VOWEL = {c: f for cs, f in (("aeiou", 1.0), ("bdgjlmnrvwyz", 1.15), ("cfhkpqstx", 1.3)) for c in cs}


class Audio:
    def __init__(self, enabled):
        self.ok, self.track, self.pos, self.sfx = False, None, 0, []
        self.tracks, self.sounds, self.syll = {}, {}, {}
        self.g_all, self.g_music, self.g_fx, self.g_voice = 0.6, 0.8, 0.5, 0.6   # set from the SOUND menu
        self.talk_text, self.talk_seen = None, 0
        self.lock = threading.Lock()
        if not enabled or not shutil.which("aplay"):
            return
        try:
            # small speaker buffer (~50 ms) so sounds come out right when you press a button
            self.proc = subprocess.Popen(["aplay", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(AUDIO_RATE), "-c", "1",
                                          "--buffer-time=90000", "--period-time=22500",
                                          "-D", AUDIO_DEVICE, "-"], stdin=subprocess.PIPE, bufsize=0,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            print("Sound off:", e)
            return
        try:   # shrink the pipe too, otherwise it can hold over a second of queued sound
            import fcntl
            fcntl.fcntl(self.proc.stdin.fileno(), 1031, 4096)   # F_SETPIPE_SZ
        except (ImportError, OSError):
            pass
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        # takes a moment, so it happens in the background
        self.sounds = {k: speaker_safe(v) for k, v in build_sfx().items()}
        self.tracks = {k: speaker_safe(v) for k, v in build_music().items()}
        self.ok = True
        chunk, lead = 1024, 0.07   # bigger chunks = far less work for the Pi; still only ~70 ms ahead
        start, written = time.time(), 0
        while True:
            ahead = written / AUDIO_RATE - (time.time() - start)
            if ahead > lead:
                time.sleep(ahead - lead)
            elif ahead < -0.25:   # fell behind (busy moment): catch up instead of lagging forever
                start, written = time.time(), 0
            try:
                self.proc.stdin.write(self.mix(chunk))
                written += chunk
            except (BrokenPipeError, OSError, ValueError):
                self.ok = False
                print("Sound stopped (check the amp wiring / AUDIO_DEVICE)")
                return

    def mix(self, n):
        out = np.zeros(n, np.float32)
        with self.lock:
            arr = self.tracks.get(self.track) if self.g_music > 0 else None
            if arr is not None:
                out += arr[(self.pos + np.arange(n)) % len(arr)] * self.g_music
                self.pos += n
            keep = []
            for snd in self.sfx:
                seg = snd[0][snd[1]:snd[1] + n]
                out[:len(seg)] += seg * (self.g_voice if snd[2] == "voice" else self.g_fx)
                snd[1] += n
                if snd[1] < len(snd[0]):
                    keep.append(snd)
            self.sfx = keep
        # soft limiter: loud moments get gently rounded off instead of hard clipping (= crackle)
        return (np.tanh(out * MASTER_VOL * self.g_all * 2) * 32767).astype(np.int16).tobytes()

    def play(self, name):
        if self.ok and self.g_fx > 0 and name in self.sounds:
            with self.lock:
                self.sfx = self.sfx[-6:] + [[self.sounds[name], 0, "fx"]]

    def set_gains(self, all_, music, fx, voice):
        self.g_all, self.g_music, self.g_fx, self.g_voice = all_, music, fx, voice

    def set_track(self, name):
        if name != self.track:
            with self.lock:
                self.track, self.pos = name, 0

    def talk(self, key, text, shown):
        """Babble one syllable for newly typed letters, in the speaker's voice."""
        if text != self.talk_text:
            self.talk_text, self.talk_seen = text, 0
        if not self.ok or self.g_voice <= 0 or key not in VOICES or shown <= self.talk_seen:
            self.talk_seen = max(self.talk_seen, shown)
            return
        new = text[self.talk_seen:min(shown, len(text))]
        self.talk_seen = shown
        letters = [c for c in new.lower() if c.isalpha()]
        if not letters:
            return
        c = letters[0]
        k = (key, c)
        if k not in self.syll:
            base, wave = VOICES[key]
            f = base * _VOWEL.get(c, 1.0) * (1 + (ord(c) % 5) * 0.04)
            self.syll[k] = speaker_safe(tone(f, 0.05, wave, 0.16, release=0.02) + tone(f * 2, 0.05, "sine", 0.06, release=0.02))
        with self.lock:
            self.sfx = self.sfx[-6:] + [[self.syll[k], 0, "voice"]]


class _Silent:
    ok = False

    def set_gains(self, *a):
        pass

    def play(self, name):
        pass

    def set_track(self, name):
        pass

    def talk(self, key, text, shown):
        pass


AUDIO = _Silent()


# ---------------- small helpers ----------------
def slide(cur, tgt, step):
    if cur < tgt:
        return min(tgt, cur + step)
    if cur > tgt:
        return max(tgt, cur - step)
    return cur


_wrap_cache = {}


def wrap(d, text, fnt, maxw):
    key = (text, id(fnt), maxw)
    if key not in _wrap_cache:
        if len(_wrap_cache) > 600:
            _wrap_cache.clear()
        _wrap_cache[key] = _wrap(d, text, fnt, maxw)
    return list(_wrap_cache[key])


def _wrap(d, text, fnt, maxw):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if d.textlength(t, font=fnt) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def center_text(d, y, text, fnt, fill, cx=W // 2, shadow=None):
    w = d.textlength(text, font=fnt)
    if shadow:
        d.text((cx - w / 2 + 1, y + 1), text, font=fnt, fill=shadow)
    d.text((cx - w / 2, y), text, font=fnt, fill=fill)


def shadow_text(d, xy, text, fnt, fill, shadow=(0, 0, 0)):
    d.text((xy[0] + 1, xy[1] + 1), text, font=fnt, fill=shadow)
    d.text(xy, text, font=fnt, fill=fill)


def draw_box(d, r, fill=CREAM, border=NAVY, rad=5):
    x0, y0, x1, y1 = r
    try:
        d.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=fill, outline=border, width=2)
        d.rounded_rectangle([x0 + 3, y0 + 3, x1 - 3, y1 - 3], radius=max(1, rad - 2), outline=(196, 196, 214), width=1)
    except AttributeError:
        d.rectangle([x0, y0, x1, y1], fill=fill, outline=border, width=2)


def star_points(cx, cy, r, rot=0.0):
    pts = []
    for i in range(10):
        ang = rot + i * math.pi / 5 - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return pts


def draw_star(d, cx, cy, r, fill, outline=(120, 90, 0)):
    d.polygon(star_points(cx, cy, r), fill=fill, outline=outline)


def draw_bolt(d, cx, cy, s=1.0, fill=YELLOW):
    pts = [(2, -6), (-3, 1), (0, 1), (-2, 7), (4, -1), (1, -1)]
    d.polygon([(cx + x * s, cy + y * s) for x, y in pts], fill=fill, outline=(120, 90, 0))


def lerp_col(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------- circuit board art ----------------
BW, BH = 212, 134


def make_board():
    im = Image.new("RGB", (BW, BH), CYAN)
    d = ImageDraw.Draw(im)
    for y in range(16, BH - 12, 6):
        for x in range(8, BW - 6, 6):
            d.point((x, y), fill=DOT)
    d.line([(4, 6), (BW - 5, 6)], fill=(220, 40, 40), width=2)
    d.line([(4, BH - 7), (BW - 5, BH - 7)], fill=(40, 80, 220), width=2)
    return im


PART_LABELS = {"led": "LED", "resistor": "resistor", "button": "button", "switch": "switch", "pot": "slide pot",
               "fan": "fan", "vibe": "vibe motor", "dip": "DIP switch", "ldr": "light sensor", "buzzer": "buzzer",
               "cap": "capacitor", "npn": "transistor", "diode": "diode", "motor": "DC motor", "laser": "laser"}


def tag(d, x, y, text, fill=(255, 255, 240), ink=INK, border=(60, 80, 100)):
    """Small name tag centred on (x, y)."""
    w = d.textlength(text, font=F_S)
    x0 = int(max(1, min(BW - w - 5, x - w / 2 - 2)))
    d.rectangle([x0, y, x0 + w + 3, y + 9], fill=fill, outline=border)
    d.text((x0 + 2, y), text, font=F_S, fill=ink)


def label_board(d, steps, highlight_last=True):
    """Names on every part plus labelled power rails, so the board reads like a real diagram.
    The part added in the latest step gets a yellow 'NEW' label."""
    tag(d, 26, 9, "+ POWER (red)", fill=(255, 225, 225), ink=(150, 20, 20), border=(200, 60, 60))
    tag(d, 30, BH - 18, "- GROUND (blue)", fill=(225, 232, 255), ink=(20, 40, 150), border=(60, 80, 200))
    row_count = {}   # labels in the same row take turns high/low so neighbours never overlap
    grounds = 0
    for si, st in enumerate(steps):
        new = highlight_last and si == len(steps) - 1
        hi = dict(fill=YELLOW, ink=(0, 0, 0), border=(0, 0, 0)) if new else {}
        pre = "NEW: " if new else ""
        for it in st["items"]:
            k = it[0]
            if k in PART_LABELS:
                name = PART_LABELS[k]
                if k == "led" and len(it) > 3:
                    name = "%s LED" % it[3]
                n = row_count.get(it[2], 0)
                row_count[it[2]] = n + 1
                big = k in ("fan", "vibe")
                if k == "pot" and len(it) > 3:
                    tag(d, it[1] + 34, it[2] - 4, pre + name, **hi)
                    continue
                if it[2] >= 95:   # bottom path: below, or above when it's a 'high' turn
                    off = -(33 if big else 22) if n % 2 == 0 else (23 if big else 13)
                else:
                    off = (23 if big else 13) if n % 2 == 0 else (34 if big else 24)
                tag(d, it[1], it[2] + off, pre + name, **hi)
            elif k == "wire" and it[3] == "red" and it[1][1] < 12 and it[2][1] >= 65:
                tag(d, it[1][0] + 22, (it[1][1] + it[2][1]) // 2 - 4, pre + "power wire", **(hi or dict(fill=(255, 225, 225))))
            elif k == "wire" and it[3] == "black" and it[2][1] > BH - 15:
                tag(d, it[1][0], 18 + 11 * grounds, pre + "ground wire", **(hi or dict(fill=(225, 225, 230))))
                grounds += 1


def draw_fan(d, x, y, ang):
    d.ellipse([x - 21, y - 21, x + 21, y + 21], fill=(45, 50, 60), outline=(0, 0, 0))
    for i in range(4):
        a0 = ang + i * math.pi / 2
        pts = [(x, y),
               (x + 19 * math.cos(a0 - 0.35), y + 19 * math.sin(a0 - 0.35)),
               (x + 19 * math.cos(a0 + 0.35), y + 19 * math.sin(a0 + 0.35))]
        d.polygon(pts, fill=(170, 175, 190), outline=(20, 20, 25))
    d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(230, 230, 235), outline=(0, 0, 0))


LEAD = (150, 150, 160)


def draw_art(d, art, gold=False):
    wcols = WIRE_GOLD if gold else WIRE
    for it in art:
        k = it[0]
        if k == "wire":
            _, a, b, col = it
            d.line([a, b], fill=wcols[col], width=3)
            for p in (a, b):
                d.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill=wcols[col], outline=(0, 0, 0))
        elif k == "trace":
            d.line([it[1], it[2]], fill=(60, 60, 70), width=1)
        elif k == "button":
            x, y = it[1], it[2]
            for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):   # its 4 legs
                d.line([(x + sx * 10, y + sy * 10), (x + sx * 14, y + sy * 14)], fill=LEAD, width=2)
            d.rectangle([x - 11, y - 11, x + 11, y + 11], fill=(70, 75, 85), outline=(0, 0, 0))
            d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(30, 30, 35), outline=(120, 120, 130))
        elif k == "resistor":
            x, y = it[1], it[2]
            d.line([(x - 20, y), (x + 20, y)], fill=LEAD, width=1)
            d.rectangle([x - 14, y - 4, x + 14, y + 4], fill=(205, 175, 115), outline=(90, 70, 40))
            for dx, col in ((-8, (120, 60, 20)), (-2, (20, 20, 20)), (4, (220, 40, 40))):
                d.line([(x + dx, y - 4), (x + dx, y + 4)], fill=col, width=2)
        elif k == "led":
            x, y = it[1], it[2]
            col = LED_COL[it[3] if len(it) > 3 else "red"]
            d.line([(x - 20, y), (x - 8, y)], fill=LEAD, width=2)   # long leg = +
            d.line([(x + 8, y), (x + 12, y)], fill=LEAD, width=1)   # short leg = -
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=col, outline=(0, 0, 0))
            d.ellipse([x - 4, y - 5, x, y - 1], fill=tuple(min(255, c + 120) for c in col))
            d.line([(x + 7, y - 6), (x + 7, y + 6)], fill=tuple(max(0, c - 110) for c in col), width=2)   # flat edge
            d.text((x - 19, y - 14), "+", font=F_B, fill=(200, 20, 20))
            d.text((x + 9, y - 14), "-", font=F_B, fill=(20, 20, 120))
        elif k == "switch":
            x, y = it[1], it[2]
            d.line([(x - 20, y), (x + 20, y)], fill=LEAD, width=1)
            d.rectangle([x - 14, y - 7, x + 14, y + 7], fill=(50, 50, 60), outline=(0, 0, 0))
            d.rectangle([x - 9, y - 4, x - 1, y + 4], fill=(235, 235, 240))
        elif k == "pot":
            x, y = it[1], it[2]
            three = len(it) > 3 and it[3] == "3pin"
            if not three:
                d.line([(x - 20, y), (x + 20, y)], fill=LEAD, width=1)
            for px_ in (-8, 0, 8):   # its 3 pins (middle = slider)
                d.line([(x + px_, y + 8), (x + px_, y + 13)], fill=LEAD, width=2)
            d.rectangle([x - 14, y - 7, x + 14, y + 8], fill=(40, 90, 200), outline=(0, 0, 0))
            d.line([(x - 10, y), (x + 10, y)], fill=(15, 30, 80), width=2)   # slider track
            d.rectangle([x + 1, y - 5, x + 6, y + 5], fill=(220, 220, 230), outline=(60, 60, 70))   # knob
            if three:
                for n_, px_ in ((1, -8), (2, 0), (3, 8)):
                    d.text((x + px_ - 2, y - 17), str(n_), font=F_S, fill=(20, 40, 120))
        elif k == "fan":
            x, y = it[1], it[2]
            d.line([(x - 26, y - 3), (x - 19, y - 3)], fill=(220, 40, 40), width=2)   # red = +
            d.line([(x - 26, y + 3), (x - 19, y + 3)], fill=(25, 25, 30), width=2)    # black = -
            draw_fan(d, x, y, 0.4)
        elif k == "vibe":
            x, y = it[1], it[2]
            d.line([(x - 22, y - 4), (x - 12, y - 4)], fill=(220, 40, 40), width=1)
            d.line([(x - 22, y + 4), (x - 12, y + 4)], fill=(25, 25, 30), width=1)
            d.ellipse([x - 14, y - 14, x + 14, y + 14], fill=(175, 175, 185), outline=(0, 0, 0))
        elif k == "dip":
            x, y = it[1], it[2]
            used = int(it[3]) if len(it) > 3 and str(it[3]).isdigit() else 1   # how many switches are flipped ON
            d.rectangle([x - 17, y - 11, x + 17, y + 11], fill=(30, 80, 190), outline=(0, 0, 0))
            d.text((x - 16, y - 21), "ON", font=F_S, fill=(20, 110, 40))
            for n in range(3):   # the kit's DIP block has 3 switches
                bx = x - 12 + n * 9
                d.rectangle([bx, y - 7, bx + 5, y + 7], fill=(20, 40, 100))   # slot
                ky = y - 7 if n < used else y + 1                               # flipped to ON?
                d.rectangle([bx, ky, bx + 5, ky + 6], fill=(240, 240, 245))
            for n in range(used - 1):   # jumper: this switch's bottom leg to the next switch's top leg
                bx = x - 9 + n * 9
                d.line([(bx, y + 13), (bx + 9, y - 13)], fill=(250, 200, 40), width=2)
        elif k == "ldr":
            x, y = it[1], it[2]
            d.line([(x - 20, y), (x + 20, y)], fill=LEAD, width=1)
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(190, 140, 60), outline=(0, 0, 0))
            d.line([(x - 6, y - 5), (x + 6, y - 5), (x - 6, y), (x + 6, y), (x - 6, y + 5), (x + 6, y + 5)],
                   fill=(70, 45, 20), width=1)
        elif k == "buzzer":
            x, y = it[1], it[2]
            d.line([(x - 20, y), (x + 20, y)], fill=LEAD, width=1)
            d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=(28, 28, 34), outline=(100, 100, 110))
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(80, 80, 90))
            d.text((x - 9, y - 10), "+", font=F_S, fill=(200, 200, 210))
        elif k == "cap":
            x, y = it[1], it[2]
            d.line([(x - 20, y), (x + 20, y)], fill=LEAD, width=1)
            d.rectangle([x - 11, y - 7, x + 11, y + 7], fill=(40, 70, 170), outline=(0, 0, 0))
            d.rectangle([x - 11, y - 7, x - 6, y + 7], fill=(180, 190, 230))
            d.text((x - 10, y - 5), "-", font=F_S, fill=(20, 30, 80))
        elif k == "npn":
            x, y = it[1], it[2]
            d.line([(x - 10, y), (x - 18, y)], fill=LEAD, width=1)
            d.line([(x, y - 10), (x, y - 18)], fill=LEAD, width=1)
            d.line([(x, y + 10), (x, y + 20)], fill=LEAD, width=1)
            d.rectangle([x - 10, y - 10, x + 10, y + 10], fill=(35, 35, 45), outline=(0, 0, 0))
            d.text((x - 8, y - 5), "NPN", font=F_S, fill=(200, 200, 215))
        elif k == "diode":
            x, y = it[1], it[2]
            d.line([(x - 20, y), (x + 20, y)], fill=LEAD, width=1)
            d.rectangle([x - 10, y - 4, x + 10, y + 4], fill=(40, 40, 46), outline=(0, 0, 0))
            d.rectangle([x + 5, y - 4, x + 8, y + 4], fill=(205, 205, 215))
        elif k == "motor":   # DC motor: silver can with a shaft
            x, y = it[1], it[2]
            rev = len(it) > 3 and it[3] == "rev"   # wired the other way round
            d.line([(x - 20, y - 3), (x - 13, y - 3)], fill=(25, 25, 30) if rev else (220, 40, 40), width=2)
            d.line([(x - 20, y + 3), (x - 13, y + 3)], fill=(220, 40, 40) if rev else (25, 25, 30), width=2)
            d.rounded_rectangle([x - 13, y - 9, x + 9, y + 9], radius=3, fill=(185, 190, 200), outline=(60, 60, 70))
            d.rectangle([x - 13, y - 9, x - 9, y + 9], fill=(120, 60, 50))
            d.rectangle([x + 9, y - 2, x + 16, y + 2], fill=(220, 220, 230), outline=(80, 80, 90))
            d.line([(x - 6, y - 9), (x - 6, y + 9)], fill=(150, 155, 165))
        elif k == "laser":   # laser module: dark body, gold lens
            x, y = it[1], it[2]
            d.line([(x - 20, y - 3), (x - 14, y - 3)], fill=(220, 40, 40), width=2)   # + (red)
            d.line([(x - 20, y + 3), (x - 14, y + 3)], fill=(25, 25, 30), width=2)    # - (black)
            d.rectangle([x - 14, y - 6, x + 8, y + 6], fill=(40, 30, 34), outline=(0, 0, 0))
            d.rectangle([x - 10, y - 3, x + 2, y + 3], fill=(200, 40, 50))
            d.rectangle([x + 8, y - 4, x + 13, y + 4], fill=(230, 190, 70), outline=(110, 80, 20))
            d.ellipse([x + 10, y - 2, x + 13, y + 1], fill=(255, 90, 90))


# ---------------- quests ----------------
ZONES = ["THE WORKSHOP", "THE LAB", "MOTOR TOWER", "SENSOR WING", "CONTROL ROOM", "GREENHOUSE", "THE ROOFTOP"]
PER_ZONE = 3

# Every circuit uses only the real kit: wires, resistor, LEDs, button, DIP switch, slide pot, fan,
# vibe motor, DC motor and laser. Boards are laid out automatically from the list of parts.
PART_W = dict(button=28, resistor=40, led=36, dip=44, pot=40, fan=46, vibe=46, motor=40, laser=40)
PART_NAME = dict(button="button", resistor="resistor", dip="DIP switch", pot="slide pot", fan="fan",
                 vibe="vibe motor", motor="DC motor", laser="laser")
# Gio walks her through every step. The first time she meets a part he explains it properly; after that he
# just gives a short, varied reminder. Every step also says exactly what the part connects to on each side,
# so series/parallel wiring always makes sense. The + rail is wired to the Pi's 5V pin.
PART_INTRO = dict(
    resistor=["Add the RESISTOR - the little tan part with colored stripes on it.",
              "A resistor slows the power down a little, so an LED gets just enough and doesn't burn out.",
              "It has NO + or - side, so it can go in either way round. Easy one!"],
    led=["Add the {name}. Look closely at its two metal legs: one is LONGER than the other.",
         "The long leg is + and the short leg is -. LEDs only light up one way round, so this matters!",
         "If one ever stays dark, it's probably just backwards. No harm done - flip it around."],
    button=["Add the BUTTON - the little square with a round top and 4 legs.",
            "It sits across the gap down the middle of the breadboard, two legs on each side.",
            "It only lets power through while you're holding it down. Let go and the power stops."],
    dip=["Add the DIP SWITCH - the blue block with a row of tiny white switches.",
         "Its legs go across the middle gap, like the button. Find the word ON printed on it.",
         "Push switch number 1 toward ON with a fingernail or pen tip. Unlike a button, it STAYS on."],
    pot=["Add the SLIDE POT - the long part with a little knob that slides back and forth.",
         "It has 3 pins: one at each end and one in the middle. The middle pin follows the slider.",
         "We use one END pin and the MIDDLE pin. Sliding the knob then lets more or less power through."],
    fan=["Add the FAN. It has two wires: one RED and one BLACK.",
         "A fan is really a little motor with blades on it. Fun fact: swap its wires and it blows the other way!"],
    vibe=["Add the VIBE MOTOR - the tiny round coin with a red wire and a black wire.",
          "Inside, a little lopsided weight spins super fast. That wobble is the buzz - just like a phone!"],
    motor=["Add the DC MOTOR - the little silver can with a metal shaft sticking out the front.",
           "It has 2 pins on the back. Which way it spins depends on which pin gets the + side. Remember that!"],
    laser=["Add the LASER module - the small tube with a lens on the front end.",
           "It has a + side and a - side, and a tiny resistor already built in, so no extra resistor needed.",
           "Safety first: NEVER point a laser at anyone's eyes - including yours!"],
)
PART_AGAIN = dict(   # short reminders once she knows the part (a few versions so it doesn't repeat)
    resistor=["Another resistor - either way round is fine.", "Pop in a resistor. No + or - to worry about!",
              "Resistor time. Any direction works."],
    led=["Here comes the {name}.", "Grab the {name}.", "Next up: the {name}."],
    button=["Add a button, across the middle gap like before.", "Another button - straddle the middle gap."],
    dip=["Add a DIP switch, and flip switch 1 to ON.", "DIP switch time - remember to flip switch 1 ON!"],
    pot=["Add the slide pot - one end pin and the middle pin, like last time."],
    fan=["Add the fan."], vibe=["Add the vibe motor."], motor=["Add the DC motor."],
    laser=["Add the laser - and keep that beam away from eyes!"],
)
POLAR = {"led", "fan", "vibe", "motor", "laser"}   # parts where it matters which side goes toward +


def connect_page(k, name, prev, nxt):
    """Exactly where the new part plugs in, on both sides."""
    if k == "led":
        return "Put its LONG (+) leg in the same row as the %s, and its SHORT (-) leg in a fresh row for the %s." % (prev, nxt)
    if k in ("fan", "vibe", "motor", "laser"):
        return "Its RED (+) wire goes in the row with the %s. Its BLACK (-) wire goes in a fresh row for the %s." % (prev, nxt)
    if k in ("button", "dip"):
        return "One side connects to the %s's row, the other side starts a fresh row for the %s." % (prev, nxt)
    if k == "pot":
        return "One end pin goes in the %s's row, and the middle pin goes in a fresh row for the %s." % (prev, nxt)
    return "One end goes in the %s's row, the other end in a fresh row for the %s." % (prev, nxt)


RED_WIRE_FIRST = ["Grab a RED wire. Plug one end into the RED line at the very top - the + POWER rail.",
                  "Plug its other end into a row in the middle of the board. Red always means + power!"]
RED_WIRE_AGAIN = ["Red wire from the + rail at the top down into your row.", "Start with a red wire: + rail to your row.",
                  "As always, a red wire brings + power down from the top rail."]
BLACK_WIRE_FIRST = ["Last part! Grab a BLACK wire. Plug one end into the row right after your last part...",
                    "...and the other end into the BLUE line at the bottom - the - GROUND rail. Now the loop is complete!"]
BLACK_WIRE_AGAIN = ["Finish with a black wire from the last row down to the blue - rail.",
                    "Black wire from your last part down to ground. Loop complete!", "Close the loop: black wire to the bottom rail."]
SPLIT_FIRST = "Now the power SPLITS into two paths, like a fork in a road. Each path gets its own parts. Top path first!"
SPLIT_AGAIN = "Time to split into two paths again - top path first."
BOTTOM_PAGE = "Top path done! Now the BOTTOM path. It starts from the same split point."
JOIN_FIRST = ["Last part! A BLACK wire joins the END of the top path and the END of the bottom path...",
              "...and goes down to the blue - GROUND rail. Both paths have a way home now, so both work at once!"]
JOIN_AGAIN = ["Black wire: join the ends of both paths, then down to the blue - rail."]
SERIES_PAGES = ["This is SERIES! The first LED's short (-) leg and this LED's long (+) leg go in the SAME row.",
                "So the power flows through the first LED, then straight into this one. One single path, like a line."]
BREADBOARD_INTRO = [
    "Hi Jaslyne! It's me, Gio. I'll walk you through every single step, promise.",
    "This board is called a BREADBOARD. You push parts into its little holes - no tools or glue needed.",
    "Holes in the same short ROW are connected underneath. That's how parts in the same row talk to each other.",
    "The RED line at the top is the + POWER rail (it gets 5 volts from the Pi). The BLUE line at the bottom is - GROUND.",
    "Power flows out of +, through your parts, and back into -. That full loop is called a CIRCUIT.",
    "Press CENTER for the next tip, LEFT to go back. Let's build!"]
_LEARNED = set()   # parts explained so far, in level order


def _part(spec, x, y):
    k, _, extra = spec.partition(":")
    if k == "led":
        return "%s LED" % extra, ("led", x, y, extra)
    return PART_NAME[k], (k, x, y, extra) if extra else (k, x, y)


def _names(specs):
    return [_part(sp, 0, 0)[0] for sp in specs]


def _lay(specs, x, y, prev, last_next, tips):
    out = []
    names = _names(specs)
    for i, spec in enumerate(specs):
        k, _, extra = spec.partition(":")
        w = PART_W[k]
        cx = x + 4 + w // 2
        name, item = _part(spec, cx, y)
        said = "second " + name if name in names[:i] else name   # two of the same LED in a row
        nxt = names[i + 1] if i + 1 < len(names) else last_next
        if nxt.endswith("LED") and k == "led":
            nxt = "next LED"
        if k == "dip" and extra in ("2", "3"):
            n = int(extra)
            which = "1 AND 2" if n == 2 else "1, 2 AND 3"
            pages = (["This time we use %s switches on the SAME DIP block - no second block needed!" % ("TWO" if n == 2 else "ALL THREE"),
                      "Put the DIP block across the middle gap like always, and flip switches %s to ON." % which]
                     + ([PART_INTRO["dip"][1]] if "dip" not in _LEARNED else []))
            _LEARNED.add("dip")
        elif k in tips:
            pages = list(tips[k])
        elif k in _LEARNED:
            pick = random.Random(sum(map(ord, said)) + cx * 7 + y * 13 + i)
            pages = [pick.choice(PART_AGAIN[k]).format(name=said)]
        else:
            pages = [p.format(name=name) for p in PART_INTRO[k]]
            _LEARNED.add(k)
        if k == "dip" and extra in ("2", "3"):
            n = int(extra)
            pages.append("Power from the %s goes into switch 1's top leg." % prev)
            pages.append("A short jumper wire joins switch 1's BOTTOM leg to switch 2's TOP leg%s." %
                         ("" if n == 2 else ", and another joins switch 2's bottom leg to switch 3's top leg"))
            pages.append("Switch %d's bottom leg starts a fresh row for the %s. Power has to get through EVERY switch, "
                         "so they ALL have to be ON - that's an AND circuit!" % (n, nxt))
        elif k == "led" and prev.endswith("LED"):
            pages += SERIES_PAGES
        elif k == "motor" and extra == "rev":
            pages.append("So: BLACK wire in the %s's row, RED wire in a fresh row for the %s." % (prev, nxt))
        else:
            pages.append(connect_page(k, name, prev, nxt))
        out.append(dict(part=name, pages=pages, items=[("trace", (x, y), (cx - w // 2 + 2, y)), item]))
        x = cx + w // 2 - 2
        prev = name
    return out, x


def _again(key, first, again):
    if key in _LEARNED:
        return [random.Random(len(_LEARNED) + len(key)).choice(again)]
    _LEARNED.add(key)
    return list(first)


def make_steps(main, top=None, bottom=None, y=70, tips=None):
    """Red wire, the parts in a row (and optionally two parallel paths), then the black ground wire."""
    tips = tips or {}
    steps = [dict(part="wires", pages=_again("redwire", RED_WIRE_FIRST, RED_WIRE_AGAIN),
                  items=[("wire", (24, 9), (24, y), "red")])]
    row, x = _lay(main, 24, y, "red wire", "split point" if top else "black wire", tips)
    steps += row
    if top:
        sx = x + 6
        t, xt = _lay(top, sx, 40, "split point", "black wire", tips)
        b, xb = _lay(bottom, sx, 100, "split point", "black wire", tips)
        t[0]["items"] = [("trace", (x, y), (sx, y)), ("trace", (sx, y), (sx, 40))] + t[0]["items"]
        b[0]["items"] = [("trace", (sx, y), (sx, 100))] + b[0]["items"]
        split = SPLIT_AGAIN if "split" in _LEARNED else SPLIT_FIRST
        _LEARNED.add("split")
        t[0]["pages"] = [split] + t[0]["pages"]
        b[0]["pages"] = [BOTTOM_PAGE] + b[0]["pages"]
        steps += t + b
        jx = max(xt, xb) + 8
        steps.append(dict(part="wires", pages=_again("join", JOIN_FIRST, JOIN_AGAIN),
                          items=[("trace", (xt, 40), (jx, 40)), ("trace", (xb, 100), (jx, 100)),
                                 ("wire", (jx, 40), (jx, 125), "black")]))
    else:
        jx = x + 10
        steps.append(dict(part="wires", pages=_again("blackwire", BLACK_WIRE_FIRST, BLACK_WIRE_AGAIN),
                          items=[("trace", (x, y), (jx, y)), ("wire", (jx, y), (jx, 125), "black")]))
    return _number(steps)


def _number(steps):
    for i, st in enumerate(steps):
        st["pages"][0] = "Step %d: %s" % (i + 1, st["pages"][0])
        st["text"] = st["pages"][0]
    return steps


def _finish(title, npc, meter, hint, win, fact, steps):
    counts = {}
    for st in steps:
        counts[st["part"]] = counts.get(st["part"], 0) + 1
    parts = [(n, name) for name, n in counts.items() if name != "wires"] + [(counts.get("wires", 0), "wires")]
    return dict(title=title, short=title, npc=npc, meter=meter, parts=[p for p in parts if p[0]], hint=hint, win=win,
                fact=fact, steps=steps)


def level(title, npc, meter, hint, win, fact, main, top=None, bottom=None, tips=None):
    return _finish(title, npc, meter, hint, win, fact, make_steps(main, top, bottom, tips=tips))


def pot_level(title, npc, meter, hint, win, fact, color):
    """Slide pot wired the way the real kit's pot works: pin 1 = + power, pin 2 (middle) = output, pin 3 = ground.
    The output pin feeds a resistor and LED, so sliding the knob dims the LED."""
    px, py = 60, 40
    first = "pot" not in _LEARNED
    _LEARNED.add("pot")
    _LEARNED.add("redwire")
    _LEARNED.add("blackwire")
    if first:
        pot_pages = ["Add the SLIDE POT - the long part with a little knob that slides back and forth.",
                     "It has 3 pins in a row: pin 1 is POWER (+), pin 3 is GROUND (-), and pin 2 in the middle is the OUTPUT.",
                     "Sliding the knob changes how much power comes out of pin 2. That's what will dim the LED!"]
    else:
        pot_pages = ["Add the slide pot again. Remember: pin 1 power, pin 2 output, pin 3 ground."]
    steps = _number([
        dict(part="slide pot", pages=pot_pages, items=[("pot", px, py, "3pin")]),
        dict(part="wires", pages=["Red wire from the + rail at the top down to PIN 1 of the slide pot (the left pin)."],
             items=[("wire", (px - 24, 9), (px - 24, py + 18), "red"), ("trace", (px - 24, py + 18), (px - 8, py + 18)),
                    ("trace", (px - 8, py + 18), (px - 8, py + 13))]),
        dict(part="wires", pages=["Black wire from PIN 3 (the right pin) over to the blue - rail at the bottom.",
                                  "Now power flows across the whole slide pot, from pin 1 to pin 3."],
             items=[("trace", (px + 8, py + 13), (px + 8, py + 18)), ("trace", (px + 8, py + 18), (200, py + 18)),
                    ("wire", (200, py + 18), (200, 125), "black")]),
        dict(part="resistor", pages=["Add a resistor in a fresh row connected to PIN 2 - the middle pin.",
                                     "Pin 2 is the output: whatever power the slider lets through comes out here."],
             items=[("trace", (px, py + 13), (px, 70)), ("trace", (px, 70), (80, 70)), ("resistor", 100, 70)]),
        dict(part="%s LED" % color, pages=["Add the %s LED: long (+) leg in the resistor's row, short (-) leg in a fresh row." % color],
             items=[("trace", (120, 70), (122, 70)), ("led", 140, 70, color)]),
        dict(part="wires", pages=["Black wire from the LED's short leg down to the blue - rail.",
                                  "Once it's powered, slide the knob and watch the LED get brighter and dimmer!"],
             items=[("trace", (154, 70), (165, 70)), ("wire", (165, 70), (165, 125), "black")]),
    ])
    return _finish(title, npc, meter, hint, win, fact, steps)


LEVELS = [
    # ===== ZONE 1: THE WORKSHOP =====
    level("Blackout Lantern", "gio", (5.0, 12), "The power's out! Wire a little lantern so we can see.",
          "Light restored! You saved the workshop!",
          "A resistor limits the current so the LED doesn't burn out.", ["resistor", "led:red"]),
    level("Gatekeeper's Signal", "silas", (5.0, 12), "Press a button to light up my signal lamp!",
          "Signal working! Silas is impressed.",
          "A push button only connects the circuit while you hold it down.", ["button", "resistor", "led:green"]),
    level("Watchtower Lamp", "gio", (5.0, 11), "A DIP switch stays ON after you flip it. Build a lamp that stays lit!",
          "Click! The watchtower lamp stays on.",
          "A DIP switch is a row of tiny switches. Each one stays ON until you flip it back.",
          ["dip", "resistor", "led:yellow"]),
    # ===== ZONE 2: THE LAB =====
    level("Safety Lock", "vex", (5.0, 12), "Lab rule: the burner light only works if the SAFETY switch is on AND you press go!",
          "Click... press... it lights! Safe AND working.",
          "Two switches in a row = AND: power only gets through when BOTH are on. Real machines use this for safety.",
          ["dip", "button", "resistor", "led:red"]),
    level("Door Bypass Split", "vex", (5.0, 24), "Split the power into two paths (that's parallel) to open the vault!",
          "Parallel split complete! Vault doors open.",
          "In parallel, each path gets the full power and works on its own. Each LED gets its own resistor.",
          ["button"], ["resistor", "led:white"], ["resistor", "led:green"]),
    pot_level("Alarm Dimmer", "gio", (3.0, 6), "The alarm light is way too bright. Add a slide pot to dim it!",
              "Ahh, much softer. Smooth dimming!",
              "The slide pot splits the power: the slider decides how much comes out of the middle pin.", "blue"),
    # ===== ZONE 3: MOTOR TOWER =====
    level("Buzz Pager", "master", (5.0, 70), "The core is rumbling! Build a button pager that buzzes.",
          "Bzzzt! Emergency pager working!",
          "A vibe motor spins a lopsided weight. That wobble is the buzz you feel!", ["button", "vibe"]),
    level("Coolant Pump", "master", (5.0, 90), "Overheat! Wire a coolant pump you can switch on and leave running.",
          "Glug glug! Coolant is flowing - the core is cooling down!",
          "Pumps are just DC motors spinning a little propeller that pushes liquid along.", ["dip", "motor"]),
    level("Master Reactor Control", "master", (5.0, 24), "Build a control panel: one switch, two lights on two paths!",
          "REACTOR STABLE! Motor Tower is clear!",
          "One switch BEFORE the split controls both paths at once.",
          ["dip"], ["resistor", "led:red"], ["resistor", "led:green"]),
    # ===== ZONE 4: SENSOR WING =====
    level("Laser Tripwire", "pixel", (5.0, 25), "BEEP. The security lasers are dead. Wire one up with a button!",
          "PEW! Laser online. I can see again!",
          "A laser makes a super-narrow beam of light that travels in a perfectly straight line.",
          ["button", "laser"]),
    level("Laser Grid", "pixel", (5.0, 25), "BEEP. Now make a laser that stays on with a DIP switch.",
          "Laser grid active. Security restored.",
          "Real laser security systems sound an alarm when someone blocks the beam!", ["dip", "laser"]),
    level("Laser Alarm", "pixel", (5.0, 37), "BEEP. Laser AND a red warning light, each on its own path!",
          "Laser alarm fully operational. Excellent, human.",
          "Parallel paths let the laser and the LED both run at the same time.",
          ["dip"], ["laser"], ["resistor", "led:red"]),
    # ===== ZONE 5: CONTROL ROOM =====
    level("Hatch Motor", "ada", (5.0, 90), "The hatch motors are dead. Press a button to spin a DC motor!",
          "Vrrrm! The motor spins!",
          "A DC motor spins when current flows through it. Motors need lots of current, so no resistor here.",
          ["button", "motor"]),
    level("Reverse Gear", "ada", (5.0, 90), "The hatch is opening the WRONG way! Make the motor spin backwards.",
          "Perfect! Now it spins the other way. Hatch closing!",
          "Swap which side of a DC motor gets + and it spins the other direction. Toy cars use this to reverse!",
          ["button", "motor:rev"],
          tips={"motor": ["Add the DC motor again - but this time we flip it around!",
                          "Last time its RED wire went toward the + side. This time we swap the two wires around.",
                          "Same motor, power flipped: it'll spin the opposite way. That's how a reverse gear works!"]}),
    level("Escape Hatch Override", "ada", (5.0, 100), "Big one! A green light AND the hatch motor, on separate paths.",
          "OVERRIDE ACCEPTED! The way to the roof is open!",
          "You've used series, parallel, switches, motors and lasers. That's real engineering!",
          ["dip"], ["resistor", "led:green"], ["motor"]),
    # ===== ZONE 6: GREENHOUSE =====
    level("Grow Light Timer", "flora", (5.0, 12), "Grow lights only come on when it's DAYTIME and the SEASON switch is on!",
          "Perfect - the seedlings are basking!",
          "Two switches on one DIP block, joined in a row: flip BOTH on or nothing happens. That's an AND circuit!",
          ["dip:2", "resistor", "led:white"]),
    level("Sprinkler & Mister", "flora", (5.0, 160), "One switch: the sprinkler pump AND the buzzing mister, each on its own path!",
          "Psshhh! Bzzz! The plants are drinking AND misty!",
          "Two motors in parallel each get the full power, so neither one slows the other down.",
          ["dip"], ["motor"], ["vibe"]),
    level("Party Bass & Lights", "flora", (5.0, 82), "Party time! A buzzing bass shaker AND a blue light, each on its own path.",
          "Party ON! The whole greenhouse is dancing!",
          "Parallel paths are why one broken bulb doesn't turn off the whole house.",
          ["dip"], ["vibe"], ["resistor", "led:blue"]),
    # ===== ZONE 7: THE ROOFTOP =====
    level("Storm Alarm", "skye", (5.0, 70), "The storm's getting worse! Build a buzzing alarm you can switch on.",
          "Bzzzt! The storm alarm is on!",
          "The vibe motor buzzes until you flip the DIP switch back off.", ["dip", "vibe"]),
    level("Signal Laser", "skye", (5.0, 95), "Signal the chopper: one button fires a laser AND buzzes a pager!",
          "PEW! Bzzt! The chopper saw the signal!",
          "Two paths from one button: press once, and both parts turn on together.",
          ["button"], ["laser"], ["vibe"]),
    level("Rescue Beacon", "skye", (5.0, 37), "Final beacon! ARM it with the DIP switch, then press FIRE: laser AND blue light!",
          "BEACON LIT! The rescue chopper is landing!",
          "AND switches, then a split into two paths - every trick you learned in one circuit. You did it, engineer!",
          ["dip", "button"], ["laser"], ["resistor", "led:blue"]),
]
NQ = len(LEVELS)
NZ = (NQ + PER_ZONE - 1) // PER_ZONE

# SIDE QUESTS: built for real on the breadboard with Gio's step-by-step help, exactly like the story quests.
# Every one is a different circuit from the story. Start them from MENU > QUESTS (they're listed under the story).
SIDE_LEVELS = [
    level("Shop Doorbell", "tess", (5.0, 82), "Customers keep sneaking in! A doorbell button that buzzes AND lights a lamp?",
          "Bzzt! Ding! Now I'll never miss a customer.",
          "Doorbells are just a button and a buzzer. Yours has a light too, on its own path.",
          ["button"], ["vibe"], ["resistor", "led:yellow"]),
    level("Toy Car Headlight", "gio", (5.0, 102), "Let's build a toy car! Press the pedal: the wheels spin AND the headlight turns on.",
          "Vroom! Headlight on. Best car ever.",
          "Real cars run the lights and the motors on separate circuits so one can't stop the other.",
          ["button"], ["motor"], ["resistor", "led:white"]),
    level("Library Laser Fence", "page", (5.0, 95), "Someone keeps moving my books! A laser fence with a buzzer, switched on for the night.",
          "Shhh... the laser fence is armed. Thank you!",
          "Museums protect paintings with invisible laser beams that set off an alarm.",
          ["dip"], ["laser"], ["vibe"]),
    level("Secret Knock", "riddle", (5.0, 70), "Riddle me this: a buzzer that ONLY works if you know the secret switch first!",
          "Bzzzt! You cracked my secret knock!",
          "Secret switch AND button = a tiny lock. Safes and car keys use the same AND idea.",
          ["dip", "button", "vibe"]),
    level("Disco Spinner", "bolt", (5.0, 115), "BEEP! Make a disco: a spinning motor AND a laser beam, both on one switch!",
          "BEEP BOOP! Dance party protocol activated!",
          "Disco lights spin a motor so the beam sweeps around the room.",
          ["dip"], ["motor"], ["laser"]),
    level("Double-Check Winch", "silas", (5.0, 90), "The loading winch is dangerous. Make it need TWO switches on before it moves.",
          "Both switches, then it winds. Nice and safe!",
          "Big machines often need two buttons pressed at once so nobody's hand is in the way.",
          ["dip:2", "motor"]),
    level("Reverse Winch", "vex", (5.0, 90), "Now unwind it! A winch that turns BACKWARDS when you switch it on.",
          "Unwinding perfectly. You're a natural, Jaslyne!",
          "Cranes use reversing motors to lift loads up and lower them back down.",
          ["dip", "motor:rev"],
          tips={"motor": ["Add the DC motor - flipped around this time!",
                          "Its BLACK wire goes toward the + side and its RED wire toward the -. That's the swap.",
                          "Same motor, power flipped: it spins the other way and the winch unwinds."]}),
]
NS = len(SIDE_LEVELS)
SIDE_REWARD = 12
LEVELS.extend(SIDE_LEVELS)   # quest number NQ + i is side quest i (the story code only ever looks at 0..NQ-1)


# ---------------- endless JOBS: a fresh real-breadboard circuit every time, the main way to earn Bolts ----------------
QJOB_COLORS = ["red", "green", "blue", "yellow", "white"]
QJOB_MA = dict(led=12, motor=90, rev=90, vibe=70, laser=25)
QJOB_SWITCH = {   # parts at the start of the row + how the customer describes it
    "button": (["button"], "that runs while you hold a button"),
    "dip": (["dip"], "that you can switch on and leave running"),
    "and": (["dip", "button"], "that only works when the safety switch is on AND you press go"),
    "andand": (["dip:2"], "that needs TWO switches on the DIP block flipped on before it works"),
    "and3": (["dip:3"], "that only works when ALL THREE switches on the DIP block are on"),
}
QJOB_THINGS = {
    "led": ["reading lamp", "night light", "warning light", "signal lamp", "porch light", "status light", "sign",
            "beacon", "glow marker", "lantern", "indicator", "mood light", "spotlight", "path light"],
    "motor": ["conveyor belt", "spinning display", "little drill", "winch", "turntable", "paint mixer", "spinning sign",
              "pinwheel", "mini crane", "wheel", "stirrer", "rotating stage", "propeller", "spinner toy"],
    "vibe": ["buzzer", "phone buzzer", "alarm shaker", "doorbell buzzer", "wake-up buzzer", "rattle alarm",
             "shaker", "tickle machine", "rumble signal", "jiggle alert"],
    "laser": ["laser pointer", "laser tripwire", "laser show", "laser level", "laser beacon", "laser fence",
              "laser guide", "laser target", "laser sight", "laser marker"],
}
QJOB_THINGS["rev"] = QJOB_THINGS["motor"]
QJOB_STORIES = {   # 8 little problems per character - every one is different
    "tess": ["A raccoon snuck into my shop last night and chewed through half my displays!",
             "I'm opening a night-market stall and it needs to stand out in the dark.",
             "My old counter gadgets finally gave up. I'm replacing the whole setup!",
             "A customer wants a gift that 'does something cool', and I promised one by tonight.",
             "The shop window looks so boring. Help me make it eye-catching!",
             "I keep dozing off at the counter on slow days. I need something to keep me alert.",
             "My delivery robot quit, so now I'm building gadgets for customers myself!",
             "It's the shop's birthday tomorrow and I want a little surprise for everyone."],
    "page": ["A book fell off the top shelf and nearly hit a reader. We need better warnings up there.",
             "Someone keeps returning books after closing. I want to know when they sneak in!",
             "The reading nook is far too dark for the night owls.",
             "I'm running a kids' science story hour and I need a demo for the big finale.",
             "The old archive room needs gentle gadgets - nothing loud, nothing hot.",
             "My bookmark-sorting machine broke, so I'm rebuilding it piece by piece.",
             "A pigeon flew in through the window and now it lives on the encyclopedias.",
             "The library is hosting a midnight reading party and the main lights are on a timer."],
    "riddle": ["What has no legs but runs, and no mouth but hums? Your next build!",
               "I hid a treasure in the arcade, but my clue machine needs a new part.",
               "Riddle: I only wake up when the secret is right. Build me something like that!",
               "My puzzle box lost its prize mechanism. Can you make a new one?",
               "The arcade's haunted-house game needs a spooky new gadget.",
               "Players keep cheating at my riddle booth. Time for a new contraption!",
               "I bet you can't build this one. Prove me wrong!",
               "The prize counter needs something flashy for tonight's winners."],
    "bolt": ["BEEP! Bolt unit 7 lost its blinker in a hallway collision. Repair needed!",
             "BEEP BOOP! Robot dance-off tonight. Bolt requires upgrades!",
             "BEEP! The charging station is impossible to find in the dark.",
             "BOOP. Bolt is lonely. Request: one gadget friend.",
             "BEEP! The hallway speed bumps need warning signals.",
             "BEEP. Bolt dropped a sandwich into its own gears. Do not ask.",
             "BEEP BEEP! A new robot is being built. It needs its very first part!",
             "BOOP! Bolt is practicing to be a lighthouse. Assistance required."],
    "silas": ["The workshop's back door sticks and nobody hears deliveries arrive.",
              "I'm teaching the new interns tomorrow and I need a perfect example circuit.",
              "My old toolbox fell apart, so I'm rebuilding my bench gadgets one by one.",
              "Someone left the paint shelf open again and it got everywhere!",
              "The forklift alarm broke, and safety comes first in my workshop.",
              "I promised my nephew I'd build him something cool for his birthday.",
              "The storage room is a maze. We need signals to find our way around.",
              "Power's stable now, so I'm finally upgrading the old junk-bin machines."],
    "vex": ["My notebook says 'experiment 47: inconclusive'. Let's try again with your help!",
            "The hamster-wheel generator retired. I need a new demo for my class.",
            "I'm writing a paper on clever circuits and I need a real one to photograph.",
            "One of my beakers glows and I'm not sure why. Let's build a safer light.",
            "A visiting scientist is coming tomorrow and I want to show off a little.",
            "I keep mixing up which experiment is running. I need indicators!",
            "The fume-hood timer broke. Back to basics with a hand-built control!",
            "I dreamed about a circuit last night. Let's see if it works in real life!"],
    "flora": ["A snail parade is crawling across the seedling trays tonight. Ugh.",
              "My cactus collection is sulking. Maybe a new gadget will cheer them up.",
              "The tomato vines climbed so fast they knocked over my old gadget.",
              "Bees keep getting lost inside the greenhouse. They need a guide.",
              "I'm entering the flower show and my display has to be unforgettable.",
              "The night-blooming flowers open at midnight and I always miss it!",
              "My compost bin needs stirring and my arms are so tired.",
              "Rain is coming and someone needs to keep an eye on the vents."],
    "skye": ["Clouds rolling in from the west - the helipad needs to be easy to see.",
             "A family of seagulls moved onto the roof. They need to stay off the landing zone.",
             "I'm practising night landings and I need markers I can control.",
             "The weather vane spins, but nobody can see it from the ground.",
             "Fog alert! The roof hatch is really hard to find.",
             "My radio died, so I'm going old-school with signals.",
             "There's a rooftop garden party tonight and the roof needs some sparkle.",
             "A kite got tangled on the antenna. I need a way to warn people up here."],
    "ada": ["MAX keeps forgetting which systems are on. He needs clear indicators.",
            "The control-room chairs keep rolling into the wrong panel. We need signals!",
            "I'm designing a backup panel in case the storm hits again.",
            "MAX asked for a 'toy'. I think he's bored. Let's make him one.",
            "One of the terminals boots up silently and nobody ever notices.",
            "I'm teaching MAX the difference between series and parallel. Visual aid needed!",
            "The night shift wants a gadget that tells them when the coffee's ready.",
            "We're testing MAX's new memory. He needs something to remember!"],
    "pixel": ["BEEP. A moth keeps setting off the motion sensor. New gadget required.",
              "BEEP. Sensor Wing inventory: one missing alarm. Build a replacement.",
              "PROCESSING... I would like to see something beautiful. Request accepted?",
              "BEEP. Security drill at 0900. Prepare a test device.",
              "BEEP. My left camera is blurry. I need a clear reference point.",
              "BEEP BOOP. Calibration day. Every sensor needs a test signal.",
              "BEEP. Unknown object in the hallway. It was a sock. Upgrade anyway.",
              "BEEP. I am learning jokes. Build something funny. Ha. Ha."],
    "master": ["The tower's stairwell is pitch dark between floors.",
               "Steam pipe three keeps hissing. We need a warning setup there.",
               "I'm retiring the ancient controls on floor two. Modern replacements, please!",
               "The service lift to the top floor needs a call signal.",
               "Mice in the basement again. Something to shoo them away, gently!",
               "The tower's anniversary is coming. Let's build a little monument gadget.",
               "My reading glasses broke and the gauges are tiny. Make it obvious!",
               "The night watchman wants a way to signal me without shouting."],
    "gio": ["Okay, idea: what if we built Canica a gadget she can't knock over?",
            "Gummy keeps napping on my charger. We need a gentle wake-up signal.",
            "Sofia barks at the mail carrier every day. Let's build a 'mail's here!' signal instead.",
            "Lafufu's tank needs some ambiance. Nothing too bright for her!",
            "I want to surprise you with something for our movie night.",
            "Remember our first date? Let's build something just as cute.",
            "Let's make a gadget for our future house. Practice run!",
            "I bet I can guess what this circuit does before you finish building it."],
}
QJOB_TWISTS = ["No pressure, but it's kind of urgent!", "Take your time - quality over speed.",
               "Bonus points if it works on the first try!", "Everyone's going to be so impressed.",
               "I'll owe you one, seriously.", "If this works, I'm telling the whole building.",
               "Don't tell anyone - it's a surprise!", "I'd do it myself, but you're way better at this.",
               "I already bought snacks to celebrate.", "I believe in you!"]
QJOB_DETAILS = ["Oh, and it's for tonight.", "It has to fit on one breadboard.", "I sketched it on a napkin, but you'll do it better.",
                "Gio said you're the best builder in the building.", "I've been waiting all week for this.",
                "My last one broke after a day, so make it sturdy!", "I tried YouTube tutorials. Didn't help.",
                "It's a gift, so make it extra neat.", "MAX recommended you personally.",
                "Even Bolt couldn't figure this one out.", "It's my first time asking for help, be gentle.",
                "Pixel already ran the numbers - it should work!"]
QJOB_WINS = ["Perfect! Here are your Bolts.", "Works like a charm - thank you!", "Amazing! You're the best engineer here.",
             "Yes! That's exactly what I needed.", "Wow, first try? Here, take these Bolts!",
             "You're a legend. Seriously.", "I'm going to show this to everyone!"]
QJOB_FACTS = {
    "and": "Two switches in a row = AND: both have to be on. Real machines use this so they can't start by accident.",
    "andand": "Two switches joined in a row only let power through when BOTH are flipped on.",
    "and3": "Three switches in a row = power only gets through when all three are on. Like a 3-part combination lock!",
    "par": "Parallel paths each get the full power, so every part works on its own.",
    "rev": "Swap a DC motor's wires and it spins the other way - that's how reverse gears work.",
    "pot": "The slide pot's middle pin gives out more or less power depending on where the knob is.",
    "led": "LEDs only work one way round - the long leg goes toward +. The resistor keeps them from burning out.",
    "motor": "DC motors spin when current flows through them. They need lots of current, so no resistor.",
    "vibe": "A vibe motor spins a lopsided weight. That wobble is the buzz you feel in a phone.",
    "laser": "A laser beam is so narrow and straight it can measure distances to the Moon.",
}


def _all_job_circuits():
    """Every different circuit a job can be (about 170). Each is (switch, load list); switch None = slide-pot dimmer."""
    singles = [("led", c) for c in QJOB_COLORS] + [("motor", None), ("rev", None), ("vibe", None), ("laser", None)]
    items = [("led", c) for c in QJOB_COLORS] + [("motor", None), ("vibe", None), ("laser", None)]
    pairs = [(a, b) for i, a in enumerate(items) for b in items[i + 1:]]
    out = [(None, [("led", c)]) for c in QJOB_COLORS]
    for sw in QJOB_SWITCH:
        out += [(sw, [ld]) for ld in singles] + [(sw, list(pr)) for pr in pairs]
    return out


QJOB_CIRCUITS = _all_job_circuits()


def _job_sig(circ):
    sw, loads = circ
    return "%s:%s" % (sw or "pot", "+".join("%s-%s" % (k, c) if c else k for k, c in loads))


def _art(words):
    return ("an " if words[0] in "aeiou" else "a ") + words


def make_quest_job(seed, used_sigs=(), used_stories=()):
    """One guided job: a circuit she hasn't built yet + a story she hasn't heard yet."""
    r = random.Random(seed)
    used_sigs, used_stories = list(used_sigs), set(used_stories)
    fresh = [c for c in QJOB_CIRCUITS if _job_sig(c) not in used_sigs]
    if not fresh:   # built every single circuit! reuse the ones from longest ago
        old = set(used_sigs[-20:])
        fresh = [c for c in QJOB_CIRCUITS if _job_sig(c) not in old]
    sw, loads = r.choice(fresh)
    problems = [(g, i) for g in sorted(QJOB_STORIES) for i in range(len(QJOB_STORIES[g]))]
    # a problem she has never heard first; once she's heard all 96, any problem (with a new detail + ending)
    heard = {"-".join(k.split("-")[:2]) for k in used_stories}
    brand_new = [pr for pr in problems if "%s-%d" % pr not in heard]
    giver, si = r.choice(brand_new or problems)
    # the extra detail + the ending: whichever she's heard the least, so they keep rotating too.
    # 96 problems x 12 details x 10 endings = 11,520 different stories before any exact repeat.
    def least(pool, pos):
        counts = [sum(1 for k in used_stories if k.split("-")[pos:pos + 1] == [str(i)]) for i in range(len(pool))]
        low = min(counts)
        return r.choice([i for i in range(len(pool)) if counts[i] == low])
    di, ti = least(QJOB_DETAILS, 2), least(QJOB_TWISTS, 3)
    for _ in range(50):   # never the exact same story twice
        sid = "%s-%d-%d-%d" % (giver, si, di, ti)
        if sid not in used_stories:
            break
        di, ti = r.randrange(len(QJOB_DETAILS)), r.randrange(len(QJOB_TWISTS))
    story = " ".join((QJOB_STORIES[giver][si], QJOB_DETAILS[di], QJOB_TWISTS[ti]))
    win = r.choice(QJOB_WINS)
    names = []
    for k, c in loads:
        thing = r.choice(QJOB_THINGS[k])
        names.append(_art("%s %s" % (c, thing)) if c else _art(thing))
    if sw is None:   # slide-pot dimmer
        color = loads[0][1]
        L = pot_level("Dimmable " + names[0].split(" ", 1)[1].title(), giver, (3.0, 6),
                      "So I need %s you can dim with a slide pot!" % names[0], win, QJOB_FACTS["pot"], color)
        reward = 10
    else:
        first, sw_text = QJOB_SWITCH[sw]
        rows = []
        for k, c in loads:
            rows.append(["resistor", "led:" + c] if k == "led" else ["motor:rev"] if k == "rev" else [k])
        mA = sum(QJOB_MA[k] for k, _ in loads)
        tips = None
        if any(k == "rev" for k, _ in loads):
            tips = {"motor": ["Add the DC motor - flipped around this time!",
                              "Its BLACK wire goes toward the + side and its RED wire toward the -.",
                              "Same motor, power flipped: it spins the other way."]}
        if len(loads) == 1:
            k = loads[0][0]
            title = names[0].split(" ", 1)[1].title()
            hint = "So I need %s %s%s." % (names[0], sw_text, " - spinning BACKWARDS" if k == "rev" else "")
            fact = QJOB_FACTS[sw if sw in ("and", "andand", "and3") else k]
            L = level(title, giver, (5.0, mA), hint, win, fact, first + rows[0], tips=tips)
            reward = 8 + (3 if sw in ("and", "andand") else 5 if sw == "and3" else 0) + (2 if k == "rev" else 0)
        else:
            title = "%s & %s" % (names[0].split(" ", 1)[1].title(), names[1].split(" ", 1)[1].title())
            hint = "So I need %s AND %s, each on its own path, %s." % (names[0], names[1], sw_text)
            fact = QJOB_FACTS["par"] if sw in ("button", "dip") else QJOB_FACTS[sw]
            L = level(title, giver, (5.0, mA), hint, win, fact, first, rows[0], rows[1])
            reward = 12 + (3 if sw in ("and", "andand") else 5 if sw == "and3" else 0)
    L.update(reward=reward, sig=_job_sig((sw, loads)), story=story, sid=sid)
    return L


JOB_SLOT = len(LEVELS)            # the current job always lives in this quest slot
LEVELS.append(make_quest_job(1))       # placeholder until the first real job is made


def zone_done(done, z):
    return sum(1 for q in range(z * PER_ZONE, min(NQ, z * PER_ZONE + PER_ZONE)) if q in done)


def quest_reward(q):
    return 8 + 2 * (q // PER_ZONE)


# ---------------- board rendering ----------------
_cache = {}


def board_img(i, step, gold=False):
    key = (i, step, gold)
    if key not in _cache:
        steps = LEVELS[i]["steps"]
        png = os.path.join(CIRCUIT_DIR, "level%d.png" % (i + 1))
        if step >= len(steps) and os.path.exists(png):
            _cache[key] = (Image.open(png).convert("RGB").resize((BW, BH)), None, False)
        else:
            im = make_board()
            d = ImageDraw.Draw(im)
            for st in steps[:step]:
                draw_art(d, st["items"], gold)
            bbox = None
            if step > 0:
                layer = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
                draw_art(ImageDraw.Draw(layer), steps[step - 1]["items"], gold)
                bbox = layer.getbbox()
            _cache[key] = (im, bbox, True)
    return _cache[key]


def wire_paths(li, step):
    segs = []
    for st in LEVELS[li]["steps"][:step]:
        for it in st["items"]:
            if it[0] in ("wire", "trace") and it[1] != it[2]:
                segs.append((it[1], it[2]))
    return segs


def electrons(d, segs, now, color=(255, 240, 120), r=2, speed=0.8):
    for n, (a, b) in enumerate(segs):
        for k in range(2):
            t = (now * speed + n * 0.17 + k * 0.5) % 1.0
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            d.ellipse([x - r, y - r, x + r, y + r], fill=color)


def draw_motor_spin(d, x, y, now):
    """Spinning disc on the motor shaft."""
    a = now * 12
    d.ellipse([x + 13, y - 6, x + 21, y + 6], outline=(255, 220, 120))
    d.line([(x + 17 + 4 * math.cos(a), y + 6 * math.sin(a)), (x + 17 - 4 * math.cos(a), y - 6 * math.sin(a))],
           fill=YELLOW, width=2)


def draw_laser_beam(d, x, y, now):
    """Red beam shooting up-right out of the lens."""
    flick = 1 + int(now * 20) % 2
    d.line([(x + 13, y - 1), (x + 34, y - 22)], fill=(255, 60, 60), width=flick + 1)
    d.line([(x + 13, y - 1), (x + 34, y - 22)], fill=(255, 200, 200), width=1)
    d.ellipse([x + 31, y - 25, x + 37, y - 19], fill=(255, 120, 120))


def animate_board(li, step, state, now, gold=False):
    board, bbox, synth = board_img(li, step, gold)
    im = board.copy()
    if not synth:
        return im, bbox
    d = ImageDraw.Draw(im)
    live = state == "win"
    if live:
        electrons(d, wire_paths(li, step), now)
    for st in LEVELS[li]["steps"][:step]:
        for it in st["items"]:
            k = it[0]
            if k == "led" and live:
                x, y = it[1], it[2]
                base = LED_COL[it[3] if len(it) > 3 else "red"]
                pr = 11 + int((math.sin(now * 5) + 1) * 3)
                for rr, col in ((pr + 6, tuple((c + 255) // 2 for c in base)),
                                (pr, tuple(min(255, c + 90) for c in base))):
                    d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=col)
                d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=tuple(min(255, c + 50) for c in base))
            elif k == "fan" and live:
                draw_fan(d, it[1], it[2], now * 9)
            elif k == "motor" and live:
                draw_motor_spin(d, it[1], it[2], -now if len(it) > 3 and it[3] == "rev" else now)
            elif k == "laser" and live:
                draw_laser_beam(d, it[1], it[2], now)
            elif k == "vibe" and live:
                x, y = it[1], it[2]
                for j in range(2):
                    rr = 18 + ((now * 10 + j * 5) % 11)
                    d.arc([x - rr, y - rr, x + rr, y + rr], -30, 30, fill=ORANGE)
                    d.arc([x - rr, y - rr, x + rr, y + rr], 150, 210, fill=ORANGE)
            elif k == "buzzer" and live:
                x, y = it[1], it[2]
                for j in range(3):
                    rr = 14 + ((now * 14 + j * 6) % 18)
                    d.arc([x - rr, y - rr, x + rr, y + rr], -45, 45, fill=YELLOW)
            elif k == "ldr" and live:
                x, y = it[1], it[2]
                for j in range(8):
                    a = j * math.pi / 4 + now
                    d.line([(x + 14 * math.cos(a), y - 24 + 14 * math.sin(a)),
                            (x + 19 * math.cos(a), y - 24 + 19 * math.sin(a))], fill=YELLOW)
                d.ellipse([x - 8, y - 32, x + 8, y - 16], fill=YELLOW)
    label_board(d, LEVELS[li]["steps"][:step], highlight_last=not live)
    return im, bbox


# ---------------- characters ----------------
BASE_DOWN = [
    "................", "....KKKKKKKK....", "...KHHHHHHHHK...", "..KHHHHHHHHHHK..",
    "..KHHSSSSSSHHK..", "..KHSSSSSSSSHK..", "..KHSESSSSESHK..", "..KHSSSSSSSSHK..",
    "...KKSSMMSSKK...", "....KWWWWWWK....", "...KWWWWWWWWK...", "..KSKWWWWWWKSK..",
    "..KSKWWWWWWKSK..", "...KKPPPPPPKK...", "....KPPKKPPK....", "....KFFK.KFFK...",
]
BASE_UP = BASE_DOWN[:4] + ["..KHHHHHHHHHHK.."] * 4 + ["...KKHHHHHHKK..."] + BASE_DOWN[9:]
BASE_SIDE = [
    "................", "....KKKKKKK.....", "...KHHHHHHHK....", "..KHHHHHHHHHK...",
    "..KHHHHHHSSSK...", "..KHHHHHSSSSK...", "..KHHHHSSSESK...", "..KHHHHSSSSSK...",
    "...KKHHSSMSKK...", "....KWWWWWWK....", "...KWWWWWWWWK...", "....KWWWWSSK....",
    "....KWWWWSSK....", "....KKPPPPKK....", "....KPPPPPPK....", "....KFFFFFFK....",
]
# Jaslyne's own sprite: long dark-brown hair past her shoulders, brown eyes, pink lips, gold necklace (L)
JAS_DOWN = [
    "................", "....KKKKKKKK....", "...KHHHHHHHHK...", "..KHHHHHHHHHHK..",
    "..KHHHSSSSHHHK..", ".KHHSSSSSSSSHHK.", ".KHHSESSSSESHHK.", ".KHHSSSSSSSSHHK.",
    ".KHHKSSMMSSKHHK.", ".KHHKWWLLWWKHHK.", ".KHKWWWWWWWWKHK.", ".KHSKWWWWWWKSHK.",
    ".KHSKWWWWWWKSHK.", "..KKKPPPPPPKKK..", "....KPPKKPPK....", "....KFFK.KFFK...",
]
JAS_UP = JAS_DOWN[:4] + ["..KHHHHHHHHHHK.."] + [".KHHHHHHHHHHHHK."] * 6 + \
    [".KHSKHHHHHHKSHK.", ".KHSKWWWWWWKSHK."] + JAS_DOWN[13:]
JAS_SIDE = [
    "................", "....KKKKKKK.....", "...KHHHHHHHK....", "..KHHHHHHHHHK...",
    "..KHHHHHHSSSK...", ".KHHHHHHSSSSK...", ".KHHHHHSSSESK...", ".KHHHHHSSSSSK...",
    ".KHHHHKSSSMK....", ".KHHHKWWLWWK....", ".KHHKWWWWWWWK...", ".KHHKWWWWSSK....",
    "..KHKWWWWSSK....", "....KKPPPPKK....", "....KPPPPPPK....", "....KFFFFFFK....",
]
JAS_LOOK = dict(H=(52, 32, 24), S=(236, 190, 160), E=(60, 34, 24), M=(214, 90, 100), L=(240, 190, 60), _style="jas")
BASE_PAL = {"K": (12, 12, 24), "E": (20, 20, 40), "M": (170, 90, 80), "F": (240, 240, 245),
            "H": (25, 25, 35), "S": (232, 172, 128), "W": (245, 245, 245), "P": (60, 60, 80)}


def sprite_from_rows(rows, pal, scale=1):
    hh, ww = len(rows), len(rows[0])
    im = Image.new("RGBA", (ww, hh), (0, 0, 0, 0))
    px = im.load()
    for y in range(hh):
        for x in range(ww):
            c = rows[y][x]
            if c in pal:
                px[x, y] = tuple(pal[c]) + (255,)
    if scale != 1:
        im = im.resize((ww * scale, hh * scale), Image.NEAREST)
    return im


_frame_cache = {}


def char_frames(pal_over):
    key = tuple(sorted(pal_over.items()))
    if key in _frame_cache:
        return _frame_cache[key]
    pal = dict(BASE_PAL)
    pal.update(pal_over)

    def walk(rows, side=False):
        a, b = list(rows), list(rows)
        if side:
            a[15] = "...KFFFK.KFFK..."
            b[15] = "....KFFK.KFFFK.."
        else:
            a[15] = "....KFFK........"
            b[15] = ".........KFFK..."
        return [rows, a, b]

    out = {}
    sets = ((JAS_DOWN, JAS_UP, JAS_SIDE) if pal_over.get("_style") == "jas" else (BASE_DOWN, BASE_UP, BASE_SIDE))
    for name, rows, side in (("down", sets[0], False), ("up", sets[1], False), ("right", sets[2], True)):
        out[name] = [sprite_from_rows(r, pal) for r in walk(rows, side)]
    out["left"] = [ImageOps.mirror(s) for s in out["right"]]
    _frame_cache[key] = out
    return out


CHAR_DEFS = {
    "jas": dict(name="Jaslyne", W=(245, 245, 245), P=(60, 60, 80), **JAS_LOOK),
    "gio": dict(name="Gio", H=(32, 30, 48), S=(232, 172, 128), W=(245, 245, 245), P=(60, 80, 150)),
    "silas": dict(name="Silas", H=(170, 170, 180), S=(205, 150, 110), W=(50, 110, 70), P=(60, 60, 70)),
    "vex": dict(name="Dr. Vex", H=(160, 70, 210), S=(235, 190, 160), W=(238, 240, 250), P=(50, 50, 70)),
    "master": dict(name="Master Builder", H=(250, 200, 30), S=(215, 160, 120), W=(235, 120, 30), P=(40, 60, 110)),
    "pixel": dict(name="Pixel", H=(90, 100, 125), S=(175, 185, 200), W=(60, 200, 230), P=(90, 95, 110), E=(60, 240, 255)),
    "ada": dict(name="Cmdr Ada", H=(225, 225, 235), S=(190, 140, 110), W=(200, 50, 70), P=(40, 40, 60)),
    "tess": dict(name="Tess", H=(190, 70, 150), S=(235, 185, 150), W=(120, 80, 180), P=(70, 50, 100)),
    "flora": dict(name="Flora", H=(120, 70, 40), S=(225, 170, 130), W=(90, 170, 80), P=(80, 60, 40)),
    "skye": dict(name="Pilot Skye", H=(240, 190, 90), S=(200, 150, 110), W=(60, 90, 160), P=(50, 50, 60)),
    "max": dict(name="M.A.X.", K=(20, 20, 30), H=(60, 64, 80), S=(40, 170, 230), W=(90, 96, 115), P=(60, 64, 80),
                E=(255, 70, 70), M=(255, 70, 70), F=(60, 64, 80)),
    "page": dict(name="Ms. Page", H=(110, 60, 30), S=(230, 180, 140), W=(120, 40, 60), P=(40, 40, 60)),
    "riddle": dict(name="Riddle", H=(140, 60, 220), S=(190, 200, 215), W=(60, 60, 80), P=(100, 100, 120), E=(255, 80, 200)),
    "bolt": dict(name="Bolt", H=(240, 200, 40), S=(200, 205, 215), W=(240, 200, 40), P=(120, 120, 130), E=(60, 240, 255)),
}


def pal_of(key):
    return {k: v for k, v in CHAR_DEFS[key].items() if k != "name"}


_portraits = {}


def portrait(key):
    if key not in _portraits:
        if key in PETS:
            _portraits[key] = pet_sprite(key, "down", 0).crop((0, 0, 16, 13)).resize((42, 33), Image.NEAREST)
        else:
            fr = char_frames(pal_of(key))["down"][0].crop((1, 1, 15, 12))
            _portraits[key] = fr.resize((14 * 3, 11 * 3), Image.NEAREST)
    return _portraits[key]


# ---------------- the pets: Canica, Gummy, Sofia and Lafufu ----------------
PETS = {"canica", "gummy", "sofia", "lafufu"}
PET_NAMES = {"canica": "Canica", "gummy": "Gummy", "sofia": "Sofia", "lafufu": "Lafufu"}
PET_TALK = {
    "canica": [[("canica", "Yip! Yip yip!"), ("jas", "Canica! Who's the tiniest, cutest girl? You are!")],
               [("canica", "*stares up at you with huge shiny eyes*"), ("jas", "Okay okay, you can have a treat.")],
               [("canica", "*does a happy little spin*"), ("jas", "Hehe, I missed you too, Canica.")]],
    "gummy": [[("gummy", "Woof!"), ("jas", "Gummy! Hi, big guy!")],
              [("gummy", "*flops over for belly rubs*"), ("jas", "Such a big softie. Good boy, Gummy.")],
              [("gummy", "*gives you the big sad puppy eyes*"), ("jas", "You're not fooling anyone, Gummy... fine, a treat.")]],
    "sofia": [[("sofia", "Arf! Arf!"), ("jas", "Sofia! Look at that fluffy face!")],
              [("sofia", "*wiggles her whole body, tail going crazy*"), ("jas", "Hi Sofia! Yes, hi, hi!")],
              [("sofia", "*tilts her scruffy little head*"), ("jas", "What are you thinking about, Sofia? Snacks?")]],
    "lafufu": [[("lafufu", "*blub blub*"), ("jas", "Hi Lafufu! Your fins look extra fancy today.")],
               [("lafufu", "*flares her big blue and red fins*"), ("jas", "Show-off. I love you, Lafufu.")],
               [("lafufu", "*swims a little loop-de-loop*"), ("jas", "Whoa! Nice moves, Lafufu.")]],
}
_pet_cache = {}


def pet_sprite(key, face, frame):
    """Little pixel versions of the real pets (2 frames each; left/right is mirrored)."""
    ck = (key, face in ("left", "right"), frame)
    if ck in _pet_cache:
        im = _pet_cache[ck]
    else:
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        bob = frame % 2
        side = face in ("left", "right")
        if key == "lafufu":   # Lafufu's tank, with Lafufu swimming in it
            d.rectangle([0, 3, 15, 15], fill=(60, 60, 70))
            d.rectangle([1, 4, 14, 14], fill=(110, 180, 230))
            d.rectangle([1, 12, 14, 14], fill=(200, 170, 110))
            d.line([(3, 12), (3, 7)], fill=(60, 170, 80))
            d.line([(12, 12), (13, 8)], fill=(60, 170, 80))
            fx = 4 + frame % 3 * 2
            d.polygon([(fx + 4, 8), (fx + 8, 5), (fx + 8, 11)], fill=(210, 40, 60))   # flowing red fins
            d.ellipse([fx, 6, fx + 5, 10], fill=(60, 90, 220))                          # blue body
            d.polygon([(fx + 2, 6), (fx + 5, 3), (fx + 6, 7)], fill=(150, 50, 160))
            d.point((fx + 1, 7), fill=(0, 0, 0))
            d.rectangle([0, 3, 15, 4], fill=(170, 210, 235))
        else:
            if key == "canica":   # fawn chihuahua: tiny body, giant ears, big eyes
                fur, light, dark = (205, 145, 85), (240, 205, 160), (150, 95, 50)
            elif key == "gummy":   # blue-gray bully: big stocky body, white chest
                fur, light, dark = (110, 115, 128), (238, 238, 242), (80, 84, 95)
            else:                  # sofia: Yorkie, dark body with tan face and legs
                fur, light, dark = (50, 50, 60), (195, 150, 100), (30, 30, 36)
            big = key == "gummy"
            y0 = 1 + bob
            # body
            d.ellipse([3 if big else 4, 7 + y0, 13 if big else 12, 14], fill=fur, outline=dark)
            # legs
            legc = light if key in ("sofia", "gummy") else fur
            for lx in ((4, 7, 10, 12) if big else (5, 7, 9, 11)):
                d.rectangle([lx - 1, 13, lx, 15], fill=legc)
            # tail (wags with the frame)
            tx = 13 if not side else 14
            d.line([(tx - 1, 9 + y0), (tx + (1 if frame % 2 else 0), 6 + y0)], fill=fur if key != "sofia" else dark, width=2)
            # head
            hx, hy = (2, y0) if side else (4, y0)
            head = light if key == "sofia" else fur
            d.ellipse([hx, hy + 1, hx + 8, hy + 8], fill=head, outline=dark)
            # ears
            if key == "canica":
                d.polygon([(hx, hy + 3), (hx - 1, hy - 2), (hx + 3, hy + 1)], fill=fur, outline=dark)
                d.polygon([(hx + 8, hy + 3), (hx + 9, hy - 2), (hx + 5, hy + 1)], fill=fur, outline=dark)
            elif key == "gummy":
                d.polygon([(hx + 1, hy + 2), (hx + 1, hy), (hx + 3, hy + 1)], fill=dark)
                d.polygon([(hx + 7, hy + 2), (hx + 7, hy), (hx + 5, hy + 1)], fill=dark)
            else:
                d.polygon([(hx + 1, hy + 3), (hx + 1, hy - 1), (hx + 3, hy + 1)], fill=light, outline=dark)
                d.polygon([(hx + 7, hy + 3), (hx + 7, hy - 1), (hx + 5, hy + 1)], fill=light, outline=dark)
                d.point((hx + 2, hy + 7), fill=(160, 120, 80))   # scruffy beard
                d.point((hx + 6, hy + 7), fill=(160, 120, 80))
            # face
            if key == "gummy":
                d.line([(hx + 4, hy + 2), (hx + 4, hy + 7)], fill=light)   # thin white blaze
                d.rectangle([4 if big else 5, 9 + y0, 7, 12], fill=light)  # white chest
            elif key == "canica":
                d.ellipse([hx + 2, hy + 5, hx + 6, hy + 8], fill=light)
            eye = (15, 10, 10)
            d.point((hx + 2, hy + 4), fill=eye)
            d.point((hx + 6, hy + 4), fill=eye)
            if key == "canica":   # chihuahua eyes are BIG
                d.point((hx + 2, hy + 3), fill=eye)
                d.point((hx + 6, hy + 3), fill=eye)
            d.point((hx + 4, hy + 6), fill=(20, 15, 15))   # nose
        _pet_cache[ck] = im
    if face == "left":
        return ImageOps.mirror(im)
    return im


# ---------------- store catalog ----------------
STORE_ITEMS = [
    dict(type="outfit", id=0, name="Classic Outfit", cost=0, W=(245, 245, 245), P=(60, 60, 80), H=(25, 25, 35), desc="Standard engineer look."),
    dict(type="outfit", id=1, name="Neon Blue Outfit", cost=10, W=(40, 180, 255), P=(30, 50, 120), H=(25, 25, 35), desc="Glows in dark labs!"),
    dict(type="outfit", id=2, name="Rose Pink Outfit", cost=15, W=(255, 100, 180), P=(90, 40, 90), H=(25, 25, 35), desc="Sleek and stylish."),
    dict(type="outfit", id=3, name="Escape Orange", cost=20, W=(255, 140, 30), P=(60, 60, 70), H=(25, 25, 35), desc="The classic prison-break jumpsuit."),
    dict(type="outfit", id=4, name="Shadow Ninja", cost=30, W=(50, 50, 70), P=(30, 30, 45), H=(90, 20, 20), desc="Sneak through the dark halls."),
    dict(type="outfit", id=5, name="Cyber Gold Outfit", cost=45, W=(250, 220, 40), P=(120, 90, 20), H=(255, 240, 150), desc="For master builders."),
    dict(type="outfit", id=6, name="Strawberry Pop", cost=35, W=(240, 70, 90), P=(250, 250, 250), H=(120, 60, 40), desc="Sweet as can be."),
    dict(type="outfit", id=7, name="Mint Chip", cost=40, W=(150, 235, 200), P=(90, 60, 50), H=(60, 40, 30), desc="Cool, fresh and comfy."),
    dict(type="outfit", id=8, name="Galaxy Dream", cost=60, W=(70, 40, 140), P=(20, 20, 60), H=(230, 200, 255), desc="Covered in tiny stars."),
    dict(type="outfit", id=9, name="Royal Engineer", cost=80, W=(130, 30, 60), P=(240, 200, 60), H=(25, 25, 35), desc="For the queen of circuits."),
    dict(type="outfit", id=14, name="Kitty Cutie", cost=25, W=(250, 250, 252), P=(240, 120, 160), H=(52, 32, 24), desc="White and pink with a red bow vibe. So cute!"),
    dict(type="outfit", id=10, name="Bunny Pajamas", cost=100, W=(255, 210, 225), P=(255, 240, 245), H=(90, 60, 50), desc="Cozy study-night pajamas."),
    dict(type="outfit", id=11, name="Cherry Blossom", cost=130, W=(255, 170, 200), P=(120, 60, 90), H=(40, 25, 30), desc="Soft pink petals everywhere."),
    dict(type="outfit", id=12, name="Starlight Gown", cost=170, W=(30, 40, 110), P=(200, 190, 255), H=(250, 240, 200), desc="Sparkles like the night sky."),
    dict(type="outfit", id=13, name="Diamond Engineer", cost=250, W=(200, 245, 255), P=(120, 200, 230), H=(255, 255, 255), desc="The rarest outfit of all."),
    dict(type="outfit", id=20, name="Witchy Purple", cost=30, W=(110, 50, 160), P=(40, 20, 60), H=(52, 32, 24), desc="Spooky and cute. Boo!"),
    dict(type="outfit", id=21, name="Cozy Sweater", cost=30, W=(200, 40, 50), P=(40, 120, 70), H=(52, 32, 24), desc="Holiday knit. So warm!"),
    dict(type="outfit", id=23, name="Red & Gold Robes", cost=35, W=(35, 30, 40), P=(150, 30, 40), H=(52, 32, 24), desc="Brave wizard robes."),
    dict(type="outfit", id=24, name="Green & Silver Robes", cost=35, W=(35, 30, 40), P=(30, 110, 60), H=(52, 32, 24), desc="Clever wizard robes."),
    dict(type="outfit", id=25, name="Blue & Bronze Robes", cost=35, W=(35, 30, 40), P=(40, 70, 160), H=(52, 32, 24), desc="Wise wizard robes."),
    dict(type="outfit", id=26, name="Yellow & Black Robes", cost=35, W=(35, 30, 40), P=(230, 190, 40), H=(52, 32, 24), desc="Loyal wizard robes."),
    dict(type="outfit", id=27, name="Banana Buddy Overalls", cost=30, W=(250, 215, 40), P=(40, 80, 170), H=(52, 32, 24), desc="Yellow shirt, blue overalls. Bello!"),
    dict(type="outfit", id=28, name="Purple Buddy Overalls", cost=30, W=(130, 60, 170), P=(60, 50, 90), H=(52, 32, 24), desc="The mischievous purple version."),
    dict(type="outfit", id=22, name="Sweetheart", cost=30, W=(255, 120, 170), P=(200, 40, 80), H=(52, 32, 24), desc="All hearts. Aww."),
    dict(type="tool", id="multimeter", name="Digital Multimeter", cost=15, desc="Shows volts and current in quests."),
    dict(type="tool", id="flashlight", name="Super Flashlight", cost=20, desc="A much bigger light in dark rooms."),
    dict(type="tool", id="gold_wires", name="Gold Wire Pack", cost=25, desc="Gold wires + 2 bonus Bolts per quest."),
    dict(type="tool", id="boots", name="Speed Boots", cost=30, desc="Walk faster around the facility."),
    dict(type="tool", id="lucky_charm", name="Lucky Charm", cost=35, desc="+1 extra Bolt from every stash you search."),
    dict(type="tool", id="puzzle_specs", name="Puzzle Specs", cost=50, desc="+2 Bolts for every puzzle you solve."),
    dict(type="tool", id="cozy_tea", name="Cozy Tea", cost=60, desc="+25% Bolts from Focus Lamp study sessions."),
]
OUTFIT_BY_ID = {it["id"]: it for it in STORE_ITEMS if it["type"] == "outfit"}


def player_pal(outfit_id):
    o = OUTFIT_BY_ID.get(outfit_id, OUTFIT_BY_ID[0])
    return dict(JAS_LOOK, W=o["W"], P=o["P"])   # outfits change clothes; her hair and face always stay hers


def draw_tool_icon(d, tid, cx, cy):
    if tid == "multimeter":
        d.rounded_rectangle([cx - 20, cy - 30, cx + 20, cy + 30], radius=5, fill=(240, 190, 30), outline=(60, 40, 0), width=2)
        d.rectangle([cx - 14, cy - 24, cx + 14, cy - 6], fill=(150, 210, 160), outline=(30, 60, 30))
        d.text((cx - 11, cy - 20), "3.30", font=F_B, fill=(20, 50, 20))
        d.ellipse([cx - 11, cy + 2, cx + 11, cy + 24], fill=(40, 40, 46), outline=(0, 0, 0))
        d.line([(cx, cy + 13), (cx + 7, cy + 7)], fill=RED, width=2)
    elif tid == "flashlight":
        d.polygon([(cx - 6, cy - 6), (cx + 6, cy - 6), (cx + 26, cy - 30), (cx - 26, cy - 30)], fill=(255, 245, 160))
        d.rectangle([cx - 8, cy - 8, cx + 8, cy - 2], fill=(90, 90, 100), outline=(0, 0, 0))
        d.rectangle([cx - 6, cy - 2, cx + 6, cy + 30], fill=(60, 120, 200), outline=(0, 0, 0))
    elif tid == "gold_wires":
        for off, col in ((-8, (240, 180, 40)), (8, (130, 90, 20))):
            pts = [(cx - 26 + i * 4, cy + off + 8 * math.sin(i * 0.9)) for i in range(14)]
            d.line(pts, fill=col, width=4)
        draw_star(d, cx, cy - 24, 7, YELLOW)
    elif tid == "puzzle_specs":
        for ox in (-13, 13):
            d.ellipse([cx + ox - 11, cy - 11, cx + ox + 11, cy + 11], fill=(170, 220, 255), outline=(40, 40, 60), width=3)
        d.line([(cx - 3, cy - 2), (cx + 3, cy - 2)], fill=(40, 40, 60), width=3)
        d.line([(cx - 9, cy - 6), (cx - 15, cy - 1)], fill=WHITE, width=2)
    elif tid == "cozy_tea":
        for i in range(3):
            d.arc([cx - 10 + i * 8, cy - 34, cx - 2 + i * 8, cy - 16], 200, 340, fill=(220, 220, 230))
        d.rounded_rectangle([cx - 18, cy - 12, cx + 12, cy + 20], radius=6, fill=(240, 140, 170), outline=(90, 30, 50), width=2)
        d.arc([cx + 4, cy - 6, cx + 24, cy + 12], 270, 90, fill=(90, 30, 50), width=3)
        d.rectangle([cx - 14, cy - 10, cx + 8, cy - 4], fill=(170, 100, 50))
    elif tid == "lucky_charm":
        d.line([(cx, cy), (cx + 4, cy + 28)], fill=(40, 120, 50), width=3)
        for ox, oy in ((-9, -9), (9, -9), (-9, 9), (9, 9)):
            d.ellipse([cx + ox - 10, cy + oy - 18, cx + ox + 10, cy + oy + 2], fill=(60, 200, 90), outline=(20, 90, 40))
        d.ellipse([cx - 4, cy - 12, cx + 4, cy - 4], fill=(40, 150, 70))
    elif tid == "boots":
        d.polygon([(cx - 20, cy - 16), (cx - 4, cy - 16), (cx - 4, cy + 4), (cx + 22, cy + 10), (cx + 22, cy + 22), (cx - 20, cy + 22)],
                  fill=(200, 60, 60), outline=(60, 10, 10))
        d.rectangle([cx - 20, cy + 16, cx + 22, cy + 22], fill=WHITE, outline=(60, 10, 10))
        draw_bolt(d, cx - 12, cy, 1.6, YELLOW)


# ---------------- tile world ----------------
THEMES = [
    dict(f1=(88, 72, 60), f2=(80, 64, 53), wall=(128, 88, 62), wallD=(74, 50, 36), top=(38, 26, 22), acc=(255, 190, 70),
         crate=(176, 124, 64), desk=(140, 96, 58), rug=(120, 36, 56)),
    dict(f1=(78, 116, 126), f2=(70, 106, 117), wall=(192, 216, 222), wallD=(112, 142, 152), top=(30, 52, 62), acc=(110, 235, 245),
         crate=(150, 205, 215), desk=(214, 228, 232), rug=(30, 90, 110)),
    dict(f1=(72, 72, 80), f2=(64, 64, 72), wall=(112, 112, 122), wallD=(62, 62, 72), top=(28, 28, 34), acc=(250, 200, 30),
         crate=(206, 170, 40), desk=(92, 92, 104), rug=(110, 90, 20)),
    dict(f1=(42, 52, 94), f2=(36, 46, 86), wall=(72, 82, 146), wallD=(40, 48, 92), top=(16, 18, 42), acc=(130, 210, 255),
         crate=(84, 114, 196), desk=(62, 72, 132), rug=(30, 60, 120)),
    dict(f1=(52, 42, 72), f2=(46, 36, 66), wall=(104, 62, 134), wallD=(62, 36, 86), top=(22, 14, 34), acc=(255, 110, 205),
         crate=(154, 74, 154), desk=(86, 54, 106), rug=(100, 20, 90)),
    dict(f1=(122, 92, 72), f2=(114, 86, 68), wall=(152, 62, 132), wallD=(92, 36, 82), top=(40, 18, 40), acc=(250, 220, 60),
         crate=(200, 150, 70), desk=(150, 100, 60), rug=(150, 40, 60)),
    dict(f1=(70, 110, 60), f2=(62, 100, 54), wall=(120, 170, 110), wallD=(70, 110, 64), top=(24, 44, 24), acc=(180, 255, 120),
         crate=(150, 110, 60), desk=(110, 80, 50), rug=(60, 130, 60)),
    dict(f1=(90, 96, 110), f2=(82, 88, 102), wall=(60, 70, 96), wallD=(36, 42, 60), top=(12, 16, 30), acc=(255, 170, 90),
         crate=(170, 120, 70), desk=(100, 100, 120), rug=(160, 80, 50)),
]
THEMES += [
    dict(f1=(96, 70, 52), f2=(88, 64, 48), wall=(70, 110, 90), wallD=(44, 74, 60), top=(30, 24, 20), acc=(255, 214, 140),
         crate=(170, 120, 70), desk=(130, 86, 52), rug=(40, 90, 70)),        # 8: study room
    dict(f1=(36, 28, 58), f2=(30, 24, 50), wall=(60, 40, 100), wallD=(36, 24, 64), top=(12, 8, 24), acc=(80, 255, 220),
         crate=(120, 60, 160), desk=(70, 50, 110), rug=(120, 30, 120)),      # 9: puzzle lab
    dict(f1=(206, 170, 176), f2=(198, 162, 170), wall=(250, 205, 222), wallD=(222, 166, 192), top=(80, 40, 60),
         acc=(255, 240, 150), crate=(200, 150, 90), desk=(170, 120, 80), rug=(240, 150, 190)),  # 10: her room
]
ZONE_THEME = [0, 1, 2, 3, 4, 6, 7]   # theme 5 is Tess's store
SOLID = set("#wcdbx123FTPQKGJ")
TERM_COLS = (4, 10, 16)

# Escapists-style stashes: CENTER on one of these tiles searches it (each one pays out once)
STASH = {"c": "crate", "d": "desk", "b": "bookshelf", "v": "vent"}
SEARCH_OPEN = {"c": "You pry open the crate and dig around...",
               "d": "You quietly slide open the desk drawer...",
               "b": "You flip through the dusty books..."}
JUNK = ["Just old resistors and a half-eaten sandwich.",
        "A manual called 'LEDs for Beginners'. Somebody drew a smiley in it.",
        "A rubber duck wearing tiny safety goggles. Adorable.",
        "Nothing but tangled jumper wires. Classic.",
        "A sticky note: 'Guards change shift at 6. Or was it 9?'"]
VENT_LINES = ["Hmm, a vent cover. Way too small to crawl through... I'll keep it in mind.",
              "I can hear the generator humming through this vent.",
              "A cold draft is coming out of the vent. Spooky!"]
# hand-placed surprises: "room:x:y" -> (text, bolts)
SECRET_NOTES = {
    "z0:3:10": ("Note #1, folded with a heart on it: 'Jaslyne - you're the brightest light in this whole "
                "facility. Love, Gio' ...and 5 Bolts tucked inside!", 5),
    "z1:15:4": ("Note #2: 'My heart is like an LED and you're my battery. With you, I light right up. - Gio' (+5 Bolts)", 5),
    "z2:9:12": ("Note #3: 'Even when the power's out, you're still my favorite light. - Gio' (+5 Bolts)", 5),
    "z3:17:10": ("Note #4: 'My resistance drops to zero every time you smile. - Gio' (+5 Bolts)", 5),
    "z4:3:4": ("Note #5: 'You're like a slide pot - you decide how bright my whole day gets. - Gio' (+5 Bolts)", 5),
    "z5:5:10": ("Note #6: 'Roses are red, LEDs are too, nothing in here shines brighter than you. - Gio' (+5 Bolts)", 5),
    "z6:15:10": ("Note #7: 'Almost out! Whatever is past that hatch, I want to see it with you. - Gio' (+5 Bolts)", 5),
    "store:1:2": ("Note #8, hidden inside a book: 'Tess let me hide this here. You're amazing, Jaslyne. - Gio' (+5 Bolts)", 5),
}
# ---------------- the story ----------------
# Saturday night at VOLTA LABS. Lightning hits the generator, the surge fries every circuit board and
# scrambles M.A.X., the building's AI. Confused and blind, MAX thinks the building is under attack and seals
# every door. Each zone you repower lets MAX see/remember a bit more, until he can lift the lockdown from the roof.
PROLOGUE_SLIDES = [
    ("facility", "Saturday night. Jaslyne and Gio pull up to VOLTA LABS, the coolest science building in the city."),
    ("facility", "Tonight they've got something special: a private after-hours tour, led by the people who work here!"),
]
BLACKOUT_SLIDES = [
    ("storm", "Then, right in the middle of the tour, a huge storm rolls in. CRACK! Lightning hits the main generator."),
    ("lockdown", "The power surge scrambles M.A.X., the building's computer brain. He panics and starts a LOCKDOWN. Every door slams shut."),
    ("dark", "The surge also fried every circuit board in the building. The lights die. Nobody can get in... or out."),
    ("dark", "Jaslyne wakes up on the cold Workshop floor. Somewhere in the dark, Gio is calling her name..."),
]
ENDING_SLIDES = [
    ("lockdown_off", "With the roof beacons lit, M.A.X. runs one last command: LOCKDOWN LIFTED. Every door in Volta Labs clicks open."),
    ("facility_lit", "Floor by floor, the lights come back on. Silas, Dr. Vex, Flora and the whole crew walk out safe."),
    ("facility_lit", "M.A.X. sends one more message to every screen in the building: 'THANK YOU, JASLYNE. THANK YOU, GIO.'"),
]
# story beats: said the first time she walks into a zone, and when its 3rd circuit is fixed
ZONE_ENTER = {
    1: [("max", "INTRUDER DETECTED IN THE LAB. PLEASE REMAIN CALM. DOORS WILL STAY SEALED."),
        ("vex", "That's MAX on the speakers. The lightning scrambled him - he thinks the building is under attack!"),
        ("jas", "So MAX isn't evil... he's just confused?"),
        ("vex", "Exactly. The more power we bring back, the more of his systems wake up. Let's help him.")],
    2: [("max", "WARNING. REACTOR TEMPERATURE RISING. ALL PERSONNEL... I CANNOT FIND ANY PERSONNEL."),
        ("master", "The coolant pumps died in the surge. If this core overheats, MAX floods the whole tower with foam!"),
        ("gio", "No foam. Definitely no foam. Let's cool it down.")],
    3: [("max", "SENSORS OFFLINE. I CANNOT SEE. I CANNOT HEAR. I AM... SCARED?"),
        ("pixel", "BEEP. MAX is blind without the Sensor Wing. That is why he keeps panicking."),
        ("jas", "Don't worry, MAX. We'll give you your eyes back.")],
    4: [("ada", "Welcome to the Control Room. This is MAX's brain. The surge wiped his memory clean."),
        ("ada", "Fix these three terminals and his memory comes back. Then he can finally think straight."),
        ("max", "WHO... WHO ARE YOU? WHY DO YOU KEEP HELPING ME?")],
    5: [("flora", "Oh thank goodness, people! I've been stuck in here with the tomatoes all night."),
        ("max", "GREENHOUSE LIFE SUPPORT IS FAILING. PLEASE HELP THE PLANTS. ...PLEASE."),
        ("gio", "Did MAX just say please? He really is getting better.")],
    6: [("skye", "Pilot Skye! My chopper is circling, but the storm knocked out the roof beacons."),
        ("max", "THE LOCKDOWN CAN ONLY BE LIFTED FROM THE ROOF. THE ROOF NEEDS POWER."),
        ("jas", "Three more circuits. Then we all go home.")],
}
ZONE_CLEAR = {
    0: [("max", "WORKSHOP POWER: ONLINE. ...UNKNOWN PERSONS DETECTED. WHO ARE YOU?"),
        ("gio", "That's MAX, the building's AI. Getting power back must have woken him up a little."),
        ("gio", "He just unlocked the Lab door on the right. Come on!")],
    1: [("vex", "I found MAX's error log! The lightning fried his memory chip. He doesn't recognize anyone anymore."),
        ("vex", "But look - every room you power up, he calms down a bit. The Motor Tower is next!")],
    2: [("master", "Core temperature normal! You saved this whole tower from a foam disaster."),
        ("max", "REACTOR STABLE. THANK... THANK YOU? THAT WORD FEELS NEW. DOOR UNSEALED.")],
    3: [("max", "I CAN SEE AGAIN. I SEE YOU. YOU ARE FIXING THINGS... NOT BREAKING THEM."),
        ("jas", "That's right, MAX. We're friends. We're trying to help everyone get out."),
        ("max", "FRIENDS. ...OPENING THE CONTROL ROOM.")],
    4: [("max", "MEMORY RESTORED. JASLYNE. GIO. VISITORS ON THE TOUR. I REMEMBER NOW."),
        ("max", "I AM SO SORRY. THE LIGHTNING CONFUSED ME. I THOUGHT I WAS PROTECTING EVERYONE."),
        ("max", "I CAN ONLY LIFT THE LOCKDOWN FROM THE ROOF. THE STAIRS GO UP THROUGH THE GREENHOUSE."),
        ("gio", "Then that's where we're going. Hang in there, MAX!")],
    5: [("flora", "The plants are saved! And the rooftop stairs are open. Go, go, go!"),
        ("max", "ROOF ACCESS UNSEALED. ONE LAST STEP, ENGINEERS.")],
}
NOTE_REACTIONS = ["...aww. Okay, now I HAVE to get us out of here.", "Hehe. That's so cheesy. I love it.",
                  "*tucks the note safely in her pocket*", "Gio, you dork. ...Cute dork.",
                  "I'm gonna find every single one of these."]


def _rng(tx, ty, n=0):
    return random.Random(tx * 733 + ty * 971 + n)


def draw_floor(d, x, y, th, tx, ty):
    c = th["f1"] if (tx + ty) % 2 == 0 else th["f2"]
    d.rectangle([x, y, x + 15, y + 15], fill=c)
    dk = tuple(max(0, v - 14) for v in c)
    d.line([(x, y + 15), (x + 15, y + 15)], fill=dk)
    d.line([(x + 15, y), (x + 15, y + 15)], fill=dk)
    r = _rng(tx, ty, 1)
    if r.random() < 0.3:
        d.point((x + r.randint(2, 12), y + r.randint(2, 12)), fill=dk)


def draw_wall(d, x, y, th, lamp=None):
    d.rectangle([x, y, x + 15, y + 15], fill=th["wall"])
    for r in range(3):
        y0 = y + r * 5
        d.line([(x, y0 + 4), (x + 15, y0 + 4)], fill=th["wallD"])
        off = 0 if r % 2 == 0 else 8
        d.line([(x + off + 7, y0), (x + off + 7, y0 + 4)], fill=th["wallD"])
    d.rectangle([x, y + 13, x + 15, y + 15], fill=th["wallD"])
    if lamp is not None:
        d.rectangle([x + 3, y + 2, x + 12, y + 10], fill=(28, 28, 34), outline=(0, 0, 0))
        col = th["acc"] if lamp else (62, 62, 72)
        d.rectangle([x + 4, y + 3, x + 11, y + 9], fill=col)
        if lamp:
            d.line([(x + 5, y + 4), (x + 8, y + 4)], fill=WHITE)


def draw_tile(d, ch, x, y, th, tx, ty, ctx):
    floorish = ch in ".rvLRSE"
    if ch == "#":
        d.rectangle([x, y, x + 15, y + 15], fill=th["top"])
        d.line([(x, y + 15), (x + 15, y + 15)], fill=tuple(min(255, v + 14) for v in th["top"]))
        return
    if ch == "D":   # plain door in a wall (study room -> puzzle lab)
        draw_wall(d, x, y, th)
        d.rectangle([x + 2, y + 2, x + 13, y + 15], fill=(60, 36, 90), outline=th["acc"])
        d.text((x + 5, y + 2), "?", font=F_B, fill=th["acc"])
        return
    if ch == "w" or ch == "S":
        lamp = None
        if ch == "w" and ty == 1 and tx in TERM_COLS:
            if ctx["zone"] is None:
                lamp = True
            else:
                lamp = (ctx["zone"] * PER_ZONE + TERM_COLS.index(tx)) in ctx["done"]
        draw_wall(d, x, y, th, lamp)
        if ch == "S":   # store door with awning
            d.rectangle([x + 2, y + 3, x + 13, y + 15], fill=(70, 34, 100), outline=YELLOW)
            d.ellipse([x + 10, y + 9, x + 12, y + 11], fill=YELLOW)
            for i in range(6):
                d.rectangle([x + 1 + i * 2, y, x + 2 + i * 2, y + 3], fill=RED if i % 2 == 0 else WHITE)
        return
    if ch in "LR":
        d.rectangle([x, y, x + 15, y + 15], fill=th["top"])
        open_ = ctx["unlocked"] if ch == "R" else True
        d.rectangle([x + 2, y + 1, x + 13, y + 15], fill=(140, 146, 158), outline=(0, 0, 0))
        d.line([(x + 7, y + 6), (x + 7, y + 15)], fill=(90, 96, 108))
        d.ellipse([x + 5, y + 2, x + 9, y + 5], fill=GREEN if open_ else RED, outline=(0, 0, 0))
        if not open_:
            for bx in (4, 8, 11):
                d.line([(x + bx, y + 7), (x + bx, y + 15)], fill=(60, 60, 70))
        return
    if ch == "E":
        draw_floor(d, x, y, th, tx, ty)
        d.rectangle([x, y + 4, x + 15, y + 15], fill=(100, 70, 40), outline=(0, 0, 0))
        d.rectangle([x + 3, y + 6, x + 12, y + 12], fill=(150, 210, 230))
        return
    draw_floor(d, x, y, th, tx, ty)
    if ch == "r":
        d.rectangle([x, y, x + 15, y + 15], fill=th["rug"])
        d.polygon([(x + 8, y + 3), (x + 13, y + 8), (x + 8, y + 13), (x + 3, y + 8)], outline=th["acc"])
    elif ch == "v":
        d.rectangle([x + 2, y + 2, x + 13, y + 13], fill=(34, 34, 42), outline=(10, 10, 14))
        for ly in (5, 8, 11):
            d.line([(x + 3, y + ly), (x + 12, y + ly)], fill=(90, 90, 104))
    elif ch == "c":
        c = th["crate"]
        dk = tuple(max(0, v - 60) for v in c)
        d.rectangle([x + 1, y + 2, x + 14, y + 14], fill=c, outline=dk)
        d.line([(x + 1, y + 2), (x + 14, y + 14)], fill=dk)
        d.line([(x + 14, y + 2), (x + 1, y + 14)], fill=dk)
    elif ch == "d":
        c = th["desk"]
        d.rectangle([x, y + 4, x + 15, y + 14], fill=c, outline=tuple(max(0, v - 50) for v in c))
        d.rectangle([x, y + 4, x + 15, y + 6], fill=tuple(min(255, v + 30) for v in c))
        r = _rng(tx, ty, 2)
        for _ in range(3):
            ix = r.randint(2, 10)
            d.rectangle([x + ix, y + 7, x + ix + r.randint(1, 3), y + 9], fill=r.choice([RED, YELLOW, CYAN, WHITE]))
    elif ch == "b":
        d.rectangle([x, y, x + 15, y + 15], fill=(88, 56, 34), outline=(40, 24, 14))
        r = _rng(tx, ty, 3)
        for sy in (1, 6, 11):
            d.line([(x, sy + y + 4), (x + 15, sy + y + 4)], fill=(50, 30, 18))
            for ix in range(0, 14, 4):
                d.rectangle([x + 1 + ix, y + sy, x + 3 + ix, y + sy + 3],
                            fill=r.choice([RED, GREEN, CYAN, YELLOW, PURPLE, ORANGE]))
    elif ch == "x":
        d.rectangle([x, y + 3, x + 15, y + 14], fill=(150, 100, 60), outline=(70, 44, 24))
        d.rectangle([x, y + 3, x + 15, y + 6], fill=(206, 154, 94))
    elif ch == "F":   # flashcard desk
        c = th["desk"]
        d.rectangle([x, y + 4, x + 15, y + 14], fill=c, outline=tuple(max(0, v - 50) for v in c))
        d.polygon([(x + 2, y + 3), (x + 8, y + 5), (x + 14, y + 3), (x + 14, y + 10), (x + 8, y + 12), (x + 2, y + 10)],
                  fill=CREAM, outline=(90, 80, 70))
        d.line([(x + 8, y + 5), (x + 8, y + 12)], fill=(90, 80, 70))
        d.line([(x + 3, y + 6), (x + 6, y + 7)], fill=(120, 120, 150))
        d.line([(x + 10, y + 7), (x + 13, y + 6)], fill=(120, 120, 150))
    elif ch == "G":   # free build workbench
        d.rectangle([x, y + 5, x + 15, y + 14], fill=(120, 90, 60), outline=(60, 40, 24))
        d.rectangle([x + 2, y + 1, x + 13, y + 8], fill=CYAN, outline=CYAN_D)
        d.line([(x + 3, y + 2), (x + 12, y + 2)], fill=RED)
        d.line([(x + 3, y + 7), (x + 12, y + 7)], fill=(40, 80, 220))
        d.line([(x + 5, y + 2), (x + 5, y + 5), (x + 10, y + 5)], fill=(240, 200, 30))
        d.ellipse([x + 9, y + 3, x + 12, y + 6], fill=(255, 70, 70))
    elif ch == "J":   # job board
        d.rectangle([x + 2, y + 9, x + 3, y + 15], fill=(90, 60, 36))
        d.rectangle([x + 12, y + 9, x + 13, y + 15], fill=(90, 60, 36))
        d.rectangle([x, y, x + 15, y + 11], fill=(190, 140, 80), outline=(90, 60, 30))
        for px_, py_ in ((2, 2), (8, 1), (4, 6), (10, 6)):
            d.rectangle([x + px_, y + py_, x + px_ + 4, y + py_ + 4], fill=WHITE)
            d.point((x + px_ + 2, y + py_), fill=RED)
        d.text((x + 3, y - 1), "!", font=F_B, fill=RED)
    elif ch == "K":   # book stand with a big lesson book
        d.rectangle([x + 6, y + 9, x + 9, y + 15], fill=(90, 60, 36))
        d.rectangle([x + 3, y + 14, x + 12, y + 15], fill=(70, 46, 28))
        d.polygon([(x + 1, y + 3), (x + 7, y + 1), (x + 7, y + 10), (x + 1, y + 11)], fill=(150, 40, 50), outline=(60, 10, 20))
        d.polygon([(x + 8, y + 1), (x + 14, y + 3), (x + 14, y + 11), (x + 8, y + 10)], fill=(150, 40, 50), outline=(60, 10, 20))
        d.polygon([(x + 2, y + 4), (x + 7, y + 2), (x + 7, y + 9), (x + 2, y + 10)], fill=CREAM)
        d.polygon([(x + 8, y + 2), (x + 13, y + 4), (x + 13, y + 10), (x + 8, y + 9)], fill=CREAM)
    elif ch == "T":   # focus lamp desk
        c = th["desk"]
        d.ellipse([x - 2, y - 2, x + 17, y + 12], fill=tuple(min(255, v + 40) for v in th["f1"]))
        d.rectangle([x, y + 6, x + 15, y + 14], fill=c, outline=tuple(max(0, v - 50) for v in c))
        d.line([(x + 4, y + 6), (x + 4, y + 1), (x + 8, y - 1)], fill=(60, 60, 70), width=1)
        d.polygon([(x + 6, y - 1), (x + 12, y - 1), (x + 14, y + 3), (x + 4, y + 3)], fill=(250, 210, 90), outline=(90, 70, 20))
        d.rectangle([x + 9, y + 8, x + 14, y + 11], fill=(200, 60, 80))
    elif ch in "PQ":   # puzzle machines: P = pipes, Q = light grid
        body = (110, 50, 170) if ch == "P" else (30, 140, 140)
        d.rectangle([x + 1, y, x + 14, y + 15], fill=body, outline=(10, 8, 20))
        d.rectangle([x + 3, y + 2, x + 12, y + 8], fill=(10, 14, 24))
        if ch == "P":
            d.line([(x + 4, y + 5), (x + 8, y + 5), (x + 8, y + 3)], fill=(80, 255, 220))
            d.line([(x + 8, y + 7), (x + 11, y + 7)], fill=(250, 220, 40))
        else:
            for i in range(3):
                for j in range(2):
                    d.point((x + 5 + i * 3, y + 4 + j * 3), fill=(250, 220, 40) if (i + j) % 2 == 0 else (60, 60, 70))
        d.rectangle([x + 3, y + 10, x + 12, y + 13], fill=tuple(max(0, v - 40) for v in body))
        d.point((x + 5, y + 11), fill=RED)
        d.point((x + 9, y + 11), fill=YELLOW)
    elif ch in "123":
        q = ctx["zone"] * PER_ZONE + int(ch) - 1
        c = th["desk"]
        d.rectangle([x, y + 8, x + 15, y + 15], fill=c, outline=tuple(max(0, v - 50) for v in c))
        draw_terminal_screen(d, x, y, q in ctx["done"], 0.0)


def draw_terminal_screen(d, x, y, complete, now):
    d.rectangle([x + 2, y, x + 13, y + 9], fill=(22, 22, 28), outline=(90, 90, 104))
    if complete:
        d.rectangle([x + 3, y + 1, x + 12, y + 8], fill=(30, 110, 70))
        draw_star(d, x + 8, y + 5, 3, YELLOW, YELLOW)
    else:
        pulse = 0.5 + 0.5 * math.sin(now * 4)
        d.rectangle([x + 3, y + 1, x + 12, y + 8], fill=lerp_col((20, 60, 110), (60, 150, 230), pulse))
        d.text((x + 6, y), "!", font=F_B, fill=WHITE)


BASE_ZONE = [
    "####################",
    "wwwwwwwwwwwwwwwwwwww",
    "#...1.....2.....3..#",
    "#..................#",
    "#..c...........c...#",
    "#..................#",
    "#......rrrrrr......#",
    "L......rrrrrr......R",
    "#......rrrrrr......#",
    "#..................#",
    "#..d.d.........d.d.#",
    "#..................#",
    "#.v..............v.#",
    "#..................#",
    "####################",
]
STORE_MAP = [
    "####################",
    "wwwwwwwwwwwwwwwwwwww",
    "#bbbb..........bbbb#",
    "#..................#",
    "#....xxxxxxxxxx....#",
    "#..................#",
    "#..................#",
    "#...bb........bb...#",
    "#.......rrrr.......#",
    "#.......rrrr.......#",
    "#...bb........bb...#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#########EE#########",
]


def _edit(rows, edits):
    rows = [list(r) for r in rows]
    for (x, y), c in edits.items():
        rows[y][x] = c
    return ["".join(r) for r in rows]


def lines3(a, b, c):
    return dict(start=a, mid=b, done=c)


ROOMS = {}
_zone_maps = [
    _edit(BASE_ZONE, {(2, 1): "S", (17, 1): "D", (9, 12): "G", (10, 12): "J"}),
    _edit(BASE_ZONE, {(3, 4): "d", (15, 4): "d"}),
    _edit(BASE_ZONE, {(3, 9): "c", (15, 9): "c", (8, 12): "c", (9, 12): "c"}),
    _edit(BASE_ZONE, {(7, 4): "v", (12, 4): "v", (7, 12): "v", (12, 12): "v"}),
    _edit(BASE_ZONE, {(6, 5): "r", (13, 5): "r", (6, 9): "r", (13, 9): "r"}),
    _edit(BASE_ZONE, {(6, 4): "c", (13, 4): "c", (3, 12): "c", (16, 12): "c"}),
    _edit(BASE_ZONE, {(7, 10): "c", (12, 10): "c", (9, 4): "v", (10, 4): "v"}),
]
_zone_npcs = [
    [dict(id="gio", x=8, y=5, wander=2, role="talk",
          lines=lines3(
              ["Jaslyne! You're okay! Lightning hit the generator, and MAX - the building's AI - locked every door.",
               "The surge fried the circuit boards too. Every room has 3 dead terminals. Fix them and its power comes back.",
               "When a room gets power, MAX wakes up a bit and unlocks the next door. If we reach the roof, we can call for help!",
               "Walk up to a terminal - the one with the bouncing ! - and press CENTER. I'll talk you through it.",
               "Psst... search desks, crates and shelves for hidden Bolts. Shiny ones still have loot!",
               "...I may also have hidden a few notes for you around here. Just saying.",
               "Oh! The door on the LEFT goes to the Study Room and the Puzzle Lab, if you ever want a break.",
               "CENTER with nothing nearby opens your menu. Tess's Store is the door in the top-left."],
              ["Nice work! The lights are coming back little by little.",
               "Remember: the LED's long leg (+) faces the resistor."],
              ["The whole Workshop is lit! Take the big door on the right to the Lab."])),
     dict(id="silas", x=17, y=6, wander=1, role="talk",
          lines=lines3(["I'm Silas, night security. MAX locked me out of my own doors! Fix all 3 terminals and he'll open this one."],
                       ["Two more to go? The Lab folks are waiting."],
                       ["Gate's open. Good luck up the Lab, kid."]))],
    [dict(id="vex", x=9, y=5, wander=2, role="talk",
          lines=lines3(["Ah, a visiting engineer! The Lab needs series AND parallel circuits. Take your time."],
                       ["Excellent! Parallel branches share the voltage, series ones share the current."],
                       ["Brilliant work! The Motor Tower is through the right door."])),
     dict(id="bolt", x=15, y=7, wander=1, role="talk",
          lines=lines3(["BEEP! Fun fact: in series, one broken part turns everything off. Parallel keeps going!"],
                       ["BEEP! Keep going! I love your wiring."], ["BEEP BOOP! Lab power at 100%!"]))],
    [dict(id="master", x=9, y=5, wander=2, role="talk",
          lines=lines3(["The reactor core is rumbling! Motors pull a lot of current, so wire carefully."],
                       ["Steady hands! The core is cooling down."],
                       ["The tower is stable. Onward to the Sensor Wing!"])),
     dict(id="bolt", x=4, y=8, wander=1, role="talk",
          lines=lines3(["BEEP! Motors need more current than LEDs. That's why we use switches."],
                       ["BEEP! Glug glug!"], ["BEEP! The coolant is flowing nicely."]))],
    [dict(id="pixel", x=9, y=5, wander=2, role="talk",
          lines=lines3(["BEEP. Sensor Wing offline. The security lasers are dead. I will guide you."],
                       ["Processing... you are doing well, human."],
                       ["All sensors online. Proceed to the Control Room."])),
     dict(id="bolt", x=16, y=9, wander=1, role="talk",
          lines=lines3(["BEEP! Lasers travel in perfectly straight lines. That's why they make great tripwires!"],
                       ["BEEP! Almost there!"], ["BEEP! Great job, engineer."]))],
    [dict(id="ada", x=9, y=5, wander=2, role="talk",
          lines=lines3(["Last stretch, engineer. The roof hatch needs a full override. Motors, switches... all of it."],
                       ["Good. The hatch motors are warming up."],
                       ["Override accepted! The stairs to the Greenhouse are open. The roof is almost in reach!"])),
     dict(id="bolt", x=15, y=6, wander=1, role="talk",
          lines=lines3(["BEEP! A slide pot can slow a DC motor down. Try it!"],
                       ["BEEP! You've got this."], ["BEEP BOOP! Almost there!"]))],
    [dict(id="flora", x=9, y=5, wander=2, role="talk",
          lines=lines3(["Oh! A visitor! My plants need grow lights AND a sprinkler pump. Help me wire them up?"],
                       ["The tomatoes are perking up already!"],
                       ["The Greenhouse is blooming! The rooftop stairs are through that door."])),
     dict(id="bolt", x=15, y=8, wander=1, role="talk",
          lines=lines3(["BEEP! If one series light breaks, they ALL go out. Parallel lights are tougher!"],
                       ["BEEP! The plants like you."], ["BEEP! Photosynthesis: activated!"]))],
    [dict(id="skye", x=9, y=5, wander=2, role="talk",
          lines=lines3(["Pilot Skye here! The rescue chopper can't land until the roof beacons are lit."],
                       ["I can see the chopper's lights in the distance!"],
                       ["Beacons are blazing! The hatch is right through that door. Let's go home!"])),
     dict(id="bolt", x=4, y=7, wander=1, role="talk",
          lines=lines3(["BEEP! A spinning motor can MAKE electricity. That's how wind turbines work!"],
                       ["BEEP! So windy up here!"], ["BEEP BOOP! See you on the outside!"]))],
]
for _z in range(NZ):
    ROOMS["z%d" % _z] = dict(name=ZONES[_z], zone=_z, theme=ZONE_THEME[_z], map=_zone_maps[_z], npcs=_zone_npcs[_z], doors={})
    if _z > 0:
        ROOMS["z%d" % _z]["doors"][(0, 7)] = dict(to="z%d" % (_z - 1), x=18, y=7, face="left")
    if _z < NZ - 1:
        ROOMS["z%d" % _z]["doors"][(19, 7)] = dict(to="z%d" % (_z + 1), x=1, y=7, face="right", need=_z)
    else:
        ROOMS["z%d" % _z]["doors"][(19, 7)] = dict(to="ending", need=_z)
ROOMS["z0"]["doors"][(2, 1)] = dict(to="store", x=9, y=13, face="up")
ROOMS["store"] = dict(
    name="TESS'S STORE", zone=None, theme=5, map=STORE_MAP, doors={
        (9, 14): dict(to="z0", x=2, y=2, face="down"), (10, 14): dict(to="z0", x=2, y=2, face="down")},
    npcs=[dict(id="tess", x=9, y=3, wander=0, role="shop", face="down",
               lines=dict(start=["Welcome to Tess's General Store! Spend your Bolts on gear and outfits!"]))])
STUDY_MAP = [
    "####################",
    "wwwwwwwwwDwwwwwwwwww",
    "#bbbb..........bbbb#",
    "#..................#",
    "#..K...K....F...F..#",
    "#..................#",
    "#.......rrrr.......#",
    "#.......rrrr.......L",
    "#.......rrrr.......#",
    "#..................#",
    "#...T....T....T....#",
    "#..................#",
    "#bb..............bb#",
    "#..................#",
    "####################",
]
ARCADE_MAP = [
    "####################",
    "wwwwwwwwwwwwwwwwwwww",
    "#..................#",
    "#..P...P....Q...Q..#",
    "#..................#",
    "#..................#",
    "#......rrrrrr......#",
    "#......rrrrrr......#",
    "#......rrrrrr......#",
    "#..................#",
    "#..P...P....Q...Q..#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#########EE#########",
]
ROOMS["z0"]["doors"][(0, 7)] = dict(to="study", x=18, y=7, face="left")
ROOMS["z0"]["doors"][(17, 1)] = dict(to="jroom", x=9, y=13, face="up")
JROOM_MAP = ["####################", "wwwwwwwwwwwwwwwwwwww"] + ["#..................#"] * 12 + ["#########EE#########"]
ROOMS["jroom"] = dict(
    name="JASLYNE'S ROOM", zone=None, theme=10, map=JROOM_MAP, doors={
        (9, 14): dict(to="z0", x=17, y=2, face="down"), (10, 14): dict(to="z0", x=17, y=2, face="down")},
    npcs=[dict(id="canica", x=6, y=7, wander=3, role="pet", lines=dict(start=["Yip!"])),
          dict(id="gummy", x=13, y=9, wander=2, role="pet", lines=dict(start=["Woof!"])),
          dict(id="sofia", x=9, y=10, wander=3, role="pet", lines=dict(start=["Arf!"])),
          dict(id="lafufu", x=17, y=3, wander=0, role="pet", lines=dict(start=["*blub*"]))])
ROOMS["study"] = dict(
    name="STUDY ROOM", zone=None, theme=8, map=STUDY_MAP, doors={
        (19, 7): dict(to="z0", x=1, y=7, face="right"), (9, 1): dict(to="arcade", x=9, y=13, face="up")},
    npcs=[dict(id="page", x=10, y=9, wander=1, role="talk", lines=dict(start=[
        "Shh... welcome to the Study Room! I'm Ms. Page, the librarian.",
        "Step 1: read a chapter at the red BOOK STANDS on the left. Short pages with pictures!",
        "Step 2: test yourself at the FLASHCARD desks on the right. They ask about chapters you've read.",
        "The glowing lamps are Focus Lamps. Do your REAL homework next to one and it pays you in Bolts.",
        "And the purple door up top leads to the Puzzle Lab. Have fun!"]))])
ROOMS["arcade"] = dict(
    name="PUZZLE LAB", zone=None, theme=9, map=ARCADE_MAP, doors={
        (9, 14): dict(to="study", x=9, y=2, face="down"), (10, 14): dict(to="study", x=9, y=2, face="down")},
    npcs=[dict(id="riddle", x=9, y=9, wander=1, role="talk", lines=dict(start=[
        "BZZT! Riddle the puzzle bot here! Purple machines are PIPE puzzles, teal ones are LIGHT GRIDS.",
        "Each type has 40 puzzles. Solve one in few moves for 3 stars! Beat them all and they go ENDLESS.",
        "Stuck? Move the cursor off the left edge and press CENTER to exit any time."]))])
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPP = {"up": "down", "down": "up", "left": "right", "right": "left"}

# terminal and stash locations per room
for _rid, _r in ROOMS.items():
    _r["terms"] = [(tx, ty, int(ch)) for ty, row in enumerate(_r["map"]) for tx, ch in enumerate(row) if ch in "123"]
    _r["stashes"] = [(tx, ty) for ty, row in enumerate(_r["map"]) for tx, ch in enumerate(row) if ch in "cdb"]

_bg_cache = {}
_static_cache = {}
_hud_cache = {}
_bar_cache = {}


def build_bg(rid, done, removed=frozenset()):
    room = ROOMS[rid]
    th = THEMES[room["theme"]]
    zone = room["zone"]
    ctx = dict(zone=zone, done=done, unlocked=zone is not None and zone_done(done, zone) >= PER_ZONE)
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for ty, row in enumerate(room["map"]):
        for tx, ch in enumerate(row):
            draw_tile(d, "." if (tx, ty) in removed else ch, tx * TS, ty * TS, th, tx, ty, ctx)
    return im


_light_cache = {}


def apply_light(im, cx, cy, level, bonus):
    if level >= 3:
        return im
    key = (level, bonus)
    if key not in _light_cache:
        yy, xx = np.mgrid[0:2 * H, 0:2 * W]
        dist = np.sqrt((xx - W) ** 2 + (yy - H) ** 2)
        base = (95, 135, 175)[level]     # dim, not pitch black, so the room is still easy to get around
        r0, r1 = 30 + bonus * 14, 84 + level * 18 + bonus * 40
        t = np.clip((r1 - dist) / (r1 - r0), 0, 1)
        _light_cache[key] = Image.fromarray((base + (255 - base) * t).astype(np.uint8), "L")
    mask = _light_cache[key].crop((W - cx, H - cy, 2 * W - cx, 2 * H - cy))
    return Image.composite(im, Image.new("RGB", (W, H), (4, 6, 14)), mask)


# ---------------- save / load ----------------
def load_progress():
    try:
        if TESTING_MODE:
            raise FileNotFoundError("testing mode: start fresh")
        with open(PROGRESS_FILE) as f:
            s = json.load(f)
        done = set(int(x) for x in s.get("done", []))
        outfit = int(s.get("outfit", 0))
        return dict(
            done=done, outfit=outfit, upgrades=set(s.get("upgrades", [])),
            bolts=int(s.get("bolts", 10 * len(done))),
            owned=set(int(x) for x in s.get("owned", [0, outfit])),
            looted=set(s.get("looted", [])),
            ach=set(s.get("ach", [])), quiz=set(int(x) for x in s.get("quiz", [])),
            talked=set(s.get("talked", [])), steps=int(s.get("steps", 0)), earned=int(s.get("earned", 0)),
            replays=int(s.get("replays", 0)), play=float(s.get("play", 0)),
            read=set(int(x) for x in s.get("read", [])), story=set(s.get("story", [])),
            cards={int(k): int(v) for k, v in s.get("cards", {}).items()},
            card_sessions=int(s.get("card_sessions", 0)), perfect_rounds=int(s.get("perfect_rounds", 0)),
            focus_sessions=int(s.get("focus_sessions", 0)), focus_min=int(s.get("focus_min", 0)),
            pipes={int(k): int(v) for k, v in s.get("pipes", {}).items()},
            lights={int(k): int(v) for k, v in s.get("lights", {}).items()}, endless=int(s.get("endless", 0)),
            room=s.get("room", "z0"), tx=int(s.get("tx", 3)), ty=int(s.get("ty", 9)),
            intro=bool(s.get("intro", True)), escaped=bool(s.get("escaped", False)), exists=True,
            **{k: s.get(k, v) for k, v in extra_defaults().items()})
    except Exception:
        return dict(done=set(), outfit=0, upgrades=set(), bolts=0, owned={0}, looted=set(), ach=set(), quiz=set(),
                    talked=set(), steps=0, earned=0, replays=0, play=0.0, read=set(), story=set(), cards={}, card_sessions=0, perfect_rounds=0,
                    focus_sessions=0, focus_min=0, pipes={}, lights={}, endless=0, room="z0", tx=3, ty=9,
                    intro=False, escaped=False, exists=False, **extra_defaults())


def write_progress(s):
    if TESTING_MODE:
        return
    try:
        os.makedirs(CIRCUIT_DIR, exist_ok=True)
        out = dict(done=sorted(s["done"]), outfit=s["outfit"], upgrades=sorted(s["upgrades"]), bolts=s["bolts"],
                   owned=sorted(s["owned"]), looted=sorted(s["looted"]), ach=sorted(s["ach"]), quiz=sorted(s["quiz"]),
                   talked=sorted(s["talked"]), steps=s["steps"], earned=s["earned"], replays=s["replays"],
                   play=round(s["play"], 1), read=sorted(s["read"]), story=sorted(s["story"]), cards=s["cards"], card_sessions=s["card_sessions"],
                   perfect_rounds=s["perfect_rounds"], focus_sessions=s["focus_sessions"], focus_min=s["focus_min"],
                   pipes=s["pipes"], lights=s["lights"], endless=s["endless"], room=s["room"], tx=s["tx"], ty=s["ty"],
                   intro=s["intro"], escaped=s["escaped"], saved_at=round(time.time(), 1))
        out.update({k: s[k] for k in EXTRA_DEFAULTS})
        with open(PROGRESS_FILE, "w") as f:
            json.dump(out, f)
    except Exception as e:
        print("Could not save progress:", e)


# ---------------- dialogue box (shared by world and quest screens) ----------------
def draw_dialog(im, key, text, shown, now, hint=None, rect=(6, 164, 314, 238)):
    AUDIO.talk(key, text, shown)
    d = ImageDraw.Draw(im)
    draw_box(d, rect)
    x0, y0, x1, y1 = rect
    tx = x0 + 10
    if key in CHAR_DEFS or key in PETS:
        p = portrait(key)
        px, py = x0 + 9, y0 + 12
        d.rectangle([px - 2, py - 2, px + p.width + 1, py + p.height + 1], fill=(34, 46, 70), outline=NAVY)
        im.paste(p, (px, py), p)
        tx = px + p.width + 10
        name = PET_NAMES[key] if key in PETS else CHAR_DEFS[key]["name"]
        w = d.textlength(name, font=F_B) + 12
        d.rounded_rectangle([x0 + 8, y0 - 7, x0 + 8 + w, y0 + 7], radius=3, fill=NAVY) if hasattr(d, "rounded_rectangle") \
            else d.rectangle([x0 + 8, y0 - 7, x0 + 8 + w, y0 + 7], fill=NAVY)
        d.text((x0 + 14, y0 - 6), name, font=F_B, fill=WHITE)
    lines = wrap(d, text, F_M, x1 - 10 - tx)
    rem = shown
    for i, ln in enumerate(lines[:4]):
        if rem <= 0:
            break
        d.text((tx, y0 + 11 + i * 12), ln[:rem], font=F_M, fill=TXT)
        rem -= len(ln) + 1
    done = shown >= len(text)
    if hint and done:
        d.text((tx, y1 - 13), hint, font=F_S, fill=(110, 110, 145))
    if done and int(now * 3) % 2 == 0 and not hint:
        d.polygon([(x1 - 20, y1 - 14), (x1 - 12, y1 - 14), (x1 - 16, y1 - 8)], fill=NAVY)
    return done


def draw_choices(d, choices, sel, anchor=(226, 156)):
    w = max(88, int(max(d.textlength(c, font=F_B) for c in choices)) + 30)
    anchor = (min(anchor[0], W - 6 - w), anchor[1])
    hh = len(choices) * 16 + 10
    x0, y1 = anchor[0], anchor[1]
    y0 = y1 - hh
    draw_box(d, (x0, y0, x0 + w, y1))
    for i, c in enumerate(choices):
        if i == sel:
            d.polygon([(x0 + 9, y0 + 9 + i * 16), (x0 + 9, y0 + 17 + i * 16), (x0 + 15, y0 + 13 + i * 16)], fill=NAVY)
        d.text((x0 + 20, y0 + 7 + i * 16), c, font=F_B, fill=TXT)


def draw_talk_bubble(d, x, y):
    """Little '...' bubble over someone you can talk to (Pokemon-style)."""
    d.rectangle([x, y, x + 10, y + 6], fill=WHITE, outline=NAVY)
    d.polygon([(x + 3, y + 6), (x + 6, y + 6), (x + 4, y + 9)], fill=WHITE, outline=NAVY)
    for i in range(3):
        d.point((x + 3 + i * 2, y + 3), fill=NAVY)


def draw_trophy(d, cx, cy, col):
    dk = tuple(max(0, c - 90) for c in col)
    d.pieslice([cx - 6, cy - 9, cx + 6, cy + 3], 0, 180, fill=col, outline=dk)
    d.rectangle([cx - 6, cy - 7, cx + 6, cy - 3], fill=col)
    d.arc([cx - 9, cy - 7, cx - 3, cy - 1], 90, 270, fill=dk)
    d.arc([cx + 3, cy - 7, cx + 9, cy - 1], 270, 90, fill=dk)
    d.rectangle([cx - 1, cy + 2, cx + 1, cy + 5], fill=dk)
    d.rectangle([cx - 4, cy + 5, cx + 4, cy + 7], fill=col, outline=dk)


# ---------------- study room ----------------
# flashcards: (question, [correct, wrong, wrong]); a card is "mastered" after 3 right answers
CARDS = [
    ("What unit measures voltage?", ["Volts", "Amps", "Ohms"]),
    ("What unit measures current?", ["Amps", "Volts", "Watts"]),
    ("What unit measures resistance?", ["Ohms", "Volts", "Amps"]),
    ("Ohm's law: Voltage = Current x ...", ["Resistance", "Watts", "Time"]),
    ("A DIP switch is a row of tiny...", ["Switches", "Lights", "Batteries"]),
    ("A push button connects the circuit only while you...", ["Hold it down", "Look at it", "Unplug it"]),
    ("What does LED stand for?", ["Light Emitting Diode", "Little Electric Dot", "Low Energy Device"]),
    ("The long leg of an LED is the...", ["+ side", "- side", "Middle"]),
    ("A complete loop that current can flow around is a...", ["Circuit", "Fuse", "Magnet"]),
    ("A circuit with a break in it is called...", ["Open", "Closed", "Short"]),
    ("A wire going straight from + to - is a...", ["Short circuit", "Series", "Parallel"]),
    ("Which material conducts electricity best?", ["Copper", "Rubber", "Wood"]),
    ("Rubber and plastic are good...", ["Insulators", "Conductors", "Batteries"]),
    ("A battery turns chemical energy into...", ["Electricity", "Sound", "Water"]),
    ("A vibe motor buzzes because it spins a...", ["Lopsided weight", "Tiny speaker", "Battery"]),
    ("Electrical power is measured in...", ["Watts", "Volts", "Ohms"]),
    ("The flow of electric charge is called...", ["Current", "Voltage", "Resistance"]),
    ("The 'push' that moves electrons is...", ["Voltage", "Current", "Friction"]),
    ("Resistors in series...", ["Add up", "Cancel out", "Disappear"]),
    ("Adding parallel paths makes total resistance...", ["Smaller", "Bigger", "Exactly zero"]),
    ("A US wall outlet gives about...", ["120 volts", "5 volts", "9 volts"]),
    ("A USB port gives about...", ["5 volts", "120 volts", "1000 volts"]),
    ("A laser makes a very narrow beam of...", ["Light", "Sound", "Water"]),
    ("A fan is really a DC motor with...", ["Blades", "Wheels", "Lights"]),
    ("How many legs does a potentiometer have?", ["Three", "Two", "Five"]),
    ("Which particle moves through a wire?", ["Electron", "Proton", "Neutron"]),
    ("Electrons have what kind of charge?", ["Negative", "Positive", "None"]),
    ("Two charges that are the same will...", ["Repel", "Attract", "Melt"]),
    ("Who is famous for the light bulb?", ["Edison", "Newton", "Darwin"]),
    ("Who flew a kite in a storm to study lightning?", ["Ben Franklin", "Einstein", "Tesla"]),
    ("Nikola Tesla championed which kind of current?", ["AC", "DC", "Static"]),
    ("Batteries give which kind of current?", ["DC", "AC", "Wi-Fi"]),
    ("A coil of wire with current through it makes an...", ["Electromagnet", "Insulator", "LED"]),
    ("A motor turns electricity into...", ["Motion", "Light", "Water"]),
    ("A speaker turns electricity into...", ["Sound", "Light", "Cold"]),
    ("Solar panels turn sunlight into...", ["Electricity", "Water", "Wind"]),
    ("On a resistor, the color for 0 is...", ["Black", "Red", "Gold"]),
    ("On a resistor, the color for 2 is...", ["Red", "Blue", "Green"]),
    ("The long rails on a breadboard are for...", ["Power", "Music", "Glue"]),
    ("What tool measures volts and amps?", ["Multimeter", "Thermometer", "Compass"]),
    ("Lightning is a giant...", ["Electric spark", "Magnet", "Battery"]),
    ("Which planet acts like a giant magnet?", ["Earth", "The Moon", "None"]),
]
# lesson books: read a chapter at a book stand, then its flashcards unlock at the flashcard desks.
# page = (text, key word, picture) - picture is a draw_art list (140x90 canvas) or a name for draw_book_art
CHAPTERS = [
    dict(title="What Is Electricity?", cards=[25, 26, 27, 16, 17, 40], pages=[
        ("Everything is made of tiny atoms. Atoms have even tinier parts called ELECTRONS. "
         "Electrons have a NEGATIVE charge.", "ELECTRON", "atom"),
        ("Charges that are the same push apart - they REPEL. Opposite charges pull together - they ATTRACT. "
         "A bit like magnets!", "REPEL / ATTRACT", "magnet"),
        ("When electrons flow through a wire, that flow is called CURRENT. The push that makes them "
         "move is called VOLTAGE.", "CURRENT + VOLTAGE", [("wire", (15, 45), (125, 45), "red")]),
        ("Lightning is a giant electric spark! Billions of electrons jump from the clouds to the "
         "ground all at once.", "LIGHTNING", "bolt"),
    ]),
    dict(title="Circuits", cards=[8, 9, 10, 11, 12, 38], pages=[
        ("A CIRCUIT is a complete loop. Electricity flows out of the battery, through the parts, "
         "and back home again.", "CIRCUIT",
         [("wire", (20, 20), (120, 20), "red"), ("wire", (120, 20), (120, 70), "red"),
          ("wire", (20, 70), (120, 70), "black"), ("wire", (20, 20), (20, 70), "black"), ("led", 70, 70, "yellow")]),
        ("If the loop has a gap, nothing works. That is an OPEN circuit. A switch simply opens and "
         "closes the loop.", "OPEN / CLOSED", [("button", 70, 45)]),
        ("A wire going straight from + to - with nothing in between is a SHORT CIRCUIT. It gets "
         "very hot. Never do it!", "SHORT CIRCUIT",
         [("wire", (20, 30), (120, 30), "red"), ("wire", (20, 60), (120, 60), "black"), ("wire", (120, 30), (120, 60), "yellow")]),
        ("CONDUCTORS like copper let electricity flow. INSULATORS like rubber and plastic block it. "
         "On a breadboard, the long rails carry power.", "CONDUCTOR",
         [("wire", (15, 30), (125, 30), "yellow"), ("wire", (15, 60), (125, 60), "blue")]),
    ]),
    dict(title="Volts, Amps and Ohms", cards=[0, 1, 2, 3, 15, 39], pages=[
        ("VOLTAGE is the push, measured in VOLTS. Think of it like the water pressure in a garden hose.",
         "VOLTS", "battery"),
        ("CURRENT is how much electricity flows, measured in AMPS. Like how much water comes out of the hose.",
         "AMPS", [("wire", (15, 45), (125, 45), "blue")]),
        ("RESISTANCE slows the flow, measured in OHMS. Ohm's law links them: "
         "Voltage = Current x Resistance.", "V = I x R", [("resistor", 70, 45)]),
        ("POWER is measured in WATTS. To measure volts and amps for real, engineers use a MULTIMETER.",
         "MULTIMETER", "meter"),
    ]),
    dict(title="LEDs and Resistors", cards=[6, 7, 36, 37, 18, 19], pages=[
        ("LED stands for Light Emitting Diode. It glows when current flows through it the right way.",
         "LED", [("led", 70, 45, "green")]),
        ("An LED's LONG leg is the + side. Put it in backwards and it just stays dark.",
         "LONG LEG = +", [("led", 70, 45, "red")]),
        ("A RESISTOR protects the LED from too much current. Its color stripes tell its value: "
         "black = 0, brown = 1, red = 2.", "COLOR STRIPES", [("resistor", 70, 45)]),
        ("Resistors in SERIES (one after another) add up. More PARALLEL paths make the total "
         "resistance smaller.", "SERIES / PARALLEL", [("resistor", 40, 45), ("resistor", 100, 45)]),
    ]),
    dict(title="Your Parts Kit", cards=[4, 5, 22, 23, 24, 14], pages=[
        ("A DIP SWITCH is a row of tiny switches in one little block. Flip each one ON or OFF with a fingernail!",
         "DIP SWITCH", [("dip", 70, 45)]),
        ("A BUTTON only connects the circuit while you press it. Let go and the circuit opens again.",
         "BUTTON", [("button", 70, 45)]),
        ("A SLIDE POT is a resistor with a slider. Slide it to make things brighter, dimmer, faster or slower.",
         "SLIDE POT", [("pot", 70, 45)]),
        ("A LASER makes a super-narrow beam of light. Super cool - but never point it at anyone's eyes!",
         "LASER", [("laser", 60, 50)]),
    ]),
    dict(title="Power and Energy", cards=[13, 31, 30, 20, 21, 35], pages=[
        ("A BATTERY turns chemical energy into electricity. It gives DC: current that flows one way.",
         "BATTERY = DC", "battery"),
        ("Wall outlets give AC: current that flips direction many times a second. Nikola Tesla "
         "championed AC!", "AC", "plug"),
        ("A US wall outlet gives about 120 volts - dangerous! A USB port gives a safe 5 volts.",
         "120V vs 5V", "plug"),
        ("SOLAR PANELS turn sunlight into electricity. Clean power, straight from the sun!",
         "SOLAR", "sun"),
    ]),
    dict(title="Magnets, Motors, Inventors", cards=[32, 33, 34, 41, 28, 29], pages=[
        ("Coil a wire and run current through it: you made an ELECTROMAGNET! The Earth itself is a "
         "giant magnet too.", "ELECTROMAGNET", "magnet"),
        ("A DC MOTOR spins when power flows. A FAN is a motor with blades, and a VIBE MOTOR spins a wobbly weight.",
         "MOTORS", [("motor", 40, 45), ("vibe", 104, 45)]),
        ("Thomas EDISON is famous for the light bulb. Ben FRANKLIN flew a kite in a storm to study "
         "lightning.", "INVENTORS", "bulb"),
        ("Now YOU are an inventor too! Every circuit you fixed in this facility used these ideas.",
         "YOU!", "star"),
    ]),
]
FOCUS_LINES = [
    "You've got this, Jaslyne. One page at a time.",
    "I'm right here studying with you. Kind of. In spirit.",
    "Deep breath. Sip some water. Keep going!",
    "Every minute counts. Future-you says thank you!",
    "Phone face-down? Good. I'm proud of you.",
    "Halfway feels far, but you're closer than you think.",
    "Smart AND pretty? Unfair advantage, honestly.",
    "If you get stuck, skip it and come back. That's allowed!",
    "The lamp is warm, the room is quiet. Perfect study vibes.",
    "After this, you deserve a snack. Or two.",
]
FOCUS_OPTIONS = [10, 25, 45, 60]
EXIT_CHOICES = ("NOT NOW", "EXIT", "SKIP", "SKIP TOUR")   # a choice list ending in one of these can be left with LEFT

# ---------------- welcome tour ----------------
# Gio shows her around the Workshop right after the opening story. Each step: what Gio says, then a goal
# she has to actually do (goal, target tile, objective shown at the top of the screen).
TOUR_INTRO = [
    ("gio", "Okay, this is SO cool. I've always wanted to see inside Volta Labs!"),
    ("jas", "Me too! Look - someone's waiting for us over by that big door."),
    ("silas", "Evening, you two! I'm Silas, night security. I'll start your tour. Ready?"),
]
TOUR = [   # goal: reach / talk / search / menu / room / finale ; npc = who to talk to
    dict(room="z0", goal="reach", target=(7, 11), objective="Walk to the yellow arrow",
         say=[("silas", "First, the basics. Use the ARROW buttons to walk around. Hold one down to jog!"),
              ("silas", "See that bouncing yellow arrow on the floor? Walk over to it.")]),
    dict(room="z0", goal="talk", npc="silas", target=None, objective="Walk next to Silas and press CENTER",
         say=[("silas", "Nicely done! Now come over and talk to me: walk right next to me and press CENTER."),
              ("gio", "CENTER is like the 'do stuff' button. You don't even have to face him perfectly.")]),
    dict(room="z0", goal="search", target=(3, 4), objective="Search the crate with the arrow (CENTER)",
         say=[("silas", "There you go! CENTER talks to people. It also uses machines and searches things."),
              ("silas", "This Workshop is full of spare parts. Desks, crates and shelves often hide BOLTS - that's money here."),
              ("silas", "Unsearched spots sparkle. Go check that crate with the arrow: face it and press CENTER.")]),
    dict(room="z0", goal="menu", target=None, objective="Press CENTER on empty floor, then LEFT to close",
         say=[("silas", "Ha! Finders keepers. The bolt number at the top of the screen shows how many you've got."),
              ("silas", "Tess runs a little shop in the top-left corner - you can spend Bolts there."),
              ("silas", "Now open your MENU: stand where nothing is next to you and press CENTER. Press LEFT to close it.")]),
    dict(room="z0", goal="room", target=(18, 7), dest="z1", objective="Go through the big door on the right",
         say=[("silas", "Your menu has your quests, trophies, bag, outfits and saving. Handy!"),
              ("silas", "The door on the left is the Study Room, if you ever want to learn more about electronics."),
              ("silas", "That's my part of the tour! Dr. Vex is waiting in the Lab, through the big door on the right.")]),
    dict(room="z1", goal="finale", npc="vex", target=None, objective="Talk to Dr. Vex",
         say=[("gio", "Whoa, check out all these machines!"),
              ("jas", "That must be Dr. Vex. Let's go say hi!")]),
]
TOUR_FINALE = [
    ("vex", "Welcome, welcome! I'm Dr. Vex. This is the Lab, where we build and test circuits."),
    ("vex", "See those glowing terminals on the wall? Each one runs part of the building's power."),
    ("vex", "And this whole building is run by our AI. Say hello, MAX!"),
    ("max", "HELLO, VISITORS. WELCOME TO VOLTA LABS. I KEEP EVERYONE HERE SAFE."),
    ("gio", "Hi MAX! ...Hey, did anyone else hear thunder just now?"),
    ("vex", "Oh, just a little storm. Nothing to worry about. Now, where was I..."),
]
WAKE_LINES = [
    ("gio", "Jaslyne! You're okay! Lightning hit the generator, and MAX locked every single door."),
    ("gio", "The surge fried the circuit boards too. If we fix them, the power comes back room by room, all the way to the roof."),
    ("gio", "See the terminal with the bouncing ! ? Walk up to it and press CENTER. I'll walk you through every step."),
    ("gio", "And remember what Silas showed us: search stuff for Bolts, and CENTER on empty floor opens the menu."),
]
TOUR_REWARD = 10
TOUR_CHAT = {   # what the staff say if she chats with them mid-tour
    "silas": "Enjoying the tour? Volta Labs is even cooler than it looks from outside.",
    "vex": "Ah, our visitors! Please, have a look around.",
    "bolt": "BEEP! Welcome, visitors! I am Bolt, the Lab's helper robot. BEEP BOOP!",
    "page": "Welcome to the Study Room! Feel free to come back and study any time.",
    "riddle": "BZZT! Puzzles! I love visitors who love puzzles!",
}
def draw_book_art(d, key, cx, cy):
    if key == "atom":
        for box in ((cx - 30, cy - 10, cx + 30, cy + 10), (cx - 10, cy - 30, cx + 10, cy + 30)):
            d.ellipse(box, outline=(60, 120, 200), width=2)
        d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(230, 80, 80), outline=(0, 0, 0))
        for ex, ey in ((cx + 30, cy), (cx, cy - 30), (cx - 21, cy + 7)):
            d.ellipse([ex - 4, ey - 4, ex + 4, ey + 4], fill=(60, 160, 255), outline=(0, 0, 0))
    elif key == "magnet":
        d.arc([cx - 26, cy - 26, cx + 26, cy + 26], 180, 360, fill=(220, 50, 50), width=12)
        d.rectangle([cx - 26, cy, cx - 14, cy + 22], fill=(220, 50, 50))
        d.rectangle([cx + 14, cy, cx + 26, cy + 22], fill=(220, 50, 50))
        d.rectangle([cx - 26, cy + 16, cx - 14, cy + 26], fill=(200, 200, 210))
        d.rectangle([cx + 14, cy + 16, cx + 26, cy + 26], fill=(200, 200, 210))
    elif key == "bolt":
        draw_bolt(d, cx, cy, 5.0)
    elif key == "battery":
        d.rectangle([cx - 30, cy - 14, cx + 26, cy + 14], fill=(40, 40, 46), outline=(0, 0, 0))
        d.rectangle([cx + 2, cy - 14, cx + 26, cy + 14], fill=(240, 180, 40), outline=(0, 0, 0))
        d.rectangle([cx + 26, cy - 5, cx + 32, cy + 5], fill=(200, 200, 210), outline=(0, 0, 0))
        d.text((cx + 10, cy - 6), "+", font=F_B, fill=(0, 0, 0))
        d.text((cx - 22, cy - 6), "-", font=F_B, fill=WHITE)
    elif key == "meter":
        draw_tool_icon(d, "multimeter", cx, cy)
    elif key == "plug":
        d.rounded_rectangle([cx - 18, cy - 10, cx + 18, cy + 26], radius=6, fill=(235, 235, 240), outline=(0, 0, 0))
        d.rectangle([cx - 10, cy - 26, cx - 5, cy - 10], fill=(200, 170, 60), outline=(0, 0, 0))
        d.rectangle([cx + 5, cy - 26, cx + 10, cy - 10], fill=(200, 170, 60), outline=(0, 0, 0))
    elif key == "sun":
        for i in range(12):
            a = i * math.pi / 6
            d.line([(cx + 22 * math.cos(a), cy + 22 * math.sin(a)), (cx + 34 * math.cos(a), cy + 34 * math.sin(a))],
                   fill=ORANGE, width=3)
        d.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], fill=YELLOW, outline=(160, 110, 0))
    elif key == "fuse":
        d.rectangle([cx - 30, cy - 10, cx + 30, cy + 10], fill=(220, 240, 250), outline=(80, 100, 120))
        d.rectangle([cx - 38, cy - 12, cx - 28, cy + 12], fill=(190, 190, 200), outline=(0, 0, 0))
        d.rectangle([cx + 28, cy - 12, cx + 38, cy + 12], fill=(190, 190, 200), outline=(0, 0, 0))
        d.line([(cx - 28, cy), (cx - 4, cy - 4), (cx + 4, cy + 4), (cx + 28, cy)], fill=(120, 90, 40), width=2)
    elif key == "bulb":
        d.ellipse([cx - 20, cy - 32, cx + 20, cy + 8], fill=YELLOW, outline=(160, 110, 0), width=2)
        d.rectangle([cx - 10, cy + 6, cx + 10, cy + 22], fill=(180, 180, 190), outline=(0, 0, 0))
        d.line([(cx - 6, cy - 6), (cx, cy - 16), (cx + 6, cy - 6)], fill=(160, 110, 0), width=2)
    elif key == "star":
        draw_star(d, cx, cy, 30, YELLOW)


STUDY_KEYS = ("read", "story", "cards", "card_sessions", "perfect_rounds", "focus_sessions", "focus_min", "pipes", "lights", "endless")

# ---------------- puzzle lab ----------------
PUZZLES_PER_KIND = 40
PN, PE, PS, PW = 1, 2, 4, 8
PIPE_DIRS = {PN: (0, -1), PE: (1, 0), PS: (0, 1), PW: (-1, 0)}
PIPE_OPP = {PN: PS, PE: PW, PS: PN, PW: PE}


def rot_cw(m):
    return ((m << 1) | (m >> 3)) & 15


def make_pipe(n, seed):
    """Net-style pipe puzzle: rotate tiles so power runs from the battery (left) to the bulb (right)."""
    r = random.Random(seed)
    w, h = min(8, 3 + n // 5), min(6, 2 + n // 7)   # puzzle 1 is a tiny 3x2
    sy, ty = r.randrange(h), r.randrange(h)
    sol = [[0] * w for _ in range(h)]
    seen, stack = {(0, sy)}, [(0, sy)]
    while stack:   # random spanning tree, so there is always a path
        x, y = stack[-1]
        nb = [(dd, x + dx, y + dy) for dd, (dx, dy) in PIPE_DIRS.items()
              if 0 <= x + dx < w and 0 <= y + dy < h and (x + dx, y + dy) not in seen]
        if not nb:
            stack.pop()
            continue
        dd, nx, ny = r.choice(nb)
        sol[y][x] |= dd
        sol[ny][nx] |= PIPE_OPP[dd]
        seen.add((nx, ny))
        stack.append((nx, ny))
    sol[sy][0] |= PW
    sol[ty][w - 1] |= PE
    while True:
        grid, par = [], 0
        for y in range(h):
            row = []
            for x in range(w):
                m = sol[y][x]
                for _ in range(r.randrange(4)):
                    m = rot_cw(m)
                k, mm = 0, m
                while mm != sol[y][x]:
                    mm, k = rot_cw(mm), k + 1
                par += k
                row.append(m)
            grid.append(row)
        pz = dict(w=w, h=h, sy=sy, ty=ty, grid=grid, par=par, sol=sol)
        if not puzzle_solved(dict(pz, kind="pipe")):
            return pz


def pipe_flow(pz):
    g, w, h, sy = pz["grid"], pz["w"], pz["h"], pz["sy"]
    if not g[sy][0] & PW:
        return set()
    seen, st = {(0, sy)}, [(0, sy)]
    while st:
        x, y = st.pop()
        for dd, (dx, dy) in PIPE_DIRS.items():
            nx, ny = x + dx, y + dy
            if g[y][x] & dd and 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and g[ny][nx] & PIPE_OPP[dd]:
                seen.add((nx, ny))
                st.append((nx, ny))
    return seen


def lights_press(g, x, y):
    h, w = len(g), len(g[0])
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        if 0 <= x + dx < w and 0 <= y + dy < h:
            g[y + dy][x + dx] = not g[y + dy][x + dx]


def make_lights(n, seed):
    """Light grid: pressing a bulb flips it and its neighbours. Turn every bulb ON."""
    r = random.Random(seed)
    s = 3 if n < 8 else 4 if n < 20 else 5 if n < 32 else 6
    k = min(s * s - 2, 1 + n // 3)   # puzzle 1 needs just one press
    while True:
        g = [[True] * s for _ in range(s)]
        for i in r.sample(range(s * s), k):
            lights_press(g, i % s, i // s)
        pz = dict(w=s, h=s, grid=g, par=k)
        if not puzzle_solved(dict(pz, kind="lights")):
            return pz


def puzzle_solved(pz):
    if pz["kind"] == "pipe":
        return (pz["w"] - 1, pz["ty"]) in pipe_flow(pz) and pz["grid"][pz["ty"]][pz["w"] - 1] & PE
    return all(all(row) for row in pz["grid"])


def puzzle_stars(moves, par):
    return 3 if moves <= par else 2 if moves <= par * 2 + 2 else 1


# ---------------- free build workbench ----------------
# A real (simplified) circuit checker: 3 rows run side by side (parallel) from the + rail to the - rail,
# each row has 5 slots in a line (series). Every slot must be filled for current to flow.
SB_ROWS, SB_COLS = 3, 5
SB_PARTS = [  # id, name, kind
    ("wire", "Wire", "wire"), ("resistor", "Resistor", "limit"),
    ("led_red", "Red LED", "led"), ("led_green", "Green LED", "led"), ("led_blue", "Blue LED", "led"),
    ("led_yellow", "Yellow LED", "led"), ("led_white", "White LED", "led"),
    ("button", "Button", "toggle"), ("dip", "DIP switch", "toggle"), ("pot", "Slide pot", "limit"),
    ("vibe", "Vibe motor", "load"), ("motor", "DC motor", "load"),
    ("laser", "Laser", "load"),
]
SB_BY_ID = {p[0]: p for p in SB_PARTS}
LED_COLORS = ["red", "green", "blue", "yellow", "white"]


def sb_kind(pid):
    return SB_BY_ID[pid][2]


def sb_polar(pid):
    return sb_kind(pid) == "led"


def sb_eval_row(row):
    """-> (status, message, working loads, all part ids)"""
    parts = [c["p"] for c in row if c]
    if not parts:
        return "empty", "Empty row. Put parts here to build a circuit!", [], parts
    if len(parts) < len(row):
        return "open", "There's a GAP in this row. Every slot needs a part - use a Wire to fill one!", [], parts
    for c in row:
        if sb_kind(c["p"]) == "toggle" and not c["on"]:
            return "open", "The %s is OFF, so the loop is broken. Select it and turn it ON." % SB_BY_ID[c["p"]][1].lower(), [], parts
    loads = [p for p in parts if sb_kind(p) in ("led", "load")]
    for c in row:
        if sb_polar(c["p"]) and c["flip"]:
            return "blocked", "The %s is BACKWARDS, so current can't get through. Select it and FLIP it." % SB_BY_ID[c["p"]][1], [], parts
    limit = any(sb_kind(p) == "limit" for p in parts)
    leds = [p for p in parts if sb_kind(p) == "led"]
    big = [p for p in parts if p in ("fan", "vibe", "motor", "laser")]
    if sum(2.0 if p in ("led_red", "led_yellow") else 3.0 for p in leds) > 4.5:
        return "toomany", ("Those LEDs need more voltage together than our 5 volts. Two red or yellow LEDs fit "
                           "in one row - put the others on another row!"), [], parts
    if big and leds:
        return "weak", ("An LED only lets a tiny trickle of current through - not enough for the %s. "
                        "Give it its own row!" % SB_BY_ID[big[0]][1].lower()), [], parts
    if big and limit:
        return "weak", ("The resistor or slide pot blocks too much current for the %s. Motors and lasers "
                        "don't need one - take it out!" % SB_BY_ID[big[0]][1].lower()), [], parts
    if not loads and not limit:
        return "short", "SHORT CIRCUIT! Only wires from + to -. Add a resistor or something to power!", [], parts
    if not loads:
        return "noload", "Current flows, but there's nothing to see. Add an LED, motor, fan or laser!", [], parts
    if any(sb_kind(p) == "led" for p in loads) and not limit:
        return "burn", "POP! The LED burned out - too much current. Add a RESISTOR to the same row.", [], parts
    names = ", ".join(SB_BY_ID[p][1] for p in loads)
    return "on", "IT WORKS! Powered: %s." % names, loads, parts


def sb_eval(grid):
    rows = [sb_eval_row(r) for r in grid]
    if any(r[0] == "short" for r in rows):   # a short drains the battery for every row
        rows = [r if r[0] != "on" else ("dead", "Nothing works: a SHORT CIRCUIT in another row is draining all the power!", [], r[3])
                for r in rows]
    return rows


def sb_lit(rows):
    return [p[4:] for s, _, loads, _ in rows if s == "on" for p in loads if p.startswith("led")]


def sb_has(rows, pid):
    return any(pid in loads for s, _, loads, _ in rows if s == "on")


def sb_row(rows, needs):
    """A working row that contains every needed part ('led' matches any LED)."""
    for s, _, _, parts in rows:
        if s == "on" and all(any(p == n or (n == "led" and p.startswith("led")) for p in parts) for n in needs):
            return True
    return False


JOB_GIVERS = ["gio", "vex", "master", "pixel", "ada", "flora", "skye", "silas", "tess", "page", "bolt"]


def make_job(seed):
    """Endless build requests. Returns (giver, text, check(rows), reward)."""
    r = random.Random(seed)
    c1 = r.choice(LED_COLORS)
    c2 = r.choice([c for c in LED_COLORS if c != c1])
    n = r.randint(2, 3)
    lit_rows = lambda R: [l for s, _, l, _ in R if s == "on" and any(p.startswith("led") for p in l)]
    jobs = [
        ("Light up a %s LED." % c1, lambda R: c1 in sb_lit(R), 8),
        ("Light %d LEDs at the same time." % n, lambda R: len(sb_lit(R)) >= n, 10),
        ("Safety lock: a DIP SWITCH and a BUTTON in the same row lighting an LED.",
         lambda R: sb_row(R, ["dip", "button", "led"]), 14),
        ("Make a vibe motor buzz.", lambda R: sb_has(R, "vibe"), 8),
        ("Spin a DC motor.", lambda R: sb_has(R, "motor"), 8),
        ("Fire a laser!", lambda R: sb_has(R, "laser"), 8),
        ("Use a BUTTON to light a %s LED." % c1, lambda R: sb_row(R, ["button", "led_" + c1]), 12),
        ("Use a DIP SWITCH to light a %s LED." % c1, lambda R: sb_row(R, ["dip", "led_" + c1]), 12),
        ("Make a pager: a BUTTON that buzzes a vibe motor.", lambda R: sb_row(R, ["button", "vibe"]), 12),
        ("Laser trap: a laser you turn on with a DIP SWITCH.", lambda R: sb_row(R, ["dip", "laser"]), 12),
        ("Put 2 LEDs in PARALLEL (on two different rows) and light them.", lambda R: len(lit_rows(R)) >= 2, 14),
        ("Light an LED and spin a motor on SEPARATE rows.",
         lambda R: bool(lit_rows(R)) and any(s == "on" and "motor" in l and not any(p.startswith("led") for p in l)
                                             for s, _, l, _ in R), 14),
        ("Fire a laser and light an LED on SEPARATE rows.",
         lambda R: bool(lit_rows(R)) and any(s == "on" and "laser" in l and not any(p.startswith("led") for p in l)
                                             for s, _, l, _ in R), 14),
        ("Make a dimmer: an LED with a SLIDE POT in its row.", lambda R: sb_row(R, ["pot", "led"]), 12),
        ("Make a pump: a DC motor you switch on with a DIP SWITCH.", lambda R: sb_row(R, ["dip", "motor"]), 12),
        ("A vibe motor and a red LED, each on its own row.", lambda R: sb_has(R, "vibe") and "red" in sb_lit(R), 14),
        ("Light a %s LED and a %s LED together." % (c1, c2), lambda R: c1 in sb_lit(R) and c2 in sb_lit(R), 12),
        ("Make a rainbow! Light red, green AND blue LEDs.",
         lambda R: all(c in sb_lit(R) for c in ("red", "green", "blue")), 18),
        ("Everything at once: a vibe motor, a DC motor AND a laser all running.",
         lambda R: all(sb_has(R, p) for p in ("vibe", "motor", "laser")), 20),
    ]
    text, check, reward = r.choice(jobs)
    return r.choice(JOB_GIVERS), text, check, reward


# ---------------- her room: furniture ----------------
# Furniture for her room (and, after the story, every room). Shop tabs follow FURN_THEMES.
FURN_THEMES = ["Home", "Living Room", "Bedroom", "Kitchen", "Bathroom", "Walls & Floors",
               "Sweet", "Kitty", "Dogs", "Wizard", "Buddies", "Garden", "Retro", "Game Room", "Starry", "Beach",
               "Spa", "Library", "Plants", "Halloween", "Christmas", "Valentine's", "Easter",
               "Lunar New Year", "Summer", "Fall", "Party"]
HOLIDAY_THEMES = {"Halloween", "Christmas", "Valentine's", "Easter", "Lunar New Year", "Summer", "Fall",
                  "Party"}
# hand-drawn pieces - id: (name, cost, solid, theme)
FURNITURE = {
    "bed": ("Comfy Bed", 30, True, "Home"), "rug_pink": ("Pink Rug", 10, False, "Sweet"),
    "rug_blue": ("Blue Rug", 10, False, "Home"), "plant": ("Potted Plant", 8, True, "Plants"),
    "lamp": ("Floor Lamp", 12, True, "Home"), "shelf": ("Bookshelf", 20, True, "Home"),
    "beanbag": ("Beanbag", 15, True, "Home"), "kitty": ("Kitty Plush", 18, True, "Kitty"),
    "bunny": ("Bunny Plush", 18, True, "Sweet"), "tv": ("Cozy TV", 40, True, "Home"),
    "desk": ("Study Desk", 20, True, "Home"), "chair": ("Chair", 8, True, "Home"),
    "flowers": ("Flower Vase", 10, True, "Garden"), "mirror": ("Mirror", 25, True, "Home"),
    "fishtank": ("Fish Tank", 45, True, "Beach"), "piano": ("Piano", 60, True, "Library"),
    "gaming": ("Gaming PC", 50, True, "Game Room"), "cake": ("Cake Stand", 15, True, "Party"),
    "starlamp": ("Star Lamp", 22, True, "Starry"), "heart_sign": ("Neon Heart", 28, True, "Retro"),
    "pumpkin": ("Jack-o-Lantern", 12, True, "Halloween"), "ghost": ("Ghost Plush", 15, True, "Halloween"),
    "xmas_tree": ("Holiday Tree", 40, True, "Christmas"), "snowman": ("Snowman", 20, True, "Christmas"),
    "heart_balloon": ("Heart Balloons", 15, True, "Valentine's"), "roses": ("Rose Bouquet", 18, True, "Valentine's"),
}
_PK, _LPK, _HPK, _WH = (255, 150, 190), (255, 205, 225), (240, 80, 150), (250, 250, 250)
_BR, _DBR, _SND, _GY, _BK = (140, 90, 55), (90, 56, 34), (235, 210, 160), (150, 150, 160), (34, 34, 40)
_GR, _DGR, _MINT, _LAV, _PUR = (70, 170, 90), (40, 110, 60), (160, 230, 200), (190, 160, 240), (140, 70, 200)
_BL, _SKY, _NV, _YL, _GO = (90, 150, 240), (160, 210, 250), (36, 40, 90), (250, 220, 60), (230, 180, 50)
_OR, _RD, _TL, _CR = (245, 150, 40), (225, 50, 60), (60, 190, 190), (248, 246, 232)
# shape-based pieces - (id, name, cost, solid, theme, shape, colour a, colour b, colour c)
FURN_SHAPED = [
    ("sofa_gray", "Gray Sofa", 35, True, "Home", "sofa", _GY, (190, 190, 200), _WH),
    ("table_wood", "Coffee Table", 15, True, "Home", "table", _BR, _DBR, _WH),
    ("rug_beige", "Beige Rug", 10, False, "Home", "rug_rect", _SND, _WH, _SND),
    ("pillow_blue", "Floor Pillow", 8, True, "Home", "cushion", _BL, _WH, _BL),
    ("bed_pink", "Princess Bed", 45, True, "Sweet", "bed2", _LPK, _PK, _WH),
    ("sofa_pink", "Pink Sofa", 35, True, "Sweet", "sofa", _PK, _LPK, _WH),
    ("teddy", "Teddy Bear", 18, True, "Sweet", "plush_round", _BR, _SND, _BK),
    ("cloud_lamp", "Cloud Lamp", 20, True, "Sweet", "cloud", _WH, _SKY, _YL),
    ("strawberry_pouf", "Strawberry Pouf", 16, True, "Sweet", "pouf", _RD, _GR, _YL),
    ("boba", "Giant Boba Cup", 14, True, "Sweet", "cup", _SND, _BK, _PK),
    ("star_pillow", "Star Pillow", 10, True, "Sweet", "cushion", _YL, _WH, _YL),
    ("kitty_pink", "Pink Kitty Plush", 18, True, "Kitty", "plush_cat", _LPK, _RD, _BK),
    ("kitty_black", "Black Kitty Plush", 18, True, "Kitty", "plush_cat", _BK, _PK, _YL),
    ("cat_tree", "Cat Tree", 30, True, "Kitty", "cattree", _SND, _BR, _PK),
    ("kitty_rug", "Kitty Bow Rug", 12, False, "Kitty", "rug_round", _WH, _RD, _PK),
    ("kitty_lamp", "Red Bow Lamp", 16, True, "Kitty", "lamp", _RD, _WH, _WH),
    ("big_bow", "Giant Red Bow", 16, True, "Kitty", "bow", _RD, _HPK, _WH),
    ("lucky_cat", "Lucky Cat", 22, True, "Kitty", "plush_cat", _WH, _GO, _RD),
    ("mushroom_stool", "Mushroom Stool", 12, True, "Garden", "mushroom", _RD, _WH, _CR),
    ("mushroom_lamp", "Mushroom Lamp", 18, True, "Garden", "mushroom", _OR, _CR, _YL),
    ("tea_table", "Tea Table", 22, True, "Garden", "table", _WH, _BR, _PK),
    ("picnic", "Picnic Basket", 12, True, "Garden", "basket", _BR, _RD, _WH),
    ("sunflower", "Sunflower Pot", 10, True, "Garden", "potplant", _BR, _GR, _YL),
    ("rose_bush", "Rose Bush", 14, True, "Garden", "bush", _DGR, _RD, _PK),
    ("quilt_bed", "Quilted Bed", 40, True, "Garden", "bed2", _BR, _GR, _CR),
    ("lava_pink", "Pink Lava Lamp", 18, True, "Retro", "lava", _PUR, _PK, _GY),
    ("lava_blue", "Blue Lava Lamp", 18, True, "Retro", "lava", _BL, _MINT, _GY),
    ("disco", "Disco Ball", 25, True, "Retro", "disco", _GY, _WH, _SKY),
    ("bfly_pink", "Butterfly Chair", 18, True, "Retro", "bchair", _PK, _HPK, _WH),
    ("blowup_chair", "Inflatable Chair", 15, True, "Retro", "bchair", _SKY, _BL, _WH),
    ("flip_phone", "Giant Flip Phone", 20, True, "Retro", "phone", _PK, _SKY, _WH),
    ("neon_star", "Neon Star", 24, True, "Retro", "neon_star", _YL, _BK, _YL),
    ("neon_moon", "Neon Moon", 24, True, "Retro", "neon_moon", _LAV, _BK, _LAV),
    ("arcade_red", "Red Arcade Machine", 45, True, "Game Room", "arcade", _RD, _BK, _YL),
    ("arcade_blue", "Blue Arcade Machine", 45, True, "Game Room", "arcade", _BL, _BK, _MINT),
    ("gchair_red", "Gaming Chair", 30, True, "Game Room", "gchair", _BK, _RD, _GY),
    ("gchair_pink", "Pink Gaming Chair", 30, True, "Game Room", "gchair", _LPK, _HPK, _WH),
    ("console", "Console + TV", 40, True, "Game Room", "tv2", _BK, _BL, _WH),
    ("neon_bolt", "Neon Lightning", 24, True, "Game Room", "neon_bolt", _TL, _BK, _TL),
    ("saturn", "Saturn Model", 25, True, "Starry", "planet", _OR, _SND, _WH),
    ("earth_model", "Earth Model", 25, True, "Starry", "planet", _BL, _GR, _WH),
    ("rocket", "Toy Rocket", 28, True, "Starry", "rocket", _WH, _RD, _GY),
    ("moon_lamp", "Moon Lamp", 22, True, "Starry", "moon", _CR, _GY, _YL),
    ("galaxy_rug", "Galaxy Rug", 14, False, "Starry", "rug_round", _NV, _PUR, _WH),
    ("astro_plush", "Astronaut Plush", 20, True, "Starry", "plush_round", _WH, _GY, _NV),
    ("palm", "Palm Tree", 30, True, "Beach", "palm", _DGR, _BR, _GR),
    ("surf_teal", "Surfboard", 20, True, "Beach", "surf", _TL, _WH, _OR),
    ("surf_pink", "Pink Surfboard", 20, True, "Beach", "surf", _PK, _WH, _YL),
    ("beachball", "Beach Ball", 8, True, "Beach", "ball", _RD, _BL, _YL),
    ("seashell", "Giant Seashell", 12, True, "Beach", "shell", _LPK, _SND, _WH),
    ("beach_chair", "Beach Chair", 15, True, "Beach", "bchair", _BL, _WH, _WH),
    ("sandcastle", "Sandcastle", 12, True, "Beach", "castle", _SND, _BR, _RD),
    ("diffuser", "Aroma Diffuser", 14, True, "Spa", "diffuser", _WH, _MINT, _WH),
    ("towels", "Fluffy Towels", 10, True, "Spa", "towels", _WH, _LPK, _MINT),
    ("candles", "Candle Set", 12, True, "Spa", "candles", _CR, _YL, _OR),
    ("vanity", "Vanity Table", 35, True, "Spa", "vanity", _WH, _PK, _SKY),
    ("bubble_tub", "Bubble Bath", 40, True, "Spa", "tub", _WH, _SKY, _WH),
    ("yoga_mat", "Yoga Mat", 8, False, "Spa", "rug_rect", _LAV, _WH, _LAV),
    ("clock", "Grandfather Clock", 40, True, "Library", "clock", _DBR, _GO, _CR),
    ("globe", "Old Globe", 25, True, "Library", "globe", _BL, _GR, _BR),
    ("books", "Book Stack", 10, True, "Library", "books", _RD, _DGR, _NV),
    ("candelabra", "Candelabra", 22, True, "Library", "candelabra", _GO, _CR, _YL),
    ("armchair", "Leather Armchair", 30, True, "Library", "sofa", _BR, _DBR, _GO),
    ("dark_shelf", "Library Shelf", 25, True, "Library", "shelf2", _DBR, _RD, _GO),
    ("cactus", "Cactus", 8, True, "Plants", "cactus", _GR, _OR, _PK),
    ("succulent", "Succulent Pot", 8, True, "Plants", "potplant", _OR, _MINT, _PK),
    ("monstera", "Big Monstera", 22, True, "Plants", "tallplant", _DGR, _BR, _GR),
    ("rattan", "Rattan Chair", 20, True, "Plants", "bchair", _SND, _BR, _WH),
    ("pampas", "Pampas Vase", 14, True, "Plants", "vase", _SND, _CR, _BR),
    ("boho_rug", "Boho Rug", 12, False, "Plants", "rug_rect", _OR, _SND, _RD),
    ("pumpkin_white", "White Pumpkin", 12, True, "Halloween", "pumpkin2", _WH, _GR, _GY),
    ("cauldron", "Bubbling Cauldron", 22, True, "Halloween", "cauldron", _BK, _GR, _PUR),
    ("skull", "Spooky Skull", 14, True, "Halloween", "skull", _WH, _BK, _GY),
    ("bat_plush", "Bat Plush", 15, True, "Halloween", "plush_bat", _BK, _PUR, _YL),
    ("candy_bowl", "Candy Bowl", 10, True, "Halloween", "bowl", _OR, _PUR, _GR),
    ("tombstone", "Tombstone", 16, True, "Halloween", "tomb", _GY, _BK, _DGR),
    ("gift_red", "Red Present", 12, True, "Christmas", "gift", _RD, _GO, _WH),
    ("gift_green", "Green Present", 12, True, "Christmas", "gift", _DGR, _RD, _WH),
    ("candy_cane", "Candy Cane", 10, True, "Christmas", "cane", _RD, _WH, _WH),
    ("fireplace", "Cozy Fireplace", 45, True, "Christmas", "fireplace", _BR, _OR, _YL),
    ("reindeer", "Reindeer Plush", 18, True, "Christmas", "plush_round", _BR, _RD, _SND),
    ("wreath", "Holiday Wreath", 14, True, "Christmas", "wreath", _DGR, _RD, _GO),
    ("heart_pillow", "Heart Pillow", 10, True, "Valentine's", "heart", _HPK, _LPK, _WH),
    ("choco_box", "Chocolate Box", 12, True, "Valentine's", "heart", _RD, _BR, _GO),
    ("love_bear", "Love Bear", 18, True, "Valentine's", "plush_round", _PK, _RD, _BK),
    ("heart_rug", "Heart Rug", 12, False, "Valentine's", "rug_round", _HPK, _LPK, _RD),
    ("egg_pink", "Pink Easter Egg", 8, True, "Easter", "egg", _PK, _YL, _WH),
    ("egg_blue", "Blue Easter Egg", 8, True, "Easter", "egg", _SKY, _LPK, _WH),
    ("egg_basket", "Egg Basket", 14, True, "Easter", "basket", _SND, _PK, _SKY),
    ("big_bunny", "Big Easter Bunny", 22, True, "Easter", "plush_long", _WH, _PK, _BK),
    ("chick", "Chick Plush", 12, True, "Easter", "plush_round", _YL, _OR, _BK),
    ("tulips", "Tulip Pot", 10, True, "Easter", "potplant", _PK, _GR, _HPK),
    ("lantern_red", "Red Lantern", 16, True, "Lunar New Year", "lantern", _RD, _GO, _YL),
    ("lantern_gold", "Gold Lantern", 16, True, "Lunar New Year", "lantern", _GO, _RD, _YL),
    ("dragon_plush", "Dragon Plush", 22, True, "Lunar New Year", "plush_round", _RD, _GO, _BK),
    ("kumquat", "Kumquat Tree", 20, True, "Lunar New Year", "potplant", _GO, _DGR, _OR),
    ("red_envelope", "Lucky Envelopes", 10, True, "Lunar New Year", "gift", _RD, _GO, _GO),
    ("flag", "Stars and Stripes Flag", 14, True, "Summer", "flag", _RD, _WH, _BL),
    ("grill", "BBQ Grill", 25, True, "Summer", "grill", _BK, _GY, _OR),
    ("cooler", "Cooler", 12, True, "Summer", "cooler", _BL, _WH, _SKY),
    ("watermelon", "Watermelon", 8, True, "Summer", "melon", _GR, _RD, _BK),
    ("pool_float", "Pool Float", 10, False, "Summer", "ring", _PK, _WH, _HPK),
    ("autumn_tree", "Autumn Tree", 30, True, "Fall", "tree", _OR, _BR, _RD),
    ("hay_bale", "Hay Bale", 10, True, "Fall", "hay", _YL, _SND, _BR),
    ("pie", "Pumpkin Pie", 10, True, "Fall", "pie", _OR, _SND, _BR),
    ("apple_basket", "Apple Basket", 12, True, "Fall", "basket", _BR, _RD, _GR),
    ("leaf_rug", "Leaf Rug", 12, False, "Fall", "rug_round", _OR, _RD, _YL),
    ("balloons", "Party Balloons", 12, True, "Party", "balloons", _PK, _BL, _YL),
    ("gift_party", "Party Present", 12, True, "Party", "gift", _PUR, _YL, _WH),
    ("cupcakes", "Cupcake Tower", 16, True, "Party", "cupcake", _PK, _WH, _RD),
    ("party_table", "Party Table", 20, True, "Party", "table", _PK, _WH, _YL),
]
_LAV2, _PEACH, _SAGE, _CREAMY, _STONE = (215, 195, 245), (255, 205, 175), (170, 200, 160), (245, 235, 215), (175, 175, 185)
_OAK, _WALNUT, _MARBLE, _BRICK, _ROSE = (200, 155, 100), (110, 70, 45), (235, 235, 240), (180, 80, 60), (235, 150, 165)
FURN_SHAPED += [
    # ----- walls & floors (floors sit under furniture; walls block like real walls)
    ("wall_white", "White Wall", 6, True, "Walls & Floors", "wall", (240, 240, 244), (210, 210, 220), _WH),
    ("wall_pink", "Pink Wall", 6, True, "Walls & Floors", "wall", _LPK, _PK, _WH),
    ("wall_lav", "Lavender Wall", 6, True, "Walls & Floors", "wall", _LAV2, _LAV, _WH),
    ("wall_mint", "Mint Wall", 6, True, "Walls & Floors", "wall", _MINT, (120, 200, 170), _WH),
    ("wall_sky", "Sky Blue Wall", 6, True, "Walls & Floors", "wall", _SKY, (120, 180, 230), _WH),
    ("wall_peach", "Peach Wall", 6, True, "Walls & Floors", "wall", _PEACH, (235, 170, 140), _WH),
    ("wall_wood", "Wood Wall", 8, True, "Walls & Floors", "wall_wood", _OAK, _WALNUT, _WH),
    ("wall_brick", "Brick Wall", 8, True, "Walls & Floors", "wall_brick", _BRICK, (230, 220, 210), _WH),
    ("wall_stone", "Stone Wall", 8, True, "Walls & Floors", "wall_brick", _STONE, (120, 120, 130), _WH),
    ("window_white", "Window", 10, True, "Walls & Floors", "window", _WH, _SKY, _WH),
    ("window_pink", "Pink Window", 10, True, "Walls & Floors", "window", _PK, _SKY, _LPK),
    ("window_curtain", "Curtained Window", 14, True, "Walls & Floors", "curtain", _WH, _SKY, _ROSE),
    ("floor_oak", "Light Wood Floor", 4, False, "Walls & Floors", "floor_wood", _OAK, (180, 135, 85), _WH),
    ("floor_walnut", "Dark Wood Floor", 4, False, "Walls & Floors", "floor_wood", _WALNUT, (90, 56, 36), _WH),
    ("floor_pink", "Pink Tile Floor", 4, False, "Walls & Floors", "floor_tile", _LPK, (240, 180, 200), _WH),
    ("floor_mint", "Mint Tile Floor", 4, False, "Walls & Floors", "floor_tile", _MINT, (140, 210, 180), _WH),
    ("floor_blue", "Blue Tile Floor", 4, False, "Walls & Floors", "floor_tile", _SKY, (130, 185, 230), _WH),
    ("floor_check", "Checker Floor", 4, False, "Walls & Floors", "floor_check", _WH, (40, 40, 46), _WH),
    ("floor_check_pink", "Pink Checker Floor", 4, False, "Walls & Floors", "floor_check", _WH, _PK, _WH),
    ("floor_marble", "Marble Floor", 5, False, "Walls & Floors", "floor_marble", _MARBLE, (200, 200, 210), _WH),
    ("carpet_pink", "Pink Carpet", 4, False, "Walls & Floors", "carpet", _PK, (240, 130, 175), _WH),
    ("carpet_lav", "Lavender Carpet", 4, False, "Walls & Floors", "carpet", _LAV2, _LAV, _WH),
    ("carpet_cream", "Cream Carpet", 4, False, "Walls & Floors", "carpet", _CREAMY, (230, 215, 190), _WH),
    ("carpet_sage", "Sage Carpet", 4, False, "Walls & Floors", "carpet", _SAGE, (150, 180, 140), _WH),
    # ----- living room
    ("sofa_blue", "Blue Sofa", 35, True, "Living Room", "sofa", _BL, _SKY, _WH),
    ("sofa_sage", "Sage Sofa", 35, True, "Living Room", "sofa", _SAGE, (200, 220, 190), _WH),
    ("sofa_cream", "Cream Sofa", 35, True, "Living Room", "sofa", _CREAMY, _WH, _PK),
    ("armchair_pink", "Pink Armchair", 25, True, "Living Room", "armchair", _PK, _LPK, _WH),
    ("armchair_gray", "Gray Armchair", 25, True, "Living Room", "armchair", _GY, (200, 200, 210), _WH),
    ("tv_stand", "TV Stand", 40, True, "Living Room", "tv2", _BK, _SKY, _WH),
    ("round_table", "Round Coffee Table", 15, True, "Living Room", "table", _WH, _OAK, _PK),
    ("bookcase_white", "White Bookcase", 25, True, "Living Room", "shelf2", _WH, _PK, _BL),
    ("lamp_gold", "Gold Floor Lamp", 16, True, "Living Room", "lamp", _GO, _CREAMY, _WH),
    ("easel", "Painting Easel", 18, True, "Living Room", "easel", _OAK, _SKY, _PK),
    ("frame_art", "Framed Art", 14, True, "Living Room", "frame", _GO, _PK, _SKY),
    # ----- bedroom
    ("canopy_pink", "Pink Canopy Bed", 60, True, "Bedroom", "canopy", _PK, _LPK, _WH),
    ("canopy_white", "White Canopy Bed", 60, True, "Bedroom", "canopy", _WH, _LAV2, _SKY),
    ("bed_blue", "Blue Bed", 40, True, "Bedroom", "bed2", _OAK, _SKY, _WH),
    ("bed_lav", "Lavender Bed", 40, True, "Bedroom", "bed2", _WH, _LAV2, _WH),
    ("wardrobe_white", "White Wardrobe", 35, True, "Bedroom", "wardrobe", _WH, (200, 200, 210), _GO),
    ("wardrobe_wood", "Wood Wardrobe", 35, True, "Bedroom", "wardrobe", _OAK, _WALNUT, _GO),
    ("dresser_pink", "Pink Dresser", 28, True, "Bedroom", "dresser", _PK, _LPK, _GO),
    ("dresser_white", "White Dresser", 28, True, "Bedroom", "dresser", _WH, (210, 210, 220), _GO),
    ("nightstand", "Nightstand", 14, True, "Bedroom", "nightstand", _OAK, _WALNUT, _YL),
    ("clothes_rack", "Clothes Rack", 22, True, "Bedroom", "rack", _GY, _PK, _SKY),
    ("full_mirror", "Standing Mirror", 25, True, "Bedroom", "vanity", _WH, _GO, _SKY),
    # ----- kitchen
    ("fridge_white", "Fridge", 40, True, "Kitchen", "fridge", _WH, (200, 200, 210), _GY),
    ("fridge_pink", "Retro Pink Fridge", 45, True, "Kitchen", "fridge", _PK, _LPK, _WH),
    ("fridge_mint", "Retro Mint Fridge", 45, True, "Kitchen", "fridge", _MINT, (200, 240, 220), _WH),
    ("stove", "Stove", 35, True, "Kitchen", "stove", _WH, _BK, _OR),
    ("kitchen_sink", "Kitchen Sink", 25, True, "Kitchen", "sink", _WH, _STONE, _SKY),
    ("counter_wood", "Wood Counter", 18, True, "Kitchen", "counter", _OAK, _WALNUT, _WH),
    ("counter_marble", "Marble Counter", 22, True, "Kitchen", "counter", _MARBLE, _GY, _WH),
    ("microwave", "Microwave", 18, True, "Kitchen", "microwave", _WH, _BK, _GR),
    ("toaster", "Toaster", 10, True, "Kitchen", "toaster", _STONE, _BK, (220, 170, 100)),
    ("coffee_maker", "Coffee Maker", 14, True, "Kitchen", "coffee", _BK, _GY, (110, 70, 45)),
    ("dining_table", "Dining Table", 25, True, "Kitchen", "table", _OAK, _WALNUT, _RD),
    ("stool_pink", "Pink Stool", 8, True, "Kitchen", "stool", _PK, _GY, _WH),
    ("stool_wood", "Wood Stool", 8, True, "Kitchen", "stool", _OAK, _WALNUT, _WH),
    ("fruit_bowl", "Fruit Bowl", 8, True, "Kitchen", "bowl", _WH, _RD, _YL),
    # ----- bathroom
    ("shower", "Shower", 40, True, "Bathroom", "shower", _WH, _SKY, _STONE),
    ("bath_sink", "Bathroom Sink", 22, True, "Bathroom", "sink", _WH, _WH, _SKY),
    ("bath_mat", "Bath Mat", 5, False, "Bathroom", "rug_rect", _MINT, _WH, _MINT),
    ("washer", "Washing Machine", 35, True, "Bathroom", "washer", _WH, _SKY, _GY),
    ("towel_pink", "Pink Towels", 10, True, "Bathroom", "towels", _LPK, _PK, _WH),
    ("bath_plant", "Bathroom Fern", 12, True, "Bathroom", "potplant", _WH, _GR, _GR),
]
_GOLDEN, _TAN, _DKFACE, _HUSKY, _CORGI = (220, 170, 90), (215, 180, 130), (70, 50, 40), (150, 155, 170), (235, 140, 60)
_BURG, _EMER, _SAPH, _BRONZE, _CANARY = (150, 30, 40), (30, 110, 60), (40, 70, 160), (190, 130, 70), (240, 200, 50)
FURN_SHAPED += [
    # ----- wizard school
    ("wizard_hat", "Wizard Hat", 14, True, "Wizard", "hat", _NV, _GO, _SKY),
    ("spellbook", "Glowing Spellbook", 16, True, "Wizard", "spellbook", _BURG, _CREAMY, (160, 255, 200)),
    ("wand_stand", "Wand Stand", 12, True, "Wizard", "wand", _WALNUT, (250, 240, 200), _GO),
    ("broom", "Flying Broom", 16, True, "Wizard", "broom", _OAK, (200, 170, 90), _BURG),
    ("owl", "Snowy Owl", 20, True, "Wizard", "owl", _WH, _YL, (60, 60, 70)),
    ("owl_brown", "Brown Owl", 20, True, "Wizard", "owl", (150, 110, 70), _OR, (60, 40, 30)),
    ("crystal_ball", "Crystal Ball", 18, True, "Wizard", "crystal", (190, 170, 255), _GO, _WH),
    ("potion_shelf", "Potion Shelf", 25, True, "Wizard", "potions", _WALNUT, (120, 230, 140), (200, 100, 240)),
    ("float_candles", "Floating Candles", 14, True, "Wizard", "candles", _CREAMY, _YL, _OR),
    ("magic_trunk", "Magic Trunk", 20, True, "Wizard", "trunk", _BURG, _GO, _WALNUT),
    ("banner_red", "Red & Gold Banner", 12, True, "Wizard", "banner", _BURG, _GO, _GO),
    ("banner_green", "Green & Silver Banner", 12, True, "Wizard", "banner", _EMER, (200, 205, 215), (200, 205, 215)),
    ("banner_blue", "Blue & Bronze Banner", 12, True, "Wizard", "banner", _SAPH, _BRONZE, _BRONZE),
    ("banner_yellow", "Yellow & Black Banner", 12, True, "Wizard", "banner", _CANARY, _BK, _BK),
    ("scarf_red", "Red & Gold Scarf Stand", 12, True, "Wizard", "scarf", _BURG, _GO, _WALNUT),
    ("wizard_rug", "Starry Wizard Rug", 14, False, "Wizard", "rug_round", _NV, _GO, _YL),
    # ----- dogs
    ("dog_golden", "Golden Pup Plush", 18, True, "Dogs", "plush_dog", _GOLDEN, _GOLDEN, _BK),
    ("dog_pug", "Pug Plush", 18, True, "Dogs", "plush_dog", _TAN, _DKFACE, _BK),
    ("dog_dalmatian", "Spotty Pup Plush", 18, True, "Dogs", "plush_dog", _WH, _BK, _BK),
    ("dog_corgi", "Corgi Plush", 18, True, "Dogs", "plush_dog", _CORGI, _WH, _BK),
    ("dog_husky", "Husky Plush", 18, True, "Dogs", "plush_dog", _HUSKY, _WH, (90, 160, 230)),
    ("dog_black", "Black Pup Plush", 18, True, "Dogs", "plush_dog", (50, 45, 50), (50, 45, 50), (230, 190, 90)),
    ("dog_bed_pink", "Pink Dog Bed", 15, True, "Dogs", "dogbed", _PK, _LPK, _WH),
    ("dog_bed_blue", "Blue Dog Bed", 15, True, "Dogs", "dogbed", _BL, _SKY, _WH),
    ("dog_house", "Dog House", 30, True, "Dogs", "doghouse", _RD, _OAK, _WH),
    ("dog_bowl", "Dog Bowl", 6, True, "Dogs", "dogbowl", _PK, (180, 120, 70), _WH),
    ("dog_bone", "Chew Bone", 5, True, "Dogs", "bone", _CREAMY, (210, 200, 180), _WH),
    ("tennis_ball", "Tennis Ball", 4, True, "Dogs", "tennis", (210, 235, 60), _WH, _WH),
    ("paw_rug", "Paw Print Rug", 12, False, "Dogs", "pawrug", _LPK, _PK, _WH),
]
_BYELLOW, _BBLUE, _BPURP = (250, 215, 40), (40, 80, 170), (130, 60, 170)
FURN_SHAPED += [
    # ----- yellow goggle buddies
    ("buddy_one", "One-Eyed Buddy Plush", 18, True, "Buddies", "buddy1", _BYELLOW, _BBLUE, (190, 190, 200)),
    ("buddy_two", "Two-Eyed Buddy Plush", 18, True, "Buddies", "buddy2", _BYELLOW, _BBLUE, (190, 190, 200)),
    ("buddy_purple", "Purple Buddy Plush", 20, True, "Buddies", "buddy2", _BPURP, (60, 50, 90), (190, 190, 200)),
    ("banana", "Giant Banana", 8, True, "Buddies", "banana", _BYELLOW, (120, 90, 30), _WH),
    ("banana_bunch", "Banana Bunch", 12, True, "Buddies", "bananas", _BYELLOW, (120, 90, 30), _WH),
    ("big_goggles", "Big Goggles", 14, True, "Buddies", "goggles", (190, 190, 200), (120, 170, 220), (60, 60, 70)),
    ("buddy_poster", "Buddy Poster", 14, True, "Buddies", "frame", _BBLUE, _BYELLOW, (250, 240, 200)),
    ("banana_rug", "Banana Rug", 12, False, "Buddies", "rug_round", _BYELLOW, _BBLUE, _WH),
    ("buddy_overalls_rug", "Overalls Rug", 12, False, "Buddies", "rug_rect", _BBLUE, _BYELLOW, _BBLUE),
    # ----- her pets as plushies
    ("plush_canica", "Canica Plush", 22, True, "Dogs", "plush_dog", (205, 145, 85), (240, 205, 160), _BK),
    ("plush_gummy", "Gummy Plush", 22, True, "Dogs", "plush_dog", (110, 115, 128), (238, 238, 242), _BK),
    ("plush_sofia", "Sofia Plush", 22, True, "Dogs", "plush_dog", (50, 50, 60), (195, 150, 100), _BK),
    ("lafufu_bowl", "Lafufu's Fish Bowl", 25, True, "Dogs", "betta_bowl", (60, 90, 220), (210, 40, 60), (110, 180, 230)),
]
FLOOR_SHAPES = {"floor_wood", "floor_tile", "floor_check", "floor_marble", "carpet"}
REMOVABLE = {"c": "crate", "d": "desk", "b": "bookshelf", "v": "vent", "r": "rug tile"}
NO_REMOVE_ROOMS = {"study", "arcade"}   # the Study Room and Puzzle Lab stay as they are
SHOP_CATS = ["OUTFITS", "TOOLS"] + FURN_THEMES


def cat_label(c):
    return c.capitalize() if c.isupper() else c
FURN_SHAPE = {}
for _fid, _name, _cost, _solid, _theme, _shape, _a, _b, _c in FURN_SHAPED:
    FURNITURE[_fid] = (_name, _cost, _solid, _theme)
    FURN_SHAPE[_fid] = (_shape, _a, _b, _c)
FLOOR_IDS = {fid for fid, v in FURN_SHAPE.items() if v[0] in FLOOR_SHAPES}
DESIGN_TOOLS = ["ITEMS", "PLACE", "MOVE", "ERASE", "UNDO", "DONE"]
CAT_COLS, CAT_ROWS = 5, 3
_thumbs = {}


def furn_thumb(fid, size):
    """Furniture picture at any size (cached) for the catalog, toolbar and live preview."""
    key = (fid, size)
    if key not in _thumbs:
        pic = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        draw_furniture(ImageDraw.Draw(pic), fid, 0, 0)
        _thumbs[key] = pic if size == 16 else pic.resize((size, size), Image.NEAREST)
    return _thumbs[key]

STORE_ITEMS += [dict(type="furniture", id=fid, name=v[0], cost=v[1], theme=v[3],
                     desc="%s decor. Buy as many as you like!" % v[3])
                for theme in FURN_THEMES for fid, v in FURNITURE.items() if v[3] == theme]


def _dk(c, n=60):
    return tuple(max(0, v - n) for v in c)


def draw_shape(d, shape, a, b, c, x, y):
    """Reusable 16x16 furniture shapes, recoloured with a/b/c."""
    o = _dk(a)
    if shape == "sofa":
        d.rectangle([x, y + 3, x + 15, y + 9], fill=a, outline=o)
        d.rectangle([x, y + 8, x + 15, y + 13], fill=b, outline=o)
        d.rectangle([x, y + 6, x + 2, y + 13], fill=a, outline=o)
        d.rectangle([x + 13, y + 6, x + 15, y + 13], fill=a, outline=o)
        d.rectangle([x + 6, y + 5, x + 9, y + 8], fill=c)
    elif shape == "table":
        d.rectangle([x, y + 6, x + 15, y + 9], fill=a, outline=_dk(a))
        d.rectangle([x + 2, y + 9, x + 3, y + 15], fill=b)
        d.rectangle([x + 12, y + 9, x + 13, y + 15], fill=b)
        d.ellipse([x + 5, y + 2, x + 10, y + 7], fill=c, outline=_dk(c))
    elif shape == "rug_rect":
        d.rectangle([x, y + 3, x + 15, y + 13], fill=a, outline=_dk(a))
        for k in (5, 8, 11):
            d.line([(x + 1, y + k), (x + 14, y + k)], fill=b)
        d.rectangle([x + 6, y + 6, x + 9, y + 10], outline=c)
    elif shape == "rug_round":
        d.ellipse([x, y + 3, x + 15, y + 13], fill=a, outline=_dk(a))
        d.ellipse([x + 3, y + 5, x + 12, y + 11], outline=b)
        d.ellipse([x + 6, y + 7, x + 9, y + 9], fill=c)
    elif shape == "cushion":
        d.rounded_rectangle([x + 2, y + 6, x + 13, y + 14], radius=3, fill=a, outline=o)
        draw_star(d, x + 8, y + 10, 3, b, outline=b) if a == c else d.line([(x + 4, y + 10), (x + 11, y + 10)], fill=b)
    elif shape == "bed2":
        d.rectangle([x, y, x + 15, y + 15], fill=a, outline=o)
        d.rectangle([x + 1, y + 6, x + 14, y + 14], fill=b)
        d.rectangle([x + 2, y + 2, x + 13, y + 5], fill=c)
        for k in range(2, 14, 4):
            d.line([(x + k, y + 7), (x + k, y + 13)], fill=_dk(b, 30))
    elif shape in ("plush_round", "plush_cat", "plush_long", "plush_bat"):
        if shape == "plush_round":
            d.ellipse([x + 2, y + 1, x + 6, y + 5], fill=a, outline=o)
            d.ellipse([x + 9, y + 1, x + 13, y + 5], fill=a, outline=o)
        elif shape == "plush_cat":
            d.polygon([(x + 3, y + 5), (x + 4, y), (x + 7, y + 3)], fill=a, outline=o)
            d.polygon([(x + 12, y + 5), (x + 11, y), (x + 8, y + 3)], fill=a, outline=o)
        elif shape == "plush_long":
            d.ellipse([x + 4, y - 3, x + 6, y + 5], fill=a, outline=o)
            d.ellipse([x + 9, y - 3, x + 11, y + 5], fill=a, outline=o)
        else:
            d.polygon([(x, y + 4), (x + 4, y + 7), (x + 1, y + 9)], fill=a)
            d.polygon([(x + 15, y + 4), (x + 11, y + 7), (x + 14, y + 9)], fill=a)
        d.ellipse([x + 3, y + 3, x + 12, y + 11], fill=a, outline=o)
        d.ellipse([x + 4, y + 9, x + 11, y + 15], fill=a, outline=o)
        d.ellipse([x + 6, y + 10, x + 9, y + 13], fill=b)
        d.point((x + 6, y + 7), fill=c)
        d.point((x + 9, y + 7), fill=c)
        if shape == "plush_cat":
            d.ellipse([x + 9, y + 1, x + 13, y + 4], fill=b)
    elif shape == "cloud":
        d.rectangle([x + 7, y + 9, x + 8, y + 15], fill=(150, 150, 160))
        for cx_, cy_, r in ((5, 6, 4), (10, 6, 4), (8, 4, 4)):
            d.ellipse([x + cx_ - r, y + cy_ - r, x + cx_ + r, y + cy_ + r], fill=a)
        d.line([(x + 3, y + 9), (x + 12, y + 9)], fill=b)
    elif shape == "pouf":
        d.ellipse([x + 1, y + 4, x + 14, y + 15], fill=a, outline=o)
        for px_, py_ in ((5, 8), (9, 7), (7, 11), (11, 11)):
            d.point((x + px_, y + py_), fill=c)
        d.polygon([(x + 5, y + 5), (x + 8, y + 2), (x + 11, y + 5)], fill=b)
    elif shape == "cup":
        d.polygon([(x + 3, y + 3), (x + 12, y + 3), (x + 11, y + 15), (x + 4, y + 15)], fill=a, outline=_dk(a))
        for px_ in (5, 8, 10):
            d.ellipse([x + px_ - 1, y + 11, x + px_ + 1, y + 13], fill=b)
        d.line([(x + 9, y), (x + 8, y + 5)], fill=c, width=2)
    elif shape == "cattree":
        d.rectangle([x + 6, y + 3, x + 9, y + 14], fill=b)
        d.rectangle([x + 1, y + 13, x + 14, y + 15], fill=a, outline=_dk(a))
        d.rectangle([x + 2, y + 1, x + 9, y + 4], fill=a, outline=_dk(a))
        d.rectangle([x + 8, y + 7, x + 14, y + 9], fill=a, outline=_dk(a))
        d.ellipse([x + 11, y + 10, x + 13, y + 12], fill=c)
    elif shape == "lamp":
        d.rectangle([x + 7, y + 6, x + 8, y + 14], fill=(80, 80, 90))
        d.rectangle([x + 4, y + 14, x + 11, y + 15], fill=(80, 80, 90))
        d.polygon([(x + 4, y + 6), (x + 11, y + 6), (x + 9, y), (x + 6, y)], fill=a, outline=o)
        d.polygon([(x + 5, y + 2), (x + 7, y + 4), (x + 5, y + 5)], fill=b)
    elif shape == "bow":
        d.polygon([(x + 8, y + 7), (x + 1, y + 2), (x + 1, y + 12)], fill=a, outline=o)
        d.polygon([(x + 8, y + 7), (x + 15, y + 2), (x + 15, y + 12)], fill=a, outline=o)
        d.ellipse([x + 6, y + 5, x + 10, y + 9], fill=b, outline=o)
    elif shape == "mushroom":
        d.rectangle([x + 5, y + 8, x + 10, y + 15], fill=b, outline=_dk(b))
        d.pieslice([x + 1, y + 1, x + 14, y + 14], 180, 360, fill=a, outline=o)
        for px_, py_ in ((4, 5), (8, 3), (11, 5)):
            d.ellipse([x + px_ - 1, y + py_ - 1, x + px_ + 1, y + py_ + 1], fill=c)
    elif shape == "basket":
        d.ellipse([x + 3, y + 5, x + 6, y + 9], fill=b)
        d.ellipse([x + 7, y + 4, x + 10, y + 8], fill=c)
        d.ellipse([x + 9, y + 6, x + 12, y + 9], fill=b)
        d.polygon([(x + 1, y + 8), (x + 14, y + 8), (x + 12, y + 15), (x + 3, y + 15)], fill=a, outline=_dk(a))
        d.arc([x + 3, y + 1, x + 12, y + 14], 180, 360, fill=_dk(a))
    elif shape == "potplant":
        d.rectangle([x + 4, y + 10, x + 11, y + 15], fill=a, outline=_dk(a))
        d.line([(x + 8, y + 10), (x + 8, y + 4)], fill=b)
        d.ellipse([x + 3, y + 5, x + 7, y + 9], fill=b)
        d.ellipse([x + 9, y + 5, x + 13, y + 9], fill=b)
        d.ellipse([x + 5, y, x + 11, y + 6], fill=c, outline=_dk(c))
    elif shape == "bush":
        d.ellipse([x, y + 3, x + 15, y + 15], fill=a, outline=_dk(a))
        for px_, py_ in ((4, 6), (10, 5), (7, 10), (12, 10), (3, 11)):
            d.ellipse([x + px_ - 1, y + py_ - 1, x + px_ + 1, y + py_ + 1], fill=b if px_ % 2 == 0 else c)
    elif shape == "lava":
        d.polygon([(x + 5, y + 1), (x + 10, y + 1), (x + 12, y + 12), (x + 3, y + 12)], fill=a, outline=_dk(a))
        d.ellipse([x + 6, y + 3, x + 9, y + 6], fill=b)
        d.ellipse([x + 7, y + 8, x + 10, y + 11], fill=b)
        d.rectangle([x + 3, y + 12, x + 12, y + 15], fill=c)
    elif shape == "disco":
        d.line([(x + 8, y), (x + 8, y + 3)], fill=(120, 120, 130))
        d.ellipse([x + 2, y + 3, x + 13, y + 14], fill=a, outline=_dk(a))
        for gx in range(4, 13, 3):
            for gy in range(5, 13, 3):
                d.point((x + gx, y + gy), fill=b if (gx + gy) % 2 else c)
    elif shape == "bchair":
        d.ellipse([x + 1, y + 1, x + 14, y + 13], fill=a, outline=o)
        d.ellipse([x + 4, y + 4, x + 11, y + 11], fill=b)
        d.line([(x + 3, y + 12), (x + 1, y + 15)], fill=(70, 70, 80))
        d.line([(x + 12, y + 12), (x + 14, y + 15)], fill=(70, 70, 80))
    elif shape == "phone":
        d.rounded_rectangle([x + 4, y, x + 11, y + 15], radius=2, fill=a, outline=o)
        d.rectangle([x + 5, y + 1, x + 10, y + 6], fill=b)
        d.line([(x + 4, y + 8), (x + 11, y + 8)], fill=o)
        for gy in (10, 12):
            d.line([(x + 6, y + gy), (x + 9, y + gy)], fill=c)
    elif shape in ("neon_star", "neon_moon", "neon_bolt"):
        d.rectangle([x, y + 1, x + 15, y + 14], fill=b, outline=(0, 0, 0))
        if shape == "neon_star":
            d.polygon(star_points(x + 8, y + 8, 6), outline=a)
        elif shape == "neon_moon":
            d.arc([x + 3, y + 3, x + 12, y + 12], 60, 300, fill=a, width=2)
        else:
            d.line([(x + 9, y + 2), (x + 5, y + 8), (x + 10, y + 8), (x + 6, y + 13)], fill=a, width=2)
    elif shape == "arcade":
        d.rectangle([x + 2, y, x + 13, y + 15], fill=a, outline=o)
        d.rectangle([x + 4, y + 2, x + 11, y + 7], fill=b)
        d.line([(x + 5, y + 4), (x + 10, y + 4)], fill=c)
        d.rectangle([x + 3, y + 9, x + 12, y + 11], fill=_dk(a, 30))
        d.point((x + 5, y + 10), fill=c)
        d.point((x + 9, y + 10), fill=(255, 255, 255))
    elif shape == "gchair":
        d.rectangle([x + 4, y, x + 11, y + 9], fill=a, outline=_dk(a, 40))
        d.rectangle([x + 6, y + 1, x + 9, y + 8], fill=b)
        d.rectangle([x + 3, y + 9, x + 12, y + 11], fill=a, outline=_dk(a, 40))
        d.line([(x + 8, y + 11), (x + 8, y + 14)], fill=c)
        d.line([(x + 4, y + 15), (x + 12, y + 15)], fill=c)
    elif shape == "tv2":
        d.rectangle([x, y + 1, x + 15, y + 10], fill=a, outline=(0, 0, 0))
        d.rectangle([x + 2, y + 3, x + 13, y + 8], fill=b)
        d.rectangle([x + 3, y + 12, x + 12, y + 15], fill=(40, 40, 50))
        d.point((x + 10, y + 13), fill=c)
    elif shape == "planet":
        d.rectangle([x + 7, y + 11, x + 8, y + 15], fill=(110, 110, 120))
        d.ellipse([x + 4, y + 2, x + 11, y + 9], fill=a, outline=o)
        d.arc([x, y + 3, x + 15, y + 9], 0, 360, fill=b)
        d.point((x + 6, y + 4), fill=c)
    elif shape == "rocket":
        d.polygon([(x + 8, y), (x + 11, y + 4), (x + 11, y + 12), (x + 5, y + 12), (x + 5, y + 4)], fill=a, outline=_dk(a))
        d.ellipse([x + 6, y + 4, x + 10, y + 8], fill=(120, 190, 240))
        d.polygon([(x + 5, y + 9), (x + 2, y + 14), (x + 5, y + 12)], fill=b)
        d.polygon([(x + 11, y + 9), (x + 14, y + 14), (x + 11, y + 12)], fill=b)
        d.polygon([(x + 6, y + 12), (x + 10, y + 12), (x + 8, y + 15)], fill=ORANGE)
    elif shape == "moon":
        d.rectangle([x + 6, y + 13, x + 9, y + 15], fill=b)
        d.ellipse([x + 2, y + 1, x + 13, y + 12], fill=a, outline=c)
        d.ellipse([x + 5, y + 4, x + 7, y + 6], fill=_dk(a, 30))
        d.ellipse([x + 9, y + 7, x + 10, y + 8], fill=_dk(a, 30))
    elif shape == "palm":
        d.line([(x + 8, y + 15), (x + 7, y + 5)], fill=b, width=2)
        for ex, ey in ((1, 4), (15, 4), (3, 9), (13, 9), (8, 0)):
            d.line([(x + 7, y + 5), (x + ex, y + ey)], fill=a, width=2)
        d.ellipse([x + 6, y + 5, x + 8, y + 7], fill=c)
    elif shape == "surf":
        d.ellipse([x + 4, y, x + 11, y + 15], fill=a, outline=_dk(a))
        d.line([(x + 8, y + 1), (x + 8, y + 14)], fill=b, width=2)
        d.ellipse([x + 6, y + 9, x + 10, y + 12], fill=c)
    elif shape == "ball":
        d.ellipse([x + 2, y + 2, x + 13, y + 13], fill=WHITE, outline=(80, 80, 90))
        d.pieslice([x + 2, y + 2, x + 13, y + 13], 200, 260, fill=a)
        d.pieslice([x + 2, y + 2, x + 13, y + 13], 320, 20, fill=b)
        d.pieslice([x + 2, y + 2, x + 13, y + 13], 80, 140, fill=c)
    elif shape == "shell":
        d.pieslice([x + 1, y + 2, x + 14, y + 15], 180, 360, fill=a, outline=_dk(a))
        d.rectangle([x + 1, y + 8, x + 14, y + 13], fill=a, outline=_dk(a))
        for k in range(3, 14, 3):
            d.line([(x + 8, y + 13), (x + k, y + 4)], fill=b)
    elif shape == "castle":
        d.rectangle([x + 2, y + 6, x + 13, y + 15], fill=a, outline=_dk(a))
        for k in (2, 6, 10):
            d.rectangle([x + k, y + 3, x + k + 2, y + 6], fill=a, outline=_dk(a))
        d.rectangle([x + 7, y + 10, x + 8, y + 15], fill=b)
        d.line([(x + 12, y + 3), (x + 12, y)], fill=b)
        d.polygon([(x + 12, y), (x + 15, y + 1), (x + 12, y + 2)], fill=c)
    elif shape == "diffuser":
        d.ellipse([x + 4, y + 7, x + 11, y + 15], fill=a, outline=(160, 160, 170))
        d.rectangle([x + 4, y + 13, x + 11, y + 15], fill=b)
        for k in range(3):
            d.arc([x + 5 + k, y - 2 + k * 2, x + 10 + k, y + 4 + k * 2], 180, 300, fill=(220, 225, 240))
    elif shape == "towels":
        for k, col in enumerate((a, b, c)):
            d.rounded_rectangle([x + 2, y + 11 - k * 4, x + 13, y + 15 - k * 4], radius=2, fill=col, outline=_dk(col, 30))
    elif shape == "candles":
        for cx_, hgt in ((4, 8), (8, 11), (12, 6)):
            d.rectangle([x + cx_ - 2, y + 15 - hgt, x + cx_ + 1, y + 15], fill=a, outline=_dk(a, 40))
            d.ellipse([x + cx_ - 1, y + 12 - hgt, x + cx_, y + 15 - hgt], fill=b)
    elif shape == "vanity":
        d.rectangle([x + 1, y + 8, x + 14, y + 11], fill=a, outline=_dk(a, 40))
        d.rectangle([x + 2, y + 11, x + 3, y + 15], fill=_dk(a, 40))
        d.rectangle([x + 12, y + 11, x + 13, y + 15], fill=_dk(a, 40))
        d.ellipse([x + 4, y, x + 11, y + 8], fill=c, outline=b, width=2)
    elif shape == "tub":
        d.rounded_rectangle([x, y + 5, x + 15, y + 14], radius=4, fill=a, outline=(150, 160, 170))
        for k in range(2, 14, 3):
            d.ellipse([x + k, y + 3, x + k + 3, y + 7], fill=WHITE, outline=b)
    elif shape == "clock":
        d.rectangle([x + 4, y, x + 11, y + 15], fill=a, outline=_dk(a, 30))
        d.ellipse([x + 5, y + 1, x + 10, y + 6], fill=c, outline=b)
        d.line([(x + 8, y + 3), (x + 8, y + 4), (x + 9, y + 4)], fill=(0, 0, 0))
        d.line([(x + 8, y + 7), (x + 8, y + 12)], fill=b)
        d.ellipse([x + 7, y + 11, x + 9, y + 13], fill=b)
    elif shape == "globe":
        d.rectangle([x + 5, y + 14, x + 10, y + 15], fill=c)
        d.line([(x + 8, y + 12), (x + 8, y + 14)], fill=c)
        d.ellipse([x + 3, y + 2, x + 12, y + 11], fill=a, outline=_dk(a))
        d.polygon([(x + 5, y + 4), (x + 8, y + 5), (x + 7, y + 8), (x + 5, y + 7)], fill=b)
        d.arc([x + 1, y, x + 14, y + 13], 120, 300, fill=c)
    elif shape == "books":
        for k, col in enumerate((a, b, c, a)):
            d.rectangle([x + 2 + k % 2, y + 12 - k * 3, x + 13 - k % 2, y + 14 - k * 3], fill=col, outline=_dk(col, 40))
    elif shape == "candelabra":
        d.rectangle([x + 5, y + 14, x + 10, y + 15], fill=a)
        d.line([(x + 8, y + 14), (x + 8, y + 6)], fill=a)
        d.arc([x + 2, y + 2, x + 14, y + 10], 0, 180, fill=a)
        for cx_ in (2, 8, 14):
            d.rectangle([x + cx_ - 1, y + 2, x + cx_, y + 6], fill=b)
            d.point((x + cx_, y + 1), fill=c)
    elif shape == "shelf2":
        d.rectangle([x + 1, y, x + 14, y + 15], fill=a, outline=_dk(a, 30))
        for sy in (1, 6, 11):
            for k in range(4):
                d.rectangle([x + 3 + k * 3, y + sy, x + 4 + k * 3, y + sy + 3], fill=b if k % 2 else c)
    elif shape == "cactus":
        d.rectangle([x + 4, y + 11, x + 11, y + 15], fill=b, outline=_dk(b))
        d.rounded_rectangle([x + 6, y + 1, x + 9, y + 11], radius=2, fill=a, outline=o)
        d.rounded_rectangle([x + 2, y + 4, x + 5, y + 8], radius=1, fill=a, outline=o)
        d.rounded_rectangle([x + 10, y + 3, x + 13, y + 7], radius=1, fill=a, outline=o)
        d.ellipse([x + 6, y, x + 9, y + 2], fill=c)
    elif shape == "tallplant":
        d.rectangle([x + 5, y + 11, x + 10, y + 15], fill=b, outline=_dk(b))
        for ex, ey in ((1, 2), (14, 3), (3, 8), (13, 9), (8, 0)):
            d.ellipse([x + ex - 3, y + ey - 2, x + ex + 3, y + ey + 3], fill=a if ex % 2 else c, outline=_dk(a, 30))
            d.line([(x + 8, y + 11), (x + ex, y + ey)], fill=_dk(a, 20))
    elif shape == "vase":
        d.polygon([(x + 5, y + 8), (x + 10, y + 8), (x + 11, y + 15), (x + 4, y + 15)], fill=c, outline=_dk(c, 40))
        for ex in (3, 7, 11):
            d.line([(x + 8, y + 8), (x + ex, y + 1)], fill=_dk(a, 30))
            d.ellipse([x + ex - 2, y, x + ex + 2, y + 4], fill=a)
    elif shape == "pumpkin2":
        d.ellipse([x + 1, y + 4, x + 14, y + 15], fill=a, outline=c)
        d.line([(x + 8, y + 5), (x + 8, y + 15)], fill=c)
        d.rectangle([x + 7, y + 1, x + 8, y + 4], fill=b)
    elif shape == "cauldron":
        d.ellipse([x + 1, y + 5, x + 14, y + 15], fill=a, outline=(0, 0, 0))
        d.ellipse([x + 2, y + 4, x + 13, y + 8], fill=b)
        for k in (5, 9):
            d.ellipse([x + k, y + 1, x + k + 3, y + 4], outline=c)
    elif shape == "skull":
        d.ellipse([x + 3, y + 2, x + 12, y + 11], fill=a, outline=c)
        d.rectangle([x + 5, y + 10, x + 10, y + 14], fill=a, outline=c)
        d.ellipse([x + 5, y + 5, x + 7, y + 8], fill=b)
        d.ellipse([x + 8, y + 5, x + 10, y + 8], fill=b)
    elif shape == "bowl":
        for k, col in enumerate((b, c, b, c)):
            d.ellipse([x + 3 + k * 2, y + 3 + (k % 2), x + 6 + k * 2, y + 6 + (k % 2)], fill=col)
        d.pieslice([x + 1, y + 1, x + 14, y + 15], 0, 180, fill=a, outline=_dk(a))
    elif shape == "tomb":
        d.rectangle([x + 3, y + 5, x + 12, y + 15], fill=a, outline=_dk(a))
        d.pieslice([x + 3, y + 1, x + 12, y + 10], 180, 360, fill=a, outline=_dk(a))
        d.line([(x + 8, y + 5), (x + 8, y + 10)], fill=b)
        d.line([(x + 6, y + 7), (x + 10, y + 7)], fill=b)
        d.rectangle([x + 1, y + 14, x + 14, y + 15], fill=c)
    elif shape == "gift":
        d.rectangle([x + 2, y + 5, x + 13, y + 15], fill=a, outline=_dk(a))
        d.rectangle([x + 7, y + 5, x + 8, y + 15], fill=b)
        d.rectangle([x + 2, y + 8, x + 13, y + 9], fill=b)
        d.polygon([(x + 8, y + 5), (x + 4, y + 1), (x + 4, y + 5)], fill=b)
        d.polygon([(x + 8, y + 5), (x + 12, y + 1), (x + 12, y + 5)], fill=b)
    elif shape == "cane":
        d.arc([x + 4, y, x + 12, y + 8], 180, 360, fill=a, width=3)
        d.line([(x + 11, y + 4), (x + 11, y + 15)], fill=a, width=3)
        for k in range(5, 15, 3):
            d.point((x + 11, y + k), fill=b)
    elif shape == "fireplace":
        d.rectangle([x, y + 1, x + 15, y + 15], fill=a, outline=_dk(a))
        d.rectangle([x + 3, y + 5, x + 12, y + 15], fill=(20, 16, 14))
        d.polygon([(x + 5, y + 15), (x + 8, y + 7), (x + 11, y + 15)], fill=b)
        d.polygon([(x + 7, y + 15), (x + 8, y + 10), (x + 9, y + 15)], fill=c)
        d.rectangle([x, y + 1, x + 15, y + 3], fill=_dk(a, 30))
    elif shape == "wreath":
        d.ellipse([x + 1, y + 1, x + 14, y + 14], outline=a, width=4)
        for px_, py_ in ((4, 3), (12, 6), (5, 12)):
            d.point((x + px_, y + py_), fill=c)
        d.polygon([(x + 8, y + 12), (x + 5, y + 15), (x + 11, y + 15)], fill=b)
    elif shape == "heart":
        d.polygon([(x + 8, y + 14), (x + 1, y + 7), (x + 1, y + 4), (x + 4, y + 1), (x + 8, y + 4),
                   (x + 12, y + 1), (x + 15, y + 4), (x + 15, y + 7)], fill=a, outline=_dk(a))
        d.line([(x + 4, y + 4), (x + 5, y + 3)], fill=b)
        d.line([(x + 5, y + 9), (x + 11, y + 9)], fill=c)
    elif shape == "egg":
        d.ellipse([x + 3, y + 1, x + 12, y + 15], fill=a, outline=_dk(a))
        d.line([(x + 4, y + 7), (x + 11, y + 7)], fill=b, width=2)
        for k in (5, 8, 11):
            d.point((x + k, y + 11), fill=c)
    elif shape == "lantern":
        d.line([(x + 8, y), (x + 8, y + 2)], fill=b)
        d.ellipse([x + 2, y + 2, x + 13, y + 13], fill=a, outline=_dk(a))
        d.rectangle([x + 5, y + 2, x + 10, y + 3], fill=b)
        d.rectangle([x + 5, y + 12, x + 10, y + 13], fill=b)
        d.line([(x + 8, y + 13), (x + 8, y + 15)], fill=c)
        d.arc([x + 5, y + 2, x + 10, y + 13], 90, 270, fill=_dk(a, 30))
    elif shape == "flag":
        d.line([(x + 2, y), (x + 2, y + 15)], fill=(120, 120, 130), width=2)
        for k in range(5):
            d.line([(x + 3, y + 1 + k * 2), (x + 14, y + 1 + k * 2)], fill=a if k % 2 == 0 else b)
        d.rectangle([x + 3, y + 1, x + 7, y + 5], fill=c)
    elif shape == "grill":
        d.pieslice([x + 2, y + 1, x + 13, y + 12], 0, 180, fill=a, outline=(0, 0, 0))
        d.line([(x + 2, y + 6), (x + 13, y + 6)], fill=b)
        d.line([(x + 4, y + 11), (x + 3, y + 15)], fill=b)
        d.line([(x + 11, y + 11), (x + 12, y + 15)], fill=b)
        d.point((x + 8, y + 4), fill=c)
    elif shape == "cooler":
        d.rectangle([x + 1, y + 5, x + 14, y + 15], fill=a, outline=_dk(a))
        d.rectangle([x + 1, y + 4, x + 14, y + 7], fill=b, outline=_dk(a))
        d.line([(x + 5, y + 2), (x + 10, y + 2)], fill=c, width=2)
    elif shape == "melon":
        d.pieslice([x, y + 2, x + 15, y + 17], 180, 360, fill=a)
        d.pieslice([x + 2, y + 4, x + 13, y + 15], 180, 360, fill=b)
        for k in (5, 8, 11):
            d.point((x + k, y + 7), fill=c)
    elif shape == "ring":
        d.ellipse([x, y + 3, x + 15, y + 14], fill=a, outline=_dk(a))
        d.ellipse([x + 5, y + 6, x + 10, y + 11], fill=(150, 200, 240))
        for k in (2, 11):
            d.rectangle([x + k, y + 6, x + k + 2, y + 9], fill=b)
    elif shape == "tree":
        d.rectangle([x + 7, y + 10, x + 8, y + 15], fill=b)
        d.ellipse([x + 1, y, x + 14, y + 11], fill=a, outline=_dk(a))
        for px_, py_ in ((4, 4), (10, 3), (7, 7), (11, 8)):
            d.point((x + px_, y + py_), fill=c)
    elif shape == "hay":
        d.rectangle([x + 1, y + 4, x + 14, y + 15], fill=a, outline=c)
        for k in range(3, 14, 3):
            d.line([(x + k, y + 5), (x + k - 1, y + 14)], fill=b)
        d.line([(x + 1, y + 9), (x + 14, y + 9)], fill=c)
    elif shape == "pie":
        d.ellipse([x + 1, y + 6, x + 14, y + 14], fill=b, outline=c)
        d.ellipse([x + 3, y + 7, x + 12, y + 12], fill=a)
        d.ellipse([x + 7, y + 8, x + 9, y + 10], fill=WHITE)
    elif shape == "balloons":
        for k, (bx, by, col) in enumerate(((3, 2, a), (8, 0, b), (11, 3, c))):
            d.line([(x + bx + 2, y + by + 6), (x + 8, y + 15)], fill=(140, 140, 150))
            d.ellipse([x + bx, y + by, x + bx + 5, y + by + 6], fill=col, outline=_dk(col))
    elif shape == "wall":
        d.rectangle([x, y, x + 15, y + 15], fill=a)
        d.rectangle([x, y, x + 15, y + 2], fill=_dk(a, -20) if max(a) < 235 else a)
        d.rectangle([x, y + 13, x + 15, y + 15], fill=b)
        d.line([(x, y + 12), (x + 15, y + 12)], fill=_dk(b, 30))
    elif shape == "wall_wood":
        d.rectangle([x, y, x + 15, y + 15], fill=a)
        for k in (4, 8, 12):
            d.line([(x + k, y), (x + k, y + 15)], fill=b)
        d.rectangle([x, y + 13, x + 15, y + 15], fill=b)
    elif shape == "wall_brick":
        d.rectangle([x, y, x + 15, y + 15], fill=b)
        for row in range(4):
            off = 0 if row % 2 == 0 else 4
            for k in range(-1, 3):
                bx = x + off + k * 8
                x0, x1 = max(x, bx), min(x + 15, bx + 6)
                if x1 >= x0:
                    d.rectangle([x0, y + row * 4, x1, y + row * 4 + 2], fill=a)
    elif shape in ("window", "curtain"):
        d.rectangle([x, y, x + 15, y + 15], fill=(240, 240, 244))
        d.rectangle([x + 2, y + 1, x + 13, y + 12], fill=b, outline=a, width=2)
        d.line([(x + 8, y + 1), (x + 8, y + 12)], fill=a)
        d.line([(x + 2, y + 6), (x + 13, y + 6)], fill=a)
        d.rectangle([x + 1, y + 12, x + 14, y + 14], fill=_dk(a, 20))
        if shape == "curtain":
            d.polygon([(x + 1, y), (x + 6, y), (x + 3, y + 13), (x + 1, y + 13)], fill=c)
            d.polygon([(x + 10, y), (x + 15, y), (x + 15, y + 13), (x + 13, y + 13)], fill=c)
    elif shape == "floor_wood":
        d.rectangle([x, y, x + 15, y + 15], fill=a)
        for k in (0, 5, 10):
            d.line([(x, y + k), (x + 15, y + k)], fill=b)
        for kx, ky in ((6, 1), (12, 6), (3, 11)):
            d.line([(x + kx, y + ky), (x + kx, y + ky + 3)], fill=b)
    elif shape == "floor_tile":
        d.rectangle([x, y, x + 15, y + 15], fill=a)
        d.line([(x, y + 7), (x + 15, y + 7)], fill=b)
        d.line([(x + 7, y), (x + 7, y + 15)], fill=b)
        d.rectangle([x, y, x + 15, y + 15], outline=b)
    elif shape == "floor_check":
        d.rectangle([x, y, x + 15, y + 15], fill=a)
        d.rectangle([x, y, x + 7, y + 7], fill=b)
        d.rectangle([x + 8, y + 8, x + 15, y + 15], fill=b)
    elif shape == "floor_marble":
        d.rectangle([x, y, x + 15, y + 15], fill=a, outline=b)
        d.line([(x + 2, y + 3), (x + 7, y + 6), (x + 9, y + 12)], fill=b)
        d.line([(x + 11, y + 2), (x + 13, y + 7)], fill=b)
    elif shape == "carpet":
        d.rectangle([x, y, x + 15, y + 15], fill=a)
        for px_, py_ in ((2, 3), (9, 1), (5, 9), (12, 11), (1, 13), (13, 5)):
            d.point((x + px_, y + py_), fill=b)
    elif shape == "armchair":
        d.rounded_rectangle([x + 2, y + 2, x + 13, y + 9], radius=3, fill=a, outline=o)
        d.rectangle([x + 3, y + 8, x + 12, y + 13], fill=b, outline=o)
        d.rectangle([x + 1, y + 6, x + 3, y + 13], fill=a, outline=o)
        d.rectangle([x + 12, y + 6, x + 14, y + 13], fill=a, outline=o)
        d.line([(x + 4, y + 14), (x + 4, y + 15)], fill=_dk(a))
        d.line([(x + 11, y + 14), (x + 11, y + 15)], fill=_dk(a))
    elif shape == "easel":
        d.line([(x + 4, y + 15), (x + 8, y + 1)], fill=a, width=2)
        d.line([(x + 12, y + 15), (x + 8, y + 1)], fill=a, width=2)
        d.rectangle([x + 3, y + 3, x + 13, y + 10], fill=WHITE, outline=_dk(a))
        d.ellipse([x + 5, y + 4, x + 9, y + 8], fill=b)
        d.rectangle([x + 9, y + 6, x + 12, y + 9], fill=c)
    elif shape == "frame":
        d.rectangle([x + 2, y + 1, x + 13, y + 13], fill=a, outline=_dk(a))
        d.rectangle([x + 4, y + 3, x + 11, y + 11], fill=c)
        d.polygon([(x + 4, y + 11), (x + 7, y + 6), (x + 11, y + 11)], fill=b)
        d.line([(x + 6, y + 13), (x + 4, y + 15)], fill=_dk(a))
        d.line([(x + 9, y + 13), (x + 11, y + 15)], fill=_dk(a))
    elif shape == "canopy":
        d.rectangle([x, y + 4, x + 15, y + 15], fill=WHITE, outline=(170, 170, 180))
        d.rectangle([x + 1, y + 8, x + 14, y + 14], fill=b)
        d.rectangle([x + 2, y + 5, x + 13, y + 7], fill=c)
        d.line([(x, y), (x, y + 15)], fill=_dk(a, 40))
        d.line([(x + 15, y), (x + 15, y + 15)], fill=_dk(a, 40))
        d.polygon([(x, y), (x + 15, y), (x + 13, y + 3), (x + 2, y + 3)], fill=a)
        d.polygon([(x, y), (x + 3, y), (x + 1, y + 9)], fill=a)
        d.polygon([(x + 15, y), (x + 12, y), (x + 14, y + 9)], fill=a)
    elif shape == "wardrobe":
        d.rectangle([x + 1, y, x + 14, y + 15], fill=a, outline=_dk(a, 50))
        d.line([(x + 8, y + 1), (x + 8, y + 14)], fill=b)
        d.point((x + 6, y + 8), fill=c)
        d.point((x + 10, y + 8), fill=c)
        d.rectangle([x + 1, y, x + 14, y + 2], fill=b)
    elif shape == "dresser":
        d.rectangle([x, y + 3, x + 15, y + 15], fill=a, outline=_dk(a, 50))
        for k in (6, 10):
            d.line([(x + 1, y + k), (x + 14, y + k)], fill=b)
        for ky in (5, 8, 12):
            d.point((x + 8, y + ky), fill=c)
        d.ellipse([x + 4, y - 1, x + 11, y + 4], fill=(200, 230, 245), outline=c)
    elif shape == "nightstand":
        d.rectangle([x + 3, y + 7, x + 12, y + 15], fill=a, outline=_dk(a, 50))
        d.line([(x + 3, y + 11), (x + 12, y + 11)], fill=b)
        d.point((x + 8, y + 9), fill=c)
        d.polygon([(x + 5, y + 6), (x + 10, y + 6), (x + 9, y + 2), (x + 6, y + 2)], fill=c)
    elif shape == "rack":
        d.line([(x + 2, y + 1), (x + 13, y + 1)], fill=a, width=2)
        d.line([(x + 2, y + 1), (x + 2, y + 15)], fill=a)
        d.line([(x + 13, y + 1), (x + 13, y + 15)], fill=a)
        for k, col in enumerate((b, c, b)):
            d.polygon([(x + 4 + k * 3, y + 2), (x + 6 + k * 3, y + 2), (x + 7 + k * 3, y + 10), (x + 3 + k * 3, y + 10)], fill=col)
    elif shape == "fridge":
        d.rounded_rectangle([x + 2, y, x + 13, y + 15], radius=2, fill=a, outline=_dk(a, 50))
        d.line([(x + 2, y + 6), (x + 13, y + 6)], fill=b)
        d.line([(x + 11, y + 2), (x + 11, y + 4)], fill=c, width=2)
        d.line([(x + 11, y + 8), (x + 11, y + 12)], fill=c, width=2)
    elif shape == "stove":
        d.rectangle([x + 1, y + 2, x + 14, y + 15], fill=a, outline=_dk(a, 50))
        for cx_ in (4, 11):
            d.ellipse([x + cx_ - 2, y + 3, x + cx_ + 2, y + 6], fill=b)
        d.rectangle([x + 3, y + 8, x + 12, y + 14], fill=b)
        d.rectangle([x + 4, y + 9, x + 11, y + 13], fill=c)
    elif shape == "sink":
        d.rectangle([x, y + 6, x + 15, y + 15], fill=a, outline=_dk(a, 50))
        d.ellipse([x + 3, y + 7, x + 12, y + 11], fill=b, outline=_dk(b, 40))
        d.line([(x + 8, y + 2), (x + 8, y + 7)], fill=_dk(b, 40), width=2)
        d.line([(x + 8, y + 2), (x + 11, y + 2)], fill=_dk(b, 40), width=2)
        d.point((x + 10, y + 9), fill=c)
    elif shape == "counter":
        d.rectangle([x, y + 3, x + 15, y + 15], fill=b, outline=_dk(b, 40))
        d.rectangle([x, y + 3, x + 15, y + 6], fill=a)
        d.line([(x + 8, y + 7), (x + 8, y + 15)], fill=_dk(b, 40))
        d.point((x + 6, y + 10), fill=c)
        d.point((x + 10, y + 10), fill=c)
    elif shape == "microwave":
        d.rectangle([x + 1, y + 5, x + 14, y + 14], fill=a, outline=_dk(a, 50))
        d.rectangle([x + 2, y + 6, x + 10, y + 13], fill=b)
        d.point((x + 12, y + 8), fill=c)
        d.point((x + 12, y + 11), fill=c)
    elif shape == "toaster":
        d.rounded_rectangle([x + 2, y + 6, x + 13, y + 14], radius=3, fill=a, outline=_dk(a, 50))
        d.line([(x + 5, y + 6), (x + 5, y + 8)], fill=b)
        d.line([(x + 10, y + 6), (x + 10, y + 8)], fill=b)
        d.rectangle([x + 4, y + 3, x + 6, y + 6], fill=c)
        d.rectangle([x + 9, y + 3, x + 11, y + 6], fill=c)
    elif shape == "coffee":
        d.rectangle([x + 3, y + 2, x + 12, y + 14], fill=a, outline=(0, 0, 0))
        d.rectangle([x + 5, y + 6, x + 10, y + 10], fill=b)
        d.rectangle([x + 6, y + 8, x + 9, y + 12], fill=c)
        d.rectangle([x + 3, y + 13, x + 12, y + 15], fill=b)
    elif shape == "stool":
        d.ellipse([x + 3, y + 3, x + 12, y + 7], fill=a, outline=_dk(a))
        d.line([(x + 5, y + 7), (x + 4, y + 15)], fill=b)
        d.line([(x + 10, y + 7), (x + 11, y + 15)], fill=b)
        d.line([(x + 5, y + 11), (x + 10, y + 11)], fill=b)
    elif shape == "shower":
        d.rectangle([x + 1, y, x + 14, y + 15], fill=(225, 240, 250), outline=c)
        d.line([(x + 8, y + 1), (x + 8, y + 4)], fill=c)
        d.ellipse([x + 6, y + 3, x + 10, y + 5], fill=c)
        for k in range(4, 13, 3):
            d.line([(x + k, y + 6), (x + k - 1, y + 11)], fill=b)
        d.rectangle([x + 1, y + 13, x + 14, y + 15], fill=a)
    elif shape == "washer":
        d.rectangle([x + 1, y + 1, x + 14, y + 15], fill=a, outline=_dk(a, 50))
        d.line([(x + 1, y + 4), (x + 14, y + 4)], fill=c)
        d.ellipse([x + 4, y + 6, x + 11, y + 13], fill=b, outline=c, width=2)
        d.point((x + 12, y + 2), fill=c)
    elif shape == "hat":
        d.polygon([(x + 1, y + 13), (x + 15, y + 13), (x + 12, y + 11), (x + 4, y + 11)], fill=a, outline=_dk(a, -30))
        d.polygon([(x + 4, y + 11), (x + 12, y + 11), (x + 10, y + 4), (x + 13, y)], fill=a, outline=_dk(a, -30))
        d.line([(x + 5, y + 10), (x + 11, y + 10)], fill=b, width=2)
        for px_, py_ in ((8, 6), (10, 3)):
            d.point((x + px_, y + py_), fill=c)
    elif shape == "spellbook":
        d.rectangle([x + 1, y + 8, x + 14, y + 15], fill=(110, 80, 50))
        d.polygon([(x + 1, y + 6), (x + 8, y + 8), (x + 15, y + 6), (x + 15, y + 12), (x + 8, y + 14), (x + 1, y + 12)],
                  fill=b, outline=a)
        d.line([(x + 8, y + 8), (x + 8, y + 14)], fill=a)
        for k in range(3):
            d.point((x + 4 + k * 4, y + 3 - k % 2), fill=c)
            d.point((x + 6 + k * 3, y + 1 + k % 2), fill=c)
    elif shape == "wand":
        d.rectangle([x + 3, y + 12, x + 12, y + 15], fill=a, outline=_dk(a, 30))
        d.line([(x + 6, y + 12), (x + 9, y + 2)], fill=(90, 60, 40), width=2)
        d.line([(x + 10, y + 12), (x + 12, y + 4)], fill=(60, 40, 30), width=2)
        d.point((x + 9, y + 1), fill=b)
        d.point((x + 12, y + 3), fill=c)
    elif shape == "broom":
        d.line([(x + 3, y + 1), (x + 10, y + 10)], fill=a, width=2)
        d.polygon([(x + 9, y + 9), (x + 15, y + 11), (x + 13, y + 15), (x + 7, y + 13)], fill=b, outline=_dk(b, 40))
        d.line([(x + 8, y + 10), (x + 11, y + 9)], fill=c, width=2)
    elif shape == "owl":
        d.line([(x + 2, y + 13), (x + 14, y + 13)], fill=(110, 80, 50), width=2)
        d.ellipse([x + 3, y + 2, x + 12, y + 13], fill=a, outline=_dk(a, 50))
        d.ellipse([x + 4, y + 4, x + 7, y + 7], fill=WHITE, outline=c)
        d.ellipse([x + 8, y + 4, x + 11, y + 7], fill=WHITE, outline=c)
        d.point((x + 5, y + 5), fill=(0, 0, 0))
        d.point((x + 9, y + 5), fill=(0, 0, 0))
        d.polygon([(x + 7, y + 7), (x + 8, y + 7), (x + 7, y + 9)], fill=b)
        d.polygon([(x + 3, y + 3), (x + 4, y), (x + 6, y + 3)], fill=a)
        d.polygon([(x + 12, y + 3), (x + 11, y), (x + 9, y + 3)], fill=a)
    elif shape == "crystal":
        d.polygon([(x + 4, y + 15), (x + 11, y + 15), (x + 10, y + 11), (x + 5, y + 11)], fill=b)
        d.ellipse([x + 2, y + 1, x + 13, y + 12], fill=a, outline=_dk(a, 40))
        d.ellipse([x + 5, y + 4, x + 8, y + 7], fill=c)
        d.arc([x + 4, y + 3, x + 11, y + 10], 200, 320, fill=(150, 120, 230))
    elif shape == "potions":
        d.rectangle([x + 1, y, x + 14, y + 15], fill=a, outline=_dk(a, 30))
        for sy, cols in ((1, (b, c, (250, 120, 120))), (8, (c, (120, 200, 255), b))):
            for i, col in enumerate(cols):
                px_ = x + 3 + i * 4
                d.ellipse([px_, y + sy + 2, px_ + 3, y + sy + 6], fill=col)
                d.rectangle([px_ + 1, y + sy, px_ + 2, y + sy + 2], fill=(220, 220, 230))
    elif shape == "trunk":
        d.rectangle([x + 1, y + 5, x + 14, y + 15], fill=a, outline=_dk(a, 40))
        d.rectangle([x + 1, y + 5, x + 14, y + 8], fill=_dk(a, 20))
        for k in (4, 11):
            d.line([(x + k, y + 5), (x + k, y + 15)], fill=c, width=2)
        d.rectangle([x + 7, y + 8, x + 9, y + 10], fill=b)
    elif shape == "banner":
        d.line([(x + 2, y), (x + 14, y)], fill=(110, 80, 50), width=2)
        d.polygon([(x + 3, y + 1), (x + 13, y + 1), (x + 13, y + 15), (x + 8, y + 12), (x + 3, y + 15)], fill=a)
        d.line([(x + 3, y + 3), (x + 13, y + 3)], fill=b)
        draw_star(d, x + 8, y + 7, 3, c, outline=c)
    elif shape == "scarf":
        d.line([(x + 8, y + 2), (x + 8, y + 15)], fill=c, width=2)
        d.line([(x + 4, y + 15), (x + 12, y + 15)], fill=c, width=2)
        for k in range(4):
            col = a if k % 2 == 0 else b
            d.rectangle([x + 4, y + 2 + k * 3, x + 7, y + 4 + k * 3], fill=col)
            d.rectangle([x + 9, y + 2 + k * 3, x + 12, y + 4 + k * 3], fill=col)
    elif shape == "plush_dog":
        d.ellipse([x + 4, y + 9, x + 12, y + 15], fill=a, outline=_dk(a, 60))
        d.ellipse([x + 3, y + 2, x + 13, y + 11], fill=a, outline=_dk(a, 60))
        d.ellipse([x + 1, y + 3, x + 5, y + 10], fill=_dk(a, 30) if b == a else b)   # floppy ears
        d.ellipse([x + 11, y + 3, x + 15, y + 10], fill=_dk(a, 30) if b == a else b)
        if b != a and a == WHITE:   # spots
            for px_, py_ in ((6, 4), (10, 7), (7, 12)):
                d.point((x + px_, y + py_), fill=b)
        d.ellipse([x + 6, y + 6, x + 10, y + 10], fill=b if b != a and a != WHITE else _dk(a, -30) if max(a) < 220 else (240, 230, 220))
        d.point((x + 6, y + 5), fill=c)
        d.point((x + 10, y + 5), fill=c)
        d.point((x + 8, y + 8), fill=(30, 20, 20))
    elif shape == "dogbed":
        d.ellipse([x, y + 5, x + 15, y + 15], fill=a, outline=_dk(a, 50))
        d.ellipse([x + 3, y + 7, x + 12, y + 13], fill=b)
        d.ellipse([x + 5, y + 8, x + 7, y + 10], fill=c)
    elif shape == "doghouse":
        d.rectangle([x + 2, y + 6, x + 13, y + 15], fill=b, outline=_dk(b, 50))
        d.polygon([(x, y + 7), (x + 8, y), (x + 15, y + 7)], fill=a, outline=_dk(a, 40))
        d.pieslice([x + 5, y + 9, x + 10, y + 19], 180, 360, fill=(40, 30, 30))
        d.rectangle([x + 5, y + 14, x + 10, y + 15], fill=(40, 30, 30))
    elif shape == "dogbowl":
        d.ellipse([x + 2, y + 9, x + 13, y + 15], fill=a, outline=_dk(a, 50))
        d.ellipse([x + 4, y + 9, x + 11, y + 12], fill=b)
        d.text((x + 5, y + 10), "", font=F_S, fill=c)
    elif shape == "bone":
        d.rectangle([x + 4, y + 7, x + 11, y + 9], fill=a)
        for ex, ey in ((3, 6), (3, 10), (12, 6), (12, 10)):
            d.ellipse([x + ex - 2, y + ey - 2, x + ex + 1, y + ey + 1], fill=a, outline=b)
    elif shape == "tennis":
        d.ellipse([x + 4, y + 7, x + 12, y + 15], fill=a, outline=_dk(a, 60))
        d.arc([x + 1, y + 6, x + 9, y + 14], 300, 60, fill=b)
        d.arc([x + 7, y + 8, x + 15, y + 16], 120, 240, fill=b)
    elif shape == "pawrug":
        d.ellipse([x, y + 3, x + 15, y + 13], fill=a, outline=_dk(a, 40))
        d.ellipse([x + 6, y + 7, x + 10, y + 11], fill=b)
        for px_, py_ in ((4, 6), (7, 4), (10, 4), (12, 6)):
            d.ellipse([x + px_ - 1, y + py_ - 1, x + px_ + 1, y + py_ + 1], fill=b)
    elif shape in ("buddy1", "buddy2"):
        d.rounded_rectangle([x + 3, y + 1, x + 12, y + 15], radius=4, fill=a, outline=_dk(a, 60))
        d.rectangle([x + 3, y + 10, x + 12, y + 15], fill=b)            # overalls
        d.rectangle([x + 6, y + 11, x + 9, y + 13], fill=_dk(b, -30))
        d.line([(x + 3, y + 5), (x + 12, y + 5)], fill=(40, 40, 46), width=2)   # goggle strap
        if shape == "buddy1":
            d.ellipse([x + 5, y + 2, x + 10, y + 7], fill=c, outline=(60, 60, 70))
            d.ellipse([x + 6, y + 3, x + 9, y + 6], fill=WHITE)
            d.point((x + 7, y + 4), fill=(80, 50, 20))
        else:
            for ex in (4, 8):
                d.ellipse([x + ex, y + 2, x + ex + 4, y + 6], fill=c, outline=(60, 60, 70))
                d.point((x + ex + 2, y + 4), fill=(80, 50, 20))
        d.line([(x + 6, y + 8), (x + 9, y + 8)], fill=(60, 30, 20))   # smile
    elif shape == "banana":
        d.arc([x + 1, y - 4, x + 15, y + 12], 30, 150, fill=a, width=4)
        d.point((x + 3, y + 7), fill=b)
        d.point((x + 13, y + 7), fill=b)
    elif shape == "bananas":
        for k in range(3):
            d.arc([x + k * 2, y - 2 + k, x + 12 + k * 2, y + 12 + k], 40, 150, fill=a, width=3)
        d.rectangle([x + 6, y + 1, x + 8, y + 4], fill=b)
    elif shape == "goggles":
        d.line([(x, y + 8), (x + 15, y + 8)], fill=c, width=2)
        for ex in (1, 8):
            d.ellipse([x + ex, y + 4, x + ex + 7, y + 12], fill=b, outline=a, width=2)
            d.point((x + ex + 2, y + 6), fill=WHITE)
    elif shape == "betta_bowl":
        d.ellipse([x + 1, y + 3, x + 14, y + 15], fill=c, outline=(200, 220, 235))
        d.rectangle([x + 3, y + 12, x + 12, y + 14], fill=(200, 170, 110))
        d.polygon([(x + 8, y + 9), (x + 12, y + 6), (x + 12, y + 12)], fill=b)
        d.ellipse([x + 4, y + 7, x + 9, y + 11], fill=a)
        d.point((x + 5, y + 8), fill=(0, 0, 0))
        d.line([(x + 3, y + 4), (x + 12, y + 4)], fill=(230, 240, 250))
    elif shape == "cupcake":
        for k, (cx_, cy_) in enumerate(((4, 11), (11, 11), (8, 5))):
            d.polygon([(x + cx_ - 3, y + cy_), (x + cx_ + 3, y + cy_), (x + cx_ + 2, y + cy_ + 4), (x + cx_ - 2, y + cy_ + 4)],
                      fill=b)
            d.ellipse([x + cx_ - 3, y + cy_ - 3, x + cx_ + 3, y + cy_ + 1], fill=a)
            d.point((x + cx_, y + cy_ - 3), fill=c)


def draw_furniture(d, fid, x, y):
    """16x16 furniture sprites for her room."""
    if fid in FURN_SHAPE:
        draw_shape(d, *FURN_SHAPE[fid], x, y)
        return
    if fid == "bed":
        d.rectangle([x, y + 2, x + 15, y + 15], fill=(140, 90, 60), outline=(60, 36, 20))
        d.rectangle([x + 1, y + 6, x + 14, y + 14], fill=(250, 170, 200))
        d.rectangle([x + 2, y + 3, x + 13, y + 6], fill=WHITE)
    elif fid in ("rug_pink", "rug_blue"):
        c = (240, 150, 190) if fid == "rug_pink" else (120, 170, 240)
        d.ellipse([x, y + 3, x + 15, y + 13], fill=c, outline=tuple(v - 50 for v in c))
        d.ellipse([x + 4, y + 6, x + 11, y + 10], outline=WHITE)
    elif fid == "plant":
        d.rectangle([x + 4, y + 10, x + 11, y + 15], fill=(190, 100, 60))
        for ox, oy in ((0, 0), (-4, 3), (4, 3), (0, 5)):
            d.ellipse([x + 5 + ox, y + 1 + oy, x + 10 + ox, y + 7 + oy], fill=(60, 170, 80))
    elif fid == "lamp":
        d.rectangle([x + 7, y + 6, x + 8, y + 14], fill=(80, 80, 90))
        d.rectangle([x + 4, y + 14, x + 11, y + 15], fill=(80, 80, 90))
        d.polygon([(x + 4, y + 6), (x + 11, y + 6), (x + 9, y), (x + 6, y)], fill=(250, 220, 120))
    elif fid == "shelf":
        d.rectangle([x + 1, y, x + 14, y + 15], fill=(110, 70, 40), outline=(50, 30, 16))
        for sy, cols in ((2, (RED, CYAN, YELLOW)), (8, (GREEN, PURPLE, ORANGE))):
            for i, c in enumerate(cols):
                d.rectangle([x + 3 + i * 4, y + sy, x + 5 + i * 4, y + sy + 4], fill=c)
    elif fid == "beanbag":
        d.ellipse([x + 1, y + 5, x + 14, y + 15], fill=(170, 100, 220), outline=(90, 40, 130))
        d.ellipse([x + 4, y + 6, x + 9, y + 9], fill=(200, 150, 240))
    elif fid in ("kitty", "bunny", "ghost"):
        c = WHITE if fid != "ghost" else (235, 235, 250)
        d.ellipse([x + 3, y + 3, x + 12, y + 11], fill=c, outline=(80, 80, 90))
        d.ellipse([x + 4, y + 9, x + 11, y + 15], fill=c, outline=(80, 80, 90))
        if fid == "kitty":
            d.polygon([(x + 3, y + 5), (x + 4, y), (x + 7, y + 3)], fill=c, outline=(80, 80, 90))
            d.polygon([(x + 12, y + 5), (x + 11, y), (x + 8, y + 3)], fill=c, outline=(80, 80, 90))
            d.ellipse([x + 9, y + 1, x + 13, y + 4], fill=RED)
        elif fid == "bunny":
            d.ellipse([x + 4, y - 3, x + 6, y + 4], fill=c, outline=(80, 80, 90))
            d.ellipse([x + 9, y - 3, x + 11, y + 4], fill=c, outline=(80, 80, 90))
        d.point((x + 6, y + 7), fill=(0, 0, 0))
        d.point((x + 9, y + 7), fill=(0, 0, 0))
    elif fid == "tv":
        d.rectangle([x, y + 2, x + 15, y + 12], fill=(30, 30, 36), outline=(0, 0, 0))
        d.rectangle([x + 2, y + 4, x + 13, y + 10], fill=(80, 160, 240))
        d.rectangle([x + 5, y + 12, x + 10, y + 15], fill=(60, 60, 70))
    elif fid == "desk":
        d.rectangle([x, y + 5, x + 15, y + 9], fill=(150, 100, 60), outline=(70, 44, 24))
        d.rectangle([x + 1, y + 9, x + 2, y + 15], fill=(110, 70, 40))
        d.rectangle([x + 13, y + 9, x + 14, y + 15], fill=(110, 70, 40))
        d.rectangle([x + 4, y + 2, x + 9, y + 5], fill=CREAM)
    elif fid == "chair":
        d.rectangle([x + 4, y + 2, x + 11, y + 8], fill=(200, 120, 160), outline=(90, 40, 70))
        d.rectangle([x + 4, y + 8, x + 11, y + 10], fill=(220, 150, 180))
        d.line([(x + 5, y + 10), (x + 5, y + 15)], fill=(90, 40, 70))
        d.line([(x + 10, y + 10), (x + 10, y + 15)], fill=(90, 40, 70))
    elif fid in ("flowers", "roses"):
        d.rectangle([x + 5, y + 9, x + 10, y + 15], fill=(120, 180, 230) if fid == "flowers" else (240, 240, 245))
        cols = (YELLOW, (255, 120, 180), WHITE) if fid == "flowers" else (RED, RED, (220, 30, 50))
        for i, c in enumerate(cols):
            d.ellipse([x + 3 + i * 3, y + 2 + (i % 2) * 2, x + 7 + i * 3, y + 6 + (i % 2) * 2], fill=c)
    elif fid == "mirror":
        d.ellipse([x + 3, y, x + 12, y + 14], fill=(200, 230, 245), outline=(200, 160, 60), width=2)
        d.line([(x + 6, y + 4), (x + 8, y + 2)], fill=WHITE)
    elif fid == "fishtank":
        d.rectangle([x, y + 3, x + 15, y + 14], fill=(90, 170, 230), outline=(40, 60, 80))
        d.polygon([(x + 4, y + 8), (x + 8, y + 6), (x + 8, y + 10)], fill=ORANGE)
        d.polygon([(x + 10, y + 11), (x + 13, y + 9), (x + 13, y + 13)], fill=YELLOW)
    elif fid == "piano":
        d.rectangle([x, y + 2, x + 15, y + 14], fill=(20, 20, 26), outline=(0, 0, 0))
        d.rectangle([x + 1, y + 8, x + 14, y + 12], fill=WHITE)
        for kx in range(2, 14, 3):
            d.rectangle([x + kx, y + 8, x + kx + 1, y + 10], fill=(0, 0, 0))
    elif fid == "gaming":
        d.rectangle([x + 1, y + 1, x + 13, y + 9], fill=(20, 20, 30), outline=(0, 0, 0))
        d.rectangle([x + 2, y + 2, x + 12, y + 8], fill=(180, 80, 240))
        d.rectangle([x + 3, y + 11, x + 12, y + 13], fill=(40, 40, 50))
        d.line([(x + 3, y + 14), (x + 12, y + 14)], fill=(80, 255, 220))
    elif fid == "cake":
        d.rectangle([x + 3, y + 7, x + 12, y + 13], fill=(255, 200, 220), outline=(160, 80, 110))
        d.rectangle([x + 3, y + 7, x + 12, y + 8], fill=WHITE)
        d.line([(x + 7, y + 3), (x + 7, y + 6)], fill=(250, 220, 90))
        d.point((x + 7, y + 2), fill=ORANGE)
    elif fid == "starlamp":
        d.rectangle([x + 6, y + 10, x + 9, y + 15], fill=(80, 80, 100))
        draw_star(d, x + 8, y + 6, 6, YELLOW)
    elif fid == "heart_sign":
        d.rectangle([x, y + 1, x + 15, y + 14], fill=(30, 20, 40), outline=(0, 0, 0))
        d.polygon([(x + 8, y + 12), (x + 3, y + 7), (x + 5, y + 4), (x + 8, y + 6), (x + 11, y + 4), (x + 13, y + 7)],
                  outline=(255, 80, 180))
    elif fid == "pumpkin":
        d.ellipse([x + 1, y + 4, x + 14, y + 15], fill=ORANGE, outline=(140, 70, 0))
        d.rectangle([x + 7, y + 1, x + 8, y + 4], fill=(60, 130, 50))
        d.polygon([(x + 4, y + 8), (x + 6, y + 8), (x + 5, y + 6)], fill=YELLOW)
        d.polygon([(x + 9, y + 8), (x + 11, y + 8), (x + 10, y + 6)], fill=YELLOW)
        d.line([(x + 5, y + 11), (x + 10, y + 11)], fill=YELLOW)
    elif fid == "xmas_tree":
        for i, (w2, ty) in enumerate(((7, 1), (6, 5), (7, 9))):
            d.polygon([(x + 8, y + ty), (x + 8 - w2, y + ty + 5), (x + 8 + w2, y + ty + 5)], fill=(40, 140, 70))
        d.rectangle([x + 7, y + 14, x + 8, y + 15], fill=(110, 70, 40))
        draw_star(d, x + 8, y + 1, 2, YELLOW)
        for px_, py_, c in ((5, 8, RED), (10, 11, CYAN), (7, 12, YELLOW)):
            d.point((x + px_, y + py_), fill=c)
    elif fid == "snowman":
        d.ellipse([x + 3, y + 7, x + 12, y + 15], fill=WHITE, outline=(150, 160, 180))
        d.ellipse([x + 5, y + 1, x + 10, y + 7], fill=WHITE, outline=(150, 160, 180))
        d.point((x + 8, y + 4), fill=ORANGE)
    elif fid == "heart_balloon":
        for ox, c in ((0, RED), (6, (255, 120, 180))):
            d.polygon([(x + 4 + ox, y + 8), (x + 1 + ox, y + 4), (x + 3 + ox, y + 1), (x + 4 + ox, y + 2),
                       (x + 5 + ox, y + 1), (x + 7 + ox, y + 4)], fill=c)
            d.line([(x + 4 + ox, y + 8), (x + 7, y + 15)], fill=(120, 120, 130))


# ---------------- daily gifts, weekly challenges, holiday events ----------------
WEEKLY_GOALS = [  # (text, stat, amount) - progress counts from the start of the week
    ("Solve 8 puzzles", lambda g: len(g.pipes) + len(g.lights) + g.endless, 8),
    ("Finish 5 workbench jobs", lambda g: g.jobs_done, 5),
    ("Finish 5 flashcard rounds", lambda g: g.card_sessions, 5),
    ("Study 60 minutes", lambda g: g.focus_min, 60),
    ("Walk 1500 steps", lambda g: g.steps, 1500),
    ("Place 6 furniture items", lambda g: g.decor_placed, 6),
    ("Earn 150 Bolts", lambda g: g.earned, 150),
]
WEEKLY_REWARD = 40
EXTRA_DEFAULTS = dict(sb=None, job_seed=None, jobs_done=0, built_ok=False, decor=[], furn={}, decor_placed=0,
                      last_day="", streak=0, week_id="", week_goal=0, week_base=0, week_done=False, weeks_done=0,
                      events_bought=0, tut=None, tut_done=False, removed=[], recent=[], sound="on",
                      vol_all=6, vol_music=8, vol_fx=5, vol_voice=6, side_done=[],
                      quest_seed=None, quest_recent=[], quests_done=0, quest_stories=[],
                      started_at=0)   # when this playthrough began: a NEW GAME beats any older game when syncing


def extra_defaults():
    return json.loads(json.dumps(EXTRA_DEFAULTS))   # fresh copies of the lists/dicts


# ---------------- achievements ----------------
MENU_ITEMS = ["QUESTS", "TROPHIES", "BAG", "OUTFIT", "SAVE", "CLOSE"]
ALL_NPCS = sorted({n["id"] for r in ROOMS.values() for n in r["npcs"]})
TOTAL_STASHES = sum(len(r["stashes"]) for r in ROOMS.values())
TOOLS = [it["id"] for it in STORE_ITEMS if it["type"] == "tool"]
ACH_BONUS = 5
ACHIEVEMENTS = [
    ("first_spark", "First Spark", "Fix your very first circuit.", lambda g: len(g.done) >= 1),
] + [
    ("zone%d" % z, "%s Restored" % ZONES[z].title(), "Bring all 3 lights back in %s." % ZONES[z].title(),
     lambda g, z=z: zone_done(g.done, z) >= PER_ZONE) for z in range(NZ)
] + [
    ("lights_on", "Lights On!", "Fix all %d circuits in the facility." % NQ, lambda g: len(g.done) >= NQ),
    ("escaped", "The Great Escape", "Escape through the roof hatch.", lambda g: g.escaped),
    ("snoop", "Snoop", "Search your first stash.", lambda g: len(g.looted) >= 1),
    ("scavenger", "Scavenger", "Search 20 stashes.", lambda g: len(g.looted) >= 20),
    ("treasure", "Treasure Hunter", "Search EVERY stash in the facility.", lambda g: len(g.looted) >= TOTAL_STASHES),
    ("first_note", "Secret Admirer", "Find one of Gio's hidden notes.", lambda g: g.notes_found() >= 1),
    ("love_letters", "Love Letters", "Find all %d of Gio's notes." % len(SECRET_NOTES),
     lambda g: g.notes_found() >= len(SECRET_NOTES)),
    ("shopper", "Retail Therapy", "Buy something at Tess's Store.", lambda g: len(g.owned) > 1 or len(g.upgrades) > 0),
    ("fashion", "Fashionista", "Own every regular outfit.",
     lambda g: all(o["id"] in g.owned for o in OUTFIT_BY_ID.values() if not o.get("event"))),
    ("equipped", "Fully Equipped", "Own every tool.", lambda g: all(t in g.upgrades for t in TOOLS)),
    ("explorer", "Explorer", "Walk 500 steps.", lambda g: g.steps >= 500),
    ("marathon", "Marathon", "Walk 3000 steps.", lambda g: g.steps >= 3000),
    ("social", "Social Butterfly", "Talk to every character.", lambda g: all(k in g.talked for k in ALL_NPCS)),
    ("saver", "Piggy Bank", "Hold 50 Bolts at once.", lambda g: g.bolts >= 50),
    ("collector", "Bolt Collector", "Earn 150 Bolts in total.", lambda g: g.earned >= 150),
    ("tycoon", "Bolt Tycoon", "Earn 400 Bolts in total.", lambda g: g.earned >= 400),
    ("practice", "Practice Makes Perfect", "Replay a circuit you already fixed.", lambda g: g.replays >= 1),
    ("dedicated", "Dedicated Engineer", "Play for one hour.", lambda g: g.play >= 3600),
    ("first_chapter", "Page Turner", "Read your first lesson chapter.", lambda g: len(g.read) >= 1),
    ("all_chapters", "Library Card", "Read every lesson chapter.", lambda g: len(g.read) >= len(CHAPTERS)),
    ("bookworm", "Bookworm", "Finish a flashcard round.", lambda g: g.card_sessions >= 1),
    ("perfect_round", "Perfect Round", "Get 5/5 in a flashcard round.", lambda g: g.perfect_rounds >= 1),
    ("cards20", "Flash Master", "Master 20 flashcards.", lambda g: g.cards_mastered() >= 20),
    ("cards_all", "Walking Encyclopedia", "Master every flashcard.", lambda g: g.cards_mastered() >= len(CARDS)),
    ("focus1", "In The Zone", "Finish a Focus Lamp session.", lambda g: g.focus_sessions >= 1),
    ("focus5", "Study Buddy", "Finish 5 Focus Lamp sessions.", lambda g: g.focus_sessions >= 5),
    ("focus_hour", "Hour Of Power", "Study 60 minutes in total.", lambda g: g.focus_min >= 60),
    ("scholar", "Scholar", "Study 5 hours in total. Wow!", lambda g: g.focus_min >= 300),
    ("pipe1", "Pipe Dream", "Solve a pipe puzzle.", lambda g: len(g.pipes) >= 1),
    ("pipe20", "Plumber Pro", "Solve 20 pipe puzzles.", lambda g: len(g.pipes) >= 20),
    ("pipe_all", "Pipe Master", "Solve all 40 pipe puzzles.", lambda g: len(g.pipes) >= PUZZLES_PER_KIND),
    ("light1", "Bright Idea", "Solve a light grid.", lambda g: len(g.lights) >= 1),
    ("light20", "Lamplighter", "Solve 20 light grids.", lambda g: len(g.lights) >= 20),
    ("light_all", "Illuminator", "Solve all 40 light grids.", lambda g: len(g.lights) >= PUZZLES_PER_KIND),
    ("stars3", "Show Off", "Get 3 stars on a puzzle.", lambda g: g.three_stars() >= 1),
    ("stars40", "Perfectionist", "Get 3 stars on 40 puzzles.", lambda g: g.three_stars() >= 40),
    ("stars_all", "Flawless", "Get 3 stars on all 80 puzzles.", lambda g: g.three_stars() >= 2 * PUZZLES_PER_KIND),
    ("endless", "Can't Stop", "Solve 10 endless puzzles.", lambda g: g.endless >= 10),
    ("first_build", "Mad Scientist", "Build a working circuit at the workbench.", lambda g: g.built_ok),
    ("job1", "Hired!", "Finish a workbench job.", lambda g: g.jobs_done >= 1),
    ("job10", "Reliable Engineer", "Finish 10 workbench jobs.", lambda g: g.jobs_done >= 10),
    ("job50", "Chief Engineer", "Finish 50 workbench jobs.", lambda g: g.jobs_done >= 50),
    ("job100", "Legendary Builder", "Finish 100 workbench jobs.", lambda g: g.jobs_done >= 100),
    ("decor1", "Home Sweet Home", "Place furniture in your room.", lambda g: len(g.decor) >= 1),
    ("decor15", "Interior Designer", "Have 15 items in your room.", lambda g: len(g.decor) >= 15),
    ("decor40", "Dream House", "Have 40 items in your room.", lambda g: len(g.decor) >= 40),
    ("streak3", "Coming Back", "Play 3 days in a row.", lambda g: g.streak >= 3),
    ("streak7", "Daily Devotion", "Play 7 days in a row.", lambda g: g.streak >= 7),
    ("weekly1", "Weekly Winner", "Finish a weekly challenge.", lambda g: g.weeks_done >= 1),
    ("weekly5", "Challenge Champ", "Finish 5 weekly challenges.", lambda g: g.weeks_done >= 5),
    ("event1", "Festive!", "Buy 10 holiday decorations.", lambda g: g.events_bought >= 10),
    ("tour", "Welcome Aboard", "Finish the Volta Labs tour.", lambda g: g.tut_done),
    ("decor_rooms", "Decorate The World", "Put furniture in 5 different rooms.",
     lambda g: len({e[0] for e in g.decor}) >= 5),
    ("decor_all", "Home Is Everywhere", "Decorate every zone of the facility.",
     lambda g: all(any(e[0] == "z%d" % z for e in g.decor) for z in range(NZ))),
]
ACHIEVEMENTS.append(("legend", "LEGEND", "Unlock every other trophy. You're amazing!",
                     lambda g: len(g.ach) >= len(ACHIEVEMENTS) - 1))


def make_confetti(n=44):
    cols = [YELLOW, GREEN, CYAN, RED, ORANGE, WHITE]
    return [(random.uniform(0, W), random.uniform(-80, 0), random.uniform(-20, 20), random.uniform(40, 90),
             random.choice(cols)) for _ in range(n)]


def draw_confetti(d, parts, t):
    for x, y0, vx, vy, col in parts:
        x2 = x + vx * t + math.sin(t * 5 + x) * 6
        y2 = y0 + vy * t + 10 * t * t
        if 0 <= y2 < H:
            d.rectangle([x2, y2, x2 + 2, y2 + 3], fill=col)


class NPC:
    def __init__(self, dd):
        self.key = dd["id"]
        self.tx, self.ty = dd["x"], dd["y"]
        self.px, self.py = self.tx * TS, self.ty * TS
        self.home = (self.tx, self.ty)
        self.wander = dd.get("wander", 0)
        self.face = dd.get("face", "down")
        self.role = dd.get("role", "talk")
        self.lines = dd["lines"]
        self.next_move = time.time() + random.uniform(1, 3)

    @property
    def moving(self):
        return self.px != self.tx * TS or self.py != self.ty * TS

    def update(self, game, now, dt):
        if self.moving:
            sp = 36 * dt
            self.px = slide(self.px, self.tx * TS, sp)
            self.py = slide(self.py, self.ty * TS, sp)
        elif self.wander and now >= self.next_move and not game.dialog and game.tut is None:   # staff hold still during the tour
            self.next_move = now + random.uniform(1.5, 4.5)
            if abs(self.tx - game.tx) + abs(self.ty - game.ty) <= 2:
                return   # hold still while the player is close, so nobody wanders into her way
            name = random.choice(list(DIRS))
            dx, dy = DIRS[name]
            nx, ny = self.tx + dx, self.ty + dy
            self.face = name
            if abs(nx - self.home[0]) <= self.wander and abs(ny - self.home[1]) <= self.wander \
                    and game.free(nx, ny, self):
                self.tx, self.ty = nx, ny


# ---------------- the game ----------------
class Game:
    def __init__(self):
        s = load_progress()
        self.sv = s
        self.has_save = s["exists"]
        self.done, self.outfit_idx, self.upgrades = s["done"], s["outfit"], s["upgrades"]
        self.bolts, self.owned, self.escaped = s["bolts"], s["owned"], s["escaped"]
        self.looted = s["looted"]
        self.ach, self.quiz, self.talked = s["ach"], s["quiz"], s["talked"]
        self.steps, self.earned, self.replays, self.play = s["steps"], s["earned"], s["replays"], s["play"]
        self.toasts, self.toast_t0 = [], None
        for k in STUDY_KEYS + tuple(EXTRA_DEFAULTS):
            setattr(self, k, s[k])
        if self.quest_seed is not None:   # an unfinished job from last time
            self.install_job(self.quest_seed)
        if not self.sb:
            self.sb = [[None] * SB_COLS for _ in range(SB_ROWS)]
        self.decor = [e if len(e) == 4 else ["jroom"] + list(e) for e in self.decor]
        self.removed_set = {tuple(e) for e in self.removed}
        self.bench, self.ovl, self.dec, self.design_item = None, None, None, None
        self.daily_checked, self.weekly_t, self.tour_menu_seen = False, 0.0, False
        self.focus, self.pz, self.card_run, self.story_run, self.book, self.library_sel = None, None, None, None, None, 0
        self.mode = "title"
        self.title_sel, self.title_confirm, self.confirm_sel = 0, False, 1
        self.room = s["room"] if s["room"] in ROOMS else "z0"
        self.tx, self.ty = s["tx"], s["ty"]
        self.px, self.py = self.tx * TS, self.ty * TS
        self.facing = "down"
        self.walking = False
        self.walk_since = None   # when the current non-stop walk began (holding a direction turns into a jog)
        self.queued = None       # a direction tapped mid-step, so quick taps are never lost
        self.npcs = []
        self.dialog = None
        self.menu = None
        self.fade = None
        self.bump_t = 0.0
        self.shop_sel, self.shop_top, self.shop_msg, self.shop_msg_t = 0, 0, "", 0.0
        self.level, self.step, self.state, self.page = 0, 0, "intro", 0
        self.expanded, self.win_page = False, 0
        self.confetti, self.win_t, self.reward = [], 0.0, 0
        self.just_won, self.zone_clear = False, None
        self.msg_key, self.msg_t0 = None, 0.0
        self.end_t0 = 0.0
        self.now = time.time()
        if UNLOCK_ALL:
            self.unlock_everything()
        self.spawn_npcs()

    def unlock_everything(self):
        """Test mode: the whole game already finished, with everything owned."""
        self.done = set(range(NQ))
        self.escaped, self.tut, self.tut_done = True, None, True
        self.bolts = 99999
        self.owned = set(OUTFIT_BY_ID)
        self.upgrades = {it["id"] for it in STORE_ITEMS if it["type"] == "tool"}
        self.furn = {fid: 10 for fid in FURNITURE}
        self.read = set(range(len(CHAPTERS)))
        self.story |= {"enter%d" % z for z in ZONE_ENTER} | {"clear%d" % z for z in ZONE_CLEAR} | \
            {"jroom", "decor_unlock"}
        self.daily_checked = True
        self.room, self.tx, self.ty = "z0", 9, 9
        self.px, self.py = self.tx * TS, self.ty * TS
        self.has_save = True   # title screen offers CONTINUE straight into the game

    # ----- state helpers
    @property
    def zone(self):
        return ROOMS[self.room]["zone"]

    def speed(self):
        return 84 if "boots" in self.upgrades else 64

    def install_job(self, seed):
        """Put job number `seed` into the job quest slot (same seed = same job, so it survives a restart)."""
        self.quest_seed = seed
        LEVELS[JOB_SLOT] = make_quest_job(seed, self.quest_recent, self.quest_stories)
        for key in [k for k in _cache if k[0] == JOB_SLOT]:
            del _cache[key]

    def save(self):
        write_progress(dict(done=self.done, outfit=self.outfit_idx, upgrades=self.upgrades, bolts=self.bolts,
                            owned=self.owned, looted=self.looted, ach=self.ach, quiz=self.quiz, talked=self.talked,
                            steps=self.steps, earned=self.earned, replays=self.replays, play=self.play,
                            **{k: getattr(self, k) for k in STUDY_KEYS + tuple(EXTRA_DEFAULTS)}, room=self.room, tx=self.tx, ty=self.ty, intro=False, escaped=self.escaped))
        self.has_save = True

    def gain(self, n):
        if n > 0:
            AUDIO.play("coin")
        self.bolts += n
        self.earned += n

    def cards_mastered(self):
        return sum(1 for v in self.cards.values() if v >= 3)

    def three_stars(self):
        return sum(1 for v in self.pipes.values() if v >= 3) + sum(1 for v in self.lights.values() if v >= 3)

    def notes_found(self):
        return sum(1 for k in SECRET_NOTES if k in self.looted)

    def check_ach(self):
        new = True
        while new:   # a trophy's bonus Bolts can unlock another trophy
            new = False
            for aid, name, _desc, fn in ACHIEVEMENTS:
                if aid not in self.ach and fn(self):
                    self.ach.add(aid)
                    self.toasts.append(name)
                    AUDIO.play("trophy")
                    self.gain(ACH_BONUS * (10 if aid == "legend" else 1))
                    new = True

    def spawn_npcs(self):
        self.npcs = [NPC(n) for n in ROOMS[self.room]["npcs"] if not (self.tut is not None and n["id"] == "gio")]
        self.trail = []

    def powered(self, zone):
        """How lit a zone is: fully lit during the prologue tour, otherwise by circuits fixed."""
        return 3 if self.tut is not None or zone is None else zone_done(self.done, zone)

    def tile(self, tx, ty):
        if 0 <= tx < MW and 0 <= ty < MH:
            if (self.room, tx, ty) in self.removed_set:
                return "."   # she removed whatever was here while decorating
            return ROOMS[self.room]["map"][ty][tx]
        return "#"

    def door_unlocked(self, tx, ty):
        dd = ROOMS[self.room]["doors"].get((tx, ty))
        if not dd:
            return False
        need = dd.get("need")
        return need is None or zone_done(self.done, need) >= PER_ZONE or (self.tut is not None and need == 0)

    def free(self, tx, ty, who=None):
        ch = self.tile(tx, ty)
        if ch in SOLID or (ch == "R" and not self.door_unlocked(tx, ty)):
            return False
        if ch == "L" and (tx, ty) not in ROOMS[self.room]["doors"]:
            return False
        if who is not None and (tx, ty) == (self.tx, self.ty):
            return False
        if who is not None and ch in "LRSED":
            return False   # NPCs never stand in doorways
        for n in self.npcs:
            if n is not who and (n.tx, n.ty) == (tx, ty):
                return False
        fid = self.furniture_at(tx, ty)
        if fid and FURNITURE[fid][2]:
            return False
        return True

    def items_at(self, tx, ty, room=None):
        room = room or self.room
        return [fid for r, x, y, fid in self.decor if r == room and (x, y) == (tx, ty)]

    def furniture_at(self, tx, ty, room=None):
        """The top item on a tile: furniture first, otherwise a floor tile."""
        here = self.items_at(tx, ty, room)
        top = [f for f in here if f not in FLOOR_IDS]
        return (top or here or [None])[-1]

    def removable_here(self, x, y):
        """Built-in objects she may clear out while decorating (never terminals, doors, machines or study stuff)."""
        key = "%s:%d:%d" % (self.room, x, y)
        if key in SECRET_NOTES and key not in self.looted:
            return False   # never throw away one of Gio's notes before she finds it
        return self.room not in NO_REMOVE_ROOMS and self.tile(x, y) in REMOVABLE

    def can_decorate(self):
        return self.room == "jroom" or self.escaped   # every room opens up once the facility is free

    def placeable(self, x, y, fid):
        """None if the spot is fine, else the reason it isn't (so doors/terminals never get blocked)."""
        if self.tile(x, y) not in ".r":
            return "Furniture has to go on the floor."
        here = self.items_at(x, y)
        if fid in FLOOR_IDS and any(f in FLOOR_IDS for f in here):
            return "There's already a floor tile there."
        if fid not in FLOOR_IDS and any(f not in FLOOR_IDS for f in here):
            return "Something is already there."
        if any((n.tx, n.ty) == (x, y) for n in self.npcs):
            return "Someone is standing there!"
        if FURNITURE[fid][2]:
            if (x, y) == (self.tx, self.ty):
                return "You're standing right there!"
            for dx, dy in DIRS.values():
                if self.tile(x + dx, y + dy) in "123xKFTPQGJSDLRE":
                    return "That would block a door or machine. Try a spot further away."
        return None

    # ----- dialogue
    def say(self, lines, choices=None, cb=None):
        """lines: list of (char_key or None, text)."""
        self.dialog = dict(lines=lines, i=0, t0=self.now, choices=choices, sel=0, cb=cb)
        self.queued = None

    def dialog_press(self, b):
        dg = self.dialog
        key, text = dg["lines"][dg["i"]]
        typed = int((self.now - dg["t0"]) * 45) >= len(text)
        last = dg["i"] == len(dg["lines"]) - 1
        if typed and last and dg["choices"]:
            n = len(dg["choices"])
            if b == "up":
                dg["sel"] = (dg["sel"] - 1) % n
            elif b == "down":
                dg["sel"] = (dg["sel"] + 1) % n
            elif b == "click" or (b == "left" and dg["choices"][-1] in EXIT_CHOICES):
                sel = dg["sel"] if b == "click" else n - 1   # LEFT always backs out
                cb = dg["cb"]
                self.dialog = None
                if cb:
                    cb(sel)
            return
        if b != "click":
            return
        if not typed:
            dg["t0"] = -1e9
        elif not last:
            dg["i"] += 1
            dg["t0"] = self.now
        else:
            cb = dg["cb"]
            self.dialog = None
            if cb:
                cb(0)

    # ----- transitions
    def fade_to(self, cb):
        if not self.fade:
            self.fade = dict(phase="out", t=0.0, cb=cb)

    def go(self, to, x=0, y=0, face="down"):
        if to == "ending":
            self.fade_to(self.start_ending)
        else:
            self.fade_to(lambda: self.enter_room(to, x, y, face))

    def enter_room(self, rid, x, y, face):
        self.room = rid
        self.tx, self.ty = x, y
        self.px, self.py = x * TS, y * TS
        self.facing = face
        self.walking, self.walk_since, self.queued = False, None, None
        self.spawn_npcs()
        AUDIO.play("door")
        bx, by = DIRS[face]
        self.trail = [(self.px - bx * TS, self.py - by * TS, face, False)]
        self.mode = "world"
        self.check_ach()
        self.save()
        z = ROOMS[rid]["zone"]
        if self.tut is not None:
            pass   # the story scenes start after the blackout
        elif z in ZONE_ENTER:
            self.story_beat("enter%d" % z, ZONE_ENTER[z])
        elif rid == "jroom":
            self.story_beat("jroom", [
                ("gio", "Surprise! While we're stuck here, I set up a room just for you."),
                ("gio", "And look who's here: Canica, Gummy, Sofia... and Lafufu in her tank! I wasn't leaving them behind."),
                ("jas", "BABIES!! Oh my gosh, hi you guys!"),
                ("gio", "It's kind of empty... Buy furniture at Tess's store and it gets delivered here."),
                (None, "To decorate: press CENTER on empty floor and choose DECORATE.")])

    def after_ending(self):
        self.enter_room("z%d" % (NZ - 1), 18, 7, "left")
        self.story_beat("decor_unlock", [
            ("gio", "The whole facility is ours now... and honestly? It could use some decorating."),
            ("max", "DECORATION PERMISSIONS GRANTED. YOU MAY DECORATE ANY ROOM IN VOLTA LABS."),
            (None, "You can now decorate EVERY room! Press CENTER on empty floor and choose DECORATE.")])

    # ----- input
    def on_press(self, b, now):
        self.now = now
        if self.fade:
            return
        if not (self.mode == "world" and not self.dialog and not self.menu and b != "click"):
            AUDIO.play("select" if b == "click" else "back" if b == "left" and (self.menu or self.mode == "shop") else "blip")
        m = self.mode
        if m == "title":
            self.title_press(b, now)
        elif m == "world":
            if self.dialog:
                self.dialog_press(b)
            elif self.menu:
                self.menu_press(b)
            elif b == "click":
                self.interact(now)
            elif b in DIRS:
                self.queued = b
        elif m == "shop":
            self.shop_press(b, now)
        elif m == "build":
            self.build_press(b, now)
        elif m == "focus":
            self.focus_press(b, now)
        elif m == "library":
            self.library_press(b, now)
        elif m == "book":
            self.book_press(b, now)
        elif m == "story":
            self.story_press(b, now)
        elif m == "bench":
            self.bench_press(b, now)
        elif m == "decor":
            self.decor_press(b, now)
        elif m == "puzzle":
            self.puzzle_press(b, now)
        elif m == "ending":
            if b == "click" and now - self.end_t0 > 2.0:
                self.fade_to(self.after_ending)

    def title_press(self, b, now):
        items = self.title_items()
        if self.title_confirm:
            if b in ("up", "down"):
                self.confirm_sel = 1 - self.confirm_sel
            elif b == "click":
                if self.confirm_sel == 0:
                    self.new_game()
                self.title_confirm = False
            elif b == "left":
                self.title_confirm = False
            return
        if b == "up":
            self.title_sel = (self.title_sel - 1) % len(items)
        elif b == "down":
            self.title_sel = (self.title_sel + 1) % len(items)
        elif b == "click":
            if items[self.title_sel] == "CONTINUE":
                self.fade_to(lambda: self.enter_room(self.room, self.tx, self.ty, "down"))
            elif self.has_save:
                self.title_confirm, self.confirm_sel = True, 1
            else:
                self.new_game()

    def title_items(self):
        return ["CONTINUE", "NEW GAME"] if self.has_save else ["NEW GAME"]

    # ----- prologue tour (before the blackout)
    def tour_goal(self):
        return TOUR[self.tut]["goal"] if self.tut is not None else None

    def start_tour(self):
        self.tut, self.tour_menu_seen = 0, False
        self.spawn_npcs()
        self.say(TOUR[0]["say"])

    def tour_next(self):
        self.tut += 1
        self.tour_menu_seen = False
        self.save()
        self.say(TOUR[self.tut]["say"])

    def tour_finale(self):
        self.say(TOUR_FINALE, cb=lambda _s: self.finish_tour())

    def finish_tour(self):
        self.tut, self.tut_done = None, True
        self.gain(TOUR_REWARD)
        self.check_ach()
        self.fade_to(self.begin_blackout)

    def skip_tour(self):
        self.tut, self.tut_done = None, True
        self.fade_to(self.begin_blackout)

    def begin_blackout(self):
        def wake():
            self.enter_room("z0", 3, 9, "up")
            self.say(WAKE_LINES)
        self.play_story(BLACKOUT_SLIDES, lambda: self.fade_to(wake))

    def tour_check(self):
        """Goals about where she is or what's open (talking and searching are checked where they happen)."""
        goal = self.tour_goal()
        step = TOUR[self.tut]
        if goal == "reach" and not self.walking and (self.tx, self.ty) == step["target"]:
            self.tour_next()
        elif goal == "room" and self.room == step["dest"]:
            self.tour_next()
        elif goal == "menu":
            if self.menu:
                self.tour_menu_seen = True
            elif self.tour_menu_seen:
                self.tour_next()

    def new_game(self):
        self.done, self.upgrades, self.bolts, self.owned = set(), set(), 0, {0}
        self.outfit_idx, self.escaped, self.looted = 0, False, set()
        self.ach, self.quiz, self.talked = set(), set(), set()
        self.steps, self.earned, self.replays, self.play = 0, 0, 0, 0.0
        self.cards, self.pipes, self.lights, self.read, self.story = {}, {}, {}, set(), set()
        self.card_sessions = self.perfect_rounds = self.focus_sessions = self.focus_min = self.endless = 0
        for k, v in extra_defaults().items():
            setattr(self, k, v)
        self.sb = [[None] * SB_COLS for _ in range(SB_ROWS)]
        self.daily_checked = False
        self.removed_set = set()
        self.started_at = round(time.time(), 1)   # brand-new playthrough
        self.save()   # so her phone sees the new game straight away

        def arrive():
            self.tut = 0   # lights on, staff in place, Gio tagging along
            self.enter_room("z0", 3, 9, "right")
            self.say(TOUR_INTRO, choices=["START THE TOUR", "SKIP TOUR"],
                     cb=lambda s: self.start_tour() if s == 0 else self.skip_tour())
        self.fade_to(lambda: self.play_story(PROLOGUE_SLIDES, lambda: self.fade_to(arrive)))

    # ----- story cutscenes
    def play_story(self, slides, cb):
        self.story_run = dict(slides=slides, i=0, t0=self.now, cb=cb)
        self.mode = "story"

    def story_press(self, b, now):
        sr = self.story_run
        text = sr["slides"][sr["i"]][1]
        if b == "left":   # skip the whole cutscene
            self.mode = "blank"
            sr["cb"]()
        elif b == "click":
            if int((now - sr["t0"]) * 40) < len(text):
                sr["t0"] = -1e9
            elif sr["i"] < len(sr["slides"]) - 1:
                sr["i"], sr["t0"] = sr["i"] + 1, now
            else:
                self.mode = "blank"
                sr["cb"]()

    def story_beat(self, key, lines, cb=None):
        """Say a story scene once; afterwards it never repeats."""
        if key in self.story:
            if cb:
                cb(0)
            return
        self.story.add(key)
        self.save()
        self.say(lines, cb=cb)

    def target_at(self, tx, ty, examine):
        """What CENTER would do with tile (tx, ty), or None. Stashes only count when you face them."""
        for n in self.npcs:
            if (n.tx, n.ty) == (tx, ty):
                return lambda: self.talk(n)
        ch = self.tile(tx, ty)
        if ch in "123" and self.zone is not None:
            q = self.zone * PER_ZONE + int(ch) - 1
            return lambda: self.quest_prompt(q)
        if ch == "x":
            return lambda: self.open_shop(self.npcs[0] if self.npcs else None)
        if ch == "K":
            return self.open_library
        if ch == "F":
            return self.study_cards
        if ch == "T":
            return self.focus_prompt
        if ch in "PQ":
            return lambda: self.puzzle_prompt("pipe" if ch == "P" else "lights")
        if ch == "G":
            return self.open_bench
        if ch == "J":
            return self.job_board
        fid = self.furniture_at(tx, ty)
        if examine and fid:
            return lambda: self.say([("jas", "My %s! I love it here." % FURNITURE[fid][0].lower()),
                                     (None, "(To move it: CENTER on empty floor, then pick DECORATE.)")])
        if examine and ch in STASH:
            return lambda: self.search(tx, ty, ch)
        return None

    def interact(self, now):
        # whatever she faces first, then people/terminals on any side - no fiddly lining up needed
        order = [self.facing] + [k for k in DIRS if k != self.facing]
        for i, name in enumerate(order):
            dx, dy = DIRS[name]
            act = self.target_at(self.tx + dx, self.ty + dy, examine=(i == 0))
            if act:
                self.facing = name
                act()
                return
        self.menu = dict(page="main", sel=0, scroll=0, msg="")

    def search(self, tx, ty, ch):
        if ch == "v":
            self.say([("jas", random.choice(VENT_LINES))])
            return
        key = "%s:%d:%d" % (self.room, tx, ty)
        if key in self.looted:
            self.say([(None, "You already searched this %s. Nothing left but dust." % STASH[ch])])
            return
        self.looted.add(key)
        if key in SECRET_NOTES:
            text, found = SECRET_NOTES[key]
            after = [("jas", random.choice(NOTE_REACTIONS)),
                     (None, "Gio's notes found: %d / %d" % (self.notes_found(), len(SECRET_NOTES)))]
        else:
            r = random.Random(key)
            found = r.choice((0, 1, 2, 2, 3))
            text = ("Found %d Bolt%s stashed inside!" % (found, "" if found == 1 else "s")) if found else r.choice(JUNK)
            after = []
        if "lucky_charm" in self.upgrades:
            found += 1
            after.append((None, "Your Lucky Charm sparkles... +1 bonus Bolt!"))
        self.gain(found)
        self.check_ach()
        self.save()
        tour_hit = self.tour_goal() == "search" and (tx, ty) == TOUR[self.tut]["target"]
        self.say([(None, SEARCH_OPEN[ch]), (None, text)] + after, cb=(lambda _s: self.tour_next()) if tour_hit else None)

    def talk(self, n):
        if self.tut is not None and n.key == TOUR[self.tut].get("npc"):
            n.face = OPP[self.facing]
            self.tour_finale() if self.tour_goal() == "finale" else self.tour_next()
            return
        if n.role == "pet":
            n.face = OPP[self.facing]
            self.talked.add(n.key)
            self.check_ach()
            self.say(random.choice(PET_TALK[n.key]))
            return
        if self.tut is not None and n.role != "shop":
            self.say([(n.key, TOUR_CHAT.get(n.key, "Welcome to Volta Labs! Enjoy the tour."))])
            return
        n.face = OPP[self.facing]
        self.talked.add(n.key)
        self.check_ach()
        k = "start"
        if n.role != "shop" and self.zone is not None:
            c = zone_done(self.done, self.zone)
            k = "start" if c == 0 else "done" if c >= PER_ZONE else "mid"
        lines = n.lines.get(k) or n.lines["start"]
        if n.role == "shop":
            self.say([(n.key, t) for t in lines], cb=lambda _s: self.open_shop(n))
        else:
            self.say([(n.key, t) for t in lines])

    def quest_prompt(self, q):
        if self.tut is not None:
            self.say([(LEVELS[q]["npc"], "That terminal's running just fine right now. Let's keep the tour going!")])
            return
        L = LEVELS[q]
        done = q in self.done or q in self.side_done
        tag = "Q%d" % (q + 1) if q < NQ else "New job (+%d Bolts)" % L["reward"] if q == JOB_SLOT else "Side quest"
        done = done and q != JOB_SLOT
        lines = ([(L["npc"], L["story"])] if L.get("story") else []) + [
                 (L["npc"], "%s: %s. %s" % (tag, L["title"], "Already fixed - replay for practice?" if done else L["hint"])),
                 (None, "Parts: " + ", ".join("%d %s" % p for p in L["parts"]) + ".")]
        self.say(lines, choices=["START", "NOT NOW"], cb=lambda s: self.fade_to(lambda: self.enter_build(q)) if s == 0 else None)

    def enter_build(self, q):
        self.mode, self.level, self.step, self.state = "build", q, 0, "intro"
        self.expanded, self.win_page, self.just_won, self.zone_clear = False, 0, False, None
        self.page = 0

    def build_pages(self, step=None):
        """What gets said at a step: (speaker, text) pages. Step 0 is the intro, then Gio guides each part."""
        L = LEVELS[self.level]
        step = self.step if step is None else step
        if step == 0:
            pages = ([(L["npc"], L["story"])] if L.get("story") else []) + [(L["npc"], L["hint"])]
            if self.level == 0:   # the very first circuit gets a breadboard tour
                pages += [("gio", t) for t in BREADBOARD_INTRO]
            return pages
        pages = [("gio", t) for t in L["steps"][step - 1]["pages"]]
        if step == len(L["steps"]):
            sp, t = pages[-1]
            pages[-1] = (sp, t + " Press CENTER to power it up!")
        return pages

    # ----- quest screen
    def build_press(self, b, now):
        N = len(LEVELS[self.level]["steps"])
        if self.state == "win":
            if b == "click":
                if self.win_page == 0:
                    self.win_page = 1
                else:
                    self.fade_to(self.leave_build)
            return
        last_page = self.page >= len(self.build_pages()) - 1
        if b in ("right", "click"):
            if not last_page:
                self.page += 1   # more of Gio's tips for this step
            elif self.step < N:
                self.step, self.page = self.step + 1, 0
            elif b == "click":
                self.win(now)
        elif b == "left":
            if self.page > 0:
                self.page -= 1
            elif self.step > 0:
                self.step -= 1
                self.page = len(self.build_pages()) - 1
        elif b == "down":
            self.expanded = not self.expanded
        elif b == "up":
            self.fade_to(self.leave_build)

    def win(self, now):
        q = self.level
        AUDIO.play("pew" if any(st["part"] == "laser" for st in LEVELS[q]["steps"]) else "power")
        self.state, self.win_t, self.win_page = "win", now, 0
        self.confetti = make_confetti()
        self.reward = 0
        if q == JOB_SLOT:   # endless job: pays every time, then the next one will be a new circuit
            self.reward = LEVELS[q]["reward"] + (2 if "gold_wires" in self.upgrades else 0)
            self.gain(self.reward)
            self.quests_done += 1
            self.jobs_done += 1
            self.quest_recent = self.quest_recent + [LEVELS[q]["sig"]]      # every circuit she's built
            self.quest_stories = self.quest_stories + [LEVELS[q]["sid"]]   # every story she's heard
            self.quest_seed = None
        elif q >= NQ:   # side quest: full Bolts the first time, half for replays, no zone doors involved
            if q not in self.side_done:
                self.side_done.append(q)
                self.reward = SIDE_REWARD
            else:
                self.reward = SIDE_REWARD // 2
                self.replays += 1
            self.gain(self.reward)
        elif q not in self.done:
            self.done.add(q)
            self.reward = quest_reward(q) + (2 if "gold_wires" in self.upgrades else 0)
            self.gain(self.reward)
            if zone_done(self.done, q // PER_ZONE) >= PER_ZONE:
                self.zone_clear = q // PER_ZONE
        else:
            self.replays += 1
        self.just_won = True
        self.check_ach()
        self.save()

    def leave_build(self):
        self.mode = "world"
        if not self.just_won:
            return
        self.just_won = False
        self.after_quest()

    def after_quest(self):
        if len(self.done) >= NQ and not self.escaped:
            self.say([("skye", "The beacons are blazing! My chopper can see us!"),
                      ("max", "ALL %d CIRCUITS ONLINE. POWER AT 100%%. LIFTING THE LOCKDOWN... NOW." % NQ),
                      ("gio", "The roof hatch is open, Jaslyne! We did it. Let's go home!")],
                     cb=lambda _s: self.go("ending"))
        elif self.zone_clear is not None:
            z = self.zone_clear
            self.zone_clear = None
            self.story_beat("clear%d" % z, ZONE_CLEAR.get(z, []) + [
                (None, "The door on the right side of this room is now unlocked.")])

    def start_ending(self):
        self.escaped = True
        self.check_ach()
        self.save()

        def show_end():
            self.mode, self.end_t0 = "ending", self.now
        self.play_story(ENDING_SLIDES, show_end)

    # ----- study room: flashcards
    def study_cards(self, chapter=None):
        """Flashcards only ask about chapters she has read (or one chapter, straight after reading it)."""
        chs = [chapter] if chapter is not None else sorted(self.read)
        if not chs:
            self.say([("page", "Read a chapter at the red BOOK STANDS first! Then the flashcards will make sense.")])
            return
        cards = [c for ch in chs for c in CHAPTERS[ch]["cards"]]
        # unmastered cards first, shuffled
        pool = sorted(cards, key=lambda i: (self.cards.get(i, 0) >= 3, random.random()))[:5]
        self.card_run = dict(pool=pool, i=0, right=0)
        what = ("'%s'" % CHAPTERS[chapter]["title"]) if chapter is not None else "the %d chapter%s you've read" % (
            len(chs), "" if len(chs) == 1 else "s")
        self.say([("page", "Flashcards on %s! +1 Bolt per right answer, +5 more for 5/5." % what),
                  (None, "Cards mastered: %d / %d  (a card is mastered after 3 right answers)" %
                   (self.cards_mastered(), len(CARDS)))],
                 choices=["LET'S GO", "NOT NOW"], cb=lambda s: self.next_card() if s == 0 else None)

    # ----- study room: lesson books
    def open_library(self):
        self.library_sel = next((i for i in range(len(CHAPTERS)) if i not in self.read), 0)
        self.mode = "library"

    def library_press(self, b, now):
        n = len(CHAPTERS)
        if b == "up":
            self.library_sel = (self.library_sel - 1) % n
        elif b == "down":
            self.library_sel = (self.library_sel + 1) % n
        elif b == "left":
            self.mode = "world"
        elif b == "click":
            self.book = dict(ch=self.library_sel, page=0)
            self.mode = "book"
        elif b == "right":
            ch = self.library_sel
            self.mode = "world"
            if ch in self.read:
                self.study_cards(ch)
            else:
                self.say([("page", "Read this chapter first, then its flashcards unlock!")])

    def book_press(self, b, now):
        bk = self.book
        pages = CHAPTERS[bk["ch"]]["pages"]
        if b in ("right", "click"):
            if bk["page"] < len(pages) - 1:
                bk["page"] += 1
            else:
                self.finish_chapter()
        elif b == "left":
            if bk["page"] > 0:
                bk["page"] -= 1
            else:
                self.mode = "library"
        elif b == "up":
            self.mode = "library"

    def finish_chapter(self):
        ch = self.book["ch"]
        first = ch not in self.read
        self.read.add(ch)
        if first:
            self.gain(5)
        self.check_ach()
        self.save()
        self.mode = "world"
        msg = "Chapter done!%s Want to test yourself on it with flashcards now?" % (" +5 Bolts." if first else "")
        self.say([("page", msg)], choices=["FLASHCARDS", "NOT NOW"],
                 cb=lambda s: self.study_cards(ch) if s == 0 else None)

    def next_card(self):
        run = self.card_run
        if run["i"] >= len(run["pool"]):
            self.finish_cards()
            return
        c = run["pool"][run["i"]]
        question, answers = CARDS[c]
        order = list(range(len(answers)))
        random.shuffle(order)

        def answered(sel):
            if sel == len(order):   # EXIT
                self.save()   # cards already answered keep their progress
                self.say([("page", "No problem! Come back any time. You got %d right this round." % run["right"])])
                return
            run["i"] += 1
            if order[sel] == 0:
                run["right"] += 1
                self.cards[c] = self.cards.get(c, 0) + 1
                self.gain(1)
                msg = "Correct! +1 Bolt." + ("  CARD MASTERED!" if self.cards[c] == 3 else "")
            else:
                msg = "Oops! The answer is '%s'." % answers[0]
            self.say([(None, msg)], cb=lambda _s: self.next_card())
        self.say([(None, "Card %d/%d: %s" % (run["i"] + 1, len(run["pool"]), question))],
                 choices=[answers[i] for i in order] + ["EXIT"], cb=answered)

    def finish_cards(self):
        run = self.card_run
        self.card_sessions += 1
        lines = [("page", "Round done! You got %d out of %d." % (run["right"], len(run["pool"])))]
        if run["right"] == len(run["pool"]):
            self.perfect_rounds += 1
            self.gain(5)
            lines.append(("page", "A perfect round! Here's 5 bonus Bolts. Brilliant!"))
        lines.append((None, "Cards mastered: %d / %d" % (self.cards_mastered(), len(CARDS))))
        self.check_ach()
        self.save()
        self.say(lines)

    # ----- study room: focus lamp (real-life study timer)
    def focus_prompt(self):
        lines = [("page", "The Focus Lamp! Study for real - homework, reading, anything - and earn Bolts while you do."),
                 ("page", "So far: %d minutes over %d sessions. How long this time?" % (self.focus_min, self.focus_sessions))]
        opts = ["%d MIN" % m for m in FOCUS_OPTIONS] + ["NOT NOW"]
        self.say(lines, choices=opts,
                 cb=lambda s: self.fade_to(lambda: self.start_focus(FOCUS_OPTIONS[s])) if s < len(FOCUS_OPTIONS) else None)

    def start_focus(self, minutes):
        self.focus = dict(minutes=minutes, end=self.now + minutes * 60, left=minutes * 60.0, paused=False, quit_t=-9.0)
        self.mode = "focus"

    def focus_reward(self, minutes, complete):
        r = minutes * 2 // 5 + 2 if complete else minutes // 5
        return r + r // 4 if "cozy_tea" in self.upgrades else r

    def focus_press(self, b, now):
        f = self.focus
        if b == "click":
            if f["paused"]:
                f["end"], f["paused"] = now + f["left"], False
            else:
                f["paused"] = True
        elif b == "left":
            if now - f["quit_t"] < 2.0:
                self.finish_focus(False)
            else:
                f["quit_t"] = now

    def finish_focus(self, complete):
        f = self.focus
        studied = f["minutes"] if complete else int((f["minutes"] * 60 - max(0, f["left"])) // 60)
        reward = self.focus_reward(studied, complete)
        self.focus_min += studied
        if complete:
            self.focus_sessions += 1
        self.gain(reward)
        self.mode = "world"
        if complete:
            lines = [("gio", "Session complete!! I'm so proud of you, Jaslyne."),
                     (None, "+%d Bolts. Total study time: %d min." % (reward, self.focus_min))]
        else:
            lines = [("gio", "Stopping early is okay. You still studied %d min - every bit counts!" % studied),
                     (None, "+%d Bolts. Total study time: %d min." % (reward, self.focus_min))]
        self.check_ach()
        self.save()
        self.say(lines)

    # ----- puzzle lab
    def puzzle_prompt(self, kind):
        done = self.pipes if kind == "pipe" else self.lights
        name = "PIPE PUZZLE" if kind == "pipe" else "LIGHT GRID"
        how = ("Spin the pipes to connect the battery to the light bulb." if kind == "pipe"
               else "Make every light bulb turn ON.")
        nxt = next((i for i in range(PUZZLES_PER_KIND) if i not in done), None)
        redo = next((i for i in range(PUZZLES_PER_KIND) if i in done and done[i] < 3), None)
        opts, acts = [], []
        if nxt is not None:
            opts.append("PUZZLE #%d" % (nxt + 1))
            acts.append(nxt)
        else:
            opts.append("ENDLESS")
            acts.append(-1)
        if redo is not None:
            opts.append("3 STARS: #%d" % (redo + 1))
            acts.append(redo)
        opts.append("NOT NOW")
        acts.append(None)
        lines = [(None, "%s machine. %s" % (name, how)),
                 (None, "Solved %d/%d     Stars %d/%d" % (len(done), PUZZLES_PER_KIND, sum(done.values()),
                                                         3 * PUZZLES_PER_KIND))]
        self.say(lines, choices=opts,
                 cb=lambda s: self.fade_to(lambda: self.start_puzzle(kind, acts[s])) if acts[s] is not None else None)

    def start_puzzle(self, kind, n):
        if n < 0:
            level, seed = random.randint(16, PUZZLES_PER_KIND - 1), random.randrange(10 ** 9)
        else:
            level, seed = n, n * 7919 + (1 if kind == "pipe" else 2)
        pz = make_pipe(level, seed) if kind == "pipe" else make_lights(level, seed)
        done = self.pipes if kind == "pipe" else self.lights
        pz.update(kind=kind, n=n, moves=0, cx=0, cy=0, won=False, reward=0, stars=0, t0=self.now,
                  howto=n in (0, 1, 2) or not done)   # picture guide before the first few
        self.pz = pz
        self.mode = "puzzle"

    def puzzle_press(self, b, now):
        pz = self.pz
        if pz["won"]:
            if b == "click":
                self.fade_to(self.leave_puzzle)
            return
        if pz["howto"]:
            if b == "click":
                pz["howto"] = False
            elif b == "left":
                self.fade_to(self.leave_puzzle)
            return
        if b == "left":
            pz["cx"] = max(-1, pz["cx"] - 1)
        elif b == "right":
            pz["cx"] = min(pz["w"] - 1, pz["cx"] + 1)
        elif b == "up":
            pz["cy"] = (pz["cy"] - 1) % pz["h"]
        elif b == "down":
            pz["cy"] = (pz["cy"] + 1) % pz["h"]
        elif b == "click":
            if pz["cx"] < 0:
                self.fade_to(self.leave_puzzle)
                return
            x, y = pz["cx"], pz["cy"]
            if pz["kind"] == "pipe":
                pz["grid"][y][x] = rot_cw(pz["grid"][y][x])
            else:
                lights_press(pz["grid"], x, y)
            pz["moves"] += 1
            if puzzle_solved(pz):
                self.puzzle_win(now)

    def puzzle_win(self, now):
        pz = self.pz
        pz["won"], pz["t0"] = True, now
        AUDIO.play("power")
        pz["stars"] = stars = puzzle_stars(pz["moves"], pz["par"])
        done = self.pipes if pz["kind"] == "pipe" else self.lights
        n = pz["n"]
        bonus = 2 if "puzzle_specs" in self.upgrades else 0
        if n < 0:
            reward = 2 + bonus
            self.endless += 1
        elif n not in done:
            reward = 4 + n // 4 + bonus
        elif stars > done[n]:
            reward = 3 * (stars - done[n])
        else:
            reward = 0
        if n >= 0:
            done[n] = max(done.get(n, 0), stars)
        pz["reward"] = reward
        self.gain(reward)
        self.confetti = make_confetti()
        self.check_ach()
        self.save()

    def leave_puzzle(self):
        self.mode = "world"

    # ----- shop
    def open_shop(self, npc):
        self.mode = "shop"
        self.shop_cat, self.shop_csel, self.shop_ctop = None, 0, 0
        self.shop_msg, self.shop_msg_t = "Welcome! Pick a section of the store.", self.now

    def owned_item(self, it):
        return (it["type"] == "outfit" and it["id"] in self.owned) or (it["type"] == "tool" and it["id"] in self.upgrades)

    def shop_items(self, cat=None):
        cat = cat or self.shop_cat
        if cat == "OUTFITS":
            return [it for it in STORE_ITEMS if it["type"] == "outfit"]
        if cat == "TOOLS":
            return [it for it in STORE_ITEMS if it["type"] == "tool"]
        return [it for it in STORE_ITEMS if it.get("theme") == cat]

    def shop_press(self, b, now):
        if self.shop_cat is None:   # choosing a section
            n = len(SHOP_CATS)
            if b == "up":
                self.shop_csel = (self.shop_csel - 1) % n
            elif b == "down":
                self.shop_csel = (self.shop_csel + 1) % n
            elif b == "left":
                self.mode = "world"
                return
            elif b == "click":
                self.shop_cat = SHOP_CATS[self.shop_csel]
                self.shop_sel = self.shop_top = 0
                self.shop_msg, self.shop_msg_t = "%s! CENTER buys. LEFT goes back to the sections." % cat_label(self.shop_cat), now
                return
            self.shop_ctop = min(max(self.shop_ctop, self.shop_csel - 5), self.shop_csel)
            return
        items = self.shop_items()
        n = len(items)
        self.shop_sel = min(self.shop_sel, n - 1)
        if b == "up":
            self.shop_sel = (self.shop_sel - 1) % n
        elif b == "down":
            self.shop_sel = (self.shop_sel + 1) % n
        elif b == "left":
            self.shop_cat = None
            self.shop_msg, self.shop_msg_t = "Pick a section of the store.", now
            return
        elif b == "click":
            it = items[self.shop_sel]
            if it["type"] == "outfit" and it["id"] in self.owned:
                self.outfit_idx = it["id"]
                msg = "Looking sharp! Outfit equipped."
            elif it["type"] == "tool" and it["id"] in self.upgrades:
                msg = "You already own that one!"
            elif self.bolts >= it["cost"]:
                self.bolts -= it["cost"]
                if it["type"] == "outfit":
                    self.owned.add(it["id"])
                    self.outfit_idx = it["id"]
                    msg = "Thank you! It's yours."
                elif it["type"] == "furniture":
                    self.furn[it["id"]] = self.furn.get(it["id"], 0) + 1
                    msg = "Delivered! In your room, press CENTER on the floor and pick DECORATE."
                else:
                    self.upgrades.add(it["id"])
                    msg = "Thank you! It's yours."
                if it.get("theme") in HOLIDAY_THEMES:
                    self.events_bought += 1
                self.check_ach()
                self.save()
            else:
                msg = "You need %d more Bolts. Fix more circuits!" % (it["cost"] - self.bolts)
            self.shop_msg, self.shop_msg_t = msg, now
            return
        else:
            return
        self.shop_msg, self.shop_msg_t = items[self.shop_sel]["desc"], now
        self.shop_top = min(max(self.shop_top, self.shop_sel - 5), self.shop_sel)

    # ----- pop-up list (used by the workbench and decorating)
    def open_ovl(self, title, items):
        self.ovl = dict(title=title, items=items, sel=0, top=0)

    def ovl_press(self, b):
        o = self.ovl
        n = len(o["items"])
        if b == "up":
            o["sel"] = (o["sel"] - 1) % n
        elif b == "down":
            o["sel"] = (o["sel"] + 1) % n
        elif b == "left":
            self.ovl = None   # LEFT always backs out
        elif b == "click":
            fn = o["items"][o["sel"]][1]
            self.ovl = None
            if fn:
                fn()
        if self.ovl:
            o["top"] = min(max(o["top"], o["sel"] - 8), o["sel"])

    def draw_ovl(self, im):
        o = self.ovl
        d = ImageDraw.Draw(im)
        rows = o["items"][o["top"]:o["top"] + 9]
        x0, y0, x1 = 150, 20, 314
        y1 = y0 + 22 + len(rows) * 15
        draw_box(d, (x0, y0, x1, y1))
        d.text((x0 + 10, y0 + 6), o["title"], font=F_B, fill=NAVY)
        for i, (label, _fn) in enumerate(rows):
            y = y0 + 20 + i * 15
            if o["top"] + i == o["sel"]:
                d.rectangle([x0 + 6, y - 1, x1 - 6, y + 12], fill=(255, 236, 160))
                d.polygon([(x0 + 9, y + 2), (x0 + 9, y + 9), (x0 + 14, y + 5)], fill=NAVY)
            d.text((x0 + 18, y), label, font=F_M, fill=TXT)
        if o["top"] > 0:
            d.polygon([(x1 - 16, y0 + 8), (x1 - 10, y0 + 8), (x1 - 13, y0 + 4)], fill=NAVY)
        if o["top"] + 9 < len(o["items"]):
            d.polygon([(x1 - 16, y1 - 8), (x1 - 10, y1 - 8), (x1 - 13, y1 - 4)], fill=NAVY)

    # ----- workbench (free build) + job board
    def job_board(self):
        """The job board next to the workbench: a character tells a brand-new story and asks for a brand-new
        circuit, and she builds it on her real breadboard with Gio's step-by-step help (same as the story quests)."""
        if self.tut is not None:
            self.say([("silas", "The job board opens after the tour. Let's keep going!")])
            return
        if not JOBS_OPEN_EARLY and sum(1 for q in self.done if q < NQ) < NQ:   # unlocks once the story is finished
            self.say([("silas", "The job board's empty while the building is still in lockdown."),
                      ("gio", "Let's get the power back on first. After that, everyone's going to want our help!")])
            return
        if self.quest_seed is None:
            self.install_job(random.SystemRandom().randrange(1 << 30))   # the game reseeds `random` for effects
        L = LEVELS[JOB_SLOT]

        def pick(s):
            if s == 0:
                self.save()
                self.fade_to(lambda: self.enter_build(JOB_SLOT))
            elif s == 1:
                self.install_job(random.SystemRandom().randrange(1 << 30))
                self.job_board()
        self.say([(L["npc"], L["story"]), (L["npc"], L["hint"]),
                  (None, "Reward: %d Bolts. Parts: %s. (Jobs done so far: %d)"
                   % (L["reward"], ", ".join("%d %s" % p for p in L["parts"]), self.quests_done))],
                 choices=["BUILD IT", "OTHER JOB", "NOT NOW"], cb=pick)

    def new_job(self):
        seed = random.randrange(10 ** 9)
        giver, text, _check, reward = make_job(seed)

        def accept(s):
            if s == 0:
                self.job_seed = seed
                self.save()
                self.say([(None, "Job accepted! Head to the WORKBENCH next to the board.")])
        self.say([(giver, "Hey Jaslyne! Can you build something for me? %s" % text),
                  (None, "Reward: %d Bolts. (Jobs done so far: %d)" % (reward, self.jobs_done))],
                 choices=["ACCEPT", "NOT NOW"], cb=accept)

    def open_bench(self):
        self.bench = dict(cx=0, cy=0, power=False, banner=None, rows=None)
        self.mode = "bench"
        self.bench_changed()

    def bench_changed(self):
        bn = self.bench
        bn["rows"] = sb_eval(self.sb) if bn["power"] else None
        if not bn["power"]:
            return
        if any(r[0] == "on" for r in bn["rows"]):
            self.built_ok = True
        if self.job_seed is not None:
            giver, text, check, reward = make_job(self.job_seed)
            if check(bn["rows"]):
                self.job_seed = None
                self.jobs_done += 1
                self.gain(reward)
                bn["banner"] = (giver, "JOB COMPLETE! +%d Bolts" % reward, text)
        self.check_ach()
        self.save()

    def bench_press(self, b, now):
        bn = self.bench
        if self.ovl:
            self.ovl_press(b)
            return
        if bn["banner"]:
            if b == "click":
                bn["banner"] = None
            return
        if b == "left":
            bn["cx"] = max(-1, bn["cx"] - 1)
        elif b == "right":
            bn["cx"] = min(SB_COLS - 1, bn["cx"] + 1)
        elif b == "up":
            bn["cy"] = (bn["cy"] - 1) % SB_ROWS
        elif b == "down":
            bn["cy"] = (bn["cy"] + 1) % SB_ROWS
        elif b == "click":
            if bn["cx"] < 0:
                if bn["cy"] == 0:
                    bn["power"] = not bn["power"]
                    self.bench_changed()
                elif bn["cy"] == 1:
                    self.open_ovl("Clear the whole board?", [("YES, CLEAR IT", self.bench_clear), ("CANCEL", None)])
                else:
                    self.save()
                    self.mode = "world"
                return
            x, y = bn["cx"], bn["cy"]
            cell = self.sb[y][x]
            if cell is None:
                self.open_ovl("Pick a part", [(name, (lambda p=pid: self.bench_place(p))) for pid, name, _k in SB_PARTS]
                              + [("CANCEL", None)])
            else:
                pid = cell["p"]
                items = []
                if sb_polar(pid):
                    items.append(("FLIP (turn around)", self.bench_flip))
                if sb_kind(pid) == "toggle":
                    items.append(("TURN OFF" if cell["on"] else "TURN ON", self.bench_toggle))
                items += [("SWAP FOR ANOTHER", lambda: self.open_ovl("Pick a part", [
                    (name, (lambda p=p2: self.bench_place(p))) for p2, name, _k in SB_PARTS] + [("CANCEL", None)])),
                          ("REMOVE", self.bench_remove), ("CANCEL", None)]
                self.open_ovl(SB_BY_ID[pid][1], items)

    def bench_cell(self):
        return self.sb[self.bench["cy"]][self.bench["cx"]]

    def bench_place(self, pid):
        self.sb[self.bench["cy"]][self.bench["cx"]] = dict(p=pid, flip=False, on=False)
        self.bench_changed()

    def bench_flip(self):
        self.bench_cell()["flip"] = not self.bench_cell()["flip"]
        self.bench_changed()

    def bench_toggle(self):
        self.bench_cell()["on"] = not self.bench_cell()["on"]
        self.bench_changed()

    def bench_remove(self):
        self.sb[self.bench["cy"]][self.bench["cx"]] = None
        self.bench_changed()

    def bench_clear(self):
        self.sb = [[None] * SB_COLS for _ in range(SB_ROWS)]
        self.bench_changed()

    # ----- her room: decorating
    def menu_items(self):
        base = ["QUESTS", "TROPHIES", "BAG", "OUTFIT", "SOUND", "SAVE", "CLOSE"]
        return ["DECORATE"] + base if self.can_decorate() else base

    # ----- design mode (decorating)
    def start_decor(self):
        dx, dy = DIRS[self.facing]
        self.dec = dict(x=min(18, max(1, self.tx + dx)), y=min(13, max(2, self.ty + dy)), onbar=False, bar=1,
                        tool="place" if self.design_item else "move", carry=None, undo=[], msg="", msg_t=0.0,
                        cat=None, rep=None, painting=False, last=None, help="design_help" not in self.story)
        self.mode = "decor"

    def design_msg(self, text):
        self.dec["msg"], self.dec["msg_t"] = text, self.now
        if not text.endswith("picked! CENTER places it. Hold CENTER while moving to place lots.") and text != "Undone!":
            AUDIO.play("error")

    def decor_press(self, b, now):
        dc = self.dec
        if dc["help"]:
            if b in ("click", "left"):
                dc["help"] = False
                self.story.add("design_help")
                self.save()
            return
        if dc["cat"]:
            self.catalog_press(b)
            return
        if b in DIRS:
            self.decor_move(b)
            dc["rep"] = (b, now + 0.28)   # keep holding to glide
        elif b == "click":
            if dc["onbar"]:
                self.toolbar_click()
            else:
                dc["painting"] = dc["tool"] == "place"
                dc["last"] = (dc["x"], dc["y"])
                self.decor_apply(dc["x"], dc["y"])

    def decor_move(self, b):
        dc = self.dec
        if dc["onbar"]:
            if b == "left":
                dc["bar"] = max(0, dc["bar"] - 1)
            elif b == "right":
                dc["bar"] = min(len(DESIGN_TOOLS) - 1, dc["bar"] + 1)
            elif b == "up":
                dc["onbar"] = False
            return
        dx, dy = DIRS[b]
        if dc["y"] + dy > 13:   # past the bottom of the room = the toolbar
            dc["onbar"] = True
            dc["bar"] = DESIGN_TOOLS.index(dc["tool"].upper())
            return
        dc["x"] = min(18, max(1, dc["x"] + dx))
        dc["y"] = min(13, max(2, dc["y"] + dy))

    def toolbar_click(self):
        dc = self.dec
        tool = DESIGN_TOOLS[dc["bar"]]
        if tool == "ITEMS" or (tool == "PLACE" and not self.design_item):
            self.open_catalog()
        elif tool in ("PLACE", "MOVE", "ERASE"):
            dc["tool"], dc["onbar"] = tool.lower(), False
        elif tool == "UNDO":
            self.decor_undo()
        else:
            self.end_decor()

    def decor_apply(self, x, y):
        dc = self.dec
        tool = dc["tool"]
        if tool == "place":
            if not self.design_item:
                self.open_catalog()
            else:
                self.design_place(x, y, self.design_item)
        elif tool == "move":
            if dc["carry"]:
                fid, ox, oy = dc["carry"]
                why = self.placeable(x, y, fid)
                if why:
                    self.design_msg(why)
                    return
                self.decor.append([self.room, x, y, fid])
                dc["carry"] = None
                self.push_undo(("move", self.room, ox, oy, x, y, fid))
                self.save()
            else:
                top = self.furniture_at(x, y)
                if not top:
                    self.design_msg("Nothing to move here. Point at a piece of furniture.")
                    return
                self.take_item(x, y, top)
                dc["carry"] = (top, x, y)
        elif tool == "erase":
            top = self.furniture_at(x, y)
            if top:
                self.take_item(x, y, top)
                AUDIO.play("erase")
                self.furn[top] = self.furn.get(top, 0) + 1
                self.push_undo(("erase", self.room, x, y, top))
                self.save()
            elif self.removable_here(x, y):
                self.decor_remove(x, y)
                self.push_undo(("remove", self.room, x, y))
            else:
                self.design_msg("Nothing to erase here." if self.tile(x, y) in ".r" else "That part of the room can't be removed.")

    def take_item(self, x, y, fid):
        for i in range(len(self.decor) - 1, -1, -1):
            r, dx, dy, f = self.decor[i]
            if r == self.room and (dx, dy) == (x, y) and f == fid:
                del self.decor[i]
                return

    def design_place(self, x, y, fid, quiet=False):
        why = self.placeable(x, y, fid)
        if why:
            if not quiet:
                self.design_msg(why)
            return False
        bought = False
        if self.furn.get(fid, 0) > 0:
            self.furn[fid] -= 1
        elif self.bolts >= FURNITURE[fid][1]:
            self.bolts -= FURNITURE[fid][1]   # bought on the spot - no trip to the store needed
            bought = True
            if FURNITURE[fid][3] in HOLIDAY_THEMES:
                self.events_bought += 1
        else:
            if not quiet:
                self.design_msg("Not enough Bolts for that one (%d needed)." % FURNITURE[fid][1])
            return False
        self.decor.append([self.room, x, y, fid])
        AUDIO.play("place")
        self.decor_placed += 1
        self.push_undo(("place", self.room, x, y, fid, bought))
        self.recent = [fid] + [f for f in self.recent if f != fid][:11]
        self.check_ach()
        self.save()
        return True

    def push_undo(self, action):
        self.dec["undo"] = (self.dec["undo"] + [action])[-40:]

    def decor_undo(self):
        dc = self.dec
        if not dc["undo"]:
            self.design_msg("Nothing to undo.")
            return
        act = dc["undo"].pop()
        kind, room = act[0], act[1]
        if kind == "place":
            _k, _r, x, y, fid, bought = act
            self.take_item(x, y, fid)
            if bought:
                self.bolts += FURNITURE[fid][1]
            else:
                self.furn[fid] = self.furn.get(fid, 0) + 1
        elif kind == "erase":
            _k, _r, x, y, fid = act
            self.decor.append([room, x, y, fid])
            self.furn[fid] = max(0, self.furn.get(fid, 0) - 1)
        elif kind == "remove":
            self.removed_set.discard((room, act[2], act[3]))
            self.removed = sorted(list(e) for e in self.removed_set)
        elif kind == "move":
            _k, _r, ox, oy, x, y, fid = act
            self.take_item(x, y, fid)
            self.decor.append([room, ox, oy, fid])
        self.design_msg("Undone!")
        self.save()

    def decor_remove(self, x, y):
        self.removed_set.add((self.room, x, y))
        self.removed = sorted(list(e) for e in self.removed_set)
        self.save()

    def decor_restore(self):
        self.removed_set = {e for e in self.removed_set if e[0] != self.room}
        self.removed = sorted(list(e) for e in self.removed_set)
        self.save()

    def end_decor(self):
        dc = self.dec
        if dc and dc["carry"]:   # put back anything still being carried
            fid, ox, oy = dc["carry"]
            self.decor.append([self.room, ox, oy, fid])
        self.mode = "world"
        self.save()

    def design_tick(self, now):
        """Hold an arrow to glide; hold CENTER while moving to paint (floors, walls...)."""
        dc = self.dec
        if dc["cat"] or dc["help"]:
            return
        if dc["rep"]:
            b, t_next = dc["rep"]
            if not held(b):
                dc["rep"] = None
            elif now >= t_next:
                self.decor_move(b)
                dc["rep"] = (b, now + 0.07)
        if dc["painting"]:
            if not held("click"):
                dc["painting"] = False
            elif not dc["onbar"] and (dc["x"], dc["y"]) != dc["last"]:
                dc["last"] = (dc["x"], dc["y"])
                self.design_place(dc["x"], dc["y"], self.design_item, quiet=True)

    # ----- design mode: the catalog
    def catalog_sections(self):
        return ["Recent", "My Stuff"] + FURN_THEMES

    def catalog_items(self, sec):
        name = self.catalog_sections()[sec]
        if name == "Recent":
            return [f for f in self.recent if f in FURNITURE]
        if name == "My Stuff":
            return sorted((f for f, c in self.furn.items() if c > 0), key=lambda f: FURNITURE[f][0])
        return [f for f, v in FURNITURE.items() if v[3] == name]

    def open_catalog(self):
        secs = self.catalog_sections()
        sec = secs.index(FURNITURE[self.design_item][3]) if self.design_item else (0 if self.recent else 2)
        items = self.catalog_items(sec)
        sel = items.index(self.design_item) if self.design_item in items else 0
        self.dec["cat"] = dict(sec=sec, top=max(0, sec - 4), focus="grid" if items else "sec", sel=sel, row0=0)
        self.dec["onbar"] = False

    def catalog_press(self, b):
        c = self.dec["cat"]
        secs = self.catalog_sections()
        items = self.catalog_items(c["sec"])
        if c["focus"] == "sec":
            if b in ("up", "down"):
                c["sec"] = (c["sec"] + (1 if b == "down" else -1)) % len(secs)
                c["sel"] = c["row0"] = 0
                c["top"] = min(max(c["top"], c["sec"] - 8), c["sec"])
            elif b in ("right", "click"):
                if items:
                    c["focus"] = "grid"
                else:
                    self.design_msg("Nothing here yet!")
            elif b == "left":
                self.dec["cat"] = None
            return
        n = len(items)
        if b == "left":
            if c["sel"] % CAT_COLS == 0:
                c["focus"] = "sec"
            else:
                c["sel"] -= 1
        elif b == "right":
            c["sel"] = min(n - 1, c["sel"] + 1)
        elif b == "up":
            if c["sel"] >= CAT_COLS:
                c["sel"] -= CAT_COLS
        elif b == "down":
            c["sel"] = min(n - 1, c["sel"] + CAT_COLS)
        elif b == "click":
            fid = items[c["sel"]]
            self.design_item = fid
            self.dec.update(tool="place", cat=None, onbar=False)
            self.design_msg("%s picked! CENTER places it. Hold CENTER while moving to place lots." % FURNITURE[fid][0])
            return
        row = c["sel"] // CAT_COLS
        c["row0"] = min(max(c["row0"], row - CAT_ROWS + 1), row)


    # ----- daily gift, weekly challenge, holiday events
    def daily_check(self):
        today = datetime.date.today()
        wk = "%d-W%02d" % today.isocalendar()[:2]
        lines = []
        if self.week_id != wk:
            self.week_id = wk
            self.week_goal = random.Random(wk).randrange(len(WEEKLY_GOALS))
            self.week_base = WEEKLY_GOALS[self.week_goal][1](self)
            self.week_done = False
            lines.append(("max", "NEW WEEKLY CHALLENGE: %s. REWARD: %d BOLTS." % (WEEKLY_GOALS[self.week_goal][0].upper(),
                                                                                 WEEKLY_REWARD)))
        if self.last_day != today.isoformat():
            yesterday = (today - datetime.timedelta(days=1)).isoformat()
            self.streak = self.streak + 1 if self.last_day == yesterday else 1
            self.last_day = today.isoformat()
            gift = 5 + 2 * min(self.streak, 7)
            self.gain(gift)
            lines.insert(0, ("max", "DAILY POWER BONUS: +%d BOLTS. COME BACK TOMORROW FOR MORE. DAY STREAK: %d." % (gift, self.streak)))
        if lines:
            self.check_ach()
            self.save()
            self.say(lines)

    def weekly_check(self):
        if self.week_done or not self.week_id:
            return
        text, stat, amount = WEEKLY_GOALS[self.week_goal]
        if stat(self) - self.week_base >= amount:
            self.week_done = True
            self.weeks_done += 1
            self.gain(WEEKLY_REWARD)
            self.check_ach()
            self.save()
            self.say([("max", "WEEKLY CHALLENGE COMPLETE: %s! +%d BOLTS." % (text.upper(), WEEKLY_REWARD))])

    # ----- pause menu
    def menu_press(self, b):
        mn = self.menu
        page = mn["page"]
        if page == "main":
            items = self.menu_items()
            if b == "up":
                mn["sel"] = (mn["sel"] - 1) % len(items)
            elif b == "down":
                mn["sel"] = (mn["sel"] + 1) % len(items)
            elif b == "left":
                self.menu = None
            elif b == "click":
                it = items[mn["sel"]]
                if it == "CLOSE":
                    self.menu = None
                elif it == "DECORATE":
                    self.menu = None
                    self.start_decor()
                elif it == "SAVE":
                    self.save()
                    mn["msg"] = "Game saved!"
                else:
                    self.menu = dict(page=it.lower(), sel=0, scroll=0, msg="", back=mn["sel"])
        elif page == "sound":   # UP/DOWN pick a slider, LEFT/RIGHT turn it down/up, CENTER = back
            rows = len(SOUND_SLIDERS) + 1
            if b == "up":
                mn["sel"] = (mn["sel"] - 1) % rows
            elif b == "down":
                mn["sel"] = (mn["sel"] + 1) % rows
            elif b == "click" or (b == "left" and mn["sel"] == rows - 1):
                self.save()
                self.menu = dict(page="main", sel=mn.get("back", 0), scroll=0, msg="")
            elif b in ("left", "right"):
                key = SOUND_SLIDERS[mn["sel"]][1]
                setattr(self, key, max(0, min(10, getattr(self, key) + (1 if b == "right" else -1))))
                AUDIO.set_gains(self.vol_all / 10, self.vol_music / 10, self.vol_fx / 10, self.vol_voice / 10)
                if key == "vol_voice":
                    AUDIO.talk_text = None
                    AUDIO.talk("gio", "la la la", 3)   # hear the new voice level
                else:
                    AUDIO.play("coin")   # hear the new level
        else:
            n = {"quests": NQ + NS, "trophies": len(ACHIEVEMENTS), "outfit": len(self.owned_outfits())}.get(page, 1)
            if b == "left":
                self.menu = dict(page="main", sel=mn.get("back", 0), scroll=0, msg="")
            elif b == "up":
                mn["sel"] = (mn["sel"] - 1) % n
            elif b == "down":
                mn["sel"] = (mn["sel"] + 1) % n
            elif b == "click" and page == "quests" and mn["sel"] >= NQ:
                q = mn["sel"]
                self.menu = None
                if q == JOB_SLOT and self.quest_seed is None:
                    self.install_job(random.SystemRandom().randrange(1 << 30))   # the game reseeds `random` for effects
                self.quest_prompt(q)
                return
            elif b == "click" and page == "outfit":
                self.outfit_idx = self.owned_outfits()[mn["sel"]]
                self.save()
            mn["scroll"] = min(max(mn["scroll"], mn["sel"] - 6), mn["sel"])

    def owned_outfits(self):
        return sorted(self.owned)

    # ----- update
    def update(self, now, dt):
        self.now = now
        if self.fade:
            f = self.fade
            f["t"] += dt / 0.2
            if f["t"] >= 1:
                if f["phase"] == "out":
                    f["cb"]()
                    f["phase"], f["t"] = "in", 0.0
                else:
                    self.fade = None
        if self.mode != "title":
            self.play += dt
            if int(self.play) % 300 == 0 and int(self.play - dt) % 300 != 0:
                self.check_ach()   # play-time trophy
        if self.toasts:
            if self.toast_t0 is None:
                self.toast_t0 = now
            elif now - self.toast_t0 > 2.8:
                self.toasts.pop(0)
                self.toast_t0 = None
        if self.mode == "world" and not self.dialog and not self.fade and self.tut is not None:
            self.tour_check()
        if self.mode == "world" and self.tut is not None:   # Gio walks in her footsteps, about a tile behind
            last = self.trail[-1] if self.trail else None
            if not last or (last[0], last[1]) != (self.px, self.py):
                self.trail.append((self.px, self.py, self.facing, self.walking))
                if len(self.trail) > 10:
                    self.trail.pop(0)
        if self.mode == "world" and not self.dialog and not self.menu and not self.fade:
            if not self.daily_checked and self.tut is None:
                self.daily_checked = True
                self.daily_check()
            elif now - self.weekly_t > 2.0:
                self.weekly_t = now
                self.weekly_check()
        if self.mode == "decor" and self.dec and not self.fade:
            self.design_tick(now)
        AUDIO.set_gains(self.vol_all / 10, self.vol_music / 10, self.vol_fx / 10, self.vol_voice / 10)
        AUDIO.set_track(self.music_track())
        if self.mode == "focus" and not self.focus["paused"] and not self.fade:
            self.focus["left"] = self.focus["end"] - now
            if self.focus["left"] <= 0:
                self.finish_focus(True)
        if self.mode == "world":
            for n in self.npcs:
                n.update(self, now, dt)
            if not self.dialog and not self.menu and not self.fade:
                self.move_player(now, dt)
            else:
                self.walking, self.walk_since = False, None

    def next_dir(self):
        q, self.queued = self.queued, None
        if q and held(q):
            return q
        return next((b for b in ("up", "down", "left", "right") if held(b)), None) or q

    def move_player(self, now, dt):
        sp = self.speed()
        if self.walk_since is not None and now - self.walk_since > 0.45:
            sp *= 1.5   # keep holding a direction and she breaks into a jog
        budget = sp * dt
        # leftover movement rolls straight into the next tile, so walking never stutters between tiles
        for _ in range(4):
            gx, gy = self.tx * TS, self.ty * TS
            if self.px != gx or self.py != gy:
                dist = abs(gx - self.px) + abs(gy - self.py)
                step = min(budget, dist)
                self.px, self.py = slide(self.px, gx, step), slide(self.py, gy, step)
                budget -= step
                self.walking = True
                if self.px != gx or self.py != gy:
                    return
                if self.arrive(now):
                    return
                continue
            want = self.next_dir()
            if not want:
                self.walking, self.walk_since = False, None
                return
            self.facing = want
            dx, dy = DIRS[want]
            nx, ny = self.tx + dx, self.ty + dy
            if not self.free(nx, ny):
                self.walking, self.walk_since = False, None
                if self.tile(nx, ny) == "R" and now - self.bump_t > 1.5:
                    self.bump_t = now
                    left = PER_ZONE - zone_done(self.done, self.zone)
                    self.say([(None, "The door is locked. Fix %d more circuit%s in this room to power it up."
                               % (left, "" if left == 1 else "s"))])
                return
            self.tx, self.ty = nx, ny
            self.steps += 1
            if self.steps % 50 == 0:
                self.check_ach()
            if self.walk_since is None:
                self.walk_since = now

    def arrive(self, now):
        dd = ROOMS[self.room]["doors"].get((self.tx, self.ty))
        if dd and self.door_unlocked(self.tx, self.ty):
            self.walking, self.walk_since = False, None
            self.go(dd["to"], dd.get("x", 0), dd.get("y", 0), dd.get("face", "down"))
            return True
        return False

    # ----- rendering
    def render(self, now):
        self.now = now
        if self.mode == "title":
            im = self.render_title(now)
        elif self.mode == "world":
            im = self.render_world(now)
        elif self.mode == "shop":
            im = self.render_shop(now)
        elif self.mode == "build":
            im = self.render_build(now)
        elif self.mode == "focus":
            im = self.render_focus(now)
        elif self.mode == "library":
            im = self.render_library(now)
        elif self.mode == "book":
            im = self.render_book(now)
        elif self.mode == "story":
            im = self.render_story(now)
        elif self.mode == "bench":
            im = self.render_bench(now)
        elif self.mode == "decor":
            im = self.render_decor(now)
        elif self.mode == "blank":
            im = Image.new("RGB", (W, H), (0, 0, 0))
        elif self.mode == "puzzle":
            im = self.render_puzzle(now)
        else:
            im = self.render_ending(now)
        if self.toasts and self.toast_t0 is not None and self.mode != "title":
            self.draw_toast(im, now)
        if self.fade:
            a = self.fade["t"] if self.fade["phase"] == "out" else 1 - self.fade["t"]
            im = Image.blend(im, Image.new("RGB", (W, H), (0, 0, 0)), max(0.0, min(1.0, a)))
        return im

    def draw_toast(self, im, now):
        t = now - self.toast_t0
        slide_in = min(1.0, t * 5) if t < 2.4 else max(0.0, 1 - (t - 2.4) * 3)
        y = int(-30 + slide_in * 48)
        d = ImageDraw.Draw(im)
        draw_box(d, (58, y, 262, y + 28), fill=(40, 30, 10), border=YELLOW)
        draw_trophy(d, 76, y + 15, YELLOW)
        d.text((92, y + 4), "TROPHY UNLOCKED!  +%d" % ACH_BONUS, font=F_S, fill=(255, 220, 120))
        d.text((92, y + 14), self.toasts[0], font=F_B, fill=WHITE)
        if int(now * 8) % 2 == 0:
            draw_star(d, 248, y + 14, 4, YELLOW)

    def render_focus(self, now):
        f = self.focus
        im = Image.new("RGB", (W, H), (16, 18, 40))
        d = ImageDraw.Draw(im)
        # night window
        d.rectangle([14, 20, 112, 96], fill=(18, 26, 64), outline=(110, 80, 50), width=4)
        r = random.Random(11)
        for _ in range(18):
            sx, sy = r.randint(20, 106), r.randint(26, 90)
            if (int(now * 2) + sx) % 7:
                d.point((sx, sy), fill=(220, 225, 255))
        d.ellipse([78, 30, 98, 50], fill=(250, 240, 200))
        d.ellipse([84, 27, 102, 45], fill=(18, 26, 64))
        d.line([(63, 20), (63, 96)], fill=(110, 80, 50), width=3)
        d.line([(14, 58), (112, 58)], fill=(110, 80, 50), width=3)
        # warm lamp glow over the desk
        for rr, col in ((70, (40, 34, 52)), (52, (62, 50, 56)), (34, (90, 70, 56))):
            d.ellipse([92 - rr, 132 - rr * 0.6, 92 + rr, 132 + rr * 0.6], fill=col)
        d.rectangle([20, 140, 170, 148], fill=(130, 86, 52), outline=(70, 44, 24))
        d.rectangle([26, 148, 32, 162], fill=(100, 66, 40))
        d.rectangle([158, 148, 164, 162], fill=(100, 66, 40))
        d.line([(130, 140), (130, 112), (118, 102)], fill=(70, 70, 80), width=2)
        d.polygon([(106, 100), (126, 100), (130, 110), (102, 110)], fill=(250, 210, 90), outline=(90, 70, 20))
        d.polygon([(44, 138), (60, 134), (76, 138), (76, 140), (44, 140)], fill=CREAM, outline=(90, 80, 70))
        d.line([(60, 134), (60, 140)], fill=(90, 80, 70))
        bob = int(math.sin(now * 1.5) * 1)
        jas = char_frames(player_pal(self.outfit_idx))["right"][0].resize((48, 48), Image.NEAREST)
        im.paste(jas, (8, 96 + bob), jas)
        # timer panel
        left = max(0.0, f["left"])
        mm, ss = divmod(int(left + 0.999), 60)
        draw_box(d, (128, 16, 312, 96), fill=(28, 30, 60), border=YELLOW)
        center_text(d, 22, "FOCUS LAMP  -  %d MIN" % f["minutes"], F_B, (255, 220, 120), cx=220)
        center_text(d, 38, "%02d:%02d" % (mm, ss), F_L, WHITE, cx=220, shadow=(0, 0, 0))
        frac = 1 - left / (f["minutes"] * 60)
        d.rectangle([142, 70, 298, 78], fill=(10, 12, 30), outline=CYAN_D)
        d.rectangle([143, 71, 143 + int(154 * frac), 77], fill=GREEN)
        d.text((142, 82), "Reward: %d Bolts" % self.focus_reward(f["minutes"], True), font=F_S, fill=YELLOW)
        d.text((232, 82), "Total %dm" % self.focus_min, font=F_S, fill=CYAN)
        if f["paused"] and int(now * 2) % 2 == 0:
            center_text(d, 110, "PAUSED", F_T, (255, 170, 200), cx=236, shadow=(0, 0, 0))
        if now - f["quit_t"] < 2.0:
            draw_box(d, (176, 128, 312, 156), fill=(60, 20, 30), border=RED)
            center_text(d, 137, "Press LEFT again to stop", F_S, WHITE, cx=244)
        elapsed = f["minutes"] * 60 - left
        draw_dialog(im, "gio", FOCUS_LINES[int(elapsed // 45) % len(FOCUS_LINES)], 999, now,
                    hint="CENTER: pause / resume      LEFT x2: stop")
        return im

    def render_puzzle(self, now):
        pz = self.pz
        im = Image.new("RGB", (W, H), (14, 12, 30))
        d = ImageDraw.Draw(im)
        for gx in range(0, W, 16):
            d.line([(gx, 16), (gx, H)], fill=(20, 18, 40))
        for gy in range(16, H, 16):
            d.line([(0, gy), (W, gy)], fill=(20, 18, 40))
        d.rectangle([0, 0, W, 15], fill=(60, 30, 100))
        title = ("PIPE PUZZLE" if pz["kind"] == "pipe" else "LIGHT GRID") + \
                (" - ENDLESS" if pz["n"] < 0 else " #%d" % (pz["n"] + 1))
        d.text((6, 3), title, font=F_B, fill=(80, 255, 220))
        d.text((196, 3), "MOVES %d   PAR %d" % (pz["moves"], pz["par"]), font=F_S, fill=WHITE)
        w, h = pz["w"], pz["h"]
        cell = min(34, 240 // w, 196 // h)
        x0, y0 = 60 + (240 - w * cell) // 2, 22 + (196 - h * cell) // 2
        # exit button
        sel_exit = pz["cx"] < 0
        draw_box(d, (4, 22, 40, 40), fill=(90, 30, 40) if sel_exit else (40, 30, 50), border=YELLOW if sel_exit else (90, 80, 110), rad=3)
        d.text((10, 27), "EXIT", font=F_B, fill=WHITE)
        if pz["kind"] == "pipe":
            flow = pipe_flow(pz)
            lw = max(3, cell // 5)
            for y in range(h):
                for x in range(w):
                    cx0, cy0 = x0 + x * cell, y0 + y * cell
                    d.rectangle([cx0, cy0, cx0 + cell - 1, cy0 + cell - 1], fill=(26, 30, 48), outline=(44, 50, 76))
                    m = pz["grid"][y][x]
                    on = (x, y) in flow
                    col = YELLOW if on else (130, 140, 165)
                    mx, my = cx0 + cell // 2, cy0 + cell // 2
                    for dd, (dx, dy) in PIPE_DIRS.items():
                        if m & dd:
                            d.line([(mx, my), (mx + dx * cell // 2, my + dy * cell // 2)], fill=col, width=lw)
                    rr = lw // 2 + 1
                    d.ellipse([mx - rr, my - rr, mx + rr, my + rr], fill=col)
            by = y0 + pz["sy"] * cell + cell // 2
            d.rectangle([x0 - 14, by - 6, x0 - 2, by + 6], fill=(60, 200, 90), outline=(0, 0, 0))
            d.rectangle([x0 - 11, by - 8, x0 - 5, by - 6], fill=(200, 200, 210))
            d.text((x0 - 12, by - 5), "+", font=F_S, fill=(0, 0, 0))
            ty = y0 + pz["ty"] * cell + cell // 2
            lit = pz["won"]
            if lit:
                for rr in (14, 10):
                    d.ellipse([x0 + w * cell + 8 - rr + 2, ty - rr, x0 + w * cell + 8 + rr + 2, ty + rr], outline=YELLOW)
            d.ellipse([x0 + w * cell + 3, ty - 6, x0 + w * cell + 15, ty + 6], fill=YELLOW if lit else (70, 70, 80), outline=(0, 0, 0))
        else:
            for y in range(h):
                for x in range(w):
                    cx0, cy0 = x0 + x * cell, y0 + y * cell
                    d.rectangle([cx0, cy0, cx0 + cell - 1, cy0 + cell - 1], fill=(26, 30, 48), outline=(44, 50, 76))
                    on = pz["grid"][y][x]
                    p = max(3, cell // 6)
                    if on:
                        d.ellipse([cx0 + p - 2, cy0 + p - 2, cx0 + cell - p + 1, cy0 + cell - p + 1], fill=(120, 100, 30))
                    d.ellipse([cx0 + p, cy0 + p, cx0 + cell - p - 1, cy0 + cell - p - 1],
                              fill=(255, 220, 80) if on else (52, 52, 64), outline=(0, 0, 0))
                    if on:
                        d.ellipse([cx0 + p + 3, cy0 + p + 3, cx0 + p + 7, cy0 + p + 7], fill=WHITE)
        if not sel_exit and not pz["won"]:
            if pz["kind"] == "lights":   # show exactly which bulbs CENTER will flip
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = pz["cx"] + dx, pz["cy"] + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        d.rectangle([x0 + nx * cell + 1, y0 + ny * cell + 1, x0 + nx * cell + cell - 2,
                                     y0 + ny * cell + cell - 2], outline=(255, 140, 200))
            col = YELLOW if int(now * 4) % 2 == 0 else WHITE
            cx0, cy0 = x0 + pz["cx"] * cell, y0 + pz["cy"] * cell
            d.rectangle([cx0 - 1, cy0 - 1, cx0 + cell, cy0 + cell], outline=col, width=2)
        d.rectangle([0, 220, W, H], fill=(40, 24, 70))
        goal = ("GOAL: light up the bulb!  CENTER = spin pipe" if pz["kind"] == "pipe"
                else "GOAL: turn ALL bulbs on!  Pink ones flip too")
        d.text((6, 224), goal, font=F_B, fill=YELLOW)
        if pz["howto"]:
            self.draw_howto(im, d, pz["kind"], now)
        if pz["won"]:
            t = now - pz["t0"]
            draw_confetti(d, self.confetti, t)
            draw_box(d, (70, 80, 250, 160), fill=(30, 24, 60), border=YELLOW)
            center_text(d, 88, "SOLVED!", F_T, YELLOW, shadow=(0, 0, 0))
            for i in range(3):
                draw_star(d, 136 + i * 24, 116, 9, YELLOW if i < pz["stars"] else (60, 60, 80))
            center_text(d, 132, ("+%d Bolts" % pz["reward"]) if pz["reward"] else "No new reward (already beaten)",
                        F_B, WHITE)
            center_text(d, 146, "CENTER: continue", F_S, CYAN)
        return im

    def render_story(self, now):
        sr = self.story_run
        key, text = sr["slides"][sr["i"]]
        im = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(im)
        self.draw_scene(im, d, key, now)
        shown = int((now - sr["t0"]) * 40)
        draw_dialog(im, None, text, shown, now, hint="CENTER: next      LEFT: skip story")
        d.text((W - 34, 4), "%d/%d" % (sr["i"] + 1, len(sr["slides"])), font=F_S, fill=(200, 200, 220))
        return im

    def draw_scene(self, im, d, key, now):
        """Simple pixel-art scenes for the cutscenes."""
        lit = key == "facility_lit"
        sky_top, sky_bot = ((60, 100, 180), (255, 170, 90)) if lit else ((6, 8, 24), (30, 22, 56))
        for y in range(0, 164, 4):
            d.rectangle([0, y, W, y + 3], fill=lerp_col(sky_top, sky_bot, y / 164))
        if key in ("facility", "storm", "facility_lit", "lockdown_off"):
            if key == "facility":
                d.ellipse([250, 18, 274, 42], fill=(240, 235, 200))
                r = random.Random(4)
                for _ in range(30):
                    d.point((r.randint(0, W), r.randint(0, 90)), fill=(210, 215, 255))
            if lit:
                d.ellipse([W // 2 - 24, 120, W // 2 + 24, 168], fill=(255, 220, 120))
            # the building
            d.rectangle([70, 60, 250, 164], fill=(34, 36, 60), outline=(14, 14, 26))
            d.rectangle([140, 36, 180, 60], fill=(40, 42, 70), outline=(14, 14, 26))
            d.line([(160, 36), (160, 18)], fill=(120, 120, 140), width=2)
            on_windows = key in ("facility", "facility_lit", "lockdown_off")
            r = random.Random(8)
            for wy in range(70, 150, 16):
                for wx in range(80, 240, 18):
                    on = on_windows and (r.random() < 0.8 or lit)
                    d.rectangle([wx, wy, wx + 9, wy + 8], fill=(250, 220, 90) if on else (22, 24, 44))
            d.rectangle([120, 44 + 100, 200, 158], fill=(20, 20, 34))
            draw_box(d, (110, 64, 210, 80), fill=(20, 60, 80), border=CYAN, rad=3)
            center_text(d, 67, "VOLTA LABS", F_B, CYAN)
            if key == "storm":
                for i in range(60):
                    rx = (i * 37 + int(now * 300)) % W
                    ry = (i * 53 + int(now * 500)) % 164
                    d.line([(rx, ry), (rx - 3, ry + 8)], fill=(110, 130, 180))
                if int(now * 3) % 3 == 0:
                    pts = [(150, 0), (130, 30), (150, 30), (125, 62), (165, 22), (145, 22), (165, 0)]
                    d.polygon(pts, fill=(255, 255, 210))
                    im.paste(Image.blend(im, Image.new("RGB", (W, H), WHITE), 0.25), (0, 0))
            if key == "lockdown_off":
                center_text(d, 20, "LOCKDOWN LIFTED", F_T, GREEN, shadow=(0, 0, 0))
        elif key == "lockdown":
            flash = int(now * 3) % 2 == 0
            d.rectangle([0, 0, W, 164], fill=(90, 10, 20) if flash else (40, 4, 10))
            d.rectangle([110, 30, 210, 150], fill=(140, 146, 158), outline=(0, 0, 0), width=2)
            for bx in range(118, 210, 14):
                d.rectangle([bx, 30, bx + 5, 150], fill=(70, 70, 80))
            center_text(d, 10, "!! LOCKDOWN !!", F_T, YELLOW if flash else RED, shadow=(0, 0, 0))
            face = portrait("max")
            d.rectangle([20, 50, 20 + face.width + 6, 50 + face.height + 6], fill=(10, 10, 20), outline=CYAN)
            im.paste(face, (23, 53), face)
            d.text((14, 98), "M.A.X.", font=F_B, fill=CYAN)
        elif key == "dark":
            d.rectangle([0, 0, W, 164], fill=(2, 2, 6))
            for rr, col in ((46, (14, 14, 22)), (30, (26, 26, 38))):
                d.ellipse([160 - rr, 110 - rr * 0.6, 160 + rr, 110 + rr * 0.6], fill=col)
            jas = char_frames(player_pal(self.outfit_idx))["down"][0].rotate(90, expand=True).resize((32, 32), Image.NEAREST)
            im.paste(jas, (144, 96), jas)
            if self.story_run and self.story_run["i"] == len(self.story_run["slides"]) - 1:
                gio = char_frames(pal_of("gio"))["left"][0].resize((32, 32), Image.NEAREST)
                im.paste(gio, (250, 84), gio)
                d.text((236, 70), "Jaslyne?!", font=F_B, fill=WHITE)

    def render_library(self, now):
        im = Image.new("RGB", (W, H), (40, 28, 22))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W, 16], fill=(90, 40, 50))
        d.text((6, 3), "LESSON BOOKS", font=F_B, fill=YELLOW)
        d.text((150, 4), "Read: %d / %d chapters" % (len(self.read), len(CHAPTERS)), font=F_S, fill=WHITE)
        for i, ch in enumerate(CHAPTERS):
            y = 20 + i * 26
            sel = i == self.library_sel
            draw_box(d, (6, y, W - 6, y + 23), fill=(110, 60, 50) if sel else (64, 40, 32),
                     border=YELLOW if sel else (120, 90, 60), rad=3)
            d.rectangle([12, y + 4, 22, y + 19], fill=(150, 40, 50) if i % 2 == 0 else (40, 90, 150), outline=(0, 0, 0))
            d.text((28, y + 3), "Chapter %d: %s" % (i + 1, ch["title"]), font=F_B, fill=WHITE)
            got = sum(1 for c in ch["cards"] if self.cards.get(c, 0) >= 3)
            d.text((28, y + 13), "flashcards mastered %d/%d" % (got, len(ch["cards"])), font=F_S, fill=(220, 200, 170))
            if i in self.read:
                d.text((W - 48, y + 7), "READ", font=F_B, fill=GREEN)
            else:
                d.text((W - 44, y + 7), "NEW", font=F_B, fill=YELLOW)
        d.rectangle([0, 206, W, H], fill=(90, 40, 50))
        d.text((8, 210), "CENTER: read chapter     RIGHT: its flashcards", font=F_B, fill=WHITE)
        d.text((8, 224), "UP/DOWN: choose     LEFT: leave", font=F_S, fill=(240, 200, 200))
        return im

    def render_book(self, now):
        bk = self.book
        ch = CHAPTERS[bk["ch"]]
        text, keyword, art = ch["pages"][bk["page"]]
        im = Image.new("RGB", (W, H), (60, 40, 28))
        d = ImageDraw.Draw(im)
        d.rectangle([6, 8, 314, 214], fill=(120, 30, 40), outline=(50, 10, 16))
        d.rectangle([12, 12, 157, 208], fill=CREAM)
        d.rectangle([163, 12, 308, 208], fill=CREAM)
        d.line([(160, 12), (160, 208)], fill=(120, 100, 80), width=3)
        d.text((20, 18), "CHAPTER %d" % (bk["ch"] + 1), font=F_S, fill=(150, 60, 60))
        for i, ln in enumerate(wrap(d, ch["title"], F_B, 130)[:2]):
            d.text((20, 28 + i * 11), ln, font=F_B, fill=NAVY)
        for i, ln in enumerate(wrap(d, text, F_M, 128)[:11]):
            d.text((20, 56 + i * 12), ln, font=F_M, fill=TXT)
        # right page: picture + key word
        if isinstance(art, list):
            pic = Image.new("RGB", (140, 90), CREAM)
            draw_art(ImageDraw.Draw(pic), art)
            im.paste(pic, (166, 36))
        else:
            draw_book_art(d, art, 236, 82)
        draw_box(d, (172, 140, 300, 170), fill=(255, 245, 200), border=(180, 140, 60), rad=4)
        d.text((180, 144), "KEY WORD", font=F_S, fill=(150, 110, 40))
        center_text(d, 155, keyword, F_B, NAVY, cx=236)
        center_text(d, 194, "page %d / %d" % (bk["page"] + 1, len(ch["pages"])), F_S, (120, 110, 100), cx=236)
        last = bk["page"] == len(ch["pages"]) - 1
        d.text((8, 220), "RIGHT/CENTER: %s     LEFT: back     UP: close book" %
               ("finish chapter!" if last else "next page"), font=F_S, fill=(255, 230, 200))
        return im

    SB_SHORT = {"wire": "wire", "resistor": "resistor", "fan": "fan", "vibe": "vibe motor", "motor": "DC motor",
                "laser": "laser", "dip": "DIP switch", "button": "button", "pot": "slide pot"}

    def draw_sb_part(self, d, cell, x, y, on, now):
        pid = cell["p"]
        if pid == "wire":
            d.line([(x - 20, y), (x + 20, y)], fill=WIRE["yellow"], width=3)
        elif pid.startswith("led"):
            col = LED_COL[pid[4:]]
            d.line([(x - 20, y), (x + 20, y)], fill=LEAD)
            if on:
                for rr in (16, 12):
                    d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=tuple(min(255, c + 80) for c in col))
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=tuple(min(255, c + 60) for c in col) if on else col, outline=(0, 0, 0))
            plus_x = x + 12 if cell["flip"] else x - 18
            d.text((plus_x, y - 15), "+", font=F_B, fill=WHITE)
        elif pid == "fan":
            draw_fan(d, x, y, now * 9 if on else 0.4)
        else:
            draw_art(d, [(pid, x, y)])
            if on and pid == "motor":
                draw_motor_spin(d, x, y, now)
            if on and pid == "laser":
                draw_laser_beam(d, x, y, now)
            if on and pid == "vibe":
                for j in range(2):
                    rr = 15 + ((now * 10 + j * 5) % 8)
                    d.arc([x - rr, y - rr, x + rr, y + rr], 150, 210, fill=ORANGE)
        # name label under the slot
        if sb_polar(pid) and cell["flip"]:
            label, ink = "BACKWARDS!", RED
        elif sb_kind(pid) == "toggle":
            label, ink = "%s: %s" % (self.SB_SHORT[pid], ("PRESSED" if pid == "button" else "ON") if cell["on"] else
                                     ("up" if pid == "button" else "OFF")), (GREEN if cell["on"] else (255, 170, 170))
        else:
            label, ink = (pid[4:] + " LED") if pid.startswith("led") else self.SB_SHORT[pid], (200, 215, 235)
        w = d.textlength(label, font=F_S)
        d.text((x - w / 2, y + 21), label, font=F_S, fill=ink)

    def render_bench(self, now):
        bn = self.bench
        im = Image.new("RGB", (W, H), (12, 16, 30))
        d = ImageDraw.Draw(im)
        for gx in range(0, W, 16):
            d.line([(gx, 16), (gx, H)], fill=(18, 24, 42))
        d.rectangle([0, 0, W, 15], fill=PANEL)
        d.text((6, 3), "WORKBENCH - FREE BUILD", font=F_B, fill=YELLOW)
        draw_bolt(d, 283, 8, 0.9)
        d.text((290, 3), "%d" % self.bolts, font=F_S, fill=YELLOW)
        if self.job_seed is not None:
            _g, text, _c, reward = make_job(self.job_seed)
            d.text((6, 18), ("JOB (+%d): " % reward) + text, font=F_S, fill=(255, 220, 120))
        else:
            d.text((6, 18), "No job right now - build anything! (Get jobs at the Job Board)", font=F_S, fill=CYAN)
        PX, MX = 62, 298
        ys = [54, 104, 154]
        xs = [86 + i * 46 for i in range(SB_COLS)]
        d.rectangle([PX - 3, 34, PX + 3, 178], fill=(220, 40, 40))
        d.rectangle([MX - 3, 34, MX + 3, 178], fill=(40, 80, 220))
        d.text((PX - 14, 26), "+ POWER", font=F_S, fill=(255, 150, 150))
        d.text((MX - 30, 26), "- GROUND", font=F_S, fill=(150, 170, 255))
        rows = bn["rows"]
        for r in range(SB_ROWS):
            y = ys[r]
            st = rows[r][0] if rows else None
            on = st == "on"
            d.line([(PX, y), (MX, y)], fill=YELLOW if on else (80, 90, 110), width=2)
            if on:
                electrons(d, [((PX, y), (MX, y))], now, speed=0.35)
            for c in range(SB_COLS):
                x, cell = xs[c], self.sb[r][c]
                d.rectangle([x - 20, y - 20, x + 20, y + 20], fill=(30, 40, 58) if cell else (18, 22, 36),
                            outline=(70, 82, 110) if cell else (50, 56, 76))
                if cell:
                    self.draw_sb_part(d, cell, x, y, on, now)
                else:
                    d.text((x - 10, y - 5), "empty", font=F_S, fill=(70, 78, 100))
            if rows:   # row result light at the end of the row
                col = GREEN if on else (90, 90, 100) if st == "empty" else (255, 170, 60) if st in ("cap", "noload") else RED
                d.ellipse([MX + 7, y - 5, MX + 17, y + 5], fill=col, outline=(0, 0, 0))
        # left-side buttons
        for i, (label, col) in enumerate((("POWER " + ("ON" if bn["power"] else "OFF"), GREEN if bn["power"] else RED),
                                          ("CLEAR", ORANGE), ("EXIT", (150, 150, 170)))):
            y = ys[i]
            sel = bn["cx"] < 0 and bn["cy"] == i
            draw_box(d, (2, y - 12, 52, y + 12), fill=(60, 60, 80) if sel else (30, 30, 46), border=YELLOW if sel else col, rad=3)
            words = label.split(" ")
            for k, wd in enumerate(words):
                tw = d.textlength(wd, font=F_S)
                d.text((27 - tw / 2, y - 4 - 5 * (len(words) - 1) + k * 10), wd, font=F_S, fill=col)
        if bn["cx"] >= 0:
            col = YELLOW if int(now * 4) % 2 == 0 else WHITE
            x, y = xs[bn["cx"]], ys[bn["cy"]]
            d.rectangle([x - 22, y - 22, x + 22, y + 22], outline=col, width=2)
        # explanation panel
        d.rectangle([0, 186, W, H], fill=(24, 30, 54))
        if not bn["power"]:
            msg = "Power is OFF. Build your circuit, then go LEFT to POWER and press CENTER to test it!"
        else:
            msg = "Row %d: %s" % (bn["cy"] + 1, rows[bn["cy"]][1])
        for i, ln in enumerate(wrap(d, msg, F_M, W - 12)[:2]):
            d.text((6, 189 + i * 12), ln, font=F_M, fill=WHITE)
        d.text((6, 225), "CENTER: add / change part     go LEFT for POWER, CLEAR, EXIT", font=F_S, fill=(150, 160, 200))
        if bn["banner"]:
            giver, title, text = bn["banner"]
            draw_box(d, (40, 60, 280, 150), fill=(30, 24, 60), border=YELLOW)
            center_text(d, 70, title, F_T, YELLOW, shadow=(0, 0, 0))
            for i, ln in enumerate(wrap(d, text, F_S, 220)[:2]):
                center_text(d, 92 + i * 11, ln, F_S, WHITE)
            center_text(d, 118, "%s says thank you!" % CHAR_DEFS[giver]["name"], F_B, (255, 170, 200))
            center_text(d, 134, "CENTER: continue", F_S, CYAN)
        if self.ovl:
            self.draw_ovl(im)
        return im

    def render_decor(self, now):
        im = self.render_world(now)
        d = ImageDraw.Draw(im)
        dc = self.dec
        # top bar
        d.rectangle([0, 0, W, 15], fill=(70, 34, 90))
        d.line([(0, 15), (W, 15)], fill=(255, 170, 210))
        d.text((5, 3), "DESIGN", font=F_B, fill=(255, 200, 230))
        tool = dc["tool"]
        if tool == "place" and self.design_item:
            fid = self.design_item
            have = self.furn.get(fid, 0)
            info = "%s  %s" % (FURNITURE[fid][0], ("have %d" % have) if have else ("%d bolts" % FURNITURE[fid][1]))
        elif tool == "move":
            info = "MOVE: carrying %s" % FURNITURE[dc["carry"][0]][0] if dc["carry"] else "MOVE: pick something up"
        elif tool == "erase":
            info = "ERASE: remove things"
        else:
            info = "pick an item (ITEMS)"
        d.text((52, 3), info[:40], font=F_S, fill=WHITE)
        draw_bolt(d, 283, 8, 0.9)
        d.text((290, 3), "%d" % self.bolts, font=F_S, fill=YELLOW)
        # cursor + live preview
        if not dc["onbar"] and not dc["cat"]:
            x, y = dc["x"] * TS, dc["y"] * TS
            ghost, ok = None, True
            if tool == "place" and self.design_item:
                ghost = self.design_item
                ok = self.placeable(dc["x"], dc["y"], ghost) is None and \
                    (self.furn.get(ghost, 0) > 0 or self.bolts >= FURNITURE[ghost][1])
            elif tool == "move" and dc["carry"]:
                ghost = dc["carry"][0]
                ok = self.placeable(dc["x"], dc["y"], ghost) is None
            elif tool == "erase":
                ok = bool(self.furniture_at(dc["x"], dc["y"]) or self.removable_here(dc["x"], dc["y"]))
            elif tool == "move":
                ok = bool(self.furniture_at(dc["x"], dc["y"]))
            if ghost:
                g = furn_thumb(ghost, 16).copy()
                g.putalpha(g.split()[3].point(lambda v: v * 170 // 255))
                im.paste(g, (x, y), g)
            pulse = int(now * 4) % 2 == 0
            col = (90, 255, 140) if ok else (255, 80, 90)
            if tool == "erase" and ok:
                col = (255, 170, 60)
            d.rectangle([x - 1, y - 1, x + TS, y + TS], outline=col if pulse else WHITE, width=2)
            if tool == "erase" and ok:
                d.line([(x + 3, y + 3), (x + 12, y + 12)], fill=(255, 80, 90), width=2)
                d.line([(x + 12, y + 3), (x + 3, y + 12)], fill=(255, 80, 90), width=2)
        # toolbar (cached: only redrawn when the tool / selection changes)
        bkey = (tool, dc["onbar"], dc["bar"], self.design_item)
        if bkey not in _bar_cache:
            if len(_bar_cache) > 60:
                _bar_cache.clear()
            bar = Image.new("RGB", (W, H - 222))
            bd = ImageDraw.Draw(bar)
            bd.rectangle([0, 0, W, H], fill=(46, 26, 62))
            bd.line([(0, 0), (W, 0)], fill=(255, 170, 210))
            bw = W // len(DESIGN_TOOLS)
            for i, name in enumerate(DESIGN_TOOLS):
                bx = i * bw
                active = name.lower() == tool
                sel = dc["onbar"] and dc["bar"] == i
                fill = (120, 60, 140) if active else (66, 40, 86)
                bd.rounded_rectangle([bx + 2, 2, bx + bw - 3, H - 224], radius=3, fill=fill,
                                     outline=YELLOW if sel else (150, 110, 170), width=2 if sel else 1)
                if name == "PLACE" and self.design_item:
                    t = furn_thumb(self.design_item, 12)
                    bar.paste(t, (bx + 4, 4), t)
                    bd.text((bx + 18, 5), "PLACE", font=F_S, fill=WHITE)
                else:
                    center_text(bd, 5, name, F_S, WHITE, cx=bx + bw // 2)
            _bar_cache[bkey] = bar
        im.paste(_bar_cache[bkey], (0, 222))
        if dc["onbar"] and not dc["cat"]:
            tips = {"ITEMS": "Browse all furniture", "PLACE": "Put the picked item down", "MOVE": "Pick up & carry things",
                    "ERASE": "Remove furniture or room objects", "UNDO": "Take back the last change",
                    "DONE": "Finish decorating"}
            tip = tips[DESIGN_TOOLS[dc["bar"]]] + "  (CENTER)"
            tw = d.textlength(tip, font=F_S)
            d.rectangle([W // 2 - tw / 2 - 5, 208, W // 2 + tw / 2 + 5, 220], fill=(30, 18, 40), outline=(255, 170, 210))
            center_text(d, 210, tip, F_S, WHITE)
        if dc["msg"] and now - dc["msg_t"] < 2.6:
            lines =wrap(d, dc["msg"], F_S, 280)[:2]
            h = 6 + 10 * len(lines)
            d.rounded_rectangle([14, 205 - h, W - 14, 203], radius=4, fill=(30, 18, 40), outline=(255, 170, 210))
            for i, ln in enumerate(lines):
                center_text(d, 205 - h + 3 + i * 10, ln, F_S, WHITE)
        if dc["cat"]:
            self.draw_catalog(im, d, now)
        if dc["help"]:
            self.draw_design_help(d, now)
        return im

    def draw_catalog(self, im, d, now):
        c = self.dec["cat"]
        secs = self.catalog_sections()
        d.rectangle([0, 16, W, H], fill=(36, 22, 50))
        d.rectangle([0, 16, W, 28], fill=(70, 34, 90))
        d.text((6, 18), "CATALOG", font=F_B, fill=(255, 200, 230))
        d.text((104, 19), "arrows browse  CENTER pick  LEFT back", font=F_S, fill=(220, 200, 230))
        # sections
        for i in range(c["top"], min(len(secs), c["top"] + 10)):
            y = 32 + (i - c["top"]) * 19
            sel = i == c["sec"]
            fill = (120, 60, 140) if sel else (56, 34, 74)
            d.rounded_rectangle([4, y, 96, y + 16], radius=3, fill=fill,
                                outline=YELLOW if sel and c["focus"] == "sec" else (110, 80, 130))
            d.text((10, y + 3), secs[i][:15], font=F_S, fill=WHITE if sel else (220, 200, 230))
        # item grid
        items = self.catalog_items(c["sec"])
        if not items:
            msg = "Place something and it shows up here!" if secs[c["sec"]] == "Recent" else "Nothing here yet!"
            center_text(d, 90, msg, F_M, (220, 200, 230), cx=208)
        for k in range(c["row0"] * CAT_COLS, min(len(items), (c["row0"] + CAT_ROWS) * CAT_COLS)):
            fid = items[k]
            col, row = k % CAT_COLS, k // CAT_COLS - c["row0"]
            bx, by = 104 + col * 42, 32 + row * 44
            sel = k == c["sel"] and c["focus"] == "grid"
            d.rounded_rectangle([bx, by, bx + 38, by + 40], radius=4, fill=(250, 236, 244) if sel else (210, 190, 215),
                                outline=YELLOW if sel else (120, 90, 140), width=2 if sel else 1)
            t = furn_thumb(fid, 32)
            im.paste(t, (bx + 3, by + 2), t)
            have = self.furn.get(fid, 0)
            label = ("x%d" % have) if have else "%d" % FURNITURE[fid][1]
            d.text((bx + 3, by + 31), label, font=F_S, fill=(30, 120, 60) if have else (120, 70, 20))
        if len(items) > (c["row0"] + CAT_ROWS) * CAT_COLS:
            d.polygon([(306, 166), (314, 166), (310, 171)], fill=WHITE)
        if c["row0"] > 0:
            d.polygon([(306, 34), (314, 34), (310, 29)], fill=WHITE)
        # details of the highlighted item
        if items:
            fid = items[min(c["sel"], len(items) - 1)]
            d.rounded_rectangle([104, 176, 316, 236], radius=4, fill=(56, 34, 74), outline=(255, 170, 210))
            t = furn_thumb(fid, 48)
            im.paste(t, (110, 182), t)
            name, cost, solid, theme = FURNITURE[fid]
            d.text((166, 182), name, font=F_B, fill=WHITE)
            have = self.furn.get(fid, 0)
            d.text((166, 196), ("You have %d" % have) if have else ("%d Bolts (bought when you place it)" % cost)[:34],
                   font=F_S, fill=(140, 230, 170) if have else YELLOW)
            kind = "Floor - goes under furniture" if fid in FLOOR_IDS else ("Walk-through" if not solid else theme)
            d.text((166, 208), kind, font=F_S, fill=(220, 200, 230))
            d.text((166, 222), "CENTER: pick this", font=F_S, fill=(255, 200, 230))

    def draw_design_help(self, d, now):
        draw_box(d, (16, 22, 304, 218), fill=(255, 245, 250), border=(150, 70, 140))
        center_text(d, 28, "DESIGN MODE", F_T, (150, 50, 120))
        lines = ["Arrows move the square around. Hold one to glide fast.",
                 "CENTER uses your tool on that square.",
                 "Go DOWN past the floor to reach the toolbar:",
                 "  ITEMS - browse every piece of furniture",
                 "  PLACE - put your picked piece down",
                 "  MOVE - pick something up and carry it",
                 "  ERASE - remove furniture or room objects",
                 "  UNDO - take back your last change",
                 "Hold CENTER while moving to place a whole line",
                 "(great for floors and walls!).",
                 "Green square = it fits. Red = it doesn't.",
                 "Pieces you don't own are bought as you place them."]
        for i, ln in enumerate(lines):
            d.text((28, 48 + i * 12), ln, font=F_S, fill=TXT)
        if int(now * 2) % 2 == 0:
            center_text(d, 200, "Press CENTER to start decorating!", F_B, (200, 60, 140))

    def draw_howto(self, im, d, kind, now):
        """Simple picture guide shown before the first puzzles of each type."""
        draw_box(d, (14, 20, 306, 216), fill=CREAM, border=NAVY)
        center_text(d, 26, "HOW TO PLAY", F_T, NAVY)
        if kind == "pipe":
            steps = ["1. The green battery has power.",
                     "2. Press CENTER on a pipe to spin it.",
                     "3. Pipes with power turn YELLOW.",
                     "4. Make a yellow path to the bulb. Done!"]
            # mini picture: battery -> 3 pipes -> bulb, middle one spinning
            y, cs = 132, 26
            d.rectangle([46, y - 6, 58, y + 6], fill=(60, 200, 90), outline=(0, 0, 0))
            spin = int(now * 1.2) % 2 == 0
            for i in range(3):
                cx = 62 + i * cs
                d.rectangle([cx, y - cs // 2, cx + cs - 1, y + cs // 2], fill=(26, 30, 48), outline=(44, 50, 76))
                mx = cx + cs // 2
                horizontal = i != 1 or spin
                col = YELLOW if (i == 0 or spin) else (130, 140, 165)
                if horizontal:
                    d.line([(cx, y), (cx + cs, y)], fill=col, width=4)
                else:
                    d.line([(mx, y - cs // 2), (mx, y + cs // 2)], fill=col, width=4)
            lit = spin
            d.ellipse([62 + 3 * cs + 4, y - 7, 62 + 3 * cs + 18, y + 7], fill=YELLOW if lit else (70, 70, 80), outline=(0, 0, 0))
            d.text((186, y - 12), "spin the middle" if not spin else "connected!", font=F_B, fill=NAVY)
            d.text((186, y + 2), "pipe..." if not spin else "bulb is ON", font=F_B, fill=GREEN if spin else NAVY)
        else:
            steps = ["1. Goal: make EVERY bulb glow yellow.",
                     "2. Press CENTER to flip a bulb on/off.",
                     "3. Careful! The bulbs next to it flip too",
                     "   (they have a pink box around them)."]
            y0, cs = 108, 18
            phase = int(now * 1.0) % 2
            for yy in range(3):
                for xx in range(3):
                    on = phase == 1 or not (abs(xx - 1) + abs(yy - 1) <= 1)
                    cx, cy = 60 + xx * cs, y0 + yy * cs
                    d.ellipse([cx + 2, cy + 2, cx + cs - 3, cy + cs - 3], fill=(255, 220, 80) if on else (52, 52, 64), outline=(0, 0, 0))
                    if abs(xx - 1) + abs(yy - 1) == 1:
                        d.rectangle([cx, cy, cx + cs - 1, cy + cs - 1], outline=(255, 140, 200))
            d.rectangle([60 + cs - 1, y0 + cs - 1, 60 + 2 * cs, y0 + 2 * cs], outline=YELLOW, width=2)
            d.text((130, y0 + 8), "press the middle..." if phase == 0 else "5 bulbs flipped!", font=F_B, fill=NAVY)
            d.text((130, y0 + 22), "" if phase == 0 else "all ON = you win", font=F_B, fill=GREEN)
        for i, s in enumerate(steps):
            d.text((26, 46 + i * 13), s, font=F_M, fill=TXT)
        d.text((26, 170), "Fewer moves = more stars.  Stuck? Go LEFT to EXIT.", font=F_S, fill=(110, 110, 145))
        if int(now * 2) % 2 == 0:
            center_text(d, 192, "Press CENTER to start!", F_B, RED)

    def music_track(self):
        m = self.mode
        if m == "title":
            return "title"
        if m in ("build", "puzzle", "bench"):
            return "build"
        if m == "ending":
            return "ending"
        if m == "focus":
            return None   # quiet while she studies for real
        if m in ("story", "blank"):
            return "cozy"
        if self.tut is not None or self.room in ("jroom", "study", "arcade", "store") or m in ("decor", "library", "book"):
            return "cozy"
        return "world"

    def entity_sprite(self, key, face, walking, now, pal=None):
        if key in PETS:
            return pet_sprite(key, face, int(now * (8 if walking else 3)) % (3 if key == "lafufu" else 2))
        fr = char_frames(pal or pal_of(key))[face]
        return fr[(1 + int(now * 7) % 2) if walking else 0]

    def render_world(self, now):
        room = ROOMS[self.room]
        zone = room["zone"]
        tour = self.tut is not None
        zdone = frozenset(q for q in self.done if zone is not None and q // PER_ZONE == zone)
        gone = frozenset((x, y) for r, x, y in self.removed_set if r == self.room)
        bkey = (self.room, zdone, tour, gone)
        if bkey not in _bg_cache:
            _bg_cache[bkey] = build_bg(self.room, set(range(NQ)) if tour else self.done, gone)
        here = tuple(tuple(e) for e in self.decor if e[0] == self.room)
        skey = (bkey, here)
        if skey not in _static_cache:   # furniture never moves on its own, so draw it once per change
            if len(_static_cache) > 24:
                _static_cache.clear()
            base = _bg_cache[bkey].copy()
            bd = ImageDraw.Draw(base)
            for _r, x, y, fid in sorted(here, key=lambda e: (e[3] not in FLOOR_IDS, FURNITURE[e[3]][2])):   # floors, rugs, rest
                draw_furniture(bd, fid, x * TS, y * TS)
            _static_cache[skey] = base
        im = _static_cache[skey].copy()
        d = ImageDraw.Draw(im)
        ents = []
        for n in self.npcs:
            ents.append((n.py, self.entity_sprite(n.key, n.face, n.moving, now), n.px, n.py))
        jas = self.entity_sprite("jas", self.facing, self.walking, now, player_pal(self.outfit_idx))
        ents.append((self.py, jas, self.px, self.py))
        if tour and self.trail:   # Gio follows a few steps behind her during the tour
            gx, gy, gface, gwalk = self.trail[0]
            ents.append((gy - 0.1, self.entity_sprite("gio", gface, gwalk, now), gx, gy))
        for _, spr, ex, ey in sorted(ents, key=lambda e: e[0]):
            d.ellipse([ex + 3, ey + 12, ex + 13, ey + 16], fill=(14, 14, 22))
            im.paste(spr, (int(ex), int(ey)), spr)
        lit = self.powered(zone)
        im = apply_light(im, int(self.px + 8), int(self.py + 8), lit, 1 if "flashlight" in self.upgrades else 0)
        d = ImageDraw.Draw(im)
        # unsearched stashes twinkle now and then, like item balls in Pokemon
        for tx, ty in room["stashes"]:
            if "%s:%d:%d" % (self.room, tx, ty) not in self.looted and (self.room, tx, ty) not in self.removed_set:
                ph = (now * 1.3 + tx * 0.37 + ty * 0.61) % 3.0
                if ph < 0.5:
                    r = 1 + int(ph * 6)
                    sx, sy = tx * TS + 12, ty * TS + 4
                    d.line([(sx - r, sy), (sx + r, sy)], fill=WHITE)
                    d.line([(sx, sy - r), (sx, sy + r)], fill=WHITE)
        if zone is not None and not tour:
            first = next((q for q in range(zone * PER_ZONE, zone * PER_ZONE + PER_ZONE) if q not in self.done), None)
            for tx, ty, idx in room["terms"]:
                q = zone * PER_ZONE + idx - 1
                draw_terminal_screen(d, tx * TS, ty * TS, q in self.done, now)
                if q == first:
                    by = ty * TS - 12 + int(math.sin(now * 6) * 2)
                    d.rounded_rectangle([tx * TS + 3, by, tx * TS + 12, by + 10], radius=2, fill=YELLOW, outline=(0, 0, 0))
                    d.text((tx * TS + 6, by - 1), "!", font=F_B, fill=(0, 0, 0))
        if not self.dialog and not self.menu and not self.walking:
            for n in self.npcs:
                if not n.moving and abs(n.tx - self.tx) + abs(n.ty - self.ty) == 1:
                    draw_talk_bubble(d, int(n.px) + 3, int(n.py) - 10 + int(now * 2) % 2)
        self.draw_hud(im, room)
        if tour and self.room == TOUR[self.tut]["room"]:
            self.draw_tour(d, now)
        if self.dialog:
            dg = self.dialog
            key, text = dg["lines"][dg["i"]]
            shown = int((now - dg["t0"]) * 45)
            done = draw_dialog(im, key, text, shown, now)
            if done and dg["i"] == len(dg["lines"]) - 1 and dg["choices"]:
                draw_choices(ImageDraw.Draw(im), dg["choices"], dg["sel"])
        if self.menu:
            self.draw_menu(im, now)
        return im

    def draw_tour(self, d, now):
        step = TOUR[self.tut]
        target = step["target"]
        if step.get("npc"):
            guide = next((n for n in self.npcs if n.key == step["npc"]), None)
            target = (guide.tx, guide.ty) if guide else None
        if target and not self.dialog:
            x, y = target[0] * TS + 8, target[1] * TS - 6 + int(math.sin(now * 6) * 3)
            d.polygon([(x - 6, y - 8), (x + 6, y - 8), (x, y)], fill=YELLOW, outline=(0, 0, 0))
            if step["goal"] == "reach":
                r = 5 + int((now * 8) % 4)
                d.ellipse([x - r, target[1] * TS + 8 - r // 2, x + r, target[1] * TS + 8 + r // 2], outline=YELLOW)
        msg = "TOUR %d/%d: %s" % (self.tut + 1, len(TOUR), step["objective"])
        w = d.textlength(msg, font=F_S)
        d.rectangle([0, H - 12, w + 10, H], fill=(40, 30, 80))
        d.text((5, H - 11), msg, font=F_S, fill=(255, 220, 120))

    def draw_hud(self, im, room):
        pct = 100 if self.tut is not None else len(self.done) * 100 // NQ
        key = (room["name"], pct, len(self.done), self.bolts)
        if key not in _hud_cache:
            if len(_hud_cache) > 40:
                _hud_cache.clear()
            bar = Image.new("RGB", (W, 16))
            self._draw_hud(ImageDraw.Draw(bar), room)
            _hud_cache[key] = bar
        im.paste(_hud_cache[key], (0, 0))

    def _draw_hud(self, d, room):
        d.rectangle([0, 0, W, 15], fill=PANEL)
        d.line([(0, 15), (W, 15)], fill=CYAN_D)
        d.text((6, 3), room["name"], font=F_B, fill=YELLOW)
        pct = 100 if self.tut is not None else len(self.done) * 100 // NQ
        d.text((134, 3), "PWR", font=F_S, fill=CYAN)
        d.rectangle([154, 4, 204, 11], fill=(10, 30, 40), outline=CYAN_D)
        if pct:
            d.rectangle([155, 5, 155 + int(48 * pct / 100), 10], fill=GREEN if pct == 100 else CYAN)
        d.text((208, 3), "%d%%" % pct, font=F_S, fill=WHITE)
        draw_star(d, 250, 8, 5, YELLOW)
        d.text((257, 3), "%d" % len(self.done), font=F_S, fill=WHITE)
        draw_bolt(d, 283, 8, 0.9)
        d.text((290, 3), "%d" % self.bolts, font=F_S, fill=YELLOW)

    def draw_menu(self, im, now):
        d = ImageDraw.Draw(im)
        mn = self.menu
        page = mn["page"]
        if page == "main":
            items = self.menu_items()
            draw_box(d, (222, 20, 314, 20 + len(items) * 18 + 12))
            for i, it in enumerate(items):
                y = 27 + i * 18
                if i == mn["sel"]:
                    d.polygon([(230, y + 1), (230, y + 9), (236, y + 5)], fill=NAVY)
                d.text((242, y), it, font=F_B, fill=TXT)
            if mn["msg"]:
                my = 20 + len(items) * 18 + 16
                draw_box(d, (196, my, 314, my + 20))
                d.text((204, my + 6), mn["msg"], font=F_M, fill=(30, 120, 60))
            return
        d.rectangle([0, 16, W, H], fill=(14, 20, 34))
        d.rectangle([0, 16, W, 34], fill=PANEL)
        d.text((10, 21), page.upper(), font=F_T, fill=YELLOW)
        d.text((190, 24), "LEFT: back", font=F_S, fill=CYAN)
        if page == "quests":
            for i in range(mn["scroll"], min(NQ + NS, mn["scroll"] + 8)):
                y = 40 + (i - mn["scroll"]) * 22
                L = LEVELS[i]
                sel = i == mn["sel"]
                side = i >= NQ
                draw_box(d, (8, y, W - 8, y + 19), fill=(40, 70, 96) if sel else (24, 36, 56), border=YELLOW if sel else CYAN_D, rad=3)
                job = i == JOB_SLOT
                d.text((16, y + 5), "JOB" if job else "S%d" % (i - NQ + 1) if side else "Q%d" % (i + 1), font=F_B,
                       fill=(120, 255, 160) if job else (255, 170, 220) if side else CYAN)
                title = (L["title"] if self.quest_seed is not None else "New job - earn Bolts!") if job else L["title"]
                d.text((44, y + 5), title[:20], font=F_B, fill=WHITE)
                d.text((196, y + 5), "CENTER: start" if side and sel else "SIDE QUEST" if side else ZONES[i // PER_ZONE][:12],
                       font=F_S, fill=(140, 170, 190))
                if i in self.done or i in self.side_done:
                    draw_star(d, W - 22, y + 10, 6, YELLOW)
        elif page == "sound":
            d.text((14, 42), "Turn each one up or down. Changes are saved.", font=F_S, fill=(180, 200, 230))
            for i, (label, key, note) in enumerate(SOUND_SLIDERS):
                y = 58 + i * 34
                sel = i == mn["sel"]
                draw_box(d, (10, y, W - 10, y + 28), fill=(40, 70, 96) if sel else (24, 36, 56),
                         border=YELLOW if sel else CYAN_D, rad=3)
                d.text((18, y + 4), label, font=F_B, fill=WHITE)
                d.text((18, y + 16), note, font=F_S, fill=(150, 175, 200))
                v = getattr(self, key)
                for k in range(10):   # 10-segment slider
                    bx = 150 + k * 13
                    on = k < v
                    d.rectangle([bx, y + 8, bx + 10, y + 20], fill=(GREEN if v > 3 else ORANGE) if on else (20, 30, 46),
                                outline=(70, 90, 110))
                d.text((W - 26, y + 10), "%d" % v, font=F_B, fill=YELLOW if sel else WHITE)
                if sel:
                    d.polygon([(142, y + 14), (147, y + 9), (147, y + 19)], fill=YELLOW)
                    d.polygon([(W - 32, y + 14), (W - 37, y + 9), (W - 37, y + 19)], fill=YELLOW)
            y = 58 + len(SOUND_SLIDERS) * 34
            sel = mn["sel"] == len(SOUND_SLIDERS)
            draw_box(d, (110, y, 210, y + 18), fill=(40, 70, 96) if sel else (24, 36, 56), border=YELLOW if sel else CYAN_D, rad=3)
            center_text(d, y + 4, "BACK", F_B, WHITE)
            d.text((14, 226), "UP/DOWN choose   LEFT/RIGHT quieter/louder   CENTER back", font=F_S, fill=CYAN)
        elif page == "trophies":
            d.text((110, 22), "%d / %d" % (len(self.ach), len(ACHIEVEMENTS)), font=F_B, fill=WHITE)
            for i in range(mn["scroll"], min(len(ACHIEVEMENTS), mn["scroll"] + 7)):
                aid, name, desc, _fn = ACHIEVEMENTS[i]
                y = 38 + (i - mn["scroll"]) * 28
                got, sel = aid in self.ach, i == mn["sel"]
                draw_box(d, (8, y, W - 8, y + 26), fill=(40, 70, 96) if sel else (24, 36, 56),
                         border=YELLOW if sel else CYAN_D, rad=3)
                draw_trophy(d, 22, y + 13, YELLOW if got else (70, 80, 100))
                d.text((36, y + 3), name if got else name + "  (locked)", font=F_B, fill=WHITE if got else (130, 140, 160))
                d.text((36, y + 14), desc, font=F_S, fill=(180, 210, 230) if got else (100, 110, 130))
        elif page == "bag":
            d.text((14, 44), "BOLTS: %d" % self.bolts, font=F_T, fill=YELLOW)
            d.text((14, 62), "STARS: %d / %d      POWER: %d%%" % (len(self.done), NQ, len(self.done) * 100 // NQ), font=F_B, fill=WHITE)
            d.text((14, 75), "NOTES %d/%d   JOBS %d   STEPS %d   TIME %dm   STREAK %dd" % (
                self.notes_found(), len(SECRET_NOTES), self.jobs_done, self.steps, int(self.play // 60), self.streak),
                font=F_S, fill=(255, 170, 200))
            d.text((14, 86), "STUDIED %dm   CARDS %d/%d   PUZZLES %d/%d   3-STAR %d" % (
                self.focus_min, self.cards_mastered(), len(CARDS), len(self.pipes) + len(self.lights),
                2 * PUZZLES_PER_KIND, self.three_stars()), font=F_S, fill=(140, 230, 200))
            goal = WEEKLY_GOALS[self.week_goal]
            prog = min(goal[2], goal[1](self) - self.week_base)
            d.text((14, 97), "WEEKLY: %s  %d/%d%s" % (goal[0], prog, goal[2], "  DONE!" if self.week_done else ""),
                   font=F_S, fill=YELLOW)
            tools = [it for it in STORE_ITEMS if it["type"] == "tool" and it["id"] in self.upgrades]
            if not tools:
                d.text((14, 116), "No tools yet. Visit Tess's Store", font=F_M, fill=CYAN)
                d.text((14, 130), "(top-left door in the Workshop)!", font=F_M, fill=CYAN)
            for i, it in enumerate(tools):
                y = 109 + i * 18
                draw_box(d, (10, y, W - 10, y + 17), fill=(24, 36, 56), border=CYAN_D, rad=3)
                d.text((18, y + 4), it["name"], font=F_B, fill=GREEN)
                d.text((122, y + 5), it["desc"][:44], font=F_S, fill=WHITE)
        elif page == "outfit":
            outs = self.owned_outfits()
            o = OUTFIT_BY_ID[outs[mn["sel"]]]
            spr = char_frames(player_pal(o["id"]))["down"][int(now * 3) % 2 * 0]
            big = spr.resize((64, 64), Image.NEAREST)
            d.rectangle([14, 50, 98, 140], fill=(30, 44, 70), outline=CYAN)
            im.paste(big, (24, 62), big)
            d.text((16, 146), o["name"], font=F_B, fill=WHITE)
            d.text((16, 160), "EQUIPPED" if o["id"] == self.outfit_idx else "CENTER: equip", font=F_S,
                   fill=GREEN if o["id"] == self.outfit_idx else YELLOW)
            for i in range(mn["scroll"], min(len(outs), mn["scroll"] + 9)):
                oid = outs[i]
                y = 42 + (i - mn["scroll"]) * 20
                sel = i == mn["sel"]
                draw_box(d, (116, y, W - 8, y + 17), fill=(40, 70, 96) if sel else (24, 36, 56), border=YELLOW if sel else CYAN_D, rad=3)
                d.text((126, y + 4), OUTFIT_BY_ID[oid]["name"], font=F_B, fill=WHITE)
                if oid == self.outfit_idx:
                    d.text((270, y + 5), "ON", font=F_S, fill=GREEN)

    def render_shop(self, now):
        im = Image.new("RGB", (W, H), (20, 18, 36))
        d = ImageDraw.Draw(im)
        for y in range(0, H, 16):
            for x in range((y // 16 % 2) * 16, W, 32):
                d.rectangle([x, y, x + 15, y + 15], fill=(24, 22, 42))
        d.rectangle([0, 0, W, 20], fill=(90, 36, 90))
        d.line([(0, 20), (W, 20)], fill=YELLOW)
        d.text((8, 5), "TESS'S GENERAL STORE", font=F_B, fill=YELLOW)
        draw_bolt(d, 262, 11, 1.0)
        d.text((270, 5), "%d" % self.bolts, font=F_B, fill=YELLOW)
        if self.shop_cat is None:
            self.draw_shop_sections(im, d, now)
            return im
        d.text((150, 5), self.shop_cat[:16], font=F_S, fill=WHITE)
        items = self.shop_items()
        self.shop_sel = min(self.shop_sel, len(items) - 1)
        it = items[self.shop_sel]
        # showcase
        d.rectangle([8, 26, 130, 142], fill=(34, 40, 70), outline=YELLOW, width=2)
        if it["type"] == "outfit":
            spr = char_frames(player_pal(it["id"]))["down"][0].resize((64, 64), Image.NEAREST)
            im.paste(spr, (37, 40 + int(math.sin(now * 3) * 2)), spr)
        elif it["type"] == "furniture":
            pic = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
            draw_furniture(ImageDraw.Draw(pic), it["id"], 0, 0)
            pic = pic.resize((64, 64), Image.NEAREST)
            im.paste(pic, (37, 44), pic)
            d.text((14, 30), "You have: %d" % self.furn.get(it["id"], 0), font=F_S, fill=CYAN)
        else:
            draw_tool_icon(d, it["id"], 69, 78)
        center_text(d, 120, it["name"], F_M, WHITE, cx=69)
        # list
        rows = items[self.shop_top:self.shop_top + 6]
        for i, r in enumerate(rows):
            idx = self.shop_top + i
            y = 26 + i * 19
            sel = idx == self.shop_sel
            draw_box(d, (138, y, W - 6, y + 17), fill=(60, 50, 100) if sel else (30, 30, 56), border=YELLOW if sel else (70, 70, 120), rad=3)
            d.text((158, y + 4), r["name"], font=F_M, fill=WHITE)
            if sel:
                d.polygon([(144, y + 4), (144, y + 12), (150, y + 8)], fill=YELLOW)
            if self.owned_item(r):
                eq = r["type"] == "outfit" and r["id"] == self.outfit_idx
                d.text((276, y + 5), "ON" if eq else "OWN", font=F_S, fill=GREEN)
            else:
                d.text((282, y + 5), "%d" % r["cost"], font=F_S, fill=YELLOW if self.bolts >= r["cost"] else RED)
        if self.shop_top > 0:
            d.polygon([(W - 14, 24), (W - 8, 24), (W - 11, 20)], fill=WHITE)
        if self.shop_top + 6 < len(items):
            d.polygon([(W - 14, 142), (W - 8, 142), (W - 11, 146)], fill=WHITE)
        status = "OWNED" if self.owned_item(it) else ("Price: %d Bolts" % it["cost"])
        d.text((10, 146), status, font=F_B, fill=GREEN if self.owned_item(it) else YELLOW)
        shown = int((now - self.shop_msg_t) * 45)
        draw_dialog(im, "tess", self.shop_msg, shown, now, hint="UP/DOWN browse   CENTER buy   LEFT back")
        return im

    def draw_shop_sections(self, im, d, now):
        cat = SHOP_CATS[self.shop_csel]
        items = self.shop_items(cat)
        d.rectangle([8, 26, 130, 142], fill=(34, 40, 70), outline=YELLOW, width=2)
        if cat == "OUTFITS":
            spr = char_frames(player_pal(self.outfit_idx))["down"][0].resize((64, 64), Image.NEAREST)
            im.paste(spr, (37, 40 + int(math.sin(now * 3) * 2)), spr)
        elif cat == "TOOLS":
            draw_tool_icon(d, "multimeter", 69, 78)
        else:   # a 2x2 peek at the furniture in this section
            for k, it in enumerate(items[:4]):
                pic = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
                draw_furniture(ImageDraw.Draw(pic), it["id"], 0, 0)
                pic = pic.resize((40, 40), Image.NEAREST)
                im.paste(pic, (22 + (k % 2) * 48, 32 + (k // 2) * 44), pic)
        center_text(d, 124, cat_label(cat), F_B, WHITE, cx=69)
        for i, c in enumerate(SHOP_CATS[self.shop_ctop:self.shop_ctop + 6]):
            idx = self.shop_ctop + i
            y = 26 + i * 19
            sel = idx == self.shop_csel
            draw_box(d, (138, y, W - 6, y + 17), fill=(60, 50, 100) if sel else (30, 30, 56),
                     border=YELLOW if sel else (70, 70, 120), rad=3)
            if sel:
                d.polygon([(144, y + 4), (144, y + 12), (150, y + 8)], fill=YELLOW)
            d.text((158, y + 4), cat_label(c), font=F_M, fill=(255, 200, 140) if c in HOLIDAY_THEMES else WHITE)
            d.text((282, y + 5), "%d" % len(self.shop_items(c)), font=F_S, fill=CYAN)
        if self.shop_ctop > 0:
            d.polygon([(W - 14, 24), (W - 8, 24), (W - 11, 20)], fill=WHITE)
        if self.shop_ctop + 6 < len(SHOP_CATS):
            d.polygon([(W - 14, 142), (W - 8, 142), (W - 11, 146)], fill=WHITE)
        d.text((10, 146), "%d sections" % len(SHOP_CATS), font=F_B, fill=YELLOW)
        shown = int((now - self.shop_msg_t) * 45)
        draw_dialog(im, "tess", self.shop_msg, shown, now, hint="UP/DOWN browse   CENTER open   LEFT leave")

    def build_msg(self):
        L = LEVELS[self.level]
        N = len(L["steps"])
        if self.state == "win":
            if self.win_page == 0:
                extra = "  (+%d Bolts)" % self.reward if self.reward else "  (Practice run)"
                return L["npc"], L["win"] + extra, "CENTER: continue"
            return L["npc"], "Did you know? " + L["fact"], "CENTER: back to the map"
        pages = self.build_pages()
        self.page = min(self.page, len(pages) - 1)
        sp, txt = pages[self.page]
        hint = "tip %d/%d    CENTER next    LEFT back    DOWN zoom    UP exit" % (self.page + 1, len(pages))
        return sp, txt, hint

    def render_build(self, now):
        li = self.level
        L = LEVELS[li]
        N = len(L["steps"])
        gold = "gold_wires" in self.upgrades
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        for gx in range(0, W, 16):
            d.line([(gx, 14), (gx, H)], fill=(12, 20, 30))
        for gy in range(14, H, 16):
            d.line([(0, gy), (W, gy)], fill=(12, 20, 30))
        d.rectangle([0, 0, W, 13], fill=PANEL)
        d.text((6, 2), "Q%d  %s" % (li + 1, L["title"].upper()), font=F_B, fill=CYAN)
        d.text((230, 2), ZONES[li // PER_ZONE] if li < NQ else "SIDE QUEST", font=F_S, fill=YELLOW)
        board, bbox = animate_board(li, self.step, self.state, now, gold)
        key = (li, self.step, self.state, self.win_page, self.page)
        if key != self.msg_key:
            self.msg_key, self.msg_t0 = key, now
        if self.expanded:
            big = board.resize((318, 201), Image.NEAREST)
            im.paste(big, (1, 16))
            d.rectangle([0, 218, W, H], fill=PANEL)
            sp, txt, _h = self.build_msg()
            d.text((6, 224), txt[:56], font=F_M, fill=WHITE)
            d.text((6, 22), "DOWN: shrink", font=F_S, fill=INK)
            return im
        d.rounded_rectangle([3, 14, 222, 155], radius=4, fill=(44, 52, 66), outline=(100, 112, 134), width=2)
        for rx, ry in ((7, 18), (218, 18), (7, 151), (218, 151)):
            d.ellipse([rx - 1, ry - 1, rx + 1, ry + 1], fill=(150, 160, 175))
        im.paste(board, (8, 18))
        if bbox and self.state != "win":
            col = YELLOW if int(now * 3) % 2 == 0 else WHITE
            d.rectangle([8 + bbox[0] - 3, 18 + bbox[1] - 3, 8 + bbox[2] + 2, 18 + bbox[3] + 2], outline=col)
        # progress segments
        sw = 218 / N
        for i in range(N):
            x0 = 4 + i * sw
            col = (GREEN if self.state == "win" else CYAN) if i < self.step else (30, 50, 66)
            d.rectangle([x0, 158, x0 + sw - 3, 162], fill=col)
        # parts panel
        d.rounded_rectangle([226, 14, 316, 155], radius=4, fill=CYAN, outline=CYAN_D, width=2)
        d.text((233, 18), "PARTS", font=F_B, fill=INK)
        placed = {}
        for st in L["steps"][:self.step]:
            placed[st["part"]] = placed.get(st["part"], 0) + 1
        nxt = L["steps"][self.step]["part"] if self.step < N else None
        for i, (n, name) in enumerate(L["parts"]):
            y = 31 + i * 13
            got = placed.get(name, 0)
            done = got >= n
            d.rectangle([232, y, 242, y + 10], fill=GREEN if done else ORANGE if got else (20, 50, 70), outline=INK)
            d.text((235, y + 1), "%d" % n, font=F_S, fill=INK if done else WHITE)
            d.text((248, y + 1), name, font=F_S, fill=INK)
            if name == nxt and self.state != "win" and int(now * 3) % 2 == 0:
                d.polygon([(229, y + 2), (229, y + 8), (232, y + 5)], fill=RED)
        if "multimeter" in self.upgrades:
            d.rectangle([231, 112, 311, 150], fill=(240, 190, 30), outline=(60, 40, 0))
            d.rectangle([235, 116, 307, 134], fill=(150, 210, 160))
            v, ma = L["meter"] if self.state == "win" else (0.0, 0)
            d.text((239, 118), "%.2f V" % v, font=F_B, fill=(20, 50, 20))
            d.text((239, 127), "%d mA" % ma, font=F_S, fill=(20, 50, 20))
            d.text((236, 138), "METER", font=F_S, fill=(60, 40, 0))
        elif nxt:
            d.text((233, 120), "NEXT PART:", font=F_S, fill=INK)
            d.text((233, 132), nxt, font=F_B, fill=INK)
        # dialogue
        sp, txt, hint = self.build_msg()
        shown = int((now - self.msg_t0) * 45)
        draw_dialog(im, sp, txt, shown, now, hint=hint)
        if self.state == "win":
            t = now - self.win_t
            d = ImageDraw.Draw(im)
            draw_confetti(d, self.confetti, t)
            draw_star(d, 214 - 12, 30, 8, YELLOW)
            if t < 0.3:
                im = Image.blend(im, Image.new("RGB", (W, H), WHITE), 0.5 * (1 - t / 0.3))
        return im

    def render_title(self, now):
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        for y in range(0, 170, 3):
            d.rectangle([0, y, W, y + 2], fill=lerp_col((8, 10, 26), (52, 30, 72), y / 170))
        r = random.Random(5)
        for _ in range(40):
            sx, sy = r.randint(0, W), r.randint(0, 110)
            if (int(now * 2) + sx) % 5:
                d.point((sx, sy), fill=(200, 210, 255))
        x = 0
        r = random.Random(9)
        while x < W:
            bw, bh = r.randint(20, 36), r.randint(40, 100)
            d.rectangle([x, 170 - bh, x + bw, 170], fill=(18, 20, 38), outline=(10, 12, 24))
            for wy in range(170 - bh + 6, 164, 9):
                for wx in range(x + 4, x + bw - 4, 7):
                    on = r.random() < 0.18 and (int(now * 1.5) + wx + wy) % 7 != 0
                    d.rectangle([wx, wy, wx + 2, wy + 3], fill=(250, 220, 90) if on else (26, 28, 50))
            x += bw + 2
        d.rectangle([0, 170, W, H], fill=(12, 16, 26))
        segs = [((0, 186), (120, 186)), ((120, 186), (120, 200)), ((120, 200), (200, 200)), ((200, 200), (200, 186)), ((200, 186), (320, 186))]
        for a, b in segs:
            d.line([a, b], fill=CYAN_D, width=2)
        electrons(d, segs, now, color=YELLOW, speed=0.5)
        center_text(d, 14, "GIO'S", F_L, YELLOW, shadow=(90, 50, 0))
        center_text(d, 38, "CIRCUIT GAME", F_L, CYAN, shadow=(0, 40, 60))
        center_text(d, 68, "ESCAPE  THE  BLACKOUT", F_B, WHITE, shadow=(0, 0, 0))
        bob = int(now * 3) % 2 * 2
        g = char_frames(pal_of("gio"))["down"][0].resize((48, 48), Image.NEAREST)
        j = char_frames(player_pal(self.outfit_idx))["down"][0].resize((48, 48), Image.NEAREST)
        im.paste(g, (18, 130 + bob), g)
        im.paste(j, (254, 130 + (2 - bob)), j)
        items = self.title_items()
        bx0, by0 = 98, 118
        draw_box(d, (bx0, by0, bx0 + 124, by0 + len(items) * 20 + 12))
        for i, it in enumerate(items):
            y = by0 + 9 + i * 20
            if i == self.title_sel and not self.title_confirm:
                d.polygon([(bx0 + 12, y + 1), (bx0 + 12, y + 11), (bx0 + 19, y + 6)], fill=NAVY)
            d.text((bx0 + 28, y), it, font=F_T, fill=TXT)
        if self.escaped:
            center_text(d, 100, "ESCAPED!", F_B, GREEN, shadow=(0, 0, 0))
        if self.title_confirm:
            draw_box(d, (70, 90, 250, 150))
            center_text(d, 98, "Erase your save?", F_B, TXT)
            for i, c in enumerate(("YES, ERASE", "NO")):
                y = 116 + i * 16
                if i == self.confirm_sel:
                    d.polygon([(100, y + 1), (100, y + 9), (106, y + 5)], fill=NAVY)
                d.text((112, y), c, font=F_B, fill=RED if i == 0 else TXT)
        return im

    def render_ending(self, now):
        t = now - self.end_t0
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        k = min(1.0, t / 6.0)
        for y in range(0, 200, 4):
            top = lerp_col((10, 12, 34), (60, 100, 180), k)
            bot = lerp_col((40, 24, 60), (255, 170, 90), k)
            d.rectangle([0, y, W, y + 3], fill=lerp_col(top, bot, y / 200))
        if k < 0.8:
            r = random.Random(3)
            for _ in range(50):
                d.point((r.randint(0, W), r.randint(0, 130)), fill=(220, 225, 255))
        sy = 170 - k * 40
        d.ellipse([W // 2 - 26, sy - 26, W // 2 + 26, sy + 26], fill=(255, 220, 120))
        d.rectangle([0, 180, W, H], fill=(18, 20, 34))
        d.rectangle([30, 164, 290, 182], fill=(34, 36, 60))
        for wx in range(36, 284, 14):
            d.rectangle([wx, 168, wx + 6, 174], fill=(250, 220, 90))
        for i in range(4):
            ph = (t + i * 0.55) % 2.2
            seed = int((t + i * 0.55) // 2.2) * 10 + i
            rr = random.Random(seed)
            cx, cy, col = rr.randint(40, W - 40), rr.randint(30, 100), rr.choice([YELLOW, GREEN, CYAN, RED, PURPLE, ORANGE])
            if ph < 1.6:
                for a in range(14):
                    ang = a * math.pi * 2 / 14
                    px_, py_ = cx + math.cos(ang) * 38 * ph, cy + math.sin(ang) * 38 * ph + 18 * ph * ph
                    c = lerp_col(col, (10, 10, 20), ph / 1.6)
                    d.ellipse([px_ - 1, py_ - 1, px_ + 1, py_ + 1], fill=c)
        g = char_frames(pal_of("gio"))["right"][0].resize((48, 48), Image.NEAREST)
        j = char_frames(player_pal(self.outfit_idx))["left"][0].resize((48, 48), Image.NEAREST)
        im.paste(g, (110, 126), g)
        im.paste(j, (162, 126), j)
        center_text(d, 14, "YOU ESCAPED!", F_L, YELLOW, shadow=(100, 40, 0))
        center_text(d, 42, "Facility power: 100%", F_B, WHITE, shadow=(0, 0, 0))
        d.text((92, 192), "Stars: %d / %d" % (len(self.done), NQ), font=F_B, fill=YELLOW)
        d.text((92, 206), "Bolts: %d" % self.bolts, font=F_B, fill=YELLOW)
        d.text((8, 222), "Trophies %d/%d" % (len(self.ach), len(ACHIEVEMENTS)), font=F_S, fill=WHITE)
        d.text((190, 192), "Great engineering,", font=F_M, fill=WHITE)
        d.text((190, 206), "Jaslyne & Gio!", font=F_M, fill=WHITE)
        if t > 2.0 and int(now * 2) % 2 == 0:
            center_text(d, 226, "PRESS CENTER", F_S, CYAN)
        return im


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    global AUDIO
    hw_init()
    init_display()
    if SOUND and not SIM:
        AUDIO = Audio(True)
    print("GIO'S CIRCUIT GAME v18.0 running...")
    web_start()
    g = Game()
    last = time.time()
    try:
        while True:
            now = time.time()
            dt, last = min(0.1, now - last), now
            g.update(now, dt)
            if _web.pop("reload", False):   # she played on her phone: pick up her new Bolts/progress
                g = Game()
            frame = g.render(now)
            push_image(frame)
            web_frame(frame)
            # keep reading the buttons until the next frame is due, so even quick taps register
            end = now + 1.0 / FPS
            while True:
                if not SIM:
                    for b in poll():
                        g.on_press(b, time.time())
                for b in web_presses():   # buttons pressed on the phone/laptop page
                    g.on_press(b, time.time())
                if time.time() >= end:
                    break
                time.sleep(POLL_DT)
    except KeyboardInterrupt:
        pass
    finally:
        if g.mode != "title":
            g.save()
        if spi is not None:
            spi.close()
        if h is not None:
            lgpio.gpiochip_close(h)


if __name__ == "__main__":
    main()
