# Production Deployment

## 0) Docker Compose (important)

**Docker Engine 25+ with legacy Compose v1.29** often fails with `KeyError: 'ContainerConfig'` when recreating containers. Use **Compose v2** on the host:

- Preferred: install Docker’s **Compose plugin** so `docker compose` works (see [Docker docs](https://docs.docker.com/compose/install/linux/)).
- Or install the **v2 standalone binary** ahead of the old v1 on your `PATH`, for example:

```bash
sudo curl -fsSL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose version   # should report v2.x
```

Ensure `which docker-compose` resolves to v2 (e.g. `/usr/local/bin` before `/usr/bin`). You can use `docker compose` instead of `docker-compose` if the plugin is installed.

## 1) Prepare environment

1. Copy `.env.prod.example` to `.env.prod`.
2. Set strong values for:
   - `POSTGRES_PASSWORD`
   - `JWT_SECRET`
   - `JWT_REFRESH_SECRET`
3. Set `CORS_ORIGINS` to your production domain.

## 2) Build and start

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
# or, if you use the standalone v2 binary named docker-compose:
docker-compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

## 3) Verify health

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 api
curl -f http://localhost:3000/healthz
```

## 4) Migrations

- API container runs migrations automatically on startup (`npm run migrate`).
- Migrations are tracked in `schema_migrations`.

## 5) Post-deploy smoke tests

1. HR login works.
2. Employee face enrollment works.
3. Kiosk check-in/check-out works.
4. Attendance appears in dashboard.
5. Odoo sync outbox drains without repeated errors.
