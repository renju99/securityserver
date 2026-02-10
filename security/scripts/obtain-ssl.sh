#!/bin/bash
# Script to obtain SSL certificates using Let's Encrypt

DOMAIN="security.berkeleyuae.com"
EMAIL="ranjith.krishnan@berkeleyuae.com"

echo "========================================="
echo "Obtaining SSL certificate for $DOMAIN"
echo "========================================="

# Make sure nginx is running
cd /home/azureuser/security
sudo docker-compose up -d nginx

# Wait for nginx to be ready
sleep 5

# Obtain certificate using certbot
sudo docker-compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d "$DOMAIN"

if [ $? -eq 0 ]; then
    echo "========================================="
    echo "Certificate obtained successfully!"
    echo "Reloading Nginx..."
    echo "========================================="
    sudo docker-compose exec nginx nginx -s reload
    echo "SSL setup complete! Your site should now be accessible at https://$DOMAIN"
else
    echo "========================================="
    echo "Failed to obtain certificate"
    echo "Please check:"
    echo "1. DNS is pointing to this server"
    echo "2. Port 80 is accessible from the internet"
    echo "3. Domain name is correct"
    echo "========================================="
    exit 1
fi







