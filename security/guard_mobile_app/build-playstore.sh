#!/usr/bin/env bash
# Build signed release AAB (Play Console) + APK, copy to a delivery folder.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

OUT_DIR="${PLAY_UPLOAD_DIR:-/home/azureuser/playstore-upload}"
mkdir -p "$OUT_DIR"

echo "Building GuardLink release bundle (AAB) + APK..."
./gradlew bundleRelease assembleRelease

AAB_SRC="$ROOT/app/build/outputs/bundle/release/app-release.aab"
APK_META="$ROOT/app/build/outputs/apk/release/output-metadata.json"

if [[ ! -f "$AAB_SRC" ]]; then
  echo "ERROR: AAB not found at $AAB_SRC" >&2
  exit 1
fi
if [[ ! -f "$APK_META" ]]; then
  echo "ERROR: APK metadata not found at $APK_META" >&2
  exit 1
fi

read -r VERSION_NAME VERSION_CODE APK_NAME < <(python3 - <<'PY' "$APK_META"
import json, sys
meta = json.load(open(sys.argv[1]))
el = meta["elements"][0]
print(el.get("versionName", "?"), el.get("versionCode", "?"), el["outputFile"])
PY
)

APK_SRC="$ROOT/app/build/outputs/apk/release/$APK_NAME"
AAB_DST="$OUT_DIR/guardlink-${VERSION_NAME}-${VERSION_CODE}.aab"
APK_DST="$OUT_DIR/guardlink-${VERSION_NAME}-${VERSION_CODE}.apk"

cp -f "$AAB_SRC" "$AAB_DST"
cp -f "$APK_SRC" "$APK_DST"

# R8 mapping file — upload to Play Console → App bundle explorer / Deobfuscation
MAPPING_SRC="$ROOT/app/build/outputs/mapping/release/mapping.txt"
MAPPING_DST="$OUT_DIR/guardlink-${VERSION_NAME}-${VERSION_CODE}-mapping.txt"
if [[ -f "$MAPPING_SRC" ]]; then
  cp -f "$MAPPING_SRC" "$MAPPING_DST"
else
  echo "WARNING: R8 mapping.txt not found — release may not be minified" >&2
  MAPPING_DST=""
fi

# Confirm targetSdk from APK
AAPT="$(ls /home/azureuser/Android/Sdk/build-tools/*/aapt 2>/dev/null | tail -1 || true)"
TARGET_SDK="?"
if [[ -n "$AAPT" ]]; then
  TARGET_SDK="$("$AAPT" dump badging "$APK_DST" 2>/dev/null | sed -n "s/.*targetSdkVersion='\([0-9]*\)'.*/\1/p" | head -1)"
fi

cat > "$OUT_DIR/PLAY_CONSOLE_UPLOAD.txt" <<EOF
GuardLink Android — Play Console upload package
================================================
Built: $(date -u '+%Y-%m-%d %H:%M:%S') UTC
Application ID: com.berkeleyuae.guardlink
versionName: ${VERSION_NAME}
versionCode: ${VERSION_CODE}
targetSdkVersion: ${TARGET_SDK}

UPLOAD THIS FILE TO PLAY CONSOLE
--------------------------------
${AAB_DST}

(Optional sideload / internal testing APK)
${APK_DST}

R8 deobfuscation mapping (upload with the release)
--------------------------------------------------
${MAPPING_DST:-MISSING — rebuild with minifyEnabled true}

How to upload
-------------
1. Open Google Play Console → GuardLink app
2. Testing (internal/closed) first, then Production → Create new release
3. Upload the .aab file above
4. Attach mapping.txt (Deobfuscation file) if Play asks
5. Paste release notes (see WHATS_NEW.txt)
6. Review and roll out to production

Notes
-----
• Play Console requires .aab (Android App Bundle), not .apk
• versionCode must be higher than the last uploaded build (${VERSION_CODE})
• Google requires targetSdk 36 (Android 16) — this build targets ${TARGET_SDK}
• This build enables R8 minify + resource shrink for Play App optimization score
EOF

cat > "$OUT_DIR/WHATS_NEW.txt" <<EOF
• Fewer login errors — native polls no longer hit rate limits
• Background radio delivery improved (no duplicate polling)
• App size and performance optimized (R8 code shrinking)
EOF

echo ""
echo "Ready for Play Console:"
echo "  AAB: $AAB_DST"
echo "  APK: $APK_DST"
echo "  Mapping: ${MAPPING_DST:-MISSING}"
echo "  versionName=$VERSION_NAME versionCode=$VERSION_CODE targetSdk=$TARGET_SDK"
ls -lh "$AAB_DST" "$APK_DST"
[[ -n "${MAPPING_DST}" && -f "${MAPPING_DST}" ]] && ls -lh "$MAPPING_DST"
