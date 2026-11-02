# Captive-portal payload pack — font/GPOS probe

**Status:** reachability/diagnostic payload. **Not** a code-exec payload.

## Why it is a probe, not a jailbreak

The only browser bug verified in the dump is the OpenType **GPOS** OOB read in
`SystemWeb` (flat `0xbac40`). It is:

- a **read**, not a write;
- in the **wrapper/parser**, not the engine (`webkit_wkc.nss` is absent from the
  dump);
- behind PAC/CFI/XOM (`pacibsp`/`autibsp`, `autda`/`blraa`, XOM text).

So the honest deliverable is: prove the web-font path is reachable on the
console and give the team a controlled way to feed the GPOS parser.

## What's here

| file | role |
|---|---|
| `index.html` | portal page; declares `@font-face` for `probeGPOS` and renders kerning/ligature-prone text |
| `loader.js` | `FontFace` load with timeout, layout measurement, JSON report to `/report` |
| `font/crafted.otf` | a real OTTO font (STIXGeneral) round-tripped through the injector |
| `font/gpos_base.bin` | the base font's GPOS table, for mutation |
| `tools/inject_gpos.py` | replace/patch the GPOS table in any OTTO font, fixing sfnt checksums |

## Run it with the bench

1. Serve this directory and the probe page from the bench host, e.g. put
   `index.html`, `loader.js`, `font/` at the probe server root, and add a
   `/report` handler that appends the POSTed JSON to a log.
2. Open the portal on the console (bench flow).
3. Read `/report`:

```json
{"ua":"...WifiWebAuthApplet...AppleWebKit/613.0...",
 "hasFontFaceCtor":true,"hasFontsSet":true,"fontLoad":"loaded","width":312.5}
```

That answer is the actual gate: **does the portal browser load a remote
`@font-face` at all?** If `fontLoad` is `loaded`, the GPOS parser is reachable
and mutation work is worth it. If it errors, the portal path is closed and the
effort should move to the engine (requires the applet NCA dump).

## Next: mutate GPOS

The parser anchors (from `REPORT-stsd-detail.md` / `REPORT.md`):

| flat | role |
|---|---|
| `0xba8d8` | function entry (PACIBSP) |
| `0xba918` | sfnt tag == `OTTO` |
| `0xba9c8` | subtable base |
| `0xbabf4` | entry count (`rev16`) |
| `0xbac30` | selector `ldrh w8,[x26],#2` |
| **`0xbac40`** | `ldrh w8,[x25,w8,uxtw #1]` — unchecked index |
| `0xbac4c` | `add x20, x9, x8` — entry as byte offset |
| `0xbac50` | `ldrh w9,[x20]` — dereference |

Usage:

```sh
# one-off byte patch inside GPOS (offset relative to the GPOS table)
python3 tools/inject_gpos.py --base font/crafted.otf --out font/try1.otf --patch 0x12=ffff

# or replace GPOS wholesale
python3 tools/inject_gpos.py --base font/crafted.otf --out font/try2.otf --gpos my_gpos.bin
```

Then point the page at `/font/tryN.otf` with `?font=/font/tryN.otf`.

The intended sweep is the **selector array** the parser reads at `0xbac30`: grow
the 16-bit index until `x25 + 2*idx` leaves the table and lands in adjacent
heap. Watch the console for a fault vs. a normal render — that contrast is the
proof the OOB is reachable.

## What this does **not** do

- no code execution, no heap grooming, no `FontFace.prototype.then` override;
- no engine exploit (needs `webkit_wkc.nss`, i.e. an fs-level applet dump);
- no bypass of PAC/CFI/XOM.

It is the step that turns "the portal can serve a page" into "the portal can
reach the vulnerable font parser with chosen bytes."
