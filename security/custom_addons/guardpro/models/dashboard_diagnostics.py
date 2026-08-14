# -*- coding: utf-8 -*-
"""Dashboard Diagnostics - Helper methods to debug data issues."""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ClientDashboard(models.Model):
    """Add diagnostic methods to Client Dashboard."""
    
    _inherit = 'client.dashboard'
    
    def action_diagnostic_report(self):
        """Generate diagnostic report to help debug data issues."""
        self.ensure_one()
        
        # Collect diagnostic information
        diagnostics = []
        
        # Dashboard Info
        diagnostics.append("=" * 60)
        diagnostics.append("DASHBOARD DIAGNOSTICS REPORT")
        diagnostics.append("=" * 60)
        diagnostics.append(f"Client: {self.client_id.name if self.client_id else 'Not Set'}")
        diagnostics.append(f"Site: {self.site_id.name if self.site_id else 'All Projects'}")
        diagnostics.append(f"Date Range: {self.date_from} to {self.date_to}")
        diagnostics.append("")
        
        # Get site domain
        site_domain = []
        if self.site_id:
            site_domain = [('site_id', '=', self.site_id.id)]
            site_ids = [self.site_id.id]
        elif self.client_id:
            sites = self.env['client.site'].search([('client_id', '=', self.client_id.id)])
            site_domain = [('site_id', 'in', sites.ids)]
            site_ids = sites.ids
            diagnostics.append(f"Sites for client: {len(sites)} sites")
            for site in sites:
                diagnostics.append(f"  - {site.name} (ID: {site.id})")
        else:
            site_ids = []
            diagnostics.append("⚠️  WARNING: No client or site selected!")
        
        diagnostics.append("")
        diagnostics.append("-" * 60)
        diagnostics.append("INCIDENT DATA CHECK")
        diagnostics.append("-" * 60)
        
        # Check ALL incidents (no filter)
        all_incidents = self.env['incident.report'].search([])
        diagnostics.append(f"Total incidents in database: {len(all_incidents)}")
        
        # Check incidents for the sites
        if site_ids:
            site_incidents = self.env['incident.report'].search([('site_id', 'in', site_ids)])
            diagnostics.append(f"Incidents for selected site(s): {len(site_incidents)}")
            
            if site_incidents:
                diagnostics.append("\nIncidents found:")
                for inc in site_incidents[:10]:  # Show max 10
                    diagnostics.append(f"  - ID: {inc.id}")
                    diagnostics.append(f"    Title: {inc.title}")
                    diagnostics.append(f"    Site: {inc.site_id.name}")
                    diagnostics.append(f"    Date/Time: {inc.incident_datetime}")
                    diagnostics.append(f"    Status: {inc.status}")
                    diagnostics.append(f"    Severity: {inc.severity}")
                    diagnostics.append("")
        
        # Check incidents in date range
        diagnostics.append("-" * 60)
        diagnostics.append("DATE RANGE FILTER CHECK")
        diagnostics.append("-" * 60)
        
        incident_domain = [
            ('incident_datetime', '>=', fields.Datetime.to_datetime(self.date_from)),
            ('incident_datetime', '<=', fields.Datetime.to_datetime(self.date_to))
        ]
        
        diagnostics.append(f"Filtering from: {fields.Datetime.to_datetime(self.date_from)}")
        diagnostics.append(f"Filtering to: {fields.Datetime.to_datetime(self.date_to)}")
        diagnostics.append("")
        
        date_filtered = self.env['incident.report'].search(incident_domain)
        diagnostics.append(f"Incidents in date range (all sites): {len(date_filtered)}")
        
        # Check incidents with both site and date filter
        final_domain = incident_domain + site_domain
        final_incidents = self.env['incident.report'].search(final_domain)
        
        diagnostics.append(f"Incidents matching ALL filters: {len(final_incidents)}")
        
        if final_incidents:
            diagnostics.append("\n✅ FOUND INCIDENTS:")
            for inc in final_incidents:
                diagnostics.append(f"  - [{inc.name}] {inc.title}")
                diagnostics.append(f"    DateTime: {inc.incident_datetime}")
                diagnostics.append(f"    Site: {inc.site_id.name}")
                diagnostics.append(f"    Severity: {inc.severity}")
                diagnostics.append(f"    Status: {inc.status}")
        else:
            diagnostics.append("\n❌ NO INCIDENTS FOUND!")
            diagnostics.append("\nPossible reasons:")
            diagnostics.append("1. Incident date is outside selected date range")
            diagnostics.append("2. Incident is at a different site/client")
            diagnostics.append("3. Incident datetime field is not set correctly")
        
        # Dashboard computed values
        diagnostics.append("")
        diagnostics.append("-" * 60)
        diagnostics.append("DASHBOARD COMPUTED VALUES")
        diagnostics.append("-" * 60)
        diagnostics.append(f"total_incidents: {self.total_incidents}")
        diagnostics.append(f"critical_incidents: {self.critical_incidents}")
        diagnostics.append(f"resolved_incidents: {self.resolved_incidents}")
        diagnostics.append(f"incident_resolution_rate: {self.incident_resolution_rate}%")
        
        # Additional checks
        diagnostics.append("")
        diagnostics.append("-" * 60)
        diagnostics.append("SHIFTS CHECK")
        diagnostics.append("-" * 60)
        
        shift_domain = [
            ('start_datetime', '>=', fields.Datetime.to_datetime(self.date_from)),
            ('start_datetime', '<=', fields.Datetime.to_datetime(self.date_to))
        ]
        shifts = self.env['guard.shift'].search(shift_domain + site_domain)
        diagnostics.append(f"Shifts in date range: {len(shifts)}")
        diagnostics.append(f"Dashboard total_shifts: {self.total_shifts}")
        diagnostics.append(f"Dashboard completed_shifts: {self.completed_shifts}")
        
        # Log everything
        full_report = "\n".join(diagnostics)
        _logger.info("\n" + full_report)
        
        # Return as notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Diagnostic Report Generated'),
                'message': _('Check the Odoo log file for detailed diagnostics. Found %s incidents.') % len(final_incidents),
                'type': 'info',
                'sticky': True,
            }
        }
    
    def action_show_incident_details(self):
        """Show all incidents with their dates for debugging."""
        self.ensure_one()
        
        # Get all incidents for this client/site
        if self.site_id:
            domain = [('site_id', '=', self.site_id.id)]
        elif self.client_id:
            sites = self.env['client.site'].search([('client_id', '=', self.client_id.id)])
            domain = [('site_id', 'in', sites.ids)]
        else:
            domain = []
        
        return {
            'name': _('All Incidents (No Date Filter)'),
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'create': False}
        }

