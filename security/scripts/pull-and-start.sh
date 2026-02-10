#!/bin/bash
# Simplified entrypoint script - no git pull logic
echo "========================================="
echo "Starting Odoo (Local Mode)..."
echo "========================================="

# Execute the original Odoo entrypoint with all arguments
exec /entrypoint.sh "$@"
