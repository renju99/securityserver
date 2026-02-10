# -*- coding: utf-8 -*-
"""Daily Activity Report PDF generator - Enhanced Version."""

from odoo import models, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class DailyActivityReportPdf(models.AbstractModel):
    """Abstract model for Daily Activity Report PDF generation with enhanced features."""

    _name = 'report.guardpro.daily_activity_report_pdf_template'
    _description = 'Daily Activity Report PDF (Enhanced)'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Get values for the daily activity report with additional computed data.
        
        This method enhances the report with:
        - Formatted statistics and summaries
        - Categorized incident data
        - Tour completion rates
        - Attendance summaries
        - Image optimization for attachments
        """
        docs = self.env['daily.activity.report'].browse(docids)
        
        # Build a dictionary of computed values for each document
        computed_values = {}
        
        for doc in docs:
            doc_values = {}
            
            # Calculate tour completion percentage
            if doc.tour_log_ids:
                completed_tours = len(doc.tour_log_ids.filtered(lambda t: t.status == 'completed'))
                doc_values['tour_completion_rate'] = (completed_tours / len(doc.tour_log_ids)) * 100
            else:
                doc_values['tour_completion_rate'] = 0
            
            # Calculate task completion percentage
            if doc.task_ids:
                doc_values['task_completion_rate'] = (doc.task_completed_count / doc.task_count) * 100 if doc.task_count > 0 else 0
            else:
                doc_values['task_completion_rate'] = 0
            
            # Categorize incidents by severity
            doc_values['high_severity_incidents'] = doc.incident_ids.filtered(lambda i: i.severity in ['high', 'critical'])
            doc_values['medium_severity_incidents'] = doc.incident_ids.filtered(lambda i: i.severity == 'medium')
            doc_values['low_severity_incidents'] = doc.incident_ids.filtered(lambda i: i.severity == 'low')
            
            # Calculate total hours worked
            doc_values['total_guard_hours'] = sum(doc.attendance_ids.mapped('hours_worked'))
            
            # Count unique guards
            doc_values['unique_guards_count'] = len(doc.attendance_ids.mapped('guard_id'))
            
            computed_values[doc.id] = doc_values
            
            _logger.info(
                'Generating enhanced DAR PDF for %s - Date: %s, Site: %s',
                doc.name,
                doc.report_date,
                doc.site_id.name
            )
        
        return {
            'doc_ids': docids,
            'doc_model': 'daily.activity.report',
            'docs': docs,
            'data': data,
            'datetime': datetime,  # Make datetime available in template
            'computed_values': computed_values,  # Pass computed values separately
        }


