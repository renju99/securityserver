#!/bin/bash
# PostgreSQL Configuration Update Script for GuardLink Scalability
# This script updates PostgreSQL max_connections to support 1000-2000 users

set -e

echo "=========================================="
echo "PostgreSQL Configuration Update"
echo "=========================================="
echo ""

# Find PostgreSQL config file
PG_VERSION=$(psql --version | grep -oP '\d+' | head -1)
PG_CONF="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"

if [ ! -f "$PG_CONF" ]; then
    # Try alternative locations
    PG_CONF="/etc/postgresql/postgresql.conf"
    if [ ! -f "$PG_CONF" ]; then
        echo "ERROR: Could not find postgresql.conf"
        echo "Please locate your postgresql.conf file and update manually:"
        echo "  sudo find /etc -name postgresql.conf 2>/dev/null"
        exit 1
    fi
fi

echo "Found PostgreSQL config: $PG_CONF"
echo ""

# Backup original config
BACKUP_FILE="${PG_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
echo "Creating backup: $BACKUP_FILE"
sudo cp "$PG_CONF" "$BACKUP_FILE"
echo "✓ Backup created"
echo ""

# Check current max_connections
CURRENT_MAX=$(sudo -u postgres psql -t -c "SHOW max_connections;" | xargs)
echo "Current max_connections: $CURRENT_MAX"
echo ""

# Update max_connections if needed
if [ "$CURRENT_MAX" -lt 500 ]; then
    echo "Updating max_connections to 500..."
    
    # Check if max_connections is already set in config
    if sudo grep -q "^max_connections" "$PG_CONF"; then
        # Update existing setting
        sudo sed -i "s/^max_connections = .*/max_connections = 500/" "$PG_CONF"
    else
        # Add new setting
        echo "" | sudo tee -a "$PG_CONF" > /dev/null
        echo "# GuardLink Scalability - Updated $(date)" | sudo tee -a "$PG_CONF" > /dev/null
        echo "max_connections = 500" | sudo tee -a "$PG_CONF" > /dev/null
    fi
    
    echo "✓ Configuration updated"
    echo ""
    echo "IMPORTANT: PostgreSQL must be restarted for changes to take effect."
    echo ""
    echo "To restart PostgreSQL, run:"
    echo "  sudo systemctl restart postgresql"
    echo ""
    echo "Or if using different service name:"
    echo "  sudo systemctl restart postgresql@${PG_VERSION}-main"
    echo ""
else
    echo "✓ max_connections is already >= 500, no changes needed"
    echo ""
fi

# Show recommended additional settings
echo "=========================================="
echo "Recommended Additional Settings"
echo "=========================================="
echo ""
echo "For optimal performance with 1000-2000 users, consider adding:"
echo ""
echo "shared_buffers = 4GB              # 25% of total RAM"
echo "effective_cache_size = 12GB       # 75% of total RAM"
echo "maintenance_work_mem = 1GB"
echo "work_mem = 20MB"
echo ""
echo "Add these to: $PG_CONF"
echo ""








