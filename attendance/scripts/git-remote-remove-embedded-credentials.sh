#!/usr/bin/env bash
# If origin uses https://TOKEN_OR_USER:SECRET@host/..., rewrite to https://host/...
# so the secret is not stored in .git/config. Use SSH or a credential helper for auth.
set -euo pipefail
url="$(git remote get-url origin 2>/dev/null || true)"
if [[ -z "$url" ]]; then
  echo "No origin remote."
  exit 0
fi
if [[ "$url" =~ ^https://[^/@]+@[^/]+/ ]]; then
  clean="$(printf '%s' "$url" | sed -E 's#^https://[^@]+@#https://#')"
  echo "Rewriting origin URL (removed embedded credentials)."
  echo "  Before: (redacted — was https://…@host/…)"
  git remote set-url origin "$clean"
  echo "  After:  $clean"
  echo "Use: gh auth login, git credential-store, or SSH (git@github.com:org/repo.git)."
else
  echo "Origin URL has no embedded https credentials; no change."
fi
