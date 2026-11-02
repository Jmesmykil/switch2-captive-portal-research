#!/usr/bin/env python3
"""Serve the captive-portal payload on the Ethernet interface, logging /report.

The bench's entry helper (switch2-local-browser-entry.py) does DNS:53 + HTTP:80
and redirects to --probe-port. Run this on that probe port so the redirect lands
on index.html, and the page's POST /report is captured to reports/.

  sudo python3 serve_payload.py --bind 192.168.50.1 --port 8765
  sudo python3 switch2-local-browser-entry.py --bind 192.168.50.1 \\
       --dns-port 53 --http-port 80 --probe-port 8765
"""
import argparse
import http.server
import os
import socketserver
import collections
import json as _json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EVENTS = collections.deque(maxlen=5000)
CMDS = collections.deque()
PROBE_STATE = {'next': 0, 'dead': set()}
RESULTS = collections.deque(maxlen=200)
_EID = [0]

def add_event(kind, text):
    _EID[0] += 1
    EVENTS.append((_EID[0], kind, time.strftime("%H:%M:%S ") + text))



class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/poll":
            import json as _j2
            out=[]
            while CMDS:
                out.append(CMDS.popleft())
            b=_j2.dumps(out).encode()
            self.send_response(200); self.send_header("content-type","application/json")
            self.send_header("Cache-Control","no-store"); self.end_headers()
            self.wfile.write(b); return
        if self.path.split("?")[0] == "/probe":
            import json as _j3
            idx=PROBE_STATE["next"]
            while idx in PROBE_STATE["dead"]: idx+=1
            PROBE_STATE["next"]=idx+1
            b=_j3.dumps({"offset":idx,"dead":sorted(PROBE_STATE["dead"])}).encode()
            self.send_response(200); self.send_header("content-type","application/json")
            self.send_header("Cache-Control","no-store"); self.end_headers()
            self.wfile.write(b); return
        if self.path.split("?")[0] == "/beacon":
            try:
                n=int(self.headers.get("Content-Length") or 0)
                body=self.rfile.read(n) if n else b""
                print("[beacon] " + body.decode("utf-8","replace")[:800], flush=True)
                add_event("beacon", body.decode("utf-8","replace"))
            except Exception as e:
                print("[beacon] err", e, flush=True)
            self.send_response(204); self.end_headers(); return
        if self.path.split("?")[0] == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            last = 0
            try:
                while True:
                    new = [e for e in EVENTS if e[0] > last]
                    for eid, kind, text in new:
                        last = eid
                        payload = _json.dumps({"id": eid, "kind": kind, "text": text})
                        self.wfile.write(("data: " + payload + "\n\n").encode())
                    self.wfile.flush()
                    time.sleep(0.25)
            except Exception:
                return
        # Media-decode reachability probe (additive; does not touch /launcher.html)
        if self.path.split("?")[0] == "/mediadecode":
            self.path = "/mediadecode.html"
            super().do_GET()
            return
        if self.path.split("?")[0] == "/probe-h264.mp4":
            self.path = "/probe-h264.mp4"
            super().do_GET()
            return
        if self.path.split("?")[0] == "/probe-vp8.webm":
            self.path = "/probe-vp8.webm"
            super().do_GET()
            return
        if self.path.split("?")[0] == "/probe-vp9.webm":
            self.path = "/probe-vp9.webm"
            super().do_GET()
            return
        # cache-bust: the console may have cached the bench page at "/"
        if self.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/launcher.html?t=%d" % int(time.time()))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if self.path.split("?")[0] in ("/port/setstatus.html", "/setstatus.html"):
            self.send_response(302)
            self.send_header("Location", "/launcher.html?t=%d" % int(time.time()))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if self.path.split("?")[0] == "/probe.html":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/cmd":
            import json as _j
            n=int(self.headers.get("content-length",0) or 0)
            body=self.rfile.read(n) if n else b"{}"
            try: c=_j.loads(body)
            except Exception: c={}
            CMDS.append(c)
            try:
                with open("/tmp/ws-cmd-file","a") as _f: _f.write(__import__("json").dumps(c)+"\n")
            except Exception: pass
            print("[cmd] "+str(c)[:300], flush=True)
            self.send_response(200); self.end_headers(); self.wfile.write(b"queued"); return
        if path == "/poll":
            import json as _j
            out=[]
            while CMDS:
                out.append(CMDS.popleft())
            b=_j.dumps(out).encode()
            self.send_response(200); self.send_header("content-type","application/json"); self.end_headers(); self.wfile.write(b); return
        if path == "/probe":
            import json as _j
            idx=PROBE_STATE["next"]
            while idx in PROBE_STATE["dead"]: idx+=1
            PROBE_STATE["next"]=idx+1
            b=_j.dumps({"offset":idx,"dead":sorted(PROBE_STATE["dead"])}).encode()
            self.send_response(200); self.send_header("content-type","application/json"); self.end_headers(); self.wfile.write(b); return
        if path == "/probe-done":
            import json as _j
            n=int(self.headers.get("content-length",0) or 0)
            try: PROBE_STATE["dead"].add(int(_j.loads(self.rfile.read(n) or b"{}")["offset"]))
            except Exception: pass
            b=_j.dumps({"ok":True,"next":PROBE_STATE["next"]}).encode()
            self.send_response(200); self.send_header("content-type","application/json"); self.end_headers(); self.wfile.write(b); return
        if path == "/result":
            import json as _j
            n=int(self.headers.get("content-length",0) or 0)
            body=self.rfile.read(n) if n else b"{}"
            print("[result] "+body.decode("utf-8","replace")[:800], flush=True)
            RESULTS.append(body.decode("utf-8","replace"))
            self.send_response(204); self.end_headers(); return
        if path == "/relay":
            import json as _j, glob as _g
            runs=_g.glob("/Users/astral/Downloads/ns2jb/host-wired-community-20261025/runs/*/connection.json")
            runs.sort(key=lambda x: __import__("os").path.getmtime(x), reverse=True)
            if not runs:
                self.send_response(503); self.end_headers(); self.wfile.write(b"no run"); return
            c=_j.load(open(runs[0]))
            n=int(self.headers.get("content-length",0) or 0)
            body=self.rfile.read(n) if n else b"{}"
            try:
                import urllib.request as _u
                req=_u.Request("http://127.0.0.1:%d/" % c["port"], data=body,
                               headers={"authorization":"Bearer "+c["token"],"content-type":"application/json"})
                r=_u.urlopen(req, timeout=30).read()
                self.send_response(200); self.send_header("content-type","application/json"); self.end_headers(); self.wfile.write(r)
            except Exception as e:
                self.send_response(502); self.end_headers(); self.wfile.write(str(e).encode())
            return
        if path == "/stage":
            import json as _j3, time as _t3
            n=int(self.headers.get("content-length",0) or 0)
            body=self.rfile.read(n) if n else b"{}"
            try:
                d=_j3.loads(body)
                fn="/tmp/staged-store-%d.json" % int(_t3.time()); open(fn,"w").write(_j3.dumps(d,indent=1))
                print("[stage] "+fn+" keys="+str(list((d.get("store") or {}).keys())), flush=True)
                add_event("stage", body.decode("utf-8","replace")[:600])
                # forward to the SmileBASIC bridge relay (best effort)
                try:
                    import urllib.request as _u4
                    _u4.urlopen(_u4.Request("http://127.0.0.1:8765/relay", data=_j3.dumps({"command":"status"}).encode(),
                                            headers={"content-type":"application/json"}), timeout=3).read()
                except Exception: pass
            except Exception as e:
                print("[stage] err", e, flush=True)
            self.send_response(204); self.end_headers(); return
        if path == "/beacon":
            n = int(self.headers.get("content-length", 0) or 0)
            body = self.rfile.read(n) if n else b""
            print("[beacon] " + body.decode("utf-8", "replace")[:1200], flush=True)
            add_event("beacon", body.decode("utf-8", "replace"))
            self.send_response(204); self.end_headers(); return
        if path != "/report":
            self.send_response(404)
            self.end_headers()
            return
        n = int(self.headers.get("content-length", 0) or 0)
        body = self.rfile.read(n)
        os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
        fn = os.path.join(HERE, "reports", f"report-{int(time.time())}.json")
        with open(fn, "wb") as f:
            f.write(body)
        print(f"[report] {fn}: {body!r}", flush=True)
        add_event("report", body.decode("utf-8", "replace"))
        self.send_response(204)
        self.end_headers()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        line = "[http H:" + self.headers.get("Host","-") + "] " + (fmt % args)
        print(line, flush=True)
        add_event("http", line)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="192.168.50.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    os.chdir(HERE)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer.daemon_threads = True
    with socketserver.ThreadingTCPServer((a.bind, a.port), Handler) as s:
        print(f"serving {HERE} on http://{a.bind}:{a.port}/", flush=True)
        s.serve_forever()
