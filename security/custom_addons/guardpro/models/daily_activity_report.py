# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from ..common.image_optimizer import ImageOptimizer
import logging

_logger = logging.getLogger(__name__)


class DailyActivityReport(models.Model):
    """Daily Activity Report (DAR)"""
    _name = 'daily.activity.report'
    _description = 'Daily Activity Report (DAR)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'report_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Report Reference',
        required=True,
        default='New',
        copy=False,
        readonly=True,
        index=True,
        help='Unique report reference'
    )

    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        tracking=True,
        index=True,
        ondelete='cascade',
        help='Site for this report'
    )
    report_date = fields.Date(
        string='Report Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        index=True,
        help='Date of activities covered'
    )
    shift_id = fields.Many2one(
        'guard.shift',
        string='Shift',
        help='Specific shift if applicable'
    )

    # Auto-populated Activity Sections
    incident_ids = fields.Many2many(
        'incident.report',
        string='Incidents',
        compute='_compute_activities',
        store=True,
        help='Incidents that occurred on this date'
    )
    incident_count = fields.Integer(
        string='Incident Count',
        compute='_compute_counts',
        store=True
    )

    tour_log_ids = fields.Many2many(
        'tour.log',
        string='Patrol Logs',
        compute='_compute_activities',
        store=True,
        help='Security tours completed'
    )
    tour_count = fields.Integer(
        string='Tour Count',
        compute='_compute_counts',
        store=True
    )

    visitor_ids = fields.Many2many(
        'visitor.management',
        string='Visitors',
        compute='_compute_activities',
        store=True,
        help='Visitors checked in/out'
    )
    visitor_count = fields.Integer(
        string='Visitor Count',
        compute='_compute_counts',
        store=True
    )

    attendance_ids = fields.Many2many(
        'guard.attendance',
        string='Attendance Records',
        compute='_compute_activities',
        store=True,
        help='Guard attendance for the day'
    )
    guards_on_duty_count = fields.Integer(
        string='Guards on Duty',
        compute='_compute_counts',
        store=True
    )

    task_ids = fields.Many2many(
        'guard.task',
        string='Tasks',
        compute='_compute_activities',
        store=True,
        help='Tasks completed or due'
    )
    task_count = fields.Integer(
        string='Task Count',
        compute='_compute_counts',
        store=True
    )
    task_completed_count = fields.Integer(
        string='Tasks Completed',
        compute='_compute_counts',
        store=True
    )

    package_ids = fields.Many2many(
        'package.management',
        string='Packages',
        compute='_compute_activities',
        store=True,
        help='Packages received'
    )
    package_count = fields.Integer(
        string='Package Count',
        compute='_compute_counts',
        store=True
    )

    lost_found_ids = fields.Many2many(
        'lost.found.item',
        string='Lost & Found Items',
        compute='_compute_activities',
        store=True,
        help='Lost & found items logged'
    )
    lost_found_count = fields.Integer(
        string='Lost & Found Count',
        compute='_compute_counts',
        store=True
    )

    # Manual Entries
    special_notes = fields.Html(
        string='Special Notes/Observations',
        help='Notable events, observations, or concerns'
    )
    weather_conditions = fields.Char(
        string='Weather Conditions',
        help='Weather during the shift'
    )
    handover_notes = fields.Html(
        string='Handover Notes',
        help='Notes for the next shift'
    )

    # Summary Statistics
    total_incidents = fields.Integer(
        string='Total Incidents',
        compute='_compute_summary_stats',
        store=True
    )
    critical_incidents = fields.Integer(
        string='Critical Incidents',
        compute='_compute_summary_stats',
        store=True
    )
    tours_completed = fields.Integer(
        string='Tours Completed',
        compute='_compute_summary_stats',
        store=True
    )
    tours_missed = fields.Integer(
        string='Tours Missed',
        compute='_compute_summary_stats',
        store=True
    )

    # Approval Workflow
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('sent', 'Sent to Client')
    ], string='Status', default='draft', tracking=True, required=True)

    # Submission
    submitted_by = fields.Many2one(
        'guard.profile',
        string='Submitted By',
        readonly=True,
        help='Guard who submitted the report'
    )
    submitted_date = fields.Datetime(
        string='Submitted Date',
        readonly=True
    )

    # Review
    reviewed_by = fields.Many2one(
        'res.users',
        string='Reviewed By',
        readonly=True,
        tracking=True
    )
    reviewed_date = fields.Datetime(
        string='Reviewed Date',
        readonly=True
    )
    review_notes = fields.Text(
        string='Review Notes',
        help='Reviewer comments'
    )

    # Client Notification
    sent_to_client = fields.Boolean(
        string='Sent to Client',
        default=False,
        tracking=True
    )
    sent_date = fields.Datetime(
        string='Sent Date',
        readonly=True
    )
    client_email = fields.Char(
        string='Client Email',
        related='site_id.client_id.email',
        readonly=True
    )
    
    # Auto-send Configuration
    auto_send = fields.Boolean(
        string='Auto-Send to Client',
        related='site_id.auto_send_dar',
        readonly=True,
        help='Automatically send to client after approval'
    )

    # Additional
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
        help='Additional photos or documents'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence number"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('daily.activity.report') or 'New'
        records = super().create(vals_list)
        
        # Optimize attached photos
        for record in records:
            if record.attachment_ids:
                record._optimize_attachments()
        
        return records
    
    def write(self, vals):
        """Override write to optimize photos on update."""
        result = super().write(vals)
        if 'attachment_ids' in vals:
            self._optimize_attachments()
        return result
    
    def _optimize_attachments(self):
        """Optimize photo attachments for storage and PDF rendering."""
        for record in self:
            photo_attachments = record.attachment_ids.filtered(
                lambda a: a.mimetype and a.mimetype.startswith('image/')
            )
            for attachment in photo_attachments:
                try:
                    # Skip if already optimized
                    if attachment.file_size and attachment.file_size < 300 * 1024:
                        continue
                    
                    original_data = attachment.datas
                    if not original_data:
                        continue
                    
                    # Optimize image
                    optimized_data = ImageOptimizer.optimize_image(
                        original_data,
                        max_dimension=1200,
                        target_format='JPEG'
                    )
                    
                    if optimized_data != original_data:
                        attachment.write({
                            'datas': optimized_data,
                            'mimetype': 'image/jpeg',
                        })
                        _logger.info(
                            'Optimized photo %s for DAR %s',
                            attachment.name,
                            record.name
                        )
                except Exception as e:
                    _logger.error(
                        'Failed to optimize photo %s: %s',
                        attachment.id,
                        str(e)
                    )

    @api.depends('site_id', 'report_date', 'shift_id')
    def _compute_activities(self):
        """Auto-populate activities for the day"""
        for report in self:
            if not report.site_id or not report.report_date:
                report.incident_ids = False
                report.tour_log_ids = False
                report.visitor_ids = False
                report.attendance_ids = False
                report.task_ids = False
                report.package_ids = False
                report.lost_found_ids = False
                continue

            date_start = fields.Datetime.to_datetime(report.report_date)
            date_end = date_start + timedelta(days=1)

            # Get incidents
            report.incident_ids = self.env['incident.report'].search([
                ('site_id', '=', report.site_id.id),
                ('incident_datetime', '>=', date_start),
                ('incident_datetime', '<', date_end)
            ])

            # Get security tours
            report.tour_log_ids = self.env['tour.log'].search([
                ('site_id', '=', report.site_id.id),
                ('start_time', '>=', date_start),
                ('start_time', '<', date_end)
            ])

            # Get visitors
            report.visitor_ids = self.env['visitor.management'].search([
                ('site_id', '=', report.site_id.id),
                ('visit_date', '=', report.report_date)
            ])

            # Get attendance
            report.attendance_ids = self.env['guard.attendance'].search([
                ('site_id', '=', report.site_id.id),
                ('checkin_time', '>=', date_start),
                ('checkin_time', '<', date_end)
            ])

            # Get tasks
            report.task_ids = self.env['guard.task'].search([
                ('site_id', '=', report.site_id.id),
                '|',
                ('due_date', '>=', date_start),
                ('completed_date', '>=', date_start),
                '|',
                ('due_date', '<=', date_end),
                ('completed_date', '<=', date_end)
            ])

            # Get packages
            report.package_ids = self.env['package.management'].search([
                ('site_id', '=', report.site_id.id),
                ('received_date', '>=', date_start),
                ('received_date', '<', date_end)
            ])

            # Get lost & found
            report.lost_found_ids = self.env['lost.found.item'].search([
                ('site_id', '=', report.site_id.id),
                ('found_date', '>=', date_start),
                ('found_date', '<=', date_end)
            ])

    @api.depends('incident_ids', 'tour_log_ids', 'visitor_ids', 'attendance_ids',
                 'task_ids', 'package_ids', 'lost_found_ids')
    def _compute_counts(self):
        """Compute activity counts"""
        for report in self:
            report.incident_count = len(report.incident_ids)
            report.tour_count = len(report.tour_log_ids)
            report.visitor_count = len(report.visitor_ids)
            report.guards_on_duty_count = len(report.attendance_ids.mapped('guard_id'))
            report.task_count = len(report.task_ids)
            report.task_completed_count = len(report.task_ids.filtered(lambda t: t.state == 'completed'))
            report.package_count = len(report.package_ids)
            report.lost_found_count = len(report.lost_found_ids)

    @api.depends('incident_ids', 'tour_log_ids')
    def _compute_summary_stats(self):
        """Compute summary statistics"""
        for report in self:
            report.total_incidents = len(report.incident_ids)
            report.critical_incidents = len(
                report.incident_ids.filtered(lambda i: i.severity == 'critical')
            )
            report.tours_completed = len(
                report.tour_log_ids.filtered(lambda t: t.status == 'completed')
            )
            # Tours missed would need to be calculated based on scheduled tours
            # For now, simplified calculation
            report.tours_missed = 0

    def action_refresh_data(self):
        """Manually refresh activity data"""
        self.ensure_one()
        self._compute_activities()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Data Refreshed'),
                'message': _('Activity data has been refreshed from the system.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_submit(self):
        """Submit for supervisor review"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('Only draft reports can be submitted.'))

        guard = self.env['guard.profile'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)

        self.write({
            'state': 'submitted',
            'submitted_date': fields.Datetime.now(),
            'submitted_by': guard.id if guard else False
        })

        # Notify supervisor
        if self.site_id.manager_id and self.site_id.manager_id.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Review Daily Activity Report: %s') % self.name,
                note=_('Please review the DAR for %s - %s') % (
                    self.site_id.name,
                    self.report_date
                ),
                user_id=self.site_id.manager_id.user_id.id
            )

        _logger.info('DAR %s submitted for review', self.name)
        return True

    def action_approve(self):
        """Approve and optionally send to client"""
        self.ensure_one()

        if self.state != 'submitted':
            raise UserError(_('Only submitted reports can be approved.'))

        self.write({
            'state': 'approved',
            'reviewed_by': self.env.user.id,
            'reviewed_date': fields.Datetime.now()
        })

        # Auto-send to client if configured
        if self.auto_send and self.client_email:
            self.action_send_to_client()

        _logger.info('DAR %s approved by %s', self.name, self.env.user.name)
        return True

    def action_reject(self):
        """Reject report"""
        self.ensure_one()

        if self.state != 'submitted':
            raise UserError(_('Only submitted reports can be rejected.'))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dar.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_report_id': self.id}
        }

    def action_send_to_client(self):
        """Email PDF to client"""
        self.ensure_one()

        if self.state not in ['approved', 'sent']:
            raise UserError(_('Only approved reports can be sent to clients.'))

        if not self.client_email:
            raise UserError(_('No client email configured for site %s.') % self.site_id.name)

        # Generate PDF report
        pdf_report = self.env.ref('guardpro.action_daily_activity_report_pdf').sudo()._render_qweb_pdf([self.id])[0]

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'DAR_{self.site_id.name}_{self.report_date}.pdf',
            'type': 'binary',
            'datas': pdf_report,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })

        # Send email
        template = self.env.ref('guardpro.email_template_dar_to_client', raise_if_not_found=False)
        if template:
            template.send_mail(
                self.id,
                force_send=True,
                email_values={
                    'attachment_ids': [(6, 0, [attachment.id])]
                }
            )

        self.write({
            'sent_to_client': True,
            'sent_date': fields.Datetime.now(),
            'state': 'sent'
        })

        _logger.info('DAR %s sent to client %s', self.name, self.client_email)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Report Sent'),
                'message': _('Daily Activity Report has been sent to %s') % self.client_email,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_generate_pdf(self):
        """Generate and download PDF"""
        self.ensure_one()
        return self.env.ref('guardpro.action_daily_activity_report_pdf').report_action(self)

    @api.model
    def auto_generate_reports(self):
        """Cron: Auto-generate DARs for previous day"""
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)

        # Get all sites with shifts from yesterday
        yesterday_start = fields.Datetime.to_datetime(yesterday)
        yesterday_end = yesterday_start + timedelta(days=1)
        shifts = self.env['guard.shift'].search([
            ('start_datetime', '>=', yesterday_start),
            ('start_datetime', '<', yesterday_end),
            ('status', 'in', ['completed', 'in_progress'])
        ])

        sites_processed = set()
        reports_created = 0

        for shift in shifts:
            if shift.site_id.id in sites_processed:
                continue

            # Check if report already exists
            existing = self.search([
                ('site_id', '=', shift.site_id.id),
                ('report_date', '=', yesterday)
            ])

            if not existing:
                # Create new DAR
                report = self.create({
                    'site_id': shift.site_id.id,
                    'report_date': yesterday,
                    'shift_id': shift.id
                })
                reports_created += 1
                _logger.info('Auto-created DAR %s for site %s', report.name, shift.site_id.name)

            sites_processed.add(shift.site_id.id)

        _logger.info('Auto-generated %d DARs for %s', reports_created, yesterday)
        return True

    @api.model
    def auto_send_approved_reports(self):
        """Cron: Auto-send approved reports to clients"""
        reports_to_send = self.search([
            ('state', '=', 'approved'),
            ('sent_to_client', '=', False),
            ('auto_send', '=', True),
            ('client_email', '!=', False)
        ])

        for report in reports_to_send:
            try:
                report.action_send_to_client()
            except Exception as e:
                _logger.error('Failed to auto-send DAR %s: %s', report.name, str(e))

        _logger.info('Auto-sent %d DARs to clients', len(reports_to_send))
        return True


class ClientSite(models.Model):
    """Extend client.site with DAR settings"""
    _inherit = 'client.site'

    auto_send_dar = fields.Boolean(
        string='Auto-Send Daily Reports',
        default=False,
        help='Automatically email approved DARs to client'
    )
    dar_recipient_emails = fields.Char(
        string='DAR Recipient Emails',
        help='Comma-separated email addresses for DAR recipients'
    )

