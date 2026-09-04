# EarthBound: Undertale-style bullet-hell battles

A ROM hack of EarthBound (SNES, USA) that replaces the passive "enemy attacks, you take
damage" turn with a real-time dodge phase, and the party's physical attacks with a
timing gauge, in the style of Undertale.

The hack is built from source: the [ebsrc](https://github.com/Herringway/ebsrc)
disassembly rebuilds the original ROM byte-for-byte, and the new engine is added on top
as normal source files. This repository holds the patch for players, the tools and tests,
and the engine source as a diff against ebsrc (`patches/ebsrc-bullet-hell.patch`); the
disassembly itself is not included, see "Building from source".

## Playing it: applying the patch

`EarthBound - Bullet Hell.ips` (about 290 KB) turns a clean EarthBound (USA) ROM into the
hacked one. No ROM is distributed here; you need your own copy.

| | size | SHA-1 |
|---|---|---|
| input: `EarthBound (USA).sfc`, No-Intro, no copier header | 3,145,728 bytes | `d67a8ef36ef616bc39306aa1b486e1bd3047815a` |
| output: patched ROM | 4,194,304 bytes | `afdf88fa5a720443ddc922d16547bde753cf9e1d` |

Apply it with any IPS patcher: [Flips](https://github.com/Alcaro/Flips) (`flips --apply`,
or drag and drop), Lunar IPS on Windows, or a browser patcher such as
[ROM Patcher JS](https://www.marcrobledo.com/RomPatcher.js/). Or use the small applier
in this repository, which only needs Python 3 and also checks the hashes:

```
python3 tools/apply_ips.py "EarthBound (USA).sfc" "EarthBound - Bullet Hell.ips" "EarthBound - Bullet Hell.sfc"
```

Notes:

* The patch is for the unheadered ROM. If your file is 3,146,240 bytes it has a
  512-byte copier header; `apply_ips.py` strips it automatically, for other tools remove
  it first (Flips does this too) or the patch lands 512 bytes off.
* The result is 4 MB (the original 3 MB plus three new banks of per-enemy data) with a
  corrected header checksum. It runs on the usual emulators (snes9x, bsnes/higan, Mesen 2,
  RetroArch cores) and on flash carts that take 4 MB HiROM images. The game's
  copy-protection checks are removed, so the expanded ROM does not trigger the
  piracy warning screen or the "enemy swarm" penalties.
* Saves and save states from the unmodified game are not expected to work; start a new
  game.

## What changes in the game

**Enemy turns.** After the usual "X attacks!" / "X used PSI Fire!" text, a white box
with a black interior opens across the area between the text window and the party's HP
windows (up to 232 by 88 pixels) while the enemies fly up off the top of the screen;
they come back when the box closes. The player's red heart appears in the box and a bullet pattern plays for about four
seconds. Move the heart with the d-pad (hold B or X to move slowly). Every hit is a
short invincibility flash.

* Dodge everything and the action is skipped with "<name> dodged quickly!". The first
  hit ends the phase: the box closes and the attack lands at full damage, bypassing the
  game's own miss and dodge rolls (a hit in the box is always a hit).
* Blue bullets only hurt while the heart is moving, orange ones only while it is still.
* **Every enemy has its own attack.** Each of the 231 enemies has a dedicated pair of
  attack programs (one for physical attacks, one for PSI and everything else) in
  `ebsrc/src/battle/bullet_hell/bh_enemies.asm`, generated from the enemy's category
  (birds dive from above, dogs and snakes sweep in from the sides, insects rise from
  below, robots strafe, ghosts fire rings and blue/orange shots, bosses get everything
  at once) with per-enemy speeds, tempo and box sizes. Each program opens with its
  category's signature move; bullets can also slither (WAVE), home in on the heart
  (SEEK) or accelerate downwards (DROP). The generator guarantees that no two programs
  share the same bytes or the same opcode sequence. Bullet speed also scales with the
  enemy's level.
* **Every enemy shoots copies of itself.** `tools/gen_bh_enemy_gfx.py` decodes each
  enemy's battle sprite from the ROM and shrinks it into bullets: 32x32 enemies get four
  16x16 minis (whole, mirrored, head, mirrored head); bigger enemies get one 32x32
  bullet (the whole enemy at half size) drawn with the hardware's 32x32 sprite size and
  mirrored for the odd bullet types. Shrinking uses majority-colour sampling so thin
  parts survive. The sheets of the enemies present are uploaded to sprite VRAM at the
  start of each battle and drawn with that enemy's own palette, so a Spiteful Crow
  throws little crows and a Skate Punk throws skate punks.

**Party attacks.** When Ness, Paula, Jeff or Poo perform a physical attack ("Bash",
"Shoot"...), the box shows a red/yellow/green gauge with a reticle that sweeps right,
bounces back left, and keeps going. Press A inside the green centre and the hit is a
guaranteed SMAAAASH; in the yellow it always connects but never criticals, with damage
falling linearly from 100% next to the green to 65% at the yellow's edge; in the red it
misses 70% of the time and does 30% to 65% when it does land. Dithering for four
seconds is a miss.

The box grows out of its centre when a phase starts and shrinks away afterwards.

Everything else (menus, PSI, items, status effects, the rolling HP meter, backgrounds,
enemy sprites, experience) is untouched.

## Three attack minigames, two ways to take a hit

Each physical attack by a party member picks one of three minigames at random
(the gauge twice as often as the others); each enemy attack is a dodge box three
times in four and a timed block otherwise. Auto Fight skips all of them.

- **Timing gauge** (as before): press A while the bouncing reticle is in the green
  for a SMAAAASH; yellow always connects, red misses 70 % of the time.
- **Rhythm** (3-5 seconds): notes scroll from the right towards the hit line on the
  left. Press A as each note crosses the line. Every press pops a green (perfect),
  yellow (good/ok) or red (missed note) block off the line with its own sound, and
  the strip along the bottom keeps the result of each note. Damage is 40-100 % by
  accuracy (perfect 10, good 7, ok 4 points per note); 90 % or better is a SMAAAASH,
  hitting nothing is a whiff.
- **Focus**: four brackets close in on a crosshair; press A when they frame it.
  Perfect (within 2 px) is a SMAAAASH at 100 %, good 85 %, ok 70 %, a miss 40 % and
  the usual hit roll. The target turns into a spark on a perfect press, and the
  pop and sound tell you the grade at once.
- **Timed block** (enemy attacks): the same brackets close on your heart. A perfect
  press dodges the attack outright ("dodged quickly"), good takes 50 %, ok 75 %, a
  miss the full hit. The brackets pause for 12 frames before they start moving and
  take 33-60 frames to reach the heart, so there is always time to read the speed.

`poke BH_DP+0x9C n` in a harness script forces a kind (1 gauge, 2 rhythm, 3 focus
for attacks; 4 block, 5 dodge box for enemy attacks); `tests/test_rhythm.txt`,
`tests/test_focus_attack.txt` and `tests/test_focus_block*.txt` play each one with
frame-exact presses (`waitle` waits until a note or the brackets reach the line).

## Classic mode, rolling HP and fairness

- **Auto Fight turns the minigames off.** Pick Auto Fight in the command menu and the
  round plays like the original game: no timing gauge, no dodge box, the original
  hit/miss/SMAAAASH rolls decide everything. Press B to leave auto mode again. Use it
  for the trash fights that would otherwise be a minigame every turn.
- **The HP/PP meters stop rolling while a minigame plays.** Mortal damage only keeps
  rolling once the box has closed, so a quick player can still reach the menu and heal.
- **Every dodge phase starts with a 20-frame grace period**, rings always leave a
  two-slot opening and close at 2.1 px/frame at most, no bullet moves faster than
  2.5 px/frame, and fans of 32x32 bullets are spaced so the heart fits between them.
  `tools/playtest_enemies.py` plays every enemy's two programs with the harness's
  automated player (`dodge`) and with a still heart; the tuned set gives the automated
  player no hit before frame 60 in 460 phases and a still heart at least 36 frames.

## Changes

### 2026-09-04

- Two new minigames, picked at random: a rhythm game for attacks and a focus/timed-block
  game for attacks and enemy attacks (above), each with instant colour and sound feedback.
- Fixed the corrupted dodge box in the Giygas prayer phase: the phase transitions
  reload the enemy sprite VRAM over the engine's tiles, which are now re-uploaded on
  every reload (`UNKNOWN_C2C21F`).
- The reported freeze on the first prayer could not be reproduced: the scripted
  final battle with a four-member party was played through all nine prayers on
  snes9x and on the bsnes-mercury accuracy core, with the shipped ROM and with this
  build, without a hang. Two hardware-only risks were removed anyway: the window
  HDMA moved to channel 7 (the game's oval-window effects can use channel 6) and the
  disabled anti-piracy check now initialises its flag, which random power-on RAM
  could otherwise leave set (encounter swarm). If it still freezes for you, please
  report the emulator or flash cart and what was on screen.
- Auto Fight as classic mode, frozen HP roll during minigames, fairness tuning (above).

## Layout

```
EarthBound (USA).sfc      original ROM (No-Intro, SHA-1 d67a8ef3...) - you supply this
EarthBound - Bullet Hell.ips  the hack as an IPS patch (see "Applying the patch")
patches/ebsrc-bullet-hell.patch  the engine source as a git diff against upstream ebsrc
ebsrc/                    local checkout of the disassembly with the patch applied (not in git)
  src/battle/bullet_hell/ bh_engine.asm (engine, bank $EE), bh_data.asm (base graphics,
                          type table), bh_enemies.asm (generated: per-enemy records,
                          462 attack programs, hit boxes; bank $F0)
  src/bankconfig/US/bank30-32.asm  the three new banks ($F0-$F2) of the 4 MB ROM
  include/bullet_hell.asm constants, direct-page layout, pattern opcode macros
  src/bin/bh/             generated: base tiles, palette, enemy bullet sheets (118 KB)
tools/                    toolchain, all built in user space
  cc65/ ebbinex/ spcasm/ ldc2/   assembler, asset extractor, SPC assembler, D compiler
  snes9x/libretro/        headless emulator core
  harness/ebharness.c     scripted headless test runner (screenshots, RAM peek/poke,
                          save states, symbol names from the ld65 map)
  gen_bh_gfx.py           base tiles (heart, box lines, gauge, bones) from ASCII art
  gen_bh_enemy_gfx.py     decodes every enemy's battle sprite and cuts its bullet sheet
  gen_bh_enemies.py       writes the per-enemy records and attack programs
  make_ips.py             builds the IPS patch from the original and the built ROM
  apply_ips.py            applies it (Python 3 only, verifies SHA-1s, strips copier headers)
  fix_checksum.py         rewrites the header checksum (run by the Makefile after linking)
  env.sh                  puts the toolchain on PATH
tests/                    harness scripts (*.txt), run.sh, captured screenshots in out/
```

## Building from source

The engine lives in `patches/ebsrc-bullet-hell.patch`, a diff against ebsrc commit
`0197d6c13ef11ad3280e9388e08a646ab1030d15` (34 source files: the engine, its include
files, the bank configuration and the hooks in the game's battle code). Everything under
ebsrc's `src/bin/` is generated, either extracted from your ROM by ebbinex or written by
the generators in `tools/`, so none of it is in git.

```
git clone https://github.com/Herringway/ebsrc.git
git -C ebsrc checkout 0197d6c13ef11ad3280e9388e08a646ab1030d15
git -C ebsrc apply ../patches/ebsrc-bullet-hell.patch
source tools/env.sh                                # needs the toolchain under tools/ (cc65, ebbinex, spcasm)
cd ebsrc
ebbinex earthbound.yml "../EarthBound (USA).sfc"   # once: extract assets from the ROM
python3 ../tools/gen_bh_gfx.py                     # base tiles and palette  -> src/bin/bh/
python3 ../tools/gen_bh_enemy_gfx.py               # per-enemy bullet sheets and hit boxes
python3 ../tools/gen_bh_enemies.py                 # per-enemy records and attack programs
make -j16                                          # -> build/earthbound.sfc
make -j16 EXTRA="-D BH_DEBUG" BUILDDIR=build-debug # optional: debug-menu build (hold Down+L at power-on)
```

The toolchain directories under `tools/` (cc65, ebbinex, spcasm, ldc2, the snes9x
libretro core) are built from their upstream sources and are not in git either; `env.sh`
expects them there. The harness is a single C file, `tools/harness/ebharness.c`, built
against the snes9x libretro core.

If you add or remove `.INCLUDE` lines in `src/bankconfig/`, delete the affected
`build/US/*.dep` files first; they are only regenerated when the bank's own file changes.

After changing a generator, re-run it before `make` (`python3 tools/gen_bh_gfx.py`,
`python3 tools/gen_bh_enemy_gfx.py`, `python3 tools/gen_bh_enemies.py`). The ROM is
4 MB (the original 3 MB plus banks $F0-$F2); the header already declared 4 MB.

Bank $C2 (the battle code) is full to within about 120 bytes. If `build/earthbound.map`
shows `BANK02` larger than `$10000`, or `BANK03` starting at `$C40000` instead of
`$C30000`, the bank overflowed and the linker silently shifted every later bank by one:
the game still runs (all code is label-resolved) but the IPS patch balloons from ~290 KB
to 3 MB. Three data tables that are only read with long addressing were already moved
from `bank02.asm` to `bank2e.asm` for this reason; move more the same way if needed.

To regenerate the patch after a build:

```
python3 tools/make_ips.py "EarthBound (USA).sfc" ebsrc/build/earthbound.sfc "EarthBound - Bullet Hell.ips"
```

It writes the patch only after applying it back to the original and checking that the
result is byte-identical to the build, and prints the SHA-1 of both ROMs.

To hand-tune one enemy, edit its record and its two programs in `bh_enemies.asm`
(each program is a few macro lines: RAIN, SIDE, AIMED, RISE, WALL, RING, SPAWN, WAIT).
The engine reads pattern indices from the record, so an enemy can also be pointed at
any other program.

## Testing

`tests/run.sh <script>` runs a harness script against `build/earthbound.sfc`. Scripts
are plain text: `run N`, `press a 6`, `hold right`, `poke SYMBOL 01 00`,
`peek SYMBOL 16`, `waitmem SYMBOL VALUE MAX`, `spam a 40 2400 SYMBOL VALUE`, `shot name`,
`save`/`load` state. Symbol names come from `build/earthbound.map`.

* `tests/intro.txt` plays a new game through the naming screens and the intro and saves
  the state `after_intro` (Ness in his room). Re-run it whenever ROM code in bank $C0
  changes, because saved states embed return addresses.
* `tests/real_battle3.txt` forces a Spiteful Crow encounter (enemies first) from that
  state and captures the dodge phase. `tests/test_fight.txt` does the same with the
  party first to capture the FIGHT gauge. `tests/test_dodge.txt`, `test_multi.txt`
  and `test_collision.txt` cover the "dodged everything" path, three enemies, and the
  overworld collision cache after a battle. `test_full_battle.txt` plays a battle to its
  end, `test_anim.txt` captures the box animation and checks that the phase runs at one
  game frame per tick.

A forced encounter is just five pokes: `CURRENT_BATTLE_GROUP`, `ENEMIES_IN_BATTLE`,
`ENEMIES_IN_BATTLE_IDS`, `BATTLE_INITIATIVE` (2 = enemies first) and `BATTLE_MODE`
(`FF FF`), from anywhere in the overworld.

### Harness commands added for the Giygas and playtest work

- `wait2 A V1 B V2 [MAX]` waits until two bytes match at once; `spam2 BTN INT MAX A V1 B V2`
  taps a button until they do. `wait2 CURRENT_FOCUS_WINDOW 0x0F BATTLE_MENU_CURRENT_CHARACTER_ID k`
  is "the command menu is open for party member k".
- `dodge MAX` plays the current dodge phase with a simple automated player (predicts every
  bullet 20 frames ahead, keeps to the box, respects blue/orange rules) and reports the
  frames survived.
- The harness also runs other libretro cores (WRAM is taken from the core's memory map when
  `retro_get_memory` has none, 32-bit pixel formats are converted); bsnes-mercury accuracy
  was used as a second opinion. States are per core.
- Scripted battles: patching the "Who are you talking to?" fallback text at ROM `$C7C588`
  with `1F 23 DB 01 02` makes any Talk-to start the final battle from a script, exactly like
  the game does (`tests/final_flow*.txt`, `tests/prayers_all.txt`). The prayer cutscenes need
  the Saturn Valley NPC flags (`EVENT_FLAGS` pokes in those scripts) or they never return.
- Engine test hook: `poke BH_DP+0x9A 1|2` forces an enemy's first or second program.

## How the engine hooks into the game

* `BH_BATTLE_INIT` at the top of `BATTLE_ROUTINE` clears the engine state.
* `BH_ENEMY_ACTION_HOOK` in `main_battle_routine.asm`, right after an action's text and
  animation and before its targets are processed. For enemy attacks it runs the dodge
  phase and returns 0 to skip the action; for party physical attacks it runs the gauge.
  Both set `BH_DMG_PCT`, which `BH_SCALE_DAMAGE` (hooked at the top of `CALC_DAMAGE`)
  applies. Game routines called from inside engine loops (sound, text) may clobber X;
  the engine saves it around them.
* `BH_RENDER` in the battle frame renderer (`C2F8F9`) appends the heart, bullets, gauge
  and box border to OAM after the enemy sprites. Enemy sprites are drawn shifted up by
  `BH_YSHIFT` (patched into `render_battle_sprite_row.asm`): just above the gauge for
  party attacks, off the top of the screen for dodge phases (`BH_CALC_YSHIFT` mode).
* `BH_SMASH_OVERRIDE` at the top of the game's SMAAAASH check forces or forbids the
  critical according to where the reticle was pressed; `BH_MISS_OVERRIDE` at the top of
  `MISS_CALC` and `DETERMINE_DODGE` forces the outcome of the hit/miss rolls (always hit
  after a dodge-phase hit or a yellow/green press, always miss for a whiff or a red
  press that rolled a miss).
* The black interior is hardware window 2 masking BG1/BG2, with its left/right edges
  driven per scanline by HDMA channel 6 (channels 0-3 belong to the battle backgrounds,
  4 to the letterbox, 5 to the swirl). The game's window registers are mirrored so they
  can be restored afterwards.
* Sprite tiles are uploaded once per battle, right after the enemy sprites are loaded
  (screen still blanked), into the first unused 32x32 enemy-sprite "piece" slots of OBJ
  VRAM: five base pieces, then one sheet per enemy kind present (up to four). They are
  re-uploaded only if an enemy is added mid-battle. Bullets cut from an enemy use the
  OBJ palette slot of that enemy's sprite; everything else uses OBJ palette 7. Uploading the tiles per phase overran the
  vertical blank and produced a garbled frame.
* RAM: the engine's direct page is a 224-byte gap after `OAM1_HIGH_TABLE` that the
  original game never used; the 32-entry bullet table sits in previously unused space at
  the end of the main RAM segment (`BH_BULLETS`). Nothing overlays game buffers.

The window HDMA table is double-buffered and the window registers are only written once
per phase: rewriting WH2/WH3 mid-frame blanks the mask until the next HDMA entry, and
editing the live table tears.

One SNES gotcha worth knowing: when more than 34 8-pixel sprite slivers share a scanline
the PPU drops the *highest priority* sprites first, so the box border uses 16x16 side
pieces, the heart/cursor are always written to OAM first, and wall rows are spaced so a
full-width row stays under the limit.

Per-frame cost: each bullet's tile, palette attribute and hit box are resolved once when
it spawns (`BH_SET_TYPE`), so the update and render loops only add, compare and copy.
The headless harness shows no dropped frames with a dozen bullets and three enemies.
