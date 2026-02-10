#!/bin/bash
set -e

# This script will be called after Odoo starts to create the database
echo "Initializing security database..."

# Wait a bit for Odoo to fully start
sleep 15

# Check if database exists, if not create it
python3 << EOF
import psycopg2
import sys

try:
    conn = psycopg2.connect(
        host="db",
        database="postgres",
        user="odoo",
        password="odoo"
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Check if security database exists
    cursor.execute("SELECT 1 FROM pg_database WHERE datname='security'")
    exists = cursor.fetchone()
    
    if not exists:
        print("Creating 'security' database...")
        cursor.execute('CREATE DATABASE security')
        print("Database 'security' created successfully!")
    else:
        print("Database 'security' already exists.")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
EOF

echo "Database initialization complete."






