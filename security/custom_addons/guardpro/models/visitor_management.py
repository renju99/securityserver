# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import html_sanitize, email_normalize
import uuid
import qrcode
import base64
from io import BytesIO
import logging

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
    visa_number = fields.Char(
        string='Visa Number',
        help='Visa number (from Emirates ID)'
    )

    # Visit Details
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=False,
        tracking=True,
        index=True,
        ondelete='cascade',
        help='Site being visited'
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
    host_phone = fields.Char(
        string='Host Phone',
        tracking=True
    )
    host_email = fields.Char(
        string='Host Email'
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
        
        return super().create(vals_list)
    
    def write(self, vals):
        """Override write to sanitize inputs on update"""
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
        
        return super().write(vals)

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
        """Check visitor against watchlist"""
        self.ensure_one()
        
        if not self.id_number:
            raise UserError(_('Please enter visitor ID number before checking watchlist.'))
        
        # Search watchlist
        watchlist_entry = self.env['visitor.watchlist'].search([
            '|',
            ('id_number', '=', self.id_number),
            ('name', '=ilike', self.name),
            ('active', '=', True)
        ], limit=1)
        
        if watchlist_entry:
            self.write({
                'watchlist_checked': True,
                'watchlist_hit': True,
                'watchlist_notes': watchlist_entry.reason,
                'state': 'denied',
                'denied_reason': _('Visitor found in watchlist: %s') % watchlist_entry.reason
            })
            
            # Create activity for supervisor
            self.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=_('Watchlist Hit: %s') % self.name,
                note=_('Visitor %s (ID: %s) is on the watchlist.\nReason: %s') % (
                    self.name, self.id_number, watchlist_entry.reason
                )
            )
            
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
        """Send notification to host"""
        self.ensure_one()
        
        if not self.host_email:
            raise UserError(_('Host email is not provided.'))
        
        # Send email notification
        template = self.env.ref('guardpro.email_template_visitor_arrival', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        
        self.write({
            'host_notified': True,
            'host_notification_date': fields.Datetime.now()
        })
        
        return True

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


    @api.model
    def check_overdue_visitors(self):
        """Cron job: Check for overdue visitors"""
        overdue_visitors = self.search([
            ('state', '=', 'checked_in'),
            ('is_overdue_checkout', '=', True)
        ])
        
        for visitor in overdue_visitors:
            # Create activity
            visitor.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=_('Overdue Visitor: %s') % visitor.name,
                note=_('Visitor %s at %s has exceeded expected visit duration.') % (
                    visitor.name, visitor.site_id.name
                )
            )
        
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

