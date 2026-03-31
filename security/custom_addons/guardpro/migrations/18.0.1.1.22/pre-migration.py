# -*- coding: utf-8 -*-
"""
Before module data loads during upgrade, move client.site.client_id off
module-defined res.partner rows (guardpro XML ids).

Otherwise ir.model.data cleanup can try to unlink demo partners (e.g. client_nshama)
while client_site rows still reference them → client_site_client_id_fkey.

Sites are not deleted; only client_id is updated when a non-XML company partner exists.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT imd.res_id
        FROM ir_model_data imd
        WHERE imd.module = 'guardpro'
          AND imd.model = 'res.partner'
          AND imd.res_id IS NOT NULL
        """
    )
    xml_partner_ids = [row[0] for row in cr.fetchall()]
    if not xml_partner_ids:
        return

    cr.execute(
        """
        SELECT COUNT(*) FROM client_site WHERE client_id IN %s
        """,
        (tuple(xml_partner_ids),),
    )
    blocked = cr.fetchone()[0]
    if not blocked:
        return

    cr.execute(
        """
        SELECT id FROM res_partner
        WHERE is_company IS TRUE
          AND id NOT IN %s
        ORDER BY id
        LIMIT 1
        """,
        (tuple(xml_partner_ids),),
    )
    row = cr.fetchone()
    if not row:
        _logger.warning(
            "guardpro pre-migration: %s client.site row(s) reference only "
            "module-defined res.partner rows; no alternate company partner to reassign. "
            "Upgrade may fail until you add another client company or reassign sites.",
            blocked,
        )
        return

    target_id = row[0]
    cr.execute(
        """
        UPDATE client_site
        SET client_id = %s
        WHERE client_id IN %s
        """,
        (target_id, tuple(xml_partner_ids)),
    )
    n = cr.rowcount
    _logger.info(
        "guardpro pre-migration: set client_id to res.partner %s on %s client.site "
        "row(s) (was module-defined partner(s) %s; FK safety for upgrade).",
        target_id,
        n,
        xml_partner_ids,
    )

    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'sla_definition'
        )
        """
    )
    if cr.fetchone()[0]:
        cr.execute(
            """
            UPDATE sla_definition
            SET client_id = %s
            WHERE client_id IN %s
            """,
            (target_id, tuple(xml_partner_ids)),
        )
        sla_n = cr.rowcount
        if sla_n:
            _logger.info(
                "guardpro pre-migration: set client_id on %s sla_definition row(s).",
                sla_n,
            )
