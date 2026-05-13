#!/bin/bash
# TLS helper for security/docker-compose.standalone.yml (project name: berkeley-security).
# Webroot issuance needs nginx running with a cert already present OR use bootstrap below.
set -euo pipefail

DOMAIN="security.berkeleyuae.com"
EMAIL="${LETSENCRYPT_EMAIL:-ranjith.krishnan@berkeleyuae.com}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEC_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
export COMPOSE_FILE="${SEC_DIR}/docker-compose.standalone.yml"

cd "${SEC_DIR}"

usage() {
  echo "Usage:"
  echo "  $0 renew          # webroot renew (stack must be up; port 443 as configured)"
  echo "  $0 bootstrap      # first cert: stops nginx, certbot --standalone on :80, then starts all"
  exit 1
}

case "${1:-}" in
  renew)
    docker compose up -d
    sleep 2
    docker compose run --rm --no-deps --entrypoint certbot certbot certonly \
      --webroot --webroot-path=/var/www/certbot \
      --email "$EMAIL" --agree-tos --no-eff-email \
      -d "$DOMAIN" || true
    docker compose exec nginx nginx -s reload
    echo "Renew / obtain attempt finished; check certbot output above."
    ;;
  bootstrap)
    echo "Stopping nginx (port 80 must be free)..."
    docker compose stop nginx 2>/dev/null || true
    docker compose up -d db odoo_security
    docker compose run --rm -p 80:80 --entrypoint certbot certbot certonly \
      --standalone \
      --email "$EMAIL" --agree-tos --no-eff-email \
      -d "$DOMAIN"
    docker compose up -d
    echo "Stack up: https://${DOMAIN}"
    ;;
  *)
    usage
    ;;
esac
