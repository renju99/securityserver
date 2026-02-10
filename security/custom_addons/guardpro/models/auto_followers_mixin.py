# -*- coding: utf-8 -*-
"""
Auto Followers Mixin
Automatically subscribe relevant users to records for better notification management
"""

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class AutoFollowersMixin(models.AbstractModel):
    """Mixin to automatically subscribe relevant users to records."""
    
    _name = 'auto.followers.mixin'
    _description = 'Auto Followers Mixin'
    
    @api.model_create_multi
    def create(self, vals_list):
        """Subscribe relevant users on create."""
        records = super().create(vals_list)
        for record in records:
            record._subscribe_auto_followers()
        return records
    
    def write(self, vals):
        """Update followers when assignment changes."""
        result = super().write(vals)
        
        # Check if assignment fields changed
        assignment_fields = ['guard_id', 'assigned_to', 'manager_id', 'supervisor_id', 
                            'reviewed_by', 'approved_by', 'user_id']
        
        if any(field in vals for field in assignment_fields):
            for record in self:
                record._subscribe_auto_followers()
        
        return result
    
    def _subscribe_auto_followers(self):
        """
        Subscribe relevant users based on record type.
        Override this method in specific models to customize behavior.
        """
        self.ensure_one()
        partners_to_subscribe = []
        
        # Subscribe assigned users
        if hasattr(self, 'guard_id') and self.guard_id and self.guard_id.user_id:
            partners_to_subscribe.append(self.guard_id.user_id.partner_id.id)
        
        if hasattr(self, 'assigned_to') and self.assigned_to:
            if hasattr(self.assigned_to, 'user_id') and self.assigned_to.user_id:
                partners_to_subscribe.append(self.assigned_to.user_id.partner_id.id)
            elif hasattr(self.assigned_to, 'partner_id'):
                partners_to_subscribe.append(self.assigned_to.partner_id.id)
        
        # Subscribe site manager
        if hasattr(self, 'site_id') and self.site_id:
            if hasattr(self.site_id, 'site_manager_id') and self.site_id.site_manager_id:
                partners_to_subscribe.append(self.site_id.site_manager_id.partner_id.id)
            if hasattr(self.site_id, 'client_id') and self.site_id.client_id:
                partners_to_subscribe.append(self.site_id.client_id.id)
        
        # Subscribe reviewers/approvers
        for field in ['reviewed_by', 'approved_by', 'supervisor_id', 'manager_id']:
            if hasattr(self, field):
                user = getattr(self, field)
                if user and hasattr(user, 'partner_id'):
                    partners_to_subscribe.append(user.partner_id.id)
        
        # Remove duplicates and subscribe
        partners_to_subscribe = list(set(partners_to_subscribe))
        if partners_to_subscribe:
            try:
                self.message_subscribe(partner_ids=partners_to_subscribe)
                _logger.debug(
                    'Auto-subscribed %d partners to %s record %s',
                    len(partners_to_subscribe), self._name, self.id
                )
            except Exception as e:
                _logger.warning(
                    'Failed to auto-subscribe partners to %s: %s',
                    self._name, str(e)
                )


# Apply to specific models
# Temporarily disabled to resolve Many2many field conflicts (Oct 2025)
# TODO: Re-enable auto followers using a different approach
# class IncidentReportAutoFollowers(models.Model):
#     """Add auto followers to incident reports."""
#     _inherit = ['incident.report', 'auto.followers.mixin']
#     _description = 'Incident Report Auto Followers'
#     
#     def _subscribe_auto_followers(self):
#         """Subscribe incident-specific followers."""
#         super()._subscribe_auto_followers()
#         # Auto-subscribe security managers for critical incidents
#         if self.severity == 'critical':
#             security_managers = self.env.ref(
#                 'guardpro.group_guardpro_manager',
#                 raise_if_not_found=False
#             )
#             if security_managers:
#                 manager_partners = security_managers.users.mapped('partner_id.id')
#                 if manager_partners:
#                     try:
#                         self.message_subscribe(partner_ids=manager_partners)
#                     except Exception:
#                         pass


# class GuardShiftAutoFollowers(models.Model):
#     """Add auto followers to guard shifts."""
#     _inherit = ['guard.shift', 'auto.followers.mixin']
#     _description = 'Guard Shift Auto Followers'


# class GuardTaskAutoFollowers(models.Model):
#     """Add auto followers to guard tasks."""
#     _inherit = ['guard.task', 'auto.followers.mixin']
#     _description = 'Guard Task Auto Followers'


# class DailyActivityReportAutoFollowers(models.Model):
#     """Add auto followers to DARs."""
#     _inherit = ['daily.activity.report', 'auto.followers.mixin']
#     _description = 'Daily Activity Report Auto Followers'
#     
#     def _subscribe_auto_followers(self):
#         """Subscribe DAR-specific followers."""
#         super()._subscribe_auto_followers()
#         # Auto-subscribe submitter and reviewer
#         if self.submitted_by:
#             self.message_subscribe(partner_ids=[self.submitted_by.partner_id.id])
#         if self.reviewed_by:
#             self.message_subscribe(partner_ids=[self.reviewed_by.partner_id.id])


# class VisitorManagementAutoFollowers(models.Model):
#     """Add auto followers to visitor records."""
#     _inherit = ['visitor.management', 'auto.followers.mixin']
#     _description = 'Visitor Management Auto Followers'
#     
#     def _subscribe_auto_followers(self):
#         """Subscribe visitor-specific followers."""
#         super()._subscribe_auto_followers()
#         # Subscribe host if available
#         if hasattr(self, 'host_user_id') and self.host_user_id:
#             self.message_subscribe(partner_ids=[self.host_user_id.partner_id.id])


# class ComplianceAuditAutoFollowers(models.Model):
#     """Add auto followers to compliance audits."""
#     _inherit = ['compliance.audit', 'auto.followers.mixin']
#     _description = 'Compliance Audit Auto Followers'
#     
#     def _subscribe_auto_followers(self):
#         """Subscribe audit-specific followers."""
#         super()._subscribe_auto_followers()
#         # Subscribe auditor
#         if self.auditor_id:
#             self.message_subscribe(partner_ids=[self.auditor_id.partner_id.id])


# class EmergencyBroadcastAutoFollowers(models.Model):
#     """Add auto followers to emergency broadcasts."""
#     _inherit = ['emergency.broadcast', 'auto.followers.mixin']
#     _description = 'Emergency Broadcast Auto Followers'
#     
#     def _subscribe_auto_followers(self):
#         """Subscribe broadcast-specific followers."""
#         super()._subscribe_auto_followers()
#         # Subscribe issuer
#         if self.issued_by:
#             self.message_subscribe(partner_ids=[self.issued_by.partner_id.id])
#         if self.sent_by:
#             self.message_subscribe(partner_ids=[self.sent_by.partner_id.id])


# class PackageManagementAutoFollowers(models.Model):
#     """Add auto followers to package management."""
#     _inherit = ['package.management', 'auto.followers.mixin']
#     _description = 'Package Management Auto Followers'
#     
#     def _subscribe_auto_followers(self):
#         """Subscribe package-specific followers."""
#         super()._subscribe_auto_followers()
#         # Subscribe receiver
#         if self.received_by:
#             self.message_subscribe(partner_ids=[self.received_by.partner_id.id])

