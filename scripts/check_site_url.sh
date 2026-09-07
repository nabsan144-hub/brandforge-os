#!/usr/bin/env bash
# Fail the build if a staging domain or a mismatched public canonical URL leaks
# into the static site.
#
# Production origin resolution: SITE_URL env override → else the committed
# sales/assets/config.js site_url → else the legacy custom domain. The
# configured production host is by definition not "staging", so deploying on a
# free host (vercel.app etc.) passes while a REAL mismatch still fails.
set -euo pipefail
cd "$(dirname "$0")/.."

REAL_DOMAIN="${SITE_URL:-}"
if [ -z "$REAL_DOMAIN" ] && [ -f sales/assets/config.js ]; then
  REAL_DOMAIN="$(sed -n "s/^ *site_url: *'\([^']*\)'.*$/\1/p" sales/assets/config.js | tail -1)"
fi
REAL_DOMAIN="${REAL_DOMAIN%/}"
[ -z "$REAL_DOMAIN" ] && REAL_DOMAIN="https://brandforge-os.com"
PROD_HOST="${REAL_DOMAIN#http://}"
PROD_HOST="${PROD_HOST#https://}"
PROD_HOST="${PROD_HOST%%/*}"
BAD_PATTERNS=('workers\.dev' 'vercel\.app' 'netlify\.app' 'github\.io')
fail=0

while IFS= read -r file; do
  for pattern in "${BAD_PATTERNS[@]}"; do
    # the configured production host is never "staging"
    if [[ "$PROD_HOST" =~ $pattern ]]; then continue; fi
    if grep -Eq "$pattern" "$file"; then
      echo "❌ $file contains staging URL pattern: /$pattern/"
      fail=1
    fi
  done
  # Legacy un-hyphenated domain (brandforgeos.com) was never purchased — any
  # occurrence is a dead link or a bouncing support address. Hyphenated
  # brandforge-os.com does NOT contain this substring, so this is safe.
  if grep -Eq "brandforgeos\.com" "$file"; then
    echo "❌ $file references the dead legacy domain brandforgeos.com (real domain: brandforge-os.com)"
    fail=1
  fi
  # Canonical tags are intentionally absolute for search engines. Use fixed
  # string checks so dots or other valid domain characters are not interpreted
  # as a regular expression.
  # Skip sales/assets/domain.js: it is the RUNTIME canonical fixer — it sets
  # href dynamically from effectiveSiteUrl, so it never contains (and must
  # never contain) a hardcoded canonical literal.
  if [[ "$file" != */assets/domain.js ]] && grep -Eq "rel=[\"']canonical[\"']" "$file"; then
    if ! grep -Fq "href=\"${REAL_DOMAIN}" "$file" && ! grep -Fq "href='${REAL_DOMAIN}" "$file"; then
      echo "❌ $file canonical does not point at ${REAL_DOMAIN}"
      fail=1
    fi
  fi
done < <(find sales cloud -type f \( -name '*.html' -o -name '*.xml' -o -name '*.txt' -o -name '*.js' \) \
  -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/dist/*' -not -path '*/build/*' \
  -not -path '*/tests/*' | sort)

if [ "$fail" -ne 0 ]; then
  echo "Staging-domain check FAILED — fix the URLs above before shipping."
  exit 1
fi
echo "✅ Staging-domain check passed (${REAL_DOMAIN})."
