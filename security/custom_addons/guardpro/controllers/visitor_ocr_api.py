# -*- coding: utf-8 -*-
"""HTTP JSON-RPC API: Emirates ID camera scan OCR (visitor management)."""

import logging

from odoo import http
from odoo.http import request

from odoo.addons.guardpro.common import emirates_id_ocr

_logger = logging.getLogger(__name__)


class VisitorEmiratesIdOcrController(http.Controller):
    @http.route(
        "/guardpro/api/visitor/emirates_id_ocr",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def emirates_id_ocr_extract(self, front_image=None, back_image=None, **kwargs):
        """Run OCR on base64 JPEG/PNG images (no ``data:`` prefix).

        Returns a dict of field names matching ``visitor.management`` plus
        ``warnings`` and ``raw_ocr_preview``. Images are not stored.
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
                front_text = emirates_id_ocr.image_bytes_to_text(front_image, eid_side="front")
            if back_image:
                back_text = emirates_id_ocr.image_bytes_to_text(back_image, eid_side="back")
            fields = emirates_id_ocr.extract_fields_from_ocr(front_text, back_text)
            # Do not return raw OCR text to the browser (PII / retention).
            fields.pop("raw_ocr_preview", None)
            fields["success"] = True
            return fields
        except RuntimeError as e:
            _logger.warning("Emirates ID OCR unavailable: %s", e)
            return {"success": False, "error": str(e)}
        except Exception as e:
            _logger.exception("Emirates ID OCR failed")
            return {"success": False, "error": str(e)}
