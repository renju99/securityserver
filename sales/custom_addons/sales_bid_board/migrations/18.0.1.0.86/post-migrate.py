"""Map legacy bid.project / bid.proposal industry selection keys to the new list."""

import logging

_logger = logging.getLogger(__name__)

_LEGACY_INDUSTRY_MAP = {
    "real_estate": "real_estate_property",
    "hospitality": "hospitality_tourism_wellness",
    "retail": "retail_other",
    "healthcare": "healthcare_clinic",
    "education": "nonprofit_social_education",
    "government": "government_public_admin",
    "other": "other",
}


def migrate(cr, version):
    for old, new in _LEGACY_INDUSTRY_MAP.items():
        cr.execute(
            "UPDATE bid_project SET industry = %s WHERE industry = %s",
            (new, old),
        )
        n = cr.rowcount
        if n:
            _logger.info(
                "sales_bid_board: migrated %s bid.project industry %r -> %r",
                n,
                old,
                new,
            )
        cr.execute(
            "UPDATE bid_proposal SET industry = %s WHERE industry = %s",
            (new, old),
        )
        n2 = cr.rowcount
        if n2:
            _logger.info(
                "sales_bid_board: migrated %s bid.proposal industry %r -> %r",
                n2,
                old,
                new,
            )
