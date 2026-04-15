"""Migrate legacy enquiry codes (BID-*, New, empty) to RFP-NNN-XXX-YYYY per emirate + creation year."""

import logging
import re

from odoo import SUPERUSER_ID, api, fields

_logger = logging.getLogger(__name__)

_RFP_FULL = re.compile(r"^RFP-(\d+)-([A-Z]{3})-(\d{4})$")


def _legacy_needs_migration(code):
    if not code or not str(code).strip():
        return True
    s = str(code).strip()
    if s.lower() == "new":
        return True
    if s.upper().startswith("BID-"):
        return True
    return False


def _bucket_year(record):
    if record.create_date:
        return record.create_date.year
    return fields.Date.context_today(record).year


def _sync_rfp_sequences(env):
    """Set ir.sequence number_next so the next create() cannot duplicate an existing RFP code."""
    Project = env["bid.project"].sudo()
    Seq = env["ir.sequence"].sudo()
    max_n = {}
    for p in Project.search([]):
        code = (p.code or "").strip()
        m = _RFP_FULL.match(code)
        if not m or not p.emirate:
            continue
        n = int(m.group(1))
        y = int(m.group(3))
        key = (p.emirate, y)
        max_n[key] = max(max_n.get(key, 0), n)

    for (emirate_key, year), last_n in max_n.items():
        seq_code = f"bid.project.rfp.{emirate_key}.{year}"
        need_next = last_n + 1
        seq = Seq.search([("code", "=", seq_code)], limit=1)
        if not seq:
            Seq.create(
                {
                    "name": f"RFP references ({emirate_key}, {year})",
                    "code": seq_code,
                    "implementation": "standard",
                    "padding": 3,
                    "number_next": need_next,
                    "number_increment": 1,
                    "company_id": False,
                }
            )
        elif seq.number_next < need_next:
            seq.write({"number_next": need_next})


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Project = env["bid.project"].sudo()
    airport_by_emirate = dict(Project._RFP_EMIRATE_AIRPORT)

    all_projects = Project.search([])
    max_n = {}
    for p in all_projects:
        code = (p.code or "").strip()
        m = _RFP_FULL.match(code)
        if not m or not p.emirate:
            continue
        n = int(m.group(1))
        y = int(m.group(3))
        key = (p.emirate, y)
        max_n[key] = max(max_n.get(key, 0), n)

    legacy = all_projects.filtered(lambda p: _legacy_needs_migration(p.code))
    if not legacy:
        _logger.info("sales_bid_board: no legacy bid.project codes to migrate")
        _sync_rfp_sequences(env)
        return

    by_bucket = {}
    for p in legacy:
        em = p.emirate or "dubai"
        if em not in airport_by_emirate:
            _logger.warning(
                "sales_bid_board: skip migrate id=%s unknown emirate=%r code=%r",
                p.id,
                em,
                p.code,
            )
            continue
        y = _bucket_year(p)
        key = (em, y)
        by_bucket.setdefault(key, []).append(p)

    ctx = {"tracking_disable": True, "mail_create_nolog": True, "mail_notrack": True}
    migrated = 0

    for (emirate_key, year), records in sorted(by_bucket.items(), key=lambda x: (x[0][1], x[0][0])):
        records.sort(key=lambda r: r.id)
        airport = airport_by_emirate[emirate_key]
        next_n = max_n.get((emirate_key, year), 0) + 1
        for p in records:
            old_code = p.code
            new_code = f"RFP-{next_n:03d}-{airport}-{year}"
            p.with_context(**ctx).write({"code": new_code})
            _logger.info(
                "sales_bid_board: migrated bid.project id=%s code %r -> %r",
                p.id,
                old_code,
                new_code,
            )
            next_n += 1
            migrated += 1
        max_n[(emirate_key, year)] = next_n - 1

    env.flush_all()
    _sync_rfp_sequences(env)
    env.flush_all()
    _logger.info("sales_bid_board: migrated %s bid.project record(s) to RFP codes", migrated)
