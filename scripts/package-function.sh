#!/usr/bin/env bash
# Build the single deployment archive holding the function code and its libraries.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FUNC_DIR="$ROOT/src/functions"
PKG_DIR="$ROOT/build/package"
ZIP_FILE="$ROOT/build/function.zip"

echo "[1/4] Preparing build directory ..."
rm -rf "$PKG_DIR" "$ZIP_FILE"
mkdir -p "$PKG_DIR"

echo "[2/4] Copying function sources ..."
cp -r "$FUNC_DIR/src/." "$PKG_DIR/"
cp "$FUNC_DIR/requirements.txt" "$PKG_DIR/requirements.txt"

echo "[3/4] Bundling declared libraries into the same archive ..."
if python -m pip install --no-deps --disable-pip-version-check -q \
    -r "$FUNC_DIR/requirements.txt" -t "$PKG_DIR" >/dev/null 2>&1; then
  echo "      bundled libraries from requirements.txt"
else
  echo "      libraries unavailable locally; handler falls back to the standard library"
fi

echo "[4/4] Assembling deployment archive ..."
python - "$PKG_DIR" "$ZIP_FILE" <<'PY'
import os
import sys
import zipfile

src, dst = sys.argv[1], sys.argv[2]
count = 0
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as archive:
    for base, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(files):
            full = os.path.join(base, name)
            rel = os.path.relpath(full, src).replace(os.sep, "/")
            archive.write(full, rel)
            count += 1
print("archive=%s files=%d bytes=%d" % (dst, count, os.path.getsize(dst)))
PY

echo "Done: $ZIP_FILE"
