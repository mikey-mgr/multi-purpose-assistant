"""
Raw debug probe for the Evolution API webhook.

Binds the same address/port as app.webhook_server and prints EVERY incoming
request verbatim (method, headers, raw body) so you can see exactly what
Evolution API is actually sending.

Run it INSTEAD of the normal webhook (it holds the same port). Point Evolution's
webhook at http://<this-host>:8055/api/webhooks/evolution then send a message.

Usage:
    python scripts/raw_evo_probe.py [port]
"""
import json
import sys

from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def dump(request: Request, path: str):
    body = await request.body()
    print("\n" + "=" * 70)
    print(f"METHOD : {request.method}")
    print(f"PATH   : /{path}")
    print(f"QUERY  : {request.url.query if request.url.query else '(none)'}")
    print("-" * 70)
    for k, v in request.headers.items():
        if k.lower() in ("apikey", "authorization", "content-type"):
            print(f"HDR {k}: {v}")
    print("-" * 70)
    if body:
        raw = body.decode("utf-8", errors="replace")
        print("RAW BODY:")
        print(raw)
        try:
            parsed = json.loads(raw)
            print("-" * 70)
            print("PARSED (pretty):")
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except Exception:
            print("(body is not valid JSON / no event field)")
    else:
        print("(no body)")
    print("=" * 70)
    return {"status": "dumped"}


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8055
    uvicorn.run(app, host="::", port=port, reload=False)