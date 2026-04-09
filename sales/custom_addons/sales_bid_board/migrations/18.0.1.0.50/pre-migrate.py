"""Clear legacy free-text scope values before column becomes Selection."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE crm_lead
        SET bid_intake_scope_of_work = NULL
        WHERE bid_intake_scope_of_work IS NOT NULL
          AND bid_intake_scope_of_work NOT IN (
              'ifm', 'cleaning', 'maintenance', 'landscape', 'laundry', 'security'
          )
        """
    )
