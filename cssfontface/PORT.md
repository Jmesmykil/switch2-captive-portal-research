# CSSFontFace UAF — port to the Switch 2 captive portal

**Source:** [ntfargo/CSSFontFace-Exploit](https://github.com/ntfargo/CSSFontFace-Exploit)
(PS4/PS5 WebKit; bug research ufm42 / ntfargo, writeup linearfox.com). Upstream
tree saved in `cssfontface/upstream-src/` for reference.

## 1. What the bug is

`FontFaceSet::load` holds a **raw reference** to a `CSSFontFace` while the
corresponding `@font-face` rule is deleted. The freed object is reclaimed with
`ArrayBuffer`s of `CSSFontFace` size, giving a **type-confused object**: the
`FontFace` returned to script now aliases an `ArrayBuffer`.

The primitive is `CSSFontFace::m_featureSettings` — a small vector
(`m_buffer`, `m_size`, `m_capacity`). Pointing `m_buffer` at an arbitrary address
and setting size/capacity to 1 gives an **arbitrary read**; the same structure
gives a write. `init_arw` then builds `addrof`/`fakeobj` and an ARW view.

Upstream scope: PS4 6.00–13.52 / PS5 1.00–13.40; exploitable 6.00–11.02 /
1.00–8.60. Newer WebKit (`m_propertiesOrCSSConnection`) breaks it.

## 2. What ports directly

| piece | file | why |
|---|---|---|
| UAF trigger | `ps4/userland.js:init_rw` | pure WebKit JS (FontFace, @font-face, `document.fonts.load`) |
| `m_featureSettings` read/write | same | pure JS over the reclaimed ArrayBuffer |
| `init_arw` (addrof/fakeobj) | same | pure JS, but needs the engine's object layout |

## 3. What does **not** port

- `version.init()` — parses the PlayStation UA; the Switch UA is
  `WifiWebAuthApplet … AppleWebKit/613.0`.
- `ps4/constants.js` — PS4 WebKit offsets, vtables, gadgets.
- `ps4/kernel.js` + `lapse.js` — PS4 kernel exploit (AIO / SCE syscalls), not
  portable to Horizon.
- `NativeFunction` syscall ids.

## 4. The Switch 2 engine — FOUND

The engine **is** in the decrypted export; it is an exefs side file, not `main`:

| item | value |
|---|---|
| path | `system-programs/040000000000085d/exefs/wkc3` |
| NSO name | `webkit_wkc` |
| build_id | `40ac5a64c4c56a1efbf46d60aaa3aac9d452c389` |
| segments | text 26,570,776 / ro 10,796,628 / data 2,097,329 |
| ro markers | `WebCore` 1404, `JavaScriptCore` 329, `JSC::` 2382, `CSSFontFace` 4 |
| debug string | `FontLoadTiming WebCore::CSSFontFace::fontLoadTiming() const` |
| source path | `F:/BrowserEngineRelease/Source/webkit/WebCore/css/CSSFontFace.cpp` |

Sibling files: `wkc0` = `oss_wkc` (WKC wrapper, 502 WebKit strings, no WebCore),
`wkc1/wkc2/wkc4` = small shims; `0400000000000837`/`0843` = `nnCompat` libraries;
`040000000000100f/exefs/subsdk4` also carries CSSFontFace strings.

Also confirmed by community analysis: NetFront 7 / WebKit 613, **JavaScript JIT
disabled** ([wontfix](https://wontfix.blogspot.com/2025/08/switch2-web.html)).

## 4a. What that means for the chain

| stage | JIT needed? | status on Switch 2 |
|---|---|---|
| CSSFontFace UAF (free/reclaim) | no | probe runnable |
| `m_featureSettings` read/write | no | needs the struct offsets |
| `init_arw` (addrof/fakeobj) | no (interpreter type confusion) | needs JSCell layout |
| upstream `rop.execute()` (`Math.expm1` pivot) | **yes** | **unusable** |
| post-ARW code exec | — | needs a non-JIT pivot (vtable/call-oriented) |

## 5. First milestone — does the UAF fire on Switch?

The reclaim needs `wk_CSSFontFace_sizeof` (ArrayBuffer size) and
`wk_CSSFontFace_m_status` (status byte offset). Those differ per WebKit build.
The upstream constants list the PS4 values (`0xb8, 0xe8, 0x120, 0x128`).

The probe (`switch.html`) tries a candidate list of sizes, runs the exact
`init_rw` free/reclaim, and checks for the two UAF signatures:

- a `FontFace` whose `unicodeRange` is the default `U+0-10FFFF`;
- an `ArrayBuffer` whose refcount field reads `2`.

If one size reclaims, **the CSSFontFace UAF is live on the Switch 2**, and that
is a heap type-confusion primitive — the write primitive the portal lacked.

## 6. After the UAF

1. derive `m_featureSettings` offsets by scanning the reclaimed object (the
   read primitive only needs `m_buffer`/`m_size`/`m_capacity`);
2. port `init_arw` with the Switch's `JSObject`/`JSCell` layout;
3. build the Switch escalation chain (not the PS4 kernel exploit).

## 7. Honest limits

- We cannot finish the ARW without the engine binary (or a leak that reveals the
  layout). The probe phase is runnable today; the full chain is not.
- The PS4 kernel exploit is irrelevant to Horizon; escalation needs its own path.
