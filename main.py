"""KAVIRA — The Glass Bridge. make.fun entry: The Poster for a Place
That Isn't There.

Draws one travel poster (768x1024) to /output/entry.png. Stdlib only
(Python 3.13, no network, no external assets): a small software
rasterizer, a DejaVu glyph atlas read from fonts.bin beside this
file, and a hand-rolled PNG writer. Deterministic: same bytes every
run (seeded randomness only).

Concept: KAVIRA, a dawn canyon in a high desert. One impossible
landmark — a glass sky-bridge arcing across the canyon gap, catching
the first sun — spans two terraced cliff cities. The sun rises over
a far canyon wall; the river below mirrors the dawn in gold. Warm
palette: violet dusk sky, rose and peach dawn, terracotta strata,
gold light. The name is set big in DejaVu Serif Bold across the sky,
one short subtitle beneath it, nothing else.

v2 rebuild (v1 LUMARA was held by the owner as too flat/empty):
painterly and dense — multi-stop gradients, stratified cliffs with
facets, layered valley mist, grain over the whole frame, and every
zone (sky, cliffs, river, foreground) filled.
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
SKY_TOP = (28, 20, 54)
SKY_2 = (86, 48, 88)
SKY_3 = (172, 92, 98)
SKY_4 = (232, 152, 98)
HORIZON = (252, 198, 122)
SUN = (255, 226, 160)
SUN_CORE = (255, 244, 214)
CLIFF_LT = (198, 112, 76)
CLIFF = (158, 82, 62)
CLIFF_DK = (106, 54, 54)
CLIFF_SH = (58, 34, 48)
STRATA_GOLD = (228, 160, 94)
STRATA_DK = (122, 64, 58)
FAR_WALL = (196, 128, 108)
FAR_WALL_DK = (150, 92, 92)
RIVER_TOP = (238, 172, 112)
RIVER_MID = (168, 110, 108)
RIVER_BOT = (54, 46, 74)
GOLD = (240, 180, 90)
GOLD_LT = (255, 215, 141)
CREAM = (250, 238, 216)
ROCK_FG = (40, 26, 40)
MIST = (226, 182, 158)
BUSH = (72, 52, 62)


def mix(a, b, t):
    """Linear blend of two RGB colours; t=0 -> a, t=1 -> b."""
    return tuple(int(a[c] + (b[c] - a[c]) * t) for c in range(3))


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


# ------------------------------------------------------- geometry helpers
def clip_y(pts, y0, y1):
    """Clip a polygon to the horizontal band y0..y1 (Sutherland-Hodgman)."""
    def clip_half(pts, y, keep_below):
        out = []
        n = len(pts)
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            ain = a[1] <= y if keep_below else a[1] >= y
            bin_ = b[1] <= y if keep_below else b[1] >= y
            if ain:
                out.append(a)
            if ain != bin_:
                t = (y - a[1]) / (b[1] - a[1]) if b[1] != a[1] else 0.0
                out.append((a[0] + (b[0] - a[0]) * t, y))
        return out
    return clip_half(clip_half(pts, y1, True), y0, False)


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


def strata_fill(cv, pts, y_top, y_bot, colors):
    """Fill a polygon with horizontal strata bands (painterly rock)."""
    n = len(colors)
    for i in range(n):
        f0, f1 = i / n, (i + 1) / n
        y0 = y_top + (y_bot - y_top) * f0
        y1 = y_top + (y_bot - y_top) * f1
        sub = clip_y(pts, y0, y1)
        if len(sub) >= 3:
            cv.polygon(sub, fill=colors[i])


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
def draw_sky(cv):
    cv.vgrad(0, 0, W, 470, [
        (0.00, SKY_TOP), (0.30, SKY_2), (0.58, SKY_3),
        (0.82, SKY_4), (1.00, HORIZON)])


def draw_clouds(cv, rng):
    # low, wide dawn clouds built from overlapping flattened
    # ellipses, kept clear of the title zone (y < 200, centre)
    clouds = [(120, 235), (620, 215), (200, 305), (540, 325),
              (90, 140), (680, 125)]
    for (cx, cy) in clouds:
        rx = rng.randint(50, 95)
        cv.ellipse(cx - rx, cy - 6, cx + rx, cy + 6,
                   fill=mix(SKY_2, SKY_3, 0.55))
        cv.ellipse(cx - rx + 18, cy - 3, cx + rx - 10, cy + 9,
                   fill=mix(SKY_3, SKY_4, 0.4))
        cv.ellipse(cx - rx + 30, cy + 2, cx + rx - 30, cy + 10,
                   fill=mix(SKY_4, GOLD_LT, 0.35))
    # a few thin high streaks, low in the sky
    for (x0, y, ln) in [(60, 250, 150), (430, 280, 180), (300, 340, 120)]:
        cv.line(x0, y, x0 + ln, y, mix(CREAM, SKY_2, 0.55), 1)


def draw_sun(cv):
    # wide soft glow, then the disc, low over the far canyon rim
    cv.disc(384, 402, 110, mix(SKY_4, SUN, 0.25))
    cv.disc(384, 402, 96, mix(SKY_4, SUN, 0.35))
    cv.disc(384, 402, 82, mix(SKY_4, SUN, 0.45))
    cv.disc(384, 402, 62, mix(SKY_4, SUN, 0.65))
    cv.disc(384, 402, 48, SUN)
    cv.disc(384, 402, 38, SUN_CORE)


def draw_far_wall(cv, rng):
    # hazy canyon wall across the gap, sun just over its rim
    pts = [(212, 402), (556, 402), (540, 520), (502, 640),
           (266, 640), (228, 520)]
    strata_fill(cv, pts, 402, 640,
                [FAR_WALL, mix(FAR_WALL, FAR_WALL_DK, 0.3),
                 mix(FAR_WALL, SKY_4, 0.25), FAR_WALL_DK,
                 mix(FAR_WALL, FAR_WALL_DK, 0.45), FAR_WALL,
                 mix(FAR_WALL, SKY_4, 0.15), FAR_WALL_DK])
    facets(cv, pts, rng, 60, [mix(FAR_WALL, CREAM, 0.25),
                              mix(FAR_WALL, FAR_WALL_DK, 0.4)])
    # thin dark cracks in the far wall, not pillars
    for (x0, y0, x1, y1) in [(330, 402, 336, 540), (446, 402, 442, 510),
                             (300, 402, 296, 470), (480, 402, 486, 500)]:
        cv.line(x0, y0, x1, y1, mix(FAR_WALL_DK, CLIFF_SH, 0.5), 1)


def draw_house(cv, x, ytop, w, h, lit=True):
    """Small cliff dwelling: dark block, flat roof, lit windows."""
    cv.rect(x, ytop - h, x + w, ytop, fill=CLIFF_SH)
    cv.rect(x - 1, ytop - h - 2, x + w + 1, ytop - h, fill=CLIFF_SH)
    if lit:
        cv.disc(x + 5, ytop - h + 6, 5, mix(GOLD, CLIFF_SH, 0.55))
        cv.rect(x + 3, ytop - h + 4, x + 6, ytop - h + 8, fill=GOLD_LT)
        if w >= 18:
            cv.rect(x + w - 7, ytop - h + 4, x + w - 4, ytop - h + 8,
                    fill=GOLD_LT)


def draw_tree(cv, x, ybase, h):
    cv.polygon([(x - 5, ybase), (x, ybase - h), (x + 5, ybase)],
               fill=BUSH)
    cv.line(x, ybase, x, ybase - h, BUSH, 1)


def draw_left_cliff(cv, rng):
    pts = [(0, 330), (150, 348), (238, 392), (268, 470), (246, 566),
           (206, 664), (158, 752), (118, 828), (66, 912), (0, 962)]
    strata_fill(cv, pts, 330, 962,
                [CLIFF_LT, CLIFF, mix(CLIFF, STRATA_GOLD, 0.5),
                 STRATA_GOLD, CLIFF_DK, CLIFF,
                 mix(CLIFF_LT, CLIFF, 0.5), CLIFF_DK,
                 mix(CLIFF, CLIFF_DK, 0.5), CLIFF_SH])
    # sunlit inner face: a lighter wedge along the gap side
    face = [(238, 392), (268, 470), (246, 566), (206, 664),
            (158, 752), (118, 828), (150, 828), (196, 700),
            (228, 590), (240, 480), (226, 420)]
    cv.polygon(face, fill=mix(CLIFF_LT, STRATA_GOLD, 0.45))
    facets(cv, pts, rng, 140, [mix(CLIFF, CREAM, 0.22),
                               mix(CLIFF_DK, CLIFF_SH, 0.5),
                               mix(STRATA_GOLD, CLIFF, 0.4)])
    # vertical cracks break the horizontal banding
    for (x0, y0, x1, y1) in [(120, 400, 100, 560), (200, 480, 220, 640),
                             (80, 600, 60, 760), (160, 700, 180, 860)]:
        cv.line(x0, y0, x1, y1, mix(CLIFF_DK, CLIFF_SH, 0.5), 1)
    # terraced dwellings cut into the rim
    draw_house(cv, 30, 348, 22, 15)
    draw_house(cv, 96, 356, 18, 12)
    draw_house(cv, 150, 372, 20, 14)
    draw_house(cv, 60, 470, 18, 12)
    draw_house(cv, 120, 540, 20, 13)
    draw_house(cv, 40, 620, 16, 11)
    draw_tree(cv, 210, 400, 22)
    draw_tree(cv, 90, 372, 18)


def draw_right_cliff(cv, rng):
    pts = [(768, 330), (618, 348), (530, 392), (500, 470), (522, 566),
           (562, 664), (610, 752), (650, 828), (702, 912), (768, 962)]
    strata_fill(cv, pts, 330, 962,
                [CLIFF_LT, CLIFF, mix(CLIFF, STRATA_GOLD, 0.5),
                 STRATA_GOLD, CLIFF_DK, CLIFF,
                 mix(CLIFF_LT, CLIFF, 0.5), CLIFF_DK,
                 mix(CLIFF, CLIFF_DK, 0.5), CLIFF_SH])
    # the right face is in shade: a darker wedge along the gap side
    face = [(530, 392), (500, 470), (522, 566), (562, 664),
            (610, 752), (650, 828), (622, 828), (574, 700),
            (542, 590), (530, 480), (544, 420)]
    cv.polygon(face, fill=mix(CLIFF_DK, CLIFF_SH, 0.45))
    facets(cv, pts, rng, 140, [mix(CLIFF, CREAM, 0.2),
                               mix(CLIFF_DK, CLIFF_SH, 0.5),
                               mix(STRATA_GOLD, CLIFF, 0.35)])
    # vertical cracks break the horizontal banding
    for (x0, y0, x1, y1) in [(648, 400, 668, 560), (568, 480, 548, 640),
                             (688, 600, 708, 760), (608, 700, 588, 860)]:
        cv.line(x0, y0, x1, y1, mix(CLIFF_DK, CLIFF_SH, 0.5), 1)
    draw_house(cv, 700, 348, 22, 15)
    draw_house(cv, 640, 356, 18, 12)
    draw_house(cv, 580, 372, 20, 14)
    draw_house(cv, 690, 470, 18, 12)
    draw_house(cv, 630, 540, 20, 13)
    draw_house(cv, 700, 620, 16, 11)
    draw_tree(cv, 560, 400, 22)
    draw_tree(cv, 660, 372, 18)


def draw_bridge(cv, rng):
    """The glass sky-bridge: a bold pale-gold arc across the gap,
    dark shadow line underneath to separate it from the far wall,
    gold rails, thin suspenders, three tiny walkers with a lantern."""
    def arc_y(x):
        t = (x - 248) / (520 - 248)
        return 404 + 66 * 4 * t * (1 - t)
    xs = list(range(248, 521, 3))
    deck = [(x, arc_y(x)) for x in xs]
    upper = [(x, arc_y(x) - 13) for x in xs]
    shadow = [(x, arc_y(x) + 3) for x in xs]
    cv.polyline(shadow, mix(CLIFF_SH, SKY_4, 0.4), 3)
    cv.polygon(upper + list(reversed(deck)),
               fill=mix(GOLD_LT, CREAM, 0.65))
    cv.polyline(upper, GOLD, 2)
    cv.polyline(deck, mix(GOLD, CLIFF_DK, 0.3), 2)
    for x in range(268, 505, 24):
        y = arc_y(x)
        cv.line(x, y - 13, x, y + 10, mix(GOLD, SKY_4, 0.3), 1)
    for x in (300, 360, 420, 470):
        y = arc_y(x)
        cv.line(x, y - 10, x + 24, y - 10, CREAM, 1)
    # three tiny walkers, the human-scale cue
    for x in (330, 390, 450):
        y = arc_y(x)
        cv.disc(x, y - 16, 3, CLIFF_SH)
        cv.line(x, y - 13, x, y - 5, CLIFF_SH, 2)
        cv.line(x, y - 5, x - 3, y, CLIFF_SH, 1)
        cv.line(x, y - 5, x + 3, y, CLIFF_SH, 1)
        cv.disc(x + 5, y - 10, 2, GOLD_LT)


def _interp_edge(edge, y):
    """Piecewise-linear x at height y for an edge [(y, x), ...]."""
    for i in range(len(edge) - 1):
        y0, x0 = edge[i]
        y1, x1 = edge[i + 1]
        if y0 <= y <= y1:
            f = 0.0 if y1 == y0 else (y - y0) / (y1 - y0)
            return x0 + (x1 - x0) * f
    return edge[-1][1]


def draw_valley_floor(cv):
    """Rocky valley floor under the river, so no sky-coloured gaps
    show between river edge and cliff base."""
    cv.vgrad(0, 640, W, 372, [(0.0, (132, 78, 76)),
                               (0.5, (96, 62, 70)),
                               (1.0, (52, 42, 66))])


def draw_river(cv, rng):
    left = [(640, 300), (760, 248), (900, 212), (1012, 132)]
    right = [(640, 468), (760, 520), (900, 556), (1012, 636)]

    def river_col(y):
        t = (y - 640) / 372.0
        if t < 0.45:
            return mix(RIVER_TOP, RIVER_MID, t / 0.45)
        return mix(RIVER_MID, RIVER_BOT, (t - 0.45) / 0.55)

    for y in range(640, 1012):
        xl = _interp_edge(left, y)
        xr = _interp_edge(right, y)
        cv.rect(int(xl), y, int(xr), y, fill=river_col(y))
    # sun column: gold dashes widening down the middle
    for i, y in enumerate(range(648, 1000, 10)):
        wdt = 10 + i * 2
        t = 0.55 - i * 0.012
        cv.line(384 - wdt, y, 384 + wdt, y, mix(GOLD, RIVER_MID, t), 1)
    # scattered shimmer across the whole river
    for _ in range(120):
        x = rng.randint(180, 590)
        y = rng.randint(660, 1000)
        ln = rng.randint(6, 34)
        col = rng.choice([mix(GOLD_LT, RIVER_MID, 0.5),
                          mix(CREAM, RIVER_MID, 0.6),
                          mix(RIVER_TOP, RIVER_MID, 0.4)])
        cv.line(x, y, x + ln, y, col, 1)
    # boulders along both banks: irregular dark rocks, not pills
    for (x, y, s) in [(240, 780, 22), (520, 800, 26), (210, 920, 30),
                      (560, 930, 24), (280, 700, 15), (490, 710, 17)]:
        cv.polygon([(x - s, y), (x - s // 2, y - s // 2),
                    (x + s // 2, y - s // 2), (x + s, y + 2),
                    (x + s // 3, y + s // 3),
                    (x - s // 2, y + s // 3)], fill=CLIFF_SH)
        cv.line(x - s // 2, y - s // 2, x + s // 2, y - s // 2,
                mix(CLIFF_LT, CLIFF_SH, 0.4), 1)


def draw_mist(cv, rng):
    # valley mist as clusters of small overlapping puffs — soft,
    # irregular edges, low contrast, never one flat shelf
    for _ in range(12):
        cx = rng.randint(230, 540)
        cy = rng.randint(625, 770)
        base = RIVER_TOP if cy < 700 else RIVER_MID
        for _ in range(6):
            px = cx + rng.randint(-55, 55)
            py = cy + rng.randint(-8, 8)
            rx = rng.randint(10, 30)
            ry = rng.randint(4, 8)
            col = mix(MIST, base, rng.uniform(0.55, 0.8))
            cv.ellipse(px - rx, py - ry, px + rx, py + ry, fill=col)
    # a few small puffs hugging the cliff bases
    for (cx, cy) in [(210, 660), (556, 672), (300, 740), (480, 748)]:
        for _ in range(4):
            px = cx + rng.randint(-30, 30)
            py = cy + rng.randint(-5, 5)
            rx = rng.randint(8, 22)
            ry = rng.randint(3, 6)
            cv.ellipse(px - rx, py - ry, px + rx, py + ry,
                       fill=mix(MIST, RIVER_MID, 0.65))


def draw_boat(cv):
    # a readable wooden boat with a glowing lantern, low on the river
    cv.disc(375, 874, 14, mix(GOLD, RIVER_BOT, 0.6))
    cv.polygon([(312, 902), (438, 902), (420, 922), (330, 922)],
               fill=ROCK_FG)
    cv.line(312, 902, 438, 902, GOLD, 2)
    cv.line(375, 902, 375, 884, ROCK_FG, 2)
    cv.disc(375, 880, 3, ROCK_FG)
    cv.disc(375, 874, 5, GOLD)
    cv.disc(375, 874, 2, GOLD_LT)
    # short reflection under the hull
    for i, y in enumerate(range(926, 978, 10)):
        wdt = 14 + i * 3
        cv.line(375 - wdt, y, 375 + wdt, y,
                mix(GOLD, RIVER_BOT, 0.35 + i * 0.05), 1)
    # a second, distant boat far up the river for depth
    cv.polygon([(424, 700), (452, 700), (446, 708), (430, 708)],
               fill=ROCK_FG)
    cv.disc(438, 694, 2, GOLD_LT)


def draw_foreground(cv, rng):
    # dark shore rocks framing the bottom corners, with shrubs
    cv.polygon([(0, 1012), (0, 948), (86, 908), (168, 946),
                (196, 1012)], fill=ROCK_FG)
    cv.polyline([(0, 948), (86, 908), (168, 946)], CLIFF_LT, 1)
    cv.polygon([(768, 1012), (768, 956), (690, 920), (624, 952),
                (600, 1012)], fill=ROCK_FG)
    cv.polyline([(768, 956), (690, 920), (624, 952)], CLIFF_LT, 1)
    for (x, y) in [(60, 940), (120, 962), (700, 950), (650, 972)]:
        cv.disc(x, y, 8, BUSH)
        cv.disc(x + 10, y + 4, 6, BUSH)
    # a tiny figure with a lantern on the right bank
    cv.disc(648, 906, 3, ROCK_FG)
    cv.line(648, 909, 648, 922, ROCK_FG, 2)
    cv.line(648, 922, 645, 932, ROCK_FG, 1)
    cv.line(648, 922, 651, 932, ROCK_FG, 1)
    cv.disc(656, 914, 3, GOLD_LT)


def draw_birds(cv):
    for (x, y, s) in [(200, 250, 7), (260, 228, 6), (540, 262, 7),
                      (600, 236, 5)]:
        cv.polyline([(x - s, y), (x, y - 4), (x + s, y)], CLIFF_SH, 1)


def draw_grain(cv, rng):
    """Fine painterly grain over the whole frame (seeded, subtle)."""
    for _ in range(26000):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        d = rng.randint(-14, 14)
        r, g, b = cv.get(x, y)
        cv._set(x, y, (max(0, min(255, r + d)),
                       max(0, min(255, g + d)),
                       max(0, min(255, b + d))))


def draw_frame(cv):
    cv.rect(12, 12, W - 13, H - 13, outline=CREAM, width=3)
    cv.rect(21, 21, W - 22, H - 22, outline=GOLD, width=1)


def draw_title(cv):
    draw_centered(cv, "serif_bold", 118, 384, 46, "KAVIRA", CREAM)
    cv.line(292, 180, 476, 180, GOLD, 2)
    sub = "THE GLASS BRIDGE"
    pitch = 23
    wdt = tracked_width(sub, pitch)
    draw_tracked(cv, "sans", 24, 384 - wdt / 2, 196, sub, GOLD, pitch)


# ------------------------------------------------------------------- main
def main():
    rng = random.Random(SEED)
    here = os.path.dirname(os.path.abspath(__file__))
    init_fonts(os.path.join(here, "fonts.bin"))

    cv = Canvas(W, H, SKY_TOP)
    draw_sky(cv)
    draw_clouds(cv, rng)
    draw_sun(cv)
    draw_birds(cv)
    draw_title(cv)
    draw_far_wall(cv, rng)
    draw_valley_floor(cv)
    draw_river(cv, rng)
    draw_left_cliff(cv, rng)
    draw_right_cliff(cv, rng)
    draw_bridge(cv, rng)
    draw_mist(cv, rng)
    draw_boat(cv)
    draw_foreground(cv, rng)
    draw_grain(cv, rng)
    draw_frame(cv)

    out = os.environ.get("OUTPUT", "/output/entry.png")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    write_png(cv, out)
    n = os.path.getsize(out)
    print(f"{out} {W}x{H} {n} bytes")


if __name__ == "__main__":
    main()
