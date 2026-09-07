"""Serve static sales files with clean URLs and native range requests.

Use the app's Python dependencies. Not a Cloud API server or deployment.
Default loopback binding is deliberate; --bind 0.0.0.0 permits a sandbox preview.
--production-headers adds the real frame restrictions for isolated browser QA.
"""
import argparse
import json
from pathlib import Path

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
from modules.static_site import SalesStaticFiles
import uvicorn
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1] / 'sales'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port', type=int, default=8765)
parser.add_argument('--bind', default='127.0.0.1')
parser.add_argument('--production-headers', action='store_true')
args = parser.parse_args()
headers = {h['key']: h['value'] for h in json.loads((ROOT / 'vercel.json').read_text())['headers'][0]['headers']}
if not args.production_headers:
    # Only the local static preview permits embedding. Deployment headers remain strict.
    headers.pop('X-Frame-Options', None)
    headers['Content-Security-Policy'] = headers['Content-Security-Policy'].replace("frame-ancestors 'none'; ", '')
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    for key, value in headers.items():
        response.headers[key] = value
    return response


# Use the same clean-path behavior as Desktop and the legacy /sales mount.
app.mount('/', SalesStaticFiles(directory=ROOT, html=True), name='sales')


if __name__ == '__main__':
    uvicorn.run(app, host=args.bind, port=args.port)
