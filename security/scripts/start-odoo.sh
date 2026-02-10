#!/bin/bash
set -e

# Pull latest code from GitHub
echo "Pulling latest code from GitHub..."
cd /mnt/extra-addons/guardpro

# Check if it's a git repository
if [ -d .git ]; then
    # Fetch and pull latest changes
    git fetch origin
    git reset --hard origin/main || git reset --hard origin/master
    echo "Code updated successfully"
else
    echo "Warning: guardpro is not a git repository. Skipping git pull."
fi

# Start Odoo
exec /entrypoint.sh "$@"






