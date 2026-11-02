#!/usr/bin/env python3
"""Minimal WebSocket bridge: page connects, server sends commands, page replies."""
import asyncio, base64, hashlib, json, sys

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
QUEUE = asyncio.Queue()

def frame(op, payload):
    n = len(payload)
    h = bytes([0x80 | op])
    if n < 126: h += bytes([n])
    elif n < 65536: h += bytes([126]) + n.to_bytes(2, "big")
    else: h += bytes([127]) + n.to_bytes(8, "big")
    return h + payload

async def handle(reader, writer):
    req = await reader.readuntil(b"\r\n\r\n")
    key = ""
    for line in req.decode("latin1").split("\r\n"):
        if line.lower().startswith("sec-websocket-key:"):
            key = line.split(":", 1)[1].strip()
    acc = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                  "Connection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n" % acc).encode())
    await writer.drain()
    print("[ws] client connected", flush=True)

    pending = {}
    async def send_loop():
        while True:
            cmd = await QUEUE.get()
            cid = str(__import__("time").time_ns())
            cmd = dict(cmd); cmd["_id"] = cid
            pending[cid] = {"cmd": cmd, "sent": __import__("time").time(), "tries": 0}
            writer.write(frame(0x1, json.dumps(cmd).encode()))
            await writer.drain()
    async def retry_loop():
        import time
        while True:
            now = time.time()
            for cid, e in list(pending.items()):
                if now - e["sent"] > 2.0:
                    if e["tries"] >= 3:
                        print("[ws] drop (no ack) " + cid, flush=True); pending.pop(cid, None); continue
                    e["tries"] += 1; e["sent"] = now
                    print("[ws] retry %s try=%d" % (cid, e["tries"]), flush=True)
                    writer.write(frame(0x1, json.dumps(e["cmd"]).encode()))
                    await writer.drain()
            await asyncio.sleep(0.5)
    async def recv_loop():
        while True:
            hdr = await reader.readexactly(2)
            op = hdr[0] & 0x0F; n = hdr[1] & 0x7F
            if n == 126: n = int.from_bytes(await reader.readexactly(2), "big")
            elif n == 127: n = int.from_bytes(await reader.readexactly(8), "big")
            mask = await reader.readexactly(4) if hdr[1] & 0x80 else b"\0\0\0\0"
            data = bytearray(await reader.readexactly(n))
            for i in range(n): data[i] ^= mask[i % 4]
            if op == 0x8: return
            txt = bytes(data).decode("utf-8", "replace")
            try:
                j = json.loads(txt)
                if j.get("_ack") in pending: pending.pop(j["_ack"], None)
            except Exception: pass
            print("[ws-result] " + txt[:1200], flush=True)
    t = asyncio.create_task(send_loop())
    t2 = asyncio.create_task(retry_loop())
    try: await recv_loop()
    except Exception: pass
    t.cancel(); t2.cancel()

async def main():
    srv = await asyncio.start_server(handle, "192.168.50.1", 8766)
    print("[ws] listening ws://192.168.50.1:8766", flush=True)
    # read commands from stdin lines (JSON) and fan out to the page
    loop = asyncio.get_event_loop()
    async def cmdfile():
        import os
        path="/tmp/ws-cmd-file"
        pos=0
        while True:
            try:
                if os.path.exists(path):
                    with open(path,"r") as f:
                        f.seek(pos)
                        for line in f:
                            line=line.strip()
                            if line:
                                try: QUEUE.put_nowait(json.loads(line))
                                except Exception as e: print("[ws] bad cmd", e, flush=True)
                        pos=f.tell()
            except Exception: pass
            await asyncio.sleep(0.4)
    asyncio.create_task(cmdfile())
    async with srv: await srv.serve_forever()

asyncio.run(main())
