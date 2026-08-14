# -*- coding: utf-8 -*-
"""Link operational records to a physical Site under a Project."""

from odoo import models, fields


class IncidentReportGuardSite(models.Model):
    _inherit = 'incident.report'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class GuardAttendanceGuardSite(models.Model):
    _inherit = 'guard.attendance'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class GuardShiftGuardSite(models.Model):
    _inherit = 'guard.shift'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class GuardTaskGuardSite(models.Model):
    _inherit = 'guard.task'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class VisitorManagementGuardSite(models.Model):
    _inherit = 'visitor.management'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class TourLogGuardSite(models.Model):
    _inherit = 'tour.log'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class SecurityTourGuardSite(models.Model):
    _inherit = 'security.tour'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class CheckpointGuardSite(models.Model):
    _inherit = 'checkpoint'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class LostFoundGuardSite(models.Model):
    _inherit = 'lost.found.item'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class PackageManagementGuardSite(models.Model):
    _inherit = 'package.management'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class KeyRegisterGuardSite(models.Model):
    _inherit = 'key.register'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )


class ComplianceAuditGuardSite(models.Model):
    _inherit = 'compliance.audit'
    guard_site_id = fields.Many2one(
        'guard.site', string='Site', index=True, ondelete='set null',
        domain="[('project_id', '=', site_id)]",
    )
