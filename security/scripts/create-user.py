#!/usr/bin/env python3
"""
Script to create Odoo user in the security database
"""
import sys
import os

# Add Odoo to path
sys.path.insert(0, '/usr/lib/python3/dist-packages')

import odoo
from odoo import api, SUPERUSER_ID

# Database configuration
DB_NAME = 'security'
DB_HOST = 'db'
DB_USER = 'odoo'
DB_PASSWORD = 'odoo'

# User to create
ODOO_USER = 'ranjith.krishnan@berkeleyuae.com'
ODOO_PASSWORD = 'Alacrity99$'

def main():
    print(f"Connecting to database '{DB_NAME}'...")
    
    # Configure Odoo
    odoo.tools.config.parse_config([
        f'--database={DB_NAME}',
        f'--db_host={DB_HOST}',
        f'--db_user={DB_USER}',
        f'--db_password={DB_PASSWORD}',
    ])
    
    try:
        # Get registry
        registry = odoo.registry(DB_NAME)
        print("Registry obtained successfully")
        
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            User = env['res.users']
            
            print(f"Checking for user '{ODOO_USER}'...")
            
            # Check if user exists
            existing_user = User.search([('login', '=', ODOO_USER)], limit=1)
            
            if existing_user:
                print(f"User '{ODOO_USER}' already exists. Updating password...")
                existing_user.write({'password': ODOO_PASSWORD})
                print(f"✓ Password updated successfully!")
            else:
                print(f"Creating new user '{ODOO_USER}'...")
                
                # Get groups
                try:
                    base_group = env.ref('base.group_user')
                    admin_group = env.ref('base.group_system')
                    groups = [base_group.id, admin_group.id]
                except:
                    # Fallback: get all groups if refs fail
                    groups = env['res.groups'].search([]).ids
                
                # Create user
                new_user = User.create({
                    'name': 'Ranjith Krishnan',
                    'login': ODOO_USER,
                    'password': ODOO_PASSWORD,
                    'groups_id': [(6, 0, groups)]
                })
                print(f"✓ User '{ODOO_USER}' created successfully!")
                print(f"  User ID: {new_user.id}")
            
            cr.commit()
            print("✓ Changes committed to database")
            return True
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)







