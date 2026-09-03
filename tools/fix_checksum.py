#!/usr/bin/env python3
"""Recompute the SNES internal header checksum of a HiROM image (in place)."""
import sys
p = sys.argv[1]
d = bytearray(open(p, "rb").read())
hdr = 0xFFB0 if len(d) >= 0x10000 else 0
# zero the checksum fields, sum every byte, then write complement + checksum
d[0xFFDC:0xFFE0] = b"\xFF\xFF\x00\x00"
total = sum(d) & 0xFFFF
d[0xFFDE] = total & 0xFF; d[0xFFDF] = total >> 8
d[0xFFDC] = (~total) & 0xFF; d[0xFFDD] = ((~total) >> 8) & 0xFF
open(p, "wb").write(d)
print(f"{p}: {len(d)} bytes, checksum {total:04X}")
