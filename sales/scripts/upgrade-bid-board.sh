#!/usr/bin/env bash
# Run from the sales/ directory (same folder as docker-compose.yml).
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v docker-compose >/dev/null 2>&1; then
  docker-compose --profile tools run --rm odoo_upgrade_bid_board
  docker-compose restart odoo_sales
else
  docker compose --profile tools run --rm odoo_upgrade_bid_board
  docker compose restart odoo_sales
fi
echo "Upgrade finished. In Odoo Apps → Update Apps List (developer mode), Sales Bid Board should show 18.0.2.0.0."
