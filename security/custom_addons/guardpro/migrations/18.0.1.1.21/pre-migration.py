# -*- coding: utf-8 -*-
"""
Before module data loads during upgrade, move shift.template rows off
module-defined client.site records (guardpro XML ids).

Otherwise ir.model.data cleanup can try to unlink those sites while
shift_template.site_id still references them → shift_template_site_id_fkey.

Templates are not deleted; only site_id is updated when a non-XML site exists.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT imd.res_id
        FROM ir_model_data imd
        WHERE imd.module = 'guardpro'
          AND imd.model = 'client.site'
          AND imd.res_id IS NOT NULL
        """
    )
    xml_site_ids = [row[0] for row in cr.fetchall()]
    if not xml_site_ids:
        return

    cr.execute(
        """
        SELECT COUNT(*) FROM shift_template WHERE site_id IN %s
        """,
        (tuple(xml_site_ids),),
    )
    blocked = cr.fetchone()[0]
    if not blocked:
        return

    cr.execute(
        """
        SELECT id FROM client_site
        WHERE id NOT IN %s
        ORDER BY id
        LIMIT 1
        """,
        (tuple(xml_site_ids),),
    )
    row = cr.fetchone()
    if not row:
        _logger.warning(
            "guardpro pre-migration: %s shift template(s) reference only "
            "module-defined client.site rows; no alternate site to reassign. "
            "Upgrade may fail until you add another site or reassign templates.",
            blocked,
        )
        return

    target_id = row[0]
    cr.execute(
        """
        UPDATE shift_template
        SET site_id = %s
        WHERE site_id IN %s
        """,
        (target_id, tuple(xml_site_ids)),
    )
    n = cr.rowcount
    _logger.info(
        "guardpro pre-migration: reassigned %s shift template(s) from "
        "module-defined site(s) %s to client.site id %s (FK safety for upgrade).",
        n,
        xml_site_ids,
        target_id,
    )
