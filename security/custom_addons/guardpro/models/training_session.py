# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class TrainingSession(models.Model):
    """Manual log of training conducted at a site (toolbox, induction, HSE, etc.)."""

    _name = 'training.session'
    _description = 'Project Training Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'session_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Reference',
        required=True,
        default='New',
        copy=False,
        readonly=True,
        index=True,
    )
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict',
        # Project visibility is enforced by client.site record rules (assigned projects).
        # Do not domain against a computed Many2many — that breaks the Many2one widget.
    )
    zone_id = fields.Many2one(
        'site.zone',
        string='Zone',
        domain="[('site_id', '=', site_id)]",
        ondelete='set null',
        tracking=True,
        index=True,
    )
    session_date = fields.Date(
        string='Training Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        index=True,
    )
    start_time = fields.Float(
        string='Start Time',
        help='Session start time (24h clock)',
    )
    end_time = fields.Float(
        string='End Time',
        help='Session end time (24h clock)',
    )
    duration_hours = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration_hours',
        store=True,
        readonly=False,
    )
    session_type = fields.Selection(
        [
            ('toolbox', 'Toolbox Talk'),
            ('induction', 'Project Induction'),
            ('hse', 'HSE / Safety'),
            ('fire_safety', 'Fire Safety / Drill'),
            ('security', 'Security Procedures'),
            ('emergency', 'Emergency Response'),
            ('first_aid', 'First Aid'),
            ('equipment', 'Equipment / Systems'),
            ('refresher', 'Refresher'),
            ('other', 'Other'),
        ],
        string='Training Type',
        required=True,
        default='toolbox',
        tracking=True,
        index=True,
    )
    topic = fields.Char(
        string='Topic / Title',
        required=True,
        tracking=True,
    )
    location = fields.Char(
        string='Training Location',
        help='Room, lobby, muster point, or area at the site',
    )
    description = fields.Html(
        string='Agenda / Content',
        help='What was covered during the training',
    )
    trainer_id = fields.Many2one(
        'res.users',
        string='Conducted By',
        default=lambda self: self.env.user,
        tracking=True,
        help='Project admin / supervisor who delivered or recorded the training',
    )
    trainer_name = fields.Char(
        string='External Trainer',
        help='Name if conducted by an external trainer or contractor',
    )
    trainer_company = fields.Char(
        string='Trainer Company / Provider',
    )
    attendee_ids = fields.Many2many(
        'guard.profile',
        'training_session_guard_rel',
        'session_id',
        'guard_id',
        string='Guard Attendees',
        help='Guards who attended this training (limited to this site)',
    )
    available_guard_ids = fields.Many2many(
        'guard.profile',
        compute='_compute_available_guard_ids',
        string='Available Project Guards',
        help='Active guards assigned to the selected site (within your site access)',
    )
    available_guard_count = fields.Integer(
        string='Project Guards Available',
        compute='_compute_available_guard_ids',
    )
    attendee_count = fields.Integer(
        string='Guard Attendees Count',
        compute='_compute_attendee_count',
        store=True,
    )
    external_attendees = fields.Text(
        string='Other Attendees',
        help='Client staff, contractors, or visitors (one per line)',
    )
    external_attendee_count = fields.Integer(
        string='Other Attendees Count',
        compute='_compute_attendee_count',
        store=True,
    )
    total_attendee_count = fields.Integer(
        string='Total Attendees',
        compute='_compute_attendee_count',
        store=True,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'training_session_attachment_rel',
        'session_id',
        'attachment_id',
        string='Attachments',
        help='Attendance sheets, slides, photos, certificates, sign-in sheets',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    notes = fields.Text(
        string='Notes / Observations',
    )
    sync_guard_records = fields.Boolean(
        string='Add to Guard Training History',
        default=True,
        help='When marked completed, create matching entries on each guard profile',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    @api.depends('site_id')
    @api.depends_context('uid')
    def _compute_available_guard_ids(self):
        Guard = self.env['guard.profile']
        user = self.env.user
        is_admin = user.has_group('guardpro.group_guardpro_admin')
        for record in self:
            if not record.site_id:
                record.available_guard_ids = Guard
                record.available_guard_count = 0
                continue
            if not is_admin and record.site_id not in user.site_ids:
                record.available_guard_ids = Guard
                record.available_guard_count = 0
                continue
            guards = Guard.search([
                ('status', '=', 'active'),
                '|',
                ('site_ids', 'in', [record.site_id.id]),
                ('current_site_id', '=', record.site_id.id),
            ])
            record.available_guard_ids = guards
            record.available_guard_count = len(guards)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'site_id' in fields_list and not res.get('site_id'):
            user = self.env.user
            sites = (
                self.env['client.site'].search([], limit=2)
                if user.has_group('guardpro.group_guardpro_admin')
                else user.site_ids
            )
            if len(sites) == 1:
                res['site_id'] = sites.id
        return res

    @api.depends('start_time', 'end_time')
    def _compute_duration_hours(self):
        for record in self:
            if record.end_time:
                diff = record.end_time - (record.start_time or 0.0)
                if diff < 0:
                    diff += 24.0
                record.duration_hours = round(diff, 2)

    @api.depends('attendee_ids', 'external_attendees')
    def _compute_attendee_count(self):
        for record in self:
            guard_count = len(record.attendee_ids)
            external_lines = [
                line.strip()
                for line in (record.external_attendees or '').splitlines()
                if line.strip()
            ]
            record.attendee_count = guard_count
            record.external_attendee_count = len(external_lines)
            record.total_attendee_count = guard_count + len(external_lines)

    @api.onchange('site_id')
    def _onchange_site_id(self):
        if self.zone_id and self.zone_id.site_id != self.site_id:
            self.zone_id = False
        if not self.site_id:
            self.attendee_ids = False
            return
        available = self.env['guard.profile'].search([
            ('status', '=', 'active'),
            '|',
            ('site_ids', 'in', [self.site_id.id]),
            ('current_site_id', '=', self.site_id.id),
        ])
        if (
            not self.env.user.has_group('guardpro.group_guardpro_admin')
            and self.site_id not in self.env.user.site_ids
        ):
            available = self.env['guard.profile']
        self.attendee_ids = self.attendee_ids & available

    def action_add_all_site_guards(self):
        """Tick every active guard assigned to this site."""
        for record in self:
            if not record.site_id:
                raise UserError(_('Select a site first.'))
            if not record.available_guard_ids:
                raise UserError(
                    _('No active guards are assigned to %s.')
                    % record.site_id.display_name
                )
            record.attendee_ids = [(6, 0, record.available_guard_ids.ids)]
        return True

    def action_clear_attendees(self):
        self.write({'attendee_ids': [(5, 0, 0)]})
        return True

    @api.constrains('attendee_ids', 'site_id')
    def _check_attendees_belong_to_site(self):
        for record in self:
            if not record.site_id or not record.attendee_ids:
                continue
            allowed = self.env['guard.profile'].search([
                ('id', 'in', record.attendee_ids.ids),
                '|',
                ('site_ids', 'in', [record.site_id.id]),
                ('current_site_id', '=', record.site_id.id),
            ])
            invalid = record.attendee_ids - allowed
            if invalid:
                raise ValidationError(
                    _('These guards are not assigned to %(site)s:\n%(names)s')
                    % {
                        'site': record.site_id.display_name,
                        'names': '\n'.join(invalid.mapped('display_name')),
                    }
                )

    @api.constrains('site_id')
    def _check_site_allowed(self):
        user = self.env.user
        if user.has_group('guardpro.group_guardpro_admin'):
            return
        for record in self:
            if record.site_id and record.site_id not in user.site_ids:
                raise ValidationError(
                    _('You can only record training for your assigned projects.')
                )

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for record in self:
            for value, label in (
                (record.start_time, _('Start Time')),
                (record.end_time, _('End Time')),
            ):
                if value is not False and (value < 0 or value >= 24):
                    raise ValidationError(
                        _('%s must be between 00:00 and 23:59.') % label
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'training.session'
                ) or _('New')
        return super().create(vals_list)

    def action_mark_completed(self):
        for record in self:
            if record.state == 'cancelled':
                raise UserError(_('Cancelled training records cannot be completed.'))
            if not record.topic:
                raise UserError(_('Please enter a topic before completing.'))
            if record.sync_guard_records and record.attendee_ids:
                record._sync_guard_training_records()
            record.state = 'completed'
        return True

    def action_reset_draft(self):
        self.write({'state': 'draft'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True

    def _sync_guard_training_records(self):
        """Create per-guard training history lines for attendees (idempotent)."""
        GuardTraining = self.env['guard.training']
        for record in self:
            instructor = record.trainer_name or (
                record.trainer_id.name if record.trainer_id else ''
            )
            for guard in record.attendee_ids:
                existing = GuardTraining.search([
                    ('guard_id', '=', guard.id),
                    ('name', '=', record.topic),
                    ('date', '=', record.session_date),
                ], limit=1)
                if existing:
                    continue
                GuardTraining.create({
                    'guard_id': guard.id,
                    'name': record.topic,
                    'date': record.session_date,
                    'instructor': instructor,
                    'hours': record.duration_hours or 0.0,
                    'notes': _(
                        'From site training %(ref)s (%(type)s) at %(site)s'
                    ) % {
                        'ref': record.name,
                        'type': dict(record._fields['session_type'].selection).get(
                            record.session_type, record.session_type
                        ),
                        'site': record.site_id.display_name,
                    },
                })
