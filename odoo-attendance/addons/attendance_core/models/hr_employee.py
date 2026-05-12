# -*- coding: utf-8 -*-
import base64
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.attendance_core.lib import face_encoding

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    attendance_face_image = fields.Image(
        string='Face enrollment (photo)',
        max_width=1920,
        max_height=1920,
        help='Reference photo. When the optional Python package face_recognition is installed '
             'on the server, use “Compute face descriptor” to store a 128-d embedding for matching.',
    )
    attendance_face_descriptor_json = fields.Text(
        string='Face descriptor (128-d)',
        copy=False,
        groups='hr.group_hr_user',
        help='JSON array of 128 floats produced from the enrollment photo (face_recognition/dlib).',
    )
    attendance_face_match_threshold = fields.Float(
        string='Face match threshold (distance)',
        default=0.52,
        groups='hr.group_hr_user',
        help='Lower is stricter. Typical same-person distances are about 0.35–0.55 with dlib models.',
    )

    def _attendance_face_image_bytes(self):
        self.ensure_one()
        raw = self.attendance_face_image
        if not raw:
            return None
        if isinstance(raw, bytes):
            return raw
        if isinstance(raw, memoryview):
            raw = raw.tobytes()
        if isinstance(raw, str):
            return base64.b64decode(raw)
        return base64.b64decode(base64.b64encode(raw))

    def action_bw_face_compute_descriptor(self):
        """Compute embedding from ``attendance_face_image`` (button for HR)."""
        for emp in self:
            data = emp._attendance_face_image_bytes()
            if not data:
                raise UserError(_('Upload a face enrollment photo first.'))
            encodings = face_encoding.face_encodings_from_image_bytes(data)
            if encodings is None:
                raise UserError(
                    _('The face_recognition Python library is not installed on this server. '
                      'Ask your administrator to install it (see requirements-optional.txt), then retry.')
                )
            if len(encodings) == 0:
                raise UserError(_('No face was detected in the image. Use a clearer frontal photo.'))
            if len(encodings) > 1:
                raise UserError(_('Several faces were detected; use a photo with a single face.'))
            emp.attendance_face_descriptor_json = json.dumps(encodings[0])
        return True

    def _attendance_face_get_reference_encoding(self):
        self.ensure_one()
        if not self.attendance_face_descriptor_json:
            return None
        try:
            ref = json.loads(self.attendance_face_descriptor_json.strip())
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(ref, list) or len(ref) != 128:
            return None
        return ref

    def _attendance_face_verify_image(self, image_bytes: bytes):
        """Return (ok: bool, distance: float|None, message: str)."""
        self.ensure_one()
        ref = self._attendance_face_get_reference_encoding()
        if not ref:
            return False, None, 'no_descriptor'
        encodings = face_encoding.face_encodings_from_image_bytes(image_bytes)
        if encodings is None:
            return False, None, 'library_missing'
        if not encodings:
            return False, None, 'no_face'
        dist = face_encoding.best_distance_to_reference(encodings, ref)
        if dist is None:
            return False, None, 'numpy_missing'
        thr = self.attendance_face_match_threshold or 0.52
        return dist <= thr, dist, 'ok'
