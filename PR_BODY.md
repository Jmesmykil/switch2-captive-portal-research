# P4: fake JSArrayBufferView -> full arbitrary R/W from plain JS (chain-write.html)

## What this adds

`chain-write.html` is the P4 stage of the data-only chain. It reuses the proven
P1-P3 machinery verbatim from `chain-final.html` (the `uaf()` FontFace
free-during-load trigger, the `ArrayBuffer(0xB8)` reclaim, the fake
`m_featureSettings` Vector read primitive `rd()`, the W/F/B pointer walk) and
converts the retarget-free into the last step the dossier calls for
(STAGE2-DOSSIER.md, P4):

> reclaim the freed GC-heap block bytes (the pool also serves MarkedBlocks -
> heap/Heap.cpp:358) -> fake JSArrayBufferView with a raw m_vector -> FULL
> ARBITRARY R/W. No PC touched.

The P4 primitive in one sentence: **corrupt one live `JSDataView` cell in place
(free-then-reclaim write) so its `m_vector` is an attacker-chosen raw pointer
and its `m_length` is attacker-chosen; every subsequent `dva.getUint32(k)` /
`dva.setUint32(k, v)` then reads/writes `m_vector + k` with no other check.**
No PC, no JIT, no fake vtable, no PAC encounter (LLInt-only build; see
"Mitigations" below).

`chain-final.html` is untouched; the new file is self-contained (same
`lg()` -> POST /report channel, same constants `S=0xb8, F=0x28, FZ=0x30,
FC=0x34, ST=0x7a`).

## The mechanism (per step, with the source that pins it)

1. **Trigger + reclaim + fake face + `rd()`** - verbatim `chain-final.html`
   (CSSFontFace UAF; `new ArrayBuffer(0xB8)` reclaim; fake face fields
   buf@+0x28 / size@+0x30 / cap@+0x34; read = `featureSettings.charCodeAt`).
   The walk leaks `B` = the reclaimed chunk's own address (face+0x60 ->
   weak-block+8 -> FontFace m_backing+0x30).
2. **Victim spray** - `0x100 x new DataView(new ArrayBuffer(0xDE))` and
   `0x100 x new Uint8Array(0xEE)`, each with two u32 tag words at data offset
   0/4 (`da7a0000+k / cafe0000+k`, `51d8 0000+k / 520b0000+k`). The DataView is
   a byteOffset-0 view, so by construction `cell.m_vector == AB_impl.m_data`
   (same stored bits, see step 4) and `cell.m_length == AB_impl.m_sizeInBytes
   == 0xDE`. A short garbage-churn round forces survivor promotion so the
   victims stop moving before the hunt.
3. **Cell hunt** - phased `rd()` scan around `B` (stride 16 = MarkedBlock
   atomSize, MarkedBlock.h:72) for a qword `0xDE` at +0x18 (`m_length`,
   size_t u64). Each hit is verified: butterfly==0 (JSArrayBufferView.cpp:61;
   DataViewMode asserts `!butterfly()` at :151), `m_mode==3` (DataViewMode,
   JSArrayBufferView.h:57-87), `m_buffer` plausible (JSDataView.h:77), and the
   ArrayBuffer-impl consistency check above. Under a raw cage the stored
   `m_vector` is dereferenced once via `rd()` and must contain the victim's
   tags - that seals the identification (victim index `k` from the tag) and
   simultaneously verifies the cage degeneracy.
4. **Cage verdict (the F5 probe)** - `Gigacage` is compiled out on
   PLATFORM(WKC) (WTF/wtf/Gigacage.h:31-32 `#define GIGACAGE_ENABLED 0`,
   masks 0 at :38-39, `caged()` identity at :80-82), and `tagArrayPtr` is the
   identity unless the build is CPU(ARM64E) (WTF/wtf/PtrTag.h:508-512 identity
   vs :447-456 `ptrauth_sign_unauthenticated(ptr, ..., length)`). If the stored
   `m_vector` is not a plausible raw pointer, the harness logs
   **`[P4-cage]`** and aborts *before* any corruption - that marker is the
   campaign's F5 "would differ under signed data pointers" verdict, obtained
   for free.
5. **One free-then-reclaim write at the cell** - payload = faithful 0xB8 copy
   of `[C, C+0xB8)` (keeps the neighboring cells sweepable) with two patches:
   `m_vector(+0x10) = T`, `m_length(+0x18) = 0x1000` (u64). `T` = `B+0x90`
   (inside the fake-face chunk's inert Timer tail, a real address from the
   walk). The free is the proven P3 gadget: aim the fake face's
   `m_featureSettings` buffer at `C` (+0x28/+0x30/+0x34), call the
   `featureSettings` setter -> `~VectorBuffer -> fastFree(C)`
   (Vector.h:427-430 -> wkcHeapFreePeer), then spray 0x80 `ArrayBuffer(0xB8)`
   backings whose contents are the payload. The 0xB8 reclaim class and the
   mid-pool placement are exactly what `chain-final.html` already proved with
   its tagged reclaim at `B+0x1000`.
6. **Full R/W proof from plain JS** - `T[0..4]` was pre-planted with magic via
   `d` (the fake-face DataView):
   - `[P4-r]`: `dva.getUint32(0) === magic` - JS-visible read through the raw
     m_vector.
   - `[P4-w]`: `dva.setUint32(0x20, magic2)` then `rd()` confirms the bytes at
     `T+0x20` - write through the fake view, verified by the independent
     fake-Vector read primitive.
   - `[P4-len]`: `dva.getUint32(0x800)` (past the real 0xDE window, inside the
     fake 0x1000 one) matches `rd()` at `T+0x800` - the bounds compare is
     gone.
   - Bonus leg `[P4-ta]`/`[P4-taw]`: the same corruption on a Uint8Array
     victim exercises the LLInt typed-array fast path
     (LowLevelInterpreter.asm:1346-1380) directly.

## Field map (webkit_3.12.11 - the tree the campaign pins; every offset cited or TODO-VERIFY)

`JSArrayBufferView : JSNonFinalObject` (JSArrayBufferView.h:101), consumed by
both the LLInt fast path and the DataView prototype path:

| offset | field | source | notes |
|---|---|---|---|
| +0x00 | JSCell (structure ID + type) | JSObject.h | copied verbatim from the victim - never forged |
| +0x08 | `m_butterfly` | JSObject.h | 0 for views: ConstructionContext sets nullptr (JSArrayBufferView.cpp:49, :61), DataViewMode asserts it (:151) |
| +0x10 | `m_vector` | JSArrayBufferView.h:223 (typedef `VectorPtr = CagedBarrierPtr<...>` at :112) | the data pointer; the campaign's ":112" pin. Read back raw by `vector()` (:192) / `vectorWithoutPACValidation()` (:193); static `offsetOfVector()` at :203 |
| +0x18 | `m_length` | JSArrayBufferView.h:224 (size_t, u64); `offsetOfLength()` :204 | THE bounds check: `i < m_length` (JSGenericTypedArrayView.h:128, :139, :144, :173) and LLInt `biaeq index, JSArrayBufferView::m_length[base], slowPath` (LowLevelInterpreter.asm:1358-1369); DataView: `byteOffset > byteLength - elementSize -> "Out of bounds access"` (JSDataViewPrototype.cpp:153-154, :208-209). The campaign's ":166-168" = the same field trio in the ConstructionContext (:166-168) |
| +0x20 | `m_mode` (u32) | JSArrayBufferView.h:225 (`offsetOfMode()` :205) | 0=FastTypedArray, 3=DataViewMode (enum :57-87); `hasArrayBuffer()` = mode>=2; `isDetached() = hasArrayBuffer() && !hasVector()` (:188) - stays non-detached since m_vector != 0 |
| +0x24 | (pad) | layout arithmetic | sizeof(JSArrayBufferView)=0x28 |
| +0x28 | `JSDataView::m_buffer` (ArrayBuffer*) | JSDataView.h:77 | plain C++ RefPtr target - untouched by the payload |

The DataView access path that makes this work with a single cell patch
(JSDataViewPrototype.cpp:129-173, `getData`): detach check (:149) -> bounds
against `dataView->length()` = m_length (:152-154) -> `dataPtr =
static_cast<uint8_t*>(dataView->vector()) + byteOffset` (:162) - **no
ArrayBuffer dereference, no byteOffset arithmetic, no C++ DataView::create
range check on this path**. `vector()` = `m_vector.getMayBeNull(length())`
(JSArrayBufferView.h:192) -> CagedBarrierPtr.h:62-63 -> CagedPtr.h:69-77 ->
with GIGACAGE off and non-ARM64E this is the raw stored pointer. The Uint8Array
path is even shorter: LLInt loads `m_length`, compares, loads `m_vector`, and
`cagedPrimitive` is a no-op without ARM64E/GIGACAGE
(LowLevelInterpreter64.asm:503-520).

### The "mask" in the campaign notes - resolved

There is **no bounds-mask field** in JSArrayBufferView in the pinned tree
(grep across JSArrayBufferView*, JSGenericTypedArrayView*, JSDataView* for
`indexingMask|maskingMask|boundsCheck`: zero hits). The two "mask" meanings in
the notes are: (a) `primitiveGigacageMask = 0` (Gigacage.h:38) - the caging
mask whose zero makes the stored m_vector a raw pointer (ENGINE-HEAP-MODEL.md
:121, marked SPECULATIVE at instruction level - this harness tests it on
device and reports `[P4-cage]`), and (b) bounds removal, which in this tree is
plainly `m_length := large` - there is no separate mask to set.

## Size-class analysis (what the brief asked to document)

- The fake view is **not** a fresh allocation: it is an in-place corruption of
  a live `JSDataView` cell. `sizeof(JSDataView)` = sizeof(JSArrayBufferView)
  (0x28) + 8 (m_buffer) = 0x30; MarkedBlock atomSize = 16 (MarkedBlock.h:72),
  blockSize = 16KB (MarkedBlock.h:75) -> the cell lives in a 0x30 atom slot of
  a 16KB MarkedBlock, which is itself a `wkcHeapMallocAlignedPeer` chunk from
  the same pool (Heap.cpp:358 `fastMallocAllocator` ->
  FastMallocAlignedMemoryAllocator -> fastAlignedMalloc;
  FastMallocWKC.cpp:81-86; ENGINE-HEAP-MODEL.md section 1.4).
- Placement therefore does **not** depend on the view's own size class. The
  placement primitive is the P3 arbitrary free (`fastFree(controlled_ptr)`,
  Vector.h:427-430) + reclaim, and the reclaim spray reuses the **proven 0xB8
  class** (`ArrayBuffer(0xB8)` backings - chain-final's tagged reclaim landed
  at `B+0x1000`, a mid-pool non-chunk-start address, so the observed pool
  behavior is address-exact, not class-strict).
- Consequence + fallback: if the closed allocator turns out class-strict for
  the cell slot, the reclaim misses and the harness says so
  (`[P4-noreclaim]`); the next knob is the byteLength ladder from the runbook
  (STAGE2-DOSSIER.md F3: {176,184,192,200} and friends) to find the class the
  allocator serves for that slot. Chosen deliberately: reuse the proven class
  + self-test instead of pre-guessing a closed-source size-class table.

## Report markers (what each means)

| marker | meaning |
|---|---|
| `[1] UAF` | the `then` getter fired during `document.fonts.load` (trigger live) |
| `[leak] W/F/B` | the self-address chain worked; B = the fake-face chunk address |
| `[B] +0x..` | the fake face's field dump (sanity) |
| `[P4-spray]` | victim spray counts + tag words |
| `[P4-scan] phase N @addr+len (up/down)` + `miss` | hunt telemetry; phases double as a bounded pool-map probe (a crash in phase N pins the pool edge; phases 0..N-1 are already in the log) |
| `[P4-cell] C=.. A=.. victim=k cage=raw` | a verified victim DataView cell; cage verdict |
| `[P4-cage]` | stored m_vector is NOT a raw pointer - the closed build tags array pointers (CPU(ARM64E) codegen); corruption aborted pre-emptively. This is the F5 verdict: the raw-m_vector route is PAC-dead on this build; see the B1 follow-up below |
| `[P4-noreclaim]` | the free+reclaim write did NOT land at C (cell bytes unchanged) - view not reclaimed |
| `[P4-shape]` | the region at C changed but the fake fields are not in place (reclaim landed, fields wrong) |
| `[P4-r]` | read through the fake view returned the pre-planted magic |
| `[P4-w]` | write through the fake view verified by `rd()` |
| `[P4-bounds]` | index 0x800 still throws "Out of bounds access" - bounds still enforced, the m_length patch did not take (layout mismatch - see VERIFICATION-NOTE.md) |
| `[P4-len]` | far-index read matches `rd()` at the same address - bounds removed |
| `[P4-ta]` / `[P4-taw]` / `[P4-tashape]` / `[P4-tanoreclaim]` | the same story for the LLInt typed-array fast path |
| `done` | end of run (always reached on every non-crash path) |

Every stage is in its own try/catch and every `lg()` immediately POSTs the
whole line list to `/report`, so the runbook's rig-side journal captures the
verdict even when a later phase crashes the applet.

## Verification steps for a gate-open console (runbook)

1. Serve `chain-write.html` at the portal root (same rig as chain-final;
   DNS -> rig, captive portal loads).
2. Load the page on the console (or `POST /rig/phase` per the fire-build
   runbook), then read the `/report` JSON lines.
3. Green run reads, in order: `[1] UAF`, `[leak] ...`, `[B] ...`,
   `[P4-spray] ...`, `[P4-scan] phase 0 ...` (some phase reports), `[P4-cell]
   ... cage=raw`, `[P4-r]`, `[P4-w]`, `[P4-len]`, optionally `[P4-ta]`,
   `[P4-taw]`, `done`. That sequence = P4 proven end to end.
4. Triage table: `[P4-scan] NO DataView cell` -> widen `PH` windows (source
   constant) or re-run (GC placement varies); `[P4-cage]` -> array-ptr
   tagging active, route closed (record the build as ARM64E-tagged);
   `[P4-noreclaim]` -> run the byteLength ladder for the cell slot;
   `[P4-shape]`/`[P4-bounds]` -> field map mismatch, see
   VERIFICATION-NOTE.md item 1 (0.12.2-vs-3.12.11 layout).
5. Crash during a scan phase: the phase logs already POSTed identify the
   window that crossed the pool edge; shrink `PH` and re-run. Crashes before
   `[1] UAF` belong to P1-P3 triage (chain-final's runbook).

## Mitigations (why this stays data-only)

- No PC is touched anywhere: no vtable, no fake JSCell dispatch, no function
  pointer is ever forged. The only "code" the fake view influences is the
  engine's own load/store paths.
- JIT: none exists on this build (ENABLE_JIT/DFG/FTL = 0,
  FeatureDefinesWKC.h:85/92/108; real-asm LLInt, C_LOOP=0). No JIT-spray, no
  RWX.
- PAC: the route never encounters a signed pointer *if* the cage is raw
  (`[P4-cell] ... cage=raw` proves it on device); if tagging is active the
  harness stops at `[P4-cage]` before doing anything dangerous.
- Follow-up if `[P4-cage]` fires (B1 route, not implemented here): the
  signature modifier of `tagArrayPtr` is `m_length`, so a raw-m_vector route
  would need engine-signed bits - obtainable by making the engine allocate at
  the target address (the same free+reclaim placement), finding the fresh
  backing's ArrayBuffer impl (scan for the known tag via its m_data), and
  transplanting its signed `m_data`/`m_vector` bits into the victim pair with
  `m_length`/`m_sizeInBytes` kept equal to the modifier. Documented as the
  contingency; the harness deliberately does not attempt it.

## Honest caveats

- GC can move the victim cells (copying eden collection). The churn round
  minimizes it, the verification chain re-reads the cell immediately before
  corruption, and a mid-spray move fails *benign* (`[P4-noreclaim]` /
  `[P4-tashape]`) because the victim object itself stays valid.
- The 0xB8 payload overlays the victim cell plus neighbor atoms; the payload
  is a byte-faithful copy of the original region so the block stays
  sweepable. The pool free-list behavior under a mid-MarkedBlock free is
  closed-source (wkcheappeer.h) - empirically proven at a mid-pool address by
  chain-final, self-tested here (`[P4-noreclaim]`).
- `rd()`'s cost is ~1 C++ getter per 4 bytes; the hunt is capped at ~98k
  probes (~1-3s) and reports per phase.
- Down-scanning windows can hit the pool edge (unmapped) - that crashes the
  applet *after* the earlier phases are POSTed; by design (crash = telemetry,
  per the fire-build oracle model). The window list starts with the
  proven-live neighborhood for exactly this reason.

## Files

- `chain-write.html` - the P4 stage (self-contained; does not modify
  `chain-final.html`).
- `PR_BODY.md` - this document.
- `VERIFICATION-NOTE.md` - the TODO-VERIFY register (every offset/assumption
  not pinned from source).
