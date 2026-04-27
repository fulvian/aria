#!/usr/bin/env python3
"""
Self-contained OAuth PKCE flow for Google Workspace MCP.
Generates verifier, prints URL, starts callback server, exchanges code, saves token.
"""
import base64, hashlib, json, os, secrets, sys, threading, time, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOKEN_DIR = PROJECT_ROOT / ".aria" / "runtime" / "credentials" / "google_workspace_mcp"
TOKEN_PATH = TOKEN_DIR / "fulviold@gmail.com.json"

CLIENT_ID = os.environ.get(
    "GOOGLE_OAUTH_CLIENT_ID",
    "PLACEHOLDER_CLIENT_ID"
)
CLIENT_SECRET = os.environ.get(
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "PLACEHOLDER_CLIENT_SECRET"
)
REDIRECT_URI = "http://localhost:8080/callback"
REDIRECT_HOST = "localhost"
REDIRECT_PORT = 8080

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
]

# Generate PKCE
code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")

# Build auth URL
params = (
    f"client_id={quote(CLIENT_ID)}"
    f"&redirect_uri={quote(REDIRECT_URI)}"
    f"&response_type=code"
    f"&scope={quote(' '.join(SCOPES))}"
    f"&code_challenge={code_challenge}"
    f"&code_challenge_method=S256"
    f"&access_type=offline"
    f"&prompt=consent"
)
auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

print("=" * 60)
print("GOOGLE WORKSPACE MCP — OAuth Re-authentication")
print("=" * 60)
print(f"Client ID: {CLIENT_ID[:35]}...")
print(f"Redirect URI: {REDIRECT_URI}")
print(f"Scopes ({len(SCOPES)}):")
for s in SCOPES:
    print(f"  + {s}")
print()
print("OPEN THIS URL IN YOUR BROWSER:")
print(auth_url)
print()
try:
    webbrowser.open(auth_url)
    print("(Browser opened automatically)")
except Exception:
    pass
print("=" * 60)
sys.stdout.flush()

# Callback handler (use mutable container)
class CallbackState:
    code = None

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            CallbackState.code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>OK! You can close this tab.</h1>")
            self.server.shutdown_flag = True
        elif "error" in params:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<h1>Error: {params['error'][0]}</h1>".encode())
            self.server.shutdown_flag = True
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Waiting...</h1>")

server = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), Handler)
t = threading.Thread(target=server.serve_forever, daemon=True)
t.start()

print("Waiting for OAuth callback on http://localhost:8080/callback ...")
start = time.time()
while time.time() - start < 300:
    if getattr(server, "shutdown_flag", False):
        break
    time.sleep(0.5)
server.shutdown()

if not CallbackState.code:
    print("TIMEOUT: No authorization code received.")
    sys.exit(1)

print(f"Authorization code received. Exchanging...")
sys.stdout.flush()

# Exchange code for tokens (WITH PKCE code_verifier)
resp = httpx.post(
    "https://oauth2.googleapis.com/token",
    data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": CallbackState.code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    },
    timeout=30,
)

if resp.status_code != 200:
    print(f"TOKEN EXCHANGE FAILED (HTTP {resp.status_code}):")
    print(resp.text[:500])
    sys.exit(1)

tokens = resp.json()
print(f"Token exchange: HTTP {resp.status_code} ✅")

# Build token JSON for workspace-mcp
import datetime
scope_list = tokens.get("scope", "").split()
token_data = {
    "token": tokens.get("access_token", ""),
    "refresh_token": tokens.get("refresh_token", ""),
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scopes": scope_list,
    "expiry": (
        datetime.datetime.now(datetime.UTC) + 
        datetime.timedelta(seconds=tokens.get("expires_in", 3600))
    ).isoformat(),
}

TOKEN_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
TOKEN_PATH.chmod(0o600)

print()
print("=" * 60)
print("TOKEN SAVED ✅")
print(f"  Path: {TOKEN_PATH}")
print(f"  Access token: {token_data['token'][:20]}...")
print(f"  Refresh token: {token_data['refresh_token'][:20]}...")
print(f"  Expiry: {token_data['expiry']}")
print(f"  Scopes ({len(scope_list)}):")
for s in scope_list:
    print(f"    + {s}")
print("=" * 60)
