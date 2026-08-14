# -*- coding: utf-8 -*-
"""Upload validation — type/size/filename allowlists for media attachments."""

import base64
import logging
import os
import re

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Limits (bytes)
MAX_IMAGE_BYTES = 10 * 1024 * 1024       # 10 MB raw upload
MAX_VIDEO_BYTES = 50 * 1024 * 1024       # 50 MB raw upload
MAX_AUDIO_BYTES = 10 * 1024 * 1024       # 10 MB voice notes
MAX_FILES_PER_REQUEST = 10
# OCR is CPU-heavy; keep ID card scans smaller than general photo uploads
MAX_OCR_IMAGE_BYTES = 8 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = frozenset({
    '.jpg', '.jpeg', '.png', '.gif', '.webp',
})
ALLOWED_VIDEO_EXTENSIONS = frozenset({
    '.mp4', '.mov', '.webm', '.m4v', '.3gp',
})
ALLOWED_AUDIO_EXTENSIONS = frozenset({
    '.mp3', '.m4a', '.aac', '.wav', '.ogg', '.webm', '.opus',
})

ALLOWED_IMAGE_MIMETYPES = frozenset({
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/gif',
    'image/webp',
})
ALLOWED_VIDEO_MIMETYPES = frozenset({
    'video/mp4',
    'video/quicktime',
    'video/webm',
    'video/3gpp',
    'video/x-m4v',
})
ALLOWED_AUDIO_MIMETYPES = frozenset({
    'audio/mpeg',
    'audio/mp3',
    'audio/mp4',
    'audio/aac',
    'audio/wav',
    'audio/x-wav',
    'audio/ogg',
    'audio/webm',
    'audio/opus',
})

# Magic-byte signatures (prefix match)
_IMAGE_MAGIC = (
    (b'\xff\xd8\xff', 'image/jpeg'),          # JPEG
    (b'\x89PNG\r\n\x1a\n', 'image/png'),      # PNG
    (b'GIF87a', 'image/gif'),
    (b'GIF89a', 'image/gif'),
    (b'RIFF', 'image/webp'),                  # WebP is RIFF....WEBP
)


class UploadValidationError(UserError):
    """Raised when an upload fails validation."""


def sanitize_filename(filename, default='upload.bin'):
    """Return a safe basename without path components."""
    if not filename:
        return default
    name = os.path.basename(str(filename).replace('\\', '/'))
    name = name.strip().lstrip('.')
    # Keep alnum, dash, underscore, dot
    name = re.sub(r'[^A-Za-z0-9._-]+', '_', name)
    if not name or name in ('.', '..'):
        return default
    return name[:180]


def _ext(filename):
    return os.path.splitext((filename or '').lower())[1]


def _sniff_image_mimetype(data):
    if not data or len(data) < 12:
        return None
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    return None


def _sniff_video_mimetype(data):
    """Best-effort video signature check (mp4/mov/3gp share ISO BMFF)."""
    if not data or len(data) < 12:
        return None
    # ISO BMFF: size(4) + 'ftyp'
    if data[4:8] == b'ftyp':
        brand = data[8:12]
        # Common audio brands — not video
        if brand in (b'M4A ', b'M4B ', b'mp4a'):
            return None
        return 'video/mp4'
    # WebM / Matroska
    if data[:4] == b'\x1a\x45\xdf\xa3':
        return 'video/webm'
    return None


def _sniff_audio_mimetype(data):
    """Best-effort audio signature check."""
    if not data or len(data) < 12:
        return None
    if data[:3] == b'ID3' or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return 'audio/mpeg'
    if data[:4] == b'OggS':
        return 'audio/ogg'
    if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
        return 'audio/wav'
    if data[4:8] == b'ftyp' and data[8:12] in (b'M4A ', b'M4B ', b'mp4a'):
        return 'audio/mp4'
    # WebM/Opus voice notes (same EBML header as video/webm)
    if data[:4] == b'\x1a\x45\xdf\xa3':
        return 'audio/webm'
    return None


def decode_payload_to_bytes(payload_data):
    """Decode base64 / data-URI / bytes to raw bytes."""
    if payload_data is None:
        return None
    if isinstance(payload_data, bytes):
        # Might already be raw, or ascii base64
        try:
            # Prefer treating as raw if looks like binary image/video
            if payload_data[:3] == b'\xff\xd8\xff' or payload_data[:8] == b'\x89PNG\r\n\x1a\n':
                return payload_data
            return base64.b64decode(payload_data, validate=False)
        except Exception:
            return payload_data
    s = str(payload_data).strip()
    if s.startswith('data:'):
        comma = s.find(',')
        if comma != -1:
            s = s[comma + 1:].strip()
    try:
        return base64.b64decode(s, validate=False)
    except Exception:
        return None


def validate_media_bytes(
    data,
    filename=None,
    content_type=None,
    allow_video=True,
    allow_image=True,
    allow_audio=False,
    max_image_bytes=None,
):
    """
    Validate media bytes for type and size.

    Returns dict: {data, filename, mimetype, is_video, is_audio}
    Raises UploadValidationError on failure.
    """
    if not data:
        raise UploadValidationError('Empty upload.')

    safe_name = sanitize_filename(filename, default='media.bin')
    ext = _ext(safe_name)
    claimed = (content_type or '').split(';')[0].strip().lower()
    image_limit = max_image_bytes or MAX_IMAGE_BYTES

    sniffed_image = _sniff_image_mimetype(data) if allow_image else None
    sniffed_video = _sniff_video_mimetype(data) if allow_video else None
    sniffed_audio = _sniff_audio_mimetype(data) if allow_audio else None

    is_video = False
    is_audio = False
    mimetype = None

    if sniffed_image and allow_image:
        is_video = False
        mimetype = sniffed_image
        if ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
            safe_name = os.path.splitext(safe_name)[0] + {
                'image/jpeg': '.jpg',
                'image/png': '.png',
                'image/gif': '.gif',
                'image/webp': '.webp',
            }.get(mimetype, '.jpg')
    elif sniffed_video and allow_video:
        is_video = True
        mimetype = sniffed_video
        if ext and ext not in ALLOWED_VIDEO_EXTENSIONS:
            safe_name = os.path.splitext(safe_name)[0] + '.mp4'
    elif sniffed_audio and allow_audio:
        is_audio = True
        mimetype = sniffed_audio
        if ext and ext not in ALLOWED_AUDIO_EXTENSIONS:
            safe_name = os.path.splitext(safe_name)[0] + {
                'audio/mpeg': '.mp3',
                'audio/ogg': '.ogg',
                'audio/wav': '.wav',
                'audio/mp4': '.m4a',
                'audio/webm': '.webm',
            }.get(mimetype, '.webm')
    else:
        if allow_image and (
            ext in ALLOWED_IMAGE_EXTENSIONS
            or claimed in ALLOWED_IMAGE_MIMETYPES
        ):
            raise UploadValidationError(
                'Unsupported or invalid image file. Use JPEG, PNG, GIF, or WebP.'
            )
        if allow_video and (
            ext in ALLOWED_VIDEO_EXTENSIONS
            or claimed in ALLOWED_VIDEO_MIMETYPES
            or (claimed or '').startswith('video/')
        ):
            raise UploadValidationError(
                'Unsupported or invalid video file. Use MP4, MOV, or WebM.'
            )
        if allow_audio and (
            ext in ALLOWED_AUDIO_EXTENSIONS
            or claimed in ALLOWED_AUDIO_MIMETYPES
            or (claimed or '').startswith('audio/')
        ):
            raise UploadValidationError(
                'Unsupported or invalid audio file.'
            )
        kinds = []
        if allow_image:
            kinds.append('images')
        if allow_video:
            kinds.append('videos')
        if allow_audio:
            kinds.append('audio')
        raise UploadValidationError(
            'File type not allowed. Only %s are accepted.' % (' / '.join(kinds) or 'media')
        )

    if is_video:
        max_size = MAX_VIDEO_BYTES
        kind = 'video'
    elif is_audio:
        max_size = MAX_AUDIO_BYTES
        kind = 'audio'
    else:
        max_size = image_limit
        kind = 'image'
    if len(data) > max_size:
        limit_mb = max_size // (1024 * 1024)
        raise UploadValidationError(
            'File too large (max %s MB for %s).' % (limit_mb, kind)
        )

    blocked_claimed = {
        'text/html', 'application/javascript', 'text/javascript',
        'application/x-msdownload', 'application/x-sh', 'application/x-httpd-php',
        'application/xhtml+xml', 'text/xml', 'application/xml',
    }
    if claimed in blocked_claimed:
        _logger.warning(
            'Rejected upload with dangerous claimed content-type %s (%s)',
            claimed, safe_name,
        )
        raise UploadValidationError('File content-type not allowed.')

    return {
        'data': data,
        'filename': safe_name,
        'mimetype': mimetype,
        'is_video': is_video,
        'is_audio': is_audio,
    }


def validate_werkzeug_file(
    uploaded_file, allow_video=True, allow_image=True, allow_audio=False,
):
    """Validate a Werkzeug FileStorage upload; returns validate_media_bytes result."""
    if not uploaded_file or not getattr(uploaded_file, 'filename', None):
        raise UploadValidationError('No file uploaded.')
    raw = uploaded_file.read()
    return validate_media_bytes(
        raw,
        filename=uploaded_file.filename,
        content_type=getattr(uploaded_file, 'content_type', None),
        allow_video=allow_video,
        allow_image=allow_image,
        allow_audio=allow_audio,
    )


def validate_json_media_payload(
    payload, allow_video=True, allow_image=True, allow_audio=False,
):
    """Validate a JSON {name, mimetype/content_type, data} media payload."""
    payload = payload or {}
    raw = decode_payload_to_bytes(payload.get('data'))
    if not raw:
        raise UploadValidationError('Invalid or empty media data.')
    return validate_media_bytes(
        raw,
        filename=payload.get('name'),
        content_type=payload.get('mimetype') or payload.get('content_type'),
        allow_video=allow_video,
        allow_image=allow_image,
        allow_audio=allow_audio,
    )


def validate_b64_payload(
    payload_data,
    filename=None,
    content_type=None,
    allow_video=False,
    allow_image=True,
    allow_audio=False,
    max_image_bytes=None,
):
    """Validate a bare base64 / data-URI string (OCR / smart-feature payloads)."""
    raw = decode_payload_to_bytes(payload_data)
    if not raw:
        raise UploadValidationError('Invalid or empty media data.')
    return validate_media_bytes(
        raw,
        filename=filename,
        content_type=content_type,
        allow_video=allow_video,
        allow_image=allow_image,
        allow_audio=allow_audio,
        max_image_bytes=max_image_bytes,
    )
