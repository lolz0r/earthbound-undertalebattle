#!/usr/bin/env python3
"""Play the whole final battle through the game's own scripting, one menu or one round per
harness run, and locate a hang if the game stops coming back.

The scripted-battle ROM copy (tools/make_scripted_rom.py) makes a Talk-to on the overworld
start enemy group 475, the Giygas fight, through the game's normal battle-start path.
Whenever a character's command menu is up the driver reads whose it is and what its first
command says (Bash, or Do Nothing when the game takes attacking away), then Ness, Jeff and
Poo attack the vulnerable enemy and Paula attacks until her menu offers Pray. Rounds play
out with A tapped every 30 frames: minigames are pressed through and dodge phases take
their hits (HP is refilled at every menu), so status effects, lost turns and the game's
own phase changes all happen as they would for a player. Everything is logged per step;
if no menu returns within --round-max frames the CPU is sampled (patched snes9x core) to
show where it is. States: tests/out/<tag>_s<N>.st.
usage: giygas_playthrough.py [--core snes9x|mercury] [--delay N] [--steps N] [--start-state S] [--tag T]"""
import subprocess, sys, os, re, argparse
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = f'{T}/tools/bin/ebharness'
CORES = {'snes9x': f'{T}/tools/snes9x/libretro/snes9x_libretro.so',
         'mercury': f'{T}/tools/mercury/bsnes_mercury_accuracy_libretro.so'}
OUT = f'{T}/tests/out'
ROM = f'{T}/ebsrc/build-debug/earthbound.sfc'; MAP = f'{T}/ebsrc/build-debug/earthbound.map'

ap = argparse.ArgumentParser(); ap.add_argument('--core', default='snes9x'); ap.add_argument('--delay', type=int, default=5)
ap.add_argument('--steps', type=int, default=400); ap.add_argument('--start-state', default=None); ap.add_argument('--round-max', type=int, default=9000)
ap.add_argument('--tag', default='giy'); ap.add_argument('--no-refill', action='store_true', help='do not refill HP (party can die)')
ap.add_argument('--out', default=None, help='state/screenshot directory (default tests/out; states are per core)')
ap.add_argument('--pray-early', action='store_true', help='Paula prays as soon as her menu offers it (random prayers before the final ones)')
ap.add_argument('--hold-a', action='store_true', help='hold A through the rounds instead of tapping it (text prints instantly, as for a player who holds A)')
ap.add_argument('--rom', default=None, help='ROM to run (default ebsrc/build-debug/earthbound.sfc; the map always comes from build-debug)')
ap.add_argument('--sram', default=None, help='boot from this battery save (path without spaces) instead of the synthetic party; no stat or flag pokes')
A = ap.parse_args()
if A.out: OUT = A.out
if A.rom: ROM = A.rom

SETUP = """load after_intro
poke GAME_STATE+122 01 02 03 04
poke GAME_STATE+150 01 02 03 04
poke GAME_STATE+174 04 04
poke EVENT_FLAGS+9 02
poke EVENT_FLAGS+27 08
poke EVENT_FLAGS+46 08
poke EVENT_FLAGS+52 20
poke EVENT_FLAGS+59 08
poke EVENT_FLAGS+81 04
poke PARTY_CHARACTERS+5 63
poke PARTY_CHARACTERS+10 E7 03
poke PARTY_CHARACTERS+21 FF FF FF
poke PARTY_CHARACTERS+69 E7 03 E7 03
poke PARTY_CHARACTERS+100 63
poke PARTY_CHARACTERS+105 E7 03
poke PARTY_CHARACTERS+116 FF FF FF
poke PARTY_CHARACTERS+164 E7 03 E7 03
poke PARTY_CHARACTERS+195 63
poke PARTY_CHARACTERS+200 E7 03
poke PARTY_CHARACTERS+211 FF FF FF
poke PARTY_CHARACTERS+259 E7 03 E7 03
poke PARTY_CHARACTERS+290 63
poke PARTY_CHARACTERS+295 E7 03
poke PARTY_CHARACTERS+306 FF FF FF
poke PARTY_CHARACTERS+354 E7 03 E7 03
poke PARTY_CHARACTERS+84 FF
poke PARTY_CHARACTERS+179 FF
poke PARTY_CHARACTERS+274 FF
poke PARTY_CHARACTERS+369 FF
run {delay}
press a 4
run 20
press a 4
waitmem BATTLE_MODE_FLAG 1 900
save {tag}_s0
"""
HP_POKES = ("" if A.no_refill else "\n".join(f"poke BATTLERS_TABLE+{o} E7 03 E7 03" for o in (17, 95, 173, 251)) + "\n") + \
           ("" if A.sram else "\n".join(f"poke BATTLERS_TABLE+{78 * k + 57} FF" for k in range(4)) + "\n")   # flash resistance: PSI Flash cannot KO the party
PEEKS = ("peek CURRENT_FOCUS_WINDOW 1\npeek BATTLE_MENU_CURRENT_CHARACTER_ID 1\npeek GIYGAS_PHASE 2\npeek CURRENT_BATTLE_GROUP 2\n"
         "peek BATTLE_MODE_FLAG 1\npeek BATTLERS_TABLE+641 2\npeek BATTLERS_TABLE+719 2\npeek BATTLERS_TABLE+636 1\npeek BATTLERS_TABLE+714 1\n"
         "peek BATTLERS_TABLE+17 2\npeek BATTLERS_TABLE+95 2\npeek BATTLERS_TABLE+173 2\npeek BATTLERS_TABLE+251 2\npeek FRAME_COUNTER 2\n")

def run(script, name):
    path = f'{OUT}/{name}.txt'; open(path, 'w').write(script)
    r = subprocess.run([H, CORES[A.core], ROM, path, OUT], cwd=f'{T}/tests', env=dict(os.environ, EBH_MAP=MAP), capture_output=True, text=True)
    return r.stdout + r.stderr
def clean(out): return "\n".join(l for l in out.splitlines() if not l.startswith(('loaded', 'Map_', 'poke', 'saved', 'shot')))
def peeks(out):
    d = {}
    for m in re.finditer(r'peek ([0-9A-F]+): ([0-9A-F ]+)', out):
        d[m.group(1)] = int.from_bytes(bytes.fromhex(m.group(2).replace(' ', '')), 'little')
    return d
_map = {}
for line in open(MAP):
    for m in re.finditer(r'(\S+)\s+([0-9A-F]{6})\s+[RL]', line): _map.setdefault(m.group(1), int(m.group(2), 16))
def key(name, off=0): return f'{((_map[name] - 0x7E0000) + off) & 0xFFFFF:05X}'
K = {n: key(*a) for n, a in dict(focus=('CURRENT_FOCUS_WINDOW',), char=('BATTLE_MENU_CURRENT_CHARACTER_ID',), phase=('GIYGAS_PHASE',),
     group=('CURRENT_BATTLE_GROUP',), mode=('BATTLE_MODE_FLAG',), hp8=('BATTLERS_TABLE', 641), hp9=('BATTLERS_TABLE', 719),
     con8=('BATTLERS_TABLE', 636), con9=('BATTLERS_TABLE', 714), hp0=('BATTLERS_TABLE', 17), hp1=('BATTLERS_TABLE', 95),
     hp2=('BATTLERS_TABLE', 173), hp3=('BATTLERS_TABLE', 251), frame=('FRAME_COUNTER',)).items()}
def info(pk): return {n: pk.get(k) for n, k in K.items()}

MENU_PEEKS = "peek OPEN_WINDOW_TABLE 128\npeek WINDOW_STATS 656\npeek MENU_OPTIONS 3150\n"
def raw(out, name):
    m = re.search(r'peek %05X: ([0-9A-F ]+)' % ((_map[name] - 0x7E0000) & 0xFFFFF), out)
    return bytes.fromhex(m.group(1).replace(' ', '')) if m else b''
def first_command(out, focus):
    """the label of the focused command window's current (first) option, from the game's menu tables:
       OPEN_WINDOW_TABLE[id] -> window_stats slot (82 bytes, current_option at 43) -> MENU_OPTIONS entry (45 bytes, label at 19)"""
    owt, ws, mo = raw(out, 'OPEN_WINDOW_TABLE'), raw(out, 'WINDOW_STATS'), raw(out, 'MENU_OPTIONS')
    if not (owt and ws and mo): return '?'
    slot = int.from_bytes(owt[focus * 2:focus * 2 + 2], 'little')
    if slot >= 8: return '?'
    cur = int.from_bytes(ws[slot * 82 + 43:slot * 82 + 45], 'little')
    if cur >= 70: return '?'
    lab = mo[cur * 45 + 19:cur * 45 + 44]
    return ''.join(chr(b - 0x30) if 0x50 <= b <= 0xAA else ' ' for b in lab).strip()

SETUP_SRAM = """sram {sram}
run 2600
spam start 30 600
run 60
press a 6
run 90
press a 6
run 90
press a 6
run 200
press a 6
run 200
run {delay}
press a 4
run 20
press a 4
waitmem BATTLE_MODE_FLAG 1 900
save {tag}_s0
"""
state = A.start_state
if state is None:
    out = run((SETUP_SRAM.format(sram=A.sram, delay=A.delay, tag=A.tag) if A.sram else SETUP.format(delay=A.delay, tag=A.tag)), f'{A.tag}_setup')
    if 'TIMEOUT' in out: print("battle did not start:\n" + clean(out)); sys.exit(1)
    state = f'{A.tag}_s0'
print(f"core={A.core} delay={A.delay} start={state}", flush=True)
NAMES = {0: 'Ness', 1: 'Paula', 2: 'Jeff', 3: 'Poo'}
rnd = 0; last_phase = None
for step in range(1, A.steps + 1):
    nxt = f'{A.tag}_s{step}'
    out = run(f"load {state}\nrun 2\n{PEEKS}{MENU_PEEKS}", f'{A.tag}_look')
    i = info(peeks(out))
    if i['phase'] == 0xFFFF or i['group'] == 483:
        print(f"step {step}: Giygas defeated (phase={i['phase']} group={i['group']})"); break
    if i['mode'] == 0:
        print(f"step {step}: battle over (BATTLE_MODE_FLAG=0) phase={i['phase']} group={i['group']}"); break
    if i['focus'] not in (0x0F, 0x12):
        # the round is running: tap A until a command menu is up again
        out = run(f"load {state}\nplayround {A.round_max} {0 if A.no_refill else 1} {1 if A.hold_a else 0}\nrun 40\n{PEEKS}save {nxt}\n", f'{A.tag}_round')
        j = info(peeks(out)); m = re.search(r'playround: (menu after (\d+) frames|TIMEOUT)', out); pr = re.search(r'\((.*)\)', out.split('playround:')[1].splitlines()[0]) if 'playround:' in out else None
        for l in out.splitlines():
            if l.startswith('playround: static') or l.startswith('playround: party member'): print("   " + l, flush=True)
        if m and m.group(2):
            rnd += 1
            print(f"step {step}: round {rnd} played in {m.group(2)} frames ({pr.group(1) if pr else ''}) -> phase={j['phase']} group={j['group']} giygasHP={j['hp8']} pokeyHP={j['hp9']} "
                  f"con8/9={j['con8']}/{j['con9']} party={j['hp0']}/{j['hp1']}/{j['hp2']}/{j['hp3']} next menu: {NAMES.get(j['char'], j['char'])}", flush=True)
            if j['phase'] == 0xFFFF or j['group'] == 483: print("Giygas defeated"); break
            state = nxt; continue
        # nothing came back: the ending, a game over, or a hang
        diag = run(f"load {state}\nplayround {A.round_max} {0 if A.no_refill else 1} {1 if A.hold_a else 0}\nshot {A.tag}_stuck\ncpu\ntrace 120\n{PEEKS}run 300\npeek FRAME_COUNTER 2\ncpu\nsave {A.tag}_stuck\n", f'{A.tag}_diag')
        print(f"step {step}: NO MENU within {A.round_max} frames after state {state} (phase={i['phase']} group={i['group']}); diagnosis:\n{clean(diag)}")
        break
    # a menu is up
    ch = i['char']; cmd0 = first_command(out, i['focus']); dn = cmd0.startswith('Do')
    two_up = (i['con9'] or 0) != 0 and (i['phase'] or 0) < 2
    if ch == 1 and ((i['phase'] or 0) >= 4 or (A.pray_early and (i['phase'] or 0) >= 2)):   # Paula prays once the game asks for it: Pray is one column right of Do Nothing, two right of Bash
        act, what = "press right 4\nrun 8\n" * (1 if dn else 2) + "press a 4\n", "Pray"
    elif dn:           act, what = "press a 4\n", "Do Nothing"
    else:              act, what = "press a 4\nrun 20\n" + ("press right 4\nrun 8\n" if two_up else ""), "Bash" + (" Pokey" if two_up else "")
    # after the choice a target window (0x31) may be up: tap A until it is gone
    out = run(f"load {state}\nrun 2\n{HP_POKES}{act}spamu a 30 600 CURRENT_FOCUS_WINDOW 0x31\nrun 30\n{PEEKS}save {nxt}\n", f'{A.tag}_act')
    j = info(peeks(out))
    if 'TIMEOUT' in out:
        print(f"step {step}: {NAMES.get(ch, ch)}: {what} -> menu did not advance:\n{clean(out)}"); break
    if i['phase'] != last_phase: print(f"  [phase {i['phase']} group {i['group']}]"); last_phase = i['phase']
    print(f"step {step}: {NAMES.get(ch, ch)} [{cmd0}]: {what}  -> {'menu ' + NAMES.get(j['char'], str(j['char'])) if j['focus'] in (0x0F, 0x12) else 'round'}", flush=True)
    state = nxt
