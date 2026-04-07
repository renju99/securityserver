#!/usr/bin/env bash
# Verify guardpro handover is present on disk and in the Odoo registry.
# Usage (from repo security/): ./scripts/verify-equipment-handover.sh [database_name]
# Requires: docker-compose project with service "odoo" running or startable.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DB="${1:-security}"
cd "$ROOT"

echo "==> 1) Source file on container (must show EquipmentHandover class)"
docker-compose exec -T odoo grep -n "class EquipmentHandover" /mnt/extra-addons/guardpro/models/equipment.py

echo "==> 2) Registry check (must print True) — database: $DB"
echo "print('equipment.handover' in env.registry)" | docker-compose exec -T odoo odoo shell -d "$DB" --config=/etc/odoo/odoo.conf --no-http

echo "OK — if step 2 is True, redeploy/restart fixed the 404. If False, run upgrade then restart:"
echo "    docker-compose run --rm odoo odoo -u guardpro -d $DB --stop-after-init --config=/etc/odoo/odoo.conf"
echo "    docker-compose restart odoo"
