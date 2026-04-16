#!/usr/bin/env bash
# Run from the sales/ directory (same folder as docker-compose.yml).
# Compares __manifest__.py on the HOST vs inside odoo_sales.
set -euo pipefail
cd "$(dirname "$0")/.."
HOST_MF="custom_addons/sales_bid_board/__manifest__.py"
if [[ ! -f "$HOST_MF" ]]; then
  echo "ERROR: $HOST_MF not found. Are you in the repo that contains sales_bid_board?"
  exit 1
fi
echo "=== HOST (this directory: $(pwd)) ==="
grep '"version"' "$HOST_MF" || true
echo ""
echo "=== INSIDE odoo_sales container (/mnt/extra-addons) ==="
if command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
elif docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=()
fi
if [[ ${#DC[@]} -gt 0 ]] && "${DC[@]}" exec -T odoo_sales sh -c "grep '\"version\"' /mnt/extra-addons/sales_bid_board/__manifest__.py" 2>/dev/null; then
  :
elif docker exec odoo_sales sh -c "grep '\"version\"' /mnt/extra-addons/sales_bid_board/__manifest__.py" 2>/dev/null; then
  :
else
  echo "ERROR: could not read manifest in container (odoo_sales not running or path missing). Try: docker exec odoo_sales grep version /mnt/extra-addons/sales_bid_board/__manifest__.py"
fi
