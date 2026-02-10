#!/bin/bash
# Script to package the procurement server for migration

FILE_NAME="procurement_migration_full_$(date +%Y%m%d_%H%M%S).tar.gz"

echo "📦 Packaging procurement server AND attachments to $FILE_NAME..."

# Ensure we are in the procurement directory
cd "$(dirname "$0")"

# We will package the app code AND the attachments from /var/www/attachments
# Note: Using -C and multiple paths to structure the archive
tar -czvf "$FILE_NAME" \
    --exclude='node_modules' \
    --exclude='.git' \
    --exclude='azure' \
    --exclude='*.tar.gz' \
    --exclude='*.zip' \
    --exclude='.antigravity-server' \
    --exclude='.cursor' \
    . \
    -C /var/www attachments

echo "✅ Full package created successfully: $FILE_NAME"
echo ""
echo "Steps to move to Azure VM:"
echo "1. Transfer: scp $FILE_NAME azureuser@<VM_IP>:/home/azureuser/"
echo "2. On Azure VM:"
echo "   mkdir -p procurement-app"
echo "   tar -xzvf $FILE_NAME -C procurement-app"
echo "   # Move attachments to the expected system location"
echo "   sudo mkdir -p /var/www"
echo "   sudo mv procurement-app/attachments /var/www/"
echo "   sudo chown -R 1000:1000 /var/www/attachments"
echo "   # Start the app"
echo "   cd procurement-app && docker compose up -d --build"
