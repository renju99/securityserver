"""Make Community name fields free-text (manual typing) on incident forms."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Dynamic incident form fields that were Salesforce dropdowns
    cr.execute(
        """
        UPDATE incident_form_field
           SET field_type = 'char',
               selection_options = NULL
         WHERE field_type = 'selection'
           AND (
                LOWER(name) LIKE '%%community name%%'
                OR LOWER(name) LIKE '%%community name as per%%'
           )
        """
    )
    _logger.info(
        'Converted Community name selection fields to char: %s',
        cr.rowcount,
    )
