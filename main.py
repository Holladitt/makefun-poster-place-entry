"""AURELIS — The Aurora Fjord. make.fun entry: The Poster for a Place
That Isn't There.

Draws one travel poster (768x1024) to /output/entry.png. Stdlib only
(Python 3.13, no network, no external assets): a small software
rasterizer, a DejaVu glyph atlas read from fonts.bin beside this
file, and a hand-rolled PNG writer. Deterministic: same bytes every
run (seeded randomness only).

Concept: AURELIS, a night fjord where the aurora burns green over
still water. One impossible landmark — a lighthouse on a rock islet
whose beam sweeps the aurora-lit fjord, under a sky full of aurora
curtains. The mountains are organic noise ridgelines with snow
catching the green light; the water mirrors the aurora in broken
shimmer; mist drifts in soft puffs. Palette: deep indigo-teal night,
emerald aurora, warm gold lamplight. The name is set big in DejaVu
Serif Bold across the sky, one short subtitle beneath it, nothing
else.

v4 (v1 LUMARA and v2/v3 KAVIRA were all held by the owner as too
flat/procedural): a NEW place and a genuinely painterly style —
no hard geometry, no flat horizontal bands, no concentric arcs, no
line ladders. Organic value-noise shapes, soft multi-stop gradients,
heavy full-frame grain, layered atmospheric mist, light that spreads
(aurora glow, lighthouse beam, lantern glows) instead of hard discs.

v5 (v4 AURELIS was held: the aurora was the best thing yet, but
the lighthouse was too small and the lower water too empty): same
place, top-3 formula — the lighthouse is now the dominant 50%+
frame hero (2.5-3x bigger, tall tower up into the aurora, strong
beam both ways), the water is full (wide gold + green reflection
columns under the tower, five lantern boats, more mist, a textured
near shore), the far ridge is deeper and hazier, the foreground
rocks are lighter and faceted. The aurora itself is untouched.
"""

import math
import os
import random
import struct
import zlib

W, H = 768, 1024
MASTER = 80  # glyph atlas em size in px (see gen_atlas.py)
SEED = 20261121

# ---------------------------------------------------------------- palette
SKY_TOP = (8, 12, 36)
SKY_2 = (16, 30, 58)
SKY_3 = (26, 54, 78)
SKY_HORIZON = (46, 88, 92)
AUR1 = (110, 235, 170)   # emerald aurora
AUR2 = (70, 210, 195)    # teal-green aurora
AUR3 = (190, 230, 140)   # pale gold-green aurora edge
AUR_WASH = (56, 108, 94)
MTN_FAR = (58, 92, 104)
MTN_FAR_LT = (96, 128, 132)
MTN_L = (20, 34, 56)
MTN_R = (26, 44, 66)
SNOW = (198, 224, 208)
SNOW_SH = (140, 168, 164)
WATER_TOP = (24, 66, 76)
WATER_MID = (16, 48, 60)
WATER_BOT = (9, 26, 42)
GOLD = (240, 185, 95)
GOLD_LT = (255, 220, 150)
BEAM = (255, 228, 165)
CREAM = (246, 236, 214)
ROCK_FG = (10, 16, 28)
PINE = (12, 24, 38)
MIST = (176, 208, 202)
LIGHT_TOWER = (14, 20, 34)


def mix(a, b, t):
    """Linear blend of two RGB colours; t=0 -> a, t=1 -> b."""
    return tuple(int(a[c] + (b[c] - a[c]) * t) for c in range(3))


# ------------------------------------------------------------- value noise
def _hash2(ix, iy, seed):
    h = (ix * 374761393 + iy * 668265263 + seed * 974634211) & 0xFFFFFFFF
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFFFFFF) / 4294967295.0


def _sm(t):
    return t * t * (3 - 2 * t)


def vnoise(x, y, seed):
    """Smooth value noise in [0, 1]; deterministic for fixed seed."""
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy
    a = _hash2(ix, iy, seed)
    b = _hash2(ix + 1, iy, seed)
    c = _hash2(ix, iy + 1, seed)
    d = _hash2(ix + 1, iy + 1, seed)
    u = _sm(fx)
    v = _sm(fy)
    return a + (b - a) * u + (c + (d - c) * u - (a + (b - a) * u)) * v


def fbm(x, y, seed, octaves=3):
    """Fractal Brownian motion over vnoise, in [0, 1]."""
    tot = 0.0
    amp = 1.0
    fr = 1.0
    norm = 0.0
    for _ in range(octaves):
        tot += vnoise(x * fr, y * fr, seed) * amp
        norm += amp
        amp *= 0.5
        fr *= 2.03
    return tot / norm


# ---------------------------------------------------------------- canvas
class Canvas:
    """RGB pixel buffer with small drawing primitives."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.pix = bytearray(w * h * 3)
        self.rect(0, 0, w - 1, h - 1, fill=bg)

    def _set(self, x, y, col):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.pix[i], self.pix[i + 1], self.pix[i + 2] = col

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            return (self.pix[i], self.pix[i + 1], self.pix[i + 2])
        return (0, 0, 0)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        if fill is not None:
            cx0, cy0 = max(x0, 0), max(y0, 0)
            cx1, cy1 = min(x1, self.w - 1), min(y1, self.h - 1)
            for y in range(cy0, cy1 + 1):
                base = (y * self.w + cx0) * 3
                row = bytes(fill) * (cx1 - cx0 + 1)
                self.pix[base:base + len(row)] = row
        if outline is not None:
            for t in range(width):
                self.rect(x0 + t, y0 + t, x1 - t, y0 + t, fill=outline)
                self.rect(x0 + t, y1 - t, x1 - t, y1 - t, fill=outline)
                self.rect(x0 + t, y0 + t, x0 + t, y1 - t, fill=outline)
                self.rect(x1 - t, y0 + t, x1 - t, y1 - t, fill=outline)

    def _disc(self, cx, cy, r, col):
        r = int(r)
        for y in range(cy - r, cy + r + 1):
            if abs(y - cy) > r:
                continue
            dx = int((r * r - (y - cy) ** 2) ** 0.5)
            self.rect(cx - dx, y, cx + dx, y, fill=col)

    def disc(self, cx, cy, r, col):
        self._disc(int(cx), int(cy), int(r), col)

    def line(self, x0, y0, x1, y1, col, width=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err, x, y = dx - dy, x0, y0
        r = max(width // 2, 0)
        while True:
            if r:
                self._disc(x, y, r, col)
            else:
                self._set(x, y, col)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def polyline(self, pts, col, width=1):
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                      col, width)

    def polygon(self, pts, fill=None, outline=None):
        pts = [(int(x), int(y)) for x, y in pts]
        if fill is not None:
            ys = [p[1] for p in pts]
            for y in range(max(min(ys), 0), min(max(ys), self.h - 1) + 1):
                xs = []
                n = len(pts)
                for i in range(n):
                    x0, y0 = pts[i]
                    x1, y1 = pts[(i + 1) % n]
                    if (y0 <= y < y1) or (y1 <= y < y0):
                        xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
                xs.sort()
                for i in range(0, len(xs) - 1, 2):
                    self.rect(int(math.ceil(xs[i])), y,
                              int(math.floor(xs[i + 1])), y, fill=fill)
        if outline is not None:
            self.polyline(pts + [pts[0]], outline, 1)

    def ellipse(self, x0, y0, x1, y1, fill=None, outline=None, width=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        if rx <= 0 or ry <= 0:
            return
        if outline is not None and fill is not None:
            self.ellipse(x0, y0, x1, y1, fill=outline)
            self.ellipse(x0 + width, y0 + width, x1 - width, y1 - width,
                         fill=fill)
            return
        col = fill if fill is not None else outline
        for y in range(max(y0, 0), min(y1, self.h - 1) + 1):
            t = 1 - ((y - cy) / ry) ** 2
            if t < 0:
                continue
            dx = int(rx * t ** 0.5)
            self.rect(int(cx - dx), y, int(cx + dx), y, fill=col)

    def gradient(self, x, y, w, h, top, bottom):
        for i in range(int(h)):
            t = i / max(int(h) - 1, 1)
            col = tuple(int(top[c] + (bottom[c] - top[c]) * t)
                         for c in range(3))
            self.rect(x, y + i, x + w, y + i, fill=col)

    def vgrad(self, x, y, w, h, stops):
        """Vertical multi-stop gradient; stops = [(t, color), ...]."""
        for i in range(int(h)):
            t = i / max(int(h) - 1, 1)
            col = stops[-1][1]
            for j in range(len(stops) - 1):
                t0, c0 = stops[j]
                t1, c1 = stops[j + 1]
                if t0 <= t <= t1:
                    f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                    col = mix(c0, c1, f)
                    break
            self.rect(x, y + i, x + w, y + i, fill=col)


# ------------------------------------------------------------------- png
def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.pix[y * stride:(y + 1) * stride]

    def chunk(tag, payload):
        c = struct.pack(">I", len(payload)) + tag + payload
        return c + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", ihdr)
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    data += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)


# ------------------------------------------------------------------ fonts
def load_fonts(path):
    """Read fonts.bin into {name: {ord: glyph}}."""
    data = open(path, "rb").read()
    assert data[:4] == b"FNT1", "bad fonts.bin"
    off = 4
    (n_fonts,) = struct.unpack_from("<I", data, off)
    off += 4
    fonts = {}
    for _ in range(n_fonts):
        (nl,) = struct.unpack_from("<B", data, off)
        off += 1
        name = data[off:off + nl].decode()
        off += nl
        (n_chars,) = struct.unpack_from("<I", data, off)
        off += 4
        glyphs = {}
        for _ in range(n_chars):
            code, adv, w, h, _pad, ox, oy = struct.unpack_from(
                "<IHHHHhh", data, off)
            off += 16
            bmp = data[off:off + w * h]
            off += w * h
            glyphs[code] = (adv, w, h, ox, oy, bmp)
        fonts[name] = glyphs
    return fonts


_FONTS = None
_SCALED = {}


def init_fonts(path):
    global _FONTS
    _FONTS = load_fonts(path)
    _SCALED.clear()


def _scaled_glyph(font_name, size, code):
    key = (font_name, size, code)
    hit = _SCALED.get(key)
    if hit is not None:
        return hit
    adv, w, h, ox, oy, bmp = _FONTS[font_name][code]
    s = size / MASTER
    if w == 0 or h == 0:
        out = (round(adv * s), 0, 0, 0, 0, [])
        _SCALED[key] = out
        return out
    sw, sh = max(1, round(w * s)), max(1, round(h * s))
    pts = []
    for sy in range(sh):
        y0, y1 = sy / s, (sy + 1) / s
        sy0, sy1 = int(y0), min(h, int(y1) + 1)
        for sx in range(sw):
            x0, x1 = sx / s, (sx + 1) / s
            sx0, sx1 = int(x0), min(w, int(x1) + 1)
            total, area = 0.0, 0.0
            for yy in range(sy0, sy1):
                wy = min(y1, yy + 1) - max(y0, yy)
                if wy <= 0:
                    continue
                row = yy * w
                for xx in range(sx0, sx1):
                    wx = min(x1, xx + 1) - max(x0, xx)
                    if wx <= 0:
                        continue
                    total += bmp[row + xx] * wx * wy
                    area += wx * wy
            cov = int(total / area) if area else 0
            if cov >= 8:
                pts.append((sx, sy, cov))
    out = (round(adv * s), round(ox * s), round(oy * s), sw, sh, pts)
    _SCALED[key] = out
    return out


def text_width(font_name, size, text):
    total = 0.0
    for ch in text:
        g = _FONTS[font_name].get(ord(ch))
        if g is None:
            continue
        total += g[0] * size / MASTER
    return total


def _draw_glyph_pts(cv, bx, by, pts, col):
    for dx, dy, cov in pts:
        xx, yy = bx + dx, by + dy
        if 0 <= xx < cv.w and 0 <= yy < cv.h:
            i = (yy * cv.w + xx) * 3
            if cov == 255:
                cv.pix[i], cv.pix[i + 1], cv.pix[i + 2] = col
            else:
                cv.pix[i] = (col[0] * cov + cv.pix[i] * (255 - cov)) // 255
                cv.pix[i + 1] = (col[1] * cov + cv.pix[i + 1] * (255 - cov)) // 255
                cv.pix[i + 2] = (col[2] * cov + cv.pix[i + 2] * (255 - cov)) // 255


def draw_text(cv, font_name, size, x, y, text, col):
    """Draw text; (x, y) is the top-left of the ascender box."""
    px = float(x)
    for ch in text:
        code = ord(ch)
        if code not in _FONTS[font_name]:
            px += size * 0.25
            continue
        adv, ox, oy, _sw, _sh, pts = _scaled_glyph(font_name, size, code)
        _draw_glyph_pts(cv, int(px) + ox, int(y) + oy, pts, col)
        px += adv
    return px


def draw_centered(cv, font_name, size, cx, y, text, col):
    w = text_width(font_name, size, text)
    draw_text(cv, font_name, size, cx - w / 2, y, text, col)


def draw_tracked(cv, font_name, size, x, y, text, col, pitch):
    """Draw with a fixed advance per character (letterspaced caps)."""
    px = float(x)
    for ch in text:
        code = ord(ch)
        if code not in _FONTS[font_name]:
            px += pitch
            continue
        _adv, ox, oy, _sw, _sh, pts = _scaled_glyph(font_name, size, code)
        _draw_glyph_pts(cv, int(px) + ox, int(y) + oy, pts, col)
        px += pitch


def tracked_width(text, pitch):
    return len(text) * pitch


# ------------------------------------------------------- soft blend tools
def blend_px(cv, x, y, col, a):
    """Alpha-blend one pixel toward col; a in [0, 1]."""
    if a <= 0.005 or not (0 <= x < cv.w and 0 <= y < cv.h):
        return
    if a >= 0.995:
        cv._set(x, y, col)
        return
    i = (y * cv.w + x) * 3
    pix = cv.pix
    pix[i] = int(pix[i] * (1 - a) + col[0] * a)
    pix[i + 1] = int(pix[i + 1] * (1 - a) + col[1] * a)
    pix[i + 2] = int(pix[i + 2] * (1 - a) + col[2] * a)


def soft_disc(cv, cx, cy, r, col, peak):
    """A disc whose alpha falls off quadratically to the rim: soft
    glow / mist puff / paper blotch with no hard edge."""
    cx, cy = int(cx), int(cy)
    r = int(r)
    if r <= 0:
        return
    pix = cv.pix
    w = cv.w
    for y in range(max(0, cy - r), min(cv.h, cy + r + 1)):
        dy = (y - cy) / r
        rem = 1 - dy * dy
        if rem <= 0:
            continue
        dx = int(r * rem ** 0.5)
        for x in range(max(0, cx - dx), min(cv.w, cx + dx + 1)):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / r
            a = peak * (1 - d) * (1 - d)
            if a <= 0.01:
                continue
            i = (y * w + x) * 3
            pix[i] = int(pix[i] * (1 - a) + col[0] * a)
            pix[i + 1] = int(pix[i + 1] * (1 - a) + col[1] * a)
            pix[i + 2] = int(pix[i + 2] * (1 - a) + col[2] * a)


def blend_rect(cv, x0, y0, x1, y1, col, a):
    """Blend a whole rectangle toward col by a fixed alpha."""
    if a <= 0.005:
        return
    pix = cv.pix
    w = cv.w
    for y in range(max(0, int(y0)), min(cv.h, int(y1) + 1)):
        for x in range(max(0, int(x0)), min(cv.w, int(x1) + 1)):
            i = (y * w + x) * 3
            pix[i] = int(pix[i] * (1 - a) + col[0] * a)
            pix[i + 1] = int(pix[i + 1] * (1 - a) + col[1] * a)
            pix[i + 2] = int(pix[i + 2] * (1 - a) + col[2] * a)


# ------------------------------------------------------- geometry helpers
def point_in_poly(x, y, pts):
    inside = False
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xin = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xin:
                inside = not inside
    return inside


def ridge_pts(x0, x1, base, amp, seed, step=8):
    """An organic ridgeline: fBm wander plus a slow sine, sampled
    every step px — never a straight line, never a regular wave."""
    pts = []
    x = x0
    while x <= x1:
        y = base + amp * (fbm(x * 0.008, seed * 0.37, seed, 3) - 0.5) * 2
        y += 5 * math.sin(x * 0.021 + seed)
        pts.append((x, int(y)))
        x += step
    pts.append((x1, int(base + amp * (fbm(x1 * 0.008, seed * 0.37,
                                          seed, 3) - 0.5) * 2
                        + 5 * math.sin(x1 * 0.021 + seed))))
    return pts


def facets(cv, pts, rng, count, cols):
    """Scatter small rock-facet triangles inside a polygon."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    for _ in range(count):
        x = rng.randint(int(min(xs)), int(max(xs)))
        y = rng.randint(int(min(ys)), int(max(ys)))
        if not point_in_poly(x, y, pts):
            continue
        s = rng.randint(4, 14)
        tri = [(x, y), (x + rng.randint(-s, s), y + rng.randint(2, s)),
               (x + rng.randint(-s, s), y + rng.randint(2, s))]
        cv.polygon(tri, fill=rng.choice(cols))


# ------------------------------------------------------------------ scene
def aurora_columns():
    """Per-column aurora band parameters: three wavy curtains whose
    centrelines wander with fBm, plus a vertical-ray factor."""
    cols = []
    for x in range(W):
        c1 = 300 + 62 * (fbm(x * 0.006, 0.0, 11, 3) - 0.5) * 2 \
            + 22 * math.sin(x * 0.010 + 1.2)
        c2 = 232 + 52 * (fbm(x * 0.007, 5.0, 23, 3) - 0.5) * 2 \
            + 18 * math.sin(x * 0.008 + 2.6)
        c3 = 372 + 46 * (fbm(x * 0.005, 9.0, 37, 3) - 0.5) * 2
        ray = 0.72 + 0.55 * fbm(x * 0.045, 7.7, 51, 3)
        cols.append((c1, c2, c3, ray))
    return cols


def draw_sky(cv):
    cv.vgrad(0, 0, W, 600, [
        (0.00, SKY_TOP), (0.35, SKY_2), (0.70, SKY_3),
        (0.92, mix(SKY_HORIZON, AUR_WASH, 0.35)), (1.00, SKY_HORIZON)])


def draw_stars(cv, rng):
    for _ in range(150):
        x = rng.randint(8, W - 8)
        y = rng.randint(8, 470)
        b = rng.randint(140, 235)
        col = (b, b, min(255, b + 18))
        cv._set(x, y, col)
        if rng.random() < 0.25:
            cv._set(x + 1, y, (b - 40, b - 40, b - 30))
    # a few bright four-point sparkles
    for (x, y, s) in [(120, 90, 6), (660, 70, 7), (560, 150, 5),
                      (210, 60, 5), (720, 200, 6), (60, 260, 5)]:
        cv.line(x - s, y, x + s, y, (235, 238, 250), 1)
        cv.line(x, y - s, x, y + s, (235, 238, 250), 1)
        cv.disc(x, y, 2, (250, 250, 255))


def draw_aurora(cv):
    """Three soft aurora curtains, blended per pixel: Gaussian
    falloff from wavy centrelines, vertical ray modulation, no
    hard edge anywhere."""
    cols = aurora_columns()
    pix = cv.pix
    w = cv.w
    for y in range(198, 479):
        row = y * w * 3
        for x in range(w):
            c1, c2, c3, ray = cols[x]
            i1 = 0.78 * math.exp(-((y - c1) / 58.0) ** 2)
            i2 = 0.52 * math.exp(-((y - c2) / 46.0) ** 2)
            i3 = 0.36 * math.exp(-((y - c3) / 42.0) ** 2)
            tot = i1 + i2 + i3
            if tot < 0.02:
                continue
            a = tot * ray
            if a > 1.0:
                a = 1.0
            r = (AUR1[0] * i1 + AUR2[0] * i2 + AUR3[0] * i3) / tot
            g = (AUR1[1] * i1 + AUR2[1] * i2 + AUR3[1] * i3) / tot
            b = (AUR1[2] * i1 + AUR2[2] * i2 + AUR3[2] * i3) / tot
            idx = row + x * 3
            pix[idx] = int(pix[idx] * (1 - a) + r * a)
            pix[idx + 1] = int(pix[idx + 1] * (1 - a) + g * a)
            pix[idx + 2] = int(pix[idx + 2] * (1 - a) + b * a)


def _ridge_diag(x0, y0, x1, y1, amp, seed, step=8):
    """Ridgeline from (x0, y0) to (x1, y1): straight diagonal
    plus fBm wander — organic, never a clean slope."""
    pts = []
    dx = x1 - x0
    dy = y1 - y0
    x = x0
    while (x <= x1 if dx >= 0 else x >= x1):
        f = (x - x0) / dx if dx else 0.0
        y = y0 + dy * f + amp * (fbm(x * 0.008, seed * 0.37,
                                     seed, 3) - 0.5) * 2
        y += 5 * math.sin(x * 0.021 + seed)
        pts.append((int(x), int(y)))
        x += step if dx >= 0 else -step
    pts.append((x1, int(y1 + amp * (fbm(x1 * 0.008, seed * 0.37,
                                        seed, 3) - 0.5) * 2
                       + 5 * math.sin(x1 * 0.021 + seed))))
    return pts


def _snow_band(cv, ridge, depth, col, rng):
    """A pale snow band hugging a ridgeline — but PATCHY: the
    band exists only where gate noise is open, so the snowline
    reads as drifted patches, never a painted stripe."""
    def flush(run):
        if len(run) < 2:
            return
        low = []
        for (x, y) in run:
            d = depth * (0.55 + 0.9 * fbm(x * 0.03, 4.4, 71, 2))
            low.append((x, int(y + d)))
        cv.polygon(run + list(reversed(low)), fill=col)

    run = []
    for (x, y) in ridge:
        if fbm(x * 0.02, 9.9, 91, 2) > 0.42:
            run.append((x, y))
        else:
            flush(run)
            run = []
    flush(run)


def draw_far_ridge(cv, rng):
    # a second, hazier ridge behind the main one, for depth
    ridge2 = ridge_pts(260, 505, 510, 36, 23)
    pts2 = ridge2 + [(510, 575), (260, 575)]
    cv.polygon(pts2, fill=mix(MTN_FAR, SKY_3, 0.55))
    ridge = ridge_pts(250, 512, 520, 48, 7)
    pts = ridge + [(512, 575), (250, 575)]
    cv.polygon(pts, fill=mix(MTN_FAR, SKY_3, 0.15))
    _snow_band(cv, ridge, 9, mix(SNOW, MTN_FAR, 0.25), rng)
    facets(cv, pts, rng, 40, [mix(MTN_FAR, MTN_FAR_LT, 0.5),
                              mix(MTN_FAR, SNOW, 0.35)])
    # mist hugging the ridge base, softening the pale band
    for (cx, cy, r, pk) in [(310, 545, 55, 0.07), (360, 535, 65, 0.08),
                            (420, 550, 50, 0.07), (465, 540, 60, 0.06)]:
        soft_disc(cv, cx, cy, r, MIST, pk)


def draw_left_mountain(cv, rng):
    ridge = _ridge_diag(0, 500, 260, 560, 26, 13)
    pts = ridge + [(260, 560), (0, 700), (0, 1024)]
    cv.polygon(pts, fill=MTN_L)
    _snow_band(cv, ridge, 10, mix(SNOW, MTN_L, 0.2), rng)
    facets(cv, pts, rng, 110, [mix(MTN_L, SNOW, 0.3),
                               mix(MTN_L, (8, 12, 30), 0.5),
                               mix(MTN_L, AUR2, 0.18)])
    # a few pines clinging to the upper slope
    for (x, y) in [(60, 640), (140, 615), (210, 590)]:
        draw_pine(cv, x, y, 26)


def draw_right_mountain(cv, rng):
    ridge = _ridge_diag(768, 500, 510, 560, 26, 19)
    pts = ridge + [(510, 560), (768, 700), (768, 1024)]
    cv.polygon(pts, fill=MTN_R)
    _snow_band(cv, ridge, 10, mix(SNOW, MTN_R, 0.2), rng)
    facets(cv, pts, rng, 110, [mix(MTN_R, SNOW, 0.3),
                               mix(MTN_R, (8, 12, 30), 0.5),
                               mix(MTN_R, AUR2, 0.18)])
    for (x, y) in [(710, 640), (630, 615), (560, 590)]:
        draw_pine(cv, x, y, 24)


def draw_pine(cv, x, ybase, h):
    """A small dark pine: three stacked triangles + trunk."""
    cv.polygon([(x - h // 3, ybase), (x, ybase - h),
                (x + h // 3, ybase)], fill=PINE)
    cv.polygon([(x - h // 4, ybase - h // 3), (x, ybase - h * 2 // 3),
                (x + h // 4, ybase - h // 3)], fill=mix(PINE, (20, 34, 50), 0.4))
    cv.line(x, ybase, x, ybase - h, PINE, 1)


def _water_xl(y):
    if y <= 560:
        return 260
    if y >= 700:
        return 0
    return int(260 - (y - 560) / 140 * 260)


def _water_xr(y):
    if y <= 560:
        return 510
    if y >= 700:
        return 768
    return int(510 + (y - 560) / 140 * 258)


def draw_water(cv, rng, cols):
    for y in range(560, 1024):
        t = (y - 560) / 464.0
        if t < 0.45:
            col = mix(WATER_TOP, WATER_MID, t / 0.45)
        else:
            col = mix(WATER_MID, WATER_BOT, (t - 0.45) / 0.55)
        cv.rect(_water_xl(y), y, _water_xr(y), y, fill=col)
    # aurora reflection: broken green-gold shimmer, weighted
    # toward columns where the aurora is bright, fading with
    # depth — mostly faint, a few bright — never uniform static
    for _ in range(200):
        x = rng.randint(60, 708)
        _c1, _c2, _c3, ray = cols[x]
        if rng.random() > ray / 1.3:
            continue
        y = rng.randint(600, 1000)
        if x < _water_xl(y) + 4 or x > _water_xr(y) - 30:
            continue
        ln = rng.randint(10, 44)
        fade = max(0.08, (1.0 - (y - 580) / 560.0) ** 1.5)
        a = (0.15 + 0.35 * ray * fade) if rng.random() < 0.85 \
            else (0.45 + 0.4 * ray * fade)
        base = rng.choice([AUR1, AUR2, AUR3, GOLD])
        col = mix(base, mix(WATER_TOP, WATER_MID, 0.5), 1 - a)
        cv.line(x, y, x + ln, y, col, 1)
    # bright reflection column under the lighthouse beam —
    # v5: wider and taller, directly under the big tower, plus
    # a green aurora column in the same place
    for _ in range(140):
        x = rng.randint(300, 470)
        y = rng.randint(600, 960)
        if x < _water_xl(y) + 4 or x > _water_xr(y) - 30:
            continue
        ln = rng.randint(8, 30)
        col = mix(GOLD_LT, WATER_MID, rng.uniform(0.35, 0.6))
        cv.line(x, y, x + ln, y, col, 1)
    for _ in range(60):
        x = rng.randint(310, 460)
        y = rng.randint(600, 940)
        if x < _water_xl(y) + 4 or x > _water_xr(y) - 30:
            continue
        ln = rng.randint(8, 30)
        base = rng.choice([AUR1, AUR2])
        col = mix(base, WATER_MID, rng.uniform(0.4, 0.65))
        cv.line(x, y, x + ln, y, col, 1)


def draw_beam(cv, ax, ay, bx, by, peak, wide=70, base=10):
    """A soft light wedge from (ax, ay) to (bx, by): alpha falls
    off along the beam and across its widening width."""
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    pix = cv.pix
    w = cv.w
    x0 = max(0, min(ax, bx) - 30)
    x1 = min(cv.w, max(ax, bx) + 30)
    y0 = max(0, min(ay, by) - 30)
    y1 = min(cv.h, max(ay, by) + 30)
    for y in range(y0, y1):
        for x in range(x0, x1):
            px, py = x - ax, y - ay
            t = (px * ux + py * uy) / length
            if t < 0.02 or t > 1.0:
                continue
            d = abs(-px * uy + py * ux)
            half = base + wide * t
            a = peak * (1 - t) ** 1.4 * math.exp(-((d / half) ** 2))
            if a < 0.015:
                continue
            i = (y * w + x) * 3
            pix[i] = int(pix[i] * (1 - a) + BEAM[0] * a)
            pix[i + 1] = int(pix[i + 1] * (1 - a) + BEAM[1] * a)
            pix[i + 2] = int(pix[i + 2] * (1 - a) + BEAM[2] * a)


def draw_lighthouse(cv, rng):
    """The landmark, v5: a BIG rock islet with a tall lighthouse
    whose beam sweeps the fjord — the one warm light in the cold
    night, now the dominant 50%+ frame hero (top-3 formula)."""
    # islet: wide and prominent, the landmark's base
    islet = [(296, 604), (330, 540), (440, 540), (474, 604)]
    cv.polygon(islet, fill=ROCK_FG)
    cv.polyline(islet, mix(ROCK_FG, SNOW, 0.35), 1)
    facets(cv, islet, rng, 26, [mix(ROCK_FG, MTN_FAR, 0.5),
                                mix(ROCK_FG, SNOW, 0.25),
                                mix(ROCK_FG, (8, 12, 30), 0.4)])
    cv.disc(330, 556, 3, mix(SNOW, ROCK_FG, 0.4))
    cv.disc(448, 560, 2, mix(SNOW, ROCK_FG, 0.4))
    cv.disc(384, 548, 2, mix(SNOW, ROCK_FG, 0.4))
    # rock bumps break the islet's flat top edge
    cv.polygon([(340, 542), (348, 532), (356, 542)], fill=ROCK_FG)
    cv.polygon([(420, 542), (428, 534), (436, 542)], fill=ROCK_FG)
    # tower: tall and tapered, dark, with a gold lamp room —
    # 2.5-3x bigger than v4, peak up inside the aurora curtain
    cv.polygon([(352, 552), (416, 552), (402, 300), (366, 300)],
               fill=LIGHT_TOWER)
    cv.rect(360, 470, 408, 478, fill=mix(LIGHT_TOWER, CREAM, 0.30))
    cv.rect(364, 390, 404, 398, fill=mix(LIGHT_TOWER, CREAM, 0.25))
    # warm edge-light on the beam side, so the tower is not a
    # flat black monolith
    cv.line(366, 300, 352, 552, mix(LIGHT_TOWER, GOLD, 0.35), 1)
    # small lit windows down the tower face (NOCTARA-style)
    for (wy, s) in [(338, 8), (408, 8), (478, 8)]:
        cv.rect(380, wy, 380 + s, wy + s + 2, fill=GOLD)
        soft_disc(cv, 384, wy + s // 2, 10, GOLD, 0.4)
    cv.rect(362, 286, 406, 300, fill=GOLD)
    cv.rect(360, 282, 408, 286, fill=LIGHT_TOWER)
    cv.disc(384, 293, 4, GOLD_LT)
    soft_disc(cv, 384, 293, 80, GOLD, 0.6)
    soft_disc(cv, 384, 293, 160, GOLD, 0.18)
    # the beam: a strong soft wedge sweeping down-left over the
    # water (wide wash + bright narrow core), plus one to the right
    draw_beam(cv, 384, 293, 100, 640, 0.9, wide=110, base=16)
    draw_beam(cv, 384, 293, 100, 640, 0.55, wide=36, base=5)
    draw_beam(cv, 384, 293, 660, 600, 0.65, wide=70, base=12)


def draw_boat(cv, x, y, s, lantern=True):
    """A tiny wooden boat with a glowing lantern."""
    cv.polygon([(x - 22 * s, y), (x + 22 * s, y),
                (x + 16 * s, y + 9 * s), (x - 16 * s, y + 9 * s)],
               fill=ROCK_FG)
    cv.line(x - 22 * s, y, x + 22 * s, y, GOLD, 1)
    if lantern:
        cv.line(x, y, x, y - 12 * s, ROCK_FG, 1)
        cv.disc(x, y - 14 * s, 2, GOLD_LT)
        soft_disc(cv, x, y - 14 * s, 12, GOLD, 0.5)
    for i, yy in enumerate(range(int(y + 12 * s), int(y + 34 * s), 8)):
        wdt = int((10 + i * 3) * s)
        cv.line(x - wdt, yy, x + wdt, yy,
                mix(GOLD, WATER_MID, 0.4 + i * 0.06), 1)


def draw_mist(cv, rng):
    """Valley mist as clusters of soft overlapping puffs —
    radial falloff, no hard edge, never one flat shelf."""
    for _ in range(16):
        cx = rng.randint(150, 640)
        cy = rng.randint(600, 860)
        for _ in range(4):
            px = cx + rng.randint(-60, 60)
            py = cy + rng.randint(-10, 10)
            r = rng.randint(35, 80)
            soft_disc(cv, px, py, r, MIST,
                      rng.uniform(0.05, 0.09))
    # a few puffs hugging the far shore
    for (cx, cy) in [(330, 570), (440, 575), (385, 600),
                     (300, 575), (480, 580)]:
        for _ in range(3):
            px = cx + rng.randint(-30, 30)
            py = cy + rng.randint(-5, 5)
            soft_disc(cv, px, py, rng.randint(14, 30), MIST,
                      rng.uniform(0.05, 0.08))


def draw_foreground(cv, rng):
    # dark shore rocks framing the bottom corners, with pines —
    # v5: lighter, faceted, snow on the top edges (no black
    # triangles anymore)
    left_pts = [(0, 1024), (0, 962), (90, 920), (180, 952),
                (210, 1024)]
    cv.polygon(left_pts, fill=mix(ROCK_FG, MTN_L, 0.45))
    cv.polyline([(0, 962), (90, 920), (180, 952)],
                mix(ROCK_FG, SNOW, 0.3), 1)
    facets(cv, left_pts, rng, 40, [mix(ROCK_FG, SNOW, 0.3),
                                   mix(ROCK_FG, MTN_FAR, 0.4),
                                   mix(ROCK_FG, (8, 12, 30), 0.4)])
    for (x, y, r) in [(15, 958, 2), (30, 950, 2), (60, 938, 3),
                      (90, 922, 2), (120, 935, 2), (150, 945, 3),
                      (180, 950, 2), (195, 965, 2)]:
        cv.disc(x, y, r, mix(SNOW, ROCK_FG, 0.5))
    right_pts = [(768, 1024), (768, 966), (690, 930), (620, 962),
                 (600, 1024)]
    cv.polygon(right_pts, fill=mix(ROCK_FG, MTN_R, 0.45))
    cv.polyline([(768, 966), (690, 930), (620, 962)],
                mix(ROCK_FG, SNOW, 0.3), 1)
    facets(cv, right_pts, rng, 40, [mix(ROCK_FG, SNOW, 0.3),
                                    mix(ROCK_FG, MTN_FAR, 0.4),
                                    mix(ROCK_FG, (8, 12, 30), 0.4)])
    for (x, y, r) in [(750, 958, 2), (740, 952, 2), (720, 945, 3),
                      (690, 932, 2), (670, 950, 2), (660, 945, 2),
                      (635, 955, 3), (610, 970, 2)]:
        cv.disc(x, y, r, mix(SNOW, ROCK_FG, 0.5))
    for (x, y, h) in [(60, 950, 34), (115, 968, 28), (155, 945, 30)]:
        draw_pine(cv, x, y, h)
    for (x, y, h) in [(700, 955, 30), (650, 972, 26)]:
        draw_pine(cv, x, y, h)
    # snow dust on the foreground rocks
    for _ in range(26):
        x = rng.randint(0, 210) if rng.random() < 0.5 else rng.randint(600, 768)
        y = rng.randint(930, 1000)
        cv.disc(x, y, rng.randint(1, 3), mix(SNOW, ROCK_FG, 0.5))
    # a lantern post on the right bank, the near human cue
    cv.line(690, 928, 690, 890, ROCK_FG, 2)
    cv.line(690, 890, 704, 890, ROCK_FG, 2)
    cv.disc(704, 896, 3, GOLD_LT)
    soft_disc(cv, 704, 896, 22, GOLD, 0.5)
    soft_disc(cv, 704, 896, 44, GOLD, 0.15)


def draw_paper(cv, rng):
    """Large, very faint warm/cool blotches: paper mottling."""
    for _ in range(12):
        x = rng.randint(0, W)
        y = rng.randint(0, H)
        r = rng.randint(120, 220)
        col = rng.choice([(200, 180, 150), (140, 160, 170),
                          (170, 150, 140)])
        soft_disc(cv, x, y, r, col, rng.uniform(0.025, 0.05))


_GRAIN_TABLE = [(i * 2654435761 % 29) - 14 for i in range(256)]


def draw_grain(cv):
    """Heavy full-frame film grain: a deterministic per-pixel
    delta from a 256-entry table, tiled by position."""
    pix = cv.pix
    w, h = cv.w, cv.h
    tab = _GRAIN_TABLE
    j = 0
    for y in range(h):
        ro = (y * 57) & 255
        for x in range(w):
            d = tab[(x * 31 + ro) & 255]
            r = pix[j] + d
            pix[j] = 0 if r < 0 else (255 if r > 255 else r)
            g = pix[j + 1] + d
            pix[j + 1] = 0 if g < 0 else (255 if g > 255 else g)
            b = pix[j + 2] + d
            pix[j + 2] = 0 if b < 0 else (255 if b > 255 else b)
            j += 3


def draw_frame(cv):
    cv.rect(12, 12, W - 13, H - 13, outline=CREAM, width=3)
    cv.rect(21, 21, W - 22, H - 22, outline=GOLD, width=1)


def draw_title(cv):
    draw_centered(cv, "serif_bold", 112, 384, 48, "AURELIS", CREAM)
    cv.line(292, 178, 476, 178, GOLD, 2)
    sub = "THE AURORA FJORD"
    pitch = 22
    wdt = tracked_width(sub, pitch)
    draw_tracked(cv, "sans", 22, 384 - wdt / 2, 196, sub, GOLD, pitch)


# ------------------------------------------------------------------- main
def main():
    rng = random.Random(SEED)
    here = os.path.dirname(os.path.abspath(__file__))
    init_fonts(os.path.join(here, "fonts.bin"))

    cols = aurora_columns()
    cv = Canvas(W, H, SKY_TOP)
    draw_sky(cv)
    draw_stars(cv, rng)
    draw_aurora(cv)
    draw_far_ridge(cv, rng)
    draw_left_mountain(cv, rng)
    draw_right_mountain(cv, rng)
    draw_water(cv, rng, cols)
    draw_lighthouse(cv, rng)
    draw_boat(cv, 250, 830, 1.4)
    draw_boat(cv, 560, 720, 1.0)
    draw_boat(cv, 430, 770, 1.2)
    draw_boat(cv, 150, 690, 0.9)
    draw_boat(cv, 610, 880, 1.3)
    draw_mist(cv, rng)
    draw_foreground(cv, rng)
    draw_title(cv)
    draw_paper(cv, rng)
    draw_grain(cv)
    draw_frame(cv)

    out = os.environ.get("OUTPUT", "/output/entry.png")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    write_png(cv, out)
    n = os.path.getsize(out)
    print(f"{out} {W}x{H} {n} bytes")


if __name__ == "__main__":
    main()
