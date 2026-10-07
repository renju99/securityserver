#!/usr/bin/env bash
# migrate-attachments-to-blob.sh
#
# Migrates existing Odoo ir.attachment files from local filestore to
# Azure Blob Storage (guardlink-media container).
#
# Blob naming matches runtime (ir_attachment_azure._blob_name):
#   azure:attachments/{checksum[:2]}/{checksum}
# where store_fname is already Odoo's content-addressed path.
#
# Only migrates eligible files:
#   - mimetype: image/*, video/*, audio/*  OR  file_size ≥ 50 KB
#   - res_model NOT in (ir.ui.view, ir.ui.menu, ir.module.module)
#   - store_fname does NOT already start with "azure:"
#   - store_fname matches Odoo filestore pattern: ab/abcdef...
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

# Fetch eligible attachment records (align with ir_attachment_azure._file_write)
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
    AND a.store_fname ~ '^[a-f0-9]{2}/[a-f0-9]+$'
    AND a.file_size >= 51200
    AND (
      a.mimetype LIKE 'image/%'
      OR a.mimetype LIKE 'video/%'
      OR a.mimetype LIKE 'audio/%'
      OR a.file_size >= 51200
    )
    AND COALESCE(a.res_model, '') NOT IN ('ir.ui.view', 'ir.ui.menu', 'ir.module.module')
  ORDER BY a.file_size DESC
) TO STDOUT WITH CSV HEADER;
"

CSV_FILE=$(mktemp /tmp/att_migrate.XXXXXX.csv)
trap 'rm -f "$CSV_FILE"' EXIT

docker exec "$DB_CONTAINER" psql -U odoo -d security -c "$QUERY" > "$CSV_FILE" 2>/dev/null
TOTAL=$(( $(wc -l < "$CSV_FILE") - 1 ))
echo "Found $TOTAL eligible attachments to migrate."
echo ""

# Avoid pipe-subshell so counters persist (process substitution).
while IFS=',' read -r att_id store_fname res_model res_id att_name mimetype file_size; do
    # Strip surrounding quotes from CSV fields
    att_id="${att_id//\"/}"
    store_fname="${store_fname//\"/}"
    res_model="${res_model//\"/}"
    res_id="${res_id//\"/}"
    att_name="${att_name//\"/}"
    mimetype="${mimetype//\"/}"
    file_size="${file_size//\"/}"

    # Strict validation — never interpolate untrusted values into SQL.
    if [[ ! "$att_id" =~ ^[0-9]+$ ]]; then
        echo "[SKIP] invalid attachment id: $att_id"
        SKIPPED=$((SKIPPED+1))
        continue
    fi
    if [[ ! "$store_fname" =~ ^[a-f0-9]{2}/[a-f0-9]+$ ]]; then
        echo "[SKIP] id=$att_id — unexpected store_fname format: $store_fname"
        SKIPPED=$((SKIPPED+1))
        continue
    fi
    if [[ ! "$file_size" =~ ^[0-9]+$ ]]; then
        file_size=0
    fi

    LOCAL_PATH="$FILESTORE_ROOT/$store_fname"

    if ! docker exec "$ODOO_CONTAINER" test -f "$LOCAL_PATH" 2>/dev/null; then
        echo "[SKIP] id=$att_id '$att_name' — filestore file not found: $store_fname"
        SKIPPED=$((SKIPPED+1))
        continue
    fi

    # Match runtime content-addressed naming (attachments/{checksum[:2]}/{checksum}).
    BLOB_NAME="attachments/${store_fname}"
    AZURE_STORE_FNAME="azure:${BLOB_NAME}"

    EXISTS=$(az storage blob exists \
        --account-name "$AZURE_STORAGE_ACCOUNT" \
        --account-key "$AZURE_STORAGE_KEY" \
        --container-name "$CONTAINER" \
        --name "$BLOB_NAME" \
        --query "exists" --output tsv 2>/dev/null || echo "false")

    if [[ "$EXISTS" == "true" ]]; then
        echo "[SKIP] id=$att_id '$att_name' already in blob"
        if [[ "$DRY_RUN" == "false" ]]; then
            docker exec "$DB_CONTAINER" psql -U odoo -d security \
                -v ON_ERROR_STOP=1 \
                -v att_id="$att_id" \
                -v new_fname="$AZURE_STORE_FNAME" \
                -v old_fname="$store_fname" \
                -c "UPDATE ir_attachment SET store_fname = :'new_fname' WHERE id = :'att_id'::integer AND store_fname = :'old_fname';" \
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

    TMPFILE=$(mktemp /tmp/att_upload.XXXXXX)
    if ! docker cp "$ODOO_CONTAINER:$LOCAL_PATH" "$TMPFILE" 2>/dev/null; then
        echo "  [ERROR] Cannot copy file from container" >&2
        rm -f "$TMPFILE"
        FAILED=$((FAILED+1))
        continue
    fi

    if az storage blob upload \
        --account-name "$AZURE_STORAGE_ACCOUNT" \
        --account-key "$AZURE_STORAGE_KEY" \
        --container-name "$CONTAINER" \
        --name "$BLOB_NAME" \
        --file "$TMPFILE" \
        --content-type "${mimetype:-application/octet-stream}" \
        --overwrite false \
        --output none 2>/dev/null; then

        docker exec "$DB_CONTAINER" psql -U odoo -d security \
            -v ON_ERROR_STOP=1 \
            -v att_id="$att_id" \
            -v new_fname="$AZURE_STORE_FNAME" \
            -v old_fname="$store_fname" \
            -c "UPDATE ir_attachment SET store_fname = :'new_fname' WHERE id = :'att_id'::integer AND store_fname = :'old_fname';" \
            >/dev/null 2>&1

        docker exec "$ODOO_CONTAINER" rm -f "$LOCAL_PATH" 2>/dev/null || true

        MIGRATED=$((MIGRATED+1))
        BYTES_MOVED=$((BYTES_MOVED + file_size))
        echo "  [OK] Migrated — local copy removed"
    else
        echo "  [ERROR] Upload failed" >&2
        FAILED=$((FAILED+1))
    fi
    rm -f "$TMPFILE"
done < <(tail -n +2 "$CSV_FILE")

echo ""
echo "=== Migration complete ==="
echo "Migrated : $MIGRATED  ($(( BYTES_MOVED / 1024 / 1024 )) MB freed)"
echo "Skipped  : $SKIPPED"
echo "Failed   : $FAILED"
