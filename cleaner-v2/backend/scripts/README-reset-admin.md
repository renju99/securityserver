# Reset admin password (admin@example.com / admin123)

## If you use Docker for Postgres

### Option A: Standalone script (recommended if docker-compose fails with ContainerConfig)

If `docker-compose up -d db` fails with `KeyError: 'ContainerConfig'` (docker-compose 1.29 + Docker 28), start the DB with plain Docker:

```bash
cd ~/cleaner-v2
sudo docker rm -f cleaner-db 2>/dev/null || true
sudo docker run -d --name cleaner-db -p 5433:5432 \
  -e POSTGRES_DB=cleaner_attendance -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=password123 \
  -v cleaner-v2_postgres_data:/var/lib/postgresql/data postgres:15
sleep 5
sudo docker exec -i cleaner-db psql -U admin -d cleaner_attendance < backend/init.sql
cd backend && npm run run-reset-admin
```

### Option B: docker-compose (after removing old container)

Remove the existing container so compose does a fresh create (avoids the recreate bug), then:

```bash
cd ~/cleaner-v2
sudo docker rm -f cleaner-db 2>/dev/null || true
sudo docker volume rm cleaner-v2_postgres_data 2>/dev/null || true
sudo docker-compose up -d db
sleep 5
sudo docker exec -i cleaner-db psql -U admin -d cleaner_attendance < backend/init.sql
cd backend && npm run run-reset-admin
```

`.env` uses port **5433** (host) so the script can connect. If you see **permission denied** on the Docker socket, use `sudo` or get added to the `docker` group.

## If you use a different Postgres (not Docker)

You need the **real** Postgres user and password (e.g. from your team, hosting panel, or the machine where the app runs). Then:

```bash
cd ~/cleaner-v2/backend
DATABASE_URL=postgres://YOUR_USER:YOUR_PASSWORD@localhost:5432/YOUR_DATABASE npm run run-reset-admin
```

Or put that `DATABASE_URL` in `backend/.env` and run `npm run run-reset-admin`.

## If the app runs on another server (e.g. Azure, VPS)

The database might be remote. Get `DATABASE_URL` from that environment (e.g. Azure App Settings, `.env` on the server, or your hosting dashboard) and run the command above with that URL.
