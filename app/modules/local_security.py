"""Local desktop browser boundary: trusted Host + per-install write capability.

This is not multi-user authentication. The server must still bind to loopback.
It blocks a hostile page from using an arbitrary DNS Host as its own origin.
"""
import ipaddress
import os
import re
import secrets
from pathlib import Path
from modules.runtime_paths import data_dir
from urllib.parse import urlsplit
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException

MAX_LOCAL_BODY = 4 * 1024 * 1024


def local_capability():
    root = Path(data_dir())
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'local-capability.token'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        token = path.read_text(encoding='ascii').strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{40,100}', token):
            raise RuntimeError('Invalid local capability file. Restore it or run explicit repair.')
        return token
    token = secrets.token_urlsafe(32)
    with os.fdopen(fd, 'w', encoding='ascii') as handle:
        handle.write(token)
    return token


def trusted_host(raw):
    if not raw or not re.fullmatch(r'[A-Za-z0-9.\-\[\]:]+', raw):
        return False
    try:
        parsed = urlsplit('//'+raw)
        host, port = parsed.hostname, parsed.port
        if not host or (port is not None and not 1 <= port <= 65535): return False
    except ValueError:
        return False
    allowed = {'localhost'} | {x.strip().lower() for x in os.environ.get('BRANDFORGE_ALLOWED_HOSTS','').split(',') if x.strip()}
    if os.environ.get('PYTEST_CURRENT_TEST'): allowed.add('testserver')
    if host.rstrip('.').lower() in allowed: return True
    try: return ipaddress.ip_address(host).is_loopback
    except ValueError: return False


def loopback_peer(scope):
    peer = (scope.get('client') or ('', 0))[0]
    if peer in ('testclient', 'testserver') and os.environ.get('PYTEST_CURRENT_TEST'):
        return True
    try:
        address = ipaddress.ip_address(peer)
        if getattr(address, 'ipv4_mapped', None):
            address = address.ipv4_mapped
        return address.is_loopback
    except ValueError:
        return False


class LocalSecurityMiddleware:
    def __init__(self, app, capability):
        self.app, self.capability = app, capability

    async def __call__(self, scope, receive, send):
        kind = scope['type']
        if kind not in ('http','websocket'):
            return await self.app(scope,receive,send)
        if not loopback_peer(scope):
            if kind == 'websocket': return await send({'type':'websocket.close','code':1008})
            return await JSONResponse({'detail':'Desktop accepts local connections only. Use the separate Cloud workspace for hosted access.'},status_code=403)(scope,receive,send)
        headers = Headers(scope=scope)
        if len(headers.getlist('host')) != 1 or not trusted_host(headers.get('host')):
            if kind == 'websocket': return await send({'type':'websocket.close','code':1008})
            return await JSONResponse({'detail':'Untrusted Host header'},status_code=400)(scope,receive,send)
        if kind == 'http' and scope.get('method') in ('POST','PUT','PATCH','DELETE'):
            # Approval links possess their own limited, expiring capability.
            approval = bool(re.fullmatch(r'/approval/[A-Za-z0-9_-]+',scope.get('path','')))
            if not approval and not secrets.compare_digest(headers.get('x-brandforge-token',''),self.capability):
                return await JSONResponse({'detail':'Local write capability required. Reload the dashboard, or read /api/session for local CLI use.'},status_code=403)(scope,receive,send)
        if kind == 'http':
            declared = headers.get('content-length')
            if declared is not None and (not declared.isdigit() or int(declared) > MAX_LOCAL_BODY):
                return await JSONResponse({'detail': 'Request body exceeds the 4 MB local limit or has an invalid length.'}, status_code=413)(scope, receive, send)
            size = 0
            async def bounded_receive():
                nonlocal size
                message = await receive()
                if message['type'] == 'http.request':
                    size += len(message.get('body', b''))
                    if size > MAX_LOCAL_BODY:
                        raise HTTPException(status_code=413, detail='Request body exceeds the 4 MB local limit.')
                return message
            return await self.app(scope, bounded_receive, send)
        await self.app(scope,receive,send)
