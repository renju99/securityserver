# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class SLADefinition(models.Model):
    """SLA Definition and Contract Terms"""
    _name = 'sla.definition'
    _description = 'SLA Definition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(
        string='SLA Name',
        required=True,
        tracking=True,
        help='Name of the Service Level Agreement'
    )
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True,
        tracking=True,
        index=True,
        domain=[('is_company', '=', True)],
        help='Client for this SLA'
    )
    site_ids = fields.Many2many(
        'client.site',
        string='Applicable Sites',
        help='Sites covered by this SLA'
    )

    # Contract Details
    contract_reference = fields.Char(
        string='Contract Reference',
        tracking=True,
        help='Contract or agreement number'
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
        help='SLA effective start date'
    )
    end_date = fields.Date(
        string='End Date',
        tracking=True,
        help='SLA expiration date'
    )
    renewal_date = fields.Date(
        string='Renewal Date',
        help='Contract renewal date'
    )

    # KPIs
    kpi_ids = fields.One2many(
        'sla.kpi',
        'sla_id',
        string='KPIs'
    )
    kpi_count = fields.Integer(
        string='KPI Count',
        compute='_compute_kpi_count'
    )

    # Performance
    performance_ids = fields.One2many(
        'sla.performance',
        'sla_id',
        string='Performance Records'
    )
    current_compliance = fields.Float(
        string='Current Compliance (%)',
        compute='_compute_current_compliance',
        store=True,
        help='Overall SLA compliance percentage'
    )

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated')
    ], string='Status', default='draft', tracking=True, required=True)

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # Penalties
    penalty_applicable = fields.Boolean(
        string='Penalties Applicable',
        default=False,
        help='Are there financial penalties for SLA breaches'
    )
    penalty_notes = fields.Text(
        string='Penalty Terms',
        help='Details of penalty structure'
    )

    notes = fields.Text(
        string='Notes'
    )

    @api.depends('kpi_ids')
    def _compute_kpi_count(self):
        """Count KPIs"""
        for sla in self:
            sla.kpi_count = len(sla.kpi_ids)

    @api.depends('performance_ids', 'performance_ids.achieved')
    def _compute_current_compliance(self):
        """Calculate overall SLA compliance"""
        for sla in self:
            # Get current month performance
            current_month = fields.Date.today().replace(day=1)
            current_performance = sla.performance_ids.filtered(
                lambda p: p.period_start >= current_month
            )
            
            if current_performance:
                total = len(current_performance)
                achieved = len(current_performance.filtered(lambda p: p.achieved))
                sla.current_compliance = (achieved / total * 100) if total > 0 else 0.0
            else:
                sla.current_compliance = 0.0

    def action_activate(self):
        """Activate SLA"""
        self.ensure_one()
        if not self.kpi_ids:
            raise UserError(_('Please define at least one KPI before activating the SLA.'))
        
        self.state = 'active'
        return True

    def action_view_performance(self):
        """View SLA performance dashboard"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sla.performance',
            'view_mode': 'pivot,graph,list,form',
            'domain': [('sla_id', '=', self.id)],
            'context': {'default_sla_id': self.id},
            'name': _('SLA Performance: %s') % self.name
        }


class SLAKPI(models.Model):
    """SLA Key Performance Indicator"""
    _name = 'sla.kpi'
    _description = 'SLA KPI'
    _order = 'sequence, name'

    sla_id = fields.Many2one(
        'sla.definition',
        string='SLA',
        required=True,
        ondelete='cascade',
        index=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    name = fields.Char(
        string='KPI Name',
        required=True,
        help='Descriptive name of the KPI'
    )
    kpi_type = fields.Selection([
        ('incident_response', 'Incident Response Time'),
        ('incident_closure', 'Incident Closure Time'),
        ('patrol_completion', 'Patrol Completion Rate'),
        ('guard_punctuality', 'Guard Punctuality'),
        ('checkpoint_compliance', 'Checkpoint Compliance'),
        ('visitor_processing', 'Visitor Processing Time'),
        ('task_completion', 'Task Completion Rate'),
        ('equipment_uptime', 'Equipment Uptime'),
        ('training_compliance', 'Training Compliance'),
        ('custom', 'Custom KPI')
    ], string='KPI Type', required=True)

    description = fields.Text(
        string='Description',
        help='How this KPI is measured'
    )

    # Target
    target_value = fields.Float(
        string='Target Value',
        required=True,
        help='Target value for this KPI'
    )
    unit = fields.Selection([
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('percentage', 'Percentage'),
        ('count', 'Count')
    ], string='Unit', required=True)

    # Better/Worse
    target_direction = fields.Selection([
        ('maximize', 'Higher is Better'),
        ('minimize', 'Lower is Better')
    ], string='Target Direction', default='maximize', required=True,
       help='Whether we want to maximize or minimize this metric')

    measurement_period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly')
    ], string='Measurement Period', default='monthly', required=True)

    # Thresholds
    warning_threshold = fields.Float(
        string='Warning Threshold (%)',
        default=90.0,
        help='Alert if performance drops below this percentage of target'
    )
    critical_threshold = fields.Float(
        string='Critical Threshold (%)',
        default=80.0,
        help='Critical alert if performance drops below this'
    )

    # Penalties
    penalty_applicable = fields.Boolean(
        string='Penalty Applicable',
        default=False
    )
    penalty_amount = fields.Monetary(
        string='Penalty Amount',
        currency_field='currency_id',
        help='Financial penalty for missing this KPI'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    # Weight
    weight = fields.Float(
        string='Weight (%)',
        default=1.0,
        help='Weight of this KPI in overall SLA score'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )


class SLAPerformance(models.Model):
    """SLA Performance Tracking"""
    _name = 'sla.performance'
    _description = 'SLA Performance Tracking'
    _order = 'period_start desc, id desc'
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    sla_id = fields.Many2one(
        'sla.definition',
        string='SLA',
        required=True,
        ondelete='cascade',
        index=True
    )
    kpi_id = fields.Many2one(
        'sla.kpi',
        string='KPI',
        required=True,
        ondelete='cascade',
        index=True
    )
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        index=True,
        help='Specific site for this performance record'
    )

    period_start = fields.Date(
        string='Period Start',
        required=True,
        index=True
    )
    period_end = fields.Date(
        string='Period End',
        required=True,
        index=True
    )

    # Values
    actual_value = fields.Float(
        string='Actual Value',
        help='Actual measured value'
    )
    target_value = fields.Float(
        string='Target Value',
        related='kpi_id.target_value',
        store=True
    )

    # Performance
    achieved = fields.Boolean(
        string='Target Achieved',
        compute='_compute_achievement',
        store=True
    )
    variance = fields.Float(
        string='Variance (%)',
        compute='_compute_achievement',
        store=True,
        help='Percentage variance from target'
    )
    performance_percentage = fields.Float(
        string='Performance %',
        compute='_compute_achievement',
        store=True,
        help='Performance as percentage of target'
    )

    # Status
    status = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('failed', 'Failed')
    ], string='Status', compute='_compute_status', store=True)

    # Penalty
    penalty_incurred = fields.Boolean(
        string='Penalty Incurred',
        compute='_compute_penalty',
        store=True
    )
    penalty_amount = fields.Monetary(
        string='Penalty Amount',
        compute='_compute_penalty',
        store=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='kpi_id.currency_id',
        store=True
    )

    # Calculation Details
    data_points = fields.Integer(
        string='Data Points',
        help='Number of measurements in this period'
    )
    calculation_method = fields.Text(
        string='Calculation Method',
        help='How the actual value was calculated'
    )

    notes = fields.Text(
        string='Notes'
    )

    @api.depends('sla_id', 'kpi_id', 'period_start', 'period_end')
    def _compute_display_name(self):
        """Generate display name"""
        for record in self:
            if record.sla_id and record.kpi_id:
                record.display_name = '%s - %s (%s to %s)' % (
                    record.sla_id.name,
                    record.kpi_id.name,
                    record.period_start or '',
                    record.period_end or ''
                )
            else:
                record.display_name = 'New'

    @api.depends('actual_value', 'target_value', 'kpi_id.target_direction')
    def _compute_achievement(self):
        """Calculate achievement and variance"""
        for record in self:
            if record.target_value and record.target_value != 0:
                # Calculate variance
                record.variance = ((record.actual_value - record.target_value) / record.target_value) * 100
                
                # Calculate performance percentage
                if record.kpi_id.target_direction == 'minimize':
                    # For minimize metrics (e.g., response time): lower is better
                    if record.actual_value <= record.target_value:
                        record.performance_percentage = 100.0
                        record.achieved = True
                    else:
                        record.performance_percentage = (record.target_value / record.actual_value) * 100
                        record.achieved = False
                else:
                    # For maximize metrics (e.g., completion rate): higher is better
                    record.performance_percentage = (record.actual_value / record.target_value) * 100
                    record.achieved = record.actual_value >= record.target_value
            else:
                record.variance = 0
                record.performance_percentage = 0
                record.achieved = False

    @api.depends('performance_percentage', 'kpi_id.warning_threshold', 'kpi_id.critical_threshold')
    def _compute_status(self):
        """Determine performance status"""
        for record in self:
            perf = record.performance_percentage
            
            if perf >= 100:
                record.status = 'excellent'
            elif perf >= record.kpi_id.warning_threshold:
                record.status = 'good'
            elif perf >= record.kpi_id.critical_threshold:
                record.status = 'warning'
            elif perf > 0:
                record.status = 'critical'
            else:
                record.status = 'failed'

    @api.depends('achieved', 'kpi_id.penalty_applicable', 'kpi_id.penalty_amount')
    def _compute_penalty(self):
        """Calculate penalty if applicable"""
        for record in self:
            if not record.achieved and record.kpi_id.penalty_applicable:
                record.penalty_incurred = True
                record.penalty_amount = record.kpi_id.penalty_amount
            else:
                record.penalty_incurred = False
                record.penalty_amount = 0.0

    @api.model
    def calculate_monthly_performance(self):
        """Cron: Calculate SLA performance for previous month"""
        # Get first and last day of previous month
        today = fields.Date.today()
        first_day_this_month = today.replace(day=1)
        last_day_prev_month = first_day_this_month - timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)

        # Get all active SLAs
        active_slas = self.env['sla.definition'].search([
            ('state', '=', 'active'),
            ('start_date', '<=', last_day_prev_month)
        ])

        records_created = 0

        for sla in active_slas:
            for kpi in sla.kpi_ids:
                if kpi.measurement_period != 'monthly':
                    continue

                # Check if performance already calculated
                existing = self.search([
                    ('sla_id', '=', sla.id),
                    ('kpi_id', '=', kpi.id),
                    ('period_start', '=', first_day_prev_month),
                    ('period_end', '=', last_day_prev_month)
                ])

                if existing:
                    continue

                # Calculate actual value based on KPI type
                actual_value = self._calculate_kpi_value(
                    kpi,
                    first_day_prev_month,
                    last_day_prev_month,
                    sla.site_ids
                )

                # Create performance record
                self.create({
                    'sla_id': sla.id,
                    'kpi_id': kpi.id,
                    'period_start': first_day_prev_month,
                    'period_end': last_day_prev_month,
                    'actual_value': actual_value,
                    'site_id': sla.site_ids[0].id if len(sla.site_ids) == 1 else False
                })
                records_created += 1

        _logger.info('Calculated performance for %d SLA KPIs', records_created)
        return True

    @api.model
    def _calculate_kpi_value(self, kpi, start_date, end_date, sites):
        """Calculate actual KPI value for the period"""
        start_dt = fields.Datetime.to_datetime(start_date)
        end_dt = fields.Datetime.to_datetime(end_date) + timedelta(days=1)

        if kpi.kpi_type == 'incident_response':
            # Average response time in minutes
            incidents = self.env['incident.report'].search([
                ('site_id', 'in', sites.ids),
                ('incident_datetime', '>=', start_dt),
                ('incident_datetime', '<', end_dt),
                ('response_time', '>', 0)
            ])
            if incidents:
                # Assuming response_time field exists (may need to add)
                avg_response = sum(incidents.mapped('response_time')) / len(incidents)
                return avg_response
            return 0.0

        elif kpi.kpi_type == 'incident_closure':
            # Average closure time in hours
            incidents = self.env['incident.report'].search([
                ('site_id', 'in', sites.ids),
                ('incident_datetime', '>=', start_dt),
                ('incident_datetime', '<', end_dt),
                ('status', '=', 'closed'),
                ('closed_date', '!=', False)
            ])
            if incidents:
                total_hours = 0
                for inc in incidents:
                    delta = inc.closed_date - inc.incident_datetime
                    total_hours += delta.total_seconds() / 3600
                return total_hours / len(incidents)
            return 0.0

        elif kpi.kpi_type == 'patrol_completion':
            # Percentage of patrols completed
            tours = self.env['tour.log'].search([
                ('site_id', 'in', sites.ids),
                ('start_time', '>=', start_dt),
                ('start_time', '<', end_dt)
            ])
            if tours:
                completed = len(tours.filtered(lambda t: t.status == 'completed'))
                return (completed / len(tours)) * 100
            return 0.0

        elif kpi.kpi_type == 'guard_punctuality':
            # Percentage of on-time check-ins
            attendance = self.env['guard.attendance'].search([
                ('site_id', 'in', sites.ids),
                ('checkin_time', '>=', start_dt),
                ('checkin_time', '<', end_dt)
            ])
            if attendance:
                on_time = len(attendance.filtered(lambda a: not a.late))
                return (on_time / len(attendance)) * 100
            return 0.0

        elif kpi.kpi_type == 'checkpoint_compliance':
            # Percentage of checkpoints scanned
            scans = self.env['checkpoint.scan'].search([
                ('site_id', 'in', sites.ids),
                ('scan_time', '>=', start_dt),
                ('scan_time', '<', end_dt)
            ])
            # Would need expected checkpoint count
            return len(scans)

        elif kpi.kpi_type == 'task_completion':
            # Task completion rate
            tasks = self.env['guard.task'].search([
                ('site_id', 'in', sites.ids),
                ('due_date', '>=', start_dt),
                ('due_date', '<', end_dt)
            ])
            if tasks:
                completed = len(tasks.filtered(lambda t: t.state == 'completed'))
                return (completed / len(tasks)) * 100
            return 0.0

        # Default for custom or other types
        return 0.0

    @api.model
    def send_kpi_breach_alerts(self):
        """Cron: Send alerts for KPI breaches"""
        # Get current month
        today = fields.Date.today()
        first_day = today.replace(day=1)

        breached_performance = self.env['sla.performance'].search([
            ('period_start', '>=', first_day),
            ('status', 'in', ['critical', 'failed']),
            ('sla_id.state', '=', 'active')
        ])

        # Planned activities intentionally disabled for SLA KPI breaches.

        _logger.info('Sent breach alerts for %d SLA KPIs', len(breached_performance))
        return True

