#!/usr/bin/env bash
# Build AppIcon.icns from generate.swift.
#
# Output: ../AppIcon.icns (sibling of Pounce.swift; consumed by ../build.sh).

set -euo pipefail
cd "$(dirname "$0")"

GEN_BIN=".build/generate"
mkdir -p .build

echo "==> Compiling icon generator"
swiftc -O \
    -target arm64-apple-macos13.0 \
    -framework Cocoa \
    -o "$GEN_BIN" \
    generate.swift

echo "==> Rendering iconset"
"$GEN_BIN"

echo "==> Packing AppIcon.icns"
iconutil -c icns AppIcon.iconset -o ../AppIcon.icns

echo "==> Done: $(realpath ../AppIcon.icns)"
ls -la ../AppIcon.icns
