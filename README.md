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

`EarthBound - Bullet Hell.ips` (about 280 KB) turns a clean EarthBound (USA) ROM into the
hacked one. No ROM is distributed here; you need your own copy.

| | size | SHA-1 |
|---|---|---|
| input: `EarthBound (USA).sfc`, No-Intro, no copier header | 3,145,728 bytes | `d67a8ef36ef616bc39306aa1b486e1bd3047815a` |
| output: patched ROM | 4,194,304 bytes | `23f1e2a35ad6ee6aeb6191b00569043cd46ca798` |

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
* The result is 4 MB (the original 3 MB plus four new banks of per-enemy data) with a
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
* **White shapes for bullets, in the enemy's theme.** Bullets are monochrome shapes
  in the Undertale manner, and each enemy throws the ones that suit it: crows throw
  feathers, beaks, eggs and wings; dogs bones, paws, fangs and footprints; snakes
  waves and scales; UFOs saucers, planets and comets; robots gears, bolts, nuts and
  lightning; Starmen stars and laser bars; ghosts wisps, skulls and hands; zombies
  bones and tombstones; cultists pentagrams and eyes; cops badges and shields; punks
  skateboards and shards; piles of puke drips, splats and bubbles; Giygas hands,
  spirals and wisps... `tools/gen_bh_enemy_gfx.py` holds a library of about 150
  shapes and 80 themes matched by enemy name (with the game's insect/metal type as
  the fallback). Every enemy gets its own sheet of four 16x16 shapes drawn from its
  theme, so two dogs still differ, and the 171 enemies whose battle sprite is bigger
  than 32 px get one 32x32 shape drawn with the hardware's 32x32 sprite size and
  mirrored for the odd bullet types (the size classes drive the spacing of the
  generated attack programs). The sheets of the enemies present are uploaded to
  sprite VRAM at the start of each battle and drawn in white with the engine's own
  palette. Earlier versions cut the bullets out of each enemy's own battle sprite;
  the shapes read better at bullet size.

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

## Six attack minigames, two ways to take a hit

Each physical attack by a party member picks one of six minigames at random
(one in six each); each enemy attack is a dodge box three times in four and a
timed block otherwise. Auto Fight skips all of them. Each box carries a one-line
instruction along its bottom edge, in the same sprite font as the grade labels
("MASH ANY BUTTON", "TAP THE BUTTON A NOTE HITS", "DODGE THE BULLETS" ...); the
lines are pre-rendered by `tools/gen_bh_gfx.py` (`bh_hints.bin`, bank $F3) and a
game uploads its own line into three spare sprite slots when it starts. Every graded
press floats a **PERFECT / GOOD / OK / MISS** label with its own sound, so the grade
is never in doubt, and a game you never press a button in says MISS and whiffs. Every
press is also shown where it lands: a white ring lights the pressed lane button, the
gauge cursor, the focus target, the mash prompt or the combo step for ten frames and the
icon pops up for the first five; a stopped slot reel gets the same ring.

Every box is one of the game's own text windows: the same rounded frame and interior
as the battle text and HP windows, in whatever flavour the player picked (Plain, Mint,
Strawberry, Banana, Peanut). It grows out of its centre and shrinks back over eight
frames like before, as a real window at every step.

- **Timing gauge** (as before): press A while the bouncing reticle is in the green
  for a SMAAAASH; yellow always connects, red misses 70 % of the time.
- **Rhythm** (3-5 seconds): the A, B, X and Y buttons sit in the middle of the box
  in their controller arrangement (X top, Y left, A right, B bottom, Super Famicom
  colours). Notes drawn as the same icons fly in from the sides (Y's from the left,
  the others from the right); press that button as the note reaches it. Within 4 px
  is PERFECT (10 points), 10 px GOOD (7), 18 px OK (4); the wrong button, or letting
  a note pass, is a MISS. The strip in the top-left corner keeps one block per note.
  Damage is 40-100 % by points, 90 % or better is a SMAAAASH.
- **Focus**: four brackets close in on a crosshair; press A when they frame it.
  PERFECT (within 2 px) is a SMAAAASH at 100 %, GOOD 85 %, OK 70 %, a MISS 40 %
  and the usual hit roll. The crosshair turns into a spark on a perfect press.
- **Mash**: mash any face button (A, B, X or Y) for two and a half seconds. Each
  press adds 14 to a nine-block power bar (red, yellow, green thirds) that drains
  one per frame; a line marks the exact fill and moves with every press, the prompt
  shows the button you just hit and jumps, each press ticks, and OK / GOOD / PERFECT
  pop up as the bar crosses 40 / 90 / 130. A full bar sparks. The fill when time
  runs out is the grade: 130+ of 144 PERFECT (SMAAAASH), 90+ GOOD, 40+ OK, less MISS.
- **Slots**: three reels of cherry, bell, seven and star spin (a symbol every six
  frames, staggered); A stops the reel the blinking A button points at. Three of a
  kind is PERFECT (a SMAAAASH; three sevens hit for 120 %), a pair GOOD (85 %),
  nothing OK (60 %). The reels stop by themselves after four seconds.
- **Combo**: five button icons; press them in order before the timer bar (nine
  blocks, three seconds) runs out. A right press turns the icon into a spark, a
  wrong or late one into a red block. Five right is PERFECT (SMAAAASH), four GOOD,
  two or three OK, less a MISS.
- **Timed block** (enemy attacks): the same brackets as the focus game close on
  your heart. PERFECT dodges the attack outright ("dodged quickly"), GOOD takes
  50 %, OK 75 %, a MISS the full hit.

Sprite budget: the engine's nine 32x32 tile pieces go into the sprite VRAM slots
left after the enemy sprites; a piece that finds no slot is marked unavailable and
the games that need it are not picked (with no room for the box pieces at all the
action resolves classically).

`poke BH_DP+0x9C n` in a harness script forces a kind (1 gauge, 2 rhythm, 3 focus,
6 mash, 7 slots, 8 combo for attacks; 4 block, 5 dodge box for enemy attacks).
`tests/test_rhythm_p2.txt`, `tests/test_combo_p2.txt` and `tests/test_slots.txt` are
generated from a first pass that reads the random lanes, sequence or reel timing and
then press the right buttons at the right frames (`waitle`/`waitmem`);
`tests/test_mash*.txt` and `tests/test_focus*.txt` cover the rest.

## Per-attack games (a Set Up option, off by default)

The file-select **Set Up** menu, after the text speed, sound and flavour questions,
asks one more: **Battle games: Standard / Per attack**. The setting is an unused event
flag saved in the file, so existing saves default to Standard (the games described
above) and every file can be set on its own.

With **Per attack**, each enemy attack plays a game built for that enemy and that
attack instead of the random dodge box or timed block: a Spiteful Crow's peck comes
at the heart from one side and you hold the d-pad toward it, its "eyes" attack drifts
crows and green blocks through the box, Master Belch's slime closes the walls in, a
Territorial Oak's flames light danger cells, a hypnosis attack scrambles the d-pad
for one dodge box, a tempo attack asks for presses on the beat. The design table with
every one of the 537 enemy-attack pairs is `docs/attack_minigames.md`; it composes
them from twenty building blocks:

| block | the game | block | the game |
|---|---|---|---|
| 1 dodge box | the enemy's own bullet pattern | 11 spotlight * | bullets show only near the heart |
| 2 timed block | the four brackets | 12 wiggle | alternate Left/Right to fill a meter |
| 3 danger cells | cells warn, then strike | 13 counter shot | press A as the sprite crosses the crosshair |
| 4 sweeps | full-width bars with a gap | 14 beat | press A on the tick |
| 5 hold and release | let go of A inside the green | 15 face it | hold the d-pad toward the strike |
| 6 arrow chain | press the arrows in order | 16 pick a cell | be in the safe cell at the reveal |
| 7 scrambled controls * | mirrored, rotated or lagging d-pad | 17 freeze * | do not move on the flash |
| 8 pull * | a drag toward a harmful edge | 18 copy | repeat the shown sequence |
| 9 closing walls * | survive the shrinking box | 19 count steps | step onto the ring |
| 10 catch and avoid | touch green, avoid the rest | 20 two hearts * | a mirrored second heart |

The blocks marked * are modifiers: they lay over the dodge box or over a heart-moving
block (3, 4, 10, 16; scrambled controls also over the d-pad games 6, 15 and 19;
freeze over everything but the timed block). Each row of the table gets its own
parameters (pattern, speed, gap, count, tell length, radius...) hashed from the enemy
and action, so two enemies sharing a block still play differently, and every game
carries its own instruction line. Grades and damage follow the standard games: a
clean run dodges the attack, hits scale the damage (50 / 75 / 100 %). An attack with
no row (the flavour-only actions, and any block that finds no sprite room) plays the
standard dodge box.

The data is generated: `tools/gen_bh_attack_games.py` reads the design table, the
action enum and the per-enemy records and writes
`ebsrc/src/battle/bullet_hell/bh_attack_games.asm` (an index by enemy id and 9-byte
entries: action, block, modifier, four parameters, hint line; 858 entries for 227
enemies, bank $F0). The engine is `bh_ag_engine.asm` (bank $EE, one init / update /
render routine per block, the modifier hooks) and the option code is `bh_setup.asm`.
The instruction lines moved to a fourth new bank ($F3, `bank33.asm`) to make room.

Test hooks: `poke BH_DP+0x9C 9` forces the per-attack path, `poke BH_AG_STATE+7 <block>`
forces a block with built-in defaults (a modifier block number plays the dodge box
with that modifier), `poke BH_AG_STATE+80 <modifier>` lays a modifier over the forced
block. Harness values are hex bytes. `tests/test_ag_*.txt` cover every block and
modifier (`test_ag_option*.txt` check the option itself).

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

### 2026-09-06

- Bullet shapes follow the enemy's theme: a library of about 150 white shapes and 80
  themes (crows throw feathers and beaks, dogs bones and paws, robots gears and
  bolts, ghosts wisps and skulls, cops badges, punks skateboards...), matched by
  enemy name. `python3 tools/gen_bh_enemy_gfx.py ebsrc --list` prints every enemy's
  theme and shapes.

### 2026-09-05

- Bullets are white shapes (stars, rings, diamonds, crosses, lines...) instead of
  pieces cut from each enemy's sprite. Each enemy keeps its own sheet of shapes and its
  bullet size class, so every attack program plays exactly as before.
- Per-attack games: a Set Up option ("Battle games: Standard / Per attack", off by
  default) under which every enemy attack plays the game designed for it in
  `docs/attack_minigames.md`. Eighteen new building blocks (twelve games and six
  modifiers) in `bh_ag_engine.asm`, the generated table `bh_attack_games.asm`, d-pad
  arrow sprites, and a fourth new bank for the instruction lines.
- Two engine helpers no longer call the game's `MULT16` / `DIVISION16S`: those keep
  their temporaries in the direct page and, with the engine's direct page selected,
  overwrote the instruction line's and one piece's tile numbers.
- Press feedback in every minigame: the icon the press lands on (lane button, gauge
  cursor, focus target, mash prompt, combo step, stopped reel) is ringed in white and
  pops up. One shared tracker (`BH_MG_PRESS`) remembers the last face button pressed.
- Giygas's praying-phase background (battle group 478) keeps its BG2 tiles in the
  upper half of the sprite VRAM, so the engine's tiles there showed as noise lines in the
  red swirl. The engine now uses only the first 16 sprite slots in that group: seven of
  the nine pieces fit behind Giygas's nine, the slot machine and the instruction line sit
  out that phase, and the swirl stays clean.
- A full playthrough harness for the final battle (`tools/giygas_playthrough.py`, below).
  The reported lock-ups did not reproduce on snes9x or bsnes-mercury, including from a
  player's own save; the 1-3 second pauses around the prayers are the game's own fades
  and scripted waits (vanilla EarthBound shows the same pauses, measured frame by frame).

### 2026-09-04

- The dodge box and every minigame box are now real game windows: rounded corners and
  the player's text-window flavour instead of a white sprite outline. The box borrows
  the naming-screen confirmation window id and reads its geometry from RAM; its
  interior tiles are drawn at low BG3 priority so the heart, bullets and labels stay
  in front of the interior while the frame stays in front of them.
- Five new minigames, picked at random: a rhythm game with the SNES buttons in the middle
  of the box, a focus/timed-block game for attacks and enemy attacks, a mash bar, a slot
  machine and a button combo (above), with PERFECT / GOOD / OK / MISS labels and sounds on
  every press and a one-line instruction drawn inside each box.
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
  src/battle/bullet_hell/ bh_engine.asm (engine, bank $EE), bh_minigames.asm (the six
                          attack games and the timed block), bh_ag_engine.asm (the
                          per-attack games and modifiers), bh_setup.asm (the Set Up
                          option), bh_data.asm (base graphics, type table),
                          bh_enemies.asm (generated: per-enemy records, 462 attack
                          programs, hit boxes; bank $F0), bh_attack_games.asm
                          (generated: the per-attack game table; bank $F0)
  src/bankconfig/US/bank30-33.asm  the four new banks ($F0-$F3) of the 4 MB ROM
  include/bullet_hell.asm constants, direct-page layout, pattern opcode macros
  src/bin/bh/             generated: base tiles, palette, per-enemy bullet shape sheets (118 KB)
tools/                    toolchain, all built in user space
  cc65/ ebbinex/ spcasm/ ldc2/   assembler, asset extractor, SPC assembler, D compiler
  snes9x/libretro/        headless emulator core
  harness/ebharness.c     scripted headless test runner (screenshots, RAM peek/poke,
                          save states, symbol names from the ld65 map)
  gen_bh_gfx.py           base tiles (heart, box lines, gauge, bones) from ASCII art
  gen_bh_enemy_gfx.py     the shape library and themes; writes every enemy's bullet sheet and hit boxes
  gen_bh_enemies.py       writes the per-enemy records and attack programs
  gen_bh_attack_games.py  writes the per-attack game table from docs/attack_minigames.md
  make_ips.py             builds the IPS patch from the original and the built ROM
  apply_ips.py            applies it (Python 3 only, verifies SHA-1s, strips copier headers)
  fix_checksum.py         rewrites the header checksum (run by the Makefile after linking)
  env.sh                  puts the toolchain on PATH
docs/attack_minigames.md  the design table: one game per enemy attack, 20 building blocks
tests/                    harness scripts (*.txt), run.sh, run_batch.sh, screenshots in out/
```

## Building from source

The engine lives in `patches/ebsrc-bullet-hell.patch`, a diff against ebsrc commit
`0197d6c13ef11ad3280e9388e08a646ab1030d15` (38 source files: the engine, its include
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
python3 ../tools/gen_bh_enemy_gfx.py               # per-enemy bullet shape sheets and hit boxes
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

### Playing the whole final battle through the game's own script

`tools/giygas_playthrough.py` plays the Giygas fight from the start of enemy group 475 to
the end of the ninth prayer with nothing but pad input, one command menu or one round per
harness run, and locates a hang if a round never comes back:

```
python3 tools/make_scripted_rom.py                     # build-debug/: a Talk-to starts battle group 475
python3 tools/giygas_playthrough.py                    # synthetic level-99 party from the after_intro state
python3 tools/giygas_playthrough.py --sram tests/out/my.srm --no-refill   # from a real battery save, no HP top-ups
python3 tools/giygas_playthrough.py --core mercury --out tests/out_merc_new  # bsnes-mercury (states are per core)
```

At every menu it reads whose it is and what the first command says (from the game's own
menu tables, so "Do Nothing" is recognised when the game takes attacking away), then Ness,
Jeff and Poo Bash the vulnerable enemy and Paula Bashes until her menu offers the final
prayers (`--pray-early` makes her pray from the second phase on, which runs the random
prayer effects). Rounds are played by `playround`: the dodge AI steers through dodge
boxes, A is tapped (or held with `--hold-a`) through text, minigames and timed blocks,
HP is topped up every frame unless `--no-refill`. Pokey's two speeches, the Devil's
Machine, Giygas's three forms, the eight prayer cutscenes and the player's prayer all
happen through the game's script. States are saved per step (`<tag>_s<N>.st`), so a
run can be resumed with `--start-state`. When no menu returns within `--round-max`
frames the driver prints the CPU registers and a 120-frame PC sample (`cpu`, `trace`,
from the patched snes9x core: `tools/snes9x-ebh-probe.patch` adds `ebh_get_cpu` to the
libretro build).

Results on 2026-09-05 (build e7dbd18): the complete battle, all nine prayers and the
ending were reached on snes9x and on bsnes-mercury, with the synthetic party, with the
random early prayers, with three different RNG paths, holding A, and from a player's
real battery save both with and without HP top-ups. No hang was found; every run that
"lost its menu" had won and was already in the ending.

### Harness commands added for the Giygas and playtest work

- `cpu` prints the 65816 registers with the nearest map symbol; `trace N` runs N frames
  and lists the distinct PCs seen after each frame (needs the patched snes9x core).
- `spamd` is `spam2` with the first press delayed by one interval (a menu about to open is
  not pressed); `spamu BTN INT MAX A V` taps until the byte at A differs from V;
  `spamor BTN INT MAX A V1 V2` taps until it equals V1 or V2.
- `playround MAX [REFILL] [HOLD]` plays until a command window has focus (see above).
- `sram FILE` loads a battery save into the cartridge SRAM (use before the title screen).

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
  and labels to OAM after the enemy sprites (and a sprite outline for the box only when
  no window slot was free). Enemy sprites are drawn shifted up by
  `BH_YSHIFT` (patched into `render_battle_sprite_row.asm`): just above the gauge for
  party attacks, off the top of the screen for dodge phases (`BH_CALC_YSHIFT` mode).
* `BH_SMASH_OVERRIDE` at the top of the game's SMAAAASH check forces or forbids the
  critical according to where the reticle was pressed; `BH_MISS_OVERRIDE` at the top of
  `MISS_CALC` and `DETERMINE_DODGE` forces the outcome of the hit/miss rolls (always hit
  after a dodge-phase hit or a yellow/green press, always miss for a whiff or a red
  press that rolled a miss).
* The box is a game window: `CREATE_WINDOW` reads the geometry of window id `$24` (the
  naming-screen confirmation, never open in battle) from `BH_BULLETS + 80` instead of the
  ROM table, and the engine opens it at the box rectangle, rounded to whole tiles. The
  window drawer adds the BG3 priority bit to every interior tile, and high-priority BG3
  covers all sprites, so the engine writes `$E040` into the window's tile buffer: the
  add wraps to `$0040`, the blank flavour tile at low priority, under the heart and
  bullets, while the frame tiles stay in front of them. While the box grows or shrinks
  the window's position and size are rewritten each frame (`BH_GAME_WINDOW_FIT`), the
  window is redrawn and its tilemap upload queued directly, since `WINDOW_TICK` skips
  both while a held button makes text print instantly. The heart and the labels keep
  clear of the eight-pixel frame tiles (`BH_FRAME_*`).
* The interior behind the low-priority tiles is hardware window 2 masking BG1/BG2, with
  its left/right edges driven per scanline by HDMA channel 7 (channels 0-3 belong to
  the battle backgrounds, 4 to the letterbox, 5 and 6 to the swirl and oval effects).
  The game's window registers are mirrored so they can be restored afterwards.
* Sprite tiles are uploaded once per battle, right after the enemy sprites are loaded
  (screen still blanked), into the first unused 32x32 enemy-sprite "piece" slots of OBJ
  VRAM: five base pieces, then one sheet per enemy kind present (up to four). They are
  re-uploaded only if an enemy is added mid-battle. Everything the engine draws uses
  OBJ palette 7. Uploading the tiles per phase overran the vertical blank and produced
  a garbled frame.
* RAM: the engine's direct page is a 224-byte gap after `OAM1_HIGH_TABLE` that the
  original game never used; the 32-entry bullet table sits in previously unused space at
  the end of the main RAM segment (`BH_BULLETS`). Nothing overlays game buffers.

The window HDMA table is double-buffered and the window registers are only written once
per phase: rewriting WH2/WH3 mid-frame blanks the mask until the next HDMA entry, and
editing the live table tears.

One SNES gotcha worth knowing: when more than 34 8-pixel sprite slivers share a scanline
the PPU drops the *highest priority* sprites first, so the fallback sprite outline uses
16x16 side pieces, the heart/cursor are always written to OAM first, and wall rows are
spaced so a full-width row stays under the limit.

Per-frame cost: each bullet's tile, palette attribute and hit box are resolved once when
it spawns (`BH_SET_TYPE`), so the update and render loops only add, compare and copy.
The headless harness shows no dropped frames with a dozen bullets and three enemies.
