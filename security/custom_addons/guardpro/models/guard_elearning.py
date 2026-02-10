# -*- coding: utf-8 -*-
"""Guard Profile Extensions for eLearning Integration."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class GuardProfile(models.Model):
    """Extend Guard Profile with eLearning Training Management."""
    
    _inherit = 'guard.profile'
    
    # eLearning Training Fields
    training_enrollment_ids = fields.One2many(
        'slide.channel.partner',
        'guard_id',
        string='Training Enrollments',
        help='Courses this guard is enrolled in'
    )
    
    completed_training_count = fields.Integer(
        string='Completed Courses',
        compute='_compute_training_statistics'
    )
    
    active_training_count = fields.Integer(
        string='Active Courses',
        compute='_compute_training_statistics'
    )
    
    training_progress_percentage = fields.Float(
        string='Overall Training Progress',
        compute='_compute_training_statistics',
        help='Average completion across all enrolled courses'
    )
    
    mandatory_training_completed = fields.Boolean(
        string='Mandatory Training Complete',
        compute='_compute_mandatory_training_status',
        help='All mandatory guard training courses are completed'
    )
    
    expiring_certifications_count = fields.Integer(
        string='Expiring Certifications',
        compute='_compute_expiring_certifications',
        help='Certifications expiring within 30 days'
    )
    
    expired_certifications_count = fields.Integer(
        string='Expired Certifications',
        compute='_compute_expiring_certifications',
        help='Expired certifications requiring renewal'
    )
    
    @api.depends('training_enrollment_ids.member_status', 'training_enrollment_ids.completion')
    def _compute_training_statistics(self):
        """Compute training statistics for the guard."""
        for record in self:
            enrollments = record.training_enrollment_ids
            
            record.completed_training_count = len(
                enrollments.filtered(lambda e: e.member_status == 'completed')
            )
            
            record.active_training_count = len(
                enrollments.filtered(lambda e: e.member_status in ['joined', 'ongoing'])
            )
            
            if enrollments:
                total_completion = sum(enrollments.mapped('completion'))
                record.training_progress_percentage = total_completion / len(enrollments)
            else:
                record.training_progress_percentage = 0.0
    
    @api.depends('training_enrollment_ids.member_status', 'training_enrollment_ids.channel_id.is_mandatory_for_guards')
    def _compute_mandatory_training_status(self):
        """Check if all mandatory training is completed."""
        for record in self:
            # Get all mandatory courses
            mandatory_courses = self.env['slide.channel'].search([
                ('is_guard_training', '=', True),
                ('is_mandatory_for_guards', '=', True)
            ])
            
            if not mandatory_courses:
                record.mandatory_training_completed = True
                continue
            
            # Check if guard has completed all mandatory courses
            completed_mandatory = record.training_enrollment_ids.filtered(
                lambda e: e.channel_id.is_mandatory_for_guards and 
                         e.member_status == 'completed' and
                         e.passed_course
            )
            
            record.mandatory_training_completed = len(completed_mandatory) >= len(mandatory_courses)
    
    @api.depends('training_enrollment_ids.certification_status')
    def _compute_expiring_certifications(self):
        """Count expiring and expired certifications."""
        for record in self:
            record.expiring_certifications_count = len(
                record.training_enrollment_ids.filtered(
                    lambda e: e.certification_status == 'expiring'
                )
            )
            
            record.expired_certifications_count = len(
                record.training_enrollment_ids.filtered(
                    lambda e: e.certification_status == 'expired'
                )
            )
    
    def action_view_training_enrollments(self):
        """View all training enrollments for this guard."""
        self.ensure_one()
        return {
            'name': _('Training Enrollments: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'slide.channel.partner',
            'view_mode': 'list,form',
            'domain': [('guard_id', '=', self.id)],
            'context': {'default_partner_id': self.partner_id.id}
        }
    
    def action_view_available_courses(self):
        """View available training courses."""
        self.ensure_one()
        return {
            'name': _('Available Training Courses'),
            'type': 'ir.actions.act_window',
            'res_model': 'slide.channel',
            'view_mode': 'kanban,list,form',
            'domain': [('is_guard_training', '=', True)],
            'context': {'default_is_guard_training': True}
        }
    
    def action_enroll_mandatory_courses(self):
        """Enroll guard in all mandatory courses."""
        self.ensure_one()
        
        # Get all mandatory courses
        mandatory_courses = self.env['slide.channel'].search([
            ('is_guard_training', '=', True),
            ('is_mandatory_for_guards', '=', True)
        ])
        
        enrolled_count = 0
        for course in mandatory_courses:
            # Check if already enrolled
            existing = self.training_enrollment_ids.filtered(
                lambda e: e.channel_id == course
            )
            
            if not existing:
                self.env['slide.channel.partner'].create({
                    'channel_id': course.id,
                    'partner_id': self.partner_id.id,
                })
                enrolled_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Enrolled in %s mandatory courses.') % enrolled_count,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def check_site_training_requirements(self, site_id):
        """
        Check if guard has completed required training for a site.
        
        :param site_id: ID of the client site
        :return: dict with status and missing courses
        """
        self.ensure_one()
        site = self.env['client.site'].browse(site_id)
        
        if not site:
            return {'status': 'error', 'message': 'Site not found'}
        
        # Get required courses for this site
        required_courses = self.env['slide.channel'].search([
            ('is_guard_training', '=', True),
            ('required_for_sites', 'in', [site_id])
        ])
        
        if not required_courses:
            return {
                'status': 'ok',
                'message': 'No specific training required for this site'
            }
        
        # Check which courses are completed with valid certification
        completed_course_ids = []
        missing_courses = []
        
        for course in required_courses:
            enrollment = self.training_enrollment_ids.filtered(
                lambda e: e.channel_id == course and 
                         e.member_status == 'completed' and
                         e.certification_status == 'valid'
            )
            
            if enrollment:
                completed_course_ids.append(course.id)
            else:
                missing_courses.append({
                    'id': course.id,
                    'name': course.name,
                    'reason': 'Not completed' if not enrollment else 'Certification expired'
                })
        
        if missing_courses:
            return {
                'status': 'incomplete',
                'message': f'{len(missing_courses)} required courses not completed',
                'missing_courses': missing_courses
            }
        else:
            return {
                'status': 'ok',
                'message': 'All required training completed'
            }
    
    @api.model
    def _cron_check_expiring_certifications(self):
        """
        Cron job to notify guards about expiring certifications.
        Run daily to check for certifications expiring within 30 days.
        """
        enrollments_expiring = self.env['slide.channel.partner'].search([
            ('certification_status', '=', 'expiring'),
            ('guard_id', '!=', False)
        ])
        
        for enrollment in enrollments_expiring:
            if enrollment.guard_id and enrollment.guard_id.user_id:
                # Only send notification if expiry date exists
                if enrollment.certification_expiry_date:
                    expiry_date_str = enrollment.certification_expiry_date.strftime('%Y-%m-%d')
                    # Send notification
                    enrollment.guard_id.message_post(
                        body=Markup(
                            '<p>Your certification for <strong>%s</strong> is expiring on %s.</p>'
                            '<p>Please renew your certification before it expires.</p>'
                        ) % (enrollment.channel_id.name, expiry_date_str),
                        subject=_('Certification Expiring Soon'),
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                        partner_ids=[enrollment.partner_id.id]
                    )
        
        _logger.info(
            'Checked expiring certifications: %s guards notified',
            len(enrollments_expiring)
        )
        
        return True

