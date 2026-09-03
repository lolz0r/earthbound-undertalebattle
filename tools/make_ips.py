#!/usr/bin/env python3
"""Build an IPS patch from the original ROM and the hacked ROM, then verify it.

usage: make_ips.py <original.sfc> <modified.sfc> <out.ips>

The IPS format writes records at 24-bit offsets, so it can grow a 3 MB ROM to 4 MB
(records past the original's end append). Runs of one byte become RLE records, so the
empty expansion banks cost almost nothing. A record may not start at offset 0x454F46
("EOF"); such a record is started one byte earlier.
"""
import hashlib, sys

def sha1(b):
    return hashlib.sha1(b).hexdigest()

def build(orig, mod):
    size = len(mod)
    src = orig + b"\x00" * (size - len(orig))
    out = bytearray(b"PATCH")
    i = 0
    while i < size:
        if src[i] == mod[i]:
            i += 1
            continue
        start = i
        # extend the record while bytes differ or the gap of equal bytes is short
        while i < size and (src[i] != mod[i] or (i + 4 < size and any(src[k] != mod[k] for k in range(i, min(i + 4, size))))):
            i += 1
        chunk = mod[start:i]
        pos = 0
        while pos < len(chunk):
            off = start + pos
            if off == 0x454F46:            # cannot start a record here
                off -= 1; pos -= 1
                piece = chunk[pos:pos + 0xFFFF]
                out += off.to_bytes(3, "big") + len(piece).to_bytes(2, "big") + piece
                pos += len(piece)
                continue
            # RLE for long runs
            run = 1
            while pos + run < len(chunk) and chunk[pos + run] == chunk[pos] and run < 0xFFFF:
                run += 1
            if run >= 16:
                out += off.to_bytes(3, "big") + b"\x00\x00" + run.to_bytes(2, "big") + bytes([chunk[pos]])
                pos += run
                continue
            # plain record up to the next long run
            end = pos + 1
            while end < len(chunk) and end - pos < 0xFFFF:
                r = 1
                while end + r < len(chunk) and chunk[end + r] == chunk[end] and r < 16:
                    r += 1
                if r >= 16:
                    break
                end += 1
            piece = chunk[pos:end]
            if start + pos + len(piece) > 0x454F46 > start + pos:
                pass  # a record spanning the magic offset is fine; only a record *starting* there is not
            out += (start + pos).to_bytes(3, "big") + len(piece).to_bytes(2, "big") + piece
            pos = end
    # the patched file must reach the modified ROM's full size even when its tail equals
    # the zero padding: write the last byte explicitly
    if len(mod) > len(orig):
        off = len(mod) - 1
        out += off.to_bytes(3, "big") + (1).to_bytes(2, "big") + bytes([mod[off]])
    out += b"EOF"
    return bytes(out)

def apply(orig, ips):
    assert ips[:5] == b"PATCH"
    out = bytearray(orig)
    p = 5
    while ips[p:p + 3] != b"EOF":
        off = int.from_bytes(ips[p:p + 3], "big"); size = int.from_bytes(ips[p + 3:p + 5], "big"); p += 5
        if size == 0:
            run = int.from_bytes(ips[p:p + 2], "big"); val = ips[p + 2]; p += 3
            data = bytes([val]) * run
        else:
            data = ips[p:p + size]; p += size
        if off + len(data) > len(out):
            out += b"\x00" * (off + len(data) - len(out))
        out[off:off + len(data)] = data
    return bytes(out)

def main():
    orig_p, mod_p, out_p = sys.argv[1:4]
    orig = open(orig_p, "rb").read(); mod = open(mod_p, "rb").read()
    ips = build(orig, mod)
    check = apply(orig, ips)
    if check != mod:
        sys.exit("verification failed: applying the patch does not reproduce the modified ROM")
    open(out_p, "wb").write(ips)
    print(f"{out_p}: {len(ips)} bytes")
    print(f"original: {len(orig)} bytes, sha1 {sha1(orig)}")
    print(f"patched:  {len(mod)} bytes, sha1 {sha1(mod)}")

if __name__ == "__main__":
    main()
