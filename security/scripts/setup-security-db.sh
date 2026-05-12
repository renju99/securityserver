#!/bin/bash
set -e

DB_NAME="security"
ODOO_USER="ranjith.krishnan@berkeleyuae.com"
ODOO_PASSWORD="Alacrity99$"
MASTER_PASSWORD="admin123"
DB_HOST="db"
POSTGRES_USER="odoo"
POSTGRES_PASSWORD="odoo"

# Detect docker command
if command -v sudo &> /dev/null && sudo docker ps &> /dev/null; then
    DOCKER_CMD="sudo docker"
else
    DOCKER_CMD="docker"
fi

DB_CONTAINER=$($DOCKER_CMD ps --filter "name=db" --format "{{.Names}}" | head -n 1)
ODOO_CONTAINER=$($DOCKER_CMD ps --filter "name=odoo-security" --format "{{.Names}}" | head -n 1)

echo "========================================="
echo "Setting up 'security' database"
echo "========================================="
echo "Database: $DB_NAME"
echo "Odoo User: $ODOO_USER"
echo "========================================="

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
until $DOCKER_CMD exec $DB_CONTAINER pg_isready -U $POSTGRES_USER > /dev/null 2>&1; do
    sleep 2
done
echo "✓ PostgreSQL is ready"

# Check if database exists and has tables
echo "Checking database status..."
TABLE_COUNT=$($DOCKER_CMD exec $DB_CONTAINER psql -U $POSTGRES_USER -d $DB_NAME -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo "0")

if [ "$TABLE_COUNT" -gt "0" ]; then
    echo "✓ Database '$DB_NAME' exists and is initialized ($TABLE_COUNT tables)"
    DB_EXISTS=true
else
    echo "Database '$DB_NAME' either doesn't exist or is not initialized"
    
    # Drop database if it exists but is empty
    if $DOCKER_CMD exec $DB_CONTAINER psql -U $POSTGRES_USER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
        echo "Dropping empty database..."
        $DOCKER_CMD exec $DB_CONTAINER psql -U $POSTGRES_USER -d postgres -c "DROP DATABASE \"$DB_NAME\";"
    fi
    
    # Create fresh database
    echo "Creating fresh database..."
    $DOCKER_CMD exec $DB_CONTAINER psql -U $POSTGRES_USER -d postgres -c "CREATE DATABASE \"$DB_NAME\" OWNER $POSTGRES_USER;"
    DB_EXISTS=false
fi

# Initialize database if needed
if [ "$DB_EXISTS" = false ]; then
    echo "Initializing Odoo database (this may take a few minutes)..."
    
    # Stop Odoo temporarily to initialize database
    echo "Stopping Odoo container temporarily..."
    $DOCKER_CMD stop $ODOO_CONTAINER
    
    # Initialize database
    $DOCKER_CMD start $ODOO_CONTAINER
    sleep 5
    
    # Run initialization in a one-off container to avoid port conflicts
    $DOCKER_CMD run --rm \
        --network security_odoo-network \
        -e HOST=$DB_HOST \
        -e USER=$POSTGRES_USER \
        -e PASSWORD=$POSTGRES_PASSWORD \
        -v security_odoo-web-data:/var/lib/odoo \
        -v $(pwd)/custom_addons:/mnt/extra-addons \
        -v $(pwd)/config:/etc/odoo \
        --entrypoint="" \
        $($DOCKER_CMD images --format "{{.Repository}}:{{.Tag}}" | grep odoo | head -n 1) \
        odoo -d $DB_NAME --stop-after-init \
        --config=/etc/odoo/odoo.conf \
        --without-demo=all \
        --init=base
    
    echo "✓ Database initialized"
    
    # Restart Odoo
    echo "Restarting Odoo..."
    $DOCKER_CMD restart $ODOO_CONTAINER
    sleep 10
fi

# Wait for Odoo to be ready
echo "Waiting for Odoo to be ready..."
for i in {1..30}; do
    if $DOCKER_CMD exec $ODOO_CONTAINER curl -s http://localhost:8069/web/health > /dev/null 2>&1; then
        echo "✓ Odoo is ready"
        break
    fi
    sleep 2
done

# Create user
echo "Creating Odoo user..."
$DOCKER_CMD cp scripts/create-user.py $ODOO_CONTAINER:/tmp/create-user.py 2>/dev/null || true
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







