# -*- coding: utf-8 -*-
"""Enhanced Audit Trail with Tamper-Proof Logging."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import hashlib
from datetime import datetime, date
import logging

_logger = logging.getLogger(__name__)


class AuditLog(models.Model):
    """Tamper-proof audit logging system."""
    
    _name = 'audit.log'
    _description = 'Audit Log'
    _order = 'create_date desc'
    _rec_name = 'action_type'
    
    # Prevent modifications
    _log_access = False
    
    # Event Information
    action_type = fields.Selection([
        ('create', 'Create'),
        ('write', 'Update'),
        ('unlink', 'Delete'),
        ('read', 'Read Sensitive'),
        ('action', 'Action Executed'),
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('export', 'Data Export'),
        ('import', 'Data Import')
    ], string='Action Type', required=True)
    
    model_name = fields.Char(
        string='Model',
        required=True
    )
    
    record_id = fields.Integer(
        string='Record ID'
    )
    
    record_name = fields.Char(
        string='Record Name'
    )
    
    # User Information
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='restrict'
    )
    
    # Network Information
    ip_address = fields.Char(
        string='IP Address'
    )
    
    user_agent = fields.Char(
        string='User Agent'
    )
    
    device_fingerprint = fields.Char(
        string='Device Fingerprint',
        help='Unique device identifier'
    )
    
    # Location Information  
    geo_location = fields.Char(
        string='Geographic Location',
        help='City, Country'
    )
    
    # Change Details
    old_values = fields.Text(
        string='Old Values',
        help='JSON of previous values'
    )
    
    new_values = fields.Text(
        string='New Values',
        help='JSON of new values'
    )
    
    changes_summary = fields.Text(
        string='Changes Summary',
        compute='_compute_changes_summary'
    )
    
    # Timestamp (immutable)
    create_date = fields.Datetime(
        string='Timestamp',
        readonly=True
    )
    
    # Tamper Protection
    hash_value = fields.Char(
        string='Hash',
        readonly=True,
        help='SHA-256 hash for tamper detection'
    )
    
    previous_hash = fields.Char(
        string='Previous Hash',
        readonly=True,
        help='Hash of previous audit record (blockchain-style)'
    )
    
    is_tampered = fields.Boolean(
        string='Tampered',
        compute='_compute_is_tampered',
        store=True
    )
    
    # Additional Context
    notes = fields.Text(
        string='Notes'
    )
    
    @api.depends('old_values', 'new_values')
    def _compute_changes_summary(self):
        """Generate human-readable changes summary."""
        for record in self:
            if not record.old_values or not record.new_values:
                record.changes_summary = ''
                continue
            
            try:
                old = json.loads(record.old_values)
                new = json.loads(record.new_values)
                
                changes = []
                for key in new:
                    if key in old and old[key] != new[key]:
                        changes.append(f"{key}: {old[key]} → {new[key]}")
                    elif key not in old:
                        changes.append(f"{key}: (new) → {new[key]}")
                
                record.changes_summary = '\n'.join(changes)
            except:
                record.changes_summary = ''
    
    def _compute_is_tampered(self):
        """Check if record has been tampered with."""
        for record in self:
            if not record.hash_value:
                record.is_tampered = False
                continue
            
            # Recompute hash
            data = f"{record.action_type}|{record.model_name}|{record.record_id}|{record.user_id.id}|{record.create_date}"
            computed_hash = hashlib.sha256(data.encode()).hexdigest()
            
            record.is_tampered = (computed_hash != record.hash_value)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create audit log with hash."""
        # Get previous hash for blockchain-style linking (use sudo to bypass access restrictions)
        last_log = self.sudo().search([], order='create_date desc', limit=1)
        previous_hash = last_log.hash_value if last_log else '0'
        
        for vals in vals_list:
            # Set previous hash
            vals['previous_hash'] = previous_hash
            
            # Generate hash
            timestamp_str = fields.Datetime.to_string(fields.Datetime.now())
            data = f"{vals.get('action_type')}|{vals.get('model_name')}|{vals.get('record_id')}|{vals.get('user_id')}|{timestamp_str}"
            vals['hash_value'] = hashlib.sha256(data.encode()).hexdigest()
            
            # Get IP address from request
            try:
                from odoo.http import request
                if request:
                    vals['ip_address'] = request.httprequest.remote_addr
                    vals['user_agent'] = request.httprequest.headers.get('User-Agent', '')
            except:
                pass
        
        return super(AuditLog, self.sudo()).create(vals_list)
    
    def write(self, vals):
        """Prevent modifications to audit logs."""
        raise UserError(_('Audit logs cannot be modified!'))
    
    def unlink(self):
        """Prevent deletion of audit logs."""
        raise UserError(_('Audit logs cannot be deleted!'))
    
    @api.model
    def log_action(self, model_name, record_id, action_type, record_name=None, old_values=None, new_values=None, notes=None):
        """Log an audit event."""
        vals = {
            'model_name': model_name,
            'record_id': record_id,
            'action_type': action_type,
            'record_name': record_name or '',
            'user_id': self.env.user.id,
            'notes': notes or ''
        }
        
        if old_values:
            vals['old_values'] = json.dumps(old_values)
        if new_values:
            vals['new_values'] = json.dumps(new_values)
        
        try:
            self.create(vals)
        except Exception as e:
            _logger.error('Failed to create audit log: %s', str(e))
    
    def action_verify_integrity(self):
        """Verify audit log integrity."""
        self.ensure_one()
        
        if self.is_tampered:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('This audit log may have been tampered with!'),
                    'type': 'danger',
                    'sticky': True,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Verified'),
                    'message': _('Audit log integrity verified.'),
                    'type': 'success',
                    'sticky': False,
                }
            }


# Mixin to add automatic audit logging to models
class AuditMixin(models.AbstractModel):
    """Mixin to enable automatic audit logging."""
    
    _name = 'audit.mixin'
    _description = 'Audit Logging Mixin'
    
    @api.model_create_multi
    def create(self, vals_list):
        """Log create actions."""
        records = super().create(vals_list)
        
        for idx, record in enumerate(records):
            # Get the corresponding vals
            vals = vals_list[idx] if idx < len(vals_list) else vals_list[0]
            
            # Serialize new values
            serialized_values = {}
            for key, val in vals.items():
                if key != 'id' and key in record._fields:
                    field = record._fields[key]
                    if field.type == 'many2one':
                        if val:
                            rec = self.env[field.comodel_name].browse(val)
                            serialized_values[key] = {'id': val, 'name': rec.display_name}
                        else:
                            serialized_values[key] = None
                    elif field.type in ('one2many', 'many2many'):
                        serialized_values[key] = str(val)
                    elif field.type in ('date', 'datetime'):
                        # Serialize datetime objects to ISO format
                        if val:
                            # Handle both datetime objects and string values (from XML)
                            serialized_values[key] = val.isoformat() if hasattr(val, 'isoformat') else val
                        else:
                            serialized_values[key] = None
                    else:
                        serialized_values[key] = val
                elif key != 'id':
                    # For fields not in _fields, try to serialize if it's a datetime or date
                    if isinstance(val, (datetime, date)):
                        serialized_values[key] = val.isoformat()
                    else:
                        serialized_values[key] = val
            
            self.env['audit.log'].log_action(
                model_name=self._name,
                record_id=record.id,
                action_type='create',
                record_name=record.display_name,
                new_values=serialized_values
            )
        
        return records
    
    def _serialize_value(self, field_name, value):
        """Convert field value to JSON-serializable format."""
        if value is False or value is None:
            return value
        
        # Get field type
        if field_name not in self._fields:
            return str(value)
        
        field = self._fields[field_name]
        field_type = field.type
        
        # Handle different field types
        if field_type == 'many2one':
            return {'id': value.id, 'name': value.display_name} if value else None
        elif field_type in ('one2many', 'many2many'):
            # Handle recordsets properly
            try:
                return [{'id': rec.id, 'name': rec.display_name} for rec in value] if value else []
            except Exception:
                # Fallback for command tuples or invalid recordsets
                return str(value)
        elif field_type in ('date', 'datetime'):
            return value.isoformat() if value else None
        elif field_type == 'binary':
            return '<binary data>' if value else None
        elif hasattr(value, 'id'):
            # Any other recordset
            try:
                return {'id': value.id, 'name': getattr(value, 'display_name', str(value))}
            except Exception:
                return str(value)
        else:
            return value
    
    def write(self, vals):
        """Log update actions."""
        # Capture old values
        old_values = {}
        for record in self:
            old_values[record.id] = {}
            for key in vals.keys():
                if hasattr(record, key):
                    old_val = getattr(record, key)
                    old_values[record.id][key] = record._serialize_value(key, old_val)
        
        result = super().write(vals)
        
        # Serialize new values
        serialized_new_values = {}
        for key, val in vals.items():
            if key in self._fields:
                field = self._fields[key]
                if field.type == 'many2one':
                    try:
                        if val:
                            rec = self.env[field.comodel_name].browse(val)
                            serialized_new_values[key] = {'id': val, 'name': rec.display_name}
                        else:
                            serialized_new_values[key] = None
                    except Exception:
                        serialized_new_values[key] = str(val)
                elif field.type in ('one2many', 'many2many'):
                    # For x2many, vals typically contains command tuples
                    # Parse command tuples to extract IDs where possible
                    try:
                        if isinstance(val, (list, tuple)):
                            # Command tuples like [(6, 0, [ids])], [(4, id)], etc.
                            ids = []
                            for cmd in val:
                                if isinstance(cmd, (list, tuple)) and len(cmd) >= 3:
                                    # (6, 0, [ids]) or (1, id, vals)
                                    if cmd[0] in (6,) and isinstance(cmd[2], list):
                                        ids.extend(cmd[2])
                                    elif cmd[0] in (4,) and len(cmd) >= 2:
                                        ids.append(cmd[1])
                            if ids:
                                records = self.env[field.comodel_name].browse(ids)
                                serialized_new_values[key] = [{'id': r.id, 'name': r.display_name} for r in records]
                            else:
                                serialized_new_values[key] = str(val)
                        else:
                            serialized_new_values[key] = str(val)
                    except Exception:
                        serialized_new_values[key] = str(val)
                elif field.type in ('date', 'datetime'):
                    # Serialize datetime objects to ISO format
                    try:
                        if val:
                            # Handle both datetime objects and string values (from XML)
                            serialized_new_values[key] = val.isoformat() if hasattr(val, 'isoformat') else val
                        else:
                            serialized_new_values[key] = None
                    except Exception:
                        serialized_new_values[key] = str(val)
                else:
                    serialized_new_values[key] = val
            else:
                # For fields not in _fields, try to serialize if it's a datetime or date
                if isinstance(val, (datetime, date)):
                    serialized_new_values[key] = val.isoformat()
                else:
                    serialized_new_values[key] = val
        
        # Log changes
        for record in self:
            if record.id in old_values:
                self.env['audit.log'].log_action(
                    model_name=self._name,
                    record_id=record.id,
                    action_type='write',
                    record_name=record.display_name,
                    old_values=old_values[record.id],
                    new_values=serialized_new_values
                )
        
        return result
    
    def unlink(self):
        """Log delete actions."""
        for record in self:
            self.env['audit.log'].log_action(
                model_name=self._name,
                record_id=record.id,
                action_type='unlink',
                record_name=record.display_name
            )
        
        return super().unlink()


# Add audit logging to critical models
# Temporarily disabled to resolve Many2many field conflicts (Oct 2025)
# TODO: Re-enable audit logging using a different approach
# class IncidentReportAudit(models.Model):
#     """Add audit logging to incident reports."""
#     _inherit = ['incident.report', 'audit.mixin']
#     _description = 'Incident Report Audit'


# class GuardShiftAudit(models.Model):
#     """Add audit logging to guard shifts."""
#     _inherit = ['guard.shift', 'audit.mixin']
#     _description = 'Guard Shift Audit'


# class DailyActivityReportAudit(models.Model):
#     """Add audit logging to daily activity reports."""
#     _inherit = ['daily.activity.report', 'audit.mixin']
#     _description = 'Daily Activity Report Audit'


# class GuardPerformanceAudit(models.Model):
#     """Add audit logging to guard performance reviews."""
#     _inherit = ['guard.performance.review', 'audit.mixin']
#     _description = 'Guard Performance Review Audit'


# class ComplianceAuditLog(models.Model):
#     """Add audit logging to compliance audits."""
#     _inherit = ['compliance.audit', 'audit.mixin']
#     _description = 'Compliance Audit Log'


# class VisitorManagementAudit(models.Model):
#     """Add audit logging to visitor management."""
#     _inherit = ['visitor.management', 'audit.mixin']
#     _description = 'Visitor Management Audit'


# class EmergencyBroadcastAudit(models.Model):
#     """Add audit logging to emergency broadcasts."""
#     _inherit = ['emergency.broadcast', 'audit.mixin']
#     _description = 'Emergency Broadcast Audit'


# Note: sla.management model doesn't exist. The actual SLA models are:
# sla.definition, sla.kpi, and sla.performance
# Uncomment and adjust if audit logging is needed for SLA models:
# class SLAPerformanceAudit(models.Model):
#     """Add audit logging to SLA performance tracking."""
#     _inherit = 'sla.performance'
#     _inherits_audit = True
#     _description = 'SLA Performance Audit'

