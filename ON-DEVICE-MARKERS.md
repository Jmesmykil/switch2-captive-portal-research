# On-device markers — Switch 2 captive portal / media decode chase (2026-11-01)

Session trail of on-hardware observations and server-side changes. Revisions below are
the authoritative current state.

## Running processes (Mac lab)
- Payload portal: `serve_payload.py --bind 192.168.50.1 --port 8765`
  cwd = `/Users/astral/Downloads/ns2jb/local-input/research-lab/captive-portal-payload`
- Entry helper: `observed-entry.py --bind 192.168.50.1 --dns-port 53 --http-port 80 --probe-port 8765`
  cwd = `/Users/astral/Downloads/ns2jb/switch2-captive-portal-research`
  (reads `profile.json` on every request; no restart needed to change profile)

## profile.json — connectivity profiles
- `redirect`  → default. ctest hosts get 302 → portal. This is the "captive" posture.
  BACKUP: `profile.json.bak`
- `connectivity_ok` → ctest hosts get HTTP 200 `ok` (X-Organization: Nintendo).
  OTHER hosts still get the 302 portal redirect. This tells the console it's online.
- `inline`, `basic_auth` → other served modes in `observed-entry.py`.

## On-device observations (markers)

1. **2110-3400** while loading `<video>` / media.
   Console (peer 192.168.50.2) resolved ctest and did `HEAD ctest... → 302`.
   - Read: the applet's connectivity/HTTP-stage check failed under `redirect`
     (302 on a connectivity check == failed connection → 2110-3400 band).
   - Decoder itself: server log shows console GET `/mediadecode` 200 and
     `/probe-h264.mp4` 200, but the page JS never POSTed a media-decode report.
     Implies either JS aborted or `<video>` decode died before the report.

2. **supernag / forced online** after switching to `connectivity_ok`.
   - Read: console trusts the 200 `ok` and enters "online" state → demands real
     connection / account. LIKELY from 90DNS blocking upstream. NOT INTENDED:
     this fights the isolated-lab assumption. Treat as side effect to avoid.

3. **"this feature is not available"** (current, in `connectivity_ok`).
   - Read: console attempts a server-dependent feature over the fake-online state
     and the backend is absent/blocked behind 90DNS + helper. Consistent with the
     `switch2-mp4-web` finding: the captive applet has no real media/feature
     pipeline (media `canPlayType("")`/error on fw 23.0.x).

## Decode probe (added to live payload, additive)
- Page: `/mediadecode` (mediadecode.html) — feeds tiny well-formed H264/VP8/VP9
  clips to `<video>`, records canPlayType + canplay/error, POSTs `/report`.
- Fixtures served: `/probe-h264.mp4` `/probe-vp8.webm` `/probe-vp9.webm`.
- Added load-beacon (POST /report on page load) so even a decode-die yields a
  `stage:"page-loaded"` report.
- `serve_payload.py` edited: additive routes for `/mediadecode` and `/probe-*`;
  `/launcher.html` chain flow (OPENWEB_SIZE=0x19D0000) preserved.

## Key open question (the gate)
Does the WifiWebAuthApplet on fw 23.0.1 reach ANY real video decoder from an
attacker-controlled `<video>`? If NO → neither captive-portal NOR News can feed
NVDEC through a user `<video>`, and we must pivot to the container-parser
surface (`SystemWeb 1042 MP4 stsd OOB`, 0x773dfc; and News speech cmd-7),
NOT a NVDEC decode path.

## Revert / retry knobs
- Restore redirect posture: `cp profile.json.bak profile.json`
- Re-try online posture later: `printf '{"profile":"connectivity_ok"}' > profile.json`
- Watchers: job (report + traffic tail) is backgrounded; restart if needed.
## 4. 28071006 (current)
- Code 28071006 seen on console after revert to redirect posture.
- Need to identify: is it a system/nag dismissal code or a lookup error?

## 5. Online / newest FW (2026-11-01, IMPORTANT)
- User went ONLINE now, on the NEWEST FW ("until probably tomorrow").
- 2807 1006 read: online/account/feature service not available on this (newest) config.
- RISK: console no longer offline; newest FW may not match the proven chain/WEBKIT build.
- Lab posture (offline captive) is now inconsistent with an online console.
- Decision pending: continue chain research vs protect the jailbreak stage until the known-good FW/exploit is confirmed available.
