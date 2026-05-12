#!/bin/bash
set -e

DB_NAME="security"
ODOO_USER="ranjith.krishnan@berkeleyuae.com"
ODOO_PASSWORD="Alacrity99$"
MASTER_PASSWORD="admin123"
DB_HOST="db"
POSTGRES_USER="odoo"
POSTGRES_PASSWORD="odoo"

echo "========================================="
echo "Creating 'security' database"
echo "========================================="
echo "Database: $DB_NAME"
echo "Odoo User: $ODOO_USER"
echo "========================================="

# Get container names dynamically (try with sudo first, then without)
if command -v sudo &> /dev/null && sudo docker ps &> /dev/null; then
    DOCKER_CMD="sudo docker"
else
    DOCKER_CMD="docker"
fi

DB_CONTAINER=$($DOCKER_CMD ps --filter "name=db" --format "{{.Names}}" | head -n 1)
ODOO_CONTAINER=$($DOCKER_CMD ps --filter "name=odoo-security" --format "{{.Names}}" | head -n 1)

if [ -z "$DB_CONTAINER" ] || [ -z "$ODOO_CONTAINER" ]; then
    echo "ERROR: Could not find database or Odoo containers"
    echo "DB Container: $DB_CONTAINER"
    echo "Odoo Container: $ODOO_CONTAINER"
    exit 1
fi

echo "Using containers:"
echo "  DB: $DB_CONTAINER"
echo "  Odoo: $ODOO_CONTAINER"

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
until $DOCKER_CMD exec $DB_CONTAINER pg_isready -U $POSTGRES_USER > /dev/null 2>&1; do
    sleep 2
done
echo "✓ PostgreSQL is ready"

# Create database if it doesn't exist
echo "Creating PostgreSQL database..."
$DOCKER_CMD exec $DB_CONTAINER psql -U $POSTGRES_USER -d postgres -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
$DOCKER_CMD exec $DB_CONTAINER psql -U $POSTGRES_USER -d postgres -c "CREATE DATABASE \"$DB_NAME\" OWNER $POSTGRES_USER;" || \
echo "Database might already exist"

# Initialize Odoo database (using config file for admin password)
echo "Initializing Odoo database..."
$DOCKER_CMD exec $ODOO_CONTAINER odoo -d $DB_NAME --stop-after-init \
    --config=/etc/odoo/odoo.conf \
    --without-demo=all \
    --init=base || echo "Database initialization completed (or already initialized)"

# Wait a bit for database to be fully ready
sleep 3

# Copy and run the user creation script
echo "Creating Odoo user..."
$DOCKER_CMD cp scripts/create-user.py $ODOO_CONTAINER:/tmp/create-user.py
$DOCKER_CMD exec $ODOO_CONTAINER python3 /tmp/create-user.py

echo ""
echo "========================================="
echo "Database setup completed!"
echo "========================================="
echo "Database: $DB_NAME"
echo "Master password: $MASTER_PASSWORD"
echo "Odoo User: $ODOO_USER"
echo "Odoo Password: $ODOO_PASSWORD"
echo "========================================="

