"""Generate fonts.bin for the LUMARA poster: DejaVu (OFL) glyph atlas.
Master em size 80 px (big display type stays crisp); only the two
fonts the poster uses. Same FNT1 format as the passport atlas.
Run once here (PIL is available on this machine, not in the grader).
"""
import struct

from PIL import Image, ImageDraw, ImageFont

FONTS = [
    ("serif_bold", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
    ("sans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]
CHARS = [chr(c) for c in range(32, 127)] + ["\u2022"]
SIZE = 80

out = bytearray()
out += b"FNT1"
out += struct.pack("<I", len(FONTS))
for name, path in FONTS:
    font = ImageFont.truetype(path, SIZE)
    out += struct.pack("<B", len(name)) + name.encode()
    out += struct.pack("<I", len(CHARS))
    for ch in CHARS:
        advance = int(round(font.getlength(ch)))
        tmp = Image.new("L", (SIZE * 2, SIZE * 2), 0)
        d = ImageDraw.Draw(tmp)
        d.text((SIZE // 2, SIZE // 2), ch, font=font, fill=255)
        bbox = tmp.getbbox()
        if bbox is None or ch == " ":
            w = h = 0
            ox = oy = 0
            data = b""
        else:
            x0, y0, x1, y1 = bbox
            w, h = x1 - x0, y1 - y0
            ox = x0 - SIZE // 2
            oy = y0 - SIZE // 2
            data = tmp.crop(bbox).tobytes()
        out += struct.pack("<IHHHHhh", ord(ch), advance, w, h, 0, ox, oy)
        out += data
    print(name, "chars:", len(CHARS))

with open("fonts.bin", "wb") as f:
    f.write(out)
print("fonts.bin bytes:", len(out))
