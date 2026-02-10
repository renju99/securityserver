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

