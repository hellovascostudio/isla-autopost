"""Hand-drawn, animated background scenes for Isla Kerrow reels (no stock footage needed).

Each scene is drawn once (static layers) and then animated per frame: slow camera push-in,
rain, flickering lamps, glowing phone screens, handwriting that appears on cue.

In post.json:
    "scenes": [
        {"scene": "hall", "at": 0},              # "at" = index of the excerpt line where the scene starts
        {"scene": "kitchen", "at": 2},
        {"scene": "phone", "at": 4},
        {"scene": "hall", "at": 7, "night": true}
    ]

Scenes:
    hall      floating slate stairs, walnut console, cream telephone with a green screen, night sea
    kitchen   dark kitchen at night, glass of water, a pale reflection in the black window
    phone     close-up of the handset screen: 02:07; rings during an sfx "ring", then "4 MISSED CALLS"
              options: time ("02:07"), missed_at (line index), missed ("4 MISSED CALLS")
    workroom  seamstress' workroom at night: rain on the window, a lamp, a wedding dress on a stand
              option: focus "dress" for a closer, slower shot of the dress
    note      a strip of calico on black velvet under the lamp; pencil lines appear on cue
              options: lines: [{"text": "June 1998", "at": 5}, {"text": "...", "at": 7, "delay": 1.2}]
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from render import FONTS, font

W, H = 1080, 1920
SW, SH = 1188, 2112          # scenes are drawn 10% larger so the camera can move

NAVY = (18, 24, 36)
DEEP = (7, 9, 15)
CREAM = (236, 230, 218)
SLATE = (38, 44, 56)
WARM = (255, 190, 120)
GREEN = (130, 255, 160)
RED = (178, 34, 40)


# ---------- drawing helpers ----------

def vgrad(img, box, top, bottom):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        k = (y - y0) / max(1, y1 - y0 - 1)
        d.line([(x0, y), (x1, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(top, bottom)))


def glow(cx, cy, rx, ry, color, strength=1.0, power=2.0):
    """Additive glow patch: (y0, x0, float array h x w x 3)."""
    x0, x1 = max(0, int(cx - 3 * rx)), min(SW, int(cx + 3 * rx))
    y0, y1 = max(0, int(cy - 3 * ry)), min(SH, int(cy + 3 * ry))
    ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    d = np.sqrt(((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2)
    a = np.exp(-d ** power) * strength
    return (y0, x0, a[..., None] * np.array(color, np.float32)[None, None, :])


def apply_glow(arr, g, k=1.0):
    y0, x0, patch = g
    h, w = patch.shape[:2]
    region = arr[y0:y0 + h, x0:x0 + w].astype(np.float32) + patch * k
    arr[y0:y0 + h, x0:x0 + w] = np.clip(region, 0, 255).astype(np.uint8)


def soft(img, draw_fn, blur, color, alpha=255):
    """Draw a shape into a mask, blur it, paste a colour through it."""
    m = Image.new("L", img.size, 0)
    draw_fn(ImageDraw.Draw(m), alpha)
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    img.paste(Image.new("RGB", img.size, color), (0, 0), m)


def shade(img, box, alpha, blur=60):
    soft(img, lambda d, a: d.rectangle(box, fill=a), blur, (0, 0, 0), alpha)


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


class Scene:
    """Base: a static image plus per-frame additions and a slow camera move."""
    zoom = (1.0, 1.07)              # zoom over the scene's lifetime (1.0 = full drawn canvas)
    focus = (0.5, 0.5)              # where the camera pushes in, as a fraction of the canvas

    def __init__(self, opts, ev, start, end):
        self.opts, self.ev, self.start, self.end = opts, ev, start, end
        self.rng = random.Random(7)
        self.base = np.array(self.draw(), np.uint8)
        self.setup()

    def draw(self):
        return Image.new("RGB", (SW, SH), NAVY)

    def setup(self):
        pass

    def animate(self, arr, t, k):   # numpy stage (glows)
        pass

    def overlay(self, img, t, k):   # PIL stage (rain, text)
        pass

    def frame(self, t):
        k = (t - self.start) / max(0.01, self.end - self.start)
        arr = self.base.copy()
        self.animate(arr, t, k)
        img = Image.fromarray(arr)
        self.overlay(img, t, k)
        z0, z1 = self.zoom
        z = z0 + (z1 - z0) * ease(k * 0.9 + 0.05)
        # visible window: at z=1 the window is W x H scaled up to fill SW (=1.1x); zoom tightens it
        vw, vh = SW / z, SH / z
        fx, fy = self.focus
        cx = SW / 2 + (fx - 0.5) * (SW - vw)
        cy = SH / 2 + (fy - 0.5) * (SH - vh)
        box = (cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2)
        return img.resize((W, H), Image.BILINEAR, box=box)

    def line_t(self, i):
        lines = self.ev["lines"]
        return lines[min(i, len(lines) - 1)]


# ---------- Answer the Landline ----------

def draw_phone(img, x, y, s=1.0):
    """Cream cordless phone dressed up as an old one, on its base. (x, y) = bottom centre."""
    d = ImageDraw.Draw(img)
    bw, bh = 150 * s, 70 * s
    soft(img, lambda dd, a: dd.ellipse([x - bw * 0.7, y - 18 * s, x + bw * 0.7, y + 18 * s], fill=a), 14,
         (0, 0, 0), 170)
    d.rounded_rectangle([x - bw / 2, y - bh, x + bw / 2, y], radius=26 * s, fill=(214, 204, 184))
    d.rounded_rectangle([x - bw / 2 + 6 * s, y - bh + 4 * s, x + bw / 2 - 6 * s, y - bh + 20 * s],
                        radius=10 * s, fill=(236, 228, 210))
    # handset lying across the top
    d.rounded_rectangle([x - bw * 0.62, y - bh - 34 * s, x + bw * 0.62, y - bh + 4 * s], radius=19 * s,
                        fill=(226, 216, 196))
    d.rounded_rectangle([x - bw * 0.66, y - bh - 40 * s, x - bw * 0.40, y - bh + 6 * s], radius=12 * s,
                        fill=(220, 210, 190))
    d.rounded_rectangle([x + bw * 0.40, y - bh - 40 * s, x + bw * 0.66, y - bh + 6 * s], radius=12 * s,
                        fill=(220, 210, 190))
    d.line([(x - bw * 0.62, y - bh - 36 * s), (x + bw * 0.62, y - bh - 36 * s)], fill=(240, 234, 220),
           width=max(2, int(3 * s)))
    # little green screen
    sx0, sy0, sx1, sy1 = x - 30 * s, y - bh - 26 * s, x + 30 * s, y - bh - 8 * s
    d.rectangle([sx0, sy0, sx1, sy1], fill=(70, 160, 95))
    return ((sx0 + sx1) / 2, (sy0 + sy1) / 2)


class Hall(Scene):
    zoom = (1.0, 1.12)
    focus = (0.40, 0.52)

    def draw(self):
        night = self.opts.get("night")
        img = Image.new("RGB", (SW, SH), NAVY)
        vgrad(img, (0, 0, SW, 1240), (16, 21, 32), (24, 30, 42))
        vgrad(img, (0, 1240, SW, SH), (20, 24, 32), (6, 8, 12))
        d = ImageDraw.Draw(img)
        # big window onto the night sea (no curtains)
        self.win = wx0, wy0, wx1, wy1 = 70, 230, 640, 1060
        vgrad(img, (wx0, wy0, wx1, 600), (14, 22, 38), (30, 44, 66))
        vgrad(img, (wx0, 600, wx1, wy1), (20, 30, 46), (8, 12, 20))
        self.horizon = 600
        soft(img, lambda dd, a: dd.ellipse([430, 330, 530, 430], fill=a), 3, (220, 222, 210), 230)
        soft(img, lambda dd, a: dd.ellipse([330, 230, 630, 530], fill=a), 70, (90, 110, 140), 90)
        d.rectangle([wx0 - 14, wy0 - 14, wx1 + 14, wy1 + 14], outline=(10, 12, 18), width=14)
        d.line([((wx0 + wx1) // 2, wy0), ((wx0 + wx1) // 2, wy1)], fill=(10, 12, 18), width=8)
        # floating slate stairs, fixed to the right wall, no handrail
        d.rectangle([1150, 0, SW, SH], fill=(14, 18, 26))                       # the wall the treads hang on
        for i in range(11):
            tx = 1150
            ty = 1240 - i * 104
            tw = 330 - i * 14
            soft(img, lambda dd, a, tx=tx, ty=ty, tw=tw: dd.rectangle([tx - tw, ty + 4, tx, ty + 44], fill=a), 18,
                 (0, 0, 0), 130)
            d.rectangle([tx - tw, ty - 30, tx, ty], fill=(46, 52, 64))
            d.rectangle([tx - tw, ty - 30, tx, ty - 25], fill=(76, 84, 98))
        # walnut console at the foot of the stairs
        cx0, cx1, cy = 300, 760, 1150
        soft(img, lambda dd, a: dd.ellipse([cx0 - 60, 1500, cx1 + 60, 1600], fill=a), 30, (0, 0, 0), 160)
        d.rectangle([cx0, cy, cx1, cy + 34], fill=(78, 50, 32))
        d.rectangle([cx0, cy, cx1, cy + 6], fill=(108, 72, 46))
        for lx in (cx0 + 30, cx1 - 50):
            d.rectangle([lx, cy + 34, lx + 20, 1560], fill=(60, 38, 24))
        d.rectangle([cx0 + 30, cy + 34, cx1 - 30, cy + 70], fill=(66, 42, 27))
        self.screen = draw_phone(img, 530, cy, 1.25)
        # floor reflection
        soft(img, lambda dd, a: dd.rectangle([0, 1600, SW, SH], fill=a), 80, (0, 0, 0), 120)
        if night:
            shade(img, (0, 0, SW, SH), 70, 0)
        return img

    def setup(self):
        sx, sy = self.screen
        self.g_screen = glow(sx, sy, 60, 40, GREEN, 0.55, 1.4)
        self.g_wide = glow(sx, sy + 60, 260, 200, (60, 140, 90), 0.20, 1.2)
        self.g_moon = glow(480, 380, 220, 220, (120, 140, 170), 0.20, 1.2)

    def animate(self, arr, t, k):
        night = 1.4 if self.opts.get("night") else 1.0
        apply_glow(arr, self.g_moon)
        apply_glow(arr, self.g_wide, night * (0.9 + 0.1 * math.sin(t * 1.3)))
        apply_glow(arr, self.g_screen, night * (0.95 + 0.05 * math.sin(t * 2.1)))

    def overlay(self, img, t, k):
        # moonlight glinting on the moving sea
        d = ImageDraw.Draw(img)
        wx0, wy0, wx1, wy1 = self.win
        rng = random.Random(3)
        for i in range(90):
            y = self.horizon + 10 + (rng.random() ** 1.6) * (wy1 - self.horizon - 20)
            depth = (y - self.horizon) / (wy1 - self.horizon)
            x = 480 + (rng.random() - 0.5) * (120 + 520 * depth) + math.sin(t * 0.9 + i) * 14 * depth
            ln = 8 + 40 * depth * rng.random()
            a = int(60 + 120 * (1 - depth) * (0.5 + 0.5 * math.sin(t * 2 + i * 1.7)))
            if wx0 < x < wx1 - ln:
                d.line([(x, y), (x + ln, y)], fill=(a, a + 6, a + 16), width=2)


class Kitchen(Scene):
    zoom = (1.02, 1.10)
    focus = (0.55, 0.48)

    def draw(self):
        img = Image.new("RGB", (SW, SH), DEEP)
        vgrad(img, (0, 0, SW, SH), (10, 13, 20), (4, 5, 9))
        d = ImageDraw.Draw(img)
        # wall of black glass
        for x in (60, 420, 780):
            d.rectangle([x, 160, x + 340, 1180], fill=(9, 12, 19), outline=(20, 24, 32), width=6)
        # reflection of the room: a tall pale shape, and another further off
        soft(img, lambda dd, a: (dd.ellipse([640, 440, 720, 530], fill=a),
                                 dd.rounded_rectangle([600, 520, 760, 1060], radius=60, fill=a)), 26,
             (150, 158, 170), 70)
        soft(img, lambda dd, a: (dd.ellipse([220, 560, 262, 606], fill=a),
                                 dd.rounded_rectangle([200, 600, 282, 860], radius=34, fill=a)), 20,
             (120, 128, 140), 34)
        # kitchen island (marble) in the foreground
        d.rectangle([0, 1250, SW, 1330], fill=(58, 60, 66))
        d.rectangle([0, 1250, SW, 1258], fill=(98, 100, 106))
        d.rectangle([0, 1330, SW, SH], fill=(12, 14, 18))
        for i in range(14):
            x = self.rng.randint(0, SW)
            d.line([(x, 1258), (x + self.rng.randint(80, 260), 1330)], fill=(74, 76, 82), width=1)
        # glass of water
        gx, gy = 640, 1250
        d.polygon([(gx - 46, gy - 190), (gx + 46, gy - 190), (gx + 38, gy), (gx - 38, gy)], fill=(40, 48, 60))
        d.polygon([(gx - 42, gy - 120), (gx + 42, gy - 120), (gx + 37, gy - 4), (gx - 37, gy - 4)],
                  fill=(58, 72, 92))
        d.line([(gx - 46, gy - 190), (gx - 38, gy)], fill=(150, 165, 185), width=3)
        d.line([(gx + 30, gy - 180), (gx + 26, gy - 20)], fill=(110, 125, 145), width=2)
        d.ellipse([gx - 46, gy - 198, gx + 46, gy - 182], outline=(130, 145, 165), width=2)
        return img

    def setup(self):
        self.g_far = glow(150, 1120, 22, 16, GREEN, 0.9, 1.4)     # the handset, far off in the hall
        self.g_far2 = glow(150, 1120, 120, 90, (40, 110, 70), 0.25, 1.2)
        self.g_glass = glow(640, 1150, 160, 140, (80, 100, 130), 0.18, 1.3)

    def animate(self, arr, t, k):
        apply_glow(arr, self.g_far2)
        apply_glow(arr, self.g_far, 0.9 + 0.1 * math.sin(t * 2))
        apply_glow(arr, self.g_glass)


class Phone(Scene):
    zoom = (1.0, 1.06)
    focus = (0.5, 0.42)

    def draw(self):
        img = Image.new("RGB", (SW, SH), DEEP)
        vgrad(img, (0, 0, SW, SH), (8, 10, 16), (3, 4, 7))
        d = ImageDraw.Draw(img)
        # the handset, very close: a cream body with a dark screen bezel
        self.bx0, self.by0, self.bx1, self.by1 = 214, 260, 974, 1260
        soft(img, lambda dd, a: dd.rounded_rectangle([self.bx0 + 30, self.by0 + 50, self.bx1 + 40, self.by1 + 70],
                                                     radius=120, fill=a), 50, (0, 0, 0), 220)
        d.rounded_rectangle([self.bx0, self.by0, self.bx1, self.by1], radius=120, fill=(196, 186, 166))
        soft(img, lambda dd, a: dd.rounded_rectangle([self.bx0 + 40, self.by0 + 20, self.bx1 - 120,
                                                      self.by0 + 220], radius=90, fill=a), 40, (240, 234, 220), 120)
        self.scr = (self.bx0 + 110, self.by0 + 250, self.bx1 - 110, self.by0 + 610)
        d.rounded_rectangle([self.scr[0] - 18, self.scr[1] - 18, self.scr[2] + 18, self.scr[3] + 18],
                            radius=30, fill=(44, 42, 40))
        d.rectangle(self.scr, fill=(30, 60, 40))
        # keypad
        for r in range(3):
            for c in range(3):
                kx = self.bx0 + 190 + c * 150
                ky = self.by0 + 700 + r * 120
                d.rounded_rectangle([kx, ky, kx + 100, ky + 64], radius=26, fill=(214, 204, 184))
        shade(img, (0, self.by1 - 200, SW, SH), 150, 80)
        return img

    def setup(self):
        x0, y0, x1, y1 = self.scr
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.g_scr = glow(cx, cy, (x1 - x0) * 0.42, (y1 - y0) * 0.42, GREEN, 0.40, 3.0)
        self.g_room = glow(cx, cy, 520, 520, (50, 130, 80), 0.22, 1.2)
        self.f_big = font("display", 150)
        self.f_small = font("sans_bold", 46)
        self.rings = self.ev.get("sfx", [])
        self.missed_t = self.line_t(self.opts["missed_at"]) if "missed_at" in self.opts else None

    def ringing(self, t):
        for st, d in self.rings:
            if st <= t <= st + d:
                ph = (t - st) % 2.2
                return 1.0 if (ph < 0.4 or 0.6 <= ph < 1.0) else 0.25
        return 0.0

    def animate(self, arr, t, k):
        r = self.ringing(t)
        apply_glow(arr, self.g_room, 0.6 + 1.2 * r)
        apply_glow(arr, self.g_scr, 0.8 + 0.9 * r)

    def overlay(self, img, t, k):
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = self.scr
        lcd = (20, 40, 26)
        missed = self.missed_t is not None and t >= self.missed_t
        r = self.ringing(t)
        top = "CALLING..." if r else ("4 MISSED CALLS" if missed else "")
        top = self.opts.get("missed", top) if (missed and not r) else top
        if top:
            tw = d.textlength(top, font=self.f_small)
            d.text(((x0 + x1 - tw) / 2, y0 + 40), top, font=self.f_small, fill=lcd)
        tm = self.opts.get("time", "02:07")
        tw = d.textlength(tm, font=self.f_big)
        d.text(((x0 + x1 - tw) / 2, y0 + 120), tm, font=self.f_big, fill=lcd)
        if r:  # tiny vibration while it rings
            pass

    def frame(self, t):
        img = super().frame(t)
        r = self.ringing(t)
        if r >= 1.0:
            dx = int(3 * math.sin(t * 90))
            img = img.transform(img.size, Image.AFFINE, (1, 0, dx, 0, 1, 0))
        return img


# ---------- Under the Lining ----------

class Workroom(Scene):
    zoom = (1.0, 1.10)
    focus = (0.5, 0.45)

    def __init__(self, opts, ev, start, end):
        if opts.get("focus") == "dress":
            self.zoom, self.focus = (1.25, 1.36), (0.78, 0.45)
        super().__init__(opts, ev, start, end)

    def draw(self):
        img = Image.new("RGB", (SW, SH), NAVY)
        vgrad(img, (0, 0, SW, SH), (20, 25, 36), (8, 10, 15))
        d = ImageDraw.Draw(img)
        # sash window onto a Bath street at night: Georgian terrace across the road
        self.win = wx0, wy0, wx1, wy1 = 120, 200, 700, 1010
        vgrad(img, (wx0, wy0, wx1, wy1), (16, 22, 36), (28, 34, 46))
        d.rectangle([wx0, 560, wx1, wy1], fill=(34, 34, 38))                     # terrace facade
        for row in range(3):
            for col in range(5):
                x = wx0 + 30 + col * 112
                y = 600 + row * 130
                lit = self.rng.random() < 0.25
                d.rectangle([x, y, x + 56, y + 90], fill=(120, 96, 60) if lit else (22, 22, 26))
        d.rectangle([wx0, 545, wx1, 560], fill=(46, 46, 50))                     # cornice
        soft(img, lambda dd, a: dd.ellipse([520, 880, 640, 1000], fill=a), 30, (255, 200, 130), 150)  # streetlamp
        d.rectangle([wx0 - 16, wy0 - 16, wx1 + 16, wy1 + 16], outline=(12, 14, 20), width=16)
        d.line([(wx0, (wy0 + wy1) // 2), (wx1, (wy0 + wy1) // 2)], fill=(12, 14, 20), width=12)
        d.line([((wx0 + wx1) // 2, wy0), ((wx0 + wx1) // 2, wy1)], fill=(12, 14, 20), width=6)
        # cutting table under the lamp
        d.rectangle([0, 1240, 760, 1290], fill=(70, 56, 44))
        d.rectangle([0, 1290, 760, SH], fill=(14, 14, 18))
        # anglepoise lamp
        d.line([(60, 1240), (150, 1020), (330, 960)], fill=(30, 32, 38), width=14)
        d.polygon([(300, 930), (420, 960), (380, 1040), (290, 1000)], fill=(36, 38, 44))
        # lamp light pool on the table
        soft(img, lambda dd, a: dd.polygon([(370, 1020), (180, 1240), (720, 1240), (480, 1020)], fill=a), 40,
             (255, 214, 160), 70)
        # silk on the table, seam ripper, a little pale heap of threads
        d.polygon([(250, 1236), (330, 1200), (640, 1210), (700, 1236)], fill=(214, 206, 190))
        d.line([(470, 1222), (560, 1214)], fill=(140, 140, 150), width=4)
        d.ellipse([556, 1208, 570, 1220], fill=RED)
        # dress form with the wedding dress, open at the side
        fx = 930
        d.rectangle([fx - 6, 760, fx + 6, 1700], fill=(30, 26, 22))
        d.polygon([(fx - 150, 1700), (fx + 150, 1700), (fx + 30, 1660), (fx - 30, 1660)], fill=(30, 26, 22))
        dress = Image.new("L", (SW, SH), 0)
        dd = ImageDraw.Draw(dress)
        dd.ellipse([fx - 74, 520, fx + 74, 600], fill=255)                       # shoulders
        dd.polygon([(fx - 88, 560), (fx + 88, 560), (fx + 52, 800), (fx - 52, 800)], fill=255)    # bodice
        dd.polygon([(fx - 52, 790), (fx + 52, 790), (fx + 200, 1520), (fx - 200, 1520)], fill=255)  # skirt
        dd.ellipse([fx - 200, 1480, fx + 200, 1560], fill=255)
        dress = dress.filter(ImageFilter.GaussianBlur(2))
        # ivory, lit from the lamp on the left, falling into shadow on the right
        xs = np.linspace(0, 1, SW, dtype=np.float32)[None, :]
        lx = np.clip((xs * SW - (fx - 200)) / 400, 0, 1)
        ys = np.linspace(0, 1, SH, dtype=np.float32)[:, None]
        lum = (1.0 - 0.62 * lx) * (1.0 - 0.25 * ys)
        col = np.stack([196 * lum, 188 * lum, 172 * lum], -1).clip(0, 255).astype(np.uint8)
        img.paste(Image.fromarray(col), (0, 0), dress)
        for i in range(6):                                                         # folds
            x = fx - 150 + i * 60
            soft(img, lambda dd, a, x=x, i=i: dd.line([(fx - 36 + i * 14, 820), (x, 1520)], fill=a, width=8), 9,
                 (70, 68, 66), 110)
        soft(img, lambda dd, a: dd.polygon([(fx - 88, 570), (fx - 66, 576), (fx - 54, 800), (fx - 70, 796)],
                                           fill=a), 3, (40, 38, 36), 220)          # the opened side seam
        # shade the right edge so the dress sits in half-light
        shade(img, (fx + 120, 0, SW, SH), 120, 70)
        return img

    def setup(self):
        self.g_lamp = glow(380, 1080, 300, 220, WARM, 0.30, 1.4)
        self.g_bulb = glow(370, 1000, 60, 40, (255, 230, 190), 0.6, 1.6)
        self.g_street = glow(580, 940, 160, 160, WARM, 0.18, 1.3)
        rng = random.Random(11)
        wx0, wy0, wx1, wy1 = self.win
        self.drops = [(rng.uniform(wx0, wx1), rng.uniform(wy0, wy1), rng.uniform(60, 160), rng.uniform(10, 40))
                      for _ in range(70)]

    def animate(self, arr, t, k):
        flick = 1.0 + 0.04 * math.sin(t * 7.3) + 0.03 * math.sin(t * 13.1)
        apply_glow(arr, self.g_street)
        apply_glow(arr, self.g_lamp, flick)
        apply_glow(arr, self.g_bulb, flick)

    def overlay(self, img, t, k):
        d = ImageDraw.Draw(img)
        wx0, wy0, wx1, wy1 = self.win
        for x, y, speed, ln in self.drops:
            yy = wy0 + (y - wy0 + t * speed) % (wy1 - wy0)
            if yy + ln < wy1:
                d.line([(x, yy), (x + 2, yy + ln)], fill=(70, 82, 100), width=2)


class Note(Scene):
    zoom = (1.0, 1.14)
    focus = (0.5, 0.40)

    def draw(self):
        img = Image.new("RGB", (SW, SH), (6, 6, 9))
        # black velvet: fine noise
        rng = np.random.default_rng(5)
        v = (rng.normal(10, 3, (SH, SW))).clip(0, 30).astype(np.uint8)
        img = Image.fromarray(np.stack([v, v, v + 2], -1))
        d = ImageDraw.Draw(img)
        # steel rule
        d.rectangle([90, 1060, 1110, 1120], fill=(120, 124, 130))
        d.rectangle([90, 1060, 1110, 1066], fill=(170, 174, 180))
        for i in range(0, 1020, 20):
            h = 30 if i % 100 == 0 else 16
            d.line([(90 + i, 1066), (90 + i, 1066 + h)], fill=(50, 52, 56), width=2)
        # the strip of calico, with a selvedge and its single red thread
        strip = Image.new("RGBA", (1000, 260), (0, 0, 0, 0))
        sd = ImageDraw.Draw(strip)
        sd.rectangle([0, 0, 1000, 260], fill=(222, 210, 186, 255))
        nz = (np.random.default_rng(9).normal(0, 7, (260, 1000))).astype(np.int16)
        arr = np.array(strip).astype(np.int16)
        arr[..., :3] = (arr[..., :3] + nz[..., None]).clip(0, 255)
        strip = Image.fromarray(arr.astype(np.uint8), "RGBA")
        sd = ImageDraw.Draw(strip)
        sd.rectangle([0, 0, 1000, 16], fill=(206, 194, 170, 255))
        sd.line([(0, 9), (1000, 9)], fill=RED + (255,), width=3)
        for x in range(0, 1000, 7):                                          # frayed cut ends
            sd.line([(x, 250 + (x * 7) % 10), (x, 260)], fill=(0, 0, 0, 0), width=4)
        for y in range(0, 260, 6):
            sd.line([(0, y), ((y * 13) % 14, y)], fill=(0, 0, 0, 0), width=3)
            sd.line([(1000 - (y * 11) % 16, y), (1000, y)], fill=(0, 0, 0, 0), width=3)
        self.strip_pos = (94, 640)
        shadow = Image.new("L", (SW, SH), 0)
        ImageDraw.Draw(shadow).rectangle([110, 668, 1110, 928], fill=200)
        img.paste(Image.new("RGB", (SW, SH), (0, 0, 0)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(22)))
        img.paste(strip, self.strip_pos, strip)
        return img

    def setup(self):
        self.g_lamp = glow(600, 760, 560, 380, WARM, 0.16, 1.5)
        self.hand = ImageFont.truetype(str(FONTS / "ReenieBeanie.ttf"), 92)
        self.texts = [(ln["text"], self.line_t(ln["at"]) + ln.get("delay", 0)) for ln in self.opts.get("lines", [])]

    def animate(self, arr, t, k):
        apply_glow(arr, self.g_lamp, 1.0 + 0.03 * math.sin(t * 5.1))

    def overlay(self, img, t, k):
        sx, sy = self.strip_pos
        y = sy + 34
        for i, (text, at) in enumerate(self.texts):
            if t < at:
                break
            reveal = min(1.0, (t - at) / max(0.8, 0.075 * len(text)))      # written left to right
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            size = 92
            fnt = ImageFont.truetype(str(FONTS / "ReenieBeanie.ttf"), size)
            while ImageDraw.Draw(img).textlength(text, font=fnt) > 880 and size > 40:
                size -= 4
                fnt = ImageFont.truetype(str(FONTS / "ReenieBeanie.ttf"), size)
            x = sx + 50
            ld.text((x, y), text, font=fnt, fill=(78, 78, 84, 235))
            tw = ld.textlength(text, font=fnt)
            mask = Image.new("L", img.size, 0)
            ImageDraw.Draw(mask).rectangle([0, 0, x + tw * reveal, SH], fill=255)
            layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", img.size, 0), mask))
            img.paste(layer, (0, 0), layer)
            y += 100 if i == 0 else 90


SCENES = {"hall": Hall, "kitchen": Kitchen, "phone": Phone, "workroom": Workroom, "note": Note}


def build(specs, ev, total):
    """Return a frame(t) function for the whole reel, cross-fading between scenes."""
    starts = [0.0 if i == 0 else max(0.0, ev["lines"][s["at"]] - 0.3) for i, s in enumerate(specs)]
    ends = starts[1:] + [total]
    scenes = [SCENES[s["scene"]]({k: v for k, v in s.items() if k not in ("scene", "at")}, ev, a, b)
              for s, a, b in zip(specs, starts, ends)]
    XF = 0.8

    def frame(t):
        i = max(j for j, a in enumerate(starts) if a <= t)
        img = scenes[i].frame(t)
        if i > 0 and t < starts[i] + XF:
            prev = scenes[i - 1].frame(t)
            img = Image.blend(prev, img, ease((t - starts[i]) / XF))
        return img
    return frame
