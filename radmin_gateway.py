"""Local Wi-Fi gateway to one RTX stand on a Radmin VPN peer."""
import argparse
import ipaddress
import json
import os
import shutil
import ssl
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
APP = ROOT / "Насос — 3D и мобильный осмотр"
STATE = ROOT / "radmin" / "private"
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
POST_PATHS = {"/api/qr", "/api/ar-frame", "/api/analyze"}
GET_PATHS = {"/mobile.html", "/ar.html", "/viewer.html", "/examples.html",
             "/mobile.js", "/mobile.css", "/camera-view.css", "/camera-view.js",
             "/alerts.js", "/trends.js", "/api/health", "/api/equipment",
             "/api/telemetry", "/api/passport", "/api/history", "/api/trends"}

class Gateway(BaseHTTPRequestHandler):
    def reply(self, status, mime, body):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def relay(self, body=None):
        path = urlsplit(self.path).path
        if path == "/":
            self.path = path = "/mobile.html"
        if path == "/kiber102-ca.cer" and body is None:
            return self.reply(200, "application/pkix-cert", self.server.ca.read_bytes())
        if body is None and path not in GET_PATHS and not any(
                path.startswith(prefix) for prefix in ("/assets/", "/results/", "/api/document/", "/api/jobs/")):
            return self.send_error(404)
        headers = {k:self.headers[k] for k in ("Accept", "Content-Type", "X-Captured-At") if k in self.headers}
        req = urllib.request.Request(self.server.peer + self.path, data=body, headers=headers)
        try:
            with HTTP.open(req, timeout=90) as res:
                self.reply(res.status, res.headers.get("Content-Type","application/octet-stream"), res.read())
        except urllib.error.HTTPError as exc:
            self.reply(exc.code, exc.headers.get("Content-Type","application/json"), exc.read())
        except (urllib.error.URLError,TimeoutError):
            self.reply(503,"application/json",json.dumps({"error":"RTX недоступен через Radmin VPN"}).encode())

    def do_GET(self):
        self.relay()

    def do_POST(self):
        if urlsplit(self.path).path not in POST_PATHS:
            return self.send_error(404)
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if not 0 < size <= 12_000_000:
            return self.send_error(413)
        self.relay(self.rfile.read(size))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("rtx", type=ipaddress.IPv4Address)
    parser.add_argument("wifi", type=ipaddress.IPv4Address)
    args=parser.parse_args()
    peer=f"http://{args.rtx}:8769"
    with HTTP.open(peer+"/api/health",timeout=8) as r:
        health=json.load(r)
    if not health.get("ok"):
        sys.exit("RTX health check failed")
    print("RTX:", args.rtx, health.get("models"), flush=True)
    STATE.mkdir(parents=True, exist_ok=True)
    # Reuse the stand's certificate and connection-page generator in isolated storage.
    (STATE/"public").mkdir(exist_ok=True)
    setup=STATE/"setup.py"
    shutil.copyfile(APP/"setup.py", setup)
    env=dict(os.environ, PUMP_LAN_IP=str(args.wifi))
    subprocess.run([sys.executable,str(setup)],env=env,check=True)
    private=STATE/"private"
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(private/"server.pem",private/"server-key.pem")
    from contextlib import ExitStack
    with ExitStack() as stack:
        plain=stack.enter_context(ThreadingHTTPServer((str(args.wifi),8769),Gateway))
        secure=stack.enter_context(ThreadingHTTPServer((str(args.wifi),8443),Gateway))
        if not args.wifi.is_loopback:
            loop=stack.enter_context(ThreadingHTTPServer(("127.0.0.1",8769),Gateway))
            loop.peer,loop.ca=peer,STATE/"public/kiber102-ca.cer"
            threading.Thread(target=loop.serve_forever,daemon=True).start()
            stack.callback(loop.shutdown)
        for server in (plain,secure):
            server.peer,server.ca=peer,STATE/"public/kiber102-ca.cer"
        secure.socket=ctx.wrap_socket(secure.socket,server_side=True)
        threading.Thread(target=plain.serve_forever,daemon=True).start()
        stack.callback(plain.shutdown)
        print("Phone:",f"https://{args.wifi}:8443/mobile.html",flush=True)
        print("QR:",STATE/"Подключить телефон.html",flush=True)
        secure.serve_forever()

if __name__=="__main__":
    main()
