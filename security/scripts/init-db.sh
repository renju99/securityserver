#!/bin/bash
set -e

DB_NAME="security"
ODOO_USER="ranjith.krishnan@berkeleyuae.com"
ODOO_PASSWORD="Alacrity99$"
MASTER_PASSWORD="admin123"

echo "========================================="
echo "Initializing 'security' database"
echo "========================================="

cd "$(dirname "$0")/.."

# Check if database exists and is initialized
DB_CONTAINER=$(docker ps --filter "name=db" --format "{{.Names}}" | head -n 1)
if [ -z "$DB_CONTAINER" ]; then
    DB_CONTAINER=$(sudo docker ps --filter "name=db" --format "{{.Names}}" | head -n 1)
    DOCKER_CMD="sudo docker"
else
    DOCKER_CMD="docker"
fi

TABLE_COUNT=$($DOCKER_CMD exec $DB_CONTAINER psql -U odoo -d $DB_NAME -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo "0")

if [ "$TABLE_COUNT" -gt "10" ]; then
    echo "✓ Database is already initialized ($TABLE_COUNT tables)"
else
    echo "Database needs initialization..."
    
    # Drop and recreate if empty
    if [ "$TABLE_COUNT" = "0" ]; then
        echo "Stopping Odoo to drop empty database..."
        ODOO_CONTAINER=$(docker ps --filter "name=odoo" --format "{{.Names}}" | head -n 1)
        if [ -z "$ODOO_CONTAINER" ]; then
            ODOO_CONTAINER=$(sudo docker ps --filter "name=odoo" --format "{{.Names}}" | head -n 1)
        fi
        if [ -n "$ODOO_CONTAINER" ]; then
            $DOCKER_CMD stop $ODOO_CONTAINER
            sleep 3
        fi
        
        echo "Dropping empty database..."
        $DOCKER_CMD exec $DB_CONTAINER psql -U odoo -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" || true
        sleep 2
        $DOCKER_CMD exec $DB_CONTAINER psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" || true
        $DOCKER_CMD exec $DB_CONTAINER psql -U odoo -d postgres -c "CREATE DATABASE \"$DB_NAME\" OWNER odoo;"
        
        # Restart Odoo after initialization
        RESTART_ODOO=true
    else
        RESTART_ODOO=false
    fi
    
    # Use docker-compose run to create a one-off container for initialization
    echo "Initializing database (this may take 2-3 minutes)..."
    cd "$(dirname "$0")/.."
    docker-compose run --rm --no-deps \
        -e HOST=db \
        -e USER=odoo \
        -e PASSWORD=odoo \
        odoo odoo -d $DB_NAME --stop-after-init \
        --config=/etc/odoo/odoo.conf \
        --without-demo=all \
        --init=base || {
        echo "Trying alternative initialization method..."
        # Alternative: use existing image
        ODOO_IMAGE=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep odoo | head -n 1)
        docker run --rm \
            --network security_odoo-network \
            -e HOST=db \
            -e USER=odoo \
            -e PASSWORD=odoo \
            -v security_odoo-web-data:/var/lib/odoo \
            -v $(pwd)/custom_addons:/mnt/extra-addons \
            -v $(pwd)/config:/etc/odoo \
            $ODOO_IMAGE odoo -d $DB_NAME --stop-after-init \
            --config=/etc/odoo/odoo.conf \
            --without-demo=all \
            --init=base
    }
    
    echo "✓ Database initialized"
    
    # Restart Odoo if we stopped it
    if [ "$RESTART_ODOO" = true ] && [ -n "$ODOO_CONTAINER" ]; then
        echo "Restarting Odoo..."
        $DOCKER_CMD start $ODOO_CONTAINER
        sleep 10
    fi
fi

# Wait for Odoo to be ready
echo "Waiting for Odoo..."
sleep 5

# Create user
echo "Creating user '$ODOO_USER'..."
$DOCKER_CMD cp scripts/create-user.py $(docker ps --filter "name=odoo" --format "{{.Names}}" | head -n 1):/tmp/create-user.py
$DOCKER_CMD exec $(docker ps --filter "name=odoo" --format "{{.Names}}" | head -n 1) python3 /tmp/create-user.py

echo ""
echo "========================================="
echo "Setup completed!"
echo "========================================="
echo "Database: $DB_NAME"
echo "Master password: $MASTER_PASSWORD"
echo "User: $ODOO_USER"
echo "Password: $ODOO_PASSWORD"
echo "========================================="

