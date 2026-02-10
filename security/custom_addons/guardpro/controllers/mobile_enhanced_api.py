# -*- coding: utf-8 -*-
"""Mobile Enhanced API Controllers for GuardPro."""

from odoo import http
from odoo.http import request
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class GuardProMobileEnhancedAPI(http.Controller):
    """Enhanced Mobile API endpoints for additional features."""

    @http.route('/guardpro/api/attendance/my-records', type='json', auth='user')
    def get_my_attendance_records(self, limit=30, **kwargs):
        """Get attendance records for current guard user."""
        try:
            # Get guard profile for current user
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Get attendance records (from guard.shift model with checkin/checkout)
            Shift = request.env['guard.shift']
            shifts = Shift.search([
                ('guard_id', '=', guard.id),
                ('checkin_time', '!=', False),
            ], order='start_datetime desc', limit=limit)

            records = []
            total_hours = 0
            days_worked = set()

            for shift in shifts:
                if shift.checkin_time:
                    hours_worked = 0
                    if shift.checkout_time and shift.checkin_time:
                        delta = shift.checkout_time - shift.checkin_time
                        hours_worked = delta.total_seconds() / 3600

                    total_hours += hours_worked
                    days_worked.add(shift.start_datetime.date() if shift.start_datetime else datetime.now().date())

                    records.append({
                        'id': shift.id,
                        'date': shift.start_datetime.date().isoformat() if shift.start_datetime else None,
                        'checkin_time': shift.checkin_time.strftime('%H:%M') if shift.checkin_time else None,
                        'checkout_time': shift.checkout_time.strftime('%H:%M') if shift.checkout_time else None,
                        'hours_worked': round(hours_worked, 2),
                        'site_name': shift.site_id.name if shift.site_id else 'N/A',
                    })

            summary = {
                'total_hours': round(total_hours, 2),
                'days_worked': len(days_worked),
            }

            return {
                'success': True,
                'records': records,
                'summary': summary
            }

        except Exception as e:
            _logger.error('Error fetching attendance records: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/training/my-courses', type='json', auth='user')
    def get_my_training_courses(self, **kwargs):
        """Get training courses for current guard user."""
        try:
            # Get guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Check if guard.elearning model exists
            if 'guard.elearning' not in request.env:
                # Return empty data if model doesn't exist
                return {
                    'success': True,
                    'courses': [],
                    'summary': {
                        'completed': 0,
                        'in_progress': 0,
                        'not_started': 0
                    }
                }

            # Get e-learning enrollments
            ELearning = request.env['guard.elearning']
            enrollments = ELearning.search([
                ('guard_id', '=', guard.id),
            ])

            courses = []
            summary = {
                'completed': 0,
                'in_progress': 0,
                'not_started': 0
            }

            for enrollment in enrollments:
                status = enrollment.status if hasattr(enrollment, 'status') else 'not_started'
                progress = enrollment.progress if hasattr(enrollment, 'progress') else 0

                if status == 'completed':
                    summary['completed'] += 1
                elif status == 'in_progress':
                    summary['in_progress'] += 1
                else:
                    summary['not_started'] += 1

                courses.append({
                    'id': enrollment.id,
                    'name': enrollment.course_id.name if hasattr(enrollment, 'course_id') and enrollment.course_id else enrollment.name,
                    'description': enrollment.course_id.description if hasattr(enrollment, 'course_id') and enrollment.course_id else '',
                    'status': status,
                    'progress': progress,
                })

            return {
                'success': True,
                'courses': courses,
                'summary': summary
            }

        except Exception as e:
            _logger.error('Error fetching training courses: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/tasks/my-tasks', type='json', auth='user')
    def get_my_tasks(self, filter='all', **kwargs):
        """Get tasks for current guard user."""
        try:
            # Get guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Check if guard.task model exists
            if 'guard.task' not in request.env:
                # Return empty data if model doesn't exist
                return {
                    'success': True,
                    'tasks': [],
                    'summary': {
                        'pending': 0,
                        'in_progress': 0,
                        'completed': 0
                    }
                }

            # Build domain based on filter
            # Note: guard.task uses 'state' field, not 'status'
            # States: draft, assigned, in_progress, completed, cancelled
            domain = [('assigned_to', '=', guard.id)]
            
            if filter != 'all':
                # Map filter names to actual state values
                if filter == 'pending':
                    domain.append(('state', 'in', ['draft', 'assigned']))
                elif filter == 'in_progress':
                    domain.append(('state', '=', 'in_progress'))
                elif filter == 'completed':
                    domain.append(('state', '=', 'completed'))

            Task = request.env['guard.task']
            tasks_records = Task.search(domain, order='priority desc, due_date asc')

            tasks = []
            summary = {
                'pending': 0,
                'in_progress': 0,
                'completed': 0
            }

            # Priority mapping: '0'=Low, '1'=Normal, '2'=High, '3'=Urgent
            priority_map = {
                '0': 'low',
                '1': 'medium',
                '2': 'high',
                '3': 'high'
            }

            for task in tasks_records:
                state = task.state if hasattr(task, 'state') else 'draft'
                
                # Map state to status for frontend
                # draft/assigned -> pending, in_progress -> in_progress, completed -> completed
                if state in ['draft', 'assigned']:
                    status = 'pending'
                    summary['pending'] += 1
                elif state == 'in_progress':
                    status = 'in_progress'
                    summary['in_progress'] += 1
                elif state == 'completed':
                    status = 'completed'
                    summary['completed'] += 1
                else:
                    status = 'pending'
                    summary['pending'] += 1

                # Get priority and map to frontend values
                priority_value = task.priority if hasattr(task, 'priority') else '1'
                priority = priority_map.get(priority_value, 'medium')

                # Strip HTML from description if present
                description = task.description if hasattr(task, 'description') else ''
                if description and isinstance(description, str):
                    # Remove HTML tags for mobile display
                    import re
                    description = re.sub('<[^<]+?>', '', description)

                tasks.append({
                    'id': task.id,
                    'name': task.name,
                    'description': description[:200] if description else '',  # Limit length
                    'status': status,
                    'priority': priority,
                    'due_date': task.due_date.isoformat() if hasattr(task, 'due_date') and task.due_date else None,
                    'task_type': task.task_type if hasattr(task, 'task_type') else 'other',
                })

            return {
                'success': True,
                'tasks': tasks,
                'summary': summary
            }

        except Exception as e:
            _logger.error('Error fetching tasks: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/equipment/my-equipment', type='json', auth='user')
    def get_my_equipment(self, **kwargs):
        """Get equipment assigned to current guard user."""
        try:
            # Get guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Check if equipment model exists
            if 'equipment' not in request.env:
                # Return empty data if model doesn't exist
                return {
                    'success': True,
                    'equipment': [],
                    'summary': {
                        'assigned': 0,
                        'maintenance_due': 0
                    }
                }

            # Get equipment assigned to guard
            Equipment = request.env['equipment']
            equipment_records = Equipment.search([
                ('assigned_to', '=', guard.id),
                ('status', '!=', 'retired')
            ])

            equipment_list = []
            summary = {
                'assigned': len(equipment_records),
                'maintenance_due': 0
            }

            for equip in equipment_records:
                status = equip.status if hasattr(equip, 'status') else 'good'
                
                # Check if maintenance is due
                if hasattr(equip, 'next_maintenance_date') and equip.next_maintenance_date:
                    if equip.next_maintenance_date <= datetime.now().date():
                        summary['maintenance_due'] += 1

                equipment_list.append({
                    'id': equip.id,
                    'name': equip.name,
                    'serial_number': equip.serial_number if hasattr(equip, 'serial_number') else None,
                    'status': status,
                    'assigned_date': equip.assigned_date.isoformat() if hasattr(equip, 'assigned_date') and equip.assigned_date else None,
                    'next_maintenance': equip.next_maintenance_date.isoformat() if hasattr(equip, 'next_maintenance_date') and equip.next_maintenance_date else None,
                })

            return {
                'success': True,
                'equipment': equipment_list,
                'summary': summary
            }

        except Exception as e:
            _logger.error('Error fetching equipment: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/guard/current-site', type='json', auth='user')
    def get_current_site(self, **kwargs):
        """Get current site information for the guard."""
        try:
            # Get guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}

            # Get current site from guard's profile or latest shift
            site = None
            
            if hasattr(guard, 'current_site_id') and guard.current_site_id:
                site = guard.current_site_id
            else:
                # Get latest shift to determine site
                latest_shift = request.env['guard.shift'].search([
                    ('guard_id', '=', guard.id),
                    ('status', '=', 'in_progress')
                ], order='start_datetime desc', limit=1)
                
                if latest_shift and latest_shift.site_id:
                    site = latest_shift.site_id

            if not site:
                return {'success': False, 'error': 'No current site found'}

            # Prepare emergency contacts
            emergency_contacts_html = ''
            if hasattr(site, 'emergency_contact_ids') and site.emergency_contact_ids:
                for contact in site.emergency_contact_ids:
                    emergency_contacts_html += f'''
                        <div style="padding: 10px; background: #f5f5f5; border-radius: 8px; margin-bottom: 8px;">
                            <strong>{contact.name}</strong><br>
                            <i class="fa fa-phone"></i> <a href="tel:{contact.phone}">{contact.phone}</a><br>
                            {f'<small>{contact.role}</small>' if hasattr(contact, 'role') else ''}
                        </div>
                    '''
            else:
                emergency_contacts_html = '<p class="text-muted">No emergency contacts configured</p>'

            return {
                'success': True,
                'site': {
                    'id': site.id,
                    'name': site.name,
                    'address': site.address if hasattr(site, 'address') else None,
                    'phone': site.phone if hasattr(site, 'phone') else None,
                    'email': site.email if hasattr(site, 'email') else None,
                    'emergency_contacts': emergency_contacts_html
                }
            }

        except Exception as e:
            _logger.error('Error fetching current site: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/knowledge/articles', type='json', auth='user')
    def get_knowledge_articles(self, article_type='all', **kwargs):
        """Get knowledge base articles for guards."""
        try:
            # Build domain based on filter
            domain = [('active', '=', True)]
            
            if article_type != 'all':
                domain.append(('article_type', '=', article_type))

            # Get knowledge articles
            Article = request.env['knowledge.article']
            articles = Article.search(domain, order='sequence, name')

            article_list = []
            for article in articles:
                # Strip HTML from content for preview
                import re
                content_preview = ''
                if article.content:
                    content_text = re.sub('<[^<]+?>', '', article.content)
                    content_preview = content_text[:150] + '...' if len(content_text) > 150 else content_text

                article_list.append({
                    'id': article.id,
                    'name': article.name,
                    'article_type': article.article_type,
                    'category': article.category_id.name if article.category_id else 'General',
                    'summary': article.summary or content_preview,
                    'content': article.content,
                    'version': article.version if hasattr(article, 'version') else None,
                })

            return {
                'success': True,
                'articles': article_list,
                'count': len(article_list)
            }

        except Exception as e:
            _logger.error('Error fetching knowledge articles: %s', str(e))
            return {'success': False, 'error': str(e)}

