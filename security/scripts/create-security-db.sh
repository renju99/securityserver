#!/bin/bash
set -e

echo "========================================="
echo "Creating 'security' database"
echo "========================================="

# Wait for Odoo to be ready
echo "Waiting for Odoo to be ready..."
sleep 10

# Create the security database
# Using Odoo's database management command
docker exec guardpro-odoo-1 odoo -d security --stop-after-init \
    --db_host=db \
    --db_user=odoo \
    --db_password=odoo \
    --admin_passwd=admin123 \
    --without-demo=all \
    --i18n-overwrite \
    --init=base || echo "Database might already exist or Odoo is not ready yet"

echo "========================================="
echo "Database 'security' creation attempted"
echo "Master password: admin123"
echo "========================================="






