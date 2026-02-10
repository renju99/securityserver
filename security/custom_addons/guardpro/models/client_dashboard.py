# -*- coding: utf-8 -*-
"""Client Dashboard with KPIs."""

from odoo import models, fields, api, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class ClientDashboard(models.Model):
    """Client portal dashboard with real-time KPIs."""
    
    _name = 'client.dashboard'
    _description = 'Client Dashboard'
    
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        domain=[('is_company', '=', True)]
    )
    
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        domain="[('client_id', '=', client_id)]"
    )
    
    date_from = fields.Date(
        string='From',
        default=lambda self: fields.Date.today() - timedelta(days=30)
    )
    
    date_to = fields.Date(
        string='To',
        default=fields.Date.today
    )
    
    # KPIs
    total_shifts = fields.Integer(
        string='Total Shifts',
        compute='_compute_kpis'
    )
    
    completed_shifts = fields.Integer(
        string='Completed Shifts',
        compute='_compute_kpis'
    )
    
    missed_shifts = fields.Integer(
        string='Missed/No-Show Shifts',
        compute='_compute_kpis'
    )
    
    shift_completion_rate = fields.Float(
        string='Completion Rate (%)',
        compute='_compute_kpis',
        digits=(5, 2)
    )
    
    total_incidents = fields.Integer(
        string='Total Incidents',
        compute='_compute_kpis'
    )
    
    critical_incidents = fields.Integer(
        string='Critical Incidents',
        compute='_compute_kpis'
    )
    
    resolved_incidents = fields.Integer(
        string='Resolved Incidents',
        compute='_compute_kpis'
    )
    
    incident_resolution_rate = fields.Float(
        string='Resolution Rate (%)',
        compute='_compute_kpis',
        digits=(5, 2)
    )
    
    total_tours = fields.Integer(
        string='Tours Completed',
        compute='_compute_kpis'
    )
    
    checkpoints_scanned = fields.Integer(
        string='Checkpoints Scanned',
        compute='_compute_kpis'
    )
    
    checkpoint_completion_rate = fields.Float(
        string='Checkpoint Completion (%)',
        compute='_compute_kpis',
        digits=(5, 2)
    )
    
    average_guard_rating = fields.Float(
        string='Average Guard Rating',
        compute='_compute_kpis',
        digits=(3, 2)
    )
    
    active_guards = fields.Integer(
        string='Active Guards',
        compute='_compute_kpis'
    )
    
    total_hours_worked = fields.Float(
        string='Total Hours Worked',
        compute='_compute_kpis',
        digits=(10, 2)
    )
    
    @api.depends('client_id', 'site_id', 'date_from', 'date_to')
    def _compute_kpis(self):
        """Compute all KPIs."""
        for record in self:
            domain = [
                ('create_date', '>=', record.date_from),
                ('create_date', '<=', record.date_to)
            ]
            
            site_domain = []
            if record.site_id:
                site_domain = [('site_id', '=', record.site_id.id)]
            elif record.client_id:
                sites = self.env['client.site'].search([('client_id', '=', record.client_id.id)])
                site_domain = [('site_id', 'in', sites.ids)]
            
            # Shift KPIs
            shifts = self.env['guard.shift'].search(domain + site_domain)
            record.total_shifts = len(shifts)
            record.completed_shifts = len(shifts.filtered(lambda s: s.status == 'completed'))
            record.missed_shifts = len(shifts.filtered(lambda s: s.status == 'no_show'))
            
            if record.total_shifts > 0:
                record.shift_completion_rate = (record.completed_shifts / record.total_shifts) * 100
            else:
                record.shift_completion_rate = 0.0
            
            # Incident KPIs
            incidents = self.env['incident.report'].search(domain + site_domain)
            record.total_incidents = len(incidents)
            record.critical_incidents = len(incidents.filtered(lambda i: i.severity == 'critical'))
            record.resolved_incidents = len(incidents.filtered(lambda i: i.status == 'resolved'))
            
            if record.total_incidents > 0:
                record.incident_resolution_rate = (record.resolved_incidents / record.total_incidents) * 100
            else:
                record.incident_resolution_rate = 0.0
            
            # Tour KPIs
            tours = self.env['tour.log'].search(domain + site_domain)
            record.total_tours = len(tours.filtered(lambda t: t.status == 'completed'))
            
            checkpoint_scans = self.env['checkpoint.scan'].search(domain + site_domain)
            record.checkpoints_scanned = len(checkpoint_scans)
            
            if record.total_tours > 0:
                expected_checkpoints = sum(tour.tour_id.total_checkpoints for tour in tours if tour.tour_id)
                if expected_checkpoints > 0:
                    record.checkpoint_completion_rate = (record.checkpoints_scanned / expected_checkpoints) * 100
                else:
                    record.checkpoint_completion_rate = 100.0
            else:
                record.checkpoint_completion_rate = 0.0
            
            # Guard Rating KPI
            if record.site_id:
                feedbacks = self.env['client.feedback'].search([
                    ('site_id', '=', record.site_id.id),
                    ('feedback_date', '>=', record.date_from),
                    ('feedback_date', '<=', record.date_to)
                ])
            else:
                feedbacks = self.env['client.feedback'].search([
                    ('client_id', '=', record.client_id.id),
                    ('feedback_date', '>=', record.date_from),
                    ('feedback_date', '<=', record.date_to)
                ])
            
            if feedbacks:
                total_rating = sum(int(f.overall_rating) for f in feedbacks)
                record.average_guard_rating = total_rating / len(feedbacks)
            else:
                record.average_guard_rating = 0.0
            
            # Active Guards
            if record.site_id:
                record.active_guards = len(set(shifts.mapped('guard_id')))
            else:
                record.active_guards = len(set(shifts.mapped('guard_id')))
            
            # Total Hours
            attendance = self.env['guard.attendance'].search(domain + site_domain)
            record.total_hours_worked = sum(att.duration for att in attendance if att.duration)
    
    def action_view_shifts(self):
        """View shifts for this period."""
        self.ensure_one()
        domain = [
            ('create_date', '>=', self.date_from),
            ('create_date', '<=', self.date_to)
        ]
        if self.site_id:
            domain.append(('site_id', '=', self.site_id.id))
        
        return {
            'name': _('Shifts'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift',
            'view_mode': 'list,form,calendar',
            'domain': domain
        }
    
    def action_view_incidents(self):
        """View incidents for this period."""
        self.ensure_one()
        domain = [
            ('create_date', '>=', self.date_from),
            ('create_date', '<=', self.date_to)
        ]
        if self.site_id:
            domain.append(('site_id', '=', self.site_id.id))
        
        return {
            'name': _('Incidents'),
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'view_mode': 'list,form',
            'domain': domain
        }
    
    def action_refresh_dashboard(self):
        """Refresh dashboard data."""
        self._compute_kpis()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Refreshed'),
                'message': _('Dashboard data has been refreshed.'),
                'type': 'success',
                'sticky': False,
            }
        }


class ClientSite(models.Model):
    """Extend client site with dashboard link."""
    
    _inherit = 'client.site'
    
    def action_view_dashboard(self):
        """Open client dashboard for this site."""
        self.ensure_one()
        
        # Find or create dashboard
        dashboard = self.env['client.dashboard'].search([
            ('site_id', '=', self.id)
        ], limit=1)
        
        if not dashboard:
            dashboard = self.env['client.dashboard'].create({
                'client_id': self.client_id.id,
                'site_id': self.id
            })
        
        return {
            'name': _('Dashboard: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'client.dashboard',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'target': 'current'
        }


class ResPartner(models.Model):
    """Extend partner with dashboard link."""
    
    _inherit = 'res.partner'
    
    def action_view_dashboard(self):
        """Open client dashboard for this client."""
        self.ensure_one()
        
        if not self.is_company:
            return
        
        # Find or create dashboard
        dashboard = self.env['client.dashboard'].search([
            ('client_id', '=', self.id),
            ('site_id', '=', False)
        ], limit=1)
        
        if not dashboard:
            dashboard = self.env['client.dashboard'].create({
                'client_id': self.id
            })
        
        return {
            'name': _('Client Dashboard: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'client.dashboard',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'target': 'current'
        }

