#!/usr/bin/env python3
"""
BrandForge OS — Cross-platform domain configuration script (Windows, macOS, Linux).
Usage:
  python scripts/set_site_url.py https://brandforge-os.com
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
import ipaddress

ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/set_site_url.py https://yourdomain.com")
        sys.exit(1)

    new_url = sys.argv[1].strip().rstrip("/")
    try:
        parsed = urlsplit(new_url)
        hostname = parsed.hostname or ''
        try: local = hostname == 'localhost' or ipaddress.ip_address(hostname).is_loopback
        except ValueError: local = hostname == 'localhost'
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/') or not hostname:
            raise ValueError()
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and local):
            raise ValueError()
        ascii_host = hostname.encode('idna').decode('ascii')
        if not re.fullmatch(r'[A-Za-z0-9.:-]+',ascii_host):raise ValueError()
        port = parsed.port
        hostpart = '['+ascii_host+']' if ':' in ascii_host else ascii_host
        new_url = parsed.scheme+'://'+hostpart+((':'+str(port)) if port else '')
    except (ValueError, UnicodeError):
        raise SystemExit('Provide a valid HTTPS origin without credentials, path, query or fragment. HTTP is allowed only on loopback.')

    # Detect current URL
    config_file = ROOT / "sales" / "assets" / "config.js"
    current_url = "https://brandforge-os.com"
    if config_file.exists():
        content = config_file.read_text(encoding="utf-8")
        m = re.search(r"site_url:\s*['\"]([^'\"]+)['\"]", content)
        if m:
            current_url = m.group(1).strip().rstrip("/")

    print(f"🔧 Setting domain to: {new_url} (replacing {current_url} and https://brandforge-os.com)")

    # 1. Update HTML files in sales/
    sales_dir = ROOT / "sales"
    for hf in sales_dir.glob("*.html"):
        text = hf.read_text(encoding="utf-8")
        text = text.replace(current_url, new_url)
        text = text.replace("https://brandforge-os.com", new_url)
        text = text.replace("https://brandforgeos.com", new_url)  # legacy un-hyphenated leftover
        text = text.replace("https://brandforge-os.vercel.app", new_url)
        hf.write_text(text, encoding="utf-8")
        print(f"  ✓ {hf.relative_to(ROOT)}")

    # 2. Update sitemap.xml & robots.txt
    sitemap = sales_dir / "sitemap.xml"
    if sitemap.exists():
        text = sitemap.read_text(encoding="utf-8")
        text = text.replace(current_url, new_url)
        text = text.replace("https://brandforge-os.com", new_url)
        text = text.replace("https://brandforgeos.com", new_url)  # legacy un-hyphenated leftover
        text = text.replace("https://brandforge-os.vercel.app", new_url)
        sitemap.write_text(text, encoding="utf-8")
        print(f"  ✓ {sitemap.relative_to(ROOT)}")

    robots = sales_dir / "robots.txt"
    if robots.exists():
        text = robots.read_text(encoding="utf-8")
        text = text.replace(current_url, new_url)
        text = text.replace("https://brandforge-os.com", new_url)
        text = text.replace("https://brandforgeos.com", new_url)  # legacy un-hyphenated leftover
        text = text.replace("https://brandforge-os.vercel.app", new_url)
        robots.write_text(text, encoding="utf-8")
        print(f"  ✓ {robots.relative_to(ROOT)}")

    # 3. Update sales/assets/config.js
    if config_file.exists():
        text = config_file.read_text(encoding="utf-8")
        text = re.sub(r"site_url:\s*['\"][^'\"]*['\"]", f"site_url: '{new_url}'", text)
        config_file.write_text(text, encoding="utf-8")
        print("  ✓ sales/assets/config.js site_url")

    # 4. Update branding guidelines if present
    bg = ROOT / "branding" / "brand-guidelines.md"
    if bg.exists():
        text = bg.read_text(encoding="utf-8")
        text = text.replace(current_url, new_url)
        text = text.replace("https://brandforge-os.com", new_url)
        text = text.replace("https://brandforgeos.com", new_url)  # legacy un-hyphenated leftover
        text = text.replace("https://brandforge-os.vercel.app", new_url)
        bg.write_text(text, encoding="utf-8")
        print("  ✓ branding/brand-guidelines.md")

    print(f"\n✅ Domain successfully updated to: {new_url}")


if __name__ == "__main__":
    main()
