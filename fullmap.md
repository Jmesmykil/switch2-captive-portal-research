# Full address map — wkc3, chat, ldn, certs (2026-10-31)

Compiled from this session's disassembly + the validated chat map. Rule:
**flat = report − 0x78** for report-framed exports; **file offset = VA − 0x7100000000**
for `wkc3`.

---

## 1. wkc3 (`webkit_wkc`, base 0x7100000000)

build `40ac5a64c4c56a1efbf46d60aaa3aac9d452c389`,
sha256 `8706796b12fef399ac1890ab1ec9eaf62b99718b0bc42f4c88430477ba1d7df6`.

| name | offset | note |
|---|---|---|
| sizeof(CSSFontFace) | `0x9ac7d8` | `mov w0,#0xb8` |
| CSSFontFace ctor | `0x9ac884` | vtable `pacda` @ `0x9ac974` |
| fastMalloc wrapper | `0x3ab668` | PLT thunk `0x1951180` (GOT `0x258a000+0xb0`) |
| CSSFontFace::setStatus | `0x9ae144` | client notify |
| client dispatch (status) | `0x9ae1f8`–`0x9ae224` | `autda` (client\|0xb64f) + `blraa` (slot+0x18\|0x4cdf) |
| status write | `0x9ae238` | `strb w20,[x19,#0x7a]` |
| removeClient | `0x9ae3d0` | reads container from `+0x58` |
| hash-set remove | `0x81a1d0` | called by removeClient |
| rehash/compact | `0x9af698` | writes `container-0x10`, `container-0xC` |
| FontFaceSet::load | `0x9ef78c` | raw-ref vector loop @ `0x9ef860` |
| client thunk | `0x9ee58c` | `sub x0,x0,#0x28` → `0x9ee3e8` |
| FontFace client subobject | `+0x28` | `FontFace+0x30` = `CSSFontFace*` |
| GPOS parser | `0xbac40` | `ldrh w8,[x25,w8,uxtw #1]` |
| ro: CSSFontFace debug str | `0x52ce96` (ro) / VA `0x1e84e96` | debug-only, unreferenced |
| ro: CSSFontFace.cpp path | `0x585f31` (ro) | build path |
| ro: Gigacage strings | 5437455, 5466092, 5949430, … | JSC internals |
| ptrauth reloc table | `0x1a9ee00` region | entries `{addend, 0x411, target}` |

Layout: `+0x08` refcount, `+0x40` sources, `+0x4C` count, `+0x58` clients,
`+0x7A` status, `+0x7F` timing, total `0xB8`.

---

## 2. chat (`040000000000004a`)

build `22de22942b39d845558cc62d41487dffdebd5fe3000000000000000000000000`
main `f03aba227ed411cced3b17995b458a67382320f7691c5db840b4ba70dd46aaff`

| name | flat | report | notes |
|---|---|---|---|
| `factory_type4_cmp` | `0xafde24` | `0xafde9c` | cmp w8,#0x4 |
| `factory_type4_beq` | `0xafde28` | `0xafdea0` | b.eq 0xafdf20 |
| `factory_wrapper_mov` | `0xafdf20` | `0xafdf98` | mov w0,#0x18 |
| `factory_wrapper_bl_new` | `0xafdf24` | `0xafdf9c` | bl operator new (0xf50520) |
| `factory_wrapper_strh_kind` | `0xafdf2c` | `0xafdfa4` | strh w19,[x0,#8] (kind) |
| `factory_wrapper_strh_size` | `0xafdf30` | `0xafdfa8` | strh w8,[x0,#0xa] (size init 8) |
| `factory_wrapper_str_vtable` | `0xafdf3c` | `0xafdfb4` | str x8,[x0] vtable 0x23e2298 |
| `factory_wrapper_str_xzr` | `0xafdf40` | `0xafdfb8` | str xzr,[x0,#0x10] |
| `builder_mov` | `0xaf20b0` | `0xaf2128` | mov w0,#0x28 |
| `builder_bl_new` | `0xaf20b4` | `0xaf212c` | bl operator new (0xf50520) |
| `builder_strh_kind` | `0xaf20c8` | `0xaf2140` | strh w8,[x0,#8] kind 9 |
| `builder_str_vtable` | `0xaf20d4` | `0xaf214c` | str x8,[x0] vtable 0x23e2318 |
| `builder_ldrb_ctrl` | `0xaf2174` | `0xaf21ec` | ldrb w8,[sp,#0xa0] |
| `builder_tst` | `0xaf2180` | `0xaf21f8` | tst w8,#1 |
| `builder_csel` | `0xaf2184` | `0xaf21fc` | csel w8,w10,w9,eq |
| `builder_add4` | `0xaf2188` | `0xaf2200` | add w8,w8,#4 |
| `builder_strh_size` | `0xaf218c` | `0xaf2204` | strh w8,[x23,#0xa] size=wirelen+4 |
| `copy_ldrh_size1` | `0xaff160` | `0xaff1d8` | ldrh w8,[x0,#0xa] |
| `copy_cmp_size1` | `0xaff164` | `0xaff1dc` | cmp w8,#4 |
| `copy_ldp` | `0xaff16c` | `0xaff1e4` | ldp x8,x9,[x1,#0x10] |
| `copy_ldrh_size2` | `0xaff1fc` | `0xaff274` | ldrh w8,[x0,#0xa] |
| `copy_sub` | `0xaff200` | `0xaff278` | sub x19,x8,#4 |
| `copy_cmp_src` | `0xaff20c` | `0xaff284` | cmp x19,x9 source-only |
| `copy_bls` | `0xaff210` | `0xaff288` | b.ls 0xaff224 |
| `copy_add_hdr` | `0xaff22c` | `0xaff2a4` | add x0,x0,#0x10 |
| `copy_mov_len` | `0xaff234` | `0xaff2ac` | mov x2,x19 |
| `copy_bl_memcpy` | `0xaff23c` | `0xaff2b4` | bl memcpy (0xf10d40) |
| `copy_ldr_limit` | `0xaff264` | `0xaff2dc` | ldr x11,[x20,#0x18] |
| `copy_cmp_limit` | `0xaff26c` | `0xaff2e4` | cmp x11,x10 |
| `copy_blo_skip` | `0xaff270` | `0xaff2e8` | b.cc 0xaff27c (skip pad) |
| `dispatch_ldr_vtable` | `0xaf5ee8` | `0xaf5f60` | ldr x15,[x19] |
| `dispatch_ldr_fn` | `0xaf5ef0` | `0xaf5f68` | ldr x8,[x15,#0x10] |
| `dispatch_blr` | `0xaf5ef8` | `0xaf5f70` | blr x8 |
| `free_ldr_ptr` | `0xafe61c` | `0xafe694` | ldr x21,[x19,#0x10] |
| `free_cbz` | `0xafe620` | `0xafe698` | cbz x21,0xafe660 |
| `free_mov_x1` | `0xafe628` | `0xafe6a0` | mov x1,x21 |
| `free_bl_memmove` | `0xafe630` | `0xafe6a8` | bl memmove (0xf01110) |
| `free_str_ptr` | `0xafe634` | `0xafe6ac` | str x23,[x19,#0x10] |
| `free_mov_x0` | `0xafe638` | `0xafe6b0` | mov x0,x21 |
| `free_bl_delete` | `0xafe63c` | `0xafe6b4` | bl operator delete (0x793260) |
| `dtor_str_vtable` | `0xaff0c0` | `0xaff138` | adrp/add/str vtable 0x23e2318 (store at 0xaff0c8) |
| `dtor_ldrb_tag` | `0xaff0cc` | `0xaff144` | ldrb w8,[x0,#0x10] |
| `dtor_tbnz` | `0xaff0d0` | `0xaff148` | tbnz w8,#0,0xaff0d8 |
| `dtor_ldr_len` | `0xaff0d8` | `0xaff150` | ldr x9,[x0,#0x10] |
| `dtor_ldr_ptr` | `0xaff0dc` | `0xaff154` | ldr x8,[x0,#0x20] |
| `dtor_and` | `0xaff0e0` | `0xaff158` | and x1,x9,#~1 |
| `dtor_mov_x0` | `0xaff0e4` | `0xaff15c` | mov x0,x8 |
| `dtor_b_delete` | `0xaff0e8` | `0xaff160` | b operator delete (0x793260) |
| `alloc_af7340` | `0xaf72c8` | `0xaf7340` | mov w0,#0x18 (24 B) vtable 0x23e2298 |
| `alloc_af709c` | `0xaf7024` | `0xaf709c` | mov w0,#0x18 (24 B, vtable 0x23e22d8) |
| `alloc_af6438` | `0xaf63c0` | `0xaf6438` | mov w0,#0x10 (16 B, vtable 0x23e2258) |
| `alloc_af17c8` | `0xaf1750` | `0xaf17c8` | mov w0,#0x18 (24 B, vtable 0x23e2358) |
| `alloc_af1684` | `0xaf160c` | `0xaf1684` | mov w0,#0x28 (40 B, vtable 0x23e2318) |
| `alloc_af6580` | `0xaf6508` | `0xaf6580` | mov w0,#0x60 (96 B, vtable 0x23e21d8) |
| `alloc_b2ef98` | `0xb2ef20` | `0xb2ef98` | mov w0,#0x40 (64 B, vtable 0x23e2c20) |
| `alloc_afdf54` | `0xafdedc` | `0xafdf54` | mov w0,#0x58 (88 B, vtable 0x23e21d8) |
| `ro_stun_cc_path` | `0xfe4c78` | `0xfe4c78` | start of D:\home\teamcity\...\stun.cc path string; 0xfe4cb1 is the 'stun.cc' suffix |

---

## 3. ldn (`0400000000000018`)

| name | offset |
|---|---|
| receive | `0xc19c0` |
| framing | `0xc2540` |
| IP/UDP | `0xc26a0` |
| DHCP | `0xc29c0` |
| options | `0xc2dc0` |
| 5-slot array | `sp+0x10` |
| signed-index | `0x3e544` |

DHCP gates: EtherType `0x0800`, IHL `0x45`, IP len 328, proto 17, UDP 67,
UDP len 308, op 1, cookie `63 82 53 63`, options `0x35`+`0xff`.

---

## 4. Certificates / trust

| item | location | status |
|---|---|---|
| browser root CAs | `/browser/RootCaEtc.pem`, `RootCaSdkAdditional.pem` | in the system-data romfs |
| cert blocklist | `/browser/certBlocklistCommon.json` | present |
| TURN/WebRTC trust | `chat-poc/turn_trust_test.py tls` | **unresolved** — decides chat path |
| fs certs / policy | `~/Desktop/CERTS.md`, `POLICY-HANDOVER.md` | historical |

The TURN cert question is the gate for the only verified write primitive: if the
console's WebRTC stack accepts the harness's CA (or a self-signed cert), the
300-byte reason lands and the overflow runs.

---

## 5. Notes

- Every wkc3 offset above was read from `text.bin` (flat) this session.
- The chat table is the validated 57-site map; `verify-map.py` reports 56/56
  code sites matching.
- The ldn table is from the pre-patch analysis; the 5-slot array is the 23.0.1
  fix (CVE-2026-82079 pre-23.0.0 had 4 slots).
