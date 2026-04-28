#!/usr/bin/env bash
# Build the sts_lightspeed pybind11 module and install it into the project venv.
#
# Run from repo root:  ./scripts/build_oracle.sh
# Or via just:         just oracle
#
# Requirements (Arch Linux):
#   sudo pacman -S cmake gcc python
#   (Python dev headers ship with the python package on Arch)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUBMODULE="$REPO_ROOT/third_party/sts_lightspeed"
BUILD_DIR="$REPO_ROOT/build/sts_lightspeed"
VENV="$REPO_ROOT/.venv"

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
for cmd in g++ python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: '$cmd' not found. Please install it first." >&2
        echo "  Arch: sudo pacman -S gcc python" >&2
        exit 1
    fi
done

# cmake may live in the project venv (installed via: uv add --dev cmake)
if ! command -v cmake &>/dev/null; then
    echo "ERROR: 'cmake' not found." >&2
    echo "  Install system cmake: sudo pacman -S cmake" >&2
    echo "  Or install via uv:    uv add --dev cmake" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Ensure submodule is populated
# ---------------------------------------------------------------------------
if [ ! -f "$SUBMODULE/CMakeLists.txt" ]; then
    echo "Initialising sts_lightspeed submodule..."
    git -C "$REPO_ROOT" submodule update --init --recursive third_party/sts_lightspeed
fi

if [ ! -f "$SUBMODULE/pybind11/CMakeLists.txt" ]; then
    echo "Initialising nested submodules (pybind11, json)..."
    git -C "$SUBMODULE" submodule update --init --recursive
fi

# ---------------------------------------------------------------------------
# Configure + build
# ---------------------------------------------------------------------------
echo "Configuring cmake..."
cmake \
    -S "$SUBMODULE" \
    -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_FLAGS="-Wno-shift-count-overflow -O3" \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5

echo "Building slaythespire module..."
cmake --build "$BUILD_DIR" --target slaythespire -j"$(nproc)"

# ---------------------------------------------------------------------------
# Install into venv site-packages
# ---------------------------------------------------------------------------
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
SITE_PACKAGES="$VENV/lib/python${PYTHON_VERSION}/site-packages"

if [ ! -d "$SITE_PACKAGES" ]; then
    echo "ERROR: venv site-packages not found at $SITE_PACKAGES" >&2
    echo "  Did you create the venv? Run: uv sync" >&2
    exit 1
fi

# Find the built .so file
SO_FILE=$(find "$BUILD_DIR" -maxdepth 1 -name "slaythespire*.so" | head -1)
if [ -z "$SO_FILE" ]; then
    echo "ERROR: Could not find slaythespire*.so in $BUILD_DIR" >&2
    exit 1
fi

echo "Installing $SO_FILE -> $SITE_PACKAGES/"
cp "$SO_FILE" "$SITE_PACKAGES/"

echo ""
echo "Done. Verify with: python -c 'import slaythespire; print(slaythespire)'"
