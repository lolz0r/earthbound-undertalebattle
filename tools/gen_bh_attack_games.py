#!/usr/bin/env python3
"""Turn docs/attack_minigames.md into the engine's per-attack game table.

Every table row (enemy, attack, minigame, blocks) becomes one 9-byte entry:
  action id (word), primary block, modifier block, p0..p3, hint line.
The primary block is the first standalone mechanic in "Blocks used" (dodge box if only
modifiers are listed), the modifier the first modifier mechanic. Parameters come from the
enemy's own record (speed, category) and a per-row hash, so rows of the same block still
play differently. Output: BH_AG_INDEX (231 words: offset of each enemy's entries, $FFFF =
none) and BH_AG_DATA (count byte + entries per enemy)."""
import re, os, sys, hashlib
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
doc = open(f"{T}/docs/attack_minigames.md").read()
actions = [m.group(1) for m in re.finditer(r'^\t(\w+)', open(f"{T}/ebsrc/include/constants/actions.asm").read().split('.ENUM BATTLE_ACTIONS')[1].split('.ENDENUM')[0], re.M)]
ACT = {n: i for i, n in enumerate(actions)}
STANDALONE = {3, 4, 5, 6, 10, 12, 13, 14, 15, 16, 18, 19}
MODIFIER = {7, 8, 9, 11, 17, 20}
# hint line index per block (tools/gen_bh_gfx.py HINTS order: 0-6 are the existing lines)
HINT = {1: 6, 2: 2, 3: 7, 4: 8, 5: 9, 6: 10, 10: 11, 12: 12, 13: 13, 14: 14, 15: 15, 16: 16, 18: 17, 19: 18,
        7: 19, 8: 20, 9: 21, 11: 22, 17: 23, 20: 24}
rows = []
for line in doc.splitlines():
    if not line.startswith('| ') or line.startswith('| Enemy') or line.startswith('| ---'): continue
    cells = [c.strip() for c in line.strip().strip('|').split('|')]
    if len(cells) < 4: continue
    enemy, attack, game, blocks = cells[:4]
    ids = [int(x) for x in re.findall(r'#(\d+)', enemy)]
    # "#218-#229" ranges
    for a, b in re.findall(r'#(\d+)-#(\d+)', enemy): ids += list(range(int(a), int(b) + 1))
    ids = sorted(set(ids))
    m = re.search(r'\(([A-Z0-9_]+),', attack)
    if not m or m.group(1) not in ACT: print('skip (no action):', enemy, attack, file=sys.stderr); continue
    aid = ACT[m.group(1)]
    bl = [int(x) for x in re.findall(r'B(\d+)', blocks)]
    prim = next((b for b in bl if b in STANDALONE), None)
    mod = next((b for b in bl if b in MODIFIER), 0)
    if prim is None: prim = 2 if 2 in bl and 1 not in bl else 1
    rows.append((ids, aid, prim, mod, game))
print(f"{len(rows)} rows", file=sys.stderr)
# per-enemy record speed/category from bh_enemies.asm (record = 12 bytes: pat, pat, type, type2, speed, tempo, w, h, cat, flags)
recs = {}
enemies_asm = open(f"{T}/ebsrc/src/battle/bullet_hell/bh_enemies.asm").read()
for i, m in enumerate(re.finditer(r'^\s*\.WORD\s+\S+,\s*\S+\s*\n\s*\.BYTE\s+([^;\n]+)', enemies_asm, re.M)):
    def num(v):
        v = v.strip()
        try: return int(v[1:], 16) if v.startswith('$') else int(v, 0)
        except ValueError: return 0
    vals = [num(v) for v in m.group(1).split(',')]
    recs[i] = vals
def params(eid, aid, prim, mod):
    h = int.from_bytes(hashlib.md5(f"{eid}:{aid}:{prim}:{mod}".encode()).digest()[:4], 'little')
    r = recs.get(eid, [0, 0, 16, 16, 0, 0, 9, 0])
    speed, tempo, cat = (r[2] or 16), (r[3] or 16), (r[6] if len(r) > 6 else 9)
    v = lambda k, n: (h >> (k * 5)) % n          # small per-row variations
    p = [0, 0, 0, 0]
    if prim == 3:   p = [20 + v(0, 4) * 4, 36 + v(1, 4) * 8, 3 + v(2, 3), 0]  # wave speed/16, frames between waves, waves
    elif prim == 4: p = [v(0, 6), 32 + v(1, 2) * 16, 3 + v(2, 3), 0]         # direction, gap px, bars
    elif prim == 5: p = [2 + v(0, 3), 10 + v(1, 3) * 4, 40 + v(2, 4) * 10, 0] # fill/frame, window px, window pos
    elif prim == 6: p = [3 + v(0, 4), 9 + v(1, 3), 0, 0]                     # arrows, blocks of 20 frames
    elif prim == 10: p = [2 + v(0, 3), 4 + v(1, 4), 12 + v(2, 3) * 4, 0]     # good, bad, speed/16
    elif prim == 12: p = [24 + v(0, 3) * 8, 1 + v(1, 2), 150 + v(2, 3) * 30, 0] # target, drain, frames
    elif prim == 13: p = [1 + v(0, 3), 16 + v(1, 3) * 6, v(2, 2), 0]         # passes, speed/16, from left/right
    elif prim == 14: p = [4 + v(0, 4), 0, 6 + v(1, 2) * 2, 0]                # beats, tempo override, tolerance
    elif prim == 15: p = [2 + v(0, 3), 24 + v(1, 3) * 6, v(2, 4), 0]         # hits, tell frames, pattern
    elif prim == 16: p = [3 + v(0, 3), 10 + v(1, 3) * 4, 1 + v(2, 2), 0]     # cells, reveal frames, rounds
    elif prim == 18: p = [3 + v(0, 3), 20 + v(1, 3) * 6, v(2, 2), 0]         # length, show frames, shapes
    elif prim == 19: p = [16, 2 + v(0, 4), 180 + v(1, 2) * 60, 0]             # step px, steps, frames
    if mod == 7:  p[3] = v(3, 4)          # mirror x / mirror y / rotate / lag
    elif mod == 8:  p[3] = v(3, 4) | ((1 + v(4, 3)) << 4)   # direction | strength
    elif mod == 9:  p[3] = 1 + v(3, 3)    # which edges
    elif mod == 11: p[3] = 40 + v(3, 3) * 8   # radius
    elif mod == 17: p[3] = 60 + v(3, 3) * 30  # window every n frames
    elif mod == 20: p[3] = v(3, 2)        # mirror axis
    return p
# a modifier only applies where the engine can honour it: the heart-moving blocks for pull /
# walls / spotlight / two hearts, the D-pad blocks for scrambled controls, everything for freeze
HEART = {1, 3, 4, 10, 16}
APPLIES = {7: HEART | {6, 15, 19}, 8: HEART, 9: HEART, 11: HEART, 17: set(range(1, 21)) - {2}, 20: HEART}
per = {}
for ids, aid, prim, mod, game in rows:
    if mod and prim not in APPLIES.get(mod, set()): mod = 0
    for eid in ids:
        per.setdefault(eid, [])
        if any(e[0] == aid for e in per[eid]): continue
        per[eid].append((aid, prim, mod, params(eid, aid, prim, mod), HINT[mod] if (prim == 1 and mod) else HINT[prim]))
out = ["; generated by tools/gen_bh_attack_games.py from docs/attack_minigames.md - do not edit",
       "; BH_AG_INDEX: per enemy id, the offset of its entries in BH_AG_DATA ($FFFF = none)",
       "; BH_AG_DATA: count, then 9-byte entries: action (word), block, modifier, p0, p1, p2, p3, hint",
       "BH_AG_INDEX:"]
off = 0; data = []
for eid in range(231):
    ents = per.get(eid)
    if not ents: out.append("\t.WORD $FFFF"); continue
    out.append(f"\t.WORD {off}   ; {eid}")
    data.append(f"\t.BYTE {len(ents)}   ; enemy {eid}")
    for aid, prim, mod, p, hint in ents:
        data.append(f"\t.WORD {aid}\n\t.BYTE {prim}, {mod}, {p[0]}, {p[1]}, {p[2]}, {p[3]}, {hint}   ; {actions[aid]}")
    off += 1 + 9 * len(ents)
out.append("BH_AG_DATA:"); out += data
open(f"{T}/ebsrc/src/battle/bullet_hell/bh_attack_games.asm", "w").write("\n".join(out) + "\n")
n = sum(len(v) for v in per.values())
print(f"wrote {n} entries for {len(per)} enemies, {off} data bytes", file=sys.stderr)
