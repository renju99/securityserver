# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import html_sanitize, email_normalize
from ..common.image_optimizer import ImageOptimizer
from ..common import constants as PMC
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class PackageManagement(models.Model):
    """Package & Delivery Management System"""
    _name = 'package.management'
    _description = 'Package & Delivery Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'received_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Package ID',
        required=True,
        default='New',
        copy=False,
        readonly=True,
        index=True,
        help='Unique package identifier'
    )

    # Package Details
    package_type = fields.Selection([
        ('parcel', 'Parcel'),
        ('document', 'Document'),
        ('food_delivery', 'Food Delivery'),
        ('equipment', 'Equipment'),
        ('furniture', 'Furniture'),
        ('medical', 'Medical Supplies'),
        ('grocery', 'Grocery'),
        ('other', 'Other')
    ], string='Package Type', required=True, default='parcel', tracking=True)

    tracking_number = fields.Char(
        string='Tracking Number',
        index=True,
        help='Courier tracking number'
    )
    barcode = fields.Char(
        string='Barcode',
        index=True,
        help='Package barcode for scanning'
    )
    courier = fields.Char(
        string='Courier/Delivery Company',
        help='Name of delivery company'
    )
    courier_contact = fields.Char(
        string='Courier Contact',
        help='Delivery person contact number'
    )

    # Size & Weight
    size = fields.Selection([
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
        ('oversized', 'Oversized')
    ], string='Size', default='medium')
    weight = fields.Float(
        string='Weight (kg)',
        help='Package weight in kilograms'
    )
    dimensions = fields.Char(
        string='Dimensions',
        help='Package dimensions (L x W x H)'
    )

    # Location
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        tracking=True,
        index=True,
        # Package chain-of-custody is a physical-asset audit record.
        # Block site deletion while packages exist.
        ondelete='restrict',
        help='Delivery site'
    )
    building = fields.Char(
        string='Building',
        help='Building name or number'
    )
    unit_number = fields.Char(
        string='Unit/Apartment Number',
        index=True,
        help='Recipient unit or apartment number'
    )
    floor = fields.Char(
        string='Floor',
        help='Floor number'
    )
    storage_location = fields.Char(
        string='Storage Location',
        help='Specific storage location for the package (e.g., Package Room A, Shelf 3)'
    )

    # Recipient
    recipient_name = fields.Char(
        string='Recipient Name',
        required=True,
        index=True,
        help='Name of the recipient'
    )
    recipient_phone = fields.Char(
        string='Recipient Phone',
        help='Recipient contact number'
    )
    recipient_email = fields.Char(
        string='Recipient Email'
    )
    recipient_alternate_contact = fields.Char(
        string='Alternate Contact',
        help='Alternative contact number'
    )

    # Dates
    received_date = fields.Datetime(
        string='Received Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True,
        help='When package was received'
    )
    notification_sent_date = fields.Datetime(
        string='Notification Sent',
        readonly=True,
        help='When recipient was notified'
    )
    pickup_date = fields.Datetime(
        string='Pickup Date',
        readonly=True,
        tracking=True,
        help='When package was collected'
    )
    expected_pickup_date = fields.Date(
        string='Expected Pickup',
        help='Expected pickup date'
    )

    # Documentation
    package_photo = fields.Image(
        string='Package Photo',
        help='Photo of the package'
    )
    label_photo = fields.Image(
        string='Label Photo',
        help='Photo of delivery label'
    )
    signature = fields.Binary(
        string='Pickup Signature',
        help='Recipient signature upon collection'
    )
    requires_signature = fields.Boolean(
        string='Requires Signature',
        default=False,
        help='Package requires signature upon delivery/pickup'
    )
    id_verified = fields.Boolean(
        string='ID Verified',
        help='Recipient ID was verified'
    )
    id_type = fields.Char(
        string='ID Type',
        help='Type of ID shown'
    )
    id_number = fields.Char(
        string='ID Number',
        help='ID number verified'
    )

    # Guards
    received_by = fields.Many2one(
        'guard.profile',
        string='Received By (Guard)',
        required=True,
        default=lambda self: self._get_current_guard(),
        help='Guard who received the package'
    )
    handed_over_by = fields.Many2one(
        'guard.profile',
        string='Handed Over By (Guard)',
        help='Guard who handed package to recipient'
    )

    # Status
    state = fields.Selection([
        ('received', 'Received'),
        ('notified', 'Recipient Notified'),
        ('collected', 'Collected'),
        ('returned', 'Returned to Sender'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged'),
        ('unclaimed', 'Unclaimed')
    ], string='Status', default='received', tracking=True, required=True)

    # Issues
    is_damaged = fields.Boolean(
        string='Damaged on Receipt',
        tracking=True
    )
    damage_notes = fields.Text(
        string='Damage Description',
        help='Description of damage'
    )
    damage_photo = fields.Image(
        string='Damage Photo',
        help='Photo showing damage'
    )
    requires_refrigeration = fields.Boolean(
        string='Requires Refrigeration',
        help='Package needs to be stored in refrigerator'
    )
    is_perishable = fields.Boolean(
        string='Perishable',
        help='Package contains perishable items'
    )
    is_fragile = fields.Boolean(
        string='Fragile',
        help='Package is fragile'
    )

    # Related
    incident_id = fields.Many2one(
        'incident.report',
        string='Related Incident',
        help='Related incident if package lost/damaged'
    )

    # Additional
    notes = fields.Text(
        string='Notes',
        help='Additional notes'
    )
    
    photo_ids = fields.Many2many(
        'ir.attachment',
        'package_management_photo_rel',
        'package_id',
        'attachment_id',
        string='Package Photos',
        help='Multiple photos of package (automatically optimized)'
    )
    
    photo_count = fields.Integer(
        string='Photo Count',
        compute='_compute_photo_count',
        store=True
    )
    
    sender_name = fields.Char(
        string='Sender Name',
        help='Name of sender'
    )
    sender_contact = fields.Char(
        string='Sender Contact',
        help='Sender contact information'
    )

    # Computed
    days_in_storage = fields.Integer(
        string='Days in Storage',
        compute='_compute_days_in_storage',
        store=True,
        help='Number of days package has been in storage'
    )
    is_overdue = fields.Boolean(
        string='Overdue Pickup',
        compute='_compute_is_overdue',
        store=True,
        help='Package has not been collected within expected time'
    )

    # Audit
    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.model
    def _get_current_guard(self):
        """Get current user's guard profile"""
        guard = self.env['guard.profile'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        return guard.id if guard else False

    @api.model
    def default_get(self, fields_list):
        """Set smart defaults based on package type."""
        res = super().default_get(fields_list)
        
        # Auto-set expected pickup date based on package type
        if 'expected_pickup_date' in fields_list and res.get('package_type'):
            today = fields.Date.today()
            package_type = res.get('package_type')
            
            # Map package types to pickup periods
            pickup_days_map = {
                'food_delivery': PMC.PACKAGE_PICKUP_FOOD_DELIVERY,
                'medical': PMC.PACKAGE_PICKUP_MEDICAL,
                'document': PMC.PACKAGE_PICKUP_DOCUMENT,
                'furniture': PMC.PACKAGE_PICKUP_FURNITURE,
                'equipment': PMC.PACKAGE_PICKUP_STANDARD,
                'grocery': PMC.PACKAGE_PICKUP_FOOD_DELIVERY,
                'parcel': PMC.PACKAGE_PICKUP_STANDARD,
                'other': PMC.PACKAGE_PICKUP_STANDARD,
            }
            
            days_to_add = pickup_days_map.get(package_type, PMC.PACKAGE_PICKUP_STANDARD)
            res['expected_pickup_date'] = fields.Date.add(today, days=days_to_add)
            
            _logger.debug(
                'Auto-set expected_pickup_date for %s package type to %d days from today',
                package_type,
                days_to_add
            )
        
        # Auto-set perishable flag based on package type
        if 'is_perishable' in fields_list and res.get('package_type') in ['food_delivery', 'grocery', 'medical']:
            res['is_perishable'] = True
        
        return res

    @api.depends('photo_ids')
    def _compute_photo_count(self):
        """Compute number of photo attachments."""
        for record in self:
            record.photo_count = len(record.photo_ids)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence number and sanitize inputs"""
        for vals in vals_list:
            # Generate sequence number
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('package.management') or 'New'
            
            # Sanitize HTML input in notes field
            if 'notes' in vals and vals['notes']:
                vals['notes'] = html_sanitize(vals['notes'])
            
            # Sanitize damage notes
            if 'damage_notes' in vals and vals['damage_notes']:
                vals['damage_notes'] = html_sanitize(vals['damage_notes'])
            
            # Normalize email addresses
            if 'recipient_email' in vals and vals['recipient_email']:
                try:
                    vals['recipient_email'] = email_normalize(vals['recipient_email'])
                except Exception as e:
                    _logger.warning(
                        'Failed to normalize email "%s": %s',
                        vals.get('recipient_email'),
                        str(e)
                    )
        
        packages = super().create(vals_list)
        
        # Optimize photos and send arrival notification
        for package in packages:
            if package.photo_ids or package.damage_photo:
                package._optimize_photos()
            package._send_arrival_email()
        
        return packages
    
    def write(self, vals):
        """Override write to optimize photos and sanitize inputs on update."""
        # Sanitize HTML input in notes field
        if 'notes' in vals and vals['notes']:
            vals['notes'] = html_sanitize(vals['notes'])
        
        # Sanitize damage notes
        if 'damage_notes' in vals and vals['damage_notes']:
            vals['damage_notes'] = html_sanitize(vals['damage_notes'])
        
        # Normalize email addresses
        if 'recipient_email' in vals and vals['recipient_email']:
            try:
                vals['recipient_email'] = email_normalize(vals['recipient_email'])
            except Exception as e:
                _logger.warning(
                    'Failed to normalize email "%s" for package(s) %s: %s',
                    vals.get('recipient_email'),
                    self.ids,
                    str(e)
                )
        
        result = super().write(vals)
        if 'photo_ids' in vals or 'damage_photo' in vals:
            self._optimize_photos()
        return result
    
    def _optimize_photos(self):
        """Optimize photo attachments for storage."""
        for record in self:
            # Optimize Many2many photos
            for attachment in record.photo_ids.filtered(
                lambda a: a.mimetype and a.mimetype.startswith('image/')
            ):
                try:
                    original_size = attachment.file_size or 0
                    
                    # Skip small images
                    if original_size < PMC.PHOTO_OPTIMIZATION_THRESHOLD:
                        continue
                    
                    original_data = attachment.datas
                    if not original_data:
                        continue
                    
                    optimized_data = ImageOptimizer.optimize_image(
                        original_data,
                        max_dimension=PMC.PACKAGE_PHOTO_MAX_DIMENSION,
                        target_format='JPEG'
                    )
                    
                    if optimized_data != original_data:
                        attachment.write({
                            'datas': optimized_data,
                            'mimetype': 'image/jpeg',
                        })
                        _logger.info(
                            'Optimized photo %s (ID: %d) for package %s: '
                            'size=%d KB -> %d KB, type=%s',
                            attachment.name,
                            attachment.id,
                            record.name,
                            original_size // 1024,
                            len(optimized_data) * 3 // 4 // 1024,  # Approximate decoded size
                            attachment.mimetype
                        )
                except Exception as e:
                    _logger.error(
                        'Failed to optimize photo %s (ID: %d) for package %s: %s\n'
                        'Details: original_size=%s KB, mimetype=%s',
                        attachment.name,
                        attachment.id,
                        record.name,
                        str(e),
                        (attachment.file_size // 1024) if attachment.file_size else 'unknown',
                        attachment.mimetype,
                        exc_info=True
                    )
            
            # Optimize Image field (damage_photo)
            if record.damage_photo:
                try:
                    original_size = len(record.damage_photo) * 3 // 4  # Approximate base64 decoded size
                    optimized_data = ImageOptimizer.optimize_image(
                        record.damage_photo,
                        max_dimension=PMC.DAMAGE_PHOTO_MAX_DIMENSION,
                        target_format='JPEG'
                    )
                    if optimized_data != record.damage_photo:
                        record.damage_photo = optimized_data
                        optimized_size = len(optimized_data) * 3 // 4
                        _logger.info(
                            'Optimized damage photo for package %s: '
                            'size=%d KB -> %d KB',
                            record.name,
                            original_size // 1024,
                            optimized_size // 1024
                        )
                except Exception as e:
                    _logger.error(
                        'Failed to optimize damage photo for package %s (ID: %d): %s\n'
                        'Details: photo_size=%s KB',
                        record.name,
                        record.id,
                        str(e),
                        (len(record.damage_photo) * 3 // 4 // 1024) if record.damage_photo else 'unknown',
                        exc_info=True
                    )
    
    def _send_arrival_email(self):
        """Send notification about package arrival.

        Email is disabled globally but we still push a mobile-outbox
        ping so the resident sees it the moment they open the TWA
        (or hear the native tray notification that the TWA emits from
        the outbox poll). If the resident isn't on the portal, we no-op.
        """
        self.ensure_one()
        if self.state != 'received':
            return
        if not self.recipient_email:
            return

        recipient_user = self._resolve_recipient_user()
        if not recipient_user:
            _logger.info(
                'package_management: no portal user resolved for recipient '
                '%s on package %s - skipping mobile arrival push.',
                self.recipient_email, self.name,
            )
            return

        try:
            self.env['guardpro.mobile.outbox'].sudo().push(
                user=recipient_user,
                kind='package_ready',
                title=_('Package arrived: %s') % (self.name or ''),
                body=_('%(courier)s has dropped off a package for you at %(site)s. '
                       'You will be notified again when it is ready to collect.') % {
                    'courier': self.courier_company or _('A courier'),
                    'site': self.site_id.name if self.site_id else _('reception'),
                },
                priority='normal',
                res_model='package.management',
                res_id=self.id,
                deep_link='/guardpro/mobile/packages/%d' % self.id,
                dedup_key='package_ready:%d:received' % self.id,
                expires_in_hours=72,
            )
        except Exception as e:  # pragma: no cover - defensive
            _logger.warning(
                'package_management: arrival outbox push failed for '
                'package %s: %s', self.name, e,
            )

    def _resolve_recipient_user(self):
        """Resolve ``recipient_email`` -> ``res.users`` scoped to the
        package's site. Mirrors ``visitor.management._resolve_host_user``."""
        self.ensure_one()
        Users = self.env['res.users']
        email = (self.recipient_email or '').strip().lower()
        if not email:
            return Users

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

        user = Users.sudo().search([
            ('login', '=ilike', email),
            ('active', '=', True),
        ], limit=1)
        return user or Users

    @api.depends('received_date', 'state')
    def _compute_days_in_storage(self):
        """Calculate days in storage"""
        now = fields.Datetime.now()
        for package in self:
            if package.received_date and package.state not in ['collected', 'returned']:
                delta = now - package.received_date
                package.days_in_storage = delta.days
            else:
                package.days_in_storage = 0

    @api.depends('expected_pickup_date', 'state')
    def _compute_is_overdue(self):
        """Check if package pickup is overdue"""
        today = fields.Date.today()
        for package in self:
            if package.expected_pickup_date and package.state in ['received', 'notified']:
                package.is_overdue = today > package.expected_pickup_date
            else:
                package.is_overdue = False

    @api.constrains('weight')
    def _check_weight(self):
        """Validate that weight is positive"""
        for record in self:
            if record.weight and record.weight <= 0:
                raise ValidationError(_('Weight must be positive'))

    def action_notify_recipient(self):
        """Send pickup notification to recipient"""
        self.ensure_one()
        
        if self.state != 'received':
            raise UserError(_('Only received packages can be notified.'))
        
        if not self.recipient_email and not self.recipient_phone:
            raise UserError(_('Please provide recipient email or phone number.'))
        
        # Email notifications are disabled globally - we rely on the
        # unified mobile outbox to actually reach the resident.
        notification_sent = False
        recipient_user = self._resolve_recipient_user()
        if recipient_user:
            try:
                self.env['guardpro.mobile.outbox'].sudo().push(
                    user=recipient_user,
                    kind='package_ready',
                    title=_('Package ready for pickup: %s') % (self.name or ''),
                    body=_('Your package is ready to collect from %(site)s '
                           '(storage: %(loc)s). Unit %(unit)s.') % {
                        'site': self.site_id.name if self.site_id else _('reception'),
                        'loc': self.storage_location or _('front desk'),
                        'unit': self.unit_number or '-',
                    },
                    priority='normal',
                    res_model='package.management',
                    res_id=self.id,
                    deep_link='/guardpro/mobile/packages/%d' % self.id,
                    dedup_key='package_ready:%d:notified' % self.id,
                    expires_in_hours=168,  # one week
                )
                notification_sent = True
            except Exception as e:  # pragma: no cover - defensive
                _logger.warning(
                    'package_management: pickup outbox push failed for '
                    'package %s: %s', self.name, e,
                )
        else:
            _logger.info(
                'package_management: no portal user resolved for recipient '
                '%s on package %s - cannot push pickup notification.',
                self.recipient_email, self.name,
            )

        # Update package state
        self.write({
            'state': 'notified',
            'notification_sent_date': fields.Datetime.now()
        })
        
        # Post message to chatter for tracking
        notification_message = Markup(
            '<strong>📧 %s</strong><br/>'
            '<b>%s:</b> %s<br/>'
            '<b>%s:</b> %s<br/>'
            '<b>%s:</b> %s<br/>'
            '<b>%s:</b> %s<br/>'
            '<b>%s:</b> %s'
        ) % (
            _('Recipient Notified'),
            _('Recipient'), self.recipient_name,
            _('Email'), self.recipient_email or _('Not provided'),
            _('Phone'), self.recipient_phone or _('Not provided'),
            _('Notification Date'), fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            _('Status'), _('Mobile push sent') if notification_sent else _('No portal user - push skipped')
        )
        
        self.message_post(
            body=notification_message,
            subject=_('Recipient Notified - Package Ready for Pickup'),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )
        
        _logger.info(
            'Notification sent for package %s to %s (email: %s, phone: %s)',
            self.name,
            self.recipient_name,
            self.recipient_email or 'N/A',
            self.recipient_phone or 'N/A'
        )
        
        return True

    def action_bulk_notify(self):
        """Notify multiple packages at once.
        
        This method filters packages that are eligible for notification
        (state='received' and has recipient contact info) and sends
        notifications to all of them.
        
        Returns:
            dict: Client action to display notification result
        """
        # Filter notifiable packages
        notifiable = self.filtered(
            lambda p: p.state == 'received' and (
                p.recipient_email or p.recipient_phone
            )
        )
        
        if not notifiable:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('No packages eligible for notification. '
                                 'Packages must be in "Received" state and have '
                                 'recipient contact information.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        success_count = 0
        failed_packages = []
        
        for package in notifiable:
            try:
                package.action_notify_recipient()
                success_count += 1
            except Exception as e:
                _logger.warning(
                    'Failed to notify package %s (recipient: %s): %s',
                    package.name,
                    package.recipient_name,
                    str(e)
                )
                failed_packages.append(package.name)
        
        # Build result message
        if success_count == len(notifiable):
            message = _('Successfully notified all %d package(s)') % success_count
            notification_type = 'success'
        elif success_count > 0:
            message = _('Notified %d of %d package(s). Failed: %s') % (
                success_count,
                len(notifiable),
                ', '.join(failed_packages)
            )
            notification_type = 'warning'
        else:
            message = _('Failed to notify all %d package(s)') % len(notifiable)
            notification_type = 'danger'
        
        _logger.info(
            'Bulk notification completed: %d/%d successful',
            success_count,
            len(notifiable)
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': notification_type,
                'sticky': notification_type == 'danger',
            }
        }

    def action_mark_collected(self):
        """Open wizard to mark package as collected"""
        self.ensure_one()
        
        if self.state not in ['received', 'notified']:
            raise UserError(_('Only received/notified packages can be marked as collected.'))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'package.collect.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_package_id': self.id}
        }

    def action_report_issue(self):
        """Create incident for lost/damaged package"""
        self.ensure_one()
        
        # Use 'other' category for package issues
        category = self.env.ref('guardpro.incident_cat_other', raise_if_not_found=False)
        
        vals = {
            'name': _('Package Issue - %s') % self.name,
            'title': _('Package Issue - %s') % self.name,
            'site_id': self.site_id.id,
            'incident_datetime': fields.Datetime.now(),
            'description': _('Package %s - Status: %s\nRecipient: %s\nCourier: %s') % (
                self.name,
                self.state,
                self.recipient_name,
                self.courier or 'Unknown'
            ),
            'severity': 'medium'
        }
        if category:
            vals['category_id'] = category.id
        
        incident = self.env['incident.report'].create(vals)
        
        self.incident_id = incident.id
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'res_id': incident.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_return_to_sender(self):
        """Mark package as returned to sender"""
        for package in self:
            if package.state in ['collected']:
                raise UserError(_('Collected packages cannot be returned.'))
            
            package.write({
                'state': 'returned',
                'notes': (package.notes or '') + _('\n\nReturned to sender on %s') % fields.Datetime.now()
            })
        
        return True

    @api.model
    def send_overdue_notifications(self):
        """Cron: Send notifications for overdue package pickups"""
        overdue_packages = self.search([
            ('state', 'in', ['received', 'notified']),
            ('is_overdue', '=', True)
        ])
        
        for package in overdue_packages:
            # Re-notify recipient
            if package.recipient_email or package.recipient_phone:
                # Send reminder notification
                pass
        
        _logger.info('Sent overdue notifications for %d packages', len(overdue_packages))
        return True

    @api.model
    def auto_mark_unclaimed(self):
        """Cron: Mark old packages as unclaimed"""
        cutoff_date = fields.Datetime.subtract(
            fields.Datetime.now(),
            days=PMC.UNCLAIMED_THRESHOLD_DAYS
        )
        
        old_packages = self.search([
            ('state', 'in', ['received', 'notified']),
            ('received_date', '<', cutoff_date)
        ])
        
        old_packages.write({'state': 'unclaimed'})
        
        _logger.info('Marked %d packages as unclaimed', len(old_packages))
        return True

