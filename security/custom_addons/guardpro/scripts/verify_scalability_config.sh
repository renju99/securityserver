#!/bin/bash
# Verification Script for GuardPro Scalability Configuration

echo "=========================================="
echo "GuardPro Scalability Configuration Check"
echo "=========================================="
echo ""

# Check Odoo configuration
echo "1. Checking odoo.conf..."
ODOO_CONF="/home/ranjith/odoo/odoo.conf"

if [ -f "$ODOO_CONF" ]; then
    WORKERS=$(grep "^workers" "$ODOO_CONF" | grep -oP '\d+' || echo "0")
    DB_MAXCONN=$(grep "^db_maxconn" "$ODOO_CONF" | grep -oP '\d+' || echo "not set")
    
    echo "   Workers: $WORKERS"
    if [ "$WORKERS" -ge 8 ]; then
        echo "   ✓ Workers configured correctly (>= 8)"
    else
        echo "   ✗ WARNING: Workers should be >= 8 for 1000-2000 users"
    fi
    
    echo "   DB Max Connections: $DB_MAXCONN"
    if [ "$DB_MAXCONN" != "not set" ] && [ "$DB_MAXCONN" -ge 400 ]; then
        echo "   ✓ Database connection pool configured correctly (>= 400)"
    else
        echo "   ✗ WARNING: db_maxconn should be >= 400"
    fi
else
    echo "   ✗ ERROR: odoo.conf not found at $ODOO_CONF"
fi
echo ""

# Check PostgreSQL configuration
echo "2. Checking PostgreSQL configuration..."
CURRENT_MAX=$(sudo -u postgres psql -t -c "SHOW max_connections;" 2>/dev/null | xargs || echo "unknown")

if [ "$CURRENT_MAX" != "unknown" ]; then
    echo "   Current max_connections: $CURRENT_MAX"
    if [ "$CURRENT_MAX" -ge 500 ]; then
        echo "   ✓ PostgreSQL max_connections is sufficient (>= 500)"
    else
        echo "   ✗ WARNING: PostgreSQL max_connections should be >= 500"
        echo "   Run: /home/ranjith/odoo/custom_addons/guardpro/scripts/update_postgresql_config.sh"
    fi
else
    echo "   ✗ Could not check PostgreSQL configuration (may need sudo access)"
fi
echo ""

# Check Odoo processes
echo "3. Checking Odoo worker processes..."
ODOO_PROCESSES=$(ps aux | grep -c "[o]doo-bin" || echo "0")
echo "   Running Odoo processes: $ODOO_PROCESSES"
if [ "$ODOO_PROCESSES" -ge 2 ]; then
    echo "   ✓ Multiple processes detected (likely workers are running)"
else
    echo "   ⚠ NOTE: Only 1 process detected. Workers may not be active yet."
    echo "   Restart Odoo to activate worker configuration."
fi
echo ""

# Check database connections
echo "4. Checking current database connections..."
if command -v psql &> /dev/null; then
    ACTIVE_CONN=$(sudo -u postgres psql -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'security';" 2>/dev/null | xargs || echo "unknown")
    if [ "$ACTIVE_CONN" != "unknown" ]; then
        echo "   Active connections to 'security' database: $ACTIVE_CONN"
        if [ "$ACTIVE_CONN" -lt 50 ]; then
            echo "   ✓ Connection count is low (normal for current load)"
        else
            echo "   ⚠ High connection count - monitor closely"
        fi
    else
        echo "   Could not check active connections"
    fi
else
    echo "   psql not found in PATH"
fi
echo ""

# Summary
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "Configuration Status:"
if [ "$WORKERS" -ge 8 ] && [ "$DB_MAXCONN" != "not set" ] && [ "$DB_MAXCONN" -ge 400 ] && [ "$CURRENT_MAX" != "unknown" ] && [ "$CURRENT_MAX" -ge 500 ]; then
    echo "✓ All critical configurations are set correctly!"
    echo ""
    echo "Next steps:"
    echo "1. Restart Odoo to apply worker configuration"
    echo "2. Monitor system performance under load"
    echo "3. Check logs for any connection pool errors"
else
    echo "⚠ Some configurations need attention. See warnings above."
    echo ""
    echo "To fix:"
    echo "1. Ensure odoo.conf has workers >= 8 and db_maxconn >= 400"
    echo "2. Run PostgreSQL update script if max_connections < 500"
    echo "3. Restart both PostgreSQL and Odoo"
fi
echo ""








