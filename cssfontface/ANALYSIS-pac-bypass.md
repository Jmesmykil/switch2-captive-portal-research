# PAC on fw 23.0.1: what is protected, and how to avoid it

Module set analysed: `chat` (040000000000004a), `ldn` (0400000000000018),
`ssl` (0400000000000024). All AArch64, stripped, statically linked.

## TL;DR

**You do not need to bypass PAC.** On these modules PAC authenticates only
return addresses. Vtable pointers are stored with a plain `str`, loaded with a
plain `ldr`, and dispatched with a plain `blr`. BTI is absent. Data-pointer PAC
is absent. Corrupting an indirect-call target therefore yields PC control with
PAC never consulted.

## Measured instruction inventory

llvm-objdump (this build) renders PAC mnemonics as `hint`; counts below are by
raw encoding, not by mnemonic.

| Instruction | Encoding | chat | ldn | ssl |
|---|---|---|---|---|
| `pacibsp` (sign LR, key B, SP) | `d503237f` | 26,853 | 1,749 | 4,900 |
| `autibsp` (auth LR, key B, SP) | `d50323ff` | 7,349 | 375 | 1,238 |
| `retab` (auth-return, key B) | `d65f0fff` | 22,734 | 1,562 | 4,399 |
| `xpaclri` (strip PAC from x30) | `d50320ff` | 6,771 | 360 | 1,093 |
| plain `ret` | `d65f03c0` | 14,520 | 770 | 2,781 |
| `blr` (indirect call) | `d63f0xxx` | 37,666 | 2,305 | 6,565 |
| `ldraa` (auth data ptr, key A) | — | 77 | 3 | 8 |
| `bti` / `bti c/j/jc` | `d50324xx` | **0** | **0** | — |
| `pacda`/`pacia` on data | — | **0** | **0** | — |

Ratios that matter:

- `ldraa` / `blr` in chat = 77 / 37,666 = **0.20 %** of indirect calls use an
  authenticated target pointer.
- BTI = 0. No forward-edge CFI at the instruction level.
- Data-pointer signing = 0. Object/vtable pointers carry no PAC.

## Evidence: vtable pointer is raw

`chat` STUN-related object, `0xaff4fc`..`0xaff504` (`FUN` installing the vtable):

```asm
aff4fc: adrp x8, 0x23e2000
aff500: add  x8, x8, #0x358      ; x8 = 0x23e2358 (vtable)
aff504: str  x8, [x0, #0x0]      ; object->vtable = x8   <-- PLAIN STORE
```

No `pacia`/`pacib`/`pacda` anywhere in the sequence. The consumer then does
`ldr xN, [x0]` and dispatches; the epilogue of the consumer is `retab` (0xaff4dc),
i.e. the *return* is authenticated but the *target* was not.

This pattern is pervasive: 1,181 `adrp`+`add`+`str x8,[x0,#0]` vtable-install
sites exist in `chat` alone.

## Why this defeats the usual PAC objection

A stack-overflow ROP chain must overwrite a saved LR, which is `pacibsp`-signed
with key B and the prologue SP as modifier; `retab` rejects a forge and traps
(`udf 0x8004` in the explicit check variant). That is the only place PAC is real.

A corrupted vtable pointer is different in kind:
1. It lives in the object's data, written by `str`, never signed.
2. Dispatch is `blr xN`, which does not authenticate.
3. BTI is absent, so the target need not be a `bti c` landing pad — any
   instruction is a valid target under `blr`.
4. The gadget's own prologue `pacibsp` signs the *real* return address that
   `blr` just placed in x30, so the gadget's `retab` authenticates correctly and
   control returns normally.

Conclusion: vtable hijack is a clean, PAC-transparent primitive. PAC only stops
the stack-return path; the forward-edge (indirect call) path is unprotected.

## Implications for the live bugs

| Bug | Primitive | PAC relevance |
|---|---|---|
| `chat` STUN ERROR-CODE (0xaff2b4) | heap overwrite past small object | If grooming places an object with a raw vtable pointer as the victim, overwrite it and dispatch is hijacked. PAC does not block this. |
| browser OpenType GPOS (0xbac40) | unbound index -> OOB read | Read primitive; useful for leaking, and for locating a vtable-owning object. |
| `nfc` (0x1b2a4) | OOB read | Leak only. |

## Remaining constraints (honest)

- **XOM / text unreadable**: cannot read code pages to build ROP gadgets at
  runtime; gadget addresses must be static offsets (known from this dump) or
  derived from a leaked module base.
- **ASLR**: need a leak before writing a target address. The `nfc` and GPOS
  reads are the candidate leak primitives.
- **Heap grooming**: the overwrite must land on an object whose first qword is a
  dispatched vtable pointer, and the replacement pointer must be a controlled,
  valid address. This is the real work, not PAC.
- **No BTI means no landing-pad constraint**, but it also means the kernel may
  enforce this differently in system modules (not in this dump — no `01*` titles).

## Browser engine (`wkc3`) — data PAC **is** present

The scope above is `chat`/`ldn`/`ssl`. The browser engine is a different build and
**does sign data pointers**; the "vtable pointers are never signed" conclusion
does not carry over.

Evidence from `webkit_wkc` (`040000000000085d/exefs/wkc3`, build
`40ac5a64…`, hash `8706796b…`), base `0x7100000000`:

```asm
; constructor installs a SIGNED vtable  @0x9ac974
9ac960: adrp x16, 0x23b5000
9ac964: add  x16, x16, #0x690
9ac968: add  x16, x16, #0x10
9ac96c: mov  x17, x20
9ac970: movk x17, #0xcea0, lsl #48   ; modifier = object | 0xcea0...
9ac974: pacda x16, x17
9ac978: mov  w0, #0x20
9ac97c: str  x16, [x19, #136]        ; signed vptr stored

; client dispatch authenticates  @0x9ae1f8..0x9ae224
9ae208: ldr  x16, [x0]               ; raw vptr
9ae210: movk x17, #0xb64f, lsl #48   ; modifier = client | 0xb64f...
9ae214: autda x16, x17
9ae218: ldr  x8, [x16, #0x18]!       ; slot +0x18
9ae220: movk x16, #0x4cdf, lsl #48
9ae224: blraa x8, x16
```

So in the browser:

- an **unsigned fake vtable fails** — `autda` will not authenticate it;
- the modifier is **address-derived** (`client|0xb64f…`), so a captured signed
  pointer is not portable across addresses;
- a spray of unsigned pointers cannot reach the client call.

The viable route is a same-size reclaim carrying a **legitimate signed vptr**
(`sizeof(CSSFontFace) = 0xb8`, `@0x9ac7d8`), then corrupt a JSC object with the
stale accesses (`+0x40`/`+0x4C` reads, `+0x7A` write) — not a vtable hijack.
This is why `DECOMP-REQUESTS.md` §F says the `chat`/`ldn` PAC model does not apply
to this module.

## Next step

Pick a `chat` object on the STUN receive path whose first qword is a vtable and
whose lifetime overlaps the overflow, then determine the heap order between the
overflow destination and that object. PAC is settled; heap order is the blocker.
