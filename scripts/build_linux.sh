#!/usr/bin/env bash
# Build the Linux desktop bundle.
#
# Requires: Flet CLI, Flutter 3.x with Linux desktop support,
# CMake, ninja-build, clang and GTK 3 development headers.
set -euo pipefail
cd "$(dirname "$0")/.."

FLET="${FLET:-flet}"

"$FLET" build linux \
  --yes \
  --exclude tests scripts data build .pytest_cache \
  --org com.traductor \
  --project traductor_offline \
  --product "Traductor Offline" \
  --description "Traductor español-inglés 100% offline" \
  --build-version 0.1.0 \
  --build-number 1

echo
echo "Bundle generado en build/linux/"
