# VERIFICATION NOTE — chain-write.html (P4) — what is pinned vs TODO-VERIFY

Rule of the campaign (STAGE2-DOSSIER.md, "Zero-hallucination discipline"):
every offset either carries a file:line from the vendored OSS tree
(`webkit_3.12.11`, the tree the campaign pins and the binary offsets
corroborate) or is listed here as an honest gap. Nothing below was invented;
each TODO-VERIFY names the on-device marker that decides it.

## Pinned from source (cited, not verified at instruction level)

- JSArrayBufferView fields +0x10 m_vector / +0x18 m_length / +0x20 m_mode —
  JSArrayBufferView.h:223-225 (`offsetOfVector/Length/Mode` :203-205); typedef
  at :112; ConstructionContext trio :166-168.
- JSDataView::m_buffer at +0x28 — JSDataView.h:77 (first member after the
  JSArrayBufferView base); sizeof(JSDataView)=0x30 is layout arithmetic
  (0x28 + 8), not a binary pin.
- Butterfly = 0 for views — JSArrayBufferView.cpp:49/:61, DataViewMode assert
  :151.
- Bounds = `i < m_length` / `byteOffset > length - elementSize` —
  JSGenericTypedArrayView.h:128/:139/:173, JSDataViewPrototype.cpp:153-154/
  :208-209, LLInt LowLevelInterpreter.asm:1358-1369; DataView deref through
  `vector()` — JSDataViewPrototype.cpp:162, JSArrayBufferView.h:192.
- Gigacage off on PLATFORM(WKC) — Gigacage.h:31-32; masks 0 :38-39; `caged()`
  identity :80-82; `tagArrayPtr` identity unless CPU(ARM64E) — PtrTag.h:508-512
  vs :447-456.
- MarkedBlock atomSize 16 / blockSize 16KB — MarkedBlock.h:72/:75; MarkedBlocks
  from the same WKC pool — Heap.cpp:358, FastMallocWKC.cpp:81-86.
- Free gadget — Vector.h:427-430 (`~VectorBuffer -> deallocateBuffer ->
  fastFree`), wkcHeapFreePeer (FastMallocWKC.cpp:57).
- No bounds-mask field exists in the pinned tree (grep across
  JSArrayBufferView*, JSGenericTypedArrayView*, JSDataView*: zero hits for
  indexingMask/maskingMask) — the campaign "mask" = primitiveGigacageMask=0
  (caging) + m_length := large (bounds).

## TODO-VERIFY register (honest gaps, each with its deciding marker)

1. **m_length width at +0x18 (u64 vs u32) / m_mode at +0x20 vs +0x1C.**
   webkit_3.12.11: size_t m_length (u64), m_mode at +0x20. The older
   webkit_0.12.2 tree in the same vendor dir declares `uint32_t m_length` and
   `TypedArrayMode m_mode` at +0x1C (0.12.2 JSArrayBufferView.h:180-182). The
   campaign's binary pins (OFF_STATUS 0x7A etc.) corroborate the 3.12.11
   WebCore, but the closed wkc3's exact tree is not instruction-verified.
   Decider: `[P4-bounds]` / `[P4-shape]` (if the u64 0x1000 at +0x18 does not
   remove the bounds, retry with u32 patches at +0x18 and +0x1C). Not
   implemented in the payload to keep one hypothesis per run.
2. **LLInt LARGE_TYPED_ARRAYS on/off.** Changes whether the fast-path bounds
   compare loads m_length as u64 or u32 (LowLevelInterpreter.asm:1357-1371).
   Harmless here (u64 0x1000 has the same low 32 bits) but note for exactness.
   Decider: instruction-level only; no runtime marker.
3. **JSDataView cellSize 0x30 / atom rounding.** Source arithmetic only; the
   0x30 verify window and the 16-byte scan stride assume it. Decider: a
   `[P4-scan]` hit that fails `dvVerify` at a neighboring 16-byte boundary.
4. **ArrayBuffer impl (C++) field offsets** (m_data / m_sizeInBytes; base =
   GCIncomingRefCounted -> DeferrableRefCounted -> RefCounted, member order
   ArrayBuffer.h:113-118/:182). Not pinned absolutely. The final design does
   NOT patch the impl (the DataView prototype path never reads it), and
   `offMD` is derived by stored-bits equality, not by offset — so the harness
   is insensitive to this gap. Recorded for the B1 follow-up leg, which would
   need the real offsets. Decider: none needed for P4 as shipped.
5. **WKC pool free-list semantics under a mid-MarkedBlock free** (headered vs
   headerless, class-strict vs address-exact). Closed source
   (wkcheappeer.h:38-60). chain-final proved address-exact placement for a
   mid-pool address with the 0xB8 class; this harness re-proves it for a cell
   slot. Decider: `[P4-noreclaim]` (then run the byteLength ladder —
   STAGE2-DOSSIER.md F3 — against the cell slot).
6. **GC-block placement relative to the ArrayBuffer spray region.** Runtime
   property of the closed allocator; the hunt starts at the proven-live
   neighborhood and widens. Decider: `[P4-scan]` phase telemetry (which
   window held the cells) -> adjust `PH`.
7. **CPU(ARM64E) in the closed build (array-ptr tagging active?).** The one
   fork that can kill the raw-m_vector route. Decider: `[P4-cell] ... cage=raw`
   vs `[P4-cage]` — this is the campaign's F5 probe, answered by the first
   gate-open run. (The ENGINE-HEAP-MODEL.md instruction-level inference
   "identity untag = plain ldr" — its section 6 item 4 — is resolved by the
   same marker.)
8. **The closed build's DataView prototype path matches the vendored
   JSDataViewPrototype.cpp:162 (`vector()+index`)** — source-cited for the OSS
   tree; if the closed build instead goes through a byteOffset-based C++
   DataView::create, index 0 still lands at the same address (the arithmetic
   is self-consistent) but the far-window test behaves differently.
   Decider: `[P4-r]` green while `[P4-len]` reports a mismatch-vs-rd or
   undefined — record the datapath variant from that combination.
9. **Allocation order inside the featureSettings setter** (parse allocations
   strictly before the old-vector free, so the freed slot is the freelist head
   when the spray starts). Empirically proven by chain-final's tagged reclaim;
   instruction-level order inside Vector move-assign not verified. Decider:
   `[P4-noreclaim]` on both legs would implicate this.
10. **Teardown of a corrupted FastTypedArray's vector** (who frees the
    auxiliary allocation behind m_vector when the view dies — JSArrayBufferView
    finalize handles Oversize only, :182-191; the Fast-path free lives in the
    auxiliary-space sweeper, not pinned here). Post-exploit lifetime hazard
    only; the page ends before teardown matters. Decider: none (out of the
    exploit window).
11. **The byteLength ladder for a 0x30-class cell slot** (if the allocator is
    class-strict, which backing size is served for the freed cell slot: 0x30?
    0x28? a bucket boundary?). TODO-VERIFY on device via the ladder; the
    shipped spray deliberately stays on the proven 0xB8 class.

## Not gaps (verified unnecessary)

- The victim's JSCell/structure word is copied byte-for-byte from a live view
  of the same class, so no structure-ID forging and noTypeInfo knowledge is
  required.
- No JSDataViewPrototype/JSObject method tables are touched (the cell copy
  keeps the original ClassInfo pointer).
- No ArrayBuffer-impl patch is needed for the shipped route (see item 4).
