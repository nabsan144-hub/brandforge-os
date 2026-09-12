"""Bounded, read-only public HTTP fetches with DNS pinning and verified TLS.

Never use this for localhost models or authenticated provider API calls.
Untrusted research/image URLs cannot select private IPs, proxies, credentials,
redirects into private networks, or a second DNS answer at connection time.
"""
from __future__ import annotations
import ipaddress
import math
import re
import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from urllib.parse import urlsplit, urljoin
import urllib3
import certifi

_DNS = ThreadPoolExecutor(max_workers=4, thread_name_prefix='public-dns')
_DNS_SLOTS = threading.BoundedSemaphore(4)
_TRANSLATION = [ipaddress.ip_network('64:ff9b::/96'), ipaddress.ip_network('64:ff9b:1::/48')]


class PublicFetchError(ValueError):
    pass


def public_ip(value):
    try:
        address = ipaddress.ip_address(value)
        mapped = getattr(address, 'ipv4_mapped', None)
        if mapped is not None:
            address = mapped
        if not address.is_global or address.is_multicast:
            return False
        if address.version == 6 and (address.sixtofour or address.teredo or any(address in n for n in _TRANSLATION)):
            return False
        return True
    except ValueError:
        return False


def resolve_public(url, timeout=4):
    if not isinstance(url, str) or len(url) > 16384 or re.search(r'[\x00-\x20\\]', url):
        raise PublicFetchError('Invalid public URL')
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError()
        hostname = parsed.hostname.rstrip('.').encode('idna').decode('ascii').lower()
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == 'https' else 80)
        if not 1 <= port <= 65535 or len(hostname) > 253:
            raise ValueError()
    except (ValueError, UnicodeError):
        raise PublicFetchError('Invalid public URL') from None
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None and not public_ip(str(literal)):
        raise PublicFetchError('Private or nonpublic destination blocked')
    if not _DNS_SLOTS.acquire(blocking=False):
        raise PublicFetchError('Public lookup capacity reached')
    try:
        future = _DNS.submit(socket.getaddrinfo, hostname, port, 0, socket.SOCK_STREAM)
    except Exception:
        _DNS_SLOTS.release()
        raise PublicFetchError('Public resolver is unavailable') from None
    future.add_done_callback(lambda _: _DNS_SLOTS.release())
    try:
        answers = future.result(timeout=max(.1, min(timeout, 4)))
    except (FutureTimeout, OSError):
        raise PublicFetchError('Public hostname could not be resolved') from None
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses or any(not public_ip(address) for address in addresses):
        raise PublicFetchError('Private or nonpublic destination blocked')
    return parsed, hostname, port, addresses[0]


@dataclass
class PublicResponse:
    status_code: int
    headers: dict
    content: bytes
    url: str

    @property
    def text(self):
        match = re.search(r'charset=([\w-]+)', self.headers.get('content-type', ''), re.I)
        try:
            return self.content.decode(match[1] if match else 'utf-8', errors='replace')
        except LookupError:
            return self.content.decode('utf-8', errors='replace')


def _exchange(parsed, hostname, port, address, timeout, max_bytes, method):
    host = '[' + hostname + ']' if ':' in hostname else hostname
    if port != (443 if parsed.scheme == 'https' else 80):
        host += ':' + str(port)
    options = {'host': address, 'port': port, 'maxsize': 1, 'block': True,
               'timeout': urllib3.Timeout(connect=min(timeout, 5), read=min(timeout, 5))}
    if parsed.scheme == 'https':
        options.update(server_hostname=hostname, assert_hostname=hostname,
                       cert_reqs=ssl.CERT_REQUIRED, ca_certs=certifi.where())
        pool = urllib3.HTTPSConnectionPool(**options)
    else:
        pool = urllib3.HTTPConnectionPool(**options)
    response = None
    deadline = time.monotonic() + timeout
    try:
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query
        response = pool.urlopen(method, path, headers={'Host': host, 'User-Agent': 'BrandForge-Public-Audit/1.4', 'Accept-Encoding': 'identity'},
                                redirect=False, retries=False, preload_content=False)
        headers = {k.lower(): v for k, v in response.headers.items()}
        if headers.get('content-encoding', 'identity').lower() not in ('', 'identity'):
            raise PublicFetchError('Compressed public response rejected for bounded decoding')
        if headers.get('content-length', '').isdigit() and int(headers['content-length']) > max_bytes:
            raise PublicFetchError('Public response is too large')
        chunks, count = [], 0
        if method != 'HEAD':
            while True:
                if time.monotonic() > deadline:
                    raise PublicFetchError('Public response exceeded its time budget')
                block = response.read(min(65536, max_bytes + 1 - count), decode_content=False)
                if not block:
                    break
                count += len(block)
                if count > max_bytes:
                    raise PublicFetchError('Public response is too large')
                chunks.append(block)
        return PublicResponse(response.status, headers, b''.join(chunks), parsed.geturl())
    finally:
        if response is not None:
            response.close()
        pool.close()


def fetch_public(url, *, timeout=10, max_bytes=2_000_000, follow_redirects=True, method='GET'):
    if method not in ('GET', 'HEAD'):
        raise PublicFetchError('Public inspection is read-only')
    if isinstance(timeout, bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or timeout<=0:
        raise PublicFetchError('Timeout must be a positive finite number')
    if isinstance(max_bytes,bool) or not isinstance(max_bytes,int) or not 1<=max_bytes<=16_000_000:
        raise PublicFetchError('Invalid public response-size limit')
    deadline = time.monotonic() + min(float(timeout), 60)
    current = url
    for _ in range(6):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PublicFetchError('Public fetch timed out')
        parsed, host, port, address = resolve_public(current, remaining)
        started = time.monotonic()
        if started>=deadline:
            raise PublicFetchError('Public lookup exhausted the time budget')
        status, error = None, None
        try:
            result = _exchange(parsed, host, port, address, max(.1, deadline-time.monotonic()), max_bytes, method)
            status = result.status_code
        except Exception as exc:
            error = type(exc).__name__
            raise PublicFetchError('Public resource could not be read safely') from None
        finally:
            from modules.net_audit import LEDGER
            LEDGER.record(method, current, status=status, elapsed_ms=int((time.monotonic()-started)*1000), error=error)
        if result.status_code not in (301, 302, 303, 307, 308) or not follow_redirects:
            return result
        location = result.headers.get('location')
        if not location:
            raise PublicFetchError('Redirect has no destination')
        current = urljoin(current, location)
        if parsed.scheme == 'https' and urlsplit(current).scheme != 'https':
            raise PublicFetchError('HTTPS downgrade blocked')
    raise PublicFetchError('Too many redirects')
