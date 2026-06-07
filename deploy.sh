#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 David Knespl
# SPDX-License-Identifier: EUPL-1.2
#
# Regenerate the orloj web edition (LINK-ONLY: no AHMP scans/figures embedded) and
# deploy it to the `gh-pages` branch of csh-cz/orloj-edice (GitHub Pages).
#
# gh-pages is a generated deploy branch: each run publishes a fresh snapshot, so the
# push is a force-push to gh-pages ONLY (never main). Scans stay on AHMP and are linked.
set -euo pipefail
cd "$(dirname "$0")"

WORK="work/orloj1587"
TITLE="Orlojní kniha (opis 1587)"
REMOTE="https://github.com/csh-cz/orloj-edice.git"
PY="${PY:-.venv/bin/python}"

echo ">> regeneruji edici (bez --embed-scan, skeny se nereprodukují) ..."
"$PY" -m transcribus.cli edition --out "$WORK" --title "$TITLE" --teige data/teige_taborsky.txt

if grep -rlq '<iframe' "$WORK/edition" 2>/dev/null; then
  echo "!! edice obsahuje <iframe> — přeruším (deploy musí být bez vložených skenů)"; exit 1
fi

echo ">> publikuji na gh-pages ..."
tmp="$(mktemp -d)"
cp -R "$WORK/edition/." "$tmp/"
touch "$tmp/.nojekyll"
(
  cd "$tmp"
  git init -q
  git checkout -q -b gh-pages
  git add -A
  git -c user.name="David Knespl" -c user.email="david.knespl@knespl.com" \
      commit -qm "deploy: orloj edition ($(date -u +%Y-%m-%dT%H:%MZ))

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
  git push -q --force "$REMOTE" gh-pages
)
rm -rf "$tmp"
echo ">> hotovo -> https://csh-cz.github.io/orloj-edice/"
