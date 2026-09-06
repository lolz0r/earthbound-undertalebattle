#!/usr/bin/env python3
"""Every enemy's bullet sheet: four monochrome shapes (or one big one) in its theme.

Bullets used to be the enemy's own battle sprite shrunk into 16x16 pieces. They are
now white shapes in the Undertale manner, drawn to suit the enemy: birds throw
feathers and wings, dogs bones and paw prints, robots gears and bolts, ghosts wisps
and skulls, cultists stars and eyes, piles of puke drips and splats... Each enemy id
(0-230) gets its own 32x32 "sheet" of four 16x16 sprites (types THEME0-3 in the attack
programs) drawn from its theme's shape list (THEMES below, chosen by name), so that
enemies of one theme still differ from one another; enemies whose battle sprite is
larger than 32 px keep one 32x32 shape (the size classes drive the spacing of the
generated attack programs, so they are kept exactly as before). The sheets are drawn
with the engine's own palette (white).

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

# ---------------------------------------------------------------------------
# shapes: predicates on normalised coordinates (u, v) in -1..1 about the centre,
# rasterised at 16 or 32 px; strokes are given in 16-px pixels and scale up
# ---------------------------------------------------------------------------
import math, random

def raster(n, pred):
    k = 2.0 / n
    return [[1 if pred((x + 0.5) * k - 1, (y + 0.5) * k - 1) else 0 for x in range(n)] for y in range(n)]

def px(n, p=1.0):
    """a stroke of p 16-px pixels in normalised units (a little heavier at 32 px)"""
    return p * (2.0 / n) * (1.0 if n <= 16 else 1.3)

def disc(u, v, cx, cy, r):
    return (u - cx) ** 2 + (v - cy) ** 2 <= r * r

def ellipse(u, v, cx, cy, rx, ry, ang=0.0):
    c, s = math.cos(ang), math.sin(ang)
    du, dv = u - cx, v - cy
    a, b = du * c + dv * s, -du * s + dv * c
    return (a / rx) ** 2 + (b / ry) ** 2 <= 1

def annulus(u, v, cx, cy, r0, r1):
    d = (u - cx) ** 2 + (v - cy) ** 2
    return r0 * r0 <= d <= r1 * r1

def seg(u, v, x0, y0, x1, y1, w):
    dx, dy = x1 - x0, y1 - y0
    l2 = dx * dx + dy * dy
    t = 0 if l2 == 0 else max(0.0, min(1.0, ((u - x0) * dx + (v - y0) * dy) / l2))
    return (u - (x0 + t * dx)) ** 2 + (v - (y0 + t * dy)) ** 2 <= w * w

def taper(u, v, x0, y0, x1, y1, w0, w1):
    """a segment whose half width goes from w0 at one end to w1 at the other"""
    dx, dy = x1 - x0, y1 - y0
    l2 = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((u - x0) * dx + (v - y0) * dy) / l2))
    w = w0 + (w1 - w0) * t
    return (u - (x0 + t * dx)) ** 2 + (v - (y0 + t * dy)) ** 2 <= w * w

def poly(u, v, pts):
    inside = False
    for i in range(len(pts)):
        x0, y0 = pts[i]; x1, y1 = pts[(i + 1) % len(pts)]
        if (y0 > v) != (y1 > v) and u < x0 + (v - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside

def rot(pts, ang, cx=0.0, cy=0.0):
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]

def rect(cx, cy, hw, hh, ang=0.0):
    return rot([(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)], ang, cx, cy)

def star_pts(points=5, ro=0.95, ri=0.4, ang=-math.pi / 2):
    return [((ro if k % 2 == 0 else ri) * math.cos(ang + k * math.pi / points),
             (ro if k % 2 == 0 else ri) * math.sin(ang + k * math.pi / points)) for k in range(points * 2)]

def ngon_pts(sides, r=0.9, ang=-math.pi / 2):
    return [(r * math.cos(ang + k * 2 * math.pi / sides), r * math.sin(ang + k * 2 * math.pi / sides)) for k in range(sides)]

def outline(pts, w):
    """the polygon's edges as strokes"""
    return lambda u, v: any(seg(u, v, pts[i][0], pts[i][1], pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1], w) for i in range(len(pts)))

def curve(u, v, fn, t0, t1, w, steps=24):
    """a stroke along the parametric curve fn(t) -> (x, y)"""
    p = fn(t0)
    for k in range(1, steps + 1):
        q = fn(t0 + (t1 - t0) * k / steps)
        if seg(u, v, p[0], p[1], q[0], q[1], w):
            return True
        p = q
    return False

def arc(cx, cy, r, a0, a1):
    return lambda t: (cx + r * math.cos(t), cy + r * math.sin(t)), a0, a1

# --- the library: name -> function(n) -> grid ---
LIB = {}
def shape(name):
    def deco(fn):
        LIB[name] = fn
        return fn
    return deco

# basic geometry
@shape("star")
def _(n): p = star_pts(); return raster(n, lambda u, v: poly(u, v, p))
@shape("star4")
def _(n): p = star_pts(4, 0.95, 0.3); return raster(n, lambda u, v: poly(u, v, p))
@shape("star6")
def _(n): p = star_pts(6, 0.95, 0.55); return raster(n, lambda u, v: poly(u, v, p))
@shape("pentagram")
def _(n): p = star_pts(5, 0.95, 0.38); o = outline(p, px(n, 0.7)); return raster(n, o)
@shape("ring")
def _(n): return raster(n, lambda u, v: annulus(u, v, 0, 0, 0.62, 0.92))
@shape("disc")
def _(n): return raster(n, lambda u, v: disc(u, v, 0, 0, 0.8))
@shape("diamond")
def _(n): return raster(n, lambda u, v: 0.6 <= abs(u) + abs(v) <= 0.94)
@shape("plus")
def _(n): w = px(n, 1.5); return raster(n, lambda u, v: (abs(u) < w or abs(v) < w) and max(abs(u), abs(v)) <= 0.9)
@shape("x")
def _(n): w = px(n, 1.1); return raster(n, lambda u, v: (seg(u, v, -0.8, -0.8, 0.8, 0.8, w) or seg(u, v, -0.8, 0.8, 0.8, -0.8, w)))
@shape("triangle")
def _(n): return raster(n, lambda u, v: -0.84 <= v <= 0.72 and abs(u) <= (v + 0.84) * 0.62)
@shape("vline")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: abs(u) <= w and abs(v) <= 0.96)
@shape("hline")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: abs(v) <= w and abs(u) <= 0.96)
@shape("square")
def _(n): t = px(n, 2.0); return raster(n, lambda u, v: 0.88 - t <= max(abs(u), abs(v)) <= 0.88)
@shape("chevron")
def _(n): w = px(n, 1.2); return raster(n, lambda u, v: seg(u, v, -0.85, 0.35, 0, -0.5, w) or seg(u, v, 0, -0.5, 0.85, 0.35, w))
@shape("crescent")
def _(n): return raster(n, lambda u, v: disc(u, v, 0, 0, 0.84) and not disc(u, v, 0.32, -0.16, 0.72))
@shape("asterisk")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: any(seg(u, v, -0.9 * math.cos(a), -0.9 * math.sin(a), 0.9 * math.cos(a), 0.9 * math.sin(a), w) for a in (0, math.pi / 3, 2 * math.pi / 3)))
@shape("bowtie")
def _(n): return raster(n, lambda u, v: abs(u) <= 0.88 and abs(v) <= abs(u) * 0.75)
@shape("dots")
def _(n): return raster(n, lambda u, v: any(disc(u, v, cx, cy, 0.24) for cx, cy in ((-0.56, 0.56), (0, 0), (0.56, -0.56))))
@shape("wave")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: abs(u) <= 0.94 and abs(v - 0.44 * math.sin(u * 2 * math.pi / 1.88)) <= w)
@shape("zigzag")
def _(n): w = px(n, 1.0); p = [(-0.9, 0.4), (-0.45, -0.4), (0, 0.4), (0.45, -0.4), (0.9, 0.4)]; return raster(n, lambda u, v: any(seg(u, v, p[i][0], p[i][1], p[i + 1][0], p[i + 1][1], w) for i in range(4)))
@shape("hexagon")
def _(n): p = ngon_pts(6, 0.92); return raster(n, lambda u, v: poly(u, v, p))
@shape("hexring")
def _(n): p = ngon_pts(6, 0.92); q = ngon_pts(6, 0.55); return raster(n, lambda u, v: poly(u, v, p) and not poly(u, v, q))
@shape("sparkle")
def _(n): p = star_pts(4, 0.98, 0.18); return raster(n, lambda u, v: poly(u, v, p))
@shape("spiral")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: curve(u, v, lambda t: (0.12 * t * math.cos(t), 0.12 * t * math.sin(t)), 0.5, 7.4, w, 60))
@shape("sun")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: disc(u, v, 0, 0, 0.45) or any(seg(u, v, 0.6 * math.cos(a), 0.6 * math.sin(a), 0.95 * math.cos(a), 0.95 * math.sin(a), w) for a in [k * math.pi / 4 for k in range(8)]))
@shape("oval")
def _(n): return raster(n, lambda u, v: ellipse(u, v, 0, 0, 0.55, 0.85))
@shape("arrow")
def _(n): w = px(n, 1.1); return raster(n, lambda u, v: seg(u, v, -0.9, 0, 0.6, 0, w) or poly(u, v, [(0.95, 0), (0.35, -0.5), (0.35, 0.5)]))
@shape("dash3")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: seg(u, v, -0.9, -0.55, 0.3, -0.55, w) or seg(u, v, -0.5, 0, 0.9, 0, w) or seg(u, v, -0.9, 0.55, 0.1, 0.55, w))

# flying things
@shape("feather")
def _(n): w = px(n, 0.7); return raster(n, lambda u, v: ellipse(u, v, 0, 0, 0.36, 0.9, 0.5) and not seg(u, v, -0.45, 0.8, 0.45, -0.8, w) and (u * math.cos(0.5) + v * math.sin(0.5)) > -0.9)
@shape("wing")
def _(n): w = px(n, 1.1); return raster(n, lambda u, v: curve(u, v, lambda t: (-0.9 + 0.9 * t, -0.2 - 0.6 * math.sin(t * math.pi)), 0, 1, w) or curve(u, v, lambda t: (0.9 * t, -0.2 - 0.6 * math.sin(t * math.pi)), 0, 1, w))
@shape("gull")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: curve(u, v, lambda t: (-0.9 + 0.9 * t, 0.2 - 0.7 * math.sin(t * math.pi) ** 0.6), 0, 1, w) or curve(u, v, lambda t: (0.9 * t, 0.2 - 0.7 * math.sin(t * math.pi) ** 0.6), 0, 1, w))
@shape("egg")
def _(n): return raster(n, lambda u, v: ellipse(u, v, 0, 0.05, 0.6, 0.85) and ((v > 0) or ellipse(u, v, 0, 0.05, 0.48, 0.85)))
@shape("beak")
def _(n): return raster(n, lambda u, v: poly(u, v, [(-0.9, -0.5), (0.9, 0.0), (-0.9, 0.5), (-0.5, 0.0)]))
@shape("cloud")
def _(n): return raster(n, lambda u, v: v <= 0.45 and (disc(u, v, -0.45, 0.2, 0.42) or disc(u, v, 0.1, -0.1, 0.55) or disc(u, v, 0.55, 0.2, 0.4) or (abs(u) <= 0.75 and 0.0 <= v <= 0.45)))
@shape("batwing")
def _(n): return raster(n, lambda u, v: poly(u, v, [(-0.95, -0.3), (-0.5, -0.65), (0, -0.4), (0.5, -0.65), (0.95, -0.3), (0.6, 0.3), (0.3, 0.05), (0, 0.55), (-0.3, 0.05), (-0.6, 0.3)]))
@shape("saucer")
def _(n): return raster(n, lambda u, v: ellipse(u, v, 0, 0.15, 0.95, 0.32) or (v <= 0.15 and disc(u, v, 0, 0.15, 0.5)))
@shape("planet")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: disc(u, v, 0, 0, 0.5) or (ellipse(u, v, 0, 0, 0.98, 0.3, -0.4) and not ellipse(u, v, 0, 0, 0.98 - 2 * w, 0.3 - 2 * w, -0.4)))
@shape("comet")
def _(n): return raster(n, lambda u, v: disc(u, v, 0.45, -0.45, 0.4) or taper(u, v, 0.35, -0.35, -0.95, 0.95, 0.28, 0.02))
@shape("moon")
def _(n): return raster(n, lambda u, v: disc(u, v, 0, 0, 0.9) and not disc(u, v, 0.4, -0.15, 0.78))
@shape("bee")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: (ellipse(u, v, 0, 0.15, 0.55, 0.4) and not (abs(u + 0.25) < w) and not (abs(u - 0.05) < w)) or ellipse(u, v, -0.25, -0.45, 0.35, 0.22, 0.4) or ellipse(u, v, 0.25, -0.45, 0.35, 0.22, -0.4) or taper(u, v, 0.55, 0.15, 0.95, 0.15, 0.12, 0.01))
@shape("stinger")
def _(n): return raster(n, lambda u, v: taper(u, v, -0.9, 0.7, 0.9, -0.7, 0.3, 0.02))
@shape("swarm")
def _(n): return raster(n, lambda u, v: any(disc(u, v, cx, cy, 0.16) for cx, cy in ((-0.6, -0.5), (0.1, -0.7), (0.6, -0.2), (-0.3, 0.0), (0.3, 0.4), (-0.6, 0.6), (0.7, 0.7))))
@shape("tentacle")
def _(n): return raster(n, lambda u, v: curve(u, v, lambda t: (-0.8 + 1.6 * t, 0.5 * math.sin(t * 2.6 * math.pi)), 0, 1, px(n, 1.4)) and True)
@shape("propeller")
def _(n): return raster(n, lambda u, v: disc(u, v, 0, 0, 0.22) or any(ellipse(u, v, 0.5 * math.cos(a), 0.5 * math.sin(a), 0.5, 0.2, a) for a in (0, 2 * math.pi / 3, 4 * math.pi / 3)))

# plants
@shape("leaf")
def _(n): w = px(n, 0.7); return raster(n, lambda u, v: (disc(u, v, -0.35, 0.35, 0.95) and disc(u, v, 0.35, -0.35, 0.95)) and not seg(u, v, -0.6, 0.6, 0.6, -0.6, w))
@shape("flower")
def _(n): return raster(n, lambda u, v: disc(u, v, 0, 0, 0.3) or any(disc(u, v, 0.58 * math.cos(a), 0.58 * math.sin(a), 0.36) for a in [k * 2 * math.pi / 5 - math.pi / 2 for k in range(5)]))
@shape("seed")
def _(n): return raster(n, lambda u, v: ellipse(u, v, 0, 0, 0.42, 0.78, 0.6))
@shape("mushroom")
def _(n): return raster(n, lambda u, v: (v <= 0.05 and disc(u, v, 0, 0.05, 0.85)) or (abs(u) <= 0.28 and 0.0 <= v <= 0.9))
@shape("thorn")
def _(n): return raster(n, lambda u, v: poly(u, v, [(-0.9, 0.9), (-0.3, -0.9), (0.9, -0.3), (-0.2, 0.2)]))
@shape("twig")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: seg(u, v, -0.8, 0.9, 0.5, -0.9, w) or seg(u, v, -0.35, 0.2, -0.9, -0.3, w) or seg(u, v, 0.15, -0.4, 0.8, -0.2, w))
@shape("spores")
def _(n): return raster(n, lambda u, v: any(disc(u, v, cx, cy, r) for cx, cy, r in ((-0.5, -0.4, 0.3), (0.45, -0.55, 0.22), (0.3, 0.35, 0.34), (-0.55, 0.6, 0.2))))
@shape("acorn")
def _(n): return raster(n, lambda u, v: (v <= -0.05 and disc(u, v, 0, -0.05, 0.8) and v >= -0.85) or (v > -0.05 and ellipse(u, v, 0, -0.05, 0.6, 0.9) and v <= 0.85) or (abs(u) < 0.12 and -0.98 <= v <= -0.6))
@shape("vine")
def _(n): w = px(n, 1.1); return raster(n, lambda u, v: curve(u, v, lambda t: (-0.9 + 1.8 * t, 0.5 * math.sin(t * 4.5)), 0, 1, w) or disc(u, v, 0.45, -0.55, 0.22))

# beasts
@shape("bone")
def _(n): w = px(n, 1.3); return raster(n, lambda u, v: seg(u, v, -0.55, 0.55, 0.55, -0.55, w) or any(disc(u, v, cx, cy, 0.3) for cx, cy in ((-0.72, 0.42), (-0.42, 0.72), (0.72, -0.42), (0.42, -0.72))))
@shape("paw")
def _(n): return raster(n, lambda u, v: ellipse(u, v, 0, 0.35, 0.5, 0.42) or any(disc(u, v, cx, cy, 0.22) for cx, cy in ((-0.65, -0.15), (-0.25, -0.55), (0.25, -0.55), (0.65, -0.15))))
@shape("fang")
def _(n): return raster(n, lambda u, v: poly(u, v, [(-0.55, -0.9), (0.55, -0.9), (0.35, -0.2), (0.0, 0.95), (-0.35, -0.2)]))
@shape("claws")
def _(n): return raster(n, lambda u, v: any(taper(u, v, x0, -0.9, x0 + 0.5, 0.9, 0.16, 0.02) for x0 in (-0.85, -0.35, 0.15)))
@shape("horn")
def _(n): return raster(n, lambda u, v: curve(u, v, lambda t: (-0.7 + 1.4 * t, 0.7 - 1.6 * t * t), 0, 1, px(n, 2.2) * (1 - 0.8 * ((u + 0.7) / 1.4 if -0.7 <= u <= 0.7 else 0))))
@shape("hoof")
def _(n): w = px(n, 1.6); return raster(n, lambda u, v: curve(u, v, lambda t: (0.6 * math.cos(t), 0.5 * math.sin(t) + 0.1), 0.2, math.pi - 0.2, w) or seg(u, v, -0.55, -0.85, -0.55, 0.15, w) or seg(u, v, 0.55, -0.85, 0.55, 0.15, w))
@shape("fish")
def _(n): return raster(n, lambda u, v: ellipse(u, v, -0.15, 0, 0.65, 0.4) or poly(u, v, [(0.4, 0), (0.95, -0.5), (0.95, 0.5)]))
@shape("bubble")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: annulus(u, v, 0, 0, 0.85 - 2 * w, 0.85) or disc(u, v, -0.35, -0.35, 0.16))
@shape("drop")
def _(n): return raster(n, lambda u, v: disc(u, v, 0, 0.3, 0.55) or poly(u, v, [(0, -0.95), (-0.5, 0.15), (0.5, 0.15)]))
@shape("cheese")
def _(n): return raster(n, lambda u, v: poly(u, v, [(-0.9, 0.75), (0.9, 0.75), (0.9, -0.2), (-0.9, -0.85)]) and not disc(u, v, 0.0, 0.3, 0.2) and not disc(u, v, 0.55, 0.1, 0.15) and not disc(u, v, -0.5, 0.15, 0.13))
@shape("whiskers")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: disc(u, v, 0, 0, 0.28) or any(seg(u, v, 0, 0, 0.95 * math.cos(a), 0.95 * math.sin(a), w) for a in (0.35, 0, -0.35, math.pi - 0.35, math.pi, math.pi + 0.35)))
@shape("lilypad")
def _(n): return raster(n, lambda u, v: disc(u, v, 0, 0, 0.85) and not poly(u, v, [(0, 0), (1, -0.45), (1, 0.15)]))
@shape("footprint")
def _(n): return raster(n, lambda u, v: ellipse(u, v, 0, 0.35, 0.42, 0.5) or any(ellipse(u, v, cx, cy, 0.18, 0.32, a) for cx, cy, a in ((-0.55, -0.35, 0.5), (0, -0.6, 0), (0.55, -0.35, -0.5))))
@shape("tooth")
def _(n): return raster(n, lambda u, v: poly(u, v, [(-0.65, -0.9), (0.65, -0.9), (0.55, 0.1), (0.2, 0.9), (0.05, 0.2), (-0.2, 0.9), (-0.55, 0.1)]))
@shape("scale")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: (disc(u, v, 0, -0.3, 0.9) and v >= -0.3 and not disc(u, v, 0, -0.3, 0.9 - 2 * w)) or (disc(u, v, 0, 0.3, 0.9) and v >= 0.3 and not disc(u, v, 0, 0.3, 0.9 - 2 * w)))
@shape("snake")
def _(n): return raster(n, lambda u, v: curve(u, v, lambda t: (-0.85 + 1.7 * t, 0.6 * math.sin(t * 2 * math.pi + 0.5)), 0, 1, px(n, 1.5)) or disc(u, v, 0.85, 0.6 * math.sin(2 * math.pi + 0.5), 0.2))
@shape("worm")
def _(n): return raster(n, lambda u, v: any(disc(u, v, -0.75 + 0.5 * k, 0.35 * math.sin(k * 1.6), 0.27) for k in range(4)))
@shape("ear")
def _(n): return raster(n, lambda u, v: disc(u, v, 0, 0, 0.85) and not disc(u, v, 0, 0.1, 0.45))
@shape("curl")
def _(n): w = px(n, 1.2); return raster(n, lambda u, v: curve(u, v, lambda t: (0.14 * t * math.cos(t) - 0.1, 0.14 * t * math.sin(t)), 1.0, 6.5, w, 50))

# insects
@shape("web")
def _(n): w = px(n, 0.6); return raster(n, lambda u, v: any(seg(u, v, 0, 0, 0.95 * math.cos(a), 0.95 * math.sin(a), w) for a in [k * math.pi / 4 for k in range(8)]) or annulus(u, v, 0, 0, 0.3 - w, 0.3 + w) or annulus(u, v, 0, 0, 0.62 - w, 0.62 + w))
@shape("spider")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: disc(u, v, 0, 0.1, 0.38) or disc(u, v, 0, -0.42, 0.24) or any(seg(u, v, 0, 0, 0.95 * math.cos(a), 0.95 * math.sin(a), w) for a in (0.3, 0.75, 2.4, 2.85, math.pi + 0.3, math.pi + 0.75, math.pi - 0.3 - math.pi, -0.75)))
@shape("antenna")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: seg(u, v, 0, 0.9, 0, -0.1, w) or seg(u, v, 0, -0.1, -0.6, -0.8, w) or seg(u, v, 0, -0.1, 0.6, -0.8, w) or disc(u, v, -0.6, -0.8, 0.16) or disc(u, v, 0.6, -0.8, 0.16))
@shape("ant")
def _(n): w = px(n, 0.7); return raster(n, lambda u, v: any(ellipse(u, v, cx, 0, rx, 0.28) for cx, rx in ((-0.62, 0.3), (0, 0.25), (0.6, 0.36))) or any(seg(u, v, 0, 0, 0.7 * math.cos(a), 0.7 * math.sin(a), w) for a in (0.9, 2.2, -0.9, -2.2, 1.5, -1.5)))
@shape("slug")
def _(n): return raster(n, lambda u, v: (v >= -0.1 and ellipse(u, v, 0, 0.2, 0.9, 0.5)) or seg(u, v, 0.5, -0.1, 0.35, -0.75, px(n, 0.8)) or seg(u, v, 0.75, -0.1, 0.85, -0.75, px(n, 0.8)))
@shape("cocoon")
def _(n): w = px(n, 0.6); return raster(n, lambda u, v: ellipse(u, v, 0, 0, 0.5, 0.9) and not (abs(v + 0.4) < w or abs(v) < w or abs(v - 0.4) < w))
@shape("smiley")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: annulus(u, v, 0, 0, 0.9 - 2 * w, 0.9) or disc(u, v, -0.32, -0.28, 0.14) or disc(u, v, 0.32, -0.28, 0.14) or curve(u, v, lambda t: (0.5 * math.cos(t), 0.5 * math.sin(t) - 0.05), 0.4, math.pi - 0.4, w))

# robots
@shape("gear")
def _(n): return raster(n, lambda u, v: (disc(u, v, 0, 0, 0.62) or any(poly(u, v, rect(0.72 * math.cos(a), 0.72 * math.sin(a), 0.2, 0.22, a)) for a in [k * math.pi / 4 for k in range(8)])) and not disc(u, v, 0, 0, 0.24))
@shape("bolt")
def _(n): p = ngon_pts(6, 0.92); return raster(n, lambda u, v: poly(u, v, p) and not disc(u, v, 0, 0, 0.36))
@shape("lightning")
def _(n): return raster(n, lambda u, v: poly(u, v, [(0.15, -0.95), (-0.6, 0.1), (-0.05, 0.1), (-0.3, 0.95), (0.6, -0.15), (0.05, -0.15)]))
@shape("reticle")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: annulus(u, v, 0, 0, 0.62 - 2 * w, 0.62) or (abs(u) < w and abs(v) <= 0.95) or (abs(v) < w and abs(u) <= 0.95))
@shape("screw")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: disc(u, v, 0, 0, 0.85) and not seg(u, v, -0.5, -0.5, 0.5, 0.5, w))
@shape("laser")
def _(n): return raster(n, lambda u, v: abs(v) <= px(n, 1.5) and abs(u) <= 0.98 or (abs(v) <= px(n, 0.5) and abs(u) <= 0.98))
@shape("bullet")
def _(n): return raster(n, lambda u, v: (abs(v) <= 0.32 and -0.9 <= u <= 0.3) or (u > 0.3 and ellipse(u, v, 0.3, 0, 0.65, 0.32)))
@shape("bomb")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: disc(u, v, -0.1, 0.2, 0.68) or seg(u, v, 0.3, -0.4, 0.55, -0.7, w) or curve(u, v, lambda t: (0.55 + 0.3 * math.sin(t), -0.7 - 0.3 * (1 - math.cos(t))), 0, 2.5, w))
@shape("target")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: annulus(u, v, 0, 0, 0.92 - 2 * w, 0.92) or annulus(u, v, 0, 0, 0.5 - 2 * w, 0.5) or disc(u, v, 0, 0, 0.15))
@shape("nut")
def _(n): p = ngon_pts(6, 0.92, 0); return raster(n, lambda u, v: poly(u, v, p) and not poly(u, v, ngon_pts(6, 0.4, 0)))
@shape("wrench")
def _(n): w = px(n, 1.2); return raster(n, lambda u, v: seg(u, v, -0.6, 0.6, 0.35, -0.35, w) or (disc(u, v, 0.55, -0.55, 0.42) and not poly(u, v, [(0.45, -0.75), (0.95, -0.95), (0.95, -0.45)])))
@shape("plug")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: poly(u, v, [(-0.7, -0.2), (0.7, -0.2), (0.7, 0.55), (0.35, 0.9), (-0.35, 0.9), (-0.7, 0.55)]) or seg(u, v, -0.35, -0.2, -0.35, -0.9, w) or seg(u, v, 0.35, -0.2, 0.35, -0.9, w))
@shape("eyeball")
def _(n): return raster(n, lambda u, v: (disc(u, v, 0, 0.5, 0.95) and disc(u, v, 0, -0.5, 0.95)) and not annulus(u, v, 0, 0, 0.2, 0.4))

# ghosts and spirits
@shape("wisp")
def _(n): return raster(n, lambda u, v: curve(u, v, lambda t: (0.3 * math.sin(t * 5) * (1 - t), -0.9 + 1.8 * t), 0, 1, px(n, 2.4) * (1.2 - t_of(u, v))) if False else (disc(u, v, 0, -0.45, 0.42) or taper(u, v, 0, -0.3, 0.1, 0.9, 0.4, 0.05)))
@shape("ghost")
def _(n): return raster(n, lambda u, v: (disc(u, v, 0, -0.3, 0.6) or (abs(u) <= 0.6 and -0.3 <= v <= 0.6)) and not any(disc(u, v, cx, 0.72, 0.18) for cx in (-0.4, 0.0, 0.4)) and not disc(u, v, -0.22, -0.35, 0.12) and not disc(u, v, 0.22, -0.35, 0.12) and v <= 0.72 + 0.001 or (abs(u) <= 0.6 and 0.6 <= v <= 0.9 and not any(disc(u, v, cx, 0.9, 0.2) for cx in (-0.4, 0.0, 0.4))))
@shape("skull")
def _(n): return raster(n, lambda u, v: ((disc(u, v, 0, -0.2, 0.68) or (abs(u) <= 0.42 and 0.2 <= v <= 0.75)) and not disc(u, v, -0.28, -0.22, 0.18) and not disc(u, v, 0.28, -0.22, 0.18) and not (abs(u) < 0.06 and 0.4 <= v <= 0.75) and not (abs(u - 0.24) < 0.06 and 0.4 <= v <= 0.75) and not (abs(u + 0.24) < 0.06 and 0.4 <= v <= 0.75)))
@shape("hourglass")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: (abs(v) <= 0.85 and abs(u) <= 0.15 + 0.6 * abs(v) and abs(u) >= 0.15 + 0.6 * abs(v) - 2.2 * w) or (abs(abs(v) - 0.85) < w and abs(u) <= 0.7) or (abs(u) <= 0.5 * (abs(v) - 0.25) and abs(v) > 0.25 and abs(v) < 0.8))
@shape("hand")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: ellipse(u, v, 0, 0.45, 0.5, 0.4) or any(seg(u, v, x, 0.2, x * 1.2, -0.85 + abs(x) * 0.5, w) for x in (-0.45, -0.15, 0.15, 0.45)) or seg(u, v, -0.4, 0.4, -0.85, 0.0, w))
@shape("cross")
def _(n): w = px(n, 1.4); return raster(n, lambda u, v: (abs(u) < w and abs(v) <= 0.95) or (abs(v + 0.35) < w and abs(u) <= 0.65))
@shape("eye")
def _(n): return raster(n, lambda u, v: (disc(u, v, 0, 0.6, 0.98) and disc(u, v, 0, -0.6, 0.98)) and not annulus(u, v, 0, 0, 0.18, 0.42))
@shape("tombstone")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: ((disc(u, v, 0, -0.35, 0.6) and v <= -0.35) or (abs(u) <= 0.6 and -0.35 <= v <= 0.9)) and not (abs(v + 0.2) < w and abs(u) < 0.3) and not (abs(u) < w and -0.5 < v < 0.1))

# psychic and magic
@shape("dice")
def _(n): return raster(n, lambda u, v: max(abs(u), abs(v)) <= 0.85 and not any(disc(u, v, cx, cy, 0.17) for cx, cy in ((-0.45, -0.45), (0, 0), (0.45, 0.45))))
@shape("note")
def _(n): w = px(n, 1.1); return raster(n, lambda u, v: ellipse(u, v, -0.35, 0.6, 0.42, 0.3, -0.4) or seg(u, v, 0.02, 0.6, 0.02, -0.9, w) or poly(u, v, [(0.02, -0.9), (0.02, -0.3), (0.7, -0.15), (0.7, -0.6)]))
@shape("record")
def _(n): w = px(n, 0.7); return raster(n, lambda u, v: disc(u, v, 0, 0, 0.92) and not disc(u, v, 0, 0, 0.14) and not annulus(u, v, 0, 0, 0.42, 0.42 + 2 * w) and not annulus(u, v, 0, 0, 0.68, 0.68 + 2 * w))
@shape("pyramid")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: poly(u, v, [(0, -0.9), (0.95, 0.75), (-0.95, 0.75)]) and not poly(u, v, [(0, -0.9 + 3 * w), (0.95 - 3.6 * w, 0.75 - w), (-0.95 + 3.6 * w, 0.75 - w)]) or (abs(v - 0.2) < w and abs(u) < 0.45))
@shape("ankh")
def _(n): w = px(n, 1.2); return raster(n, lambda u, v: annulus(u, v, 0, -0.5, 0.3 - w, 0.3 + w) or (abs(u) < w and -0.2 <= v <= 0.95) or (abs(v - 0.05) < w and abs(u) <= 0.7))
@shape("eye2")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: (disc(u, v, 0, 0.6, 0.98) and disc(u, v, 0, -0.6, 0.98) and not (disc(u, v, 0, 0.6, 0.98 - 2 * w) and disc(u, v, 0, -0.6, 0.98 - 2 * w))) or disc(u, v, 0, 0, 0.25))
@shape("orb")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: disc(u, v, 0, 0, 0.85) and not disc(u, v, -0.3, -0.3, 0.2) and not annulus(u, v, 0, 0, 0.55, 0.55 + 2 * w))
@shape("bolt2")
def _(n): return raster(n, lambda u, v: poly(u, v, [(-0.2, -0.95), (0.45, -0.95), (0.05, -0.2), (0.5, -0.2), (-0.35, 0.95), (-0.1, 0.15), (-0.55, 0.15)]))
@shape("cardsuit")
def _(n): return raster(n, lambda u, v: disc(u, v, -0.4, -0.2, 0.42) or disc(u, v, 0.4, -0.2, 0.42) or disc(u, v, 0, -0.6, 0.42) or poly(u, v, [(0, -0.3), (0.55, 0.45), (-0.55, 0.45)]) or (abs(u) < 0.14 and 0.3 <= v <= 0.9))
@shape("hat")
def _(n): return raster(n, lambda u, v: ellipse(u, v, 0, 0.35, 0.95, 0.3) or poly(u, v, [(-0.5, 0.35), (0.5, 0.35), (0.1, -0.95), (-0.1, -0.95)]))
@shape("question")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: curve(u, v, lambda t: (0.45 * math.cos(t), -0.45 + 0.45 * math.sin(t)), -math.pi, 0.5, w) or seg(u, v, 0.4, -0.25, 0, 0.1, w) or seg(u, v, 0, 0.1, 0, 0.4, w) or disc(u, v, 0, 0.8, 0.17))

# people
@shape("badge")
def _(n): p = star_pts(7, 0.95, 0.65); return raster(n, lambda u, v: poly(u, v, p) and not disc(u, v, 0, 0, 0.3))
@shape("shield")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: poly(u, v, [(-0.85, -0.85), (0.85, -0.85), (0.85, 0.1), (0, 0.9), (-0.85, 0.1)]) and not (abs(u) < w and -0.6 <= v <= 0.6) and not (abs(v + 0.25) < w and abs(u) < 0.6))
@shape("skateboard")
def _(n): return raster(n, lambda u, v: ellipse(u, v, 0, -0.15, 0.95, 0.3) or disc(u, v, -0.5, 0.45, 0.22) or disc(u, v, 0.5, 0.45, 0.22))
@shape("peace")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: annulus(u, v, 0, 0, 0.9 - 2 * w, 0.9) or (abs(u) < w and abs(v) <= 0.9) or seg(u, v, 0, 0, -0.62, 0.62, w) or seg(u, v, 0, 0, 0.62, 0.62, w))
@shape("check")
def _(n): w = px(n, 1.3); return raster(n, lambda u, v: seg(u, v, -0.85, 0.05, -0.3, 0.7, w) or seg(u, v, -0.3, 0.7, 0.85, -0.7, w))
@shape("shard")
def _(n): return raster(n, lambda u, v: poly(u, v, [(-0.6, -0.95), (0.3, -0.5), (0.9, 0.2), (0.1, 0.95), (-0.2, 0.3), (-0.9, 0.1)]))
@shape("fist")
def _(n): w = px(n, 0.7); return raster(n, lambda u, v: (max(abs(u), abs(v + 0.05)) <= 0.7 and disc(u, v, 0, 0, 0.95)) and not any(abs(u - x) < w and -0.75 <= v <= 0.15 for x in (-0.35, 0, 0.35)) and not (abs(v - 0.2) < w and abs(u) <= 0.7))
@shape("purse")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: (abs(u) <= 0.75 and -0.2 <= v <= 0.85 and not (abs(v - 0.3) < w and abs(u) < 0.5)) or curve(u, v, lambda t: (0.5 * math.cos(t), -0.2 - 0.6 * math.sin(t)), 0.15, math.pi - 0.15, w))
@shape("coin")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: disc(u, v, 0, 0, 0.88) and not annulus(u, v, 0, 0, 0.6, 0.6 + 2 * w) and not (abs(u) < w and abs(v) < 0.42) and not (abs(v) < w and abs(u) < 0.3))
@shape("knife")
def _(n): return raster(n, lambda u, v: poly(u, v, [(-0.9, 0.9), (-0.55, 0.55), (0.35, -0.35), (0.85, -0.85), (0.95, -0.55), (0.55, 0.05), (-0.35, 0.75)]) or seg(u, v, -0.75, 0.35, -0.35, 0.75, px(n, 1.2)))
@shape("exclaim")
def _(n): return raster(n, lambda u, v: (abs(u) <= 0.2 - 0.08 * (v + 0.9) and -0.95 <= v <= 0.35) or disc(u, v, 0, 0.72, 0.2))
@shape("noose")
def _(n): w = px(n, 1.1); return raster(n, lambda u, v: (abs(u) < w and -0.95 <= v <= -0.2) or annulus(u, v, 0, 0.35, 0.5 - w, 0.5 + w))
@shape("key")
def _(n): w = px(n, 1.1); return raster(n, lambda u, v: annulus(u, v, -0.5, -0.4, 0.3 - w, 0.3 + w) or seg(u, v, -0.28, -0.18, 0.8, 0.9, w) or seg(u, v, 0.55, 0.65, 0.8, 0.4, w) or seg(u, v, 0.35, 0.45, 0.6, 0.2, w))

# slime and fire
@shape("blob")
def _(n): return raster(n, lambda u, v: math.hypot(u, v) <= 0.72 + 0.16 * math.sin(3 * math.atan2(v, u) + 0.7) + 0.06 * math.sin(7 * math.atan2(v, u)))
@shape("drip")
def _(n): return raster(n, lambda u, v: (v <= -0.2 and abs(u) <= 0.9 and v >= -0.9) or taper(u, v, -0.45, -0.2, -0.45, 0.6, 0.2, 0.08) or taper(u, v, 0.3, -0.2, 0.3, 0.9, 0.24, 0.1) or disc(u, v, 0.3, 0.8, 0.18))
@shape("splat")
def _(n): return raster(n, lambda u, v: disc(u, v, 0, 0, 0.5) or any(ellipse(u, v, 0.55 * math.cos(a), 0.55 * math.sin(a), 0.4, 0.2, a) for a in (0.3, 1.4, 2.6, 3.9, 5.1)))
@shape("bubbles")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: annulus(u, v, -0.4, 0.35, 0.42 - 2 * w, 0.42) or annulus(u, v, 0.45, -0.2, 0.34 - 2 * w, 0.34) or annulus(u, v, -0.15, -0.65, 0.2 - 2 * w, 0.2))
@shape("gas")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: any(curve(u, v, lambda t, x=x: (x + 0.18 * math.sin(t * 3.5 + x), -0.9 + 1.8 * t), 0, 1, w) for x in (-0.5, 0.0, 0.5)))
@shape("flame")
def _(n): return raster(n, lambda u, v: (v >= 0 and disc(u, v, 0, 0.15, 0.62) and v <= 0.75) or poly(u, v, [(0.1, -0.95), (0.62, 0.15), (-0.62, 0.15), (-0.25, -0.35)]) and not (disc(u, v, 0.05, 0.35, 0.28) and v > 0.1))
@shape("spark")
def _(n): p = star_pts(4, 0.98, 0.22, -math.pi / 2); q = star_pts(4, 0.55, 0.12, -math.pi / 4); return raster(n, lambda u, v: poly(u, v, p) or poly(u, v, q))
@shape("ember")
def _(n): return raster(n, lambda u, v: any(disc(u, v, cx, cy, r) for cx, cy, r in ((0, 0.3, 0.4), (-0.45, -0.3, 0.22), (0.5, -0.45, 0.18), (0.1, -0.75, 0.14))))
@shape("smoke")
def _(n): return raster(n, lambda u, v: disc(u, v, -0.3, 0.45, 0.42) or disc(u, v, 0.2, 0.1, 0.5) or disc(u, v, -0.15, -0.4, 0.34) or disc(u, v, 0.35, -0.65, 0.25))

# objects
@shape("cup")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: (poly(u, v, [(-0.65, -0.3), (0.45, -0.3), (0.35, 0.85), (-0.55, 0.85)])) or curve(u, v, lambda t: (0.45 + 0.35 * math.sin(t), -0.05 + 0.4 * (1 - math.cos(t))), 0, math.pi, w) or curve(u, v, lambda t: (-0.3 + 0.1 * math.sin(t * 6), -0.45 - 0.5 * t), 0, 1, px(n, 0.6)) or curve(u, v, lambda t: (0.05 + 0.1 * math.sin(t * 6 + 1), -0.45 - 0.5 * t), 0, 1, px(n, 0.6)))
@shape("sign")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: poly(u, v, [(-0.9, -0.85), (0.5, -0.85), (0.95, -0.35), (0.5, 0.15), (-0.9, 0.15)]) and not (abs(v + 0.35) < w and -0.7 <= u <= 0.4) or (abs(u + 0.3) < w and 0.15 <= v <= 0.95))
@shape("clock")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: annulus(u, v, 0, 0, 0.9 - 2 * w, 0.9) or seg(u, v, 0, 0, 0, -0.6, w) or seg(u, v, 0, 0, 0.45, 0.2, w))
@shape("wheel")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: annulus(u, v, 0, 0, 0.9 - 2.6 * w, 0.9) or disc(u, v, 0, 0, 0.22) or any(seg(u, v, 0, 0, 0.8 * math.cos(a), 0.8 * math.sin(a), w) for a in [k * math.pi / 3 for k in range(6)]))
@shape("tent")
def _(n): w = px(n, 0.9); return raster(n, lambda u, v: poly(u, v, [(0, -0.9), (0.95, 0.8), (-0.95, 0.8)]) and not poly(u, v, [(0, 0.1), (0.35, 0.8), (-0.35, 0.8)]) or (abs(u) < w and -0.95 <= v <= -0.5))
@shape("balloon")
def _(n): w = px(n, 0.7); return raster(n, lambda u, v: ellipse(u, v, 0, -0.3, 0.52, 0.6) or poly(u, v, [(0, 0.28), (-0.15, 0.45), (0.15, 0.45)]) or curve(u, v, lambda t: (0.15 * math.sin(t * 5), 0.45 + 0.5 * t), 0, 1, w))
@shape("confetti")
def _(n): return raster(n, lambda u, v: any(poly(u, v, rect(cx, cy, 0.22, 0.1, a)) for cx, cy, a in ((-0.6, -0.55, 0.5), (0.2, -0.7, -0.3), (0.65, -0.1, 1.0), (-0.3, 0.05, -0.8), (0.4, 0.5, 0.2), (-0.65, 0.65, 1.2), (0.05, 0.8, -0.5))))
@shape("pick")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: seg(u, v, -0.6, 0.9, 0.5, -0.5, w) or curve(u, v, lambda t: (0.9 * math.cos(t) - 0.1, 0.9 * math.sin(t) + 0.2), -2.4, -0.5, w * 1.2))
@shape("sword")
def _(n): w = px(n, 1.0); return raster(n, lambda u, v: taper(u, v, 0.1, -0.1, 0.85, -0.85, 0.16, 0.02) or seg(u, v, -0.35, 0.35, 0.15, -0.15, w * 1.3) or seg(u, v, -0.4, -0.1, 0.1, 0.4, w) or seg(u, v, -0.35, 0.35, -0.75, 0.75, w * 1.2))
@shape("taxi")
def _(n): return raster(n, lambda u, v: (abs(u) <= 0.9 and -0.1 <= v <= 0.45) or (abs(u) <= 0.5 and -0.5 <= v <= -0.1) or disc(u, v, -0.5, 0.55, 0.22) or disc(u, v, 0.5, 0.55, 0.22))
@shape("monkey")
def _(n): return raster(n, lambda u, v: disc(u, v, 0, 0.05, 0.62) or disc(u, v, -0.65, -0.25, 0.28) or disc(u, v, 0.65, -0.25, 0.28))
@shape("banana")
def _(n): return raster(n, lambda u, v: curve(u, v, lambda t: (0.85 * math.cos(t), 0.85 * math.sin(t) - 0.3), 0.35, math.pi - 0.35, px(n, 1.8)) and True)
@shape("dna")
def _(n): w = px(n, 0.8); return raster(n, lambda u, v: curve(u, v, lambda t: (0.55 * math.sin(t * 2 * math.pi), -0.9 + 1.8 * t), 0, 1, w) or curve(u, v, lambda t: (-0.55 * math.sin(t * 2 * math.pi), -0.9 + 1.8 * t), 0, 1, w) or any(abs(v - y) < w and abs(u) <= 0.55 * abs(math.sin((y + 0.9) / 1.8 * 2 * math.pi)) for y in (-0.65, -0.2, 0.25, 0.7)))
@shape("brick")
def _(n): w = px(n, 0.7); return raster(n, lambda u, v: max(abs(u), abs(v)) <= 0.9 and not (abs(v) < w) and not (abs(v + 0.6) < w) and not (abs(v - 0.6) < w) and not (abs(u) < w and -0.6 < v < 0) and not (abs(u + 0.5) < w and (v > 0 or v < -0.6)) and not (abs(u - 0.5) < w and (v > 0 or v < -0.6)))

def t_of(u, v):
    return 0.0

# ---------------------------------------------------------------------------
# themes: the shapes an enemy of that theme throws (the first entry is the one a
# big-sprite enemy gets most often); matched by name keywords, most specific first
# ---------------------------------------------------------------------------
THEMES = {
    "crow":     ["feather", "gull", "beak", "egg", "wing", "claws"],
    "bird":     ["feather", "gull", "wing", "egg", "beak", "cloud"],
    "bat":      ["batwing", "moon", "fang", "wing", "star4", "crescent"],
    "ufo":      ["saucer", "star", "sparkle", "planet", "comet", "ring", "moon"],
    "fly":      ["bee", "swarm", "wing", "dots", "stinger", "antenna"],
    "kraken":   ["tentacle", "wave", "bubble", "drop", "curl", "fish"],
    "spinner":  ["propeller", "gear", "sparkle", "ring", "asterisk", "star6"],
    "sky":      ["cloud", "gull", "dash3", "feather", "star4", "moon"],
    "butterfly": ["wing", "flower", "dots", "leaf", "sparkle", "swarm"],
    "plant":    ["leaf", "seed", "twig", "thorn", "vine", "flower", "acorn"],
    "mushroom": ["mushroom", "spores", "smoke", "leaf", "seed", "blob"],
    "dog":      ["bone", "paw", "fang", "claws", "footprint", "tooth"],
    "snake":    ["snake", "wave", "scale", "fang", "zigzag", "diamond"],
    "buffalo":  ["horn", "hoof", "footprint", "smoke", "dash3", "bone"],
    "fish":     ["fish", "bubble", "bubbles", "wave", "drop", "scale"],
    "rat":      ["cheese", "whiskers", "paw", "tooth", "footprint", "oval"],
    "frog":     ["drop", "lilypad", "bubble", "swarm", "wave", "bubbles"],
    "bear":     ["paw", "ear", "claws", "fang", "footprint", "bone"],
    "mole":     ["pick", "footprint", "claws", "spores", "smoke", "ear"],
    "duck":     ["egg", "feather", "gull", "drop", "wave", "beak"],
    "wolf":     ["fang", "claws", "paw", "moon", "bone", "footprint"],
    "dino":     ["tooth", "fang", "footprint", "egg", "claws", "scale"],
    "croc":     ["tooth", "scale", "claws", "drop", "wave", "fang"],
    "monkey":   ["monkey", "banana", "bubbles", "paw", "swarm", "oval"],
    "insect":   ["ant", "antenna", "swarm", "dots", "stinger", "hexring", "worm"],
    "spider":   ["web", "spider", "dots", "swarm", "antenna", "x"],
    "slug":     ["slug", "drip", "worm", "bubbles", "blob", "wave"],
    "worm":     ["worm", "cocoon", "wave", "spores", "dots", "curl"],
    "scorpion": ["stinger", "claws", "bone", "fang", "curl", "x"],
    "mook":     ["cocoon", "eye", "tentacle", "swarm", "orb", "spores"],
    "robot":    ["gear", "bolt", "nut", "screw", "lightning", "reticle", "laser", "plug"],
    "starman":  ["star", "lightning", "sparkle", "star4", "reticle", "laser", "gear"],
    "octobot":  ["tentacle", "gear", "reticle", "laser", "bolt", "target"],
    "gun":      ["bullet", "target", "reticle", "laser", "bomb", "dash3"],
    "pokey":    ["spark", "bullet", "gear", "reticle", "bolt", "laser"],
    "clumsy":   ["gear", "nut", "wrench", "screw", "bolt", "plug"],
    "ninja":    ["star4", "sparkle", "knife", "dash3", "shard", "x"],
    "ghost":    ["ghost", "wisp", "skull", "moon", "hand", "smoke"],
    "zombie":   ["hand", "skull", "bone", "tombstone", "cross", "drip"],
    "spirit":   ["wisp", "note", "smoke", "sparkle", "moon", "ghost"],
    "electric": ["lightning", "bolt2", "spark", "zigzag", "star4", "plug"],
    "art":      ["shard", "confetti", "spiral", "eye", "question", "dna"],
    "nightmare": ["eye", "skull", "moon", "spiral", "hand", "wisp"],
    "cultist":  ["star", "pentagram", "eye2", "spiral", "hat", "cross"],
    "record":   ["record", "note", "ring", "spiral", "star6", "target"],
    "painter":  ["splat", "confetti", "drip", "sparkle", "star", "blob"],
    "dice":     ["dice", "cardsuit", "coin", "star4", "question", "diamond"],
    "storm":    ["lightning", "cloud", "bolt2", "drop", "zigzag", "gas"],
    "pyramid":  ["pyramid", "ankh", "eye2", "sun", "scale", "diamond"],
    "psychic":  ["spiral", "eye2", "star", "sparkle", "orb", "question"],
    "sphere":   ["orb", "ring", "target", "disc", "smiley", "bubble"],
    "eye":      ["eye", "eye2", "orb", "sparkle", "moon", "spiral"],
    "flame":    ["flame", "ember", "spark", "sun", "smoke", "drop"],
    "cop":      ["badge", "shield", "bullet", "exclaim", "target", "dash3"],
    "punk":     ["skateboard", "shard", "spark", "exclaim", "x", "zigzag"],
    "lady":     ["purse", "hat", "exclaim", "coin", "flower", "question"],
    "hippie":   ["peace", "flower", "note", "sparkle", "leaf", "smoke"],
    "yesman":   ["check", "exclaim", "coin", "hat", "question", "badge"],
    "frank":    ["knife", "shard", "hat", "coin", "exclaim", "x"],
    "tough":    ["fist", "shard", "exclaim", "spark", "bone", "x"],
    "shattered": ["shard", "x", "diamond", "sparkle", "hourglass", "brick"],
    "noose":    ["noose", "hand", "hourglass", "moon", "cross", "curl"],
    "dungeon":  ["brick", "key", "sword", "shield", "square", "tent"],
    "person":   ["fist", "exclaim", "hat", "coin", "shard", "dash3"],
    "kid":      ["balloon", "confetti", "sparkle", "star", "check", "coin"],
    "captain":  ["badge", "shield", "sword", "exclaim", "star", "target"],
    "slime":    ["blob", "drip", "splat", "bubbles", "gas", "smoke"],
    "giygas":   ["eye", "spiral", "wisp", "hand", "skull", "dna", "blob"],
    "tango":    ["note", "spiral", "ring", "star4", "wave", "dash3"],
    "clock":    ["clock", "hourglass", "gear", "ring", "spiral", "wheel"],
    "taxi":     ["taxi", "wheel", "exclaim", "dash3", "smoke", "coin"],
    "cup":      ["cup", "drop", "gas", "smoke", "ring", "bubble"],
    "bomb":     ["bomb", "spark", "ember", "star4", "smoke", "sun"],
    "sign":     ["sign", "arrow", "exclaim", "question", "check", "brick"],
    "tent":     ["tent", "moon", "star", "smoke", "hand", "skull"],
    "hieroglyph": ["ankh", "eye2", "pyramid", "snake", "scale", "sun"],
    "guard":    ["shield", "sword", "spear" if False else "badge", "brick", "star", "cross"],
    "reveler":  ["confetti", "balloon", "note", "cup", "star", "sparkle"],
    "kiss":     ["cardsuit", "eye", "sparkle", "moon", "note", "spiral"],
    "music":    ["note", "record", "wave", "sparkle", "star6", "ring"],
    "eel":      ["lightning", "snake", "wave", "bubble", "zigzag", "spark"],
    "booka":    ["feather", "egg", "beak", "gull", "cloud", "star4"],
    "orb":      ["orb", "sparkle", "ring", "target", "spiral", "star4"],
    "protoplasm": ["blob", "bubbles", "dna", "drip", "splat", "smoke"],
    "petunia":  ["flower", "thorn", "leaf", "spores", "seed", "vine"],
    "sphere2":  ["smiley", "orb", "ring", "disc", "bubble", "target"],
    "shambler": ["curl", "cloud", "smoke", "spiral", "wave", "blob"],
    "menace":   ["note", "sparkle", "wave", "asterisk", "star6", "spiral"],
    "digger":   ["pick", "smoke", "brick", "spores", "footprint", "claws"],
    "mouse":    ["cheese", "whiskers", "paw", "footprint", "tooth", "oval"],
    "generic":  ["star", "ring", "disc", "diamond", "plus", "x", "triangle", "chevron", "crescent", "asterisk", "bowtie", "dots", "wave", "sparkle", "hexagon", "square"],
}
KEYWORDS = [
    ("crow", ["crow"]), ("bat", ["batty"]), ("ufo", ["ufo"]), ("fly", ["fly", "buzz buzz"]),
    ("kraken", ["kraken"]), ("spinner", ["spinning robo"]), ("sky", ["swoosh", "flying man"]),
    ("butterfly", ["butterfly"]), ("mushroom", ["mushroom", "shroom", "shrooom"]),
    ("plant", ["sprout", "oak", "tree", "plant", "cactus", "weed", "seed", "vine", "bush"]),
    ("petunia", ["petunia"]), ("dog", ["dog"]), ("snake", ["snake", "coil", "asp"]),
    ("buffalo", ["buffalo", "ram", "goat", "gruff"]), ("fish", ["fish"]), ("rat", ["rat"]),
    ("mouse", ["mouse"]), ("frog", ["frog"]), ("bear", ["bear"]), ("mole", ["mole"]),
    ("duck", ["duck"]), ("wolf", ["wolf"]), ("dino", ["saur"]), ("croc", ["crocodile"]),
    ("monkey", ["monkey"]), ("spider", ["spider", "arachnid"]), ("slug", ["slug"]),
    ("worm", ["worm", "caterpillar", "cocoon"]), ("scorpion", ["skelpion", "scorpion"]),
    ("mook", ["mook"]), ("insect", ["ant", "roach", "cricket", "centipede", "mite"]),
    ("starman", ["starman"]), ("octobot", ["octobot"]), ("gun", ["gun", "cannon", "sentry", "tank", "military"]),
    ("pokey", ["pokey"]), ("clumsy", ["clumsy"]), ("ninja", ["ninja"]),
    ("robot", ["robo", "mani mani", "mani-mani", "atomic", "reactor", "nuclear", "mechanical", "bionic"]),
    ("zombie", ["zombie"]), ("nightmare", ["nightmare"]), ("spirit", ["spirit"]),
    ("electric", ["electro", "zap"]), ("art", ["abstract", "dali"]),
    ("ghost", ["spook", "ghost", "possessor", "specter", "phantom", "putrid", "moonside", "boogey", "demon", "evil elemental"]),
    ("record", ["record"]), ("painter", ["carpainter"]), ("dice", ["dice"]),
    ("storm", ["thunder", "storm"]), ("pyramid", ["pyramid", "hieroglyph", "royal", "general"]),
    ("psychic", ["psychic", "psycho", "ego"]), ("cultist", ["cultist", "monotoli", "priest", "bishop", "chosen", "magic", "mystical"]),
    ("sphere2", ["smilin"]), ("sphere", ["sphere", "foppy", "fobby"]), ("eye", ["eye"]),
    ("flame", ["flame", "fire", "elemental"]), ("cop", ["cop"]), ("punk", ["punk"]),
    ("lady", ["lady", "mrs."]), ("hippie", ["hippie"]), ("yesman", ["yes man"]), ("frank", ["frank"]),
    ("tough", ["tough", "everdred"]), ("shattered", ["shattered"]), ("noose", ["noose"]),
    ("dungeon", ["dungeon"]), ("kid", ["kid", "picky", "tony", "cave boy", "handsome"]),
    ("captain", ["captain"]), ("giygas", ["giygas"]), ("tango", ["tangoo"]),
    ("slime", ["belch", "barf", "puke", "slimy", "sludge", "pile", "blob", "goo", "fart", "gas"]),
    ("clock", ["clock"]), ("taxi", ["taxi"]), ("cup", ["coffee", "cup"]), ("bomb", ["bomb"]),
    ("sign", ["sign"]), ("tent", ["tent"]), ("reveler", ["reveler", "party man"]),
    ("kiss", ["kiss"]), ("music", ["musica", "conducting"]), ("eel", ["eel"]), ("booka", ["booka", "ranboob"]),
    ("orb", ["orb"]), ("protoplasm", ["protoplasm"]), ("shambler", ["shambler", "wooly"]),
    ("menace", ["menace"]), ("digger", ["digger"]), ("guard", ["guard"]),
    ("person", ["man", "guy", "gang", "junior", "mr.", "shopper", "cranky", "local", "pet", "criminal"]),
    ("bird", ["bird", "eagle", "bee", "mosquito"]),
]

def theme_for(name, etype):
    n = name.lower()
    for theme, keys in KEYWORDS:
        if any(k in n for k in keys):
            return theme
    return {1: "insect", 2: "robot"}.get(etype, "generic")

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

_cache = {}
def render(name, n):
    if (name, n) not in _cache:
        _cache[(name, n)] = LIB[name](n)
    return _cache[(name, n)]

def shapes_for(eid, theme, big):
    """the enemy's shapes: one 32x32 from its theme for big sprites, else four of its theme's"""
    r = random.Random(eid * 7919 + 13)
    pool = THEMES[theme]
    if big:
        nm = pool[0] if r.random() < 0.5 else r.choice(pool)
        return [render(nm, 32)], [nm]
    names = r.sample(pool, 4)
    return [render(nm, 16) for nm in names], names

def parse_types():
    text = open(os.path.join(ROOT, "src", "data", "battle", "enemies.asm")).read()
    return [{"NORMAL": 0, "INSECT": 1, "METAL": 2}[m] for m in re.findall(r"ENEMYTYPE::(\w+)", text)]

def main():
    enemies = parse_enemies()
    etypes = parse_types()
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
        theme = theme_for(name, etypes[eid] if eid < len(etypes) else 0)
        grids, names = shapes_for(eid, theme, big)
        sprites = [white(g) for g in grids]
        sheets.append(sheet_bytes(sprites))
        boxes.append([hitbox(s, big) for s in sprites] * (4 if big else 1))
        previews.append((eid, name, theme, names, sprites))
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
    nbig = sum(1 for p in previews if len(p[4]) == 1)
    used = sorted({nm for p in previews for nm in p[3]})
    themes = sorted({p[2] for p in previews})
    print(f"wrote {len(sheets)} enemy sheets ({sum(len(s) for s in sheets)} bytes, {nbig} big) and hit boxes to {outdir}")
    print(f"{len(LIB)} shapes in the library, {len(used)} used, {len(themes)} themes in play")
    if "--list" in sys.argv:
        for eid, name, theme, names, _ in previews:
            print(f"{eid:3d} {name:28s} {theme:10s} {' '.join(names)}")
    try:
        from PIL import Image
        ids = [int(a) for a in sys.argv[2:] if a.isdigit()] or [159, 81, 1, 121, 55, 93, 2, 34, 9, 32, 150, 88]
        cell = 16 * 3
        im = Image.new("RGB", (len(ids) * (4 * cell + 8), 2 * cell + 4), (40, 40, 40))
        for k, eid in enumerate(ids):
            _, name, theme, names, sprites = previews[eid]
            for i, sp in enumerate(sprites):
                for y in range(len(sp)):
                    for x in range(len(sp[0])):
                        if sp[y][x]:
                            for dy in range(3):
                                for dx in range(3):
                                    im.putpixel((k * (4 * cell + 8) + i * cell + x * 3 + dx, y * 3 + dy), (255, 255, 255))
        im.save(os.path.join(outdir, "enemy_preview.png"))
        print("preview:", [(previews[e][1], previews[e][2], previews[e][3]) for e in ids])
    except ImportError:
        pass

if __name__ == "__main__":
    main()
