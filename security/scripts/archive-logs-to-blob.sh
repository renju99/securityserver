#!/usr/bin/env bash
# archive-logs-to-blob.sh
# Upload compressed Odoo log archives to Azure Blob Storage (guardlink-logs container).
# Run by cron daily at 03:10 (after logrotate at 03:00).
#
# Requires: az CLI logged in, /home/azureuser/security/.env.storage

set -euo pipefail

ENV_FILE="$(dirname "$(realpath "${BASH_SOURCE[0]}")")/../.env.storage"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found" >&2
  exit 1
fi
# shellcheck source=/dev/null
set -a && source "$ENV_FILE" && set +a

LOG_VOLUME_DATA="/var/lib/docker/volumes/security_odoo-web-data/_data"
TMPDIR_UPLOAD="$(mktemp -d /tmp/odoo-log-upload.XXXXXX)"
trap 'rm -rf "$TMPDIR_UPLOAD"' EXIT

UPLOADED=0
SKIPPED=0
FAILED=0

for GZ in "$LOG_VOLUME_DATA"/odoo.log-*.gz; do
  [[ -f "$GZ" ]] || continue
  BASENAME="$(basename "$GZ")"

  # Skip files older than 15 days (they will be deleted by the blob lifecycle policy anyway)
  if [[ "$(find "$GZ" -mtime +15 2>/dev/null)" != "" ]]; then
    echo "[SKIP] Older than 15 days: $BASENAME"
    SKIPPED=$((SKIPPED+1))
    continue
  fi

  # Check if already in blob
  EXISTS=$(az storage blob exists \
    --account-name "$AZURE_STORAGE_ACCOUNT" \
    --account-key "$AZURE_STORAGE_KEY" \
    --container-name "$AZURE_STORAGE_CONTAINER_LOGS" \
    --name "$BASENAME" \
    --query "exists" --output tsv 2>/dev/null || echo "false")

  if [[ "$EXISTS" == "true" ]]; then
    echo "[SKIP] Already in blob: $BASENAME"
    SKIPPED=$((SKIPPED+1))
    continue
  fi

  # Copy to a temp file azureuser can read (log volume is root-owned)
  TMPFILE="$TMPDIR_UPLOAD/$BASENAME"
  if ! sudo cp "$GZ" "$TMPFILE" || ! sudo chown azureuser:azureuser "$TMPFILE"; then
    echo "[ERROR] Cannot copy $GZ to temp location" >&2
    FAILED=$((FAILED+1))
    continue
  fi

  echo "[UPLOAD] $BASENAME ($(du -sh "$TMPFILE" | cut -f1))..."
  if az storage blob upload \
      --account-name "$AZURE_STORAGE_ACCOUNT" \
      --account-key "$AZURE_STORAGE_KEY" \
      --container-name "$AZURE_STORAGE_CONTAINER_LOGS" \
      --name "$BASENAME" \
      --file "$TMPFILE" \
      --overwrite false \
      --output none 2>/dev/null; then
    echo "[OK] Uploaded: $BASENAME"
    UPLOADED=$((UPLOADED+1))
  else
    echo "[ERROR] Upload failed: $BASENAME" >&2
    FAILED=$((FAILED+1))
  fi
done

echo "Done. Uploaded=$UPLOADED Skipped=$SKIPPED Failed=$FAILED"
