#!/bin/bash
# GuardPro Docker Production Deployment Script
# This script automates the deployment process after code push

set -e

echo "=========================================="
echo "GuardPro Docker Production Deployment"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration - UPDATE THESE FOR YOUR ENVIRONMENT
ODOO_CONTAINER="odoo"  # Update with your Odoo container name
POSTGRES_CONTAINER="postgres"  # Update with your PostgreSQL container name
DB_NAME="security"  # Update with your database name
DB_USER="odoo"  # Update with your database user
PROJECT_DIR="/path/to/odoo-project"  # Update with your project directory

# Functions
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}ERROR: $1 is not installed${NC}"
        exit 1
    fi
}

check_container() {
    if ! docker ps --format '{{.Names}}' | grep -q "^${1}$"; then
        echo -e "${RED}ERROR: Container '$1' is not running${NC}"
        exit 1
    fi
}

# Pre-flight checks
echo "1. Running pre-flight checks..."
check_command docker
check_command git
check_container $ODOO_CONTAINER
check_container $POSTGRES_CONTAINER
echo -e "${GREEN}✓ Pre-flight checks passed${NC}"
echo ""

# Step 1: Pull latest code
echo "2. Pulling latest code..."
cd "$PROJECT_DIR" || exit 1
git pull origin main || git pull origin master
echo -e "${GREEN}✓ Code updated${NC}"
echo ""

# Step 2: Verify odoo.conf has scalability settings
echo "3. Verifying odoo.conf configuration..."
if docker exec $ODOO_CONTAINER test -f /etc/odoo/odoo.conf; then
    WORKERS=$(docker exec $ODOO_CONTAINER grep "^workers" /etc/odoo/odoo.conf | grep -oP '\d+' || echo "0")
    DB_MAXCONN=$(docker exec $ODOO_CONTAINER grep "^db_maxconn" /etc/odoo/odoo.conf | grep -oP '\d+' || echo "not set")
    
    if [ "$WORKERS" -lt 8 ] || [ "$DB_MAXCONN" = "not set" ] || [ "$DB_MAXCONN" -lt 400 ]; then
        echo -e "${YELLOW}WARNING: odoo.conf may need updating${NC}"
        echo "  Current workers: $WORKERS (should be >= 8)"
        echo "  Current db_maxconn: $DB_MAXCONN (should be >= 400)"
        echo ""
        echo "Please update odoo.conf manually and restart containers"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}✓ Configuration verified${NC}"
        echo "  Workers: $WORKERS"
        echo "  DB Max Connections: $DB_MAXCONN"
    fi
else
    echo -e "${YELLOW}WARNING: odoo.conf not found in container${NC}"
    echo "  Configuration may be in docker-compose.yml or environment variables"
fi
echo ""

# Step 3: Check PostgreSQL max_connections
echo "4. Checking PostgreSQL configuration..."
PG_MAXCONN=$(docker exec $POSTGRES_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SHOW max_connections;" 2>/dev/null | xargs || echo "unknown")

if [ "$PG_MAXCONN" != "unknown" ]; then
    echo "  Current max_connections: $PG_MAXCONN"
    if [ "$PG_MAXCONN" -lt 500 ]; then
        echo -e "${YELLOW}WARNING: PostgreSQL max_connections should be >= 500${NC}"
        echo "  Current: $PG_MAXCONN"
        echo "  Please update PostgreSQL configuration (see PRODUCTION_DOCKER_DEPLOYMENT.md)"
    else
        echo -e "${GREEN}✓ PostgreSQL configuration OK${NC}"
    fi
else
    echo -e "${YELLOW}WARNING: Could not check PostgreSQL configuration${NC}"
fi
echo ""

# Step 4: Restart containers (if needed)
echo "5. Restarting containers..."
read -p "Restart Odoo and PostgreSQL containers? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  Stopping containers..."
    docker stop $ODOO_CONTAINER $POSTGRES_CONTAINER 2>/dev/null || true
    
    echo "  Starting PostgreSQL..."
    docker start $POSTGRES_CONTAINER
    sleep 5
    
    echo "  Starting Odoo..."
    docker start $ODOO_CONTAINER
    sleep 5
    
    echo -e "${GREEN}✓ Containers restarted${NC}"
else
    echo "  Skipping container restart"
fi
echo ""

# Step 5: Verify workers
echo "6. Verifying Odoo workers..."
sleep 3
WORKER_COUNT=$(docker exec $ODOO_CONTAINER ps aux | grep -c "[o]doo-bin" || echo "0")
echo "  Worker processes: $WORKER_COUNT"

if [ "$WORKER_COUNT" -ge 9 ]; then
    echo -e "${GREEN}✓ Workers are running correctly (expected: 9+, got: $WORKER_COUNT)${NC}"
elif [ "$WORKER_COUNT" -eq 1 ]; then
    echo -e "${RED}✗ Only 1 process detected - workers may not be configured${NC}"
    echo "  Check odoo.conf has workers = 8"
else
    echo -e "${YELLOW}⚠ Unexpected worker count: $WORKER_COUNT${NC}"
fi
echo ""

# Step 6: Update GuardPro module
echo "7. Updating GuardPro module..."
read -p "Update GuardPro module? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  Running module update..."
    docker exec $ODOO_CONTAINER odoo-bin -c /etc/odoo/odoo.conf -d $DB_NAME -u guardpro --stop-after-init 2>&1 | tail -20
    echo ""
    echo -e "${GREEN}✓ Module update completed${NC}"
    echo ""
    echo "  Note: If Odoo stopped, restart it with:"
    echo "    docker start $ODOO_CONTAINER"
else
    echo "  Skipping module update"
    echo "  Update manually via Odoo web interface: Apps > GuardPro > Upgrade"
fi
echo ""

# Step 7: Final verification
echo "8. Final verification..."
echo "  Checking container status..."
if docker ps --format '{{.Names}}' | grep -q "^${ODOO_CONTAINER}$"; then
    echo -e "${GREEN}✓ Odoo container is running${NC}"
else
    echo -e "${RED}✗ Odoo container is not running${NC}"
fi

if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    echo -e "${GREEN}✓ PostgreSQL container is running${NC}"
else
    echo -e "${RED}✗ PostgreSQL container is not running${NC}"
fi
echo ""

# Summary
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Monitor logs: docker logs -f $ODOO_CONTAINER"
echo "2. Test application access"
echo "3. Verify workers: docker exec $ODOO_CONTAINER ps aux | grep odoo-bin"
echo "4. Check for errors in logs"
echo ""
echo "For detailed instructions, see:"
echo "  PRODUCTION_DOCKER_DEPLOYMENT.md"
echo ""
echo -e "${GREEN}Deployment script completed!${NC}"








