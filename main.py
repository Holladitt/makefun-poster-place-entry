"""LUMARA — The Lantern Isles. make.fun entry: The Poster for a Place
That Isn't There.

Draws one travel poster (768x1024) to /output/entry.png. Stdlib only
(Python 3.13, no network, no external assets): a small software
rasterizer, a DejaVu glyph atlas read from fonts.bin beside this
file, and a hand-rolled PNG writer. Deterministic: same bytes every
run (seeded randomness only).

Concept: LUMARA, the Lantern Isles — a valley of floating islands
at dusk. One giant island carries a lantern village on its flat top
and pours waterfalls off its edges into the mist; two smaller
islands flank it. A pale full moon rises behind it, and a tiny
paper-lantern boat drifts on the still lake below, its gold
reflection leading the eye back up to the island. Palette: deep
indigo sky, warm gold lantern light, pale cream rock and type.
Name set in big DejaVu Serif Bold across the top, one short
subtitle line beneath it, nothing else.
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
SKY_TOP = (13, 22, 48)
SKY_MID = (26, 54, 82)
HORIZON = (74, 104, 116)
DUSK = (206, 148, 86)
MOON = (246, 233, 201)
MOON_DK = (226, 210, 170)
GOLD = (240, 180, 90)
GOLD_LT = (255, 215, 141)
CREAM = (247, 235, 212)
ROCK = (22, 35, 56)
ROCK_LT = (46, 68, 92)
LAKE = (16, 42, 60)
LAKE_LT = (34, 74, 94)
MIST = (168, 192, 196)


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


# ------------------------------------------------------------------ scene
def draw_sky(cv):
    cv.gradient(0, 0, W, 400, SKY_TOP, SKY_MID)
    cv.gradient(0, 400, W, 260, SKY_MID, HORIZON)
    # thin warm dusk band where sky meets the mist
    cv.gradient(0, 630, W, 34, HORIZON, mix(HORIZON, DUSK, 0.55))


def draw_stars(cv, rng):
    for _ in range(80):
        x = rng.randint(16, W - 16)
        y = rng.randint(16, 380)
        r = rng.choice([1, 1, 1, 2])
        col = rng.choice([CREAM, CREAM, GOLD_LT, mix(CREAM, SKY_TOP, 0.4)])
        cv.disc(x, y, r, col)
    # six four-point sparkles
    for _ in range(6):
        x = rng.randint(40, W - 40)
        y = rng.randint(40, 300)
        s = rng.randint(4, 7)
        cv.line(x - s, y, x + s, y, GOLD_LT, 1)
        cv.line(x, y - s, x, y + s, GOLD_LT, 1)
        cv.disc(x, y, 1, GOLD_LT)


def draw_moon(cv):
    # two-stage soft halo, then the disc, then a few faint craters
    cv.disc(625, 290, 72, mix(SKY_MID, MOON, 0.20))
    cv.disc(625, 290, 62, mix(SKY_MID, MOON, 0.42))
    cv.disc(625, 290, 54, MOON)
    cv.disc(608, 272, 9, MOON_DK)
    cv.disc(638, 300, 6, MOON_DK)
    cv.disc(618, 306, 4, MOON_DK)
    cv.disc(644, 272, 3, MOON_DK)


def draw_house(cv, x, ytop, w, h):
    """Tiny dark house with lit windows, sitting on ytop."""
    cv.rect(x, ytop - h, x + w, ytop, fill=ROCK)
    cv.polygon([(x - 2, ytop - h), (x + w // 2, ytop - h - 9),
                (x + w + 2, ytop - h)], fill=ROCK)
    cv.rect(x + 3, ytop - h + 4, x + 6, ytop - h + 8, fill=GOLD)
    if w >= 18:
        cv.rect(x + w - 7, ytop - h + 4, x + w - 4, ytop - h + 8,
                fill=GOLD)


def draw_lantern_post(cv, x, ybase, h=16):
    cv.line(x, ybase, x, ybase - h, ROCK, 1)
    cv.disc(x, ybase - h - 3, 6, mix(GOLD, SKY_MID, 0.45))
    cv.disc(x, ybase - h - 3, 3, GOLD)


def draw_island(cv, cx, top, half_w, point_y, houses=True):
    """Floating rock: flat plateau on top, cone with a bulging curve
    tapering to a point; the right face catches the moonlight."""
    hw = half_w
    hgt = point_y - top
    top_edge = [(cx - hw, top + 8), (cx - hw * 0.75, top),
                (cx - hw * 0.3, top + 5), (cx, top),
                (cx + hw * 0.3, top + 5), (cx + hw * 0.75, top),
                (cx + hw, top + 8)]
    # side profile as fractions of the island's height, so small
    # islets get the same curve instead of overshooting spikes
    left = [(cx - hw * 0.93, top + hgt * 0.25),
            (cx - hw * 0.78, top + hgt * 0.50),
            (cx - hw * 0.50, top + hgt * 0.75),
            (cx - hw * 0.22, top + hgt * 0.92)]
    right = [(cx + hw * 0.22, top + hgt * 0.92),
             (cx + hw * 0.50, top + hgt * 0.75),
             (cx + hw * 0.78, top + hgt * 0.50),
             (cx + hw * 0.93, top + hgt * 0.25)]
    cv.polygon(top_edge + right + [(cx, point_y)] + left, fill=ROCK)
    # moonlit facet: the whole right face, one flat lighter tone
    facet = [(cx, top), (cx + hw * 0.3, top + 5),
             (cx + hw * 0.75, top), (cx + hw, top + 8)] + right + \
        [(cx, point_y)]
    cv.polygon(facet, fill=mix(ROCK, ROCK_LT, 0.7))
    # a few rock facets on the cone
    cv.polyline([(cx - hw * 0.45, top + hgt * 0.38),
                 (cx - hw * 0.3, point_y - hgt * 0.45)], ROCK_LT, 1)
    cv.polyline([(cx + hw * 0.45, top + hgt * 0.45),
                 (cx + hw * 0.28, point_y - hgt * 0.38)], ROCK_LT, 1)
    if houses:
        # village along the plateau, windows lit
        draw_house(cv, cx - half_w + 26, top, 20, 15)
        draw_house(cv, cx - half_w + 62, top + 2, 16, 12)
        draw_house(cv, cx - 30, top - 1, 22, 16)
        draw_house(cv, cx + 12, top + 1, 18, 13)
        draw_house(cv, cx + half_w - 66, top, 20, 15)
        draw_lantern_post(cv, cx - half_w + 100, top)
        draw_lantern_post(cv, cx + half_w - 100, top + 2)
        # tiny cypress silhouettes
        cv.polygon([(cx - 52, top), (cx - 46, top - 22),
                    (cx - 40, top)], fill=ROCK)
        cv.polygon([(cx + 88, top + 1), (cx + 94, top - 18),
                    (cx + 100, top + 1)], fill=ROCK)


def draw_waterfall(cv, x, y0, y1, rng):
    """Two soft pale strands with a slight wobble, ending above
    the mist instead of scratching down into it."""
    for dx, wdt, col in [(0, 2, mix(MIST, CREAM, 0.4)),
                         (5, 1, mix(MIST, SKY_MID, 0.35))]:
        pts = []
        y = y0
        while y <= y1:
            pts.append((x + dx + int(2 * math.sin((y - y0) / 22.0)), y))
            y += 5
        cv.polyline(pts, col, wdt)


def draw_mist(cv):
    # a few small puffs clustered under the island and the falls,
    # plus one very faint wide haze — clouds, not a shelf
    cv.ellipse(300, 648, 468, 672, fill=mix(HORIZON, MIST, 0.28))
    cv.ellipse(120, 652, 280, 676, fill=mix(HORIZON, MIST, 0.20))
    cv.ellipse(500, 654, 640, 678, fill=mix(HORIZON, MIST, 0.20))
    cv.ellipse(180, 668, 588, 688, fill=mix(HORIZON, MIST, 0.12))


def draw_lake(cv, rng):
    cv.rect(0, 690, W - 1, 1011, fill=LAKE)
    # horizontal shimmer, denser toward the middle
    for _ in range(60):
        x = rng.randint(30, W - 60)
        y = rng.randint(710, 1000)
        ln = rng.randint(8, 42)
        col = rng.choice([LAKE_LT, LAKE_LT, mix(LAKE_LT, GOLD, 0.25)])
        cv.line(x, y, x + ln, y, col, 1)
    # varied gold dashes for the boat's reflection, no solid column
    for i, y in enumerate(range(902, 988, 9)):
        wdt = rng.randint(5, 12 + i * 3)
        t = 0.15 + i * 0.06
        cv.line(384 - wdt, y, 384 + wdt, y, mix(GOLD, LAKE, t), 1)
    # faint moon-glint on the water, tying the moon to the lake
    for y in range(720, 960, 14):
        wdt = rng.randint(6, 20)
        cv.line(625 - wdt, y, 625 + wdt, y, mix(GOLD, LAKE, 0.78), 1)


def draw_boat(cv):
    # a bigger, readable lantern boat on the lake, the human-scale cue
    cv.polygon([(334, 876), (434, 876), (416, 894), (352, 894)],
               fill=ROCK_LT)
    cv.line(334, 876, 434, 876, GOLD, 2)
    cv.line(384, 876, 384, 840, ROCK, 2)
    cv.disc(384, 836, 14, mix(GOLD, LAKE, 0.55))
    cv.disc(384, 836, 8, GOLD)
    cv.disc(384, 836, 3, GOLD_LT)
    # its reflection, short and close under the hull
    for i, y in enumerate(range(896, 962, 11)):
        wdt = 8 + i * 2
        cv.line(384 - wdt, y, 384 + wdt, y,
                mix(GOLD, LAKE, 0.3 + i * 0.06), 1)


def draw_foreground(cv):
    # small dark shore cliff, bottom left, with one lantern post
    cv.polygon([(12, 1012), (12, 968), (80, 928), (150, 918),
                (200, 958), (215, 1012)], fill=ROCK)
    cv.polyline([(12, 968), (80, 928), (150, 918), (200, 958)],
                ROCK_LT, 1)
    draw_lantern_post(cv, 148, 920, 18)


def draw_birds(cv):
    for (x, y, s) in [(255, 305, 7), (302, 282, 6), (210, 330, 5)]:
        cv.polyline([(x - s, y), (x, y - 4), (x + s, y)], ROCK, 1)


def draw_frame(cv):
    cv.rect(12, 12, W - 13, H - 13, outline=CREAM, width=3)
    cv.rect(21, 21, W - 22, H - 22, outline=GOLD, width=1)


def draw_title(cv):
    # name in big serif, then a gold rule and one short subtitle line
    draw_centered(cv, "serif_bold", 118, 384, 52, "LUMARA", CREAM)
    cv.line(292, 182, 476, 182, GOLD, 2)
    sub = "THE LANTERN ISLES"
    pitch = 24
    wdt = tracked_width(sub, pitch)
    draw_tracked(cv, "sans", 25, 384 - wdt / 2, 198, sub, GOLD, pitch)


# ------------------------------------------------------------------- main
def main():
    rng = random.Random(SEED)
    here = os.path.dirname(os.path.abspath(__file__))
    init_fonts(os.path.join(here, "fonts.bin"))

    cv = Canvas(W, H, SKY_TOP)
    draw_sky(cv)
    draw_stars(cv, rng)
    draw_moon(cv)
    draw_title(cv)
    # flanking islets first (behind the main island)
    draw_island(cv, 118, 348, 62, 452, houses=False)
    draw_house(cv, 96, 348, 16, 12)
    draw_lantern_post(cv, 140, 348, 14)
    draw_island(cv, 668, 372, 54, 470, houses=False)
    draw_house(cv, 648, 372, 15, 11)
    draw_lantern_post(cv, 690, 372, 14)
    draw_waterfall(cv, 118, 356, 500, rng)
    draw_waterfall(cv, 668, 380, 520, rng)
    # the one great island
    draw_island(cv, 384, 400, 234, 645, houses=True)
    draw_waterfall(cv, 185, 412, 606, rng)
    draw_waterfall(cv, 582, 412, 606, rng)
    draw_mist(cv)
    draw_birds(cv)
    draw_lake(cv, rng)
    draw_boat(cv)
    draw_foreground(cv)
    draw_frame(cv)

    out = os.environ.get("OUTPUT", "/output/entry.png")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    write_png(cv, out)
    n = os.path.getsize(out)
    print(f"{out} {W}x{H} {n} bytes")


if __name__ == "__main__":
    main()
