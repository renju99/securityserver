#!/usr/bin/env python3
"""
Script to create Odoo database 'security' with master password
"""
import requests
import time
import sys

ODOO_URL = "http://localhost:8069"
MASTER_PASSWORD = "admin123"
DB_NAME = "security"
DB_USER = "admin"
DB_PASSWORD = "admin"
LANGUAGE = "en_US"

def wait_for_odoo(max_attempts=30):
    """Wait for Odoo to be ready"""
    print("Waiting for Odoo to be ready...")
    for i in range(max_attempts):
        try:
            response = requests.get(f"{ODOO_URL}/web/database/manager", timeout=5)
            if response.status_code == 200:
                print("Odoo is ready!")
                return True
        except:
            pass
        time.sleep(2)
        print(f"Attempt {i+1}/{max_attempts}...")
    return False

def create_database():
    """Create the security database"""
    if not wait_for_odoo():
        print("ERROR: Odoo is not ready. Please start Odoo first.")
        sys.exit(1)
    
    print(f"\nCreating database '{DB_NAME}'...")
    
    # Create database via Odoo's database manager
    data = {
        'master_pwd': MASTER_PASSWORD,
        'name': DB_NAME,
        'login': DB_USER,
        'password': DB_PASSWORD,
        'phone': '',
        'email': 'admin@example.com',
        'lang': LANGUAGE,
        'country_code': '',
        'demo': False,
    }
    
    try:
        response = requests.post(
            f"{ODOO_URL}/web/database/create",
            data=data,
            timeout=60
        )
        
        if response.status_code == 200:
            print(f"✓ Database '{DB_NAME}' created successfully!")
            print(f"  Master password: {MASTER_PASSWORD}")
            print(f"  Admin user: {DB_USER}")
            print(f"  Admin password: {DB_PASSWORD}")
            return True
        else:
            print(f"ERROR: Failed to create database. Status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"ERROR: Exception while creating database: {e}")
        return False

if __name__ == "__main__":
    success = create_database()
    sys.exit(0 if success else 1)






