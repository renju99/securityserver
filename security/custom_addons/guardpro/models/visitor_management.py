# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import html_sanitize, email_normalize
import uuid
import qrcode
import base64
import re
from io import BytesIO
import logging
from datetime import datetime
import pytz
import xlsxwriter

_logger = logging.getLogger(__name__)


class VisitorManagement(models.Model):
    """Visitor and Contractor Management System"""
    _name = 'visitor.management'
    _description = 'Visitor Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_date desc, checkin_time desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Visitor Name',
        required=True,
        tracking=True,
        index=True,
        help='Full name of the visitor'
    )
    visitor_type = fields.Selection([
        ('visitor', 'Visitor'),
        ('contractor', 'Contractor'),
        ('vendor', 'Vendor'),
        ('delivery', 'Delivery Person'),
        ('job_applicant', 'Job Applicant'),
        ('vip', 'VIP'),
        ('other', 'Other')
    ], string='Visitor Type', default='visitor', required=True, tracking=True)

    # Identification
    id_type = fields.Selection([
        ('emirates_id', 'Emirates ID'),
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
        ('labor_card', 'Labor Card'),
        ('other', 'Other')
    ], string='ID Type', tracking=True)
    id_number = fields.Char(
        string='ID Number',
        tracking=True,
        help='Identification number'
    )
    id_photo = fields.Binary(
        string='ID Photo/Scan',
        help='Scan or photo of visitor identification'
    )
    visitor_photo = fields.Image(
        string='Visitor Photo',
        help='Photo of the visitor taken during check-in'
    )
    
    name_arabic = fields.Char(
        string='Name (Arabic)',
        help='Visitor name in Arabic (from Emirates ID)'
    )
    nationality = fields.Char(
        string='Nationality',
        help='Nationality (from Emirates ID)'
    )
    date_of_birth = fields.Date(
        string='Date of Birth',
        help='Date of birth (from Emirates ID)'
    )
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female')
    ], string='Gender', help='Gender (from Emirates ID)')
    
    # New Emirates ID Fields
    id_expiry_date = fields.Date(
        string='ID Expiry Date',
        help='Identification expiry date (from Emirates ID)'
    )
    id_issue_date = fields.Date(
        string='ID Issue Date',
        help='Identification issue date (from Emirates ID)'
    )
    passport_number = fields.Char(
        string='Passport Number',
        help='Passport number (from Emirates ID)'
    )
    occupation = fields.Char(
        string='Occupation',
        help='Occupation (from Emirates ID)'
    )
    employer_name = fields.Char(
        string='Employer',
        help='Employer name as shown on Emirates ID (back)'
    )
    issuing_place = fields.Char(
        string='Issuing Place',
        help='Issuing place as shown on Emirates ID (back)'
    )
    visa_number = fields.Char(
        string='Visa Number',
        help='Visa number (from Emirates ID)'
    )

    # Visit Details
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=False,
        tracking=True,
        index=True,
        # Visitor logs are security-audit records - keep the log even
        # if the site is later deleted (SET NULL rather than cascade).
        ondelete='set null',
        help='Site being visited'
    )
    zone_id = fields.Many2one(
        'site.zone',
        string='Zone',
        domain="[('site_id', '=', site_id)]",
        ondelete='set null',
        tracking=True,
        index=True,
    )
    visit_date = fields.Date(
        string='Visit Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        index=True
    )
    checkin_time = fields.Datetime(
        string='Check-in Time',
        readonly=True,
        tracking=True,
        index=True
    )
    checkout_time = fields.Datetime(
        string='Check-out Time',
        readonly=True,
        tracking=True
    )
    expected_duration = fields.Float(
        string='Expected Duration (hours)',
        help='Expected duration of visit in hours'
    )
    actual_duration = fields.Float(
        string='Actual Duration (hours)',
        compute='_compute_actual_duration',
        store=True,
        help='Actual time spent on site'
    )

    # Host Information
    host_name = fields.Char(
        string='Host Name',
        required=True,
        tracking=True,
        help='Name of the person being visited'
    )
    host_id = fields.Many2one(
        'visitor.host',
        string='Host',
        tracking=True,
        help='Select host from maintained host directory'
    )
    host_phone = fields.Char(
        string='Host Phone',
        tracking=True
    )
    host_email = fields.Char(
        string='Host Email'
    )
    host_community = fields.Char(
        string='Community',
        help='Community of the host / person being visited'
    )
    host_unit_number = fields.Char(
        string='Unit Number',
        help='Unit / villa / apartment number of the host'
    )
    host_department = fields.Char(
        string='Department',
        help='Department of the host'
    )
    host_notified = fields.Boolean(
        string='Host Notified',
        default=False,
        help='Host has been notified of visitor arrival'
    )
    host_notification_date = fields.Datetime(
        string='Notification Date',
        readonly=True
    )

    # Purpose
    visit_purpose = fields.Selection([
        ('meeting', 'Meeting'),
        ('delivery', 'Delivery'),
        ('maintenance', 'Maintenance'),
        ('contractor_work', 'Contractor Work'),
        ('interview', 'Job Interview'),
        ('inspection', 'Inspection'),
        ('training', 'Training'),
        ('event', 'Event/Function'),
        ('other', 'Other')
    ], string='Visit Purpose', required=True)
    purpose_details = fields.Text(
        string='Purpose Details',
        help='Detailed description of visit purpose'
    )

    # Security
    vehicle_number = fields.Char(
        string='Vehicle Number',
        tracking=True,
        help='Vehicle registration number if visitor has a vehicle'
    )
    vehicle_make = fields.Char(
        string='Vehicle Make/Model'
    )
    parking_slot = fields.Char(
        string='Parking Slot Assigned'
    )
    items_carried_in = fields.Text(
        string='Items Carried In',
        help='Items or equipment brought by visitor'
    )
    items_carried_out = fields.Text(
        string='Items Carried Out',
        help='Items taken out by visitor'
    )

    # Contact Information
    mobile_number = fields.Char(
        string='Mobile Number',
        tracking=True
    )
    email = fields.Char(
        string='Email'
    )
    company = fields.Char(
        string='Company/Organization'
    )

    # Pre-registration
    pre_registered = fields.Boolean(
        string='Pre-Registered',
        default=False,
        help='Visitor was pre-registered before arrival'
    )
    qr_code = fields.Char(
        string='QR Code',
        readonly=True,
        copy=False,
        help='Unique QR code for visitor'
    )
    qr_image = fields.Binary(
        string='QR Code Image',
        compute='_compute_qr_image',
        help='QR code image for visitor badge'
    )

    # Compliance
    nda_signed = fields.Boolean(
        string='NDA Signed',
        tracking=True,
        help='Non-Disclosure Agreement signed'
    )
    nda_document = fields.Binary(
        string='NDA Document',
        help='Signed NDA document'
    )
    code_of_conduct_accepted = fields.Boolean(
        string='Code of Conduct Accepted',
        tracking=True
    )
    safety_briefing_completed = fields.Boolean(
        string='Safety Briefing Completed',
        tracking=True
    )
    health_declaration = fields.Boolean(
        string='Health Declaration Submitted',
        help='Visitor submitted health declaration'
    )
    temperature_checked = fields.Boolean(
        string='Temperature Checked'
    )
    temperature_reading = fields.Float(
        string='Temperature (°C)',
        help='Body temperature reading'
    )

    # Watchlist Check
    watchlist_checked = fields.Boolean(
        string='Watchlist Checked',
        default=False,
        help='Visitor was checked against watchlist'
    )
    watchlist_hit = fields.Boolean(
        string='Watchlist Hit',
        default=False,
        tracking=True,
        help='Visitor found in watchlist'
    )
    watchlist_notes = fields.Text(
        string='Watchlist Notes',
        help='Details if visitor is on watchlist'
    )
    denied_reason = fields.Text(
        string='Access Denial Reason',
        help='Reason for denying access'
    )

    # Badge
    badge_number = fields.Char(
        string='Badge Number',
        tracking=True,
        help='Physical badge number issued'
    )
    badge_returned = fields.Boolean(
        string='Badge Returned',
        default=False,
        tracking=True
    )
    badge_return_date = fields.Datetime(
        string='Badge Return Date',
        readonly=True
    )

    # State
    state = fields.Selection([
        ('pre_registered', 'Pre-Registered'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('denied', 'Access Denied'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired')
    ], string='Status', default='pre_registered', tracking=True, required=True)

    # Guards
    guard_checkin_id = fields.Many2one(
        'guard.profile',
        string='Guard (Check-in)',
        readonly=True,
        help='Guard who checked in the visitor'
    )
    guard_checkout_id = fields.Many2one(
        'guard.profile',
        string='Guard (Check-out)',
        readonly=True,
        help='Guard who checked out the visitor'
    )

    # Additional fields
    notes = fields.Text(
        string='Notes',
        help='Additional notes about the visit'
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
        help='Additional documents or photos'
    )

    # Computed fields
    is_vip = fields.Boolean(
        string='VIP Status',
        compute='_compute_is_vip',
        store=True
    )
    is_overdue_checkout = fields.Boolean(
        string='Overdue Checkout',
        compute='_compute_is_overdue_checkout',
        help='Visitor has exceeded expected visit duration'
    )
    
    # Audit
    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Generate QR code on creation and sanitize inputs"""
        for vals in vals_list:
            # Generate QR code
            if not vals.get('qr_code'):
                vals['qr_code'] = str(uuid.uuid4())
            
            # Sanitize HTML input fields
            if 'purpose_details' in vals and vals['purpose_details']:
                vals['purpose_details'] = html_sanitize(vals['purpose_details'])
            
            if 'items_carried_in' in vals and vals['items_carried_in']:
                vals['items_carried_in'] = html_sanitize(vals['items_carried_in'])
            
            if 'items_carried_out' in vals and vals['items_carried_out']:
                vals['items_carried_out'] = html_sanitize(vals['items_carried_out'])
            
            if 'watchlist_notes' in vals and vals['watchlist_notes']:
                vals['watchlist_notes'] = html_sanitize(vals['watchlist_notes'])
            
            if 'denied_reason' in vals and vals['denied_reason']:
                vals['denied_reason'] = html_sanitize(vals['denied_reason'])
            
            if 'notes' in vals and vals['notes']:
                vals['notes'] = html_sanitize(vals['notes'])
            
            # Sync host details from selected host directory entry.
            if vals.get('host_id'):
                host = self.env['visitor.host'].browse(vals['host_id'])
                if host.exists():
                    vals['host_name'] = host.display_name
                    vals['host_email'] = host.email

            # Normalize email addresses
            if 'email' in vals and vals['email']:
                try:
                    vals['email'] = email_normalize(vals['email'])
                except Exception as e:
                    _logger.warning(
                        'Failed to normalize visitor email "%s": %s',
                        vals.get('email'),
                        str(e)
                    )
            
            if 'host_email' in vals and vals['host_email']:
                try:
                    vals['host_email'] = email_normalize(vals['host_email'])
                except Exception as e:
                    _logger.warning(
                        'Failed to normalize host email "%s": %s',
                        vals.get('host_email'),
                        str(e)
                    )
        
        records = super().create(vals_list)
        for record in records:
            if record.host_id and record.site_id:
                record.host_id._sync_site_from_visit(record.site_id)
        return records
    
    def write(self, vals):
        """Override write to sanitize inputs on update"""
        # Sync host details from selected host directory entry.
        if vals.get('host_id'):
            host = self.env['visitor.host'].browse(vals['host_id'])
            if host.exists():
                vals['host_name'] = host.display_name
                vals['host_email'] = host.email

        # Sanitize HTML input fields
        if 'purpose_details' in vals and vals['purpose_details']:
            vals['purpose_details'] = html_sanitize(vals['purpose_details'])
        
        if 'items_carried_in' in vals and vals['items_carried_in']:
            vals['items_carried_in'] = html_sanitize(vals['items_carried_in'])
        
        if 'items_carried_out' in vals and vals['items_carried_out']:
            vals['items_carried_out'] = html_sanitize(vals['items_carried_out'])
        
        if 'watchlist_notes' in vals and vals['watchlist_notes']:
            vals['watchlist_notes'] = html_sanitize(vals['watchlist_notes'])
        
        if 'denied_reason' in vals and vals['denied_reason']:
            vals['denied_reason'] = html_sanitize(vals['denied_reason'])
        
        if 'notes' in vals and vals['notes']:
            vals['notes'] = html_sanitize(vals['notes'])
        
        # Normalize email addresses
        if 'email' in vals and vals['email']:
            try:
                vals['email'] = email_normalize(vals['email'])
            except Exception as e:
                _logger.warning(
                    'Failed to normalize visitor email "%s" for visitor(s) %s: %s',
                    vals.get('email'),
                    self.ids,
                    str(e)
                )
        
        if 'host_email' in vals and vals['host_email']:
            try:
                vals['host_email'] = email_normalize(vals['host_email'])
            except Exception as e:
                _logger.warning(
                    'Failed to normalize host email "%s" for visitor(s) %s: %s',
                    vals.get('host_email'),
                    self.ids,
                    str(e)
                )
        
        result = super().write(vals)
        if 'host_id' in vals or 'site_id' in vals:
            for record in self:
                if record.host_id and record.site_id:
                    record.host_id._sync_site_from_visit(record.site_id)
        return result

    @api.onchange('host_id')
    def _onchange_host_id(self):
        """Autofill host name/email when selecting from dropdown."""
        if self.host_id:
            self.host_name = self.host_id.display_name
            self.host_email = self.host_id.email

    @api.model
    def _normalize_visitor_id_number(self, id_number):
        """Normalize ID for matching (strip spaces/dashes, uppercase)."""
        if not id_number:
            return ''
        return re.sub(r'[\s\-]', '', str(id_number)).upper()

    @api.model
    def lookup_returning_visitor(self, id_number, exclude_id=None, site_ids=None):
        """
        Return field defaults from the most recent visit with the same ID.

        Used by reception/security so returning visitors (matched by Emirates ID)
        do not need their details retyped.

        ``site_ids`` restricts the search to those sites. Pass an empty list to
        force no results (fail closed). ``None`` means no site filter (admin /
        intentionally unrestricted callers only).
        """
        norm = self._normalize_visitor_id_number(id_number)
        if len(norm) < 5:
            return {}

        # Fail closed: empty site list → no cross-tenant PII
        if site_ids is not None and not site_ids:
            return {}

        domain = [('id_number', '!=', False)]
        if site_ids is not None:
            domain.append(('site_id', 'in', list(site_ids)))
        if exclude_id:
            domain.append(('id', '!=', int(exclude_id)))

        # Prefer exact match, then normalized match among recent candidates
        prior = self.search(
            domain + [('id_number', '=', str(id_number).strip())],
            limit=1,
            order='visit_date desc, id desc',
        )
        if not prior:
            tail = norm[-12:] if len(norm) > 12 else norm
            candidates = self.search(
                domain + [('id_number', 'ilike', '%' + tail + '%')],
                limit=40,
                order='visit_date desc, id desc',
            )
            prior = candidates.filtered(
                lambda v: self._normalize_visitor_id_number(v.id_number) == norm
            )[:1]

        if not prior:
            return {}

        visit = prior[0]
        fields_to_copy = [
            'name', 'name_arabic', 'nationality', 'date_of_birth', 'gender',
            'mobile_number', 'email', 'company', 'occupation', 'employer_name',
            'issuing_place', 'passport_number', 'visa_number', 'visitor_type',
            'id_type', 'id_expiry_date', 'id_issue_date',
            'host_id', 'host_name', 'host_phone', 'host_email',
            'host_community', 'host_unit_number', 'host_department',
        ]
        data = {'prior_visit_id': visit.id}
        for fname in fields_to_copy:
            value = visit[fname]
            if not value:
                continue
            if fname == 'host_id':
                data[fname] = value.id
            elif fname in ('date_of_birth', 'id_expiry_date', 'id_issue_date'):
                data[fname] = fields.Date.to_string(value) if value else False
            else:
                data[fname] = value
        return data

    @api.onchange('id_number')
    def _onchange_id_number_returning_visitor(self):
        """Autofill contact/host details when a known Emirates ID is entered."""
        if not self.id_number:
            return
        exclude_id = self._origin.id if self._origin else None
        # Scope to this form's site, else the user's assigned projects (never global)
        if self.site_id:
            site_ids = [self.site_id.id]
        elif self.env.user.has_group('guardpro.group_guardpro_admin'):
            site_ids = None
        else:
            site_ids = self.env.user.site_ids.ids
        data = self.lookup_returning_visitor(
            self.id_number, exclude_id=exclude_id, site_ids=site_ids,
        )
        if not data:
            return

        filled = []
        for fname, value in data.items():
            if fname == 'prior_visit_id' or not value:
                continue
            current = self[fname]
            if fname == 'host_id':
                if current:
                    continue
                self.host_id = value
            elif current:
                continue
            else:
                self[fname] = value
            filled.append(fname)

        if filled:
            return {
                'warning': {
                    'title': _('Returning visitor'),
                    'message': _(
                        'Details loaded from a previous visit for this ID. '
                        'Please verify before saving.'
                    ),
                }
            }

    @api.depends('qr_code')
    def _compute_qr_image(self):
        """Generate QR code image"""
        for record in self:
            if record.qr_code:
                try:
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(record.qr_code)
                    qr.make(fit=True)
                    
                    img = qr.make_image(fill_color="black", back_color="white")
                    buffer = BytesIO()
                    img.save(buffer, format='PNG')
                    record.qr_image = base64.b64encode(buffer.getvalue())
                except Exception as e:
                    _logger.error(
                        'Error generating QR code for visitor %s (ID: %d): %s\n'
                        'Details: qr_code=%s',
                        record.name,
                        record.id,
                        str(e),
                        record.qr_code,
                        exc_info=True
                    )
                    record.qr_image = False
            else:
                record.qr_image = False

    @api.depends('visitor_type')
    def _compute_is_vip(self):
        """Determine VIP status"""
        for record in self:
            record.is_vip = record.visitor_type == 'vip'

    @api.depends('checkin_time', 'checkout_time', 'expected_duration', 'state')
    def _compute_is_overdue_checkout(self):
        """Check if visitor has overstayed"""
        now = fields.Datetime.now()
        for record in self:
            if record.state == 'checked_in' and record.checkin_time and record.expected_duration:
                expected_checkout = fields.Datetime.add(
                    record.checkin_time,
                    hours=record.expected_duration
                )
                record.is_overdue_checkout = now > expected_checkout
            else:
                record.is_overdue_checkout = False

    @api.depends('checkin_time', 'checkout_time')
    def _compute_actual_duration(self):
        """Calculate actual visit duration"""
        for record in self:
            if record.checkin_time and record.checkout_time:
                delta = record.checkout_time - record.checkin_time
                record.actual_duration = delta.total_seconds() / 3600  # Convert to hours
            else:
                record.actual_duration = 0.0

    @api.constrains('temperature_reading')
    def _check_temperature(self):
        """Validate that temperature reading is within acceptable range"""
        for record in self:
            if record.temperature_reading:
                if not (30.0 <= record.temperature_reading <= 45.0):
                    raise ValidationError(_('Temperature must be between 30-45°C'))

    def action_check_watchlist(self):
        """Check visitor against watchlist (site-scoped, including creator's sites)."""
        self.ensure_one()
        
        if not self.id_number:
            raise UserError(_('Please enter visitor ID number before checking watchlist.'))

        # Use sudo so empty-/cross-rule gaps never skip a real threat; then
        # restrict to this visit's site (or company-wide entries with no sites).
        Watchlist = self.env['visitor.watchlist'].sudo()
        domain = [
            ('active', '=', True),
            '|',
            ('id_number', '=', self.id_number),
            ('name', '=ilike', self.name),
        ]
        if self.site_id:
            domain = [
                '&',
                '|', ('site_ids', 'in', [self.site_id.id]), ('site_ids', '=', False),
            ] + domain
        watchlist_entry = Watchlist.search(domain, limit=1)
        
        if watchlist_entry:
            self.write({
                'watchlist_checked': True,
                'watchlist_hit': True,
                'watchlist_notes': watchlist_entry.reason,
                'state': 'denied',
                'denied_reason': _('Visitor found in watchlist: %s') % watchlist_entry.reason
            })
            
            _logger.warning(
                'Watchlist hit for visitor %s (ID: %s)',
                self.name, self.id_number
            )
        else:
            self.write({
                'watchlist_checked': True,
                'watchlist_hit': False
            })
            _logger.info(
                'Watchlist check passed for visitor %s (ID: %s)',
                self.name, self.id_number
            )
        
        return True

    
    def action_checkin(self):
        """Check in visitor"""
        self.ensure_one()
        
        if self.state == 'denied':
            raise UserError(_('Cannot check in a denied visitor.'))
        
        if self.state == 'checked_in':
            raise UserError(_('Visitor is already checked in.'))
        
        # Get current guard
        guard = self.env['guard.profile'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        self.write({
            'state': 'checked_in',
            'checkin_time': fields.Datetime.now(),
            'guard_checkin_id': guard.id if guard else False
        })
        
        # Notify host if email provided
        if self.host_email and not self.host_notified:
            self.action_notify_host()
        
        _logger.info(
            'Visitor %s checked in at site %s',
            self.name, self.site_id.name
        )
        
        return True

    def action_checkout(self):
        """Check out visitor"""
        self.ensure_one()
        
        if self.state != 'checked_in':
            raise UserError(_('Only checked-in visitors can be checked out.'))
        
        # Get current guard
        guard = self.env['guard.profile'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        
        self.write({
            'state': 'checked_out',
            'checkout_time': fields.Datetime.now(),
            'guard_checkout_id': guard.id if guard else False
        })
        
        _logger.info(
            'Visitor %s checked out from site %s',
            self.name, self.site_id.name
        )
        
        return True

    def action_notify_host(self):
        """Ping the host on their mobile app that a visitor has arrived.

        Delivery strategy:
        * Resolve the host's ``res.users`` record (via matching resident
          portal user or any user with the same email on the same site).
        * Drop a row in the unified mobile outbox so their phone shows
          an in-app card + a tray notification. The TWA natively polls
          the outbox every few seconds - the host hears about the
          visitor without having to open the app first.
        * Keep the legacy ``host_notified`` flag for backward compat
          so dashboards / filters that rely on it still work.
        """
        self.ensure_one()

        if not self.host_email:
            raise UserError(_('Host email is not provided.'))

        # Find the resident portal user tied to this host_email at this
        # site. If a resident has moved or the email doesn't match, fall
        # back to any res.users record with that login so manager-level
        # hosts still get pinged.
        host_user = self._resolve_host_user()

        if host_user:
            visitor_name = self.name or _('a visitor')
            try:
                company = self.company_name
            except AttributeError:
                company = False
            detail_bits = [visitor_name]
            if company:
                detail_bits.append('(%s)' % company)
            visit_purpose = getattr(self, 'purpose', '') or ''
            if visit_purpose:
                detail_bits.append('- %s' % visit_purpose)
            body = _('%(visitor)s has arrived at %(site)s reception.') % {
                'visitor': ' '.join(detail_bits),
                'site': self.site_id.name if self.site_id else _('the gate'),
            }

            self.env['guardpro.mobile.outbox'].sudo().push(
                user=host_user,
                kind='visitor_arrival',
                title=_('Visitor at reception: %s') % visitor_name,
                body=body,
                priority='high',
                res_model='visitor.management',
                res_id=self.id,
                deep_link='/guardpro/mobile/visitors/%d' % self.id,
                # One dedup row per live visitor record - re-running the
                # notify button does not stack cards.
                dedup_key='visitor_arrival:%d' % self.id,
                # Visitor sessions are short - expire the ping in 12h
                # so it doesn't linger past the visit itself.
                expires_in_hours=12,
            )
        else:
            _logger.info(
                'visitor.management: no portal user resolved for host '
                'email %s on visitor %s - skipping mobile push.',
                self.host_email, self.name,
            )

        self.write({
            'host_notified': True,
            'host_notification_date': fields.Datetime.now()
        })

        return True

    def _resolve_host_user(self):
        """Return the best ``res.users`` recordset to ping for
        ``self.host_email`` on ``self.site_id`` - or an empty recordset
        if nobody is matched."""
        self.ensure_one()
        Users = self.env['res.users']
        email = (self.host_email or '').strip().lower()
        if not email:
            return Users

        # 1) Site-scoped resident portal user.
        Resident = self.env.get('tenant.resident')
        if Resident is not None and self.site_id:
            candidates = Resident.sudo().search([
                ('site_id', '=', self.site_id.id),
                '|',
                    ('user_id.login', '=ilike', email),
                    ('partner_id.email', '=ilike', email),
            ], limit=1)
            if candidates and candidates.user_id:
                return candidates.user_id

        # 2) Any active user with this login - covers building / site
        # managers who are hosts but aren't modelled as residents.
        user = Users.sudo().search([
            ('login', '=ilike', email),
            ('active', '=', True),
        ], limit=1)
        return user or Users

    def action_deny_access(self):
        """Deny visitor access"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'visitor.deny.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_visitor_id': self.id}
        }

    def action_cancel(self):
        """Cancel visitor registration"""
        for record in self:
            if record.state == 'checked_in':
                raise UserError(_('Cannot cancel a checked-in visitor. Please check out first.'))
            record.state = 'cancelled'
        return True

    def action_return_badge(self):
        """Mark badge as returned"""
        self.ensure_one()
        if not self.badge_number:
            raise UserError(_('No badge assigned to this visitor.'))
        
        self.write({
            'badge_returned': True,
            'badge_return_date': fields.Datetime.now()
        })
        return True

    def action_save_and_continue(self):
        """Action for the Save button on the form.
        Clicking a type='object' button automatically saves the record.
        Returns a notification to the user.
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Visitor record has been saved successfully.'),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'} if self.env.context.get('close_on_save') else None,
            }
        }

    def action_discard_changes(self):
        """Action for the Discard button on the form.
        Redirects back to the list view, effectively abandoning unsaved changes.
        """
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'visitor.management',
            'view_mode': 'list',
            'target': 'current',
        }

    def action_read_emirates_id(self):
        """
        Placeholder for Emirates ID reading.
        The actual logic is handled in JavaScript (emirates_id_reader.js)
        """
        return True

    def action_scan_emirates_id_camera(self):
        """Camera scan + OCR is handled in ``emirates_id_camera_scan.js``."""
        return True


    @api.model
    def check_overdue_visitors(self):
        """Cron job: Check for overdue visitors"""
        overdue_visitors = self.search([
            ('state', '=', 'checked_in'),
            ('is_overdue_checkout', '=', True)
        ])
        
        # Planned activities intentionally disabled for overdue visitors.
        
        _logger.info('Found %d overdue visitors', len(overdue_visitors))
        return True

    @api.model
    def auto_expire_old_registrations(self):
        """Cron job: Auto-expire old pre-registrations"""
        cutoff_date = fields.Date.subtract(fields.Date.today(), days=7)
        
        old_registrations = self.search([
            ('state', '=', 'pre_registered'),
            ('visit_date', '<', cutoff_date)
        ])
        
        old_registrations.write({'state': 'expired'})
        
        _logger.info('Expired %d old pre-registrations', len(old_registrations))
        return True

    @api.model
    def _recipients_for_site_visitor_log(self, site):
        """Resolve per-site mailbox for the daily visitor PII report.

        Priority (first non-empty only — never fan-out to multiple roles):
        1. site.site_email (comma/semicolon separated allowed)
        2. site.manager_id.email
        3. site.client_id.email
        """
        raw_parts = []
        if site and site.site_email:
            raw_parts.extend(re.split(r'[,;\s]+', site.site_email.strip()))
        elif site and site.manager_id and site.manager_id.email:
            raw_parts.append(site.manager_id.email)
        elif site and site.client_id and site.client_id.email:
            raw_parts.append(site.client_id.email)

        emails = []
        seen = set()
        for part in raw_parts:
            if not part:
                continue
            try:
                normalized = email_normalize(part)
            except Exception:
                normalized = False
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            emails.append(normalized)
        return emails

    @api.model
    def send_daily_visitor_log_email(self):
        """Cron: send daily visitor log at 18:00 Asia/Dubai — one email per site.

        Each site only receives its own visitors' PII. Sites without a configured
        recipient (site_email / manager / client) are skipped. Unassigned visitors
        are never emailed.
        """
        dubai_tz = pytz.timezone('Asia/Dubai')
        now_dubai = datetime.now(dubai_tz)
        today_dubai = now_dubai.date()

        # Run hourly via cron, but only send during 18:00 hour.
        if now_dubai.hour != 18:
            return True

        config = self.env['ir.config_parameter'].sudo()
        sent_key = 'guardpro.daily_visitor_log_last_sent_date'
        if config.get_param(sent_key) == str(today_dubai):
            return True

        visitors = self.search([
            ('visit_date', '=', today_dubai),
            ('site_id', '!=', False),
        ])
        unassigned = self.search_count([
            ('visit_date', '=', today_dubai),
            ('site_id', '=', False),
        ])
        if unassigned:
            _logger.warning(
                'Daily visitor log: skipped %s visitor(s) with no site_id (PII not emailed)',
                unassigned,
            )

        sender = 'noreply@berkeleyuae.com'
        sent_count = 0
        skipped_sites = []

        site_groups = {}
        for visitor in visitors:
            site_groups.setdefault(visitor.site_id.id, self.env['visitor.management'])
            site_groups[visitor.site_id.id] |= visitor

        for site_id, site_visitors in site_groups.items():
            site = self.env['client.site'].browse(site_id)
            recipients = self._recipients_for_site_visitor_log(site)
            if not recipients:
                skipped_sites.append(site.display_name or site_id)
                continue

            total = len(site_visitors)
            checked_in = len(site_visitors.filtered(lambda v: v.state == 'checked_in'))
            checked_out = len(site_visitors.filtered(lambda v: v.state == 'checked_out'))
            denied = len(site_visitors.filtered(lambda v: v.state == 'denied'))
            pre_registered = len(site_visitors.filtered(lambda v: v.state == 'pre_registered'))

            body_html = (
                f'<div style="font-family:Arial,sans-serif;">'
                f'<h3>Daily Visitor Log - {site.name} - {today_dubai}</h3>'
                f'<p>This report contains visitors for <strong>{site.name}</strong> only.</p>'
                f'<p><strong>Total:</strong> {total}</p>'
                f'<ul>'
                f'<li>Checked In: {checked_in}</li>'
                f'<li>Checked Out: {checked_out}</li>'
                f'<li>Denied: {denied}</li>'
                f'<li>Pre-Registered: {pre_registered}</li>'
                f'</ul>'
                f'<p style="margin-top:16px;">A detailed Excel file is attached with this site\'s visitor records.</p>'
                f'</div>'
            )

            xlsx_data = self._build_daily_visitor_log_xlsx(
                site_visitors, today_dubai, dubai_tz
            )
            site_slug = re.sub(r'[^\w\-]+', '_', site.code or site.name or 'site')[:40]
            mail = self.env['mail.mail'].sudo().create({
                'subject': f'Daily Visitor Log - {site.name} - {today_dubai}',
                'email_from': sender,
                'email_to': ','.join(recipients),
                'body_html': body_html,
                'attachment_ids': [(0, 0, {
                    'name': f'visitor_log_{site_slug}_{today_dubai}.xlsx',
                    'datas': base64.b64encode(xlsx_data),
                    'mimetype': (
                        'application/vnd.openxmlformats-officedocument'
                        '.spreadsheetml.sheet'
                    ),
                })],
                'auto_delete': False,
            })
            mail.send()
            sent_count += 1
            _logger.info(
                'Daily visitor log emailed for site %s (%s) to %s (%s visitors)',
                site.name, today_dubai, ','.join(recipients), total,
            )

        if skipped_sites:
            _logger.warning(
                'Daily visitor log: no recipient configured for site(s): %s '
                '(set Project Email, Project Manager email, or Client email)',
                ', '.join(str(s) for s in skipped_sites),
            )

        # Mark day complete even if some sites were skipped, to avoid retry loops
        # that re-spam successfully delivered sites.
        config.set_param(sent_key, str(today_dubai))
        _logger.info(
            'Daily visitor log run finished for %s: %s site email(s) sent, %s skipped',
            today_dubai, sent_count, len(skipped_sites),
        )
        return True

    @api.model
    def _build_daily_visitor_log_xlsx(self, visitors, report_date, dubai_tz):
        """Build an XLSX workbook containing detailed visitor records."""
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Visitor Log')

        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#E8EEF7', 'border': 1})
        cell_fmt = workbook.add_format({'border': 1})

        headers = [
            'Visitor Name', 'Visitor Type', 'State', 'Visit Date',
            'Check-in (Dubai)', 'Check-out (Dubai)',
            'Site', 'Host Name', 'Host Email', 'Host Phone',
            'Community', 'Unit Number',
            'Purpose', 'Purpose Details',
            'Company', 'Mobile Number', 'Email',
            'ID Type', 'ID Number', 'Badge Number',
            'Vehicle Number', 'Nationality', 'Date of Birth', 'Gender',
            'ID Issue Date', 'ID Expiry Date',
            'Pre-Registered', 'Walk-in', 'Watchlist Hit',
            'Denied Reason', 'Expected Duration (hrs)', 'Actual Duration (hrs)',
            'Created On (Dubai)'
        ]

        for col, title in enumerate(headers):
            worksheet.write(0, col, title, header_fmt)
            worksheet.set_column(col, col, 20)

        row = 1
        for visitor in visitors:
            checkin = visitor.checkin_time
            checkout = visitor.checkout_time
            created = visitor.create_date

            checkin_local = fields.Datetime.context_timestamp(
                visitor.with_context(tz='Asia/Dubai'), checkin
            ) if checkin else False
            checkout_local = fields.Datetime.context_timestamp(
                visitor.with_context(tz='Asia/Dubai'), checkout
            ) if checkout else False
            created_local = fields.Datetime.context_timestamp(
                visitor.with_context(tz='Asia/Dubai'), created
            ) if created else False

            values = [
                visitor.name or '',
                dict(visitor._fields['visitor_type'].selection).get(visitor.visitor_type, '') if visitor.visitor_type else '',
                dict(visitor._fields['state'].selection).get(visitor.state, '') if visitor.state else '',
                str(visitor.visit_date or ''),
                checkin_local.strftime('%Y-%m-%d %H:%M:%S') if checkin_local else '',
                checkout_local.strftime('%Y-%m-%d %H:%M:%S') if checkout_local else '',
                visitor.site_id.name or '',
                visitor.host_name or '',
                visitor.host_email or '',
                visitor.host_phone or '',
                visitor.host_community or '',
                visitor.host_unit_number or '',
                dict(visitor._fields['visit_purpose'].selection).get(visitor.visit_purpose, '') if visitor.visit_purpose else '',
                visitor.purpose_details or '',
                visitor.company or '',
                visitor.mobile_number or '',
                visitor.email or '',
                dict(visitor._fields['id_type'].selection).get(visitor.id_type, '') if visitor.id_type else '',
                visitor.id_number or '',
                visitor.badge_number or '',
                visitor.vehicle_number or '',
                visitor.nationality or '',
                str(visitor.date_of_birth or ''),
                dict(visitor._fields['gender'].selection).get(visitor.gender, '') if visitor.gender else '',
                str(visitor.id_issue_date or ''),
                str(visitor.id_expiry_date or ''),
                'Yes' if visitor.pre_registered else 'No',
                'Yes' if getattr(visitor, 'walk_in', False) else 'No',
                'Yes' if visitor.watchlist_hit else 'No',
                visitor.denied_reason or '',
                visitor.expected_duration or 0.0,
                visitor.actual_duration or 0.0,
                created_local.strftime('%Y-%m-%d %H:%M:%S') if created_local else '',
            ]

            for col, value in enumerate(values):
                worksheet.write(row, col, value, cell_fmt)
            row += 1

        worksheet.freeze_panes(1, 0)
        workbook.close()
        output.seek(0)
        return output.read()


class VisitorHost(models.Model):
    """Host directory used for searchable dropdown in visitor entries."""
    _name = 'visitor.host'
    _description = 'Visitor Host'
    _order = 'first_name, last_name, id'
    _rec_name = 'display_name'

    first_name = fields.Char(string='First Name', required=True, index=True)
    last_name = fields.Char(string='Last Name', required=True, index=True)
    email = fields.Char(string='Email', required=True, index=True)
    active = fields.Boolean(default=True)
    display_name = fields.Char(string='Name', compute='_compute_display_name', store=True)
    site_ids = fields.Many2many(
        'client.site',
        'visitor_host_site_rel',
        'host_id',
        'site_id',
        string='Sites',
        help='Sites where this host appears in visitor workflows. '
             'Auto-assigned from the creator\'s sites or the visit site.',
    )

    _sql_constraints = [
        ('visitor_host_email_unique', 'unique(email)', 'Host email must be unique.'),
    ]

    @api.model
    def _default_site_ids(self):
        """Default sites for new hosts: caller's assigned projects."""
        user = self.env.user
        if user.site_ids:
            return [(6, 0, user.site_ids.ids)]
        return []

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'site_ids' in fields_list and not res.get('site_ids'):
            res['site_ids'] = self._default_site_ids()
        return res

    def _sync_site_from_visit(self, site):
        """Ensure ``site`` is linked on this host (idempotent)."""
        if not site:
            return
        for host in self:
            if site not in host.site_ids:
                host.sudo().write({'site_ids': [(4, site.id)]})

    @api.constrains('site_ids')
    def _check_host_site_ids(self):
        for host in self:
            if not host.site_ids and not self.env.user.has_group(
                'guardpro.group_guardpro_admin'
            ):
                raise ValidationError(
                    _('Please assign at least one site to host "%s".')
                    % (host.display_name or host.email)
                )

    @api.depends('first_name', 'last_name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{(rec.first_name or '').strip()} {(rec.last_name or '').strip()}".strip()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('email'):
                vals['email'] = email_normalize(vals['email'])
            if not vals.get('site_ids'):
                defaults = self._default_site_ids()
                if defaults:
                    vals['site_ids'] = defaults
                else:
                    ctx_site = (
                        self.env.context.get('default_site_id')
                        or self.env.context.get('force_site_id')
                    )
                    if ctx_site:
                        vals['site_ids'] = [(6, 0, [int(ctx_site)])]
                    elif self.env.su or self.env.user.has_group(
                        'guardpro.group_guardpro_admin'
                    ):
                        all_sites = self.env['client.site'].sudo().search([
                            ('active', '=', True),
                        ]).ids
                        if all_sites:
                            vals['site_ids'] = [(6, 0, all_sites)]
                        else:
                            raise UserError(_(
                                'Cannot create a host: no active sites exist.'
                            ))
                    else:
                        raise UserError(_(
                            'Cannot create a host without sites. '
                            'Ask an administrator to assign sites to your user.'
                        ))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('email'):
            vals['email'] = email_normalize(vals['email'])
        return super().write(vals)

    def name_get(self):
        result = []
        for rec in self:
            label = rec.display_name or f"{rec.first_name or ''} {rec.last_name or ''}".strip()
            if rec.email:
                label = f"{label} ({rec.email})"
            result.append((rec.id, label))
        return result

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
        args = list(args or [])
        if name:
            args = ['|', '|', '|',
                    ('display_name', operator, name),
                    ('first_name', operator, name),
                    ('last_name', operator, name),
                    ('email', operator, name)] + args
        return self._search(args, limit=limit, order=order)


class VisitorWatchlist(models.Model):
    """Visitor Watchlist/Denied Access List"""
    _name = 'visitor.watchlist'
    _description = 'Visitor Watchlist/Denied Access List'
    _order = 'added_date desc, name'

    name = fields.Char(
        string='Name',
        required=True,
        index=True,
        help='Name of person on watchlist'
    )
    id_number = fields.Char(
        string='ID Number',
        index=True,
        help='Identification number'
    )
    reason = fields.Text(
        string='Reason for Listing',
        required=True,
        help='Reason for adding to watchlist'
    )
    category = fields.Selection([
        ('security_threat', 'Security Threat'),
        ('previous_incident', 'Previous Incident'),
        ('legal_issue', 'Legal Issue'),
        ('banned', 'Permanently Banned'),
        ('temporary', 'Temporary Restriction'),
        ('other', 'Other')
    ], string='Category', default='other')
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Uncheck to remove from watchlist'
    )
    added_date = fields.Date(
        string='Added Date',
        default=fields.Date.today,
        required=True
    )
    expiry_date = fields.Date(
        string='Expiry Date',
        help='Date when restriction expires (if applicable)'
    )
    added_by = fields.Many2one(
        'res.users',
        string='Added By',
        default=lambda self: self.env.user,
        readonly=True
    )
    notes = fields.Text(
        string='Notes',
        help='Additional information'
    )
    photo = fields.Image(
        string='Photo',
        help='Photo for identification'
    )
    site_ids = fields.Many2many(
        'client.site',
        'visitor_watchlist_site_rel',
        'watchlist_id',
        'site_id',
        string='Sites',
        help='Sites where this watchlist entry applies. '
             'Auto-assigned from the visit site / creator sites on create.',
    )

    @api.model
    def _default_site_ids(self):
        user = self.env.user
        if user.site_ids:
            return [(6, 0, user.site_ids.ids)]
        return []

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'site_ids' in fields_list and not res.get('site_ids'):
            res['site_ids'] = self._default_site_ids()
        return res

    @api.constrains('site_ids')
    def _check_watchlist_site_ids(self):
        for entry in self:
            if not entry.site_ids and not self.env.user.has_group(
                'guardpro.group_guardpro_admin'
            ):
                raise ValidationError(
                    _('Please assign at least one site to watchlist entry "%s".')
                    % entry.name
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('site_ids'):
                defaults = self._default_site_ids()
                if defaults:
                    vals['site_ids'] = defaults
                else:
                    ctx_site = (
                        self.env.context.get('default_site_id')
                        or self.env.context.get('force_site_id')
                    )
                    if ctx_site:
                        vals['site_ids'] = [(6, 0, [int(ctx_site)])]
                    else:
                        all_sites = self.env['client.site'].sudo().search([
                            ('active', '=', True),
                        ]).ids
                        if all_sites and (
                            self.env.su
                            or self.env.user.has_group('guardpro.group_guardpro_admin')
                        ):
                            vals['site_ids'] = [(6, 0, all_sites)]
                        elif not all_sites:
                            raise UserError(_(
                                'Cannot create a watchlist entry: no active sites exist.'
                            ))
                        else:
                            raise UserError(_(
                                'Cannot create a watchlist entry without sites. '
                                'Ask an administrator to assign sites to your user.'
                            ))
        return super().create(vals_list)

    @api.model
    def check_expired_entries(self):
        """Cron job: Deactivate expired watchlist entries"""
        today = fields.Date.today()
        expired = self.search([
            ('active', '=', True),
            ('expiry_date', '<', today),
            ('expiry_date', '!=', False)
        ])
        
        expired.write({'active': False})
        
        _logger.info('Deactivated %d expired watchlist entries', len(expired))
        return True

