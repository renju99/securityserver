# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import email_normalize
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class LostFoundItem(models.Model):
    """Lost & Found Property Management"""
    _name = 'lost.found.item'
    _description = 'Lost & Found Property'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'found_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Item ID',
        required=True,
        default='New',
        copy=False,
        readonly=True,
        index=True,
        help='Unique identifier for lost/found item'
    )

    # Item Details
    item_category = fields.Selection([
        ('electronics', 'Electronics'),
        ('jewelry', 'Jewelry/Valuables'),
        ('documents', 'Documents/ID'),
        ('keys', 'Keys'),
        ('wallet', 'Wallet/Purse'),
        ('clothing', 'Clothing'),
        ('bags', 'Bags/Luggage'),
        ('phone', 'Mobile Phone'),
        ('laptop', 'Laptop/Tablet'),
        ('watch', 'Watch'),
        ('glasses', 'Glasses'),
        ('other', 'Other')
    ], string='Item Category', required=True, tracking=True)

    description = fields.Html(
        string='Item Description',
        required=True,
        sanitize=True,
        help='Detailed description of the item'
    )
    brand = fields.Char(
        string='Brand/Make',
        help='Brand or manufacturer'
    )
    model = fields.Char(
        string='Model',
        help='Model number or name'
    )
    color = fields.Char(
        string='Color',
        help='Primary color of the item'
    )
    serial_number = fields.Char(
        string='Serial Number',
        help='Serial number if applicable'
    )
    distinguishing_features = fields.Html(
        string='Distinguishing Features',
        sanitize=True,
        help='Unique characteristics for identification'
    )
    estimated_value = fields.Monetary(
        string='Estimated Value',
        currency_field='currency_id',
        help='Estimated monetary value'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    # Photos
    photo_1 = fields.Image(
        string='Photo 1',
        help='Primary photo of the item'
    )
    photo_2 = fields.Image(
        string='Photo 2',
        help='Additional photo'
    )
    photo_3 = fields.Image(
        string='Photo 3',
        help='Additional photo'
    )

    # Found Details
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        required=True,
        tracking=True,
        index=True,
        # Lost-and-found entries are property-custody records.
        ondelete='restrict',
        help='Site where item was found'
    )
    location_found = fields.Char(
        string='Location Found',
        required=True,
        help='Specific location where item was discovered'
    )
    found_date = fields.Datetime(
        string='Date/Time Found',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True,
        help='When the item was found'
    )
    found_by = fields.Char(
        string='Found By (Name)',
        help='Name of person who found the item'
    )
    found_by_contact = fields.Char(
        string='Finder Contact',
        help='Contact information of finder'
    )
    guard_logged_by = fields.Many2one(
        'guard.profile',
        string='Logged By (Guard)',
        required=True,
        default=lambda self: self._get_current_guard(),
        help='Guard who logged the item'
    )

    # Storage
    storage_location = fields.Char(
        string='Storage Location',
        tracking=True,
        help='Where the item is stored (e.g., Safe A, Shelf 3)'
    )
    storage_date = fields.Datetime(
        string='Stored Date',
        default=fields.Datetime.now,
        help='When item was placed in storage'
    )

    # Legal Holding Period
    holding_period_days = fields.Integer(
        string='Holding Period (Days)',
        default=90,
        required=True,
        help='Number of days to hold item before disposal'
    )
    holding_expiry_date = fields.Date(
        string='Holding Expiry',
        compute='_compute_holding_expiry',
        store=True,
        help='Date when holding period expires'
    )
    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_days_until_expiry',
        help='Days remaining in holding period'
    )

    # State
    state = fields.Selection([
        ('stored', 'In Storage'),
        ('claimed', 'Claimed/Returned'),
        ('disposed', 'Disposed'),
        ('donated', 'Donated'),
        ('police', 'Handed to Police'),
        ('lost', 'Lost/Destroyed')
    ], string='Status', default='stored', tracking=True, required=True)

    # Claim Details
    claim_date = fields.Datetime(
        string='Claim Date',
        readonly=True,
        tracking=True
    )
    claimant_name = fields.Char(
        string='Claimant Name',
        tracking=True
    )
    claimant_id_type = fields.Char(
        string='ID Type'
    )
    claimant_id_number = fields.Char(
        string='ID Number',
        help='Claimant identification number'
    )
    claimant_phone = fields.Char(
        string='Phone'
    )
    claimant_email = fields.Char(
        string='Email'
    )
    claimant_signature = fields.Binary(
        string='Signature',
        help='Digital signature of claimant'
    )
    verification_notes = fields.Html(
        string='Verification Notes',
        sanitize=True,
        help='Notes on how ownership was verified'
    )
    verification_questions = fields.Html(
        string='Verification Questions/Answers',
        sanitize=True,
        help='Questions asked to verify ownership'
    )
    returned_by = fields.Many2one(
        'guard.profile',
        string='Returned By (Guard)',
        help='Guard who returned item to claimant'
    )

    # Disposition
    disposition_date = fields.Date(
        string='Disposition Date',
        help='Date of final disposition'
    )
    disposition_notes = fields.Html(
        string='Disposition Notes',
        sanitize=True,
        help='Details of how item was disposed'
    )
    disposition_authorized_by = fields.Many2one(
        'res.users',
        string='Authorized By',
        help='Person who authorized disposition'
    )
    disposition_document = fields.Binary(
        string='Disposition Document',
        help='Certificate or document for disposition'
    )

    # Related
    incident_id = fields.Many2one(
        'incident.report',
        string='Related Incident',
        help='Related incident report if any'
    )
    
    # Computed
    is_high_value = fields.Boolean(
        string='High Value Item',
        compute='_compute_is_high_value',
        store=True,
        help='Item value exceeds threshold'
    )
    is_expiring_soon = fields.Boolean(
        string='Expiring Soon',
        compute='_compute_is_expiring_soon',
        store=True,
        help='Holding period expires within 7 days'
    )

    # Additional
    notes = fields.Html(
        string='Notes',
        sanitize=True,
        help='Additional notes'
    )
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

    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence number and normalize inputs"""
        for vals in vals_list:
            # Generate sequence number
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('lost.found.item') or 'New'
            
            # Normalize email addresses
            if 'claimant_email' in vals and vals['claimant_email']:
                try:
                    vals['claimant_email'] = email_normalize(vals['claimant_email'])
                except Exception as e:
                    _logger.warning(
                        'Failed to normalize claimant email "%s": %s',
                        vals.get('claimant_email'),
                        str(e)
                    )
        
        return super().create(vals_list)
    
    def write(self, vals):
        """Override write to normalize inputs on update"""
        # Normalize email addresses
        if 'claimant_email' in vals and vals['claimant_email']:
            try:
                vals['claimant_email'] = email_normalize(vals['claimant_email'])
            except Exception as e:
                _logger.warning(
                    'Failed to normalize claimant email "%s" for item(s) %s: %s',
                    vals.get('claimant_email'),
                    self.ids,
                    str(e)
                )
        
        return super().write(vals)

    @api.depends('storage_date', 'holding_period_days')
    def _compute_holding_expiry(self):
        """Calculate holding expiry date"""
        for item in self:
            if item.storage_date and item.holding_period_days:
                storage_dt = fields.Datetime.from_string(item.storage_date)
                expiry_dt = storage_dt + timedelta(days=item.holding_period_days)
                item.holding_expiry_date = expiry_dt.date()
            else:
                item.holding_expiry_date = False

    @api.depends('holding_expiry_date', 'state')
    def _compute_days_until_expiry(self):
        """Calculate days until holding period expires"""
        today = fields.Date.today()
        for item in self:
            if item.holding_expiry_date and item.state == 'stored':
                delta = item.holding_expiry_date - today
                item.days_until_expiry = delta.days
            else:
                item.days_until_expiry = 0

    @api.depends('estimated_value')
    def _compute_is_high_value(self):
        """Determine if item is high value"""
        HIGH_VALUE_THRESHOLD = 1000  # Configure as needed
        for item in self:
            item.is_high_value = (item.estimated_value or 0) >= HIGH_VALUE_THRESHOLD

    @api.depends('days_until_expiry', 'state')
    def _compute_is_expiring_soon(self):
        """Check if expiring within 7 days"""
        for item in self:
            item.is_expiring_soon = (
                item.state == 'stored' and
                0 < item.days_until_expiry <= 7
            )

    def action_mark_claimed(self):
        """Open wizard to mark item as claimed"""
        self.ensure_one()
        
        if self.state != 'stored':
            raise UserError(_('Only items in storage can be marked as claimed.'))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'lost.found.claim.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_item_id': self.id}
        }

    def action_dispose(self):
        """Open wizard to dispose item"""
        self.ensure_one()
        
        if self.state != 'stored':
            raise UserError(_('Only items in storage can be disposed.'))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'lost.found.dispose.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_item_id': self.id}
        }

    def action_create_incident(self):
        """Create related incident report"""
        self.ensure_one()
        
        category = self.env.ref('guardpro.incident_cat_other', raise_if_not_found=False)
        vals = {
            'name': _('Lost Property - %s') % self.name,
            'title': _('Lost Property - %s') % self.name,
            'site_id': self.site_id.id,
            'incident_datetime': self.found_date,
            'description': _('Lost/Found item logged: %s\nLocation: %s') % (
                self.description,
                self.location_found
            ),
            'severity': 'low'
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

    @api.model
    def send_expiry_reminders(self):
        """Cron: Send reminders for items approaching expiry"""
        items = self.search([
            ('state', '=', 'stored'),
            ('days_until_expiry', '<=', 7),
            ('days_until_expiry', '>', 0)
        ])
        
        for item in items:
            # Create activity for supervisor
            item.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Lost & Found Item Expiring: %s') % item.name,
                note=_('Item %s (%s) expires in %d days.\nLocation: %s\nValue: %s') % (
                    item.name,
                    item.description,
                    item.days_until_expiry,
                    item.storage_location or 'Not specified',
                    item.estimated_value or 'Unknown'
                )
            )
        
        _logger.info('Sent expiry reminders for %d lost & found items', len(items))
        return True

    @api.model
    def auto_update_expired_items(self):
        """Cron: Update status of expired items"""
        expired_items = self.search([
            ('state', '=', 'stored'),
            ('holding_expiry_date', '<', fields.Date.today())
        ])
        
        for item in expired_items:
            # Create notification
            item.message_post(
                body=_('Holding period has expired for this item. Please dispose according to policy.'),
                subject=_('Holding Period Expired'),
                message_type='notification'
            )
        
        _logger.info('Found %d expired lost & found items', len(expired_items))
        return True

