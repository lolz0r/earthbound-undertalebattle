# EarthBound: Undertale-style bullet-hell battles

A ROM hack of EarthBound (SNES, USA) that replaces the passive "enemy attacks, you take
damage" turn with a real-time dodge phase, and the party's physical attacks with a
timing gauge, in the style of Undertale.

The hack is built from source: the [ebsrc](https://github.com/Herringway/ebsrc)
disassembly (checked out in `ebsrc/`, branch `bullet-hell`) rebuilds the original ROM
byte-for-byte, and the new engine is added on top as normal source files.

## What changes in the game

**Enemy turns.** After the usual "X attacks!" / "X used PSI Fire!" text, a white box
with a black interior opens across the area between the text window and the party's HP
windows (up to 232 by 88 pixels) while the enemies fly up off the top of the screen;
they come back when the box closes. The player's red heart appears in the box and a bullet pattern plays for about four
seconds. Move the heart with the d-pad (hold B or X to move slowly). Every hit is a
short invincibility flash.

* Dodge everything and the action is skipped with "<name> dodged quickly!". The first
  hit ends the phase: the box closes and the attack lands at full damage.
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
* **Every enemy shoots pieces of itself.** `tools/gen_bh_enemy_gfx.py` decodes each
  enemy's battle sprite from the ROM and cuts four bullet sprites out of it (a mini, its
  face, its middle, a mirrored mini). The sheets of the enemies present are uploaded to
  sprite VRAM at the start of each battle and drawn with that enemy's own palette, so
  a Spiteful Crow throws little crows and a Runaway Dog little dogs.

**Party attacks.** When Ness, Paula, Jeff or Poo perform a physical attack ("Bash",
"Shoot"...), the box shows a red/yellow/green gauge with a reticle that sweeps right,
bounces back left, and keeps going. Press A inside the green centre and the hit is a
guaranteed SMAAAASH; anywhere else can never SMAAAASH and the damage falls off linearly
from 100% next to the green to 30% at the red ends. Dithering for four seconds whiffs
at 20%.

The box grows out of its centre when a phase starts and shrinks away afterwards.

Everything else (menus, PSI, items, status effects, the rolling HP meter, backgrounds,
enemy sprites, experience) is untouched.

## Layout

```
EarthBound (USA).sfc      original ROM (No-Intro, SHA-1 d67a8ef3...) - you supply this
ebsrc/                    disassembly + the hack (git branch bullet-hell)
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
  env.sh                  puts the toolchain on PATH
tests/                    harness scripts (*.txt), run.sh, captured screenshots in out/
```

## Building

```
source tools/env.sh
cd ebsrc
ebbinex earthbound.yml "../EarthBound (USA).sfc"   # once: extract assets from the ROM
make -j16                                          # -> build/earthbound.sfc
make -j16 EXTRA="-D BH_DEBUG" BUILDDIR=build-debug # optional: debug-menu build (hold Down+L at power-on)
```

If you add or remove `.INCLUDE` lines in `src/bankconfig/`, delete the affected
`build/US/*.dep` files first; they are only regenerated when the bank's own file changes.

After changing a generator, re-run it before `make` (`python3 tools/gen_bh_gfx.py`,
`python3 tools/gen_bh_enemy_gfx.py`, `python3 tools/gen_bh_enemies.py`). The ROM is
4 MB (the original 3 MB plus banks $F0-$F2); the header already declared 4 MB.

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
  critical according to where the reticle was pressed.
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
