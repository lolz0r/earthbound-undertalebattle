#!/usr/bin/env python3
"""Copy ebsrc/build/earthbound.sfc to ebsrc/build-debug/ with the "Who are you talking to?"
fallback text replaced by a start-battle command for enemy group 475 (the Giygas fight),
so a scripted Talk-to on the overworld starts the final battle through the game's own
battle-start path. tests/run.sh <script> debug runs against that copy.
usage: make_scripted_rom.py [group] [source.sfc] [destination dir]   (the map is copied from ebsrc/build)"""
import shutil, sys, os
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
group = int(sys.argv[1]) if len(sys.argv) > 1 else 475
src = sys.argv[2] if len(sys.argv) > 2 else f"{T}/ebsrc/build/earthbound.sfc"
dst_dir = sys.argv[3] if len(sys.argv) > 3 else f"{T}/ebsrc/build-debug"; os.makedirs(dst_dir, exist_ok=True)
rom = bytearray(open(src, "rb").read())
off = 0xC7C588 - 0xC00000            # HiROM file offset of MSG "Who are you talking to?"
rom[off:off + 5] = bytes([0x1F, 0x23, group & 0xFF, group >> 8, 0x02])   # [1F 23 group] start battle, [02] end
open(f"{dst_dir}/earthbound.sfc", "wb").write(rom)
shutil.copy(f"{T}/ebsrc/build/earthbound.map", f"{dst_dir}/earthbound.map")
print(f"wrote {dst_dir}/earthbound.sfc (Talk-to starts battle group {group})")
