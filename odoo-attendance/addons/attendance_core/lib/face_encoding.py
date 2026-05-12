# -*- coding: utf-8 -*-
"""Optional face encoding using the ``face_recognition`` library (dlib).

Install on the Odoo server when you need kiosk-style matching::

    pip install face_recognition

If the library is missing, APIs return a clear error instead of crashing.
"""
import io
import json
import logging

_logger = logging.getLogger(__name__)


def face_encodings_from_image_bytes(image_bytes: bytes):
    """Return a list of 128-float encodings (one per detected face), or None if library missing."""
    try:
        import face_recognition  # noqa: PLC0415
    except ImportError:
        _logger.info('face_recognition is not installed; face matching is unavailable.')
        return None
    image = face_recognition.load_image_file(io.BytesIO(image_bytes))
    encodings = face_recognition.face_encodings(image)
    if not encodings:
        return []
    return [e.tolist() for e in encodings]


def face_distance(encoding_a, encoding_b) -> float | None:
    """Euclidean distance between two 128-float lists (lower is more similar)."""
    try:
        import numpy as np  # noqa: PLC0415
    except ImportError:
        return None
    if not encoding_a or not encoding_b or len(encoding_a) != 128 or len(encoding_b) != 128:
        return None
    a = np.array(encoding_a, dtype=np.float64)
    b = np.array(encoding_b, dtype=np.float64)
    return float(np.linalg.norm(a - b))


def best_distance_to_reference(encodings: list, reference: list) -> float | None:
    """Minimum distance from reference to any encoding in the list."""
    if not encodings or not reference:
        return None
    best = None
    for enc in encodings:
        if len(enc) != 128:
            continue
        d = face_distance(enc, reference)
        if d is None:
            continue
        if best is None or d < best:
            best = d
    return best
