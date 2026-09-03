#!/usr/bin/env python3
"""Cut four bullet sprites out of every enemy's own battle sprite.

For each enemy id (0-230) this reads the enemy's battle sprite (HAL-compressed 4bpp
tiles in src/bin/battle_sprites), rebuilds the image, and derives a 32x32 "sheet" of
four 16x16 sprites in the enemy's own palette indices:
  0  the whole enemy shrunk to fit 16x16        (a "mini")
  1  the mini, mirrored
  2  a smaller mini (12x12)
  3  the enemy's upper half shrunk to fit 16x16 (its head)
Native-size crops were tried first and looked like random texture chunks for big
enemies, so everything is a scaled-down whole (or upper half) that stays recognisable.
At battle time the sheet is uploaded to sprite VRAM and drawn with the enemy's own
OBJ palette, so the bullets are literally pieces of that enemy.

Outputs (in src/bin/bh):
  enemy_sheets_a.bin   sheets for ids 0-127  (512 bytes each)
  enemy_sheets_b.bin   sheets for ids 128-230
  bh_enemy_hitboxes.bin  231 x 4 x (half width, half height)
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

def crop(img, x0, y0, w, h):
    H, W = len(img), len(img[0])
    return [[img[y][x] if 0 <= x < W and 0 <= y < H else 0 for x in range(x0, x0 + w)] for y in range(y0, y0 + h)]

def scale_to(img, box, size=16):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    s = max(w, h) / size
    out = [[0] * size for _ in range(size)]
    ox, oy = (size - int(w / s)) // 2, (size - int(h / s)) // 2
    for y in range(size):
        for x in range(size):
            sx, sy = x0 + int((x - ox) * s), y0 + int((y - oy) * s)
            if x0 <= sx < x1 and y0 <= sy < y1:
                out[y][x] = img[sy][sx]
    return out

def mirror(sp):
    return [row[::-1] for row in sp]

def hitbox(sp):
    x0, y0, x1, y1 = bbox(sp)
    hw = max(1, min(6, (x1 - x0) // 2 - 1))
    hh = max(1, min(6, (y1 - y0) // 2 - 1))
    return hw, hh

def sheet_bytes(sprites):
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

def load_palette(index):
    p = os.path.join(ROOT, "src", "bin", "battle_sprites", "palettes", f"{index}.pal")
    raw = open(p, "rb").read()
    cols = []
    for i in range(16):
        v = raw[i * 2] | (raw[i * 2 + 1] << 8)
        cols.append(((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3))
    return cols

def main():
    enemies = parse_enemies()
    _, sizes = sprite_sizes()
    sheets, boxes, previews = [], [], []
    cache = {}
    for eid, (name, sprite, pal) in enumerate(enemies):
        if sprite == 0 or sprite - 1 >= len(sizes):
            sprites = [[[0] * 16 for _ in range(16)] for _ in range(4)]
        else:
            idx = sprite - 1
            if idx not in cache:
                path = os.path.join(ROOT, "src", "bin", "battle_sprites", f"{idx}.gfx.lzhal")
                if not os.path.exists(path):   # a few sprites differ per region and live under bin/US
                    path = os.path.join(ROOT, "src", "bin", "US", "battle_sprites", f"{idx}.gfx.lzhal")
                data = exhal(open(path, "rb").read())
                cache[idx] = sprite_image(data, sizes[idx])
            img = cache[idx]
            x0, y0, x1, y1 = bbox(img)
            cx = (x0 + x1) // 2
            mini = scale_to(img, (x0, y0, x1, y1))
            small = scale_to(img, (x0, y0, x1, y1), 12)
            small = [[0] * 2 + row + [0] * 2 for row in small]
            small = [[0] * 16] * 2 + small + [[0] * 16] * 2
            head = scale_to(img, (x0, y0, x1, y0 + max(8, (y1 - y0) // 2)))
            sprites = [mini, mirror(mini), small, head]
        sheets.append(sheet_bytes(sprites))
        boxes.append([hitbox(s) for s in sprites])
        previews.append((eid, name, pal, sprites))
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
    print(f"wrote {len(sheets)} enemy sheets ({sum(len(s) for s in sheets)} bytes) and hit boxes to {outdir}")
    try:
        from PIL import Image
        ids = [int(a) for a in sys.argv[2:]] or [159, 81, 1, 121, 55, 93, 2, 34, 9, 32, 150, 88]
        cell = 16 * 3
        im = Image.new("RGB", (len(ids) * (4 * cell + 8), cell + 4), (40, 40, 40))
        for k, eid in enumerate(ids):
            _, name, pal, sprites = previews[eid]
            cols = load_palette(pal)
            for i, sp in enumerate(sprites):
                for y in range(16):
                    for x in range(16):
                        v = sp[y][x]
                        if v:
                            for dy in range(3):
                                for dx in range(3):
                                    im.putpixel((k * (4 * cell + 8) + i * cell + x * 3 + dx, y * 3 + dy), cols[v])
        im.save(os.path.join(outdir, "enemy_preview.png"))
        print("preview:", [previews[e][1] for e in ids])
    except ImportError:
        pass

if __name__ == "__main__":
    main()
