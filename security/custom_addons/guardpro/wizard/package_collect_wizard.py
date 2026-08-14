# -*- coding: utf-8 -*-
"""Package Collection Wizard with Signature Capture and ID Verification."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup
import logging

from odoo.addons.guardpro.common.upload_validation import (
    UploadValidationError,
    decode_payload_to_bytes,
    validate_media_bytes,
)

_logger = logging.getLogger(__name__)


class PackageCollectWizard(models.TransientModel):
    """
    Package Collection Wizard.
    
    Handles package collection with:
    - ID verification
    - Signature capture
    - Photo documentation
    - Collection notes
    """
    
    _name = 'package.collect.wizard'
    _description = 'Package Collection Wizard'
    
    package_id = fields.Many2one(
        'package.management',
        string='Package',
        required=True,
        readonly=True
    )
    
    # Package Information (Read-only for reference)
    recipient_name = fields.Char(
        related='package_id.recipient_name',
        string='Recipient Name',
        readonly=True
    )
    package_type = fields.Selection(
        related='package_id.package_type',
        string='Package Type',
        readonly=True
    )
    tracking_number = fields.Char(
        related='package_id.tracking_number',
        string='Tracking Number',
        readonly=True
    )
    received_date = fields.Datetime(
        related='package_id.received_date',
        string='Received Date',
        readonly=True
    )
    
    # Collection Details
    collector_name = fields.Char(
        string='Collector Name',
        required=True,
        help='Name of person collecting the package'
    )
    collector_phone = fields.Char(
        string='Collector Phone',
        help='Contact number of collector'
    )
    collector_email = fields.Char(
        string='Collector Email'
    )
    
    # ID Verification
    id_verified = fields.Boolean(
        string='ID Verified',
        default=False,
        help='Verify collector identification'
    )
    id_type = fields.Selection([
        ('emirates_id', 'Emirates ID'),
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
        ('labor_card', 'Labor Card'),
        ('company_id', 'Company ID'),
        ('other', 'Other')
    ], string='ID Type')
    id_number = fields.Char(
        string='ID Number',
        help='Identification number'
    )
    id_photo = fields.Binary(
        string='ID Photo/Scan',
        help='Photo or scan of identification document'
    )
    
    # Signature Capture
    signature = fields.Binary(
        string='Signature',
        required=True,
        help='Collector signature - draw on touchscreen or upload image'
    )
    signature_date = fields.Datetime(
        string='Signature Date',
        default=fields.Datetime.now,
        readonly=True
    )
    
    # Additional Verification
    collector_photo = fields.Binary(
        string='Collector Photo',
        help='Photo of person collecting package (optional)'
    )
    
    relationship_to_recipient = fields.Selection([
        ('self', 'Self (Recipient)'),
        ('family', 'Family Member'),
        ('colleague', 'Colleague'),
        ('authorized_person', 'Authorized Person'),
        ('building_staff', 'Building Staff'),
        ('other', 'Other')
    ], string='Relationship', default='self', required=True)
    
    authorization_letter = fields.Binary(
        string='Authorization Letter',
        help='Upload authorization letter if collecting on behalf of someone else'
    )
    
    authorization_letter_filename = fields.Char(
        string='Authorization Letter Filename'
    )
    
    # Package Condition
    package_condition = fields.Selection([
        ('good', 'Good Condition'),
        ('damaged', 'Damaged'),
        ('opened', 'Opened/Tampered'),
        ('wet', 'Water Damaged'),
        ('other', 'Other Issue')
    ], string='Package Condition', default='good', required=True)
    
    condition_notes = fields.Text(
        string='Condition Notes',
        help='Additional notes about package condition'
    )
    
    condition_photo = fields.Binary(
        string='Condition Photo',
        help='Photo showing package condition'
    )
    
    # Collection Notes
    notes = fields.Text(
        string='Collection Notes',
        help='Any additional notes about the collection'
    )
    
    # Guard Information
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard Handling Collection',
        default=lambda self: self._get_current_guard(),
        required=True
    )
    
    # Verification Checks
    verify_recipient_match = fields.Boolean(
        string='Recipient Name Matches ID',
        default=False,
        help='Check if collector name matches package recipient'
    )
    
    send_confirmation_email = fields.Boolean(
        string='Send Confirmation Email',
        default=True,
        help='Send collection confirmation to recipient'
    )
    
    send_confirmation_sms = fields.Boolean(
        string='Send Confirmation SMS',
        default=False,
        help='Send SMS confirmation to recipient'
    )
    
    @api.model
    def _get_current_guard(self):
        """Get current user's guard profile."""
        guard = self.env['guard.profile'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        return guard.id if guard else False
    
    @api.model
    def default_get(self, fields_list):
        """Set default values from package."""
        res = super().default_get(fields_list)
        
        # Get package from context
        package_id = self.env.context.get('default_package_id')
        if package_id:
            package = self.env['package.management'].browse(package_id)
            
            # Pre-fill collector info from package recipient
            if 'collector_name' in fields_list:
                res['collector_name'] = package.recipient_name
            if 'collector_phone' in fields_list:
                res['collector_phone'] = package.recipient_phone
            if 'collector_email' in fields_list:
                res['collector_email'] = package.recipient_email
        
        return res
    
    @api.onchange('collector_name', 'recipient_name')
    def _onchange_verify_recipient_match(self):
        """Auto-verify if collector name matches recipient."""
        if self.collector_name and self.recipient_name:
            # Simple name matching (case-insensitive)
            self.verify_recipient_match = (
                self.collector_name.strip().lower() == 
                self.recipient_name.strip().lower()
            )
    
    @api.constrains('id_verified', 'id_type', 'id_number')
    def _check_id_verification(self):
        """Validate ID verification fields."""
        for record in self:
            if record.id_verified:
                if not record.id_type or not record.id_number:
                    raise ValidationError(
                        _('ID Type and ID Number are required when ID is verified.')
                    )
    
    @api.constrains('relationship_to_recipient', 'authorization_letter')
    def _check_authorization(self):
        """Check authorization requirements."""
        for record in self:
            # If collecting for someone else, may need authorization
            if record.relationship_to_recipient not in ['self'] and not record.verify_recipient_match:
                # Warning in logs but don't block (business decision)
                _logger.warning(
                    'Package %s collected by %s (relationship: %s) without matching recipient name',
                    record.package_id.name,
                    record.collector_name,
                    record.relationship_to_recipient
                )
    
    def action_collect_package(self):
        """Process package collection."""
        self.ensure_one()
        
        # Validate required fields
        if not self.signature:
            raise UserError(_('Signature is required to collect the package.'))
        
        if not self.collector_name:
            raise UserError(_('Collector name is required.'))

        for field_name in ('id_photo', 'collector_photo', 'condition_photo'):
            value = self[field_name]
            if not value:
                continue
            raw = decode_payload_to_bytes(value)
            if not raw:
                raise UserError(_('Invalid image for %s.') % field_name)
            try:
                validate_media_bytes(
                    raw,
                    filename='%s.jpg' % field_name,
                    allow_video=False,
                    allow_image=True,
                )
            except UploadValidationError as exc:
                raise UserError(str(exc)) from exc
        
        # Prepare collection data
        collection_vals = {
            'state': 'collected',
            'pickup_date': fields.Datetime.now(),
            'handed_over_by': self.guard_id.id,
            'id_verified': self.id_verified,
            'id_type': self.id_type,
            'id_number': self.id_number,
            'signature': self.signature,
        }
        
        # Add condition notes if package damaged
        if self.package_condition != 'good':
            damage_note = _(
                '\n\n=== COLLECTION CONDITION ===\n'
                'Condition: %s\n'
                'Notes: %s\n'
                'Collected by: %s\n'
                'Date: %s'
            ) % (
                dict(self._fields['package_condition'].selection).get(self.package_condition),
                self.condition_notes or 'None',
                self.collector_name,
                fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            collection_vals['notes'] = (self.package_id.notes or '') + damage_note
        
        # Add general notes
        if self.notes:
            general_note = _('\n\n=== COLLECTION NOTES ===\n%s') % self.notes
            collection_vals['notes'] = (collection_vals.get('notes', self.package_id.notes or '')) + general_note
        
        # Update package
        self.package_id.write(collection_vals)
        
        # Post message to chatter
        collection_message = Markup(
            '<strong>Package Collected</strong><br/>'
            '<b>Collector:</b> %s<br/>'
            '<b>Relationship:</b> %s<br/>'
            '<b>ID Verified:</b> %s<br/>'
            '<b>Guard:</b> %s<br/>'
            '<b>Date:</b> %s'
        ) % (
            self.collector_name,
            dict(self._fields['relationship_to_recipient'].selection).get(
                self.relationship_to_recipient
            ),
            _('Yes') if self.id_verified else _('No'),
            self.guard_id.name,
            fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        if self.id_verified:
            collection_message += Markup(
                '<br/><b>ID Type:</b> %s<br/><b>ID Number:</b> %s'
            ) % (
                dict(self._fields['id_type'].selection).get(self.id_type),
                self.id_number
            )
        
        self.package_id.message_post(
            body=collection_message,
            subject=_('Package Collected'),
            message_type='notification'
        )
        
        # Create attachments for photos and documents
        attachment_vals_list = []
        
        if self.id_photo:
            attachment_vals_list.append({
                'name': f'ID_Photo_{self.package_id.name}.jpg',
                'datas': self.id_photo,
                'res_model': 'package.management',
                'res_id': self.package_id.id,
                'mimetype': 'image/jpeg',
                'description': f'ID verification for collection by {self.collector_name}'
            })
        
        if self.collector_photo:
            attachment_vals_list.append({
                'name': f'Collector_Photo_{self.package_id.name}.jpg',
                'datas': self.collector_photo,
                'res_model': 'package.management',
                'res_id': self.package_id.id,
                'mimetype': 'image/jpeg',
                'description': f'Collector photo - {self.collector_name}'
            })
        
        if self.condition_photo:
            attachment_vals_list.append({
                'name': f'Condition_Photo_{self.package_id.name}.jpg',
                'datas': self.condition_photo,
                'res_model': 'package.management',
                'res_id': self.package_id.id,
                'mimetype': 'image/jpeg',
                'description': f'Package condition: {self.package_condition}'
            })
        
        if self.authorization_letter:
            attachment_vals_list.append({
                'name': f'Authorization_Letter_{self.package_id.name}.pdf',
                'datas': self.authorization_letter,
                'res_model': 'package.management',
                'res_id': self.package_id.id,
                'mimetype': 'application/pdf',
                'description': f'Authorization letter for {self.collector_name}'
            })
        
        if attachment_vals_list:
            self.env['ir.attachment'].create(attachment_vals_list)
        
        # Send confirmation emails/SMS if requested
        if self.send_confirmation_email and self.package_id.recipient_email:
            self._send_collection_confirmation_email()
        
        if self.send_confirmation_sms and self.package_id.recipient_phone:
            self._send_collection_confirmation_sms()
        
        # Log the collection
        _logger.info(
            'Package %s collected by %s (ID verified: %s) at %s',
            self.package_id.name,
            self.collector_name,
            self.id_verified,
            self.package_id.site_id.name
        )
        
        # Show success notification and close wizard
        notification_message = _(
            'Package %s successfully marked as collected by %s'
        ) % (
            self.package_id.name,
            self.collector_name
        )
        self.env.user.notify_success(
            message=notification_message,
            title=_('Success')
        )
        return {'type': 'ir.actions.act_window_close'}
    
    def _send_collection_confirmation_email(self):
        """Send email confirmation of package collection."""
        self.ensure_one()
        
        template = self.env.ref(
            'guardpro.email_template_package_collected',
            raise_if_not_found=False
        )
        
        if template:
            try:
                # Create email context with collector details
                # Pass values directly in context, accessible in template
                email_context = {
                    'collector_name': self.collector_name,
                    'collection_date': fields.Datetime.now(),
                    'guard_name': self.guard_id.name if self.guard_id else '',
                    'id_verified': self.id_verified,
                    'relationship': dict(
                        self._fields['relationship_to_recipient'].selection
                    ).get(self.relationship_to_recipient, ''),
                }
                
                template.with_context(**email_context).send_mail(
                    self.package_id.id,
                    force_send=True
                )
                
                _logger.info(
                    'Collection confirmation email sent to %s for package %s',
                    self.package_id.recipient_email,
                    self.package_id.name
                )
            except Exception as e:
                _logger.warning(
                    'Failed to send collection confirmation email: %s',
                    str(e),
                    exc_info=True
                )
        else:
            _logger.warning(
                'Email template "email_template_package_collected" not found'
            )
    
    def _send_collection_confirmation_sms(self):
        """Send SMS confirmation of package collection."""
        self.ensure_one()
        
        # SMS implementation depends on SMS gateway setup
        # This is a placeholder for future SMS integration
        
        _logger.info(
            'SMS confirmation requested for package %s to %s (not yet implemented)',
            self.package_id.name,
            self.package_id.recipient_phone
        )
        
        # TODO: Implement SMS gateway integration
        # Example: self.env['sms.api'].send_sms(
        #     self.package_id.recipient_phone,
        #     f'Your package {self.package_id.name} has been collected.'
        # )

