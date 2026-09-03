#!/usr/bin/env python3
"""Generate a dedicated bullet-hell attack program for every enemy.

Writes src/battle/bullet_hell/bh_enemies.asm (bank $F0) containing:
  BH_ENEMY_TABLE     one 12-byte record per enemy id (0-230):
                     0-1 physical-attack pattern index (word)   2-3 PSI/other pattern index (word)
                     4 bullet type for BH_TYPE_ENEMY   5 bullet type for BH_TYPE_ENEMY2
                     6 speed scale (16 = 1.0)          7 tempo scale (16 = 1.0, smaller = denser)
                     8 box width override (0 = none)   9 box height override (0 = none)
                     10 category                       11 flags
  BH_PATTERN_TABLE   pointer per pattern; pattern 2*id is the enemy's physical-attack program,
                     2*id+1 its PSI/other program
  BH_PAT_E<id>_A/_B  the programs themselves, built from move templates with parameters
                     drawn from a per-enemy random stream. The generator verifies that no two
                     programs are byte-identical and that no two enemies share a record.
  BH_ENEMY_HITBOXES  4 x (half width, half height) per enemy for its four bullet sprites
                     (from tools/gen_bh_enemy_gfx.py)

Bullet types 13-16 (BH_TYPE_THEME0..3) are the four sprites cut from the enemy's own battle
sprite: mini, face, middle, mirrored mini. Everything in the output is meant to be hand-edited
for enemies you care about; regenerate only if you want to start over.
"""
import os, re, sys, random

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "ebsrc")
TH = ["BH_TYPE_THEME0", "BH_TYPE_THEME1", "BH_TYPE_THEME2", "BH_TYPE_THEME3"]
EDGES = ["BH_EDGE_TOP", "BH_EDGE_BOTTOM", "BH_EDGE_LEFT", "BH_EDGE_RIGHT", "BH_EDGE_ANY"]

CATEGORIES = [
    ("bird",   ["crow", "bird", "ufo", "fly", "bat", "bee", "mosquito", "sky", "eagle", "kraken", "swoosh", "spinning robo"]),
    ("plant",  ["sprout", "oak", "tree", "mushroom", "shroom", "plant", "flower", "cactus", "weed", "seed", "vine", "bush"]),
    ("beast",  ["dog", "snake", "coil", "cat", "buffalo", "wolf", "ram", "runaway", "mole", "rat", "duck", "fish", "gruff", "goat", "frog", "elephant", "lion", "bear"]),
    ("insect", ["ant", "spider", "roach", "cricket", "slug", "worm", "cocoon", "mook", "centipede", "scorpion", "smilin"]),
    ("robot",  ["robo", "starman", "octobot", "mani mani", "clumsy", "atomic", "military", "pokey", "gun", "cannon", "tank", "sentry", "ninja"]),
    ("ghost",  ["spook", "ghost", "spirit", "zombie", "possessor", "nightmare", "electro", "specter", "phantom", "putrid", "moonside", "abstract", "ness's"]),
    ("psi",    ["cultist", "carpainter", "monotoli", "pyramid", "priest", "bishop", "chosen", "loaded dice", "magic", "mystical", "thunder", "storm"]),
    ("person", ["punk", "cop", "lady", "man", "guy", "gang", "yes man", "frank", "tough", "junior", "captain", "mr.", "mrs.", "kid", "hippie", "shopper", "cranky"]),
    ("slime",  ["belch", "barf", "puke", "slimy", "sludge", "pile", "blob", "goo", "fart", "gas"]),
]
CAT_INDEX = {c: i for i, (c, _) in enumerate(CATEGORIES)}
CAT_INDEX["generic"] = len(CATEGORIES)

def category(name, etype):
    n = name.lower()
    for cat, keys in CATEGORIES:
        if any(k in n for k in keys):
            return cat
    return {1: "insect", 2: "robot"}.get(etype, "generic")

# ---------------------------------------------------------------------------
# move templates: each returns a list of assembly lines. `r` is the enemy's RNG,
# `t` a function giving a bullet type name, `sp` the base speed (1/16 px/frame).
# ---------------------------------------------------------------------------
def m_rain(r, t, sp):
    n = r.randint(2, 4)
    return [f"\t\tBH_RAIN {t()}, {sp + r.randint(-4, 6)}", f"\t\tBH_WAIT {r.randint(6, 12)}"] * n

def m_side(r, t, sp):
    return [f"\t\tBH_SIDE {t()}, {sp + r.randint(0, 8)}", f"\t\tBH_WAIT {r.randint(9, 15)}"] * r.randint(2, 3)

def m_aimed(r, t, sp, edge=None):
    e = edge or r.choice(EDGES)
    return [f"\t\tBH_AIMED {t()}, {e}, {sp + r.randint(-2, 8)}", f"\t\tBH_WAIT {r.randint(10, 18)}"] * r.randint(1, 3)

def m_dive(r, t, sp):
    return [f"\t\tBH_AIMED {t()}, BH_EDGE_TOP, {sp + r.randint(4, 10)}", f"\t\tBH_WAIT {r.randint(5, 8)}"] * r.randint(2, 3) + [f"\t\tBH_WAIT {r.randint(16, 28)}"]

def m_volley(r, t, sp):
    return [f"\t\tBH_AIMED {t()}, BH_EDGE_LEFT, {sp + r.randint(0, 6)}", f"\t\tBH_WAIT {r.randint(8, 14)}",
            f"\t\tBH_AIMED {t()}, BH_EDGE_RIGHT, {sp + r.randint(0, 6)}", f"\t\tBH_WAIT {r.randint(8, 14)}"]

def m_burst(r, t, sp):
    n = r.randint(2, 4)
    e = r.choice(EDGES)
    return [f"\t\tBH_AIMED {t()}, {e}, {sp + r.randint(2, 10)}", f"\t\tBH_WAIT {r.randint(3, 5)}"] * n + [f"\t\tBH_RWAIT {r.randint(24, 34)}, {r.randint(40, 56)}"]

def m_wall(r, t, sp):
    return [f"\t\tBH_WALL {t()}, {r.choice([36, 40, 44, 48])}, {sp - r.randint(0, 6)}", f"\t\tBH_WAIT {r.randint(44, 60)}"]

def m_rise(r, t, sp):
    return [f"\t\tBH_RISE {t()}, {sp + r.randint(-2, 6)}", f"\t\tBH_WAIT {r.randint(8, 14)}"] * r.randint(2, 3)

def m_ring(r, t, sp):
    return [f"\t\tBH_RING {t()}, {r.choice([5, 6, 8])}, {sp + r.randint(-2, 4)}", f"\t\tBH_WAIT {r.randint(34, 48)}"]

def m_fan(r, t, sp):
    # three bullets from the top centre spreading out
    v = sp + r.randint(0, 6)
    y = -20
    return [f"\t\tBH_SPAWN {t()}, 48, {y}, {-(v // 2)}, {v}", f"\t\tBH_SPAWN {t()}, 64, {y}, 0, {v}",
            f"\t\tBH_SPAWN {t()}, 80, {y}, {v // 2}, {v}", f"\t\tBH_WAIT {r.randint(24, 40)}"]

def m_gatling(r, t, sp):
    e = r.choice(["BH_EDGE_LEFT", "BH_EDGE_RIGHT"])
    return [f"\t\tBH_AIMED {t()}, {e}, {sp + r.randint(8, 14)}", f"\t\tBH_WAIT {r.randint(5, 7)}"] * r.randint(3, 5) + [f"\t\tBH_WAIT {r.randint(20, 30)}"]

def m_blueorange(r, t, sp):
    return [f"\t\tBH_AIMED BH_TYPE_BLUE, BH_EDGE_ANY, {sp}", f"\t\tBH_WAIT {r.randint(14, 20)}",
            f"\t\tBH_AIMED BH_TYPE_ORANGE, BH_EDGE_ANY, {sp}", f"\t\tBH_WAIT {r.randint(14, 20)}"]

MOVES = {
    "bird":    [m_dive, m_rain, m_fan, m_aimed],
    "plant":   [m_rain, m_wall, m_rise, m_fan],
    "beast":   [m_side, m_volley, m_rise, m_aimed],
    "insect":  [m_rise, m_wall, m_rain, m_side],
    "robot":   [m_gatling, m_burst, m_wall, m_ring],
    "ghost":   [m_ring, m_blueorange, m_aimed, m_fan],
    "psi":     [m_ring, m_burst, m_fan, m_aimed],
    "person":  [m_side, m_volley, m_aimed, m_rain],
    "slime":   [m_rain, m_wall, m_rise, m_side],
    "generic": [m_rain, m_aimed, m_side, m_wall, m_burst, m_fan],
}
BOXES = {
    "bird": [(160, 56), (176, 48), (152, 60)], "plant": [(160, 56), (144, 64)], "beast": [(144, 48), (160, 48), (168, 44)],
    "insect": [(144, 64), (136, 64)], "robot": [(160, 48), (176, 48)], "ghost": [(128, 72), (120, 72)],
    "psi": [(128, 64), (136, 64)], "person": [(144, 56), (152, 52)], "slime": [(160, 56), (152, 60)],
    "generic": [(144, 56), (160, 48), (128, 64)],
}

def parse_enemies():
    text = open(os.path.join(ROOT, "src", "data", "battle", "enemies.asm")).read()
    blocks = text.split("PADDEDEBTEXT ")[1:]
    out = []
    for i, b in enumerate(blocks):
        name = re.match(r'"([^"]*)"', b).group(1)
        etype = {"NORMAL": 0, "INSECT": 1, "METAL": 2}[re.search(r"ENEMYTYPE::(\w+)", b).group(1)]
        level = int(re.search(r"\.BYTE (\d+) ;Level", b).group(1))
        hp = int(re.search(r"\.WORD (\d+) ;HP", b).group(1))
        boss = int(re.search(r"\.BYTE \$([0-9A-Fa-f]+) ;Boss flag", b).group(1), 16)
        out.append((i, name, etype, level, hp, boss))
    return out

def program(eid, cat, boss, which, salt=0):
    r = random.Random(f"{eid}:{which}:{salt}")
    moves = MOVES[cat]
    nmoves = r.randint(3, 4) + (1 if boss else 0)
    sp = 20 + (4 if boss else 0)
    types = TH[:]
    r.shuffle(types)
    counter = [0]
    def t():
        v = types[counter[0] % (2 if which == "A" else 3)]
        counter[0] += 1
        return v
    w, h = r.choice(BOXES[cat])
    if boss:
        w, h = w + 8, h + 8
    frames = r.choice([220, 240, 260]) + (60 if boss else 0)
    lines = [f"BH_PAT_E{eid:03d}_{which}:", f"\tBH_HEADER {w}, {h}, {frames}", "\tBH_LOOP 0"]
    chosen = [moves[r.randrange(len(moves))] for _ in range(nmoves)]
    if which == "B" and cat not in ("ghost",):   # the PSI program leans on rings / bursts
        chosen[0] = r.choice([m_ring, m_burst, m_fan])
    for mv in chosen:
        lines += mv(r, t, sp)
    lines += ["\tBH_ENDLOOP", ""]
    # the program's shape: its sequence of opcodes (so no two enemies attack the same way)
    shape = tuple(l.split()[0] for l in lines if l.startswith("\t\tBH_"))
    return lines, shape

def main():
    enemies = parse_enemies()
    programs, seen_prog, seen_shape, seen_rec, records = [], set(), set(), set(), []
    for eid, name, etype, level, hp, boss in enemies:
        cat = "generic" if eid == 0 else category(name, etype)
        big = boss or hp >= 1500
        progs = []
        for which in ("A", "B"):
            salt = 0
            while True:
                p, shape = program(eid, cat, big, which, salt)
                key = "\n".join(p[1:])
                # every program must differ from every other one both in its exact bytes and
                # in its sequence of opcodes
                if key not in seen_prog and shape not in seen_shape:
                    seen_prog.add(key); seen_shape.add(shape); break
                salt += 1
            progs.append(p)
        r = random.Random(f"rec:{eid}")
        t1, t2 = r.sample(TH, 2)
        speed = 14 + r.randint(0, 6) + (3 if big else 0)
        tempo = 12 + r.randint(0, 8) - (3 if big else 0)
        while (t1, t2, speed, tempo, cat) in seen_rec:
            tempo = 10 + (tempo - 9) % 12
        seen_rec.add((t1, t2, speed, tempo, cat))
        records.append((eid, name, level, big, cat, t1, t2, speed, max(9, tempo)))
        programs += progs
    out = os.path.join(ROOT, "src", "battle", "bullet_hell", "bh_enemies.asm")
    with open(out, "w") as f:
        f.write("; Per-enemy bullet-hell data: one dedicated attack program pair and one record per enemy.\n")
        f.write("; Generated by tools/gen_bh_enemies.py - hand edits welcome, keep the order of the tables.\n\n")
        f.write("BH_ENEMY_TABLE:\n")
        f.write("; .WORD phys pattern, PSI pattern / .BYTE bullet type, bullet type 2, speed x/16, tempo x/16, box w, box h, category, flags\n")
        for eid, name, level, big, cat, t1, t2, speed, tempo in records:
            f.write(f"\t.WORD {2*eid}, {2*eid+1}\n\t.BYTE {t1}, {t2}, {speed}, {tempo}, 0, 0, {CAT_INDEX[cat]}, 0"
                    f"\t; {eid:3d} {name} (L{level}{', boss' if big else ''}, {cat})\n")
        f.write(f"BH_ENEMY_COUNT = {len(records)}\n\n")
        f.write("; pattern index -> program address (all programs live in this bank)\nBH_PATTERN_TABLE:\n")
        for eid, *_ in records:
            f.write(f"\t.WORD .LOWORD(BH_PAT_E{eid:03d}_A), .LOWORD(BH_PAT_E{eid:03d}_B)\n")
        f.write(f"BH_PATTERN_COUNT = {2 * len(records)}\n\n")
        f.write("; 4 x (half width, half height) hit boxes of each enemy's four bullet sprites\nBH_ENEMY_HITBOXES:\n\t.INCBIN \"bin/bh/bh_enemy_hitboxes.bin\"\n\n")
        f.write("; ---------------------------------------------------------------------------\n; attack programs\n; ---------------------------------------------------------------------------\n")
        f.write("E  = BH_TYPE_ENEMY\nE2 = BH_TYPE_ENEMY2\n\n")
        for p in programs:
            f.write("\n".join(p) + "\n")
    print(f"wrote {len(records)} records and {len(programs)} programs to {out}")

if __name__ == "__main__":
    main()
