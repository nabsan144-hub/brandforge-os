"""
BrandForge OS - Web Searcher & Site Auditor

Honest, multi-provider web search:
  1. Brave Search API   (if BRAVE_API_KEY set)
  2. Tavily Search API  (if TAVILY_API_KEY set)
  3. DuckDuckGo HTML    (no key; works from many residential IPs, may be
                         bot-challenged from datacenter IPs)
  4. DuckDuckGo Instant Answer API (no key, real but limited)
If everything fails → returns [] with meta "offline". Callers MUST render
that as "live search unavailable" — never fabricate results.

Site auditing: meta/SEO analysis works without any browser; Playwright
(real Chromium) is used automatically when installed for JS pages + screenshots.
"""

import ipaddress
import logging
import os
import re
from typing import List, Dict
from urllib.parse import urlparse, parse_qs, unquote
from modules.public_http import fetch_public

log = logging.getLogger("brandforge.web_searcher")

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class WebSearcher:
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir  # explicit tenant/data dir (screenshots); env is the fallback
        self.session = requests.Session() if requests else None
        # hostname -> (monotonic_ts, resolves_safe) — see _host_resolves_safe
        self._dns_cache: Dict[str, tuple] = {}
        self._DNS_CACHE_TTL = 15.0
        if self.session:
            self.session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
        self.blocked_networks = [
            ipaddress.ip_network('0.0.0.0/8'),      # "this network" — resolves to loopback on Linux
            ipaddress.ip_network('127.0.0.0/8'),
            ipaddress.ip_network('10.0.0.0/8'),
            ipaddress.ip_network('172.16.0.0/12'),
            ipaddress.ip_network('192.168.0.0/16'),
            ipaddress.ip_network('169.254.0.0/16'),  # link-local incl. cloud metadata
            ipaddress.ip_network('100.64.0.0/10'),   # CGNAT
            ipaddress.ip_network('198.18.0.0/15'),   # benchmarking / some CDN backends
            ipaddress.ip_network('::1/128'),
            ipaddress.ip_network('fc00::/7'),        # ULA
            ipaddress.ip_network('fe80::/10'),       # IPv6 link-local
        ]

    @staticmethod
    def _normalize_url(url: str) -> str:
        value = str(url or "").strip()
        if value and not re.match(r"^https?://", value, re.IGNORECASE):
            value = "https://" + value
        return value

    # ---------- SSRF protection (kept from v1, verified) ----------

    def _is_blocked_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return True
            # unbracketed IPv6 in the authority is invalid per RFC 3986 —
            # no legitimate URL looks like this; fail closed
            netloc = (parsed.netloc or "").split("@")[-1]
            if netloc.count(":") >= 2 and not netloc.startswith("["):
                return True
            hostname = parsed.hostname
            if not hostname:
                return True
            if hostname.lower() in ('localhost', 'metadata.google.internal'):
                return True

            def _in_blocked(ip) -> bool:
                for net in self.blocked_networks:
                    if ip in net:
                        return True
                return False

            def _check_ip(ip_str: str) -> bool:
                """True = block. Non-IP hostnames (domains) return False."""
                try:
                    ip = ipaddress.ip_address(ip_str)
                except ValueError:
                    # not an IP literal: fail closed only if it LOOKS like a
                    # mangled IPv6 (multiple colons), else treat as domain
                    return ip_str.count(':') >= 2
                if _in_blocked(ip):
                    return True
                # IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1) → check the v4 side
                mapped = getattr(ip, "ipv4_mapped", None)
                if mapped is not None and _in_blocked(mapped):
                    return True
                return False

            return _check_ip(hostname)
        except Exception:
            return True

    def _host_resolves_safe(self, hostname: str) -> bool:
        """Resolve the hostname and block if ANY address is private/loopback.
        Preflight check (the actual fetch separately pins its connection). This helper checks
        IP *literals* at parse time — a domain can resolve to 127.0.0.1 at
        fetch time. Network requests do not rely on this cached boolean;
        modules.public_http resolves and pins every real connection."""
        import socket
        import time as _time
        # Short-TTL cache: the Playwright request guard re-validates every
        # subresource of a page (dozens of requests, a handful of hosts) —
        # resolve each distinct hostname at most once per window.
        cached = self._dns_cache.get(hostname)
        now = _time.monotonic()
        if cached is not None and now - cached[0] < self._DNS_CACHE_TTL:
            return cached[1]
        try:
            infos = socket.getaddrinfo(hostname, None)
        except Exception:
            return False
        safe = bool(infos)
        for info in infos:
            addr = info[4][0]
            try:
                ip = ipaddress.ip_address(addr)
            except ValueError:
                continue
            for net in self.blocked_networks:
                if ip in net:
                    safe = False
                    break
                mapped = getattr(ip, "ipv4_mapped", None)
                if mapped is not None and mapped in net:
                    safe = False
                    break
            if not safe:
                break
        self._dns_cache[hostname] = (now, safe)
        return safe

    # ---------- search (honest, multi-provider) ----------

    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Returns a list of REAL results. Empty list = search unavailable.
        Never returns synthetic/placeholder rows."""
        # Long queries are truncated, not rejected: silently returning []
        # made long swarm queries look like "search unavailable".
        if not query:
            return []
        query = str(query)[:200]
        try:
            max_results = max(1, min(int(max_results), 10))
        except (TypeError, ValueError):
            max_results = 5
        if requests is None:
            return []

        for fn in (self._search_brave, self._search_tavily, self._search_ddg_html, self._search_ddg_instant):
            try:
                results = fn(query, max_results)
                if results:
                    return results
            except Exception:
                continue
        return []

    def _search_brave(self, query: str, max_results: int) -> List[Dict]:
        key = os.environ.get("BRAVE_API_KEY", "")
        if not key:
            return []
        resp = self.session.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={"X-Subscription-Token": key, "Accept": "application/json"},
            timeout=8,
        )
        resp.raise_for_status()
        out = []
        for r in resp.json().get("web", {}).get("results", [])[:max_results]:
            out.append({"title": r.get("title", "")[:100], "url": r.get("url", "")[:300], "snippet": (r.get("description") or "")[:200]})
        return out

    def _search_tavily(self, query: str, max_results: int) -> List[Dict]:
        key = os.environ.get("TAVILY_API_KEY", "")
        if not key:
            return []
        resp = self.session.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": query, "max_results": max_results},
            timeout=10,
        )
        resp.raise_for_status()
        out = []
        for r in resp.json().get("results", [])[:max_results]:
            out.append({"title": r.get("title", "")[:100], "url": r.get("url", "")[:300], "snippet": (r.get("content") or "")[:200]})
        return out

    def _search_ddg_html(self, query: str, max_results: int) -> List[Dict]:
        resp = self.session.post("https://html.duckduckgo.com/html/", data={"q": query}, timeout=8)
        resp.raise_for_status()
        html_text = resp.text[:20000]
        if "result__a" not in html_text:  # bot challenge / layout change → not real results
            log.warning("DDG HTML parser found 0 results on a 200 response — layout may have changed")
            return []
        results = []
        blocks = re.findall(r'<div class="result__body">.*?</div>\s*</div>', html_text, re.DOTALL)[: max_results * 2]
        for block in blocks:
            try:
                href_match = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', block)
                title_match = re.search(r'class="result__a"[^>]*>(.*?)</a>', block, re.DOTALL)
                snippet_match = re.search(r'result__snippet[^>]*>(.*?)</', block, re.DOTALL)
                if not href_match:
                    continue
                href = href_match.group(1)
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else "Result"
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()[:200] if snippet_match else ""
                if "uddg=" in href:
                    try:
                        qs = parse_qs(urlparse(href).query)
                        if "uddg" in qs:
                            href = unquote(qs["uddg"][0])
                    except Exception:
                        pass
                if href.startswith("http") and not self._is_blocked_url(href):
                    results.append({"title": title[:100], "url": href[:300], "snippet": snippet})
                    if len(results) >= max_results:
                        break
            except Exception:
                continue
        if not results:
            log.warning("DDG HTML parser found 0 results on a 200 response — layout may have changed")
        return results

    def _search_ddg_instant(self, query: str, max_results: int) -> List[Dict]:
        resp = self.session.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=8,
        )
        resp.raise_for_status()
        j = resp.json()
        out = []
        abstract = (j.get("AbstractText") or "").strip()
        if abstract and j.get("AbstractURL"):
            out.append({"title": (j.get("Heading") or query)[:100], "url": j["AbstractURL"][:300], "snippet": abstract[:200]})
        for t in (j.get("RelatedTopics") or [])[: max(0, max_results - len(out))]:
            if isinstance(t, dict) and t.get("Text") and t.get("FirstURL"):
                out.append({"title": t["Text"][:100], "url": t["FirstURL"][:300], "snippet": ""})
        return out

    def format_search_summary(self, query: str, results: List[Dict]) -> str:
        if not results:
            return "Live web search is unavailable right now (offline or network-limited). This section contains no live data."
        lines = [f"Live search '{query}':"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', '')} — {r.get('url', '')}\n   {r.get('snippet', '')[:150]}")
        return "\n".join(lines)[:2000]

    # ---------- site inspection & SEO audit ----------

    def fetch_html(self, url: str) -> str:
        if not url or len(str(url)) > 500:
            return ""
        url = self._normalize_url(url)
        if self._is_blocked_url(url):
            return ""
        try:
            response = fetch_public(url, timeout=15, max_bytes=2_000_000)
            return response.text if response.status_code < 400 else ''
        except Exception:
            return ''

    def inspect_competitor_url(self, url: str, html_text: str = None) -> str:
        if html_text is None:
            html_text = self.fetch_html(url)
        if not html_text:
            return ""
        html_text = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        html_text = re.sub(r'<style[^>]*>.*?</style>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', html_text)
        return re.sub(r'\s+', ' ', text).strip()[:6000]

    @staticmethod
    def _meta(html_text: str, name_attr: str) -> str:
        m = re.search(
            r'<meta[^>]+(?:name|property)=["\']' + re.escape(name_attr) + r'["\'][^>]+content=["\']([^"\']*)["\']',
            html_text, re.IGNORECASE,
        ) or re.search(
            r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name|property)=["\']' + re.escape(name_attr) + r'["\']',
            html_text, re.IGNORECASE,
        )
        return m.group(1).strip() if m else ""

    def seo_audit_html(self, url: str, html_text: str) -> Dict:
        """Static SEO/CRO analysis of raw HTML. No browser required."""
        from html import unescape

        html_text = str(html_text or "")[:200_000]
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html_text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        words = len(re.sub(r"<[^>]+>", " ", text).split())
        title_match = re.search(r"<title\b[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
        title_text = unescape(re.sub(r"<[^>]+>", " ", title_match.group(1))).strip() if title_match else ""
        h1 = re.findall(r"<h1\b[\s>]", html_text, re.IGNORECASE)
        h2 = re.findall(r"<h2\b[\s>]", html_text, re.IGNORECASE)
        cta_nodes = re.findall(r"<(?:a|button)\b[^>]*>(.*?)</(?:a|button)>", html_text, re.IGNORECASE | re.DOTALL)
        cta = [
            unescape(re.sub(r"<[^>]+>", " ", node)).strip()
            for node in cta_nodes
            if re.search(r"\b(?:buy|get started|sign up|pricing|start|order|book|try|download|contact)\b", unescape(re.sub(r"<[^>]+>", " ", node)), re.IGNORECASE)
        ]
        imgs = re.findall(r"<img\b[^>]*>", html_text, re.IGNORECASE)
        imgs_no_alt = [img for img in imgs if not re.search(r"\balt\s*=", img, re.IGNORECASE)]
        link_tags = re.findall(r"<link\b[^>]*>", html_text, re.IGNORECASE)
        canonical = any(
            re.search(r"\brel\s*=\s*[\"'][^\"']*\bcanonical\b[^\"']*[\"']", tag, re.IGNORECASE)
            and re.search(r"\bhref\s*=\s*([\"'])[^\"']+\1", tag, re.IGNORECASE)
            for tag in link_tags
        )
        schema = '"@type"' in html_text and 'application/ld+json' in html_text
        checks = {
            "has_title": bool(title_text),
            "title_length_ok": bool(title_text) and 30 <= len(title_text) <= 65,
            "has_meta_description": bool(self._meta(html_text, "description")),
            "has_og_tags": bool(self._meta(html_text, "og:title")),
            "has_canonical": canonical,
            "has_schema": schema,
            "h1_count": len(h1),
            "h2_count": len(h2),
            "has_cta": bool(cta),
            "cta_count": len(cta),
            "word_count": words,
            "images": len(imgs),
            "images_missing_alt": len(imgs_no_alt),
            "viewport_meta": bool(re.search(r"<meta\b[^>]*\bname\s*=\s*[\"']viewport[\"']", html_text, re.IGNORECASE)),
            "lang_attr": re.search(r"<html\b[^>]*\blang\s*=\s*[\"'][a-z]{2,3}(?:-[A-Za-z]{2,4})?[\"']", html_text, re.IGNORECASE) is not None,
        }

        def add(weight, condition):
            return weight if condition else 0

        score = 0
        score += add(10, checks["has_title"])
        score += add(5, checks["title_length_ok"])
        score += add(10, checks["has_meta_description"])
        score += add(8, checks["has_og_tags"])
        score += add(8, checks["has_canonical"])
        score += add(8, checks["has_schema"])
        if checks["h1_count"] == 1:
            score += 10
        elif checks["h1_count"]:
            score += 5
        score += add(5, checks["h2_count"] >= 2)
        score += add(10, checks["has_cta"])
        if words >= 600:
            score += 12
        elif words >= 300:
            score += 8
        elif words >= 100:
            score += 4
        if checks["viewport_meta"] and checks["lang_attr"]:
            score += 10
        elif checks["viewport_meta"]:
            score += 5
        score += add(8, checks["images"] and checks["images_missing_alt"] == 0)

        recommendations = []
        if not checks["has_title"]:
            recommendations.append("Add a <title>")
        elif not checks["title_length_ok"]:
            recommendations.append("Title should be 30–65 characters")
        if not checks["has_meta_description"]:
            recommendations.append("Add a meta description (150–160 chars)")
        if not checks["has_og_tags"]:
            recommendations.append("Add Open Graph tags for social sharing")
        if not checks["has_canonical"]:
            recommendations.append("Add a canonical link tag")
        if not checks["has_schema"]:
            recommendations.append("Add JSON-LD schema (Organization/Product) for rich results")
        if checks["h1_count"] != 1:
            recommendations.append(f"Use exactly one H1 (found {checks['h1_count']})")
        if not checks["has_cta"]:
            recommendations.append("Add a clear CTA button")
        if words < 600:
            recommendations.append(f"Aim for 600+ words of real content (found {words})")
        if checks["images_missing_alt"]:
            recommendations.append(f"Add alt text to {checks['images_missing_alt']} images")
        if not checks["viewport_meta"]:
            recommendations.append("Add mobile viewport meta tag")
        return {
            "url": url,
            "score": min(100, score),
            "title": title_text[:150],
            "checks": checks,
            "recommendations": recommendations,
        }

    def browser_audit(self, url: str, take_screenshot: bool = False,
                      pre_fetched_html: str = None) -> Dict:
        """Playwright first (real Chrome), falls back to static HTML analysis.
        `pre_fetched_html` avoids a second network fetch when the caller
        already pulled the page (deep_competitor_analysis)."""
        url = self._normalize_url(url)
        if self._is_blocked_url(url):
            return {"url": url, "error": "Blocked for security", "method": "blocked"}
        # Close the DNS-rebinding gap: _is_blocked_url only rejects IP
        # *literals* at parse time — a domain that RESOLVES to a private/
        # loopback/link-local address (169.254.169.254, 10.x, …) must be
        # rejected before Chrome is pointed at it. fetch_html() has always
        # done this check; the real-browser path must not skip it.
        try:
            hostname = urlparse(url).hostname
        except Exception:
            hostname = None
        if not hostname or not self._host_resolves_safe(hostname):
            return {"url": url, "error": "Blocked for security", "method": "blocked"}
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--force-webrtc-ip-handling-policy=disable_non_proxied_udp', '--dns-prefetch-disable', '--disable-background-networking'])
                context = browser.new_context(service_workers='block', accept_downloads=False)
                page = context.new_page()
                if not hasattr(context, 'route_web_socket'):
                    browser.close()
                    raise RuntimeError('Update Playwright to enable safe public-page inspection')
                context.route_web_socket('**/*', lambda route: route.close())
                context.add_init_script("for(const name of ['RTCPeerConnection','webkitRTCPeerConnection','WebTransport','Worker','SharedWorker']){try{Object.defineProperty(globalThis,name,{value:undefined,configurable:false,writable:false})}catch{}}")
                import time
                deadline = time.monotonic() + 30
                budget = {'requests': 0, 'bytes': 0}

                def _guard_request(route, request):
                    # Chrome never resolves an untrusted destination itself.
                    # Each read is pinned, bounded, cookieless and read-only.
                    if urlparse(request.url).scheme in ('data', 'blob'):
                        return route.continue_()
                    if request.method not in ('GET', 'HEAD') or budget['requests'] >= 80 or budget['bytes'] >= 32_000_000 or time.monotonic() >= deadline:
                        return route.abort()
                    budget['requests'] += 1
                    try:
                        result = fetch_public(request.url, timeout=min(5, deadline-time.monotonic()),
                                              max_bytes=min(6_000_000, 32_000_000-budget['bytes']),
                                              follow_redirects=False, method=request.method)
                        budget['bytes'] += len(result.content)
                        headers = {k:v for k,v in result.headers.items() if k in ('content-type', 'location', 'access-control-allow-origin')}
                        return route.fulfill(status=result.status_code, headers=headers, body=result.content)
                    except Exception:
                        return route.abort()

                context.route('**/*', _guard_request)
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                html_text = page.content()
                if len(html_text.encode('utf-8')) > 2_000_000:
                    browser.close()
                    raise RuntimeError('Rendered page exceeds analysis limit')
                title = page.title()[:200]
                text = page.inner_text("body")[:6000]
                result = self.seo_audit_html(url, html_text)
                result.update({
                    "title": title or result["title"],
                    "method": "playwright_real_browser",
                    "text_preview": text[:1500],
                })
                if take_screenshot:
                    import hashlib
                    safe = hashlib.sha256(url.encode()).hexdigest()[:8]
                    base = self.data_dir or os.environ.get("BRANDFORGE_DATA_DIR") or \
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
                    shot = os.path.join(base, "output", f"screenshot_{safe}.png")
                    os.makedirs(os.path.dirname(shot), exist_ok=True)
                    page.screenshot(path=shot, full_page=False)
                    result["screenshot"] = shot
                browser.close()
                return result
        except ImportError:
            html_text = pre_fetched_html or self.fetch_html(url)
            if not html_text:
                return {"url": url, "method": "static", "score": None,
                        "note": "Could not fetch page. Install playwright for JS pages: pip install playwright && playwright install chromium"}
            result = self.seo_audit_html(url, html_text)
            result["method"] = "static_html_analysis"
            return result
        except Exception as e:
            html_text = pre_fetched_html or self.fetch_html(url)
            if html_text:
                result = self.seo_audit_html(url, html_text)
                result["method"] = "static_html_analysis"
                result["playwright_error"] = str(e)[:150]
                return result
            return {"url": url, "error": str(e)[:200], "method": "failed"}

    def deep_competitor_analysis(self, url: str, brand_name: str = "") -> Dict:
        url = self._normalize_url(url)
        if self._is_blocked_url(url):
            return {"url": url, "error": "Blocked"}
        # Fetch once, reuse for both the text extract and the static-audit
        # fallback (previously every audit made 2-3 identical GETs).
        html_once = self.fetch_html(url)
        fast = self.inspect_competitor_url(url, html_text=html_once)
        audit = self.browser_audit(url, take_screenshot=False, pre_fetched_html=html_once)
        audit_checks = audit.get("checks") if isinstance(audit.get("checks"), dict) else {}
        insights = {
            "has_pricing": "pricing" in fast.lower() or "$" in fast,
            "has_testimonials": "testimonial" in fast.lower() or "review" in fast.lower(),
            "has_cta": "buy now" in fast.lower() or "get started" in fast.lower() or bool(audit_checks.get("has_cta")),
        }
        recommendations = list(audit.get("recommendations", []) if isinstance(audit.get("recommendations"), list) else [])
        if not insights["has_pricing"]:
            recommendations.append("Add clear pricing — transparency increases trust")
        if not insights["has_testimonials"]:
            recommendations.append("Add social proof — testimonials increase conversion")
        return {
            "url": url,
            "brand": brand_name[:80],
            "extracted_word_count": len(fast.split()),
            "audit": audit,
            "insights": insights,
            "recommendations": recommendations,
        }
