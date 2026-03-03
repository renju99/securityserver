#!/bin/bash
# Run this after starting the DB (e.g. with docker run). Fixes 502 by starting backend + frontend.
set -e
cd "$(dirname "$0")/.."
echo "Connecting cleaner-db to app network..."
sudo docker network create cleaner-v2_cleaner-net 2>/dev/null || true
sudo docker network connect cleaner-v2_cleaner-net cleaner-db 2>/dev/null || true
echo "Starting redis, backend, frontend..."
sudo docker-compose -f docker-compose.app-only.yml up -d --build
echo "Done. Give it 30s then check https://cleaning.berkeleyuae.com"
