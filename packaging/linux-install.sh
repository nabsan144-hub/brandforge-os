#!/bin/sh
# Per-user, offline install/repair. Never touches BrandForgeOS customer data.
set -eu
BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEST="${HOME}/.local/opt/brandforge-os"
case "${1:-}" in ''|--repair|--uninstall|--rollback|--discard-backup) ;; *) echo 'Usage: install.sh [--repair|--rollback|--discard-backup|--uninstall]'; exit 2;; esac
for exe in /proc/[0-9]*/exe; do
  resolved=$(readlink -- "$exe" 2>/dev/null || true)
  case "$resolved" in "$DEST/"*|"$DEST.previous/"*) echo 'Close the installed BrandForge application before changing its runtime.'; exit 1;; esac
done
if [ "${1:-}" = "--uninstall" ]; then
  rm -rf -- "$DEST" "$DEST.previous"
  rm -f -- "$HOME/.local/share/applications/brandforge-os.desktop"
  echo 'Application and rollback runtime removed. Customer data and data backups were not deleted.'; exit 0
fi
if [ "${1:-}" = "--discard-backup" ]; then
  rm -rf -- "$DEST.previous"; echo 'Previous runtime removed; customer data unchanged.'; exit 0
fi
if [ "${1:-}" = "--rollback" ]; then
  [ -d "$DEST.previous" ] || { echo 'No previous runtime'; exit 1; }
  [ ! -e "$DEST.swap" ] || { echo 'Resolve the interrupted rollback (.swap) before continuing.'; exit 1; }
  [ ! -e "$DEST" ] || mv -- "$DEST" "$DEST.swap"
  if ! mv -- "$DEST.previous" "$DEST"; then
    [ ! -e "$DEST.swap" ] || mv -- "$DEST.swap" "$DEST"
    exit 1
  fi
  [ ! -e "$DEST.swap" ] || mv -- "$DEST.swap" "$DEST.previous"
  echo 'Runtime rollback complete. Customer data unchanged; this does not downgrade or restore data.'; exit 0
fi
[ -x "$BASE/runtime/BrandForge" ] || { echo 'Missing runtime'; exit 1; }
[ -f "$BASE/SHA256SUMS" ] || { echo 'Missing integrity manifest'; exit 1; }
(cd "$BASE" && sha256sum --check --strict SHA256SUMS >/dev/null)
[ ! -e "$DEST.previous" ] || { echo 'A rollback copy exists. Use --discard-backup after reviewing it, then run --repair.'; exit 1; }
mkdir -p "$HOME/.local/opt" "$HOME/.local/share/applications"
STAGE="$DEST.installing"
[ ! -e "$STAGE" ] || { echo 'Resolve the interrupted staging copy (.installing) before continuing.'; exit 1; }
if ! cp -R -- "$BASE/runtime" "$STAGE"; then rm -rf -- "$STAGE"; exit 1; fi
if ! (cd "$STAGE" && sed 's|  runtime/|  |' "$BASE/SHA256SUMS" | sha256sum --check --strict >/dev/null); then rm -rf -- "$STAGE"; exit 1; fi
[ ! -e "$DEST" ] || mv -- "$DEST" "$DEST.previous"
if ! mv -- "$STAGE" "$DEST"; then
  [ ! -e "$DEST.previous" ] || mv -- "$DEST.previous" "$DEST"
  exit 1
fi
EXEC=$(printf '%s' "$DEST/BrandForge" | sed 's/\\/\\\\/g;s/"/\\"/g;s/`/\\`/g;s/\$/\\$/g;s/%/%%/g')
cat > "$HOME/.local/share/applications/brandforge-os.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=BrandForge OS
Exec="$EXEC"
Terminal=true
Categories=Office;
DESKTOP
printf '%s\n' 'Installed. Launch BrandForge OS from your application menu.' 'Prior runtime retained as .previous when updating. Close the application before repair, rollback or uninstall.'
