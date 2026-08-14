# -*- coding: utf-8 -*-
"""Smart Features API - Task Suggestions and Enhanced Incidents."""

from odoo import http, fields
from odoo.http import request
import logging
import json
import base64
from datetime import datetime

from odoo.addons.guardpro.common.upload_validation import (
    UploadValidationError,
    validate_b64_payload,
)

_logger = logging.getLogger(__name__)


def _b64_for_binary_field(validated):
    """Odoo Binary fields expect base64 text."""
    return base64.b64encode(validated['data']).decode('ascii')


class GuardLinkSmartFeaturesAPI(http.Controller):
    """API endpoints for smart task suggestions and enhanced incident reporting."""

    # =========================================================================
    # SMART TASK SUGGESTIONS
    # =========================================================================

    @http.route('/guardpro/api/tasks/suggestions', type='json', auth='user')
    def get_task_suggestions(self, latitude=None, longitude=None, **kwargs):
        """Get task suggestions for current guard."""
        try:
            # Get guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Build context
            context = {
                'latitude': latitude,
                'longitude': longitude,
                'site_id': guard.current_site_id.id if guard.current_site_id else None
            }

            # Generate suggestions
            Suggestion = request.env['guard.task.suggestion']
            suggestions = Suggestion.generate_suggestions(guard.id, context)

            # Also get pending suggestions
            pending_suggestions = Suggestion.search([
                ('guard_id', '=', guard.id),
                ('status', '=', 'pending')
            ], order='suggested_at desc')

            suggestions_list = []
            for sugg in pending_suggestions:
                suggestions_list.append({
                    'id': sugg.id,
                    'template_name': sugg.template_id.name,
                    'template_id': sugg.template_id.id,
                    'task_type': sugg.template_id.task_type,
                    'priority': sugg.template_id.priority,
                    'reason': sugg.suggested_reason,
                    'suggested_at': sugg.suggested_at.isoformat(),
                    'estimated_duration': sugg.template_id.estimated_duration,
                    'description': sugg.template_id.description
                })

            return {
                'success': True,
                'suggestions': suggestions_list,
                'total': len(suggestions_list)
            }

        except Exception as e:
            _logger.error('Error getting task suggestions: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/tasks/suggestion/<int:suggestion_id>/accept', type='json', auth='user')
    def accept_task_suggestion(self, suggestion_id, **kwargs):
        """Accept a task suggestion and create task."""
        try:
            Suggestion = request.env['guard.task.suggestion']
            suggestion = Suggestion.browse(suggestion_id)

            if not suggestion.exists():
                return {'success': False, 'error': 'Suggestion not found'}

            # Accept suggestion (creates task)
            task = suggestion.accept_suggestion()

            return {
                'success': True,
                'task_id': task.id,
                'task_name': task.name,
                'message': 'Task created successfully'
            }

        except Exception as e:
            _logger.error('Error accepting suggestion: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/tasks/suggestion/<int:suggestion_id>/dismiss', type='json', auth='user')
    def dismiss_task_suggestion(self, suggestion_id, **kwargs):
        """Dismiss a task suggestion."""
        try:
            Suggestion = request.env['guard.task.suggestion']
            suggestion = Suggestion.browse(suggestion_id)

            if not suggestion.exists():
                return {'success': False, 'error': 'Suggestion not found'}

            suggestion.dismiss_suggestion()

            return {'success': True, 'message': 'Suggestion dismissed'}

        except Exception as e:
            _logger.error('Error dismissing suggestion: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/tasks/suggestion/<int:suggestion_id>/snooze', type='json', auth='user')
    def snooze_task_suggestion(self, suggestion_id, hours=1, **kwargs):
        """Snooze a task suggestion."""
        try:
            Suggestion = request.env['guard.task.suggestion']
            suggestion = Suggestion.browse(suggestion_id)

            if not suggestion.exists():
                return {'success': False, 'error': 'Suggestion not found'}

            suggestion.snooze_suggestion(hours)

            return {
                'success': True,
                'message': f'Suggestion snoozed for {hours} hour(s)',
                'snoozed_until': suggestion.snoozed_until.isoformat()
            }

        except Exception as e:
            _logger.error('Error snoozing suggestion: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/tasks/templates', type='json', auth='user')
    def get_task_templates(self, **kwargs):
        """Get available task templates."""
        try:
            # Get guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Site-scoped + intentional globals (empty site_id)
            user = request.env.user
            if user.has_group('guardpro.group_guardpro_admin'):
                template_domain = [('active', '=', True)]
            else:
                allowed_sites = list(user.site_ids.ids)
                template_domain = [
                    ('active', '=', True),
                    '|',
                    ('site_id', '=', False),
                    ('site_id', 'in', allowed_sites),
                ]

            Template = request.env['guard.task.template']
            templates = Template.search(template_domain, order='sequence, name')

            templates_list = []
            for template in templates:
                templates_list.append({
                    'id': template.id,
                    'name': template.name,
                    'description': template.description,
                    'task_type': template.task_type,
                    'priority': template.priority,
                    'estimated_duration': template.estimated_duration,
                    'requires_photo': template.requires_photo,
                    'checklist_count': len(template.checklist_ids)
                })

            return {
                'success': True,
                'templates': templates_list,
                'total': len(templates_list)
            }

        except Exception as e:
            _logger.error('Error getting task templates: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/tasks/create-from-template', type='json', auth='user')
    def create_task_from_template(self, template_id, **kwargs):
        """Create a task from a template."""
        try:
            # Get guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Get template (record rules enforce site / global visibility)
            Template = request.env['guard.task.template']
            template = Template.browse(template_id)

            if not template.exists():
                return {'success': False, 'error': 'Template not found'}

            user = request.env.user
            if (
                not user.has_group('guardpro.group_guardpro_admin')
                and template.site_id
                and template.site_id.id not in user.site_ids.ids
            ):
                return {'success': False, 'error': 'Template not found'}

            site_id = False
            if guard.current_site_id and guard.current_site_id.id in user.site_ids.ids:
                site_id = guard.current_site_id.id
            elif user.site_ids:
                site_id = user.site_ids.ids[0]
            if template.site_id:
                site_id = template.site_id.id

            # Create task
            Task = request.env['guard.task']
            task = Task.create({
                'name': template.name,
                'description': template.description,
                'task_type': template.task_type,
                'priority': template.priority,
                'assigned_to': guard.id,
                'site_id': site_id,
                'template_id': template.id,
                'state': 'assigned',
                'due_date': fields.Date.today()
            })

            return {
                'success': True,
                'task_id': task.id,
                'task_name': task.name
            }

        except Exception as e:
            _logger.error('Error creating task from template: %s', str(e))
            return {'success': False, 'error': str(e)}

    # =========================================================================
    # ENHANCED INCIDENT REPORTING
    # =========================================================================

    @http.route('/guardpro/api/incidents/templates', type='json', auth='user')
    def get_incident_templates(self, **kwargs):
        """Get available incident templates."""
        try:
            Template = request.env['incident.template']
            templates = Template.search([
                ('active', '=', True)
            ], order='sequence, name')

            templates_list = []
            for template in templates:
                templates_list.append({
                    'id': template.id,
                    'name': template.name,
                    'code': template.code,
                    'incident_type': template.incident_type,
                    'default_severity': template.default_severity,
                    'description_template': template.description_template,
                    'requires_photos': template.requires_photos,
                    'min_photos': template.min_photos,
                    'requires_witness': template.requires_witness,
                    'requires_video': template.requires_video,
                    'icon': template.icon,
                    'color': template.color,
                    'checklist_count': len(template.checklist_item_ids)
                })

            return {
                'success': True,
                'templates': templates_list,
                'total': len(templates_list)
            }

        except Exception as e:
            _logger.error('Error getting incident templates: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/incidents/template/<int:template_id>', type='json', auth='user')
    def get_incident_template_details(self, template_id, **kwargs):
        """Get detailed information about an incident template."""
        try:
            Template = request.env['incident.template']
            template = Template.browse(template_id)

            if not template.exists():
                return {'success': False, 'error': 'Template not found'}

            checklist = []
            for item in template.checklist_item_ids:
                checklist.append({
                    'id': item.id,
                    'name': item.name,
                    'description': item.description,
                    'is_mandatory': item.is_mandatory,
                    'requires_photo': item.requires_photo
                })

            return {
                'success': True,
                'template': {
                    'id': template.id,
                    'name': template.name,
                    'description_template': template.description_template,
                    'incident_type': template.incident_type,
                    'default_severity': template.default_severity,
                    'checklist': checklist,
                    'requires_photos': template.requires_photos,
                    'min_photos': template.min_photos,
                    'requires_witness': template.requires_witness,
                    'requires_video': template.requires_video
                }
            }

        except Exception as e:
            _logger.error('Error getting template details: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/incidents/add-witness', type='json', auth='user')
    def add_incident_witness(self, incident_id, name, contact_phone=None,
                            contact_email=None, statement=None, witness_type='eyewitness',
                            **kwargs):
        """Add witness information to an incident."""
        try:
            Incident = request.env['incident.report']
            incident = Incident.browse(incident_id)

            if not incident.exists():
                return {'success': False, 'error': 'Incident not found'}

            # Create witness record
            Witness = request.env['incident.witness']
            witness = Witness.create({
                'incident_id': incident_id,
                'name': name,
                'contact_phone': contact_phone,
                'contact_email': contact_email,
                'statement': statement or '',
                'witness_type': witness_type,
                'consent_given': True  # Assumed from UI consent checkbox
            })

            return {
                'success': True,
                'witness_id': witness.id,
                'message': 'Witness added successfully'
            }

        except Exception as e:
            _logger.error('Error adding witness: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/incidents/save-annotation', type='json', auth='user')
    def save_media_annotation(self, incident_id, media_type, original_media_base64,
                              annotated_media_base64, annotation_data, **kwargs):
        """Save annotated photo/video for incident."""
        try:
            Incident = request.env['incident.report']
            incident = Incident.browse(incident_id)

            if not incident.exists():
                return {'success': False, 'error': 'Incident not found'}

            mt = (media_type or 'photo').strip().lower()
            if mt not in ('photo', 'video'):
                return {'success': False, 'error': 'media_type must be photo or video'}

            allow_image = mt == 'photo'
            allow_video = mt == 'video'
            try:
                original = validate_b64_payload(
                    original_media_base64,
                    filename='original.%s' % ('jpg' if allow_image else 'mp4'),
                    allow_video=allow_video,
                    allow_image=allow_image,
                    allow_audio=False,
                )
                annotated = validate_b64_payload(
                    annotated_media_base64,
                    filename='annotated.%s' % ('jpg' if allow_image else 'mp4'),
                    allow_video=allow_video,
                    allow_image=allow_image,
                    allow_audio=False,
                )
            except UploadValidationError as exc:
                return {'success': False, 'error': str(exc)}

            Annotation = request.env['incident.media.annotation']
            annotation = Annotation.create({
                'incident_id': incident_id,
                'media_type': mt,
                'original_media': _b64_for_binary_field(original),
                'annotated_media': _b64_for_binary_field(annotated),
                'annotation_data': json.dumps(annotation_data) if isinstance(annotation_data, dict) else annotation_data
            })

            return {
                'success': True,
                'annotation_id': annotation.id,
                'message': 'Annotation saved successfully'
            }

        except Exception as e:
            _logger.error('Error saving annotation: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/tasks/voice-notes', type='json', auth='user')
    def save_task_voice_notes(self, task_id, voice_data_base64, transcription=None, **kwargs):
        """Save voice notes for task completion."""
        try:
            Task = request.env['guard.task']
            task = Task.browse(task_id)

            if not task.exists():
                return {'success': False, 'error': 'Task not found'}

            try:
                voice = validate_b64_payload(
                    voice_data_base64,
                    filename='voice.webm',
                    content_type='audio/webm',
                    allow_video=False,
                    allow_image=False,
                    allow_audio=True,
                )
            except UploadValidationError as exc:
                return {'success': False, 'error': str(exc)}

            task.write({
                'completion_notes_voice': _b64_for_binary_field(voice),
                'voice_notes_text': transcription
            })

            return {
                'success': True,
                'message': 'Voice notes saved successfully'
            }

        except Exception as e:
            _logger.error('Error saving voice notes: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/incidents/upload-video', type='json', auth='user')
    def upload_incident_video(self, incident_id, video_data_base64, duration=None, **kwargs):
        """Upload video evidence for incident."""
        try:
            Incident = request.env['incident.report']
            incident = Incident.browse(incident_id)

            if not incident.exists():
                return {'success': False, 'error': 'Incident not found'}

            try:
                validated = validate_b64_payload(
                    video_data_base64,
                    filename='evidence.mp4',
                    content_type='video/mp4',
                    allow_video=True,
                    allow_image=False,
                    allow_audio=False,
                )
            except UploadValidationError as exc:
                return {'success': False, 'error': str(exc)}

            incident.write({
                'video_evidence': _b64_for_binary_field(validated),
                'video_duration': duration
            })

            return {
                'success': True,
                'message': 'Video uploaded successfully',
                'video_size': len(validated['data'])
            }

        except Exception as e:
            _logger.error('Error uploading video: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/tasks/dependencies/<int:task_id>', type='json', auth='user')
    def get_task_dependencies(self, task_id, **kwargs):
        """Get dependencies for a task."""
        try:
            Task = request.env['guard.task']
            task = Task.browse(task_id)

            if not task.exists():
                return {'success': False, 'error': 'Task not found'}

            dependencies = []
            for dep in task.dependency_ids:
                dependencies.append({
                    'id': dep.id,
                    'depends_on_task_id': dep.depends_on_task_id.id,
                    'depends_on_task_name': dep.depends_on_task_id.name,
                    'dependency_type': dep.dependency_type,
                    'is_satisfied': dep.is_satisfied,
                    'blocking': dep.dependency_type == 'blocking'
                })

            return {
                'success': True,
                'dependencies': dependencies,
                'can_start': task.can_start,
                'has_blocking': task.has_blocking_dependencies
            }

        except Exception as e:
            _logger.error('Error getting task dependencies: %s', str(e))
            return {'success': False, 'error': str(e)}

