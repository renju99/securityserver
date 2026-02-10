#!/bin/bash
set -e

DB_NAME="security"
ODOO_USER="ranjith.krishnan@berkeleyuae.com"
ODOO_PASSWORD="Alacrity99$"
MASTER_PASSWORD="admin123"
DB_HOST="db"
DB_PORT="5432"
POSTGRES_USER="odoo"
POSTGRES_PASSWORD="odoo"

echo "========================================="
echo "Creating 'security' database"
echo "========================================="
echo "Database: $DB_NAME"
echo "Odoo User: $ODOO_USER"
echo "========================================="

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until docker exec guardpro-db-1 pg_isready -U $POSTGRES_USER -h localhost > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo "PostgreSQL is ready!"

# Create the database in PostgreSQL if it doesn't exist
echo "Creating PostgreSQL database '$DB_NAME'..."
docker exec guardpro-db-1 psql -U $POSTGRES_USER -d postgres -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
docker exec guardpro-db-1 psql -U $POSTGRES_USER -d postgres -c "CREATE DATABASE \"$DB_NAME\" OWNER $POSTGRES_USER;"

if [ $? -eq 0 ]; then
    echo "✓ PostgreSQL database '$DB_NAME' created successfully!"
else
    echo "Database might already exist, continuing..."
fi

# Wait for Odoo to be ready
echo "Waiting for Odoo to be ready..."
sleep 10

# Initialize the Odoo database with the specified user
echo "Initializing Odoo database with user credentials..."
docker exec guardpro-odoo-1 odoo -d $DB_NAME --stop-after-init \
    --db_host=$DB_HOST \
    --db_user=$POSTGRES_USER \
    --db_password=$POSTGRES_PASSWORD \
    --admin_passwd=$MASTER_PASSWORD \
    --without-demo=all \
    --i18n-overwrite \
    --init=base

if [ $? -eq 0 ]; then
    echo "✓ Odoo database initialized successfully!"
    
    # Now create the Odoo user with the specified credentials
    echo "Creating Odoo user '$ODOO_USER'..."
    docker exec guardpro-odoo-1 odoo shell -d $DB_NAME --db_host=$DB_HOST --db_user=$POSTGRES_USER --db_password=$POSTGRES_PASSWORD << EOF
import odoo
from odoo import api, SUPERUSER_ID

env = api.Environment(odoo.registry($DB_NAME).cursor(), SUPERUSER_ID, {})

# Check if user already exists
User = env['res.users']
existing_user = User.search([('login', '=', '$ODOO_USER')], limit=1)

if existing_user:
    print(f"User '$ODOO_USER' already exists. Updating password...")
    existing_user.write({'password': '$ODOO_PASSWORD'})
    print(f"✓ Password updated for user '$ODOO_USER'")
else:
    # Create new user
    # First, ensure admin user exists and get its partner
    admin_user = User.search([('login', '=', 'admin')], limit=1)
    if not admin_user:
        admin_user = User.create({
            'name': 'Administrator',
            'login': 'admin',
            'password': 'admin',
            'groups_id': [(6, 0, [env.ref('base.group_system').id])]
        })
    
    # Create the new user
    new_user = User.create({
        'name': 'Ranjith Krishnan',
        'login': '$ODOO_USER',
        'password': '$ODOO_PASSWORD',
        'groups_id': [(6, 0, [
            env.ref('base.group_user').id,
            env.ref('base.group_system').id
        ])]
    })
    print(f"✓ User '$ODOO_USER' created successfully!")

env.cr.commit()
EOF

    echo "========================================="
    echo "Database setup completed!"
    echo "========================================="
    echo "Database: $DB_NAME"
    echo "Master password: $MASTER_PASSWORD"
    echo "Odoo User: $ODOO_USER"
    echo "Odoo Password: $ODOO_PASSWORD"
    echo "========================================="
else
    echo "ERROR: Failed to initialize Odoo database"
    exit 1
fi







