# -*- coding: utf-8 -*-
"""Photo Attachment Mixin for Models."""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from ..common.image_optimizer import ImageOptimizer
import logging

_logger = logging.getLogger(__name__)


class PhotoAttachmentMixin(models.AbstractModel):
    """
    Mixin to add photo attachment capabilities with automatic optimization.
    
    Models inheriting this mixin get:
    - Multiple photo attachment fields (photo_ids)
    - Automatic image optimization on upload
    - Photo count tracking
    - Validation and size limits
    """
    
    _name = 'photo.attachment.mixin'
    _description = 'Photo Attachment Mixin'
    
    # Photo attachments
    photo_ids = fields.Many2many(
        'ir.attachment',
        string='Photos',
        help='Attach photos (automatically optimized for storage)'
    )
    
    photo_count = fields.Integer(
        string='Photo Count',
        compute='_compute_photo_count',
        store=True
    )
    
    @api.depends('photo_ids')
    def _compute_photo_count(self):
        """Compute number of photos attached."""
        for record in self:
            record.photo_count = len(record.photo_ids)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to optimize photos on creation."""
        records = super().create(vals_list)
        for record in records:
            if record.photo_ids:
                record._optimize_attached_photos()
        return records
    
    def write(self, vals):
        """Override write to optimize photos on update."""
        result = super().write(vals)
        if 'photo_ids' in vals:
            self._optimize_attached_photos()
        return result
    
    def _optimize_attached_photos(self):
        """
        Optimize all attached photos.
        
        This method processes all photo attachments and optimizes them
        for efficient storage and PDF rendering.
        """
        for record in self:
            for attachment in record.photo_ids.filtered(
                lambda a: a.mimetype and a.mimetype.startswith('image/')
            ):
                try:
                    # Skip if already optimized (check if size is reasonable)
                    if attachment.file_size and attachment.file_size < 300 * 1024:  # 300KB
                        continue
                    
                    # Get original data
                    original_data = attachment.datas
                    if not original_data:
                        continue
                    
                    # Optimize image
                    optimized_data = ImageOptimizer.optimize_image(
                        original_data,
                        max_dimension=1200,  # Good for PDF quality
                        target_format='JPEG'
                    )
                    
                    # Update attachment with optimized data
                    if optimized_data != original_data:
                        attachment.write({
                            'datas': optimized_data,
                            'mimetype': 'image/jpeg',
                        })
                        _logger.info(
                            'Optimized photo %s for %s',
                            attachment.name,
                            record._name
                        )
                
                except Exception as e:
                    _logger.error(
                        'Failed to optimize photo %s: %s',
                        attachment.id,
                        str(e)
                    )
    
    @api.constrains('photo_ids')
    def _check_photo_size(self):
        """Validate photo sizes are within acceptable limits."""
        max_size_mb = 10  # 10MB per photo before optimization
        
        for record in self:
            for attachment in record.photo_ids:
                if attachment.file_size and attachment.file_size > max_size_mb * 1024 * 1024:
                    raise ValidationError(
                        'Photo "%s" is too large (%.1f MB). '
                        'Maximum size is %d MB per photo.' % (
                            attachment.name,
                            attachment.file_size / (1024 * 1024),
                            max_size_mb
                        )
                    )
    
    def action_view_photos(self):
        """Open a view to see all attached photos."""
        self.ensure_one()
        return {
            'name': 'Photos',
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,tree,form',
            'domain': [('id', 'in', self.photo_ids.ids)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            }
        }

