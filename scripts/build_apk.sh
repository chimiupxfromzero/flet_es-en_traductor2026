#!/usr/bin/env bash
# Build small, per-architecture Android APKs.
#
#   scripts/build_apk.sh [arm64-v8a]
#
# Requires: Flet CLI, Flutter, Java 17+, Android SDK with accepted licenses.
set -euo pipefail
cd "$(dirname "$0")/.."

ARCH="${1:-}"
FLET="${FLET:-flet}"

if [[ -n "$ARCH" ]]; then
  ARCH_ARGS=(--arch "$ARCH")
else
  ARCH_ARGS=()
fi

"$FLET" build apk \
  --yes \
  --exclude tests scripts data build .pytest_cache \
  --org com.traductor \
  --project traductor_offline \
  --product "Traductor Offline" \
  --description "Traductor español-inglés 100% offline" \
  --build-version 0.1.0 \
  --build-number 1 \
  --split-per-abi \
  "${ARCH_ARGS[@]}"

echo
echo "APK(s) generados en build/apk/"
