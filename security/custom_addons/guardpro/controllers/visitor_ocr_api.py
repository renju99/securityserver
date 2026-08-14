# -*- coding: utf-8 -*-
"""HTTP JSON-RPC API: Emirates ID camera scan OCR (visitor management)."""

import base64
import logging

from odoo import http
from odoo.http import request

from odoo.addons.guardpro.common import emirates_id_ocr
from odoo.addons.guardpro.common.upload_validation import (
    MAX_OCR_IMAGE_BYTES,
    UploadValidationError,
    validate_b64_payload,
)

_logger = logging.getLogger(__name__)


def _validated_ocr_image_b64(payload, side_label):
    """Decode/validate OCR scan; return bare base64 for emirates_id_ocr."""
    try:
        validated = validate_b64_payload(
            payload,
            filename='%s.jpg' % side_label,
            content_type='image/jpeg',
            allow_video=False,
            allow_image=True,
            allow_audio=False,
            max_image_bytes=MAX_OCR_IMAGE_BYTES,
        )
    except UploadValidationError as exc:
        raise UploadValidationError(
            '%s image: %s' % (side_label.capitalize(), exc)
        ) from exc
    return base64.b64encode(validated['data']).decode('ascii')


class VisitorEmiratesIdOcrController(http.Controller):
    @http.route(
        "/guardpro/api/visitor/emirates_id_ocr",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def emirates_id_ocr_extract(self, front_image=None, back_image=None, **kwargs):
        """Run OCR on base64 JPEG/PNG images (data-URI allowed).

        Returns a dict of field names matching ``visitor.management`` plus
        ``warnings``. Images are not stored.
        """
        if not front_image and not back_image:
            return {
                "success": False,
                "error": "Provide at least one image (front_image or back_image).",
            }
        try:
            front_text = ""
            back_text = ""
            if front_image:
                front_b64 = _validated_ocr_image_b64(front_image, "front")
                front_text = emirates_id_ocr.image_bytes_to_text(front_b64, eid_side="front")
            if back_image:
                back_b64 = _validated_ocr_image_b64(back_image, "back")
                back_text = emirates_id_ocr.image_bytes_to_text(back_b64, eid_side="back")
            fields = emirates_id_ocr.extract_fields_from_ocr(front_text, back_text)
            # Do not return raw OCR text to the browser (PII / retention).
            fields.pop("raw_ocr_preview", None)
            fields["success"] = True
            return fields
        except UploadValidationError as e:
            return {"success": False, "error": str(e)}
        except RuntimeError as e:
            _logger.warning("Emirates ID OCR unavailable: %s", e)
            return {"success": False, "error": str(e)}
        except Exception as e:
            _logger.exception("Emirates ID OCR failed")
            return {"success": False, "error": str(e)}

    @http.route(
        "/guardpro/api/visitor/lookup_by_id",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def visitor_lookup_by_id(self, id_number=None, site_id=None, **kwargs):
        """Return prior visit details for a returning visitor (site-scoped).

        Searches only within the caller's assigned projects. Optional ``site_id``
        further narrows to one site and must be in the caller's assignments.
        """
        if not id_number or not str(id_number).strip():
            return {"success": False, "error": "id_number is required."}
        try:
            user = request.env.user
            if user.has_group("guardpro.group_guardpro_admin"):
                site_ids = None
                if site_id not in (None, False, ""):
                    try:
                        site_ids = [int(site_id)]
                    except (TypeError, ValueError):
                        return {"success": False, "error": "Invalid site_id."}
            else:
                allowed = list(user.site_ids.ids)
                if not allowed:
                    return {"success": True, "found": False, "fields": {}}
                if site_id not in (None, False, ""):
                    try:
                        sid = int(site_id)
                    except (TypeError, ValueError):
                        return {"success": False, "error": "Invalid site_id."}
                    if sid not in allowed:
                        return {"success": True, "found": False, "fields": {}}
                    site_ids = [sid]
                else:
                    site_ids = allowed

            # sudo + explicit site_ids so lookup cannot widen via missing rules
            Visitor = request.env["visitor.management"].sudo()
            data = Visitor.lookup_returning_visitor(
                str(id_number).strip(),
                site_ids=site_ids,
            )
            if not data:
                return {"success": True, "found": False, "fields": {}}
            return {
                "success": True,
                "found": True,
                "fields": data,
            }
        except Exception as e:
            _logger.exception("Visitor ID lookup failed")
            return {"success": False, "error": str(e)}
