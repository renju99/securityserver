#!/usr/bin/env bash
# migrate-attachments-to-blob.sh
#
# Migrates existing Odoo ir.attachment files from local filestore to
# Azure Blob Storage (guardlink-media container).
#
# Only migrates eligible files:
#   - mimetype: image/*, video/*, audio/*
#   - file size ≥ 50 KB
#   - res_model NOT in (ir.ui.view, ir.ui.menu, ir.module.module)
#   - store_fname does NOT already start with "azure:"
#
# Updates ir_attachment.store_fname in the DB after each successful upload.
# Safe to re-run: already-migrated files are skipped.
#
# Usage:
#   sudo bash /home/azureuser/security/scripts/migrate-attachments-to-blob.sh [--dry-run]

set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY-RUN] No files will be uploaded or DB rows updated."
fi

SCRIPT_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
ENV_FILE="$SCRIPT_DIR/../.env.storage"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE not found" >&2; exit 1
fi
# shellcheck source=/dev/null
set -a && source "$ENV_FILE" && set +a

CONTAINER="$AZURE_STORAGE_CONTAINER_MEDIA"
FILESTORE_ROOT="/var/lib/odoo/.local/share/Odoo/filestore/security"
ODOO_CONTAINER="odoo-security"
DB_CONTAINER="security-db-1"

echo "=== GuardLink: Migrate ir.attachment to Azure Blob ==="
echo "Container : $CONTAINER"
echo "Filestore : $FILESTORE_ROOT (inside $ODOO_CONTAINER)"
echo "Dry-run   : $DRY_RUN"
echo ""

MIGRATED=0
SKIPPED=0
FAILED=0
BYTES_MOVED=0

# Fetch eligible attachment records
QUERY="
COPY (
  SELECT
    a.id,
    a.store_fname,
    a.res_model,
    a.res_id,
    a.name,
    a.mimetype,
    a.file_size
  FROM ir_attachment a
  WHERE
    a.store_fname IS NOT NULL
    AND a.store_fname != ''
    AND a.store_fname NOT LIKE 'azure:%'
    AND a.file_size >= 51200
    AND (
      a.mimetype LIKE 'image/%'
      OR a.mimetype LIKE 'video/%'
      OR a.mimetype LIKE 'audio/%'
      OR a.file_size >= 512000
    )
    AND a.res_model NOT IN ('ir.ui.view', 'ir.ui.menu', 'ir.module.module')
  ORDER BY a.file_size DESC
) TO STDOUT WITH CSV HEADER;
"

CSV_FILE=$(mktemp /tmp/att_migrate.XXXXXX.csv)
trap 'rm -f "$CSV_FILE"' EXIT

docker exec "$DB_CONTAINER" psql -U odoo -d security -c "$QUERY" > "$CSV_FILE" 2>/dev/null
TOTAL=$(( $(wc -l < "$CSV_FILE") - 1 ))
echo "Found $TOTAL eligible attachments to migrate."
echo ""

# Process each record
tail -n +2 "$CSV_FILE" | while IFS=',' read -r att_id store_fname res_model res_id att_name mimetype file_size; do
    # Strip surrounding quotes from CSV fields
    att_id="${att_id//\"/}"
    store_fname="${store_fname//\"/}"
    res_model="${res_model//\"/}"
    res_id="${res_id//\"/}"
    att_name="${att_name//\"/}"
    mimetype="${mimetype//\"/}"
    file_size="${file_size//\"/}"

    if [[ -z "$store_fname" || -z "$att_id" ]]; then
        continue
    fi

    # Build local filestore path
    LOCAL_PATH="$FILESTORE_ROOT/$store_fname"

    # Check file exists in container
    if ! docker exec "$ODOO_CONTAINER" test -f "$LOCAL_PATH" 2>/dev/null; then
        echo "[SKIP] id=$att_id '$att_name' — filestore file not found: $store_fname"
        SKIPPED=$((SKIPPED+1))
        continue
    fi

    # Build blob name
    MODEL_SLUG="${res_model//./_}"
    SAFE_NAME="${att_name//\//_}"
    BLOB_NAME="attachments/${MODEL_SLUG}/${res_id}/${att_id}_${SAFE_NAME}"

    # Check if already in blob
    EXISTS=$(az storage blob exists \
        --account-name "$AZURE_STORAGE_ACCOUNT" \
        --account-key "$AZURE_STORAGE_KEY" \
        --container-name "$CONTAINER" \
        --name "$BLOB_NAME" \
        --query "exists" --output tsv 2>/dev/null || echo "false")

    if [[ "$EXISTS" == "true" ]]; then
        echo "[SKIP] id=$att_id '$att_name' already in blob"
        if [[ "$DRY_RUN" == "false" ]]; then
            # Ensure DB is updated even if blob exists from a previous partial run
            docker exec "$DB_CONTAINER" psql -U odoo -d security \
                -c "UPDATE ir_attachment SET store_fname='azure:$BLOB_NAME' WHERE id=$att_id AND store_fname='$store_fname';" \
                >/dev/null 2>&1 || true
        fi
        SKIPPED=$((SKIPPED+1))
        continue
    fi

    SIZE_KB=$(( file_size / 1024 ))
    echo "[UPLOAD] id=$att_id '$att_name' (${SIZE_KB}KB) → $BLOB_NAME"

    if [[ "$DRY_RUN" == "true" ]]; then
        MIGRATED=$((MIGRATED+1))
        continue
    fi

    # Copy file out of the container to a temp location azureuser can read
    TMPFILE=$(mktemp /tmp/att_upload.XXXXXX)
    if ! docker cp "$ODOO_CONTAINER:$LOCAL_PATH" "$TMPFILE" 2>/dev/null; then
        echo "  [ERROR] Cannot copy file from container" >&2
        rm -f "$TMPFILE"
        FAILED=$((FAILED+1))
        continue
    fi

    # Upload to Azure Blob
    if az storage blob upload \
        --account-name "$AZURE_STORAGE_ACCOUNT" \
        --account-key "$AZURE_STORAGE_KEY" \
        --container-name "$CONTAINER" \
        --name "$BLOB_NAME" \
        --file "$TMPFILE" \
        --content-type "$mimetype" \
        --overwrite false \
        --output none 2>/dev/null; then

        # Update DB store_fname
        docker exec "$DB_CONTAINER" psql -U odoo -d security \
            -c "UPDATE ir_attachment SET store_fname='azure:$BLOB_NAME' WHERE id=$att_id AND store_fname='$store_fname';" \
            >/dev/null 2>&1

        # Remove local filestore copy
        docker exec "$ODOO_CONTAINER" rm -f "$LOCAL_PATH" 2>/dev/null || true

        MIGRATED=$((MIGRATED+1))
        BYTES_MOVED=$((BYTES_MOVED + file_size))
        echo "  [OK] Migrated — local copy removed"
    else
        echo "  [ERROR] Upload failed" >&2
        FAILED=$((FAILED+1))
    fi
    rm -f "$TMPFILE"
done

echo ""
echo "=== Migration complete ==="
echo "Migrated : $MIGRATED  ($(( BYTES_MOVED / 1024 / 1024 )) MB freed)"
echo "Skipped  : $SKIPPED"
echo "Failed   : $FAILED"
