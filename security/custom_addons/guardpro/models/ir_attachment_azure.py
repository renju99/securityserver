# -*- coding: utf-8 -*-
"""
Azure Blob Storage backend for ir.attachment.

Odoo's default filestore puts every binary attachment on local disk.
This override transparently routes writes for large / media attachments
to the Azure Blob container "guardlink-media", keeping local disk lean.

Rules (mimic the filestore content-addressing scheme):
  - store_fname prefix "azure:"  → file lives in Azure Blob
  - all other store_fname values → Odoo local filestore (unchanged)

What goes to Azure:
  • Any mimetype starting with  image/, video/, audio/
  • Any file whose raw size is ≥ AZURE_SIZE_THRESHOLD bytes
  • Exceptions: ir.ui.view (compiled JS/CSS assets – keep local for speed)

Fallback: if the Azure SDK is not configured the file stays on disk and
a warning is logged once. No data is ever lost.
"""
import base64
import logging
import os

from odoo import models

_logger = logging.getLogger(__name__)

# Models whose attachments should ALWAYS stay on local disk (Odoo internals).
_LOCAL_ONLY_MODELS = frozenset({
    'ir.ui.view',
    'ir.ui.menu',
    'ir.module.module',
})

# Mimetypes that must never go to Azure (compiled web assets / maps).
_LOCAL_ONLY_MIMETYPES = frozenset({
    'text/css',
    'text/javascript',
    'application/javascript',
    'application/x-javascript',
    'text/scss',
    'text/less',
})

# Minimum file size (bytes) to qualify for Azure storage.
AZURE_SIZE_THRESHOLD = int(os.environ.get('AZURE_ATTACH_MIN_BYTES', '51200'))  # 50 KB

# Azure container for general-purpose attachments.
AZURE_MEDIA_CONTAINER = os.environ.get('AZURE_STORAGE_CONTAINER_MEDIA', 'guardlink-media')

# Prefix stored in store_fname to mark Azure-hosted files.
AZURE_PREFIX = 'azure:'

_SDK_WARNED = False  # log the SDK-missing warning only once


def _is_web_asset_attachment(name='', url='', mime=''):
    """Compiled Odoo asset bundles must stay on local filestore.

    ``ir.binary`` streams attachments via a local filesystem path derived from
    ``store_fname``. Azure-prefixed store names break ``web.assets_*.min.js``
    with FileNotFoundError / HTTP 500.
    """
    name = (name or '').lower()
    url = (url or '').lower()
    mime = (mime or '').lower()
    if mime in _LOCAL_ONLY_MIMETYPES:
        return True
    if '/web/assets/' in url:
        return True
    if name.startswith('web.assets_') or name.startswith('web._assets'):
        return True
    if name.endswith(('.js', '.css', '.js.map', '.css.map', '.min.js', '.min.css')):
        return True
    return False


def _get_blob_client():
    """Return a (BlobServiceClient, container_name) tuple, or (None, None)."""
    global _SDK_WARNED
    conn_str = os.environ.get('AZURE_STORAGE_CONNECTION_STRING', '')
    if not conn_str:
        return None, None
    try:
        from azure.storage.blob import BlobServiceClient
        return BlobServiceClient.from_connection_string(conn_str), AZURE_MEDIA_CONTAINER
    except ImportError:
        if not _SDK_WARNED:
            _logger.warning(
                'GuardLink: azure-storage-blob SDK not installed — '
                'attachments will use local filestore. '
                'Run: pip3 install azure-storage-blob'
            )
            _SDK_WARNED = True
        return None, None
    except Exception as exc:
        _logger.error('GuardLink: BlobServiceClient init failed: %s', exc)
        return None, None


def _should_use_azure(attachment):
    """Return True when this attachment should be stored in Azure Blob."""
    if attachment.res_model in _LOCAL_ONLY_MODELS:
        return False
    mime = (attachment.mimetype or '').lower()
    if mime.startswith(('image/', 'video/', 'audio/')):
        return True
    # Fall back to size check for other types (PDFs, spreadsheets, etc.)
    raw = attachment.datas or b''
    if isinstance(raw, str):
        raw = raw.encode()
    size = len(base64.b64decode(raw)) if raw else 0
    return size >= AZURE_SIZE_THRESHOLD


def _blob_name(checksum):
    """Content-addressed blob name (mirrors Odoo filestore's 2-char prefix scheme)."""
    return f'attachments/{checksum[:2]}/{checksum}'


class IrAttachmentAzure(models.Model):
    _inherit = 'ir.attachment'

    # ------------------------------------------------------------------
    # Write / Read / Delete overrides
    # ------------------------------------------------------------------

    def _file_write(self, value, checksum):
        """
        Route large / media attachments to Azure Blob.
        Returns a store_fname that encodes the storage location:
          - Local:  '<2-char-prefix>/<hash>'  (Odoo default)
          - Azure:  'azure:<blob-name>'

        NOTE: In Odoo 18, value is raw bytes (not base64).
        """
        # Odoo 18 passes raw bytes; earlier versions passed base64 strings.
        if isinstance(value, (bytes, bytearray)):
            raw = bytes(value)
        else:
            try:
                raw = base64.b64decode(value)
            except Exception:
                return super()._file_write(value, checksum)

        client, container = _get_blob_client()
        if client is None:
            return super()._file_write(value, checksum)

        # Get metadata safely (self is a recordset, usually single record here)
        try:
            mime = (self.mimetype or '').lower()
            model = self.res_model or ''
            name = self.name or ''
            url = self.url or ''
        except Exception:
            mime = ''
            model = ''
            name = ''
            url = ''

        is_media = mime.startswith(('image/', 'video/', 'audio/'))
        is_large = len(raw) >= AZURE_SIZE_THRESHOLD
        is_local_only = model in _LOCAL_ONLY_MODELS
        is_asset = _is_web_asset_attachment(name=name, url=url, mime=mime)

        # Asset bundles are multi-MB JS/CSS. During bundle generation Odoo often
        # calls _file_write on an empty recordset (no name/mime/model yet).
        # Default those writes to local filestore — Azure store_fname breaks
        # ir.binary streaming (HTTP 500 on web.assets_web.min.js).
        if is_local_only or is_asset or (not mime and not model and not name):
            return super()._file_write(value, checksum)

        if not is_media and not is_large:
            return super()._file_write(value, checksum)

        blob_name = _blob_name(checksum)
        try:
            from azure.storage.blob import ContentSettings
            container_client = client.get_container_client(container)
            container_client.upload_blob(
                name=blob_name,
                data=raw,
                overwrite=True,
                content_settings=ContentSettings(content_type=self.mimetype or 'application/octet-stream'),
            )
            _logger.info(
                'GuardLink attach: uploaded %s (%d bytes) → blob %s',
                self.name, len(raw), blob_name
            )
            return AZURE_PREFIX + blob_name
        except Exception as exc:
            _logger.error(
                'GuardLink attach: blob upload failed for %s, falling back to filestore: %s',
                self.name, exc
            )
            return super()._file_write(value, checksum)

    def _file_read(self, fname):
        """Read from Azure Blob when store_fname starts with 'azure:'."""
        if not (fname or '').startswith(AZURE_PREFIX):
            return super()._file_read(fname)

        blob_name = fname[len(AZURE_PREFIX):]
        client, container = _get_blob_client()
        if client is None:
            _logger.error('GuardLink attach: cannot read blob %s — SDK not configured', blob_name)
            return b''
        try:
            data = client.get_blob_client(container=container, blob=blob_name).download_blob().readall()
            return bytes(data)
        except Exception as exc:
            _logger.error('GuardLink attach: blob read failed for %s: %s', blob_name, exc)
            return b''

    def _file_delete(self, fname):
        """Delete from Azure Blob when store_fname starts with 'azure:'."""
        if not (fname or '').startswith(AZURE_PREFIX):
            return super()._file_delete(fname)

        blob_name = fname[len(AZURE_PREFIX):]
        client, container = _get_blob_client()
        if client is None:
            return
        try:
            client.get_blob_client(container=container, blob=blob_name).delete_blob()
            _logger.info('GuardLink attach: deleted blob %s', blob_name)
        except Exception as exc:
            _logger.warning('GuardLink attach: blob delete failed for %s: %s', blob_name, exc)
