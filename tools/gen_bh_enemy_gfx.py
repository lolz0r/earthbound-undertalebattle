#!/usr/bin/env python3
"""Every enemy's bullet sheet: four monochrome shapes (or one big one).

Bullets used to be the enemy's own battle sprite shrunk into 16x16 pieces. They are
now general-purpose white shapes in the Undertale manner: stars, rings, discs,
diamonds, crosses, lines, chevrons, crescents... Each enemy id (0-230) still gets
its own 32x32 "sheet" of four 16x16 sprites (types THEME0-3 in the attack programs),
chosen deterministically from the library below so that enemies differ from one
another, and enemies whose battle sprite is larger than 32 px keep one 32x32 shape
(the size classes drive the spacing of the generated attack programs, so they are
kept exactly as before). The sheets are drawn with the engine's own palette (white).

Outputs (in src/bin/bh):
  enemy_sheets_a.bin   sheets for ids 0-127  (512 bytes each)
  enemy_sheets_b.bin   sheets for ids 128-230
  bh_enemy_hitboxes.bin  231 x 4 x (half width, half height); bit 7 of the first
                         width flags a 32x32 sheet
  enemy_preview.png    contact sheet of a few enemies (needs PIL)
"""
import os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "ebsrc")
SIZES = {1: (1, 1), 2: (2, 1), 3: (1, 2), 4: (2, 2), 5: (4, 2), 6: (4, 4)}   # pieces (w, h)

def bitrev(b):
    return int(f"{b:08b}"[::-1], 2)

def exhal(data):
    """HAL Laboratory LZ decompression (as used by EarthBound's DECOMP)."""
    out = bytearray(); pos = 0
    while True:
        c = data[pos]; pos += 1
        if c == 0xFF:
            break
        method = c >> 5
        if method == 7:
            method = (c >> 2) & 7
            length = ((c & 3) << 8 | data[pos]) + 1; pos += 1
        else:
            length = (c & 0x1F) + 1
        if method == 0:
            out += data[pos:pos + length]; pos += length
        elif method == 1:
            out += bytes([data[pos]]) * length; pos += 1
        elif method == 2:
            out += bytes(data[pos:pos + 2]) * length; pos += 2
        elif method == 3:
            b = data[pos]; pos += 1
            out += bytes(((b + i) & 0xFF) for i in range(length))
        else:
            off = (data[pos] << 8) | data[pos + 1]; pos += 2
            for i in range(length):
                if method == 4:
                    out.append(out[off + i])
                elif method == 5:
                    out.append(bitrev(out[off + i]))
                else:
                    out.append(out[off - i])
    return bytes(out)

def decode_tile(b):
    px = [[0] * 8 for _ in range(8)]
    for y in range(8):
        p0, p1, p2, p3 = b[y * 2], b[y * 2 + 1], b[16 + y * 2], b[16 + y * 2 + 1]
        for x in range(8):
            bit = 7 - x
            px[y][x] = ((p0 >> bit) & 1) | (((p1 >> bit) & 1) << 1) | (((p2 >> bit) & 1) << 2) | (((p3 >> bit) & 1) << 3)
    return px

def encode_tile(px):
    out = bytearray()
    for planes in ((0, 1), (2, 3)):
        for y in range(8):
            for plane in planes:
                byte = 0
                for x in range(8):
                    if (px[y][x] >> plane) & 1:
                        byte |= 0x80 >> x
                out.append(byte)
    return bytes(out)

def sprite_image(data, size):
    """decompressed sprite -> 2D list of palette indices (W x H pixels)"""
    wp, hp = SIZES[size]
    W, H = wp * 32, hp * 32
    img = [[0] * W for _ in range(H)]
    for p in range(wp * hp):
        px0, py0 = (p % wp) * 32, (p // wp) * 32
        for t in range(16):
            off = (p * 16 + t) * 32
            if off + 32 > len(data):
                break
            tile = decode_tile(data[off:off + 32])
            tx, ty = px0 + (t % 4) * 8, py0 + (t // 4) * 8
            for y in range(8):
                img[ty + y][tx:tx + 8] = tile[y]
    return img

def bbox(img):
    ys = [y for y, row in enumerate(img) if any(row)]
    xs = [x for x in range(len(img[0])) if any(row[x] for row in img)]
    if not xs:
        return (0, 0, len(img[0]), len(img))
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)

def parse_enemies():
    text = open(os.path.join(ROOT, "src", "data", "battle", "enemies.asm")).read()
    blocks = text.split("PADDEDEBTEXT ")[1:]
    out = []
    for b in blocks:
        name = re.match(r'"([^"]*)"', b).group(1)
        sprite = int(re.search(r"\.WORD \$([0-9A-Fa-f]+) ;Battle sprite", b).group(1), 16)
        pal = int(re.search(r"\.BYTE \$([0-9A-Fa-f]+) ;Palette", b).group(1), 16)
        out.append((name, sprite, pal))
    return out

def sprite_sizes():
    text = open(os.path.join(ROOT, "src", "data", "battle", "battle_sprites_pointers.asm")).read()
    return [int(m) for m in re.findall(r"BATTLE_SPRITE_SIZE::_(\d+)X\d+", text)], \
           [{"32X32": 1, "64X32": 2, "32X64": 3, "64X64": 4, "128X64": 5, "128X128": 6}[m]
            for m in re.findall(r"BATTLE_SPRITE_SIZE::_(\d+X\d+)", text)]


WHITE = 1     # palette index of white in the engine's palette (tools/gen_bh_gfx.py)

# ---- shape rasterisers: n -> n x n grid of 0/1, drawn about the centre ----
import math, random

def raster(n, pred):
    return [[1 if pred(x + 0.5 - n / 2, y + 0.5 - n / 2) else 0 for x in range(n)] for y in range(n)]

def in_polygon(px, py, poly):
    inside = False
    for i in range(len(poly)):
        x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % len(poly)]
        if (y0 > py) != (y1 > py):
            xi = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
            if px < xi:
                inside = not inside
    return inside

def star_poly(n, points=5, inner=0.42):
    ro, ri = 0.48 * n, 0.48 * n * inner
    poly = []
    for k in range(points * 2):
        a = -math.pi / 2 + k * math.pi / points
        r = ro if k % 2 == 0 else ri
        poly.append((r * math.cos(a), r * math.sin(a)))
    return poly

def line_dist(x, y, ang):
    """distance from (x, y) to the line through the origin at angle ang"""
    return abs(-math.sin(ang) * x + math.cos(ang) * y)

def shape_star(n):     p = star_poly(n); return raster(n, lambda x, y: in_polygon(x, y, p))
def shape_ring(n):     return raster(n, lambda x, y: (0.30 * n) ** 2 <= x * x + y * y <= (0.46 * n) ** 2)
def shape_disc(n):     return raster(n, lambda x, y: x * x + y * y <= (0.40 * n) ** 2)
def shape_diamond(n):  return raster(n, lambda x, y: 0.30 * n <= abs(x) + abs(y) <= 0.47 * n)
def shape_plus(n):     w = 1.5 * n / 16; return raster(n, lambda x, y: (abs(x) < w or abs(y) < w) and max(abs(x), abs(y)) <= 0.45 * n)
def shape_x(n):        w = 1.1 * n / 16; return raster(n, lambda x, y: (abs(x - y) < w * 1.42 or abs(x + y) < w * 1.42) and max(abs(x), abs(y)) <= 0.42 * n)
def shape_triangle(n): return raster(n, lambda x, y: -0.42 * n <= y <= 0.36 * n and abs(x) <= (y + 0.42 * n) * 0.62)
def shape_vline(n):    w = 1.0 * n / 16; return raster(n, lambda x, y: abs(x) <= w and abs(y) <= 0.48 * n)
def shape_hline(n):    w = 1.0 * n / 16; return raster(n, lambda x, y: abs(y) <= w and abs(x) <= 0.48 * n)
def shape_square(n):   t = 2.0 * n / 16; return raster(n, lambda x, y: 0.44 * n - t <= max(abs(x), abs(y)) <= 0.44 * n)
def shape_chevron(n):  t = 1.2 * n / 16; return raster(n, lambda x, y: abs(x) <= 0.45 * n and abs(y - (abs(x) * 0.8 - 0.32 * n)) <= t)
def shape_crescent(n): return raster(n, lambda x, y: x * x + y * y <= (0.42 * n) ** 2 and (x - 0.16 * n) ** 2 + (y + 0.08 * n) ** 2 > (0.36 * n) ** 2)
def shape_asterisk(n): w = 1.0 * n / 16; return raster(n, lambda x, y: x * x + y * y <= (0.46 * n) ** 2 and min(line_dist(x, y, a) for a in (0, math.pi / 3, 2 * math.pi / 3)) <= w)
def shape_bowtie(n):   return raster(n, lambda x, y: abs(x) <= 0.44 * n and abs(y) <= abs(x) * 0.75)
def shape_dots(n):     r = 0.13 * n; return raster(n, lambda x, y: any((x - cx) ** 2 + (y - cy) ** 2 <= r * r for cx, cy in ((-0.28 * n, 0.28 * n), (0, 0), (0.28 * n, -0.28 * n))))
def shape_wave(n):     t = 1.0 * n / 16; return raster(n, lambda x, y: abs(x) <= 0.47 * n and abs(y - 0.22 * n * math.sin(x * 2 * math.pi / (0.94 * n))) <= t)

SHAPES = [("star", shape_star), ("ring", shape_ring), ("disc", shape_disc), ("diamond", shape_diamond),
          ("plus", shape_plus), ("x", shape_x), ("triangle", shape_triangle), ("vline", shape_vline),
          ("hline", shape_hline), ("square", shape_square), ("chevron", shape_chevron), ("crescent", shape_crescent),
          ("asterisk", shape_asterisk), ("bowtie", shape_bowtie), ("dots", shape_dots), ("wave", shape_wave)]
BIG_SHAPES = ["star", "ring", "diamond", "plus", "x", "triangle", "square", "asterisk", "chevron", "crescent"]
BY_NAME = dict(SHAPES)

def white(grid):
    return [[WHITE if v else 0 for v in row] for row in grid]

def hitbox(sp, big=False):
    x0, y0, x1, y1 = bbox(sp)
    lim = 13 if big else 6
    hw = max(1, min(lim, (x1 - x0) // 2 - 1))
    hh = max(1, min(lim, (y1 - y0) // 2 - 1))
    return (hw | 0x80, hh) if big else (hw, hh)   # bit 7 of the width flags a 32x32 bullet

def sheet_bytes(sprites):
    if len(sprites) == 1:          # one 32x32 sprite fills the whole piece
        piece = sprites[0]
    else:
        piece = [[0] * 32 for _ in range(32)]
        for i, sp in enumerate(sprites):
            ox, oy = (i % 2) * 16, (i // 2) * 16
            for y in range(16):
                piece[oy + y][ox:ox + 16] = sp[y]
    out = bytearray()
    for tr in range(4):
        for tc in range(4):
            out += encode_tile([[piece[tr * 8 + y][tc * 8 + x] for x in range(8)] for y in range(8)])
    return bytes(out)

def is_big(img):
    x0, y0, x1, y1 = bbox(img)
    return max(x1 - x0, y1 - y0) > 32

def shapes_for(eid, big):
    """the enemy's shapes: one 32x32 for big sprites, else four distinct 16x16 ones"""
    r = random.Random(eid * 7919 + 13)
    if big:
        nm = r.choice(BIG_SHAPES)
        return [BY_NAME[nm](32)], [nm]
    names = r.sample([s[0] for s in SHAPES], 4)
    return [BY_NAME[nm](16) for nm in names], names

def main():
    enemies = parse_enemies()
    _, sizes = sprite_sizes()
    sheets, boxes, previews = [], [], []
    cache = {}
    for eid, (name, sprite, pal) in enumerate(enemies):
        big = False
        if sprite != 0 and sprite - 1 < len(sizes):
            idx = sprite - 1
            if idx not in cache:
                path = os.path.join(ROOT, "src", "bin", "battle_sprites", f"{idx}.gfx.lzhal")
                if not os.path.exists(path):   # a few sprites differ per region and live under bin/US
                    path = os.path.join(ROOT, "src", "bin", "US", "battle_sprites", f"{idx}.gfx.lzhal")
                cache[idx] = is_big(sprite_image(exhal(open(path, "rb").read()), sizes[idx]))
            big = cache[idx]
        grids, names = shapes_for(eid, big)
        sprites = [white(g) for g in grids]
        sheets.append(sheet_bytes(sprites))
        boxes.append([hitbox(s, big) for s in sprites] * (4 if big else 1))
        previews.append((eid, name, names, sprites))
    outdir = os.path.join(ROOT, "src", "bin", "bh")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "enemy_sheets_a.bin"), "wb") as f:
        f.write(b"".join(sheets[:128]))
    with open(os.path.join(outdir, "enemy_sheets_b.bin"), "wb") as f:
        f.write(b"".join(sheets[128:]))
    with open(os.path.join(outdir, "bh_enemy_hitboxes.bin"), "wb") as f:
        for bx in boxes:
            for hw, hh in bx:
                f.write(bytes((hw, hh)))
    nbig = sum(1 for p in previews if len(p[3]) == 1)
    print(f"wrote {len(sheets)} enemy sheets ({sum(len(s) for s in sheets)} bytes, {nbig} big) and hit boxes to {outdir}")
    try:
        from PIL import Image
        ids = [int(a) for a in sys.argv[2:]] or [159, 81, 1, 121, 55, 93, 2, 34, 9, 32, 150, 88]
        cell = 16 * 3
        im = Image.new("RGB", (len(ids) * (4 * cell + 8), 2 * cell + 4), (40, 40, 40))
        for k, eid in enumerate(ids):
            _, name, names, sprites = previews[eid]
            for i, sp in enumerate(sprites):
                for y in range(len(sp)):
                    for x in range(len(sp[0])):
                        if sp[y][x]:
                            for dy in range(3):
                                for dx in range(3):
                                    im.putpixel((k * (4 * cell + 8) + i * cell + x * 3 + dx, y * 3 + dy), (255, 255, 255))
        im.save(os.path.join(outdir, "enemy_preview.png"))
        print("preview:", [(previews[e][1], previews[e][2]) for e in ids])
    except ImportError:
        pass

if __name__ == "__main__":
    main()
