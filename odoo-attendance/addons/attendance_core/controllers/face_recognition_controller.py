# -*- coding: utf-8 -*-
import base64
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class AttendanceFaceController(http.Controller):
    """JSON-RPC style routes for kiosk / device integration (auth=user)."""

    @http.route('/attendance_core/face/enroll', type='json', auth='user', readonly=False)
    def face_enroll(self, employee_id, image_b64=None, **kwargs):
        """Store descriptor from optional base64 image; if no image, use employee's enrollment photo."""
        employee = request.env['hr.employee'].browse(int(employee_id))
        if not employee.exists():
            return {'ok': False, 'error': 'employee_not_found'}
        if not employee.has_access('write'):
            return {'ok': False, 'error': 'access_denied'}
        if image_b64:
            image_bytes = base64.b64decode(image_b64)
            employee.write({'attendance_face_image': base64.b64encode(image_bytes)})
        employee.action_bw_face_compute_descriptor()
        return {'ok': True}

    @http.route('/attendance_core/face/verify', type='json', auth='user', readonly=True)
    def face_verify(self, employee_id, image_b64, **kwargs):
        """Compare live image (base64) to stored descriptor."""
        employee = request.env['hr.employee'].browse(int(employee_id))
        if not employee.exists():
            return {'ok': False, 'error': 'employee_not_found'}
        if not employee.has_access('read'):
            return {'ok': False, 'error': 'access_denied'}
        if not image_b64:
            return {'ok': False, 'error': 'missing_image'}
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception:  # noqa: BLE001
            return {'ok': False, 'error': 'invalid_base64'}
        match, distance, code = employee._attendance_face_verify_image(image_bytes)
        if code == 'library_missing':
            return {'ok': False, 'error': 'face_recognition_not_installed'}
        if code == 'numpy_missing':
            return {'ok': False, 'error': 'numpy_not_installed'}
        if code == 'no_descriptor':
            return {'ok': False, 'error': 'no_descriptor'}
        if code == 'no_face':
            return {'ok': False, 'error': 'no_face_detected'}
        return {'ok': True, 'match': match, 'distance': distance, 'threshold': employee.attendance_face_match_threshold}
