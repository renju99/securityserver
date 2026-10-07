# -*- coding: utf-8 -*-
"""
Azure Blob Storage helper for PTT audio.

Reads credentials from env vars (injected via docker-compose / .env.storage):
    AZURE_STORAGE_CONNECTION_STRING
    AZURE_STORAGE_CONTAINER_AUDIO   (default: guardlink-audio)

Falls back gracefully when the SDK is not installed or the connection string
is absent — in that case every call returns None and callers stay on the
Odoo filestore path (backward-compatible).
"""
import logging
import os

_logger = logging.getLogger(__name__)

_CONN_STR = os.environ.get('AZURE_STORAGE_CONNECTION_STRING', '')
_CONTAINER = os.environ.get('AZURE_STORAGE_CONTAINER_AUDIO', 'guardlink-audio')
_SDK_AVAILABLE = False
_BlobServiceClient = None

try:
    from azure.storage.blob import (
        BlobServiceClient,
        generate_blob_sas,
        BlobSasPermissions,
    )
    _BlobServiceClient = BlobServiceClient
    _SDK_AVAILABLE = True
except ImportError:
    _logger.warning(
        'GuardLink PTT: azure-storage-blob SDK not installed — '
        'PTT audio will use the Odoo filestore. '
        'Run: pip3 install azure-storage-blob'
    )


def _client():
    """Return a BlobServiceClient, or None if not configured."""
    if not _SDK_AVAILABLE or not _CONN_STR:
        return None
    try:
        return _BlobServiceClient.from_connection_string(_CONN_STR)
    except Exception as exc:
        _logger.error('GuardLink PTT: cannot create BlobServiceClient: %s', exc)
        return None


def blob_name_for_message(message_id, stream_id=None, ext='webm'):
    """Deterministic blob name for a PTT message."""
    safe = (stream_id or f'msg_{message_id}').replace('/', '_')
    return f'ptt/{message_id}/{safe}.{ext}'


def upload_audio(message_id, stream_id, audio_bytes, content_type='audio/webm'):
    """Upload raw audio bytes to Azure Blob and return the blob name.

    Returns None on failure so callers fall back to filestore.
    """
    client = _client()
    if client is None:
        return None
    ext = 'ogg' if 'ogg' in content_type or 'opus' in content_type else 'webm'
    name = blob_name_for_message(message_id, stream_id, ext)
    try:
        container = client.get_container_client(_CONTAINER)
        container.upload_blob(
            name=name,
            data=audio_bytes,
            overwrite=True,
            content_settings=__import__(
                'azure.storage.blob', fromlist=['ContentSettings']
            ).ContentSettings(content_type=content_type),
        )
        _logger.info('GuardLink PTT: uploaded blob %s (%d bytes)', name, len(audio_bytes))
        return name
    except Exception as exc:
        _logger.error('GuardLink PTT: blob upload failed for message %d: %s', message_id, exc)
        return None


def download_audio(blob_name):
    """Download audio bytes from Azure Blob. Returns (bytes, content_type) or (None, None)."""
    client = _client()
    if client is None:
        return None, None
    try:
        blob = client.get_blob_client(container=_CONTAINER, blob=blob_name)
        data = blob.download_blob()
        # BlobProperties is not a dict — use attribute access.
        props = getattr(data, 'properties', None)
        content_settings = getattr(props, 'content_settings', None) if props else None
        content_type = (
            getattr(content_settings, 'content_type', None) if content_settings else None
        ) or 'audio/webm'
        return data.readall(), content_type
    except Exception as exc:
        _logger.error('GuardLink PTT: blob download failed for %s: %s', blob_name, exc)
        return None, None


def delete_audio(blob_name):
    """Delete a blob. Returns True on success, False on failure."""
    client = _client()
    if client is None:
        return False
    try:
        client.get_blob_client(container=_CONTAINER, blob=blob_name).delete_blob()
        _logger.info('GuardLink PTT: deleted blob %s', blob_name)
        return True
    except Exception as exc:
        _logger.warning('GuardLink PTT: blob delete failed for %s: %s', blob_name, exc)
        return False


def is_configured():
    """True when the SDK is installed and connection string is set."""
    return _SDK_AVAILABLE and bool(_CONN_STR)
