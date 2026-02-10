#!/usr/bin/env python3
"""
Script to create Odoo database via web API
"""
import requests
import time
import sys

ODOO_URL = "http://localhost:8069"
MASTER_PASSWORD = "admin123"
DB_NAME = "security"
ODOO_USER = "ranjith.krishnan@berkeleyuae.com"
ODOO_PASSWORD = "Alacrity99$"

def wait_for_odoo(max_attempts=30):
    """Wait for Odoo to be ready"""
    print("Waiting for Odoo to be ready...")
    for i in range(max_attempts):
        try:
            response = requests.get(f"{ODOO_URL}/web/database/manager", timeout=5)
            if response.status_code == 200:
                print("✓ Odoo is ready!")
                return True
        except Exception as e:
            pass
        time.sleep(2)
        if i % 5 == 0:
            print(f"Attempt {i+1}/{max_attempts}...")
    return False

def create_database():
    """Create the security database"""
    if not wait_for_odoo():
        print("ERROR: Odoo is not ready. Please start Odoo first.")
        return False
    
    print(f"\nCreating database '{DB_NAME}'...")
    
    # Create database via Odoo's database manager
    data = {
        'master_pwd': MASTER_PASSWORD,
        'name': DB_NAME,
        'login': 'admin',
        'password': 'admin',
        'phone': '',
        'email': 'admin@example.com',
        'lang': 'en_US',
        'country_code': '',
        'demo': False,
    }
    
    try:
        response = requests.post(
            f"{ODOO_URL}/web/database/create",
            data=data,
            timeout=120,
            allow_redirects=False
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.status_code in [200, 303, 302]:
            print(f"✓ Database '{DB_NAME}' created successfully!")
            return True
        else:
            print(f"Response text: {response.text[:500]}")
            # Check if database already exists
            if "already exists" in response.text.lower() or response.status_code == 200:
                print("Database might already exist, continuing...")
                return True
            return False
    except Exception as e:
        print(f"ERROR: Exception while creating database: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_user():
    """Create user via XML-RPC"""
    try:
        import xmlrpc.client
        
        print(f"\nCreating user '{ODOO_USER}' via XML-RPC...")
        
        # Connect to Odoo
        common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
        models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
        
        # Authenticate as admin
        uid = common.authenticate(DB_NAME, 'admin', 'admin', {})
        if not uid:
            print("ERROR: Could not authenticate as admin")
            return False
        
        print(f"Authenticated as admin (UID: {uid})")
        
        # Check if user exists
        user_ids = models.execute_kw(
            DB_NAME, uid, 'admin',
            'res.users', 'search',
            [[['login', '=', ODOO_USER]]]
        )
        
        if user_ids:
            print(f"User '{ODOO_USER}' already exists. Updating password...")
            models.execute_kw(
                DB_NAME, uid, 'admin',
                'res.users', 'write',
                [user_ids, {'password': ODOO_PASSWORD}]
            )
            print("✓ Password updated!")
        else:
            # Get admin group
            admin_group_id = models.execute_kw(
                DB_NAME, uid, 'admin',
                'res.groups', 'search',
                [[['full_name', '=', 'Settings / Administration']]]
            )
            
            user_group_id = models.execute_kw(
                DB_NAME, uid, 'admin',
                'res.groups', 'search',
                [[['full_name', '=', 'Internal User']]]
            )
            
            groups = []
            if admin_group_id:
                groups.append(admin_group_id[0])
            if user_group_id:
                groups.append(user_group_id[0])
            
            # Create user
            user_id = models.execute_kw(
                DB_NAME, uid, 'admin',
                'res.users', 'create',
                [{
                    'name': 'Ranjith Krishnan',
                    'login': ODOO_USER,
                    'password': ODOO_PASSWORD,
                    'groups_id': [(6, 0, groups)]
                }]
            )
            print(f"✓ User '{ODOO_USER}' created successfully! (ID: {user_id})")
        
        return True
        
    except Exception as e:
        print(f"ERROR creating user: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Creating 'security' database with user")
    print("=" * 50)
    
    # Create database
    db_created = create_database()
    
    if db_created:
        # Wait a bit for database to be ready
        print("\nWaiting for database to be ready...")
        time.sleep(10)
        
        # Create user
        user_created = create_user()
        
        if user_created:
            print("\n" + "=" * 50)
            print("SUCCESS! Database setup completed")
            print("=" * 50)
            print(f"Database: {DB_NAME}")
            print(f"Master password: {MASTER_PASSWORD}")
            print(f"Odoo User: {ODOO_USER}")
            print(f"Odoo Password: {ODOO_PASSWORD}")
            print("=" * 50)
            sys.exit(0)
        else:
            print("\nDatabase created but user creation failed")
            sys.exit(1)
    else:
        print("\nDatabase creation failed")
        sys.exit(1)







