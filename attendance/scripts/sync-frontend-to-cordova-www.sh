#!/usr/bin/env bash
# Build the React (Vite) app and copy it into Cordova mobile/www, preserving native hooks.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONT="$ROOT/frontend"
MOB="$ROOT/mobile"

echo "==> Building web app for Cordova (VITE_BASE=./ file URLs)"
(cd "$FRONT" && VITE_BASE=./ npm run build)

echo "==> Removing old hashed bundles (keeps www/js, www/img, etc.)"
rm -rf "$MOB/www/assets" "$MOB/www/dist"

echo "==> Copying frontend/dist -> mobile/www"
mkdir -p "$MOB/www/js"
cp -a "$FRONT/dist/." "$MOB/www/"

echo "==> Refresh app-native.js from source of truth (mobile/js)"
if [[ -f "$MOB/js/app-native.js" ]]; then
  cp -a "$MOB/js/app-native.js" "$MOB/www/js/app-native.js"
fi

echo "==> Patching index.html for Cordova"
python3 -c "
from pathlib import Path
root = Path('$ROOT')
p = root / 'mobile' / 'www' / 'index.html'
t = p.read_text(encoding='utf-8')
if 'cordova.js' not in t:
    inject = '''  <script src=\"cordova.js\"></script>
  <script src=\"js/socket.io.min.js\"></script>
  <script src=\"js/app-native.js\"></script>
</body>'''
    if '</body>' not in t:
        raise SystemExit('no </body> in index.html')
    t = t.replace('</body>', inject, 1)
    p.write_text(t, encoding='utf-8')
    print('patched index.html for Cordova')
else:
    print('index.html already includes cordova.js')
"

if [[ ! -f "$MOB/www/js/socket.io.min.js" ]]; then
  echo "WARN: $MOB/www/js/socket.io.min.js missing — restore from backup or vendor before release build."
fi

echo "==> Done. Cordova www is in sync with latest frontend build."
echo "    Next: cd mobile && npx cordova build android --release"
