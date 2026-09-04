#!/usr/bin/env python3
"""Automated dodge-phase playtest: every enemy, both attack programs, with the harness's
automated player. Writes tests/out/playtest.json (and prints a summary).
usage: playtest_enemies.py [ids...]"""
import json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
T = '/home/lolz0r/earthbound'
H = f'{T}/tools/bin/ebharness'; CORE = f'{T}/tools/snes9x/libretro/snes9x_libretro.so'
ROM = f'{T}/ebsrc/build/earthbound.sfc'; MAP = f'{T}/ebsrc/build/earthbound.map'
OUT = f'{T}/tests/out/playtest'; os.makedirs(OUT, exist_ok=True)
import shutil; shutil.copy(f'{T}/tests/out/after_intro.st', OUT)
groups = json.load(open(f'{T}/tests/out/enemy_groups.json'))
inc = open(f'{T}/ebsrc/include/bullet_hell.asm').read()
def off(name): return int(re.search(rf'^{name}\s*=\s*\$([0-9A-F]+)', inc, re.M).group(1), 16)
SPEED, TEMPO, TIMER = off('BH_SPEED'), off('BH_TEMPO'), off('BH_TIMER')
names = {}
for i, m in enumerate(re.finditer(r'PADDEDEBTEXT "([^"]*)"', open(f'{T}/ebsrc/src/data/battle/enemies.asm').read())): names[i] = m.group(1)
MODE = 'still' if '--still' in sys.argv else 'ai'
def script(eid, pat):
    g = int(groups.get(str(eid), 1))
    return '\n'.join([
        f'load after_intro', 'run 30',
        f'poke CURRENT_BATTLE_GROUP {g & 255:02X} {g >> 8:02X}', 'poke ENEMIES_IN_BATTLE 01 00',
        f'poke ENEMIES_IN_BATTLE_IDS {eid & 255:02X} {eid >> 8:02X}', 'poke BATTLE_INITIATIVE 02 00', 'poke BATTLE_MODE FF FF',
        'poke PARTY_CHARACTERS+10 E7 03', 'poke PARTY_CHARACTERS+69 E7 03 E7 03',
        'waitmem BATTLE_MODE_FLAG 1 900', f'poke BH_DP+0x9A {pat:02X}',
        'spam a 40 3000 BH_DP 1', f'peek BH_DP+{TIMER} 2', f'peek BH_DP+{SPEED} 2', f'peek BH_DP+{TEMPO} 2',
        ('dodge 1200' if MODE == 'ai' else 'waitmem BH_DP 0 1300\npeek BH_DP+0x0A 2\npeek BH_DP+0x2A 2'), '']) 
def run(job):
    eid, pat = job
    sp = f'{OUT}/e{eid}_p{pat}.txt'; open(sp, 'w').write(script(eid, pat))
    r = subprocess.run([H, CORE, ROM, sp, OUT], env=dict(os.environ, EBH_MAP=MAP), capture_output=True, text=True, timeout=600, cwd=f'{T}/tests')
    res = {'id': eid, 'name': names.get(eid, '?'), 'pat': pat}
    m = re.search(r'spam a: (condition met|TIMEOUT)', r.stdout); res['phase'] = bool(m and m.group(1) == 'condition met')
    peeks = re.findall(r'peek [0-9A-F]+: ([0-9A-F]{2}) ([0-9A-F]{2})', r.stdout)
    if len(peeks) >= 3:
        res['duration'] = int(peeks[0][1] + peeks[0][0], 16); res['speed'] = int(peeks[1][1] + peeks[1][0], 16); res['tempo'] = int(peeks[2][1] + peeks[2][0], 16)
    m = re.search(r'dodge: (\d+) frames, hits=(\d+) frame=(\d+) active=(\d+)', r.stdout)
    if m: res.update(frames=int(m.group(1)), hits=int(m.group(2)), frame=int(m.group(3)), active=int(m.group(4)))
    if MODE == 'still' and len(peeks) >= 5:
        res.update(hits=int(peeks[3][1] + peeks[3][0], 16), frame=int(peeks[4][1] + peeks[4][0], 16))
    res['mode'] = MODE
    return res
ids = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(range(231))
jobs = [(e, p) for e in ids for p in (1, 2)]
with ThreadPoolExecutor(max_workers=max(2, os.cpu_count() - 1)) as ex: results = list(ex.map(run, jobs))
prev = {}
try: prev = {(r['id'], r['pat']): r for r in json.load(open(f'{T}/tests/out/playtest_{MODE}.json'))}
except Exception: pass
for r in results: prev[(r['id'], r['pat'])] = r
json.dump(sorted(prev.values(), key=lambda r: (r['id'], r['pat'])), open(f'{T}/tests/out/playtest_{MODE}.json', 'w'), indent=0)
nophase = [r for r in results if not r['phase']]; hit = [r for r in results if r.get('hits')]
print(f'{len(results)} runs, {len(nophase)} without a phase, {len(hit)} hits')
for r in sorted(hit, key=lambda r: r.get('frame', 0)): print(f"  HIT {r['id']:3d} {r['name'][:22]:22s} pat {r['pat']} at frame {r.get('frame')}/{r.get('duration')} speed {r.get('speed')} tempo {r.get('tempo')}")
