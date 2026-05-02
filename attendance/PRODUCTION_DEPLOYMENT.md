# Production Deployment

## 1) Prepare environment

1. Copy `.env.prod.example` to `.env.prod`.
2. Set strong values for:
   - `POSTGRES_PASSWORD`
   - `JWT_SECRET`
   - `JWT_REFRESH_SECRET`
3. Set `CORS_ORIGINS` to your production domain.

## 2) Build and start

```bash
docker-compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

## 3) Verify health

```bash
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs --tail=100 api
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
