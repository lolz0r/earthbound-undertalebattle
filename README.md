# EarthBound: Undertale-style bullet-hell battles

A ROM hack of EarthBound (SNES, USA) that replaces the passive "enemy attacks, you take
damage" turn with a real-time dodge phase, and the party's physical attacks with a
timing gauge, in the style of Undertale.

The hack is built from source: the [ebsrc](https://github.com/Herringway/ebsrc)
disassembly (checked out in `ebsrc/`, branch `bullet-hell`) rebuilds the original ROM
byte-for-byte, and the new engine is added on top as normal source files.

## What changes in the game

**Enemy turns.** After the usual "X attacks!" / "X used PSI Fire!" text, a white box
with a black interior opens above the party's HP windows and the enemies slide up above
it. The player's red heart appears in the box and a bullet pattern plays for about four
seconds. Move the heart with the d-pad (hold B or X to move slowly). Every hit is a
short invincibility flash.

* 0 hits: the action is skipped and "<name> dodged quickly!" is shown.
* 1 hit: the action resolves at 40% damage. 2 hits: 70%. 3 or more: full damage.
* Blue bullets only hurt while the heart is moving, orange ones only while it is still.
* Bullet speed scales with the enemy's level; the pattern depends on the action type
  (physical / piercing / PSI / other) and on the enemy, so different enemies attack
  differently. Patterns are small bytecode programs in
  `ebsrc/src/battle/bullet_hell/bh_patterns.asm`.

**Party attacks.** When Ness, Paula, Jeff or Poo perform a physical attack ("Bash",
"Shoot"...), the box shows a red/yellow/green gauge with a cursor sweeping across it.
Press A near the green centre for up to 130% damage; the edges give 30%; not pressing
at all gives 20%. SMAAAASH criticals still happen on top of that.

The box grows out of its centre when a phase starts and shrinks away afterwards.

Everything else (menus, PSI, items, status effects, the rolling HP meter, backgrounds,
enemy sprites, experience) is untouched.

## Layout

```
EarthBound (USA).sfc      original ROM (No-Intro, SHA-1 d67a8ef3...) - you supply this
ebsrc/                    disassembly + the hack (git branch bullet-hell)
  src/battle/bullet_hell/ bh_engine.asm (engine), bh_patterns.asm (bullet patterns),
                          bh_data.asm (graphics/palette/type table)
  include/bullet_hell.asm constants, direct-page layout, pattern macros
  src/bin/bh/             generated sprite tiles + palette
tools/                    toolchain, all built in user space
  cc65/ ebbinex/ spcasm/ ldc2/   assembler, asset extractor, SPC assembler, D compiler
  snes9x/libretro/        headless emulator core
  harness/ebharness.c     scripted headless test runner (screenshots, RAM peek/poke,
                          save states, symbol names from the ld65 map)
  gen_bh_gfx.py           generates src/bin/bh/*.bin from ASCII art
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

After changing `tools/gen_bh_gfx.py` run `python3 tools/gen_bh_gfx.py` before `make`.

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
  applies.
* `BH_RENDER` in the battle frame renderer (`C2F8F9`) appends the heart, bullets, gauge
  and box border to OAM after the enemy sprites. Enemy sprites are drawn shifted up by
  `BH_YSHIFT` (patched into `render_battle_sprite_row.asm`).
* The black interior is hardware window 2 masking BG1/BG2, with its left/right edges
  driven per scanline by HDMA channel 6 (channels 0-3 belong to the battle backgrounds,
  4 to the letterbox, 5 to the swirl). The game's window registers are mirrored so they
  can be restored afterwards.
* Sprite tiles (2.5 KB) are uploaded at the start of each phase into the first unused
  32x32 enemy-sprite "piece" slots of OBJ VRAM, and the palette into OBJ palette 7.
* RAM: the engine's direct page is a 224-byte gap after `OAM1_HIGH_TABLE` that the
  original game never used; the 32-entry bullet table sits in previously unused space at
  the end of the main RAM segment (`BH_BULLETS`). Nothing overlays game buffers.

One SNES gotcha worth knowing: when more than 34 8-pixel sprite slivers share a scanline
the PPU drops the *highest priority* sprites first, so the box border uses 16x16 side
pieces and the heart/cursor are always written to OAM first.
