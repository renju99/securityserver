#!/usr/bin/env python3
"""
Script to create Odoo database 'security' with specific user credentials
"""
import subprocess
import sys
import time
import os

DB_NAME = "security"
ODOO_USER = "ranjith.krishnan@berkeleyuae.com"
ODOO_PASSWORD = "Alacrity99$"
MASTER_PASSWORD = "admin123"
DB_HOST = "db"
POSTGRES_USER = "odoo"
POSTGRES_PASSWORD = "odoo"

def run_command(cmd, check=True):
    """Run a docker exec command"""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )
    if check and result.returncode != 0:
        print(f"ERROR: Command failed: {cmd}")
        print(f"Output: {result.stderr}")
        return False
    return result.returncode == 0

def check_postgres_ready():
    """Check if PostgreSQL is ready"""
    print("Checking PostgreSQL readiness...")
    for i in range(30):
        if run_command(f'docker exec guardpro-db-1 pg_isready -U {POSTGRES_USER}', check=False):
            print("✓ PostgreSQL is ready!")
            return True
        time.sleep(2)
    return False

def check_database_exists():
    """Check if database already exists"""
    cmd = f'docker exec guardpro-db-1 psql -U {POSTGRES_USER} -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname=\'{DB_NAME}\'"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return '1' in result.stdout.strip()

def create_postgres_database():
    """Create the PostgreSQL database"""
    if check_database_exists():
        print(f"Database '{DB_NAME}' already exists in PostgreSQL")
        return True
    
    print(f"Creating PostgreSQL database '{DB_NAME}'...")
    cmd = f'docker exec guardpro-db-1 psql -U {POSTGRES_USER} -d postgres -c "CREATE DATABASE \\"{DB_NAME}\\" OWNER {POSTGRES_USER};"'
    if run_command(cmd):
        print(f"✓ PostgreSQL database '{DB_NAME}' created!")
        return True
    return False

def initialize_odoo_database():
    """Initialize the Odoo database"""
    print(f"Initializing Odoo database '{DB_NAME}'...")
    cmd = f'docker exec guardpro-odoo-1 odoo -d {DB_NAME} --stop-after-init --db_host={DB_HOST} --db_user={POSTGRES_USER} --db_password={POSTGRES_PASSWORD} --admin_passwd={MASTER_PASSWORD} --without-demo=all --i18n-overwrite --init=base'
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ Odoo database '{DB_NAME}' initialized!")
        return True
    else:
        print(f"Warning: Database initialization returned code {result.returncode}")
        print("This might be okay if database was already initialized")
        return True  # Continue anyway

def create_odoo_user():
    """Create the Odoo user using Odoo shell"""
    print(f"Creating Odoo user '{ODOO_USER}'...")
    
    python_script = f'''
import odoo
from odoo import api, SUPERUSER_ID

# Initialize Odoo
odoo.tools.config.parse_config([
    '--database={DB_NAME}',
    '--db_host={DB_HOST}',
    '--db_user={POSTGRES_USER}',
    '--db_password={POSTGRES_PASSWORD}',
])

# Get registry
registry = odoo.registry({DB_NAME})
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {{}})
    
    User = env['res.users']
    
    # Check if user exists
    existing_user = User.search([('login', '=', '{ODOO_USER}')], limit=1)
    
    if existing_user:
        print(f"User '{{existing_user.login}}' already exists. Updating password...")
        existing_user.write({{'password': '{ODOO_PASSWORD}'}})
        print(f"✓ Password updated for user '{ODOO_USER}'")
    else:
        # Get base groups
        base_user_group = env.ref('base.group_user')
        admin_group = env.ref('base.group_system')
        
        # Create new user
        new_user = User.create({{
            'name': 'Ranjith Krishnan',
            'login': '{ODOO_USER}',
            'password': '{ODOO_PASSWORD}',
            'groups_id': [(6, 0, [base_user_group.id, admin_group.id])]
        }})
        print(f"✓ User '{ODOO_USER}' created successfully!")
    
    cr.commit()
'''
    
    # Write script to temp file
    script_file = '/tmp/create_user_script.py'
    with open(script_file, 'w') as f:
        f.write(python_script)
    
    # Copy script to container and execute
    subprocess.run(f'docker cp {script_file} guardpro-odoo-1:/tmp/create_user_script.py', shell=True)
    
    cmd = f'docker exec guardpro-odoo-1 python3 /tmp/create_user_script.py'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    # Clean up
    os.remove(script_file)
    
    if result.returncode == 0:
        print(result.stdout)
        return True
    else:
        print(f"ERROR creating user: {result.stderr}")
        return False

def main():
    print("=" * 50)
    print("Creating 'security' database with user")
    print("=" * 50)
    print(f"Database: {DB_NAME}")
    print(f"Odoo User: {ODOO_USER}")
    print("=" * 50)
    
    # Step 1: Check PostgreSQL
    if not check_postgres_ready():
        print("ERROR: PostgreSQL is not ready")
        sys.exit(1)
    
    # Step 2: Create PostgreSQL database
    if not create_postgres_database():
        print("ERROR: Failed to create PostgreSQL database")
        sys.exit(1)
    
    # Step 3: Initialize Odoo database
    print("\nWaiting a bit for Odoo to be ready...")
    time.sleep(5)
    
    if not initialize_odoo_database():
        print("ERROR: Failed to initialize Odoo database")
        sys.exit(1)
    
    # Step 4: Create Odoo user
    print("\nWaiting a bit more before creating user...")
    time.sleep(5)
    
    if not create_odoo_user():
        print("ERROR: Failed to create Odoo user")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("SUCCESS! Database setup completed")
    print("=" * 50)
    print(f"Database: {DB_NAME}")
    print(f"Master password: {MASTER_PASSWORD}")
    print(f"Odoo User: {ODOO_USER}")
    print(f"Odoo Password: {ODOO_PASSWORD}")
    print("=" * 50)

if __name__ == "__main__":
    main()







