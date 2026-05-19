# -*- coding: utf-8 -*-
"""GuardLink Documentation Controller."""

import os
import logging
from odoo import http
from odoo.http import request
from markupsafe import Markup

_logger = logging.getLogger(__name__)

try:
    import markdown
except ImportError:
    _logger.warning("markdown library not installed. Documentation viewer will not work.")
    markdown = None


class GuardLinkDocumentation(http.Controller):
    """Controller for displaying GuardLink documentation."""

    def _get_docs_path(self):
        """Get the path to the docs directory."""
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(module_path, 'docs')

    def _get_file_structure(self):
        """Build the documentation file structure - End User focused."""
        docs_path = self._get_docs_path()
        structure = {
            'overview': {
                'title': 'Guide home',
                'description': 'Navigate the documentation like a guidebook',
                'sections': [
                    {'file': 'INDEX.md', 'title': 'Documentation hub', 'description': 'Chapters, scope, and links'},
                    {'file': 'GETTING_STARTED.md', 'title': 'Chapter 1 — Get started', 'description': 'First site, shift, tour, and mobile patrol loop'},
                    {'file': 'README.md', 'title': 'What is GuardLink?', 'description': 'Product summary and quick setup'},
                    {'file': 'QUICK_REFERENCE.md', 'title': 'Quick reference', 'description': 'Shortcuts and tips'},
                ]
            },
            'getting_started': {
                'title': 'Setup and concepts',
                'description': 'Installation and how the app fits together',
                'sections': [
                    {'file': 'user-guide/01-introduction.md', 'title': 'Introduction', 'description': 'Concepts and navigation'},
                    {'file': 'user-guide/02-installation.md', 'title': 'Installation', 'description': 'Installing GuardLink on Odoo 18'},
                    {'file': 'user-guide/03-configuration.md', 'title': 'Configuration', 'description': 'Settings and security groups'},
                    {'file': 'user-guide/04-features.md', 'title': 'Features overview', 'description': 'Areas of the module'},
                ]
            },
            'operations': {
                'title': 'Daily operations',
                'description': 'Shifts, incidents, visitors, and access',
                'sections': [
                    {'file': 'operations/shift_management.md', 'title': 'Shift Management', 'description': 'How to create, assign, and manage guard shifts'},
                    {'file': 'operations/incident_management.md', 'title': 'Incident Management', 'description': 'How to report and track security incidents'},
                    {'file': 'operations/visitor_management.md', 'title': 'Visitor Management', 'description': 'How to register and track visitors'},
                    {'file': 'operations/access_control.md', 'title': 'Access Control', 'description': 'How to manage site access and permissions'},
                ]
            },
            'guards': {
                'title': 'Guard management',
                'description': 'Profiles, attendance, performance, training',
                'sections': [
                    {'file': 'guards/profile_management.md', 'title': 'Guard Profiles', 'description': 'How to create and manage guard profiles'},
                    {'file': 'guards/attendance.md', 'title': 'Attendance Tracking', 'description': 'How to track guard attendance'},
                    {'file': 'guards/performance.md', 'title': 'Performance Management', 'description': 'How to track and evaluate guard performance'},
                    {'file': 'guards/training.md', 'title': 'Training & Certifications', 'description': 'How to manage guard training and certifications'},
                ]
            },
            'sites': {
                'title': 'Site management',
                'description': 'Sites, checkpoints, patrols, equipment',
                'sections': [
                    {'file': 'sites/site_setup.md', 'title': 'Site Setup', 'description': 'How to create and configure sites'},
                    {'file': 'sites/checkpoints.md', 'title': 'Checkpoints', 'description': 'How to set up and manage checkpoints'},
                    {'file': 'sites/patrols.md', 'title': 'Patrol Routes', 'description': 'How to create and manage patrol routes'},
                    {'file': 'sites/equipment.md', 'title': 'Equipment', 'description': 'How to manage site equipment'},
                ]
            },
            'compliance': {
                'title': 'Compliance & reporting',
                'description': 'Audits, daily activity reports, SLAs',
                'sections': [
                    {'file': 'compliance/audits.md', 'title': 'Audits & Inspections', 'description': 'How to conduct and manage compliance audits'},
                    {'file': 'compliance/reports.md', 'title': 'Daily Activity Reports', 'description': 'How to create and manage DARs'},
                    {'file': 'compliance/sla.md', 'title': 'SLA Management', 'description': 'How to monitor and manage SLAs'},
                ]
            },
            'workflows': {
                'title': 'Workflows & help',
                'description': 'Common flows and troubleshooting',
                'sections': [
                    {'file': 'user-guide/05-workflows.md', 'title': 'Workflow Guide', 'description': 'Common task workflows'},
                    {'file': 'user-guide/06-troubleshooting.md', 'title': 'Troubleshooting', 'description': 'Common issues and solutions'},
                ]
            },
        }
        return structure

    def _read_markdown_file(self, filename):
        """Read and convert markdown file to HTML."""
        if not markdown:
            return "<p class='alert alert-warning'>Markdown library not installed. Please install it with: pip3 install markdown</p>"
        
        docs_path = self._get_docs_path()
        filepath = os.path.join(docs_path, filename)
        
        if not os.path.exists(filepath):
            return f"<p class='alert alert-danger'>File not found: {filename}</p>"
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Convert markdown to HTML with extensions
            # codehilite: light Pygments style (requires Pygments; see requirements.txt)
            html = markdown.markdown(
                content,
                extensions=[
                    'fenced_code',
                    'codehilite',
                    'tables',
                    'toc',
                    'nl2br',
                ],
                extension_configs={
                    'codehilite': {
                        'pygments_style': 'default',
                    },
                },
            )
            return html
        except Exception as e:
            _logger.error(f"Error reading markdown file {filename}: {str(e)}")
            return f"<p class='alert alert-danger'>Error reading file: {str(e)}</p>"

    @http.route([
        '/guardpro/documentation',
        '/guardpro/documentation/<path:doc_file>',
    ], type='http', auth='user', website=True)
    def documentation_viewer(self, doc_file='INDEX.md', **kwargs):
        """Display documentation page."""
        # Check if user has guardpro admin access
        if not request.env.user.has_group('guardpro.group_guardpro_admin'):
            return request.render('web.http_error', {
                'status_code': 403,
                'status_message': 'Access Denied',
                'message': 'You do not have permission to access the documentation. Please contact your administrator.'
            })

        structure = self._get_file_structure()
        content_html = self._read_markdown_file(doc_file)
        # Wrap in Markup to prevent HTML escaping in Odoo 18 (t-out requires this for raw HTML)
        content = Markup(content_html)
        
        # Determine current section and find current page info
        current_section = 'overview'
        current_page_info = None
        
        for section_key, section_data in structure.items():
            for file_info in section_data['sections']:
                if file_info['file'] == doc_file:
                    current_section = section_key
                    current_page_info = file_info
                    break
        
        values = {
            'doc_structure': structure,
            'current_file': doc_file,
            'current_section': current_section,
            'current_page_info': current_page_info,
            'content': content,
            'page_name': 'documentation',
        }
        
        return request.render('guardpro.documentation_page', values)

    @http.route('/guardpro/documentation/search', type='json', auth='user')
    def search_documentation(self, query=None, **kwargs):
        """Search through documentation files."""
        try:
            # Handle JSON-RPC format
            if isinstance(kwargs.get('params'), dict):
                query = kwargs['params'].get('query', query)
            
            if not query or len(query) < 3:
                return {'results': []}
            
            docs_path = self._get_docs_path()
            results = []
            query = query.lower()
            
            structure = self._get_file_structure()
            for section_key, section_data in structure.items():
                for file_info in section_data.get('sections', []):
                    filepath = os.path.join(docs_path, file_info['file'])
                    if os.path.exists(filepath):
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            if query in content.lower():
                                # Find context around the match
                                lines = content.split('\n')
                                for i, line in enumerate(lines):
                                    if query in line.lower():
                                        context = ' '.join(lines[max(0, i-1):min(len(lines), i+2)])
                                        results.append({
                                            'file': file_info['file'],
                                            'title': file_info['title'],
                                            'section': section_key,
                                            'context': context[:200] + '...' if len(context) > 200 else context,
                                        })
                                        break
                        except Exception as e:
                            _logger.error(f"Error searching file {file_info['file']}: {str(e)}")
            
            return {'results': results[:10]}  # Limit to 10 results
        
        except Exception as e:
            _logger.error(f"Error in documentation search: {str(e)}")
            return {'error': str(e), 'results': []}

