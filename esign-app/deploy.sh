#!/bin/bash
set -e

# Change to script directory
cd "$(dirname "$0")"

echo "Deploying eSign App..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    exit 1
fi

# Build and start services using sudo for docker access
sudo docker-compose down --remove-orphans || true
sudo docker-compose up -d --build

echo "Waiting for backend to start DB initialization..."
sleep 10

# Run DB initialization inside the backend container
echo "Initializing database..."
sudo docker-compose exec -T backend python init_db.py

echo "Deployment complete! Access the frontend at http://<VM-IP>:3000 and backend at http://<VM-IP>:8000"
