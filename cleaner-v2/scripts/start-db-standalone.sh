#!/bin/bash
# Start Postgres for cleaner-v2 without docker-compose (avoids ContainerConfig bug with docker-compose 1.29 + Docker 28).
# Uses port 5433 so it doesn't conflict with Postgres on 5432.
set -e
CONTAINER="cleaner-db"
IMAGE="postgres:15"
PORT="${1:-5433}"
docker rm -f "$CONTAINER" 2>/dev/null || true
docker run -d \
  --name "$CONTAINER" \
  -p "${PORT}:5432" \
  -e POSTGRES_DB=cleaner_attendance \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD=password123 \
  -v cleaner-v2_postgres_data:/var/lib/postgresql/data \
  "$IMAGE"
echo "Started $CONTAINER on port $PORT. Wait a few seconds, then run:"
echo "  docker exec -i $CONTAINER psql -U admin -d cleaner_attendance < backend/init.sql"
echo "  cd backend && npm run run-reset-admin"
