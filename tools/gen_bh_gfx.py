#!/usr/bin/env python3
"""Generate the bullet-hell sprite tiles and palette for the EarthBound hack.

Output (relative to the ebsrc tree):
  src/bin/bh/bh_tiles.bin    - N "pieces" of 32x32 px, each stored as 4 rows of 4 tiles
                               (128 bytes per row, 512 bytes per piece), SNES 4bpp format.
  src/bin/bh/bh_palette.bin  - 16 colours, SNES BGR555 little endian (32 bytes).

Piece 0 ("sheet"): four 16x16 sprites: heart, round bullet, flame bullet, small dot.
Piece 1 ("hline"): 32x32 with a 2px thick white line along the top rows.
Piece 2 ("vline"): sheet of 16x16 sprites; sprite 0 has a 2px white line along its left columns
                   (16x16 side-border pieces keep the per-scanline sprite budget low).
Piece 3 ("gauge"): four 16x16 sprites used by the FIGHT timing bar: red, yellow, green blocks, cursor.
Piece 4 ("bone"):  16x32 bone bullet pieces (two 16x16: bone top, bone shaft).
Piece 5 ("minigame"): focus bracket corner, crosshair, "S" label, spark.
Piece 6 ("buttons"):  A/B/X/Y button icons (rhythm game lanes and notes).
Piece 7 ("labels"):   PER FEC T GOO; the other label fragments live in pieces 2 and 5.
Piece 8 ("slots"):    cherry, bell, seven, star for the slot machine.
"""
import os, sys

# palette index meanings (colour 0 = transparent)
TRANSPARENT, WHITE, RED, BLACK, GREY, BLUE, ORANGE, GREEN, YELLOW, DARKRED, LIGHTRED, DARKGREY, LIGHTGREEN, BROWN, LIGHTBLUE, PINK = range(16)
PALETTE = [
    (0, 0, 0),        # 0 transparent
    (31, 31, 31),     # 1 white
    (31, 0, 0),       # 2 red (heart)
    (0, 0, 0),        # 3 black
    (20, 20, 20),     # 4 grey
    (4, 8, 31),       # 5 blue bullet
    (31, 18, 0),      # 6 orange bullet
    (0, 28, 4),       # 7 green
    (31, 30, 4),      # 8 yellow
    (18, 0, 0),       # 9 dark red (heart shading)
    (31, 14, 14),     # 10 light red (heart highlight)
    (10, 10, 10),     # 11 dark grey
    (16, 31, 12),     # 12 light green
    (16, 8, 0),       # 13 brown
    (18, 24, 31),     # 14 light blue
    (31, 20, 26),     # 15 pink
]

def bgr555(r, g, b):
    return (b << 10) | (g << 5) | r

def encode_tile(pix):
    """pix: 8x8 list of lists of palette indices -> 32 bytes 4bpp."""
    out = bytearray()
    for plane_pair in ((0, 1), (2, 3)):
        for y in range(8):
            for plane in plane_pair:
                byte = 0
                for x in range(8):
                    if (pix[y][x] >> plane) & 1:
                        byte |= 0x80 >> x
                out.append(byte)
    return bytes(out)

def blank(w=32, h=32):
    return [[0] * w for _ in range(h)]

def blit(dst, src, ox, oy):
    for y, row in enumerate(src):
        for x, v in enumerate(row):
            if v:
                dst[oy + y][ox + x] = v

def from_art(rows, key):
    return [[key.get(ch, 0) for ch in row] for row in rows]

# ---- 16x16 sprites drawn as ASCII art ----
HEART = from_art([
    "................",
    "................",
    "....hh....hh....",
    "...hhhh..hhhh...",
    "..hHhhhhhhhhhh..",
    "..hhhhhhhhhhhh..",
    "..hhhhhhhhhhhh..",
    "..hhhhhhhhhhhh..",
    "...hhhhhhhhhh...",
    "....hhhhhhhh....",
    ".....hhhhhh.....",
    "......hhhh......",
    ".......hh.......",
    "................",
    "................",
    "................",
], {"h": RED, "H": LIGHTRED, "d": DARKRED})

ROUND = from_art([
    "................",
    "................",
    "................",
    "................",
    "......wwww......",
    ".....wwwwww.....",
    "....wwwwwwww....",
    "....wwwwwwww....",
    "....wwwwwwww....",
    "....wwwwwwww....",
    ".....wwwwww.....",
    "......wwww......",
    "................",
    "................",
    "................",
    "................",
], {"w": WHITE})

FLAME = from_art([
    ".......w........",
    ".......ww.......",
    "......www.......",
    "......wwww......",
    ".....wwwww......",
    ".....wwwwww.....",
    "....wwwwwww.....",
    "....wwwwwwww....",
    "....wwwwwwww....",
    "....wwwwwwww....",
    ".....wwwwww.....",
    ".....wwwwww.....",
    "......wwww......",
    "......wwww......",
    ".......ww.......",
    "................",
], {"w": WHITE})

DOT = from_art([
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    ".......ww.......",
    "......wwww......",
    "......wwww......",
    ".......ww.......",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
], {"w": WHITE})

def block(colour, inset=0):
    s = blank(16, 16)
    for y in range(inset, 16 - inset):
        for x in range(inset, 16 - inset):
            s[y][x] = colour
    return s

CURSOR = blank(16, 16)
for y in range(16):
    CURSOR[y][7] = WHITE
    CURSOR[y][8] = WHITE

BONE_TOP = from_art([
    "................",
    "....ww....ww....",
    "...wwww..wwww...",
    "...wwwwwwwwww...",
    "...wwwwwwwwww...",
    "....wwwwwwww....",
    ".....wwwwww.....",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
], {"w": WHITE})

BONE_SHAFT = from_art([
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
    "......wwww......",
], {"w": WHITE})


# ---- minigame sprites (piece 5) ----
BRACKET = from_art([          # corner bracket, flipped for the other three corners
    "wwwwwwwwww......",
    "wwwwwwwwww......",
    "ww..............",
    "ww..............",
    "ww..............",
    "ww..............",
    "ww..............",
    "ww..............",
    "ww..............",
    "ww..............",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
], {"w": WHITE})
CROSSHAIR = from_art([
    "................",
    "..bb........bb..",
    "..b..........b..",
    "..b...bbbb...b..",
    "......b..b......",
    ".......ww.......",
    ".......ww.......",
    "......b..b......",
    "......bbbb......",
    "................",
    "..b..........b..",
    "..bb........bb..",
    "................",
    "................",
    "................",
    "................",
], {"b": LIGHTBLUE, "w": WHITE})
NOTE = from_art([
    "................",
    ".........ww.....",
    ".........www....",
    ".........w.ww...",
    ".........w..ww..",
    ".........w...w..",
    ".........w......",
    ".........w......",
    ".........w......",
    ".........w......",
    ".....wwwww......",
    "....wwwwww......",
    "...wwwwwww......",
    "...wwwwww.......",
    "....wwww........",
    "................",
], {"w": WHITE})
SPARK = from_art([
    "................",
    ".......y........",
    ".......y........",
    ".......y........",
    "......yyy.......",
    "..y...yyy...y...",
    "...yy.yyy.yy....",
    ".yyyyyyyyyyyyy..",
    "...yy.yyy.yy....",
    "..y...yyy...y...",
    "......yyy.......",
    ".......y........",
    ".......y........",
    ".......y........",
    "................",
    "................",
], {"y": YELLOW})


# ---- 4x6 micro font for the minigame labels and button icons ----
FONT = {
    "A": [".##.", "#..#", "####", "#..#", "#..#", "#..#"],
    "B": ["###.", "#..#", "###.", "#..#", "#..#", "###."],
    "C": [".###", "#...", "#...", "#...", "#...", ".###"],
    "D": ["###.", "#..#", "#..#", "#..#", "#..#", "###."],
    "E": ["####", "#...", "###.", "#...", "#...", "####"],
    "F": ["####", "#...", "###.", "#...", "#...", "#..."],
    "G": [".###", "#...", "#.##", "#..#", "#..#", ".###"],
    "I": ["####", ".#..", ".#..", ".#..", ".#..", "####"],
    "K": ["#..#", "#.#.", "##..", "#.#.", "#..#", "#..#"],
    "M": ["#..#", "####", "####", "#..#", "#..#", "#..#"],
    "O": [".##.", "#..#", "#..#", "#..#", "#..#", ".##."],
    "P": ["###.", "#..#", "###.", "#...", "#...", "#..."],
    "R": ["###.", "#..#", "###.", "#.#.", "#..#", "#..#"],
    "S": [".###", "#...", ".##.", "...#", "...#", "###."],
    "T": ["####", ".#..", ".#..", ".#..", ".#..", ".#.."],
    "X": ["#..#", "#..#", ".##.", ".##.", "#..#", "#..#"],
    "Y": ["#..#", "#..#", ".##.", ".#..", ".#..", ".#.."],
    "H": ["#..#", "#..#", "####", "#..#", "#..#", "#..#"],
    "J": ["..##", "...#", "...#", "...#", "#..#", ".##."],
    "L": ["#...", "#...", "#...", "#...", "#...", "####"],
    "N": ["#..#", "##.#", "##.#", "#.##", "#.##", "#..#"],
    "Q": [".##.", "#..#", "#..#", "#..#", "#.##", ".###"],
    "U": ["#..#", "#..#", "#..#", "#..#", "#..#", ".##."],
    "V": ["#..#", "#..#", "#..#", "#..#", ".##.", ".##."],
    "W": ["#..#", "#..#", "#..#", "####", "####", "#..#"],
    "Z": ["####", "...#", "..#.", ".#..", "#...", "####"],
    "!": [".#..", ".#..", ".#..", ".#..", "....", ".#.."],
    " ": ["....", "....", "....", "....", "....", "...."],
}

def glyph(dst, ch, ox, oy, colour):
    for y, row in enumerate(FONT[ch]):
        for x, c in enumerate(row):
            if c == "#":
                dst[oy + y][ox + x] = colour

def label(text, colour):
    """up to three letters, 5 px pitch, in one 16x16 sprite (left aligned so sprites chain)"""
    s = blank(16, 16)
    for i, ch in enumerate(text[:3]):
        glyph(s, ch, i * 5, 5, colour)
    return s

def button_icon(letter, fill, ink):
    """a 16 px round button with its letter: the rhythm game's lane targets and notes"""
    s = blank(16, 16)
    for y in range(16):
        for x in range(16):
            if (x - 7.5) ** 2 + (y - 7.5) ** 2 <= 7.5 ** 2:
                s[y][x] = fill
    glyph(s, letter, 6, 5, ink)
    return s


# ---- slot machine symbols (piece 8) ----
CHERRY = from_art([
    "..........bb....",
    ".........bb.....",
    "........bb......",
    ".......bb.......",
    "......bb........",
    ".....b..........",
    "....b...........",
    "..rrr...rrr.....",
    ".rrrrr.rrrrr....",
    ".rRrrr.rRrrr....",
    ".rrrrr.rrrrr....",
    ".rrrrr.rrrrr....",
    "..rrr...rrr.....",
    "................",
    "................",
    "................",
], {"r": RED, "R": LIGHTRED, "b": BROWN})
BELL = from_art([
    "......yy........",
    ".....yyyy.......",
    "....yyyyyy......",
    "....yyyyyy......",
    "...yyyyyyyy.....",
    "...yyyyyyyy.....",
    "...yyyyyyyy.....",
    "..yyyyyyyyyy....",
    "..yyyyyyyyyy....",
    ".yyyyyyyyyyyy...",
    ".yyyyyyyyyyyy...",
    "wwwwwwwwwwwwww..",
    ".....wwww.......",
    "......ww........",
    "................",
    "................",
], {"y": YELLOW, "w": WHITE})
SEVEN = from_art([
    "................",
    ".wwwwwwwwwww....",
    ".wwwwwwwwwww....",
    ".wwwwwwwwwww....",
    "........www.....",
    ".......www......",
    ".......www......",
    "......www.......",
    "......www.......",
    ".....www........",
    ".....www........",
    "....www.........",
    "....www.........",
    "................",
    "................",
    "................",
], {"w": WHITE})
STAR = from_art([
    ".......y........",
    ".......y........",
    "......yyy.......",
    "......yyy.......",
    ".....yyyyy......",
    ".yyyyyyyyyyyyy..",
    "..yyyyyyyyyyy...",
    "...yyyyyyyyy....",
    "....yyyyyyy.....",
    "....yyyyyyy.....",
    "...yyyy.yyyy....",
    "...yyy...yyy....",
    "..yy.......yy...",
    "................",
    "................",
    "................",
], {"y": YELLOW})

def piece_sheet(sprites):
    """4 sprites of 16x16 into a 32x32 piece: (0,0),(16,0),(0,16),(16,16)."""
    p = blank()
    for i, s in enumerate(sprites):
        blit(p, s, (i % 2) * 16, (i // 2) * 16)
    return p

RING = blank(16, 16)              # press highlight: a 2 px white ring the size of a button icon
for y in range(16):
    for x in range(16):
        r2 = (x - 7.5) ** 2 + (y - 7.5) ** 2
        if 5.6 ** 2 <= r2 <= 7.9 ** 2:
            RING[y][x] = WHITE

def piece_hline():
    p = blank()
    for y in (0, 1):
        for x in range(32):
            p[y][x] = WHITE
    blit(p, RING, 0, 16)           # sprite offset 32 of piece 1
    return p

def vline16():
    s = blank(16, 16)
    for y in range(16):
        s[y][0] = WHITE
        s[y][1] = WHITE
    return s

def piece_vline():
    # the three free sprites carry label fragments: "D" (of GOOD), "OK", "MIS" (of MISS)
    return piece_sheet([vline16(), label("D", YELLOW), label("OK", WHITE), label("MIS", RED)])

PIECES = [
    piece_sheet([HEART, ROUND, FLAME, DOT]),
    piece_hline(),
    piece_vline(),
    piece_sheet([block(RED), block(YELLOW), block(GREEN), CURSOR]),
    piece_sheet([BONE_TOP, BONE_SHAFT, block(BLUE, 4), block(ORANGE, 4)]),
    piece_sheet([BRACKET, CROSSHAIR, label("S", RED), SPARK]),   # piece 5: focus brackets, crosshair, "S" (of MISS), spark
    piece_sheet([button_icon("A", RED, WHITE), button_icon("B", YELLOW, BLACK),
                 button_icon("X", BLUE, WHITE), button_icon("Y", GREEN, BLACK)]),   # piece 6: rhythm lane buttons
    piece_sheet([label("PER", LIGHTGREEN), label("FEC", LIGHTGREEN), label("T", LIGHTGREEN), label("GOO", YELLOW)]),  # piece 7: labels
    piece_sheet([CHERRY, BELL, SEVEN, STAR]),           # piece 8: slot machine symbols
]

def encode_piece(p):
    out = bytearray()
    for tr in range(4):            # tile row
        for tc in range(4):        # tile column
            tile = [[p[tr * 8 + y][tc * 8 + x] for x in range(8)] for y in range(8)]
            out += encode_tile(tile)
    return bytes(out)


# ---- minigame instructions, pre-rendered as lines of 16x16 sprites (3 letters each) ----
HINTS = [
    "PRESS A IN THE GREEN",        # 0 timing gauge
    "TAP THE BUTTON A NOTE HITS",  # 1 rhythm
    "PRESS A WHEN THEY FRAME IT",  # 2 focus and timed block
    "MASH ANY BUTTON",             # 3 mash
    "PRESS A TO STOP EACH REEL",   # 4 slots
    "HIT THE BUTTONS IN ORDER",    # 5 combo
    "DODGE THE BULLETS",           # 6 dodge box
]
HINT_PIECES = 3                    # up to 12 sprites = 36 letters per line

def hint_pieces(text):
    chunks = [text[i:i + 3] for i in range(0, len(text), 3)]
    assert len(chunks) <= HINT_PIECES * 4, text
    sprites = [label(c, WHITE) for c in chunks]
    while len(sprites) < HINT_PIECES * 4:
        sprites.append(blank(16, 16))
    return b"".join(encode_piece(piece_sheet(sprites[i:i + 4])) for i in range(0, HINT_PIECES * 4, 4)), len(chunks)

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "ebsrc")
    outdir = os.path.join(root, "src", "bin", "bh")
    os.makedirs(outdir, exist_ok=True)
    tiles = b"".join(encode_piece(p) for p in PIECES)
    with open(os.path.join(outdir, "bh_tiles.bin"), "wb") as f:
        f.write(tiles)
    pal = bytearray()
    for r, g, b in PALETTE:
        v = bgr555(r, g, b)
        pal += bytes((v & 0xFF, v >> 8))
    with open(os.path.join(outdir, "bh_palette.bin"), "wb") as f:
        f.write(pal)
    hints, lens = b"", []
    for text in HINTS:
        data, n = hint_pieces(text)
        hints += data
        lens.append(n)
    with open(os.path.join(outdir, "bh_hints.bin"), "wb") as f:
        f.write(hints)
    with open(os.path.join(root, "src", "battle", "bullet_hell", "bh_hint_table.asm"), "w") as f:
        f.write("; generated by tools/gen_bh_gfx.py: sprites per instruction line\nBH_HINT_LEN_TABLE:\n")
        for text, n in zip(HINTS, lens):
            f.write(f"\t.BYTE {n}\t; {text}\n")
    print(f"wrote {len(HINTS)} instruction lines ({len(hints)} bytes)")
    print(f"wrote {len(PIECES)} pieces ({len(tiles)} bytes), palette to {outdir}")

if __name__ == "__main__":
    main()
