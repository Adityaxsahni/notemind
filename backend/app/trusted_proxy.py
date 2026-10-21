"""The visitor's address behind a proxy whose own address isn't fixed (Vercel).

uvicorn's --forwarded-allow-ips trusts X-Forwarded-For by the proxy's IP, which works for the
Docker setup (fixed container addresses) but not for Vercel, whose servers call the API from
many changing addresses. Without this, all Vercel visitors would share one rate-limit
bucket, so a handful of logins would lock everyone out.

Instead, the frontend's proxy (frontend/src/proxy.ts) sends a shared secret with each API
request. Only a request carrying it may set the client address, taken from x-real-ip, which
Vercel overwrites with the real visitor address on every request. The secret header is
removed before the app sees the request.
"""

import hmac

from starlette.types import ASGIApp, Receive, Scope, Send

SECRET_HEADER = b"x-notemind-proxy"


class TrustedProxyMiddleware:
    def __init__(self, app: ASGIApp, secret: str) -> None:
        self.app = app
        self.secret = secret.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = scope["headers"]
            sent = next((v for k, v in headers if k == SECRET_HEADER), None)
            scope = {**scope, "headers": [(k, v) for k, v in headers if k != SECRET_HEADER]}
            if sent is not None and hmac.compare_digest(sent, self.secret):
                real_ip = next((v for k, v in headers if k == b"x-real-ip"), None)
                if real_ip:
                    scope["client"] = (real_ip.decode("latin-1").strip(), 0)
        await self.app(scope, receive, send)
