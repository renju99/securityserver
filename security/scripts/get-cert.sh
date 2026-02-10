#!/bin/bash
set -e

DOMAIN="security.berkeleyuae.com"
EMAIL="ranjith.krishnan@berkeleyuae.com"

echo "========================================="
echo "Obtaining SSL certificate for $DOMAIN"
echo "========================================="

cd /home/azureuser/security

# Ensure nginx is running
echo "Starting Nginx..."
sudo docker-compose up -d nginx
sleep 3

# Check if nginx is healthy
if ! sudo docker-compose ps nginx | grep -q "Up"; then
    echo "ERROR: Nginx is not running properly"
    exit 1
fi

echo "Nginx is running. Obtaining certificate..."

# Obtain certificate
sudo docker-compose run --rm --no-deps certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN" \
    --verbose

if [ $? -eq 0 ]; then
    echo "========================================="
    echo "Certificate obtained successfully!"
    echo "Switching to HTTPS configuration..."
    echo "========================================="
    
    # Enable HTTPS config - replace HTTP-only with HTTPS config
    rm nginx/conf.d/security.berkeleyuae.com.conf
    mv nginx/conf.d/security.berkeleyuae.com.https.conf.disabled nginx/conf.d/security.berkeleyuae.com.conf
    
    # Restart nginx
    sudo docker-compose restart nginx
    sleep 3
    
    echo "SSL setup complete! Your site is now accessible at https://$DOMAIN"
else
    echo "========================================="
    echo "Failed to obtain certificate"
    echo "Please verify:"
    echo "1. DNS for $DOMAIN points to this server's IP"
    echo "2. Port 80 is accessible from the internet"
    echo "3. The domain is correct"
    echo "========================================="
    exit 1
fi

