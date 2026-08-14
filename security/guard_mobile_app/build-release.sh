#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "Building GuardLink release APK..."
./gradlew assembleRelease

APK_DIR="$ROOT/app/build/outputs/apk/release"
META_FILE="$APK_DIR/output-metadata.json"

if [[ ! -f "$META_FILE" ]]; then
  echo "ERROR: Build metadata not found at $META_FILE" >&2
  exit 1
fi

APK_FILE="$APK_DIR/$(python3 - <<'PY' "$META_FILE"
import json, sys
meta = json.load(open(sys.argv[1]))
print(meta["elements"][0]["outputFile"])
PY
)"

if [[ ! -f "$APK_FILE" ]]; then
  echo "ERROR: Expected APK not found at $APK_FILE" >&2
  exit 1
fi

echo ""
echo "Release APK ready:"
echo "  $APK_FILE"
python3 - <<'PY' "$META_FILE"
import json, sys
meta = json.load(open(sys.argv[1]))
el = meta.get("elements", [{}])[0]
print(f"  versionName: {el.get('versionName', '?')}")
print(f"  versionCode: {el.get('versionCode', '?')}")
PY
ls -lh "$APK_FILE"
