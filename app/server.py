"""
BRANDFORGE OS - The Marketing OS
FastAPI server — honest features, real gating, local-first.

- Serves dashboard at / and /dist/, sales site at /sales/
- Local desktop mode (default): full features, binds 127.0.0.1
- Hosted web mode (BRANDFORGE_HOSTED=1): binds 0.0.0.0, enforces free tier
  (3 campaigns) unless a valid license file exists (Paddle webhook fills it)
- Settings API for provider/API-key management (keys go to .env, chmod 600)
- Campaign detail / file / ZIP download endpoints
"""

import json
import os
from modules.runtime_paths import dashboard_dir
import re
import threading
import difflib
import functools
import time
from contextlib import nullcontext as _nullcontext
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Response, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from modules.static_site import SalesStaticFiles
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field, field_validator, model_validator

from engines.ai_engine import get_engine
from modules.project_manager import ProjectManager
from modules.client_manager import ClientManager
from modules.swarm_director import SwarmDirector
from modules.swarm_council import run_council as _run_council
from modules.swarm_council import stream_council as _run_council_stream
from modules.mcp_registry import MCPRegistry
from modules.campaign_templates import list_campaign_templates
from modules.document_exporter import campaign_pdf, campaign_docx
from modules.approval_manager import ApprovalManager
from modules.net_audit import LEDGER, install as _install_net_audit
from modules import update_check as _update_check

# Track requests-library calls. This is an application log, not an OS/network
# firewall; urllib, httpx, browser traffic and other processes are not covered.
_install_net_audit()

HOSTED = os.environ.get("BRANDFORGE_HOSTED", "0") == "1"
if HOSTED and os.environ.get("BRANDFORGE_I_UNDERSTAND_NO_AUTH", "0") != "1":
    raise RuntimeError(
        "BRANDFORGE_HOSTED=1 exposes this SINGLE-USER app with no authentication — every "
        "visitor could read all campaigns and change settings. For multi-user cloud, "
        "deploy hosted/ (login + server-enforced plans). To run this mode anyway, "
        "also set BRANDFORGE_I_UNDERSTAND_NO_AUTH=1."
    )
FREE_CAMPAIGN_LIMIT = 3

# Single source of truth for the runtime version (keep in sync with
# app/pyproject.toml and the CHANGELOG top entry at each release).
from version_info import __version__

app = FastAPI(
    title="BrandForge OS - The Marketing OS",
    description="Your offline marketing department. 6-stage pipeline, local-first, owned forever.",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------- security headers ----------
# Fonts are self-hosted (sales/assets/fonts) — no third-party origins needed.
# The dashboard index.html carries ONE inline theme-init script (reads
# localStorage before the bundle loads). It's allowlisted by exact hash so the
# strict script-src 'self' stays intact — without it the theme never restored
# and the CSP flagged a console error on every load.
_THEME_INLINE_HASH = "sha256-nS0NIpuTNkpLr/DMwkufcxTJVyEAzqnyuh0o2k4I52M="


def _compute_theme_inline_hash() -> str:
    """Hash the ACTUAL inline theme script in web/dist/index.html.

    The pinned constant above breaks silently whenever the dashboard is
    rebuilt with a changed inline script (theme restore stops working, only
    a console CSP error explains why). Computing the hash from the real file
    keeps the strict CSP intact across rebuilds; the constant stays as the
    fallback when the dist file is absent (pip-installed wheel).
    """
    import base64
    import hashlib
    try:
        dist_html = os.path.join(dashboard_dir(), "index.html")
        with open(dist_html, "r", encoding="utf-8") as f:
            html_text = f.read()
        # The theme-init script is the only attribute-less <script> tag
        # (the bundle is <script type="module" ...>), so the literal match
        # can only hit it.
        m = re.search(r"<script>(.*?)</script>", html_text, re.DOTALL)
        if m and m.group(1).strip():
            digest = hashlib.sha256(m.group(1).encode("utf-8")).digest()
            return "sha256-" + base64.b64encode(digest).decode("ascii")
    except Exception:
        pass
    return _THEME_INLINE_HASH


_DEFAULT_CSP = (
    "default-src 'self'; "
    f"script-src 'self' '{_compute_theme_inline_hash()}'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "img-src 'self' data: blob:; connect-src 'self' ws: wss:; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
)
# Generated deliverables (landing pages, ad cards, SVGs) are attacker-influenced
# surface: no scripts, no same-origin access, inline styles only.
_ARTIFACT_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; sandbox"
# The sales pages are first-party static content that legitimately uses inline
# scripts/styles (theme init, demo, ROI calculator). A 'self'-only script-src
# would freeze them (scroll-reveal elements stay invisible) when served from
# this server's /sales mount — so /sales gets inline permission, everything
# else keeps the strict policy. Paddle origins are allowed so the pricing
# page's checkout works when served from this mount too.
_SALES_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.paddle.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.paddle.com; img-src 'self' data: blob: https://*.paddle.com; "
    "connect-src 'self' https: https://*.paddle.com; font-src 'self' data:; "
    "media-src 'self' data:; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; frame-src https://*.paddle.com https://paddle.com"
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/approval/"):
        response.headers["Cache-Control"] = "no-store"
    # setdefault: per-route responses (deliverable files) carry a stricter CSP.
    if path in ("/docs", "/redoc", "/openapi.json") or path.startswith(("/docs/", "/redoc/")):
        # FastAPI's Swagger UI / ReDoc load their JS+CSS from cdn.jsdelivr.net;
        # the strict 'self'-only CSP made /docs a blank page. Relax ONLY the
        # docs routes to that one trusted CDN; everything else keeps the
        # strict policy.
        csp = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
    elif path == "/sales" or path.startswith("/sales/"):
        csp = _SALES_CSP
    else:
        csp = _DEFAULT_CSP
    response.headers.setdefault("Content-Security-Policy", csp)
    return response

# Local state corruption is not an empty dataset and must not look like success.
from modules.state_io import LocalStateError
from modules.settings_store import SettingsStorageError

@app.exception_handler(LocalStateError)
@app.exception_handler(SettingsStorageError)
async def local_state_failure(request, error):
    return JSONResponse({'detail': 'Local data could not be read or safely updated. Existing files were preserved; check storage and restore a valid backup if needed.'}, status_code=503)

# CORS: explicit allowlist by default; customize via BRANDFORGE_CORS_ORIGINS (comma list)
_default_cors_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
_cors_env = os.environ.get("BRANDFORGE_CORS_ORIGINS", "").strip()
if _cors_env:
    _origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    _origins = [o.strip() for o in _default_cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- CSRF: reject cross-origin state-changing requests ----------
# This API is intentionally unauthenticated (single-user, loopback by
# default). Browsers attach Origin to cross-origin POSTs — including
# "simple" text/plain bodies that skip the CORS preflight — and while the
# CORS block keeps the attacker's JS from READING the response, the request
# still EXECUTES server-side (blind CSRF: tool executions that trigger SSRF,
# swarm quota burn, settings/API-key overwrite). So: when Origin/Referer is
# present and is neither this server itself nor an explicitly allowed
# origin, refuse. Header-less clients (CLI, curl, Swagger UI, tests) are
# unaffected.
def _origin_of(header_value: str) -> str:
    """Normalize an Origin/Referer header to scheme://netloc. Returns ''
    only when the header is absent. A literal 'null' (sandboxed iframe,
    stripped referrer) or unparseable value normalizes to 'null', which
    never matches the allowlist — unknown origins fail closed."""
    v = (header_value or "").strip()
    if not v:
        return ""
    if v.lower() == "null":
        return "null"
    parsed = urlparse(v if "://" in v else f"http://{v}")
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else "null"


_EXTRA_CSRF_ORIGINS = {o.strip().rstrip("/") for o in _origins if o.strip() and o.strip() != "*"}
if any(o.strip() == "*" for o in _origins):
    raise RuntimeError("Wildcard CORS is not supported by the local desktop app; list explicit local origins")
_CSRF_CHECK_DISABLED = False

from modules.local_security import LocalSecurityMiddleware, local_capability
_LOCAL_CAPABILITY = local_capability()
app.add_middleware(LocalSecurityMiddleware, capability=_LOCAL_CAPABILITY)

@app.get("/api/session")
def local_browser_session():
    return JSONResponse({"capability": _LOCAL_CAPABILITY}, headers={"Cache-Control":"no-store"})


@app.middleware("http")
async def reject_cross_origin_writes(request: Request, call_next):
    if request.method in ("POST", "PUT", "DELETE", "PATCH") and not _CSRF_CHECK_DISABLED:
        origin = _origin_of(request.headers.get("origin") or "") or \
            _origin_of(request.headers.get("referer") or "")
        if origin:
            host = (request.headers.get("host") or "").strip()
            same_origin = host and origin in (f"http://{host}", f"https://{host}")
            if not same_origin and origin not in _EXTRA_CSRF_ORIGINS:
                return JSONResponse({"detail": "Cross-origin request blocked"}, status_code=403)
    return await call_next(request)

# ---------- rate limiting (with eviction, thread-safe) ----------
_rate_limit_store: Dict[str, List[float]] = {}
_rate_last_sweep = [time.time()]
_rate_lock = threading.Lock()
_RATE_STORE_CAP = 10_000

def _limit(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(f"BRANDFORGE_RATE_{name}", default)))
    except (TypeError, ValueError):
        return default


def _check_rate_limit(ip: str, limit: int = 20, window: int = 60, bucket: str = "default") -> bool:
    """Per-(IP, endpoint-family) rate limiting.

    Bucketing by endpoint family keeps one busy surface (e.g. chat) from
    starving another (e.g. the public approval portal) — the old single
    per-IP bucket conflated all endpoints."""
    global _rate_limit_store
    now = time.time()
    key = f"{ip}:{bucket}"
    with _rate_lock:
        if now - _rate_last_sweep[0] > 300:  # sweep stale IPs every 5 min
            _rate_limit_store = {
                k: v for k, v in _rate_limit_store.items() if v and now - max(v) < 300
            }
            _rate_last_sweep[0] = now
        if key not in _rate_limit_store and len(_rate_limit_store) >= _RATE_STORE_CAP:
            # Dict insertion order is request recency order for this store. Drop
            # the oldest half rather than allowing unique-IP floods to grow RAM.
            evict_count = max(1, _RATE_STORE_CAP // 2)
            for old_key in list(_rate_limit_store)[:evict_count]:
                _rate_limit_store.pop(old_key, None)
        bucket_list = _rate_limit_store.setdefault(key, [])
        # prune in place
        keep = [t for t in bucket_list if now - t < window]
        bucket_list.clear()
        bucket_list.extend(keep)
        if len(bucket_list) >= limit:
            return False
        bucket_list.append(now)
        return True

# Canonical implementations live in modules.security (single source of truth —
# these were duplicated across 5+ files with divergent rules). Names kept for
# backwards compatibility with tests and call sites.
from modules.security import safe_slug as _safe_slug, safe_text as _safe_text  # noqa: E402

# ---------- core singletons ----------
_engine = None
_pm = None
_cm = None
_tools = None
_approvals = None

_core_lock = threading.Lock()
# Serializes the free-tier "check count, then create" window in hosted desktop
# mode so concurrent swarm runs can't both pass the cap.
_free_tier_lock = threading.Lock()
# Serializes writes to the shared engine singleton (settings + client activation).
_settings_lock = threading.Lock()

def get_core():
    global _engine, _pm, _cm, _tools
    with _core_lock:
        if _engine is None:
            # Respect the founder's saved provider (config.json / .env).
            # Forcing "offline" here discarded Settings after every restart.
            _engine = get_engine(provider=None)
            _pm = ProjectManager()
            _cm = ClientManager()
            _tools = MCPRegistry()
    return _engine, _pm, _cm, _tools


def request_engine():
    import copy
    engine = get_core()[0]
    with _settings_lock:
        snapshot = copy.copy(engine)
        snapshot.config = copy.deepcopy(engine.config)
        snapshot._file_env = dict(engine._file_env)
        snapshot._request_snapshot = True
    return snapshot


def get_approvals():
    global _approvals
    if _approvals is None:
        _, pm, _, _ = get_core()
        with _core_lock:
            if _approvals is None:
                _approvals = ApprovalManager(pm.base_dir)
    return _approvals

# ---------- licensing (local = full; hosted = gated until licensed) ----------
def get_license_state() -> Dict[str, Any]:
    if not HOSTED:
        return {"mode": "local", "licensed": True, "tier": "desktop",
                "note": "Local install — full features, owned forever."}
    lic_file = os.path.join(os.path.dirname(__file__), "license.json")
    if os.path.exists(lic_file):
        try:
            with open(lic_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("valid"):
                return {"mode": "hosted", "licensed": True, "tier": data.get("tier", "pro"),
                        "note": "Licensed — full features."}
        except Exception:
            pass
    return {"mode": "hosted", "licensed": False, "tier": "free",
            "limit": FREE_CAMPAIGN_LIMIT,
            "note": f"Free tier: {FREE_CAMPAIGN_LIMIT} campaigns. Upgrade for unlimited."}

# ---------- static mounts ----------
_dist_dir = dashboard_dir()
_assets_dir = os.path.join(_dist_dir, "assets")
_sales_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sales")

if os.path.exists(_dist_dir) and os.path.exists(_assets_dir):
    # The root route is the canonical dashboard entry point. Do not mount the
    # same index again at /dist/ (duplicate URLs and duplicate SEO surface);
    # expose only its hashed assets for the relative paths in index.html.
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

if os.path.exists(_sales_dir):
    app.mount("/sales", SalesStaticFiles(directory=_sales_dir, html=True), name="sales")

# ---------- models ----------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    # None = use the engine's saved provider (Settings). Do not default to
    # "offline" — that silently downgraded every dashboard chat after the
    # founder connected Groq/Gemini.
    provider: Optional[str] = Field(None, max_length=20)
    use_tools: bool = True

    @field_validator('message')
    @classmethod
    def validate_message(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Message cannot be empty')
        return _safe_text(v, 2000)


class SwarmChatRequest(BaseModel):
    """Chat WITH the swarm: 3 agents discuss the question in turns."""
    message: str = Field(..., min_length=1, max_length=2000)

    @field_validator('message')
    @classmethod
    def validate_message(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Message cannot be empty')
        return _safe_text(v, 2000)


class PerformanceEntryRequest(BaseModel):
    spend: float = Field(..., ge=0, le=10_000_000)
    clicks: int = Field(0, ge=0, le=1_000_000_000)
    leads: int = Field(0, ge=0, le=1_000_000_000)
    revenue: float = Field(0, ge=0, le=10_000_000)
    note: str = Field("", max_length=300)


class BannerSize(BaseModel):
    width: int = Field(300, ge=50, le=5000)
    height: int = Field(250, ge=50, le=5000)
    preset: str = Field("", max_length=30)

    @model_validator(mode="after")
    def validate_preset(self):
        if self.preset:
            from modules.visual_designer import AD_SIZES
            if self.preset not in AD_SIZES: raise ValueError("Unknown banner preset")
            self.width, self.height = AD_SIZES[self.preset][:2]
        return self


class SwarmRequest(BaseModel):
    campaign_name: str = Field(..., min_length=1, max_length=80)
    product_name: str = Field(..., min_length=1, max_length=80)
    industry: str = Field("General", max_length=80)
    target_audience: str = Field("your customers", max_length=120)
    key_benefits: str = Field("High quality", max_length=500)
    client_id: Optional[str] = Field("default", max_length=40)
    lang: Optional[str] = Field("en", max_length=5, description="Campaign language: en, hi, ur, es, pt")
    tier: Optional[str] = Field(None, max_length=20, description="Ignored — tier is license-derived, not client-declared")

    custom_sizes: List[BannerSize] = Field(default_factory=list, max_length=21)
    offer: str = Field("", max_length=200)
    cta: str = Field("", max_length=40)
    url: str = Field("", max_length=500)
    generate_new_logo: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        if value and urlparse(value).scheme not in ("http", "https"):
            raise ValueError("Destination must be an http or https URL")
        return value

    @field_validator('campaign_name', 'product_name', 'industry', 'target_audience', 'key_benefits')
    @classmethod
    def validate_safe(cls, v):
        return _safe_text(v, 500)

class ToolRequest(BaseModel):
    tool_name: str = Field(..., min_length=1, max_length=40)
    args: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('tool_name')
    @classmethod
    def validate_tool(cls, v):
        v = _safe_slug(v, 40)
        if not v:
            raise ValueError('Invalid tool name')
        return v

class ClientRequest(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=80)
    industry: str = Field("Marketing & SaaS", max_length=80)
    tone_of_voice: str = Field("Executive, Bold", max_length=80)
    target_audience: str = Field("", max_length=120)
    brand_promise: str = Field("", max_length=240)
    proof_points: str = Field("", max_length=500)
    prohibited_claims: str = Field("", max_length=300)
    agency_footer: str = Field("", max_length=180)
    show_brandforge_branding: bool = True
    primary_color: str = Field("#E8B54A", max_length=20)
    secondary_color: str = Field("#0F172A", max_length=20)
    agency_brand: str = Field("BRANDFORGE OS", max_length=80)

    @field_validator('client_name', 'industry', 'tone_of_voice', 'agency_brand')
    @classmethod
    def validate_text(cls, v):
        return _safe_text(v, 80)

    @field_validator('target_audience')
    @classmethod
    def validate_audience(cls, v):
        return _safe_text(v, 120)

    @field_validator('brand_promise')
    @classmethod
    def validate_promise(cls, v):
        return _safe_text(v, 240)

    @field_validator('proof_points', 'prohibited_claims', 'agency_footer')
    @classmethod
    def validate_brand_notes(cls, v):
        return _safe_text(v, 500)

class ApprovalUpdateRequest(BaseModel):
    decision: Optional[str] = Field(None, max_length=30)
    comment: str = Field("", max_length=1000)

    @field_validator("decision")
    @classmethod
    def valid_decision(cls, value):
        if value == "":
            raise ValueError("Omit decision for a comment-only update")
        if value is not None and value not in ("approved", "changes_requested"):
            raise ValueError("Invalid approval decision")
        return value


class CampaignStatusRequest(BaseModel):
    status: str = Field(..., min_length=3, max_length=30)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        value = value.strip().lower()
        if value not in ProjectManager.CAMPAIGN_STATUSES:
            raise ValueError("Invalid campaign status")
        return value


class SettingsRequest(BaseModel):
    # provider=None means "leave the text provider unchanged" — an API client
    # saving only AI-image settings must not silently reset the text engine
    # to offline (the old default did exactly that).
    provider: Optional[str] = Field(None, max_length=20)
    api_key: Optional[str] = Field(None, max_length=200)
    model: Optional[str] = Field(None, max_length=80)
    # AI image design (separate engine, separate optional key)
    image_provider: Optional[str] = Field(None, max_length=20)
    image_model: Optional[str] = Field(None, max_length=80)
    image_api_key: Optional[str] = Field(None, max_length=200)

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value):
        return (str(value).strip().lower() if value else None)

    @field_validator('model')
    @classmethod
    def validate_model(cls, v, info):
        if v is not None and v.strip():
            value = v.strip()
            # OpenRouter model IDs conventionally contain one slash
            # (provider/model). Gemini path values are percent-encoded by the
            # client, so slash is safe there too, but reject path-like segments.
            pattern = r"^[A-Za-z0-9._:\-/]{1,80}$"
            if not re.match(pattern, value) or value.startswith(("/", "-")) or ".." in value:
                raise ValueError("Model name contains invalid characters")
            if ("//" in value or not re.fullmatch(r"[A-Za-z0-9._:-]+(?:/[A-Za-z0-9._:-]+)*", value)):
                raise ValueError("Model name contains invalid characters")
            return value
        return v

# ---------- routes ----------
@app.get("/", response_class=HTMLResponse)
def root():
    dist_path = os.path.join(dashboard_dir(), "index.html")
    if os.path.exists(dist_path):
        with open(dist_path, "r", encoding="utf-8") as f:
            return f.read()
    # Fallback — e.g. a pip-installed wheel without the static folders.
    # The CLI and API remain fully functional; the UI needs a git checkout.
    return """
    <html><head><title>BrandForge OS - Marketing OS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body{font-family:system-ui;background:#05070a;color:#fff;padding:40px} .card{background:#0a0e15;border:1px solid #1c2535;border-radius:16px;padding:24px;max-width:640px} a{color:#E8B54A} code{background:#1e293b;padding:2px 6px;border-radius:6px}</style></head><body>
    <div class="card">
    <h1>BrandForge OS — The Marketing OS</h1>
    <p>Campaign drafts you review and control.</p>
    <p>API docs: <a href="/docs">/docs</a> &nbsp;•&nbsp; Health: <a href="/health">/health</a></p>
    <p style="color:#9aa3b5;font-size:13px;margin-top:12px">Dashboard static files not found in this install.
    Run from a git checkout — <code>cd app &amp;&amp; python brandforge.py --onboard</code> — for the full UI.
    The CLI and API are fully functional here.</p>
    </div></body></html>
    """

@app.get("/health")
def health():
    eng, pm, cm, tools = get_core()
    lic = get_license_state()
    return {
        "status": "running",
        "name": "BrandForge OS",
        "tagline": "Campaign drafts you review and control",
        "version": __version__,
        "provider": eng.provider,
        # offline/ollama need no key — report False instead of a misleading
        # "has key" signal in the dashboard.
        "has_api_key": False if eng.provider in ("offline", "ollama") else eng.has_key(eng.provider),
        # Honesty signal: offline engine makes zero outbound AI calls;
        # ollama talks only to localhost. Anything else calls a cloud API.
        "offline_mode": eng.provider == "offline" or (eng.provider == "ollama" and urlparse(eng.ollama_url).hostname in ("localhost", "127.0.0.1", "::1")),
        "active_client": cm.get_active_client().get("client_name", "Default Studio"),
        "tools_count": len(tools.tools),
        "campaigns": len(pm.list_campaigns()),
        "license": lic,
        "time": datetime.now().isoformat(),
    }


# ---------- tracked requests + optional update check ----------

@app.get("/api/network-audit")
def api_network_audit():
    """Hosts/status for tracked requests-library calls, not exhaustive egress.
    Never records query strings, headers, keys or prompt bodies."""
    return LEDGER.snapshot()


_update_state: Dict[str, Any] = {
    "current": __version__, "latest": None, "update_available": False,
    "checked_at": None, "error": None,
}
_update_lock = threading.Lock()
_update_inflight = False
# Handle to the lazily-started worker so tests/ops can deterministically wait
# for a check to publish instead of racing a fixed poll budget (this is what
# made the consent-gate test flaky under full-suite load).
_update_thread = None


class UpdateConsentRequest(BaseModel):
    enabled: bool


@app.get("/api/update-consent")
def get_update_consent():
    """null = never asked (show the one-time prompt)."""
    eng, _, _, _ = get_core()
    return {"consent": eng.config.get("update_check"), "env_forced": _update_check.enabled(), "env_disabled": os.environ.get("BRANDFORGE_UPDATE_CHECK") is not None and not _update_check.enabled()}


@app.post("/api/update-consent")
def set_update_consent(req: UpdateConsentRequest):
    global _update_state
    with _settings_lock:
        eng, _, _, _ = get_core()
        if not eng.update_configuration({"update_check":"on" if req.enabled else "off"}):
            raise HTTPException(503, eng.settings_error)
    # a consent change invalidates any cached result so the next view of the
    # dashboard re-evaluates under the new gate
    with _update_lock:
        _update_state = {**_update_state, "checked_at": None}
    return {"consent": eng.config["update_check"]}


@app.get("/api/update-check")
def api_update_check(refresh: int = 0):
    """Maintenance-signal check against GitHub releases. Lazily started in a
    background thread (never blocks, never at import time so tests stay
    hermetic); BRANDFORGE_UPDATE_CHECK=0 disables it entirely. The check
    itself goes through requests, so it appears in the network ledger."""
    global _update_state, _update_inflight, _update_thread
    eng, _, _, _ = get_core()
    if not _update_check.allowed(str(eng.config.get("update_check", "")) == "on"):
        return {"current": __version__, "latest": None, "update_available": False,
                "checked_at": None, "error": "consent_required"}
    with _update_lock:
        needs_check = _update_state.get("checked_at") is None or refresh
        if needs_check and not _update_inflight:
            _update_inflight = True

            def _run():
                global _update_state, _update_inflight
                try:
                    _update_state = _update_check.check_for_update(__version__, consent=str(eng.config.get("update_check", "")) == "on")
                finally:
                    with _update_lock:
                        _update_inflight = False

            _update_thread = threading.Thread(target=_run, daemon=True, name="update-check")
            _update_thread.start()
        return _update_state

@app.get("/logo-mark.svg")
def logo_mark():
    p = os.path.join(_dist_dir, "logo-mark.svg")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(p, media_type="image/svg+xml", filename="logo-mark.svg")

@app.post("/api/chat")
def chat(req: ChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip, limit=_limit("CHAT", 30), window=60, bucket="CHAT"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    _, _, cm, _ = get_core()
    eng = request_engine()
    allowed = list(eng.PROVIDER_MODELS.keys())
    # Optional per-request override. Implemented as a shallow COPY of the
    # engine (shared memory/tools/clients, private provider/model/api_key) —
    # the old code mutated the singleton and restored it in `finally`, so two
    # concurrent chats with different providers ran with each other's
    # provider AND key (verified race).
    override = (req.provider or "").strip().lower() or None
    if override and override != eng.provider:
        if override not in allowed:
            raise HTTPException(status_code=400, detail=f"Unknown provider. Allowed: {', '.join(allowed)}")
        if override not in ("offline", "ollama") and not eng.has_key(override):
            raise HTTPException(status_code=400, detail=f"No API key configured for '{override}'. Set it in Settings or via environment.")
        import copy
        eng = copy.copy(eng)
        eng.provider = override
        eng.model = eng.PROVIDER_MODELS.get(override, eng.model)
        eng.api_key = eng.key_for(override) or ""
    try:
        active_client = cm.get_active_client()
        response = eng.generate_text(req.message, use_tools=req.use_tools,
                                     context={"industry": active_client.get("industry", ""),
                                              # Real audience field — the old code passed the
                                              # client's NAME here ("For Default Studio who…").
                                              "target_audience": active_client.get("target_audience", "")},
                                     client_id=active_client.get("client_id", "default"))
        used = getattr(eng, "last_provider", eng.provider)
        return {
            "founder_message": req.message,
            "brandforge_response": _generated_image_urls(response),
            "memory_saved": getattr(eng,"memory_saved",True),
            "vanguard_response": response,  # backward compat alias
            "provider": used,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)[:200]}") from e


# Images the chat tool loop generates land in the app's output dir. The model
# reports the PC path back; the dashboard can't render that, so swap any
# output-dir path (any OS separator style) for the served route.
_OUTPUT_PATH_RE = re.compile(r"[\w\-./\\]*?output[\\/](ai_image_[A-Za-z0-9]{8,32}\.(?:jpg|png))")


def _generated_image_urls(text: str) -> str:
    if not text or "ai_image_" not in text:
        return text
    return _OUTPUT_PATH_RE.sub(r"/api/files/generated/\1", text)


_GENERATED_FILE_RE = re.compile(r"^(?:ai_image_[A-Za-z0-9]{8,32}\.(?:jpg|png)|tool_[a-f0-9]{12}\.(?:svg|html))$")


@app.get("/api/files/generated/{filename}")
def generated_file(filename: str):
    """Serve chat-generated AI images. Strict allowlist: only
    ``ai_image_<8 hex>.jpg|png`` files that live in the tool output dir —
    no traversal, no arbitrary extension, no path escaping."""
    if not _GENERATED_FILE_RE.fullmatch(filename or ""):
        raise HTTPException(status_code=404, detail="File not found")
    _, _, _, tools = get_core()
    path = os.path.realpath(os.path.join(tools.output_dir, filename))
    if os.path.dirname(path) != os.path.realpath(tools.output_dir) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    media = {".png":"image/png", ".jpg":"image/jpeg", ".svg":"image/svg+xml", ".html":"text/html"}[os.path.splitext(path)[1]]
    return FileResponse(path, media_type=media,
                        headers={"Content-Security-Policy": _ARTIFACT_CSP})


@app.post("/api/swarm/chat")
def swarm_chat(req: SwarmChatRequest, request: Request):
    """The swarm DISCUSSES the question: Strategist → Copywriter → Critic,
    each reading the previous turns, then a combined final plan."""
    client_ip = request.client.host if request.client else "unknown"
    # 4 real provider calls per round — tighter than plain chat on purpose.
    if not _check_rate_limit(client_ip, limit=_limit("SWARM_CHAT", 8), window=60, bucket="SWARM_CHAT"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    _, _, cm, _ = get_core()
    eng = request_engine()
    try:
        active_client = cm.get_active_client()
        result = _run_council(
            eng, req.message,
            context={"industry": active_client.get("industry", ""),
                     "target_audience": active_client.get("target_audience", "")},
            client_id=active_client.get("client_id", "default"),
        )
        return {
            "turns": result["turns"],
            "final": _generated_image_urls(result["final"]),
            "provider": result["provider"],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Swarm chat failed: {str(e)[:200]}") from e


@app.post("/api/swarm/chat/stream")
async def swarm_chat_stream(req: SwarmChatRequest, request: Request):
    """The council DEBATE, live: Server-Sent Events emit each agent's turn as
    it finishes so the customer watches Strategist → Copywriter → Critic →
    FINAL PLAN happen, instead of staring at loading dots."""
    import asyncio as _aio
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip, limit=_limit("SWARM_CHAT", 8), window=60, bucket="SWARM_CHAT"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    _, _, cm, _ = get_core()
    eng = request_engine()
    active_client = cm.get_active_client()
    ctx = {"industry": active_client.get("industry", ""),
           "target_audience": active_client.get("target_audience", ""),
           "brand": active_client.get("client_name", "") or active_client.get("agency_brand", "")}
    client_id = active_client.get("client_id", "default")

    queue: "_aio.Queue" = _aio.Queue()
    loop = _aio.get_running_loop()

    def worker():
        try:
            for ev in _run_council_stream(eng, req.message, ctx, client_id):
                loop.call_soon_threadsafe(queue.put_nowait, ev)
        except Exception as e:  # surface as an event, never hang the stream
            loop.call_soon_threadsafe(queue.put_nowait,
                                      {"type": "final", "final": f"(council error: {str(e)[:150]})",
                                       "provider": getattr(eng, "provider", "offline")})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=worker, daemon=True).start()

    async def gen():
        while True:
            ev = await queue.get()
            if ev is None:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})

@app.post("/api/swarm/run")
def run_swarm(req: SwarmRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip, limit=_limit("SWARM", 10), window=60, bucket="SWARM"):
        raise HTTPException(status_code=429, detail="Campaign rate limit exceeded")

    _, pm, cm, _ = get_core()
    eng = request_engine()

    # Tier gating — license-derived, NOT client-declared. The check-then-create
    # window is serialized for the free tier with a module lock held across the
    # whole swarm run + save, so two concurrent requests can't both pass the
    # count before either campaign exists (same race class as the hosted
    # services, which enforce post-insert).
    lic = get_license_state()
    free_gate = lic.get("licensed") is False
    _gate = _free_tier_lock if free_gate else _nullcontext()

    safe_campaign = _safe_slug(req.campaign_name, 60)
    requested_client = (req.client_id or "").strip()
    if not requested_client or requested_client.lower() == "default":
        requested_client = cm.get_active_client().get("client_id", "default")
    client_id = _safe_slug(requested_client, 40)
    if not cm.get_client(client_id):
        raise HTTPException(status_code=404, detail="Client not found")

    try:
        with _gate:
            if free_gate:
                existing = pm.list_campaigns()
                if len(existing) >= FREE_CAMPAIGN_LIMIT:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": f"Free tier limit reached - {FREE_CAMPAIGN_LIMIT} campaigns max",
                            "upgrade": "Upgrade for unlimited campaigns and full commercial/white-label license rights.",
                            "current": len(existing),
                            "limit": FREE_CAMPAIGN_LIMIT,
                        },
                    )
            swarm = SwarmDirector(eng)
            result = swarm.execute_swarm_campaign(
                _safe_text(req.product_name, 80),
                _safe_text(req.industry, 80),
                _safe_text(req.target_audience, 120),
                _safe_text(req.key_benefits, 500),
                client_id=client_id,
                lang=req.lang or "en", custom_sizes=[size.model_dump() for size in req.custom_sizes],
                offer=_safe_text(req.offer, 200), cta=_safe_text(req.cta, 40), url=req.url,
                generate_new_logo=req.generate_new_logo,
            )
            out_dir = pm.save_campaign(safe_campaign, result["strategy_data"], result["copy_data"],
                                       result["visual_files"], client_id=client_id,
                                       analysis_data=result.get("analysis_data", {}),
                                       lang=req.lang or "en")
            # save_campaign auto-revisions when the name already exists (it
            # must never destroy a saved campaign's status/history) — report
            # the folder it actually wrote to, so "View Campaign" and the
            # download link point at the real campaign.
            safe_campaign = os.path.basename(os.path.normpath(out_dir))

            # Report the actual deliverables in the campaign folder, not just the
            # visuals — the report .md ships with every campaign.
            try:
                deliverables = sorted(f for f in os.listdir(out_dir)
                                      if f != "campaign.json" and not f.endswith("_export.zip"))
            except OSError:
                deliverables = list(result["visual_files"].keys())

        return {
            "campaign_name": safe_campaign,
            "product": result["strategy_data"]["product_name"],
            "status": "completed",
            "tier": lic.get("tier", "desktop"),
            "deliverables": deliverables,
            "strategy_preview": result["strategy_data"]["strategy_text"][:600],
            "research_live": result["meta"].get("research_live", False),
            # Phase 4: surface trust signals AT generation completion, not
            # only inside the campaign detail view.
            "provider": result["meta"].get("provider", eng.provider),
            "quality": (result.get("analysis_data") or {}).get("quality_score"),
            "claim_review": (result.get("analysis_data") or {}).get("claim_review"),
            "output_dir": out_dir,
            "view": f"/api/campaigns/{safe_campaign}",
            "download": f"/api/campaigns/{safe_campaign}/download",
            "features": {
                # Honest flags: local desktop is full; hosted free is limited.
                "watermarked": bool(lic.get("mode") == "hosted" and not lic.get("licensed")),
                "unlimited": bool(lic.get("licensed", True)),
                "browser_audit": True,  # tool exists in all installs; Playwright optional
                "white_label": bool(lic.get("licensed", True)),  # free hosted: no white-label promise
                "tier": lic.get("tier", "desktop"),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Swarm failed: {str(e)[:300]}") from e

@app.get("/api/campaigns")
def list_campaigns():
    _, pm, _, _ = get_core()
    camps = pm.list_campaigns()
    return {"campaigns": camps, "count": len(camps)}

@app.get("/api/campaigns/{name}")
def campaign_detail(name: str):
    _, pm, _, _ = get_core()
    data = pm.get_campaign(name)
    if not data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return data

@app.post("/api/campaigns/{name}/revisions")
def create_campaign_revision(name: str):
    _, pm, _, _ = get_core()
    try:
        return pm.create_revision(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Campaign not found") from None
    except (ValueError, json.JSONDecodeError) as exc:
        # json.JSONDecodeError is a ValueError subclass; a corrupt/half-written
        # campaign.json used to surface as a raw 500 traceback here.
        raise HTTPException(status_code=422, detail=f"Campaign data is corrupt and cannot be revised: {str(exc)[:120]}") from exc


@app.put("/api/campaigns/{name}/status")
def update_campaign_status(name: str, req: CampaignStatusRequest):
    _, pm, _, _ = get_core()
    try:
        return pm.update_campaign_status(name, req.status)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Campaign not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/campaigns/{name}/files/{filename}")
def campaign_file(name: str, filename: str):
    _, pm, _, _ = get_core()
    full = pm.get_campaign_file(name, filename)
    if not full:
        raise HTTPException(status_code=404, detail="File not found")
    media = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
             ".html": "text/html", ".json": "application/json", ".md": "text/markdown",
             ".csv": "text/csv", ".txt": "text/plain"}
    ext = os.path.splitext(full)[1].lower()
    resp = FileResponse(full, media_type=media.get(ext, "application/octet-stream"))
    if ext in (".html", ".svg"):
        resp.headers["Content-Security-Policy"] = _ARTIFACT_CSP
    return resp

@app.get("/api/campaigns/{name}/download")
def campaign_download(name: str):
    _, pm, _, _ = get_core()
    path = pm._campaign_path(_safe_slug(name, 60))
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Campaign not found")
    zip_path = pm.export_zip(name)  # unique temp file — no concurrent-download race
    # Delete the temp zip on BOTH the success path and any stream failure so
    # a failed download can't litter /tmp with export zips.
    def _cleanup():
        try:
            os.remove(zip_path)
        except OSError:
            pass
    try:
        return FileResponse(zip_path, media_type="application/zip",
                            filename=f"{_safe_slug(name, 60)}_export.zip",
                            background=BackgroundTask(_cleanup))
    except Exception:
        _cleanup()
        raise

@app.get("/api/campaign-templates")
def campaign_templates():
    """Safe, static starter briefs for the campaign-creation form."""
    return {"templates": list_campaign_templates()}


class TextRevisionRequest(BaseModel):
    strategy: Optional[str] = Field(None, max_length=20000)
    copy_text: Optional[str] = Field(None, alias="copy", max_length=20000)
    seo: Optional[str] = Field(None, max_length=20000)

@app.post("/api/campaigns/{name}/text-revision")
def edit_campaign_text(name: str, req: TextRevisionRequest):
    _, pm, _, _ = get_core()
    changes = req.model_dump(exclude_none=True, by_alias=True)
    if not changes: raise HTTPException(status_code=400,detail="No text changes supplied")
    try: return pm.revise_text(name,changes)
    except FileNotFoundError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=400,detail=str(exc)) from exc

@app.get("/api/campaigns/{name}/compare/{other}")
def compare_campaign_revisions(name: str, other: str):
    _, pm, _, _ = get_core()
    left, right = pm.get_campaign(name), pm.get_campaign(other)
    if not left or not right: raise HTTPException(status_code=404, detail="Campaign not found")
    left_copy=str((left.get("copy") or {}).get("copy_text", "")).splitlines()
    right_copy=str((right.get("copy") or {}).get("copy_text", "")).splitlines()
    diff=list(difflib.unified_diff(left_copy,right_copy,fromfile=name,tofile=other,lineterm=""))[:1000]
    return {"left":{"name":name,"status":left.get("status"),"quality":((left.get("analysis") or {}).get("quality_score") or {}).get("score"),"warnings":((left.get("analysis") or {}).get("claim_review") or {}).get("warning_count",0)},"right":{"name":other,"status":right.get("status"),"quality":((right.get("analysis") or {}).get("quality_score") or {}).get("score"),"warnings":((right.get("analysis") or {}).get("claim_review") or {}).get("warning_count",0)},"copy_diff":diff}

@app.get("/api/campaigns/{name}/export.pdf")
def campaign_pdf_export(name: str):
    _, pm, _, _ = get_core()
    campaign = pm.get_campaign(name)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    try:
        payload = campaign_pdf(campaign)
    except Exception as e:
        # Defense-in-depth: a malformed campaign must yield a clean 500 with
        # context, not an unhandled parser traceback.
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)[:150]}") from e
    return Response(content=payload, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{_safe_slug(name, 60)}_campaign.pdf"'})


@app.get("/api/campaigns/{name}/export.docx")
def campaign_docx_export(name: str):
    _, pm, _, _ = get_core()
    campaign = pm.get_campaign(name)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    try:
        payload = campaign_docx(campaign)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DOCX export failed: {str(e)[:150]}") from e
    return Response(content=payload, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="{_safe_slug(name, 60)}_copy_pack.docx"'})


@app.post("/api/campaigns/{name}/approval-links")
def create_approval_link(name: str, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    # Approval tokens were previously unlimited and unthrottled — anyone on
    # the loopback/LAN could balloon approvals.json forever.
    if not _check_rate_limit(client_ip, limit=_limit("APPROVAL", 20), window=60, bucket="APPROVAL"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    _, pm, _, _ = get_core()
    if not pm.get_campaign(name): raise HTTPException(status_code=404, detail="Campaign not found")
    token=get_approvals().create(name, store_token=not HOSTED)
    return {"token":token,"url":str(request.base_url).rstrip('/') + '/approval/' + token}


_APPROVAL_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def _approval_token_or_404(token: str) -> str:
    """Approval tokens are secrets.token_urlsafe(32) — [A-Za-z0-9_-]{43}.
    Anything outside that charset can never be a real token; rejecting it
    here (a) fails closed and (b) keeps arbitrary path text out of the
    HTML responses below (the submit handler redirects to /approval/{token}
    inside a meta-refresh attribute)."""
    if not _APPROVAL_TOKEN_RE.match(token or ""):
        raise HTTPException(status_code=404, detail="Approval link unavailable")
    return token


_APPROVAL_FILE_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


def _approval_campaign_dir(item) -> str:
    _, pm, _, _ = get_core()
    return pm.campaign_dir(item["campaign"])


@app.get("/approval/{token}", response_class=HTMLResponse)
def approval_portal(token: str):
    """Client-facing review portal v2: full deliverable set (visuals as
    images, landing page as a script-free sandboxed iframe), per-asset
    comments, approve / request-changes. Comments and decisions remain in
    approval_manager with a full audit trail."""
    import html
    token = _approval_token_or_404(token)
    item = get_approvals().get(token)
    if not item or item.get("revoked"): raise HTTPException(status_code=404, detail="Approval link unavailable")
    _, pm, _, _ = get_core(); campaign = pm.get_campaign(item['campaign'])
    if not campaign:
        raise HTTPException(status_code=404, detail="The campaign for this approval link no longer exists")
    product = html.escape(str((campaign.get('strategy') or {}).get('product_name', 'Campaign')))
    copy = html.escape(str((campaign.get('copy') or {}).get('copy_text', ''))[:12000]).replace('\n', '<br>')

    # ---- deliverables grid ----
    camp_dir = _approval_campaign_dir(item)
    try:
        names = sorted(f for f in os.listdir(camp_dir) if os.path.isfile(os.path.join(camp_dir, f)))
    except OSError:
        names = []
    imgs, pages, docs = [], [], []
    for f in names:
        if f == "campaign.json" or f.endswith("_export.zip"):
            continue
        low = f.lower()
        if low.endswith((".svg", ".png", ".jpg", ".jpeg", ".webp")):
            imgs.append(f)
        elif low.endswith((".html", ".htm")):
            pages.append(f)
        else:
            docs.append(f)

    def img_card(f):
        return (f'<figure><img src="/approval/{token}/file/{f}" alt="{html.escape(f)}" loading="lazy">'
                f'<figcaption>{html.escape(f)}</figcaption></figure>')

    def page_card(f):
        # Client sees the real page but scripts can never run: sandbox="".
        try:
            with open(os.path.join(camp_dir, f), encoding="utf-8", errors="replace") as fh:
                content = fh.read(5_000_001)
                if len(content.encode("utf-8")) > 5_000_000:
                    return ""
        except OSError:
            return ""
        return (f'<figure><iframe sandbox="" title="{html.escape(f)}" srcdoc="{html.escape(content, quote=True)}"></iframe>'
                f'<figcaption>{html.escape(f)} (scripts disabled)</figcaption></figure>')

    assets_grid = "".join(img_card(f) for f in imgs) + "".join(page_card(f) for f in pages)
    docs_list = "".join(f'<li><a href="/approval/{token}/file/{f}" download>{html.escape(f)}</a></li>' for f in docs)
    asset_options = "".join(f'<option value="{html.escape(f)}">{html.escape(f)}</option>' for f in (imgs + pages + docs))

    # ---- comments (legacy global + per-asset) ----
    comments = ""
    for c in item.get('comments', []):
        tag = f' <b>[{html.escape(str(c.get("asset")))}]</b>' if c.get("asset") else ""
        comments += (f'<li>{html.escape(str(c.get("text", "")))}{tag} '
                     f'<small>{html.escape(str(c.get("at", ""))[:19])}</small></li>')
    comments = comments or "<li>No comments yet.</li>"

    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{product} — Approval</title><style>body{{font-family:system-ui;background:#f5f6f8;color:#17202a;margin:0;padding:24px}}main{{max-width:860px;margin:auto;background:#fff;padding:28px;border-radius:14px}}textarea{{width:100%;min-height:90px}}button{{padding:10px 14px;margin:8px 8px 0 0;border:0;border-radius:8px;background:#18202a;color:#fff}}pre{{white-space:normal;line-height:1.6}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,240px),1fr));gap:14px}}figure{{margin:0;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden}}figure img{{width:100%;display:block;background:#0b0f17}}figure iframe{{width:100%;height:320px;border:0;background:#fff}}figcaption{{padding:8px 10px;font-size:12px;color:#57606a}}select,textarea{{font:inherit}}</style></head><body><main><p>CLIENT REVIEW</p><h1>{product}</h1><p>Status: {html.escape(str(item.get('decision','pending')).replace('_',' '))}</p><h2>Deliverables</h2><div class="grid">{assets_grid or "<p>No visual deliverables.</p>"}</div>{("<h2>Documents</h2><ul>" + docs_list + "</ul>") if docs_list else ""}<h2>Campaign copy</h2><pre>{copy}</pre><h2>Decision</h2><form method="post"><label>Comment on a specific deliverable (optional): <select name="asset"><option value="">— whole campaign —</option>{asset_options}</select></label><textarea name="comment" placeholder="Optional comment or requested changes"></textarea><br><button name="decision" value="approved">Approve</button><button name="decision" value="changes_requested">Request changes</button><button name="decision" value="">Comment only</button></form><h2>Comments</h2><ul>{comments}</ul></main></body></html>'''


@app.get("/approval/{token}/file/{fname}")
def approval_file(token: str, fname: str):
    """Serve one deliverable to a token holder. Fails closed: charset
    whitelist + realpath containment + revoked-token check. Non-image files
    download as attachments so nothing executes in the portal origin."""
    from fastapi.responses import Response as _Resp
    import mimetypes
    token = _approval_token_or_404(token)
    if not _APPROVAL_FILE_RE.match(fname or ""):
        raise HTTPException(status_code=404, detail="File unavailable")
    # internal state must never ride the review link, even to token holders
    if fname == "campaign.json" or fname.endswith("_export.zip") or fname.startswith("."):
        raise HTTPException(status_code=404, detail="File unavailable")
    item = get_approvals().get(token)
    if not item or item.get("revoked"): raise HTTPException(status_code=404, detail="Approval link unavailable")
    camp_dir = os.path.realpath(_approval_campaign_dir(item))
    target = os.path.realpath(os.path.join(camp_dir, fname))
    if os.path.commonpath([camp_dir, target]) != camp_dir or not os.path.isfile(target):
        raise HTTPException(status_code=404, detail="File unavailable")
    with open(target, "rb") as fh:
        body = fh.read(5_000_001)
    if len(body) > 5_000_000:
        raise HTTPException(status_code=413, detail="This file exceeds the review-link limit; export the complete pack from Desktop.")
    mime = mimetypes.guess_type(fname)[0] or "application/octet-stream"
    headers = {"Content-Disposition": "inline" if mime.startswith("image/") else "attachment", "Content-Security-Policy": _ARTIFACT_CSP}
    return _Resp(content=body, media_type=mime, headers=headers)


@app.get("/api/approvals")
def approvals_inbox():
    """Agency inbox: open review links with status + last client comment.
    Tokens are stored (desktop-local only) so links can be reopened."""
    return {"approvals": get_approvals().list_all()}


# ---------- Phase 6: manual performance loop ----------

_perf = None


def get_perf():
    global _perf
    if _perf is None:
        # get_core() takes _core_lock itself — call it BEFORE locking,
        # mirroring get_approvals() (a Lock is not reentrant).
        _, pm, _, _ = get_core()
        with _core_lock:
            if _perf is None:
                from modules.performance_tracker import PerformanceTracker
                _perf = PerformanceTracker(pm.base_dir)
    return _perf


@app.post("/api/campaigns/{name}/performance")
def add_performance(name: str, req: PerformanceEntryRequest):
    _, pm, _, _ = get_core()
    if not pm.get_campaign(name):
        raise HTTPException(status_code=404, detail="Campaign not found")
    entry = get_perf().add_entry(name, req.spend, req.clicks, req.leads,
                                 req.revenue, note=req.note)
    return {"entry": entry, "summary": get_perf().summary(name)}


@app.get("/api/campaigns/{name}/performance")
def get_performance(name: str):
    _, pm, _, _ = get_core()
    campaign = pm.get_campaign(name)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {
        "entries": get_perf().entries(name),
        "summary": get_perf().summary(name),
        # the AI side of the loop: quality score + engine this campaign used
        "quality": ((campaign.get("analysis") or {}).get("quality_score")),
        "provider": campaign.get("provider", "offline"),
    }


@app.post("/approval/{token}", response_class=HTMLResponse)
def approval_portal_submit(token: str, request: Request, decision: str = Form(""), comment: str = Form(""), asset: str = Form("")):
    token = _approval_token_or_404(token)
    # Public review links are shareable — a token-holder must not be able to
    # hammer the store (approvals.json growth / audit spam).
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip, limit=_limit("APPR_POST", 10), window=60, bucket="APPR_POST"):
        raise HTTPException(status_code=429, detail="Too many updates — try again shortly")
    item = get_approvals().update(token, decision or None, comment, asset=asset)
    if not item:
        raise HTTPException(status_code=404, detail="Approval link unavailable")
    return HTMLResponse('<html><head><meta http-equiv="refresh" content="0;url=/approval/'+token+'"></head><body>Saved.</body></html>')

@app.get("/api/approvals/{token}")
def approval_detail(token: str):
    token = _approval_token_or_404(token)
    item=get_approvals().get(token)
    if not item or item.get("revoked"): raise HTTPException(status_code=404, detail="Approval link unavailable")
    _, pm, _, _ = get_core()
    campaign = pm.get_campaign(item["campaign"])
    if not campaign:
        raise HTTPException(status_code=404, detail="The campaign for this approval link no longer exists")
    return {"approval": item, "campaign": campaign}


@app.put("/api/approvals/{token}")
def update_approval(token: str, req: ApprovalUpdateRequest, request: Request):
    token = _approval_token_or_404(token)
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip, limit=_limit("APPR_POST", 10), window=60, bucket="APPR_POST"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    item=get_approvals().update(token,req.decision,req.comment)
    if not item: raise HTTPException(status_code=404, detail="Approval link unavailable")
    return {"approval":item}


@app.delete("/api/approvals/{token}")
def revoke_approval(token: str, request: Request):
    token = _approval_token_or_404(token)
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip, limit=_limit("APPR_POST", 10), window=60, bucket="APPR_POST"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    if not get_approvals().revoke(token): raise HTTPException(status_code=404, detail="Approval link not found")
    return {"success":True}


@app.get("/api/tools")
def list_tools():
    _, _, _, tools = get_core()
    return {"tools": tools.list_tools(), "count": len(tools.tools)}

@app.post("/api/tools/execute")
def execute_tool(req: ToolRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip, limit=_limit("TOOL", 30), window=60, bucket="TOOL"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    _, _, _, tools = get_core()
    if req.tool_name not in [t["name"] for t in tools.list_tools()]:
        raise HTTPException(status_code=404, detail=f"Tool {req.tool_name} not found")
    try:
        result = tools.execute_tool(req.tool_name, req.args)
        if isinstance(result, dict) and result.get("error"):
            return JSONResponse({"success": False, "tool": req.tool_name, "error": str(result["error"])[:300]}, status_code=422)
        return {"tool": req.tool_name, "args": req.args, "result": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)[:200]}") from e

@app.get("/api/clients")
def list_clients():
    _, _, cm, _ = get_core()
    return {"clients": cm.list_clients(), "active": cm.get_active_client(), "count": len(cm.list_clients())}

@app.post("/api/clients")
def create_client(req: ClientRequest):
    _, _, cm, _ = get_core()
    client_id, updated = cm.save_named_client(req.model_dump(exclude_unset=True))
    return {"success": True, "client_id": client_id, "updated": updated}


@app.put("/api/clients/{client_id}")
def update_client(client_id: str, req: ClientRequest):
    """Update a Brand Brain profile without allowing its identifier to change."""
    _, _, cm, _ = get_core()
    safe_id = _safe_slug(client_id, 40)
    existing = cm.get_client(safe_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Client not found")
    updated = dict(existing)
    updated.update({
        "client_id": safe_id,
        "client_name": req.client_name,
        "industry": req.industry,
        "tone_of_voice": req.tone_of_voice,
        "target_audience": req.target_audience,
        "brand_promise": req.brand_promise,
        "proof_points": req.proof_points,
        "prohibited_claims": req.prohibited_claims,
        "agency_footer": req.agency_footer,
        "show_brandforge_branding": req.show_brandforge_branding,
        "primary_color": req.primary_color,
        "secondary_color": req.secondary_color,
        "agency_brand": req.agency_brand,
    })
    cm.save_client(updated)
    return {"success": True, "client": updated}


@app.post("/api/clients/{client_id}/logo")
async def upload_client_logo(client_id: str, logo: UploadFile = File(...)):
    _, _, cm, _ = get_core()
    if (logo.content_type or "") not in ("image/png", "image/jpeg"):
        raise HTTPException(status_code=400, detail="Logo must be PNG or JPEG")
    import tempfile
    suffix = ".png" if logo.content_type == "image/png" else ".jpg"
    # Read one byte beyond the limit instead of buffering an unbounded upload
    # from an unauthenticated request before checking its size.
    data = await logo.read(5_000_001)
    if not data or len(data) > 5_000_000:
        raise HTTPException(status_code=400, detail="Logo must be between 1 byte and 5 MB")
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f: f.write(data)
        path = cm.save_logo(client_id, tmp)
        return {"success": True, "logo_path": path}
    except (ValueError, OSError) as exc:
        # OSError includes PIL's UnidentifiedImageError — junk image bytes must
        # yield a clean 400, not an unhandled 500.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if os.path.exists(tmp): os.remove(tmp)


@app.get("/api/clients/{client_id}/logo")
def get_client_logo(client_id: str):
    """Serve a stored brand logo to the dashboard (upload existed, GET didn't).

    logo_path comes from the client profile JSON — validate it really points
    inside the managed logos dir before serving, so a hand-edited profile
    can't turn this into an arbitrary-file-read.
    """
    _, _, cm, _ = get_core()
    client = cm.get_client(_safe_slug(client_id, 40))
    path = (client or {}).get("logo_path", "")
    if not path or not isinstance(path, str):
        raise HTTPException(status_code=404, detail="Logo not found")
    logos_dir = os.path.realpath(os.path.join(cm.clients_dir, "logos"))
    resolved = os.path.realpath(path)
    try:
        if os.path.commonpath([logos_dir, resolved]) != logos_dir or not os.path.isfile(resolved):
            raise HTTPException(status_code=404, detail="Logo not found")
    except ValueError:
        raise HTTPException(status_code=404, detail="Logo not found") from None
    media = {".png": "image/png", ".jpg": "image/jpeg"}
    ext = os.path.splitext(resolved)[1].lower()
    if ext not in media:
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(resolved, media_type=media[ext])


@app.post("/api/clients/{client_id}/activate")
def activate_client(client_id: str):
    with _settings_lock:
        eng, _, cm, _ = get_core()
        safe_id = _safe_slug(client_id, 40)
        client = cm.get_client(safe_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        cm.set_active_client(safe_id)
        eng.refresh_active_client()
        return {"success": True, "active": safe_id, "client": client}

@app.get("/api/memory")
def get_memory(limit: int = 20, client: Optional[str] = None):
    # Clamp both ends: LIMIT -1 means "unbounded" in SQLite — a negative
    # query param would dump the entire chat history.
    limit = max(0, min(limit, 100))
    eng, _, cm, _ = get_core()
    # Default to the ACTIVE client: chats are saved under it, so the old
    # hardcoded default ("default") returned an empty history on a fresh
    # install whose chats live under e.g. "default_studio".
    if client is None:
        client = cm.get_active_client().get("client_id", "default")
    client_slug = _safe_slug(client, 40)
    history = eng.memory.get_recent_chat_history(limit=limit, client_id=client_slug)
    if eng.memory.last_error:
        raise HTTPException(503,'Memory could not be read. Existing data was preserved.')
    long_term=eng.memory.get_long_term_memory(client_slug)
    if eng.memory.last_error:
        raise HTTPException(503,'Long-term memory could not be read. Existing data was preserved.')
    return {"history": history, "count": len(history), "long_term_size": len(long_term)}

@app.get("/api/license")
def license_info():
    return get_license_state()

@app.get("/api/settings")
def get_settings():
    eng, _, cm, _ = get_core()
    # Never advertise the offline engine's internal model name — the Settings
    # UI used to re-submit it as a provider model when switching providers,
    # persisting "smart-offline-engine-v2" as e.g. a Groq model (wrong-model
    # 404 on every call, silent offline fallback).
    model = "" if eng.provider == "offline" else eng.model
    try:
        from modules.ai_image_designer import AIImageDesigner, IMAGE_PROVIDER_IDS
        img = AIImageDesigner(ai_engine=eng)
        image_settings = {
            "provider": img.provider_setting,
            "model": img.model_setting,
            "key_status": {p: img.has_key(p) for p in IMAGE_PROVIDER_IDS},
            "any_key": img.has_any_key(),
        }
    except Exception:
        image_settings = {"provider": "auto", "model": "", "key_status": {}, "any_key": False}
    return {
        "provider": eng.provider,
        "model": model,
        "has_api_key": eng.has_key(eng.provider),
        "providers": list(eng.PROVIDER_MODELS.keys()),
        "active_client": cm.get_active_client(),
        "license": get_license_state(),
        "image": image_settings,
    }

@app.get("/api/settings/key-status")
def settings_key_status(provider: str):
    """Return only whether a provider key exists, without changing the form state."""
    eng, _, _, _ = get_core()
    selected = (provider or "").strip().lower()
    if selected not in eng.PROVIDER_MODELS:
        raise HTTPException(status_code=400, detail="Unknown provider")
    return {"provider": selected, "has_api_key": eng.has_key(selected)}


@app.post("/api/settings")
def update_settings(req: SettingsRequest):
    # Validate all fields before the recoverable pair of file replacements.
    with _settings_lock:
        eng, _, _, _ = get_core()
        changes, keys = {}, {}
        if req.provider is None and (req.api_key is not None or req.model is not None):
            raise HTTPException(400, 'Choose a text provider when saving a key or model.')
        if req.provider is not None:
            if req.provider not in eng.PROVIDER_MODELS:
                raise HTTPException(400, 'Unknown text provider.')
            model = eng.DEPRECATED_MODELS.get((req.model or '').strip(),(req.model or '').strip())
            if (model in set(eng.PROVIDER_MODELS.values()) and model != eng.PROVIDER_MODELS[req.provider]) or (model.startswith('gemini-') and req.provider not in ('gemini','openrouter')):
                model = ''
            if req.api_key:
                if req.provider not in eng.ENV_KEYS or len(req.api_key.strip())<8 or any(c in req.api_key for c in ('\r','\n','\0')):
                    raise HTTPException(400, 'Enter a valid provider key of at least 8 characters.')
                keys[eng.ENV_KEYS[req.provider]]=req.api_key.strip()
            elif req.provider not in ('offline','ollama') and not eng.has_key(req.provider):
                raise HTTPException(400, 'This provider needs a configured API key.')
            changes.update(provider=req.provider,model=model or eng.PROVIDER_MODELS[req.provider])
        image_result={}
        if req.image_provider is not None or req.image_api_key or req.image_model is not None:
            from modules.ai_image_designer import AIImageDesigner,IMAGE_PROVIDERS,IMAGE_PROVIDER_SETTING_IDS
            current=AIImageDesigner(ai_engine=eng)
            chosen=(req.image_provider or current.provider_setting or 'auto').strip().lower()
            if chosen not in IMAGE_PROVIDER_SETTING_IDS:
                raise HTTPException(400, 'Unknown image provider.')
            image_model=(req.image_model or '').strip()
            if image_model and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',image_model):
                raise HTTPException(400, 'Invalid image model ID.')
            if req.image_api_key:
                if chosen not in IMAGE_PROVIDERS or len(req.image_api_key.strip())<8 or any(c in req.image_api_key for c in ('\r','\n','\0')):
                    raise HTTPException(400, 'Choose an image provider and enter a valid key.')
                keys[IMAGE_PROVIDERS[chosen]['env']]=req.image_api_key.strip()
            image_result={'image_provider':chosen,'image_model':image_model}
            changes.update(image_result)
        if not eng.update_configuration(changes,keys):
            raise HTTPException(503, eng.settings_error)
        return {'success':True,'provider':eng.provider,'model':eng.model,'has_api_key':eng.has_key(eng.provider),**image_result}

# ---------- WebSocket (valid JSON now) ----------
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []
        self.max_connections = 20
        self._lock = threading.Lock()

    async def connect(self, ws: WebSocket):
        # Reserve the slot before awaiting accept(); otherwise two handshakes
        # can both observe room and exceed the connection cap.
        with self._lock:
            if len(self.active) >= self.max_connections:
                allowed = False
            else:
                self.active.append(ws)
                allowed = True
        if not allowed:
            await ws.close(code=1008, reason="Too many connections")
            return False
        try:
            await ws.accept()
            return True
        except Exception:
            self.disconnect(ws)
            raise

    def disconnect(self, ws: WebSocket):
        with self._lock:
            if ws in self.active:
                self.active.remove(ws)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    import anyio

    # Cross-site WebSocket hijack guard: browsers do NOT enforce same-origin
    # on WebSocket handshakes, so a malicious page could open
    # ws://localhost:8000/ws and drive the engine (blind CSRF over WS).
    # The HTTP POST routes check Origin; the WS handshake must too.
    import secrets as _secrets
    offered = [x.strip() for x in websocket.headers.get("sec-websocket-protocol", "").split(",")]
    token = websocket.headers.get("x-brandforge-token", "")
    if not _secrets.compare_digest(token, _LOCAL_CAPABILITY) and not any(_secrets.compare_digest(x, _LOCAL_CAPABILITY) for x in offered):
        await websocket.close(code=1008, reason="Local write capability required")
        return
    ws_origin = _origin_of(websocket.headers.get("origin") or "")
    if ws_origin:
        host = (websocket.headers.get("host") or "").strip()
        same_origin = host and ws_origin in (f"http://{host}", f"https://{host}")
        if not same_origin and ws_origin not in _EXTRA_CSRF_ORIGINS:
            await websocket.close(code=1008, reason="Cross-origin connection blocked")
            return

    client_ip = websocket.client.host if websocket.client else "unknown"
    if not _check_rate_limit(client_ip, limit=_limit("WS", 20), window=60, bucket="WS"):
        await websocket.close(code=1008, reason="Rate limit")
        return
    connected = await manager.connect(websocket)
    if not connected:
        return
    try:
        await websocket.send_text(json.dumps({"type": "connected", "message": "BrandForge OS connected"}))
        while True:
            data = await websocket.receive_text()
            if len(data) > 2000:
                await websocket.send_text(json.dumps({"type": "error", "message": "Message too long - max 2000 chars"}))
                continue
            _, _, cm, _ = get_core()
            eng = request_engine()
            safe_data = _safe_text(data, 2000)
            # Same client context as /api/chat: the WS path used to save
            # history under client "default" with no brand context, so WS
            # conversations were invisible in client-scoped memory and never
            # saw the active brand's industry/audience (verified split).
            active_client = cm.get_active_client()
            call = functools.partial(
                eng.generate_text, safe_data,
                context={"industry": active_client.get("industry", ""),
                         "target_audience": active_client.get("target_audience", "")},
                client_id=active_client.get("client_id", "default"),
            )
            # generate_text is blocking (LLM HTTP / file I/O) — never run it on
            # the event loop or every other request freezes for the duration.
            resp = await anyio.to_thread.run_sync(call)
            await websocket.send_text(json.dumps({"type": "response", "message": resp[:2000]}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import argparse
    import uvicorn

    # Opt-in background daemon (heartbeat + daily summary + memory rotation).
    # Was dead code — nothing ever started it.
    if os.environ.get("BRANDFORGE_DAEMON", "0") == "1":
        try:
            try:
                from daemon import BrandForgeDaemon
            except ImportError:
                from daemon import VanguardDaemon as BrandForgeDaemon
            BrandForgeDaemon().start()
        except Exception as e:
            print(f"daemon unavailable: {e}")

    parser = argparse.ArgumentParser(description="BrandForge OS server")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind address. Default 127.0.0.1 (local-only, private). "
                             "Use Cloud for remote access; Desktop must remain on loopback.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    import ipaddress
    try:
        local_bind = args.host == 'localhost' or ipaddress.ip_address(args.host).is_loopback
    except ValueError:
        local_bind = False
    if not local_bind or HOSTED:
        parser.error('Desktop is local-only. Deploy the authenticated cloud/ product for remote access.')

    print(f"""
    BRANDFORGE OS v{__version__} | mode={'hosted' if HOSTED else 'local'}
    Dashboard:  http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/
    Sales:      http://localhost:{args.port}/sales/
    API docs:   http://localhost:{args.port}/docs
    Bind:       {args.host}:{args.port}
    """)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info", proxy_headers=False)
