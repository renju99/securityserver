#!/bin/bash
git pull origin main
docker build -t vendor-registration .
docker stop procurement-container || true
docker rm procurement-container || true
docker run -d --name procurement-container --restart always -p 127.0.0.1:3000:3000 -v /var/www/attachments:/app/uploads -v /root/procurement/data:/app/data vendor-registration
echo "Deployment complete!"
