#!/usr/bin/env python3
"""Apply the bullet-hell IPS patch to a clean EarthBound (USA) ROM.

usage: apply_ips.py <original.sfc> <patch.ips> <output.sfc>

Only needs Python 3. Checks the input against the known original SHA-1, strips a
512-byte copier header if one is present, applies the patch (plain and RLE records,
growing the file to 4 MB) and prints the SHA-1 of the result so it can be compared
with the value in README.md.
"""
import hashlib, sys

ORIGINAL_SHA1 = "d67a8ef36ef616bc39306aa1b486e1bd3047815a"   # EarthBound (USA).sfc, 3 MB, no header
ORIGINAL_SIZE = 3 * 1024 * 1024

def apply(rom, ips):
    if ips[:5] != b"PATCH":
        sys.exit("not an IPS file (missing PATCH signature)")
    out = bytearray(rom)
    p = 5
    while ips[p:p + 3] != b"EOF":
        off = int.from_bytes(ips[p:p + 3], "big")
        size = int.from_bytes(ips[p + 3:p + 5], "big")
        p += 5
        if size == 0:                                   # RLE record
            run = int.from_bytes(ips[p:p + 2], "big")
            data = bytes([ips[p + 2]]) * run
            p += 3
        else:
            data = ips[p:p + size]
            p += size
        if off + len(data) > len(out):
            out += b"\x00" * (off + len(data) - len(out))
        out[off:off + len(data)] = data
    return bytes(out)

def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    rom_path, ips_path, out_path = sys.argv[1:4]
    rom = open(rom_path, "rb").read()
    if len(rom) == ORIGINAL_SIZE + 512:
        print("input has a 512-byte copier header; removing it")
        rom = rom[512:]
    got = hashlib.sha1(rom).hexdigest()
    if got != ORIGINAL_SHA1:
        print(f"warning: input SHA-1 is {got}, expected {ORIGINAL_SHA1} (unheadered EarthBound (USA));"
              " the result will probably not work")
    out = apply(rom, open(ips_path, "rb").read())
    open(out_path, "wb").write(out)
    print(f"wrote {out_path}: {len(out)} bytes, sha1 {hashlib.sha1(out).hexdigest()}")

if __name__ == "__main__":
    main()
