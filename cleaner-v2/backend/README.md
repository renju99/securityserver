# Cleaner Attendance V2 – Backend

## Setup

1. Copy `.env.example` to `.env` and set `DATABASE_URL` and `JWT_SECRET`.
2. **Using Docker:** From project root run `docker compose up -d db` (or `docker-compose up -d db`). Then create tables:
   ```bash
   docker exec -i cleaner-db psql -U admin -d cleaner_attendance < init.sql
   ```
3. **Or** use your own Postgres: create a database and run `init.sql` in it.
4. Create or reset the default admin user (see below).

## Default login

- **Email:** `admin@example.com`
- **Password:** `admin123`

### Option A: Seed (when DATABASE_URL works)

```bash
npm run seed
```

If you get "password authentication failed", set `DATABASE_URL` in `.env` to your real Postgres URL, e.g.  
`postgres://USER:PASSWORD@localhost:5432/DATABASE`.

### Option B: Reset admin without DATABASE_URL

If the seed can’t connect (wrong credentials in `.env`), reset the admin using SQL with your own client:

```bash
npm run reset-admin
```

This writes `scripts/reset-admin.sql`. Run it with your Postgres user and database, e.g.:

```bash
psql -U YOUR_USER -d YOUR_DATABASE -f backend/scripts/reset-admin.sql
```

Then log in with **admin@example.com** / **admin123**.
