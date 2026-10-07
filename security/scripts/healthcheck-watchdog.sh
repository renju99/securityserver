#!/usr/bin/env bash
# GuardLink / security.berkeleyuae.com health watchdog.
# Detects Postgres shared-memory / connection failures and Odoo downtime,
# then restarts the stack with cooldown to avoid flapping.
#
# Install (crontab):
#   */2 * * * * /home/azureuser/security/scripts/healthcheck-watchdog.sh >> /var/log/guardlink-health.log 2>&1

set -u

COMPOSE_DIR="${COMPOSE_DIR:-/home/azureuser/security}"
DB_CONTAINER="${DB_CONTAINER:-security-db-1}"
ODOO_CONTAINER="${ODOO_CONTAINER:-odoo-security}"
LOCK_DIR="${LOCK_DIR:-/tmp/guardlink-health}"
COOLDOWN_SEC="${COOLDOWN_SEC:-300}"   # do not auto-restart more than once per 5 minutes
PUBLIC_URL="${PUBLIC_URL:-https://security.berkeleyuae.com/web/login}"

mkdir -p "$LOCK_DIR"
LOG_TS() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

log() { echo "$(LOG_TS) $*"; }

in_cooldown() {
  local stamp_file="$LOCK_DIR/last_restart"
  [[ -f "$stamp_file" ]] || return 1
  local last now
  last=$(cat "$stamp_file" 2>/dev/null || echo 0)
  now=$(date +%s)
  (( now - last < COOLDOWN_SEC ))
}

mark_restart() {
  date +%s > "$LOCK_DIR/last_restart"
}

db_ok() {
  docker exec "$DB_CONTAINER" pg_isready -U odoo -d security >/dev/null 2>&1 \
    && docker exec "$DB_CONTAINER" psql -U odoo -d security -tAc 'SELECT 1' 2>/dev/null | grep -q 1
}

odoo_ok() {
  # Prefer in-container check (doesn't need published ports)
  docker exec "$ODOO_CONTAINER" curl -fsS -o /dev/null --connect-timeout 5 \
    http://127.0.0.1:8069/web/login >/dev/null 2>&1
}

public_ok() {
  # Soft check — TLS/proxy issues should not by themselves restart Postgres
  local code
  code=$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 8 -k -L "$PUBLIC_URL" 2>/dev/null || echo 000)
  [[ "$code" =~ ^(200|303)$ ]]
}

restart_stack() {
  local reason="$1"
  if in_cooldown; then
    log "FAIL ($reason) — restart skipped (cooldown ${COOLDOWN_SEC}s)"
    return 0
  fi
  log "FAIL ($reason) — restarting db then odoo"
  mark_restart
  (
    cd "$COMPOSE_DIR" || exit 1
    docker compose restart db
    # Wait until Postgres accepts connections again
    for _ in $(seq 1 30); do
      if db_ok; then
        break
      fi
      sleep 2
    done
    docker compose restart odoo_security
    sleep 8
  )
  if db_ok && odoo_ok; then
    log "RECOVERED after restart ($reason)"
  else
    log "STILL DOWN after restart ($reason) — manual intervention required"
  fi
}

# Containers must exist / be running
if ! docker inspect "$DB_CONTAINER" >/dev/null 2>&1; then
  log "ERROR: missing container $DB_CONTAINER"
  exit 1
fi
if ! docker inspect "$ODOO_CONTAINER" >/dev/null 2>&1; then
  log "ERROR: missing container $ODOO_CONTAINER"
  exit 1
fi

db_running=$(docker inspect -f '{{.State.Running}}' "$DB_CONTAINER" 2>/dev/null || echo false)
odoo_running=$(docker inspect -f '{{.State.Running}}' "$ODOO_CONTAINER" 2>/dev/null || echo false)

if [[ "$db_running" != "true" ]]; then
  restart_stack "db container not running"
  exit 0
fi

if ! db_ok; then
  restart_stack "postgres not accepting queries (possible shm failure)"
  exit 0
fi

if [[ "$odoo_running" != "true" ]]; then
  restart_stack "odoo container not running"
  exit 0
fi

if ! odoo_ok; then
  restart_stack "odoo HTTP not responding on :8069"
  exit 0
fi

# Healthy
if ! public_ok; then
  log "WARN: stack healthy locally but public URL check failed (proxy/TLS?)"
else
  # Quiet success — keep log small; uncomment for verbose:
  # log "OK"
  :
fi

exit 0
