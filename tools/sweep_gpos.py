#!/usr/bin/env python3
"""Generate GPOS-mutated font variants for the captive-portal fault sweep.

Each variant patches one 16-bit word of the GPOS table to 0xffff. The sweep page
loads them in order and shows only the index, so a parser fault freezes the
console at the culpable variant — no logging needed.

usage:
  sweep_gpos.py --base font/crafted.otf --outdir font/sweep --stride 16
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject_gpos as ig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--stride", type=int, default=16)
    ap.add_argument("--value", default="ffff")
    a = ap.parse_args()

    data = open(a.base, "rb").read()
    ver, tables = ig.read_sfnt(data)
    gpos = bytearray(tables[b"GPOS"])
    os.makedirs(a.outdir, exist_ok=True)
    val = bytes.fromhex(a.value)

    n = 0
    for off in range(0, max(1, len(gpos) - len(val) + 1), a.stride):
        g = bytearray(gpos)
        g[off:off + len(val)] = val
        tables[b"GPOS"] = bytes(g)
        out = ig.build_sfnt(ver, tables)
        with open(os.path.join(a.outdir, f"s_{n:03d}.otf"), "wb") as f:
            f.write(out)
        n += 1
    with open(os.path.join(a.outdir, "count.txt"), "w") as f:
        f.write(str(n))
    print(f"generated {n} variants in {a.outdir} (stride {a.stride}, value {a.value})")


if __name__ == "__main__":
    main()
