#!/usr/bin/env bash
set -euo pipefail

# Build the sts_lightspeed oracle module (slaythespire Python extension)
# Run via: just oracle  OR  ./scripts/build_oracle.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/third_party/sts_lightspeed"
BUILD="$SRC/build"

if [ ! -d "$SRC" ]; then
    echo "ERROR: sts_lightspeed submodule not found."
    echo "  Run: git submodule update --init --recursive"
    exit 1
fi

echo "==> Building sts_lightspeed pybind11 module..."
cmake -S "$SRC" -B "$BUILD" \
    -DCMAKE_BUILD_TYPE=Release \
    -DPYTHON_EXECUTABLE="$(which python3)"

cmake --build "$BUILD" -j"$(nproc)"

# Copy the built .so into the project's src tree so it's importable
EXT="$(find "$BUILD" -name 'slaythespire*.so' -o -name 'slaythespire*.pyd' | head -1)"
if [ -z "$EXT" ]; then
    echo "ERROR: Built extension not found in $BUILD"
    exit 1
fi

DEST="$ROOT/src/"
cp -v "$EXT" "$DEST"

echo "==> Done. Oracle module installed to $DEST"
echo "    Run: just test  (or pytest tests/test_oracle.py -v)"
