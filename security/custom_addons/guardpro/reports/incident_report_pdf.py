# -*- coding: utf-8 -*-
"""Incident Report PDF generator."""

from odoo import models, api


class IncidentReportPdf(models.AbstractModel):
    """Abstract model for incident report PDF generation."""

    _name = 'report.guardpro.incident_report_pdf_template'
    _description = 'Incident Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for the incident report."""
        docs = self.env['incident.report'].browse(docids)
        
        return {
            'doc_ids': docids,
            'doc_model': 'incident.report',
            'docs': docs,
            'data': data,
        }


class MedicalIncidentReportPdf(models.AbstractModel):
    """Medical Emergency Incident Report PDF."""

    _name = 'report.guardpro.incident_medical_pdf_template'
    _description = 'Medical Emergency Incident Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for medical incident report."""
        docs = self.env['incident.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'incident.report',
            'docs': docs,
            'data': data,
        }


class FireIncidentReportPdf(models.AbstractModel):
    """Fire/Smoke Incident Report PDF."""

    _name = 'report.guardpro.incident_fire_pdf_template'
    _description = 'Fire/Smoke Incident Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for fire incident report."""
        docs = self.env['incident.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'incident.report',
            'docs': docs,
            'data': data,
        }


class SecurityIncidentReportPdf(models.AbstractModel):
    """Security/Theft Incident Report PDF."""

    _name = 'report.guardpro.incident_security_pdf_template'
    _description = 'Security/Theft Incident Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for security incident report."""
        docs = self.env['incident.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'incident.report',
            'docs': docs,
            'data': data,
        }


class VehicleIncidentReportPdf(models.AbstractModel):
    """Vehicle Incident Report PDF."""

    _name = 'report.guardpro.incident_vehicle_pdf_template'
    _description = 'Vehicle Incident Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for vehicle incident report."""
        docs = self.env['incident.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'incident.report',
            'docs': docs,
            'data': data,
        }


class SafetyHazardReportPdf(models.AbstractModel):
    """Safety Hazard Report PDF."""

    _name = 'report.guardpro.incident_safety_pdf_template'
    _description = 'Safety Hazard Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for safety hazard report."""
        docs = self.env['incident.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'incident.report',
            'docs': docs,
            'data': data,
        }


class StatementIncidentReportPdf(models.AbstractModel):
    """Statement Form Incident Report PDF."""

    _name = 'report.guardpro.incident_statement_pdf_template'
    _description = 'Statement Form Incident Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for statement incident report."""
        docs = self.env['incident.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'incident.report',
            'docs': docs,
            'data': data,
        }


class FoundItemIncidentReportPdf(models.AbstractModel):
    """Found Item Incident Report PDF."""

    _name = 'report.guardpro.incident_found_item_pdf_template'
    _description = 'Found Item Incident Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for found item incident report."""
        docs = self.env['incident.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'incident.report',
            'docs': docs,
            'data': data,
        }


class ReturnFormIncidentReportPdf(models.AbstractModel):
    """Return Form Incident Report PDF."""

    _name = 'report.guardpro.incident_return_form_pdf_template'
    _description = 'Return Form Incident Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for return form incident report."""
        docs = self.env['incident.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'incident.report',
            'docs': docs,
            'data': data,
        }


class CommunityViolationIncidentReportPdf(models.AbstractModel):
    """Community Violation Incident Report PDF."""

    _name = 'report.guardpro.incident_community_violation_pdf_template'
    _description = 'Community Violation Incident Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get values for community violation incident report."""
        docs = self.env['incident.report'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'incident.report',
            'docs': docs,
            'data': data,
        }

