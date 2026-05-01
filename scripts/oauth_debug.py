#!/usr/bin/env python3
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "PLACEHOLDER_CLIENT_ID_OLD"

from http.server import BaseHTTPRequestHandler, HTTPServer

from oauth_first_setup import generate_code_challenge, generate_code_verifier


class H(BaseHTTPRequestHandler):
    c = {}

    def log_message(self, *a):
        pass

    def do_GET(self):
        p = self.path.split("?", 1)
        if len(p) > 1:
            for k, v in [x.split("=", 1) for x in p[1].split("&")]:
                if k == "code":
                    self.c["code"] = v
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"OK")
        self.server.shutdown_flag = True


cv = generate_code_verifier(64)
cc = generate_code_challenge(cv)
client_id = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
url = (
    f"https://accounts.google.com/o/oauth2/v2/auth"
    f"?client_id={client_id}"
    f"&redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fcallback"
    f"&response_type=code"
    f"&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.readonly"
    f"&code_challenge={cc}"
    f"&code_challenge_method=S256"
    f"&access_type=offline&prompt=consent"
)
print("=" * 60)
print("OPEN THIS URL IN YOUR BROWSER:")
print(url)
print("=" * 60)
print("WAITING FOR CALLBACK (300s timeout)...")

s = HTTPServer(("localhost", 8080), H)
t = threading.Thread(target=s.serve_forever, daemon=True)
t.start()
start = time.time()
while not getattr(s, "shutdown_flag", False) and time.time() - start < 300:
    time.sleep(0.5)
s.shutdown()

if H.c.get("code"):
    print("GOT CODE:", H.c["code"][:30])
    import httpx

    r = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": "PLACEHOLDER_CLIENT_SECRET_OLD",
            "code": H.c["code"],
            "code_verifier": cv,
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:8080/callback",
        },
        timeout=30,
    )
    print("TOKEN STATUS:", r.status_code)
    if r.status_code == 200:
        tokens = r.json()
        rt = tokens.get("refresh_token")
        if rt:
            from aria.credentials.keyring_store import KeyringStore

            KeyringStore().put_oauth("google_workspace", "primary", rt)
            print("TOKEN STORED! Preview:", rt[:30])
        else:
            print("NO refresh_token IN RESPONSE:", tokens)
    else:
        print("ERROR RESPONSE:", r.text[:300])
else:
    print("NO CODE RECEIVED")
