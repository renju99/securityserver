#!/bin/bash
# Script to migrate vendor files from container to persistent location

echo "=== Migrating vendor files to persistent location ==="

# Step 1: Copy files from container's internal storage to mounted volume
echo "Step 1: Copying files from container to /app/uploads (mounted volume)..."
docker exec procurement-container sh -c 'if [ -d "/app/D:\\Vendors" ]; then cp -r "/app/D:\\Vendors"/* /app/uploads/ 2>&1; echo "Files copied"; else echo "Source directory not found"; fi'

# Step 2: Verify files are in persistent location on host
echo ""
echo "Step 2: Verifying files in persistent location (/var/www/attachments)..."
echo "Vendor folders found:"
find /var/www/attachments -maxdepth 1 -type d -name "*SUB-*" | wc -l
echo ""
echo "Total files:"
find /var/www/attachments -type f | wc -l
echo ""
echo "Total size:"
du -sh /var/www/attachments

echo ""
echo "=== Migration complete ==="
echo "All files are now in /var/www/attachments and will persist after container rebuild"



