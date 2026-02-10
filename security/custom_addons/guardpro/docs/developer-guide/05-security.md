# GuardPro Security

## Overview

GuardPro implements a comprehensive security framework that protects sensitive security data, ensures proper access control, and maintains audit trails for compliance. The security system is built on Odoo's robust security architecture with additional layers specific to security management operations.

## Security Architecture

### Multi-Layer Security Model

```
Security Layers
├── Authentication Layer
│   ├── User Authentication
│   ├── Session Management
│   ├── Password Policies
│   └── Multi-Factor Authentication
├── Authorization Layer
│   ├── Role-Based Access Control
│   ├── Record-Level Security
│   ├── Field-Level Security
│   └── API Access Control
├── Data Protection Layer
│   ├── Encryption at Rest
│   ├── Encryption in Transit
│   ├── Data Masking
│   └── Backup Security
├── Audit & Compliance Layer
│   ├── Audit Trails
│   ├── Compliance Monitoring
│   ├── Incident Logging
│   └── Regulatory Reporting
└── Network Security Layer
    ├── Firewall Configuration
    ├── VPN Access
    ├── Intrusion Detection
    └── Network Monitoring
```

## Authentication System

### User Authentication

```python
# Enhanced Authentication System
class GuardProAuthentication:
    def __init__(self, env):
        self.env = env
        self.max_login_attempts = 5
        self.lockout_duration = 30  # minutes
        self.session_timeout = 8  # hours
    
    def authenticate_user(self, login, password, device_info=None):
        """Enhanced user authentication with security features"""
        # Check if user is locked out
        if self._is_user_locked_out(login):
            raise AccessDenied(_("Account is temporarily locked. Please try again later."))
        
        # Attempt authentication
        try:
            user = self._authenticate_credentials(login, password)
            
            # Log successful login
            self._log_login_attempt(login, True, device_info)
            
            # Reset failed attempts
            self._reset_failed_attempts(login)
            
            # Check if MFA is required
            if self._requires_mfa(user):
                return self._initiate_mfa(user)
            
            # Create session
            session = self._create_secure_session(user, device_info)
            
            return {
                'status': 'success',
                'user_id': user.id,
                'session_token': session.token,
                'expires_at': session.expires_at
            }
            
        except AccessDenied:
            # Log failed login
            self._log_login_attempt(login, False, device_info)
            
            # Increment failed attempts
            self._increment_failed_attempts(login)
            
            raise AccessDenied(_("Invalid credentials"))
    
    def _authenticate_credentials(self, login, password):
        """Authenticate user credentials"""
        # Check password complexity
        if not self._validate_password_complexity(password):
            raise AccessDenied(_("Password does not meet complexity requirements"))
        
        # Authenticate with Odoo
        user = self.env['res.users'].sudo().search([('login', '=', login)])
        
        if not user or not user._crypt_context().verify(password, user.password):
            raise AccessDenied(_("Invalid credentials"))
        
        # Check if user is active
        if not user.active:
            raise AccessDenied(_("Account is deactivated"))
        
        # Check if user has GuardPro access
        if not user.has_group('guardpro.group_guardpro_user'):
            raise AccessDenied(_("Access denied to GuardPro system"))
        
        return user
    
    def _requires_mfa(self, user):
        """Check if user requires multi-factor authentication"""
        # Check if MFA is enabled for user
        if user.mfa_enabled:
            return True
        
        # Check if MFA is required for admin users
        if user.has_group('guardpro.group_guardpro_admin'):
            return True
        
        # Check if MFA is required for sensitive operations
        if user.has_group('guardpro.group_guardpro_manager'):
            return True
        
        return False
    
    def _initiate_mfa(self, user):
        """Initiate multi-factor authentication"""
        # Generate MFA token
        mfa_token = self._generate_mfa_token(user)
        
        # Send MFA code via SMS or email
        if user.mfa_method == 'sms':
            self._send_sms_mfa(user, mfa_token)
        elif user.mfa_method == 'email':
            self._send_email_mfa(user, mfa_token)
        
        # Create MFA session
        mfa_session = self.env['guard.mfa.session'].create({
            'user_id': user.id,
            'token': mfa_token,
            'expires_at': fields.Datetime.now() + timedelta(minutes=5),
            'status': 'pending'
        })
        
        return {
            'status': 'mfa_required',
            'mfa_session_id': mfa_session.id,
            'mfa_method': user.mfa_method
        }
    
    def _create_secure_session(self, user, device_info):
        """Create secure user session"""
        # Generate session token
        session_token = self._generate_session_token()
        
        # Create session record
        session = self.env['guard.user.session'].create({
            'user_id': user.id,
            'token': session_token,
            'device_info': device_info,
            'ip_address': self._get_client_ip(),
            'user_agent': self._get_user_agent(),
            'expires_at': fields.Datetime.now() + timedelta(hours=self.session_timeout),
            'status': 'active'
        })
        
        return session
    
    def _log_login_attempt(self, login, success, device_info):
        """Log login attempt"""
        self.env['guard.login.log'].create({
            'login': login,
            'success': success,
            'ip_address': self._get_client_ip(),
            'user_agent': self._get_user_agent(),
            'device_info': device_info,
            'timestamp': fields.Datetime.now()
        })
    
    def _is_user_locked_out(self, login):
        """Check if user is locked out"""
        lockout_record = self.env['guard.login.lockout'].search([
            ('login', '=', login),
            ('locked_until', '>', fields.Datetime.now())
        ])
        
        return bool(lockout_record)
    
    def _increment_failed_attempts(self, login):
        """Increment failed login attempts"""
        attempts = self.env['guard.login.attempts'].search([('login', '=', login)])
        
        if attempts:
            attempts.write({
                'attempt_count': attempts.attempt_count + 1,
                'last_attempt': fields.Datetime.now()
            })
            
            # Lock account if max attempts reached
            if attempts.attempt_count >= self.max_login_attempts:
                self._lock_user_account(login)
        else:
            self.env['guard.login.attempts'].create({
                'login': login,
                'attempt_count': 1,
                'last_attempt': fields.Datetime.now()
            })
    
    def _lock_user_account(self, login):
        """Lock user account"""
        locked_until = fields.Datetime.now() + timedelta(minutes=self.lockout_duration)
        
        self.env['guard.login.lockout'].create({
            'login': login,
            'locked_until': locked_until,
            'reason': 'max_failed_attempts'
        })
        
        # Notify administrators
        self._notify_account_lockout(login)
    
    def _validate_password_complexity(self, password):
        """Validate password complexity"""
        # Minimum length
        if len(password) < 8:
            return False
        
        # Must contain uppercase letter
        if not any(c.isupper() for c in password):
            return False
        
        # Must contain lowercase letter
        if not any(c.islower() for c in password):
            return False
        
        # Must contain digit
        if not any(c.isdigit() for c in password):
            return False
        
        # Must contain special character
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False
        
        return True
```

### Session Management

```python
# Session Management System
class GuardProSessionManager:
    def __init__(self, env):
        self.env = env
    
    def validate_session(self, session_token):
        """Validate user session"""
        session = self.env['guard.user.session'].search([
            ('token', '=', session_token),
            ('status', '=', 'active'),
            ('expires_at', '>', fields.Datetime.now())
        ])
        
        if not session:
            raise AccessDenied(_("Invalid or expired session"))
        
        # Update last activity
        session.write({'last_activity': fields.Datetime.now()})
        
        return session.user_id
    
    def terminate_session(self, session_token):
        """Terminate user session"""
        session = self.env['guard.user.session'].search([
            ('token', '=', session_token)
        ])
        
        if session:
            session.write({'status': 'terminated'})
    
    def terminate_all_sessions(self, user_id):
        """Terminate all sessions for user"""
        sessions = self.env['guard.user.session'].search([
            ('user_id', '=', user_id),
            ('status', '=', 'active')
        ])
        
        sessions.write({'status': 'terminated'})
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        expired_sessions = self.env['guard.user.session'].search([
            ('expires_at', '<', fields.Datetime.now()),
            ('status', '=', 'active')
        ])
        
        expired_sessions.write({'status': 'expired'})
    
    def get_active_sessions(self, user_id):
        """Get active sessions for user"""
        return self.env['guard.user.session'].search([
            ('user_id', '=', user_id),
            ('status', '=', 'active'),
            ('expires_at', '>', fields.Datetime.now())
        ])
```

## Authorization System

### Role-Based Access Control

```python
# Role-Based Access Control System
class GuardProRBAC:
    def __init__(self, env):
        self.env = env
        self.roles = {
            'admin': 'guardpro.group_guardpro_admin',
            'manager': 'guardpro.group_guardpro_manager',
            'supervisor': 'guardpro.group_guardpro_supervisor',
            'guard': 'guardpro.group_guardpro_guard',
            'client': 'guardpro.group_guardpro_client'
        }
    
    def check_permission(self, user_id, resource, action, context=None):
        """Check if user has permission for resource action"""
        user = self.env['res.users'].browse(user_id)
        
        # Admin has full access
        if user.has_group(self.roles['admin']):
            return True
        
        # Check role-specific permissions
        if resource == 'guard.profile':
            return self._check_guard_permission(user, action, context)
        elif resource == 'guard.shift':
            return self._check_shift_permission(user, action, context)
        elif resource == 'guard.incident':
            return self._check_incident_permission(user, action, context)
        elif resource == 'guard.site':
            return self._check_site_permission(user, action, context)
        
        return False
    
    def _check_guard_permission(self, user, action, context):
        """Check guard profile permissions"""
        if action == 'read':
            # All users can read guard profiles they have access to
            return True
        elif action == 'write':
            # Managers and supervisors can modify guards at their sites
            if user.has_group(self.roles['manager']) or user.has_group(self.roles['supervisor']):
                return True
            # Guards can modify their own profile
            if user.has_group(self.roles['guard']):
                return context and context.get('guard_id') == user.guard_id.id
        elif action == 'create':
            # Only managers can create guard profiles
            return user.has_group(self.roles['manager'])
        elif action == 'delete':
            # Only admins can delete guard profiles
            return user.has_group(self.roles['admin'])
        
        return False
    
    def _check_shift_permission(self, user, action, context):
        """Check shift permissions"""
        if action == 'read':
            return True
        elif action == 'write':
            # Managers and supervisors can modify shifts at their sites
            if user.has_group(self.roles['manager']) or user.has_group(self.roles['supervisor']):
                return True
            # Guards can modify their own shifts
            if user.has_group(self.roles['guard']):
                return context and context.get('guard_id') == user.guard_id.id
        elif action == 'create':
            # Managers and supervisors can create shifts
            return user.has_group(self.roles['manager']) or user.has_group(self.roles['supervisor'])
        elif action == 'delete':
            # Only managers can delete shifts
            return user.has_group(self.roles['manager'])
        
        return False
    
    def _check_incident_permission(self, user, action, context):
        """Check incident permissions"""
        if action == 'read':
            return True
        elif action == 'write':
            # Managers and supervisors can modify incidents at their sites
            if user.has_group(self.roles['manager']) or user.has_group(self.roles['supervisor']):
                return True
            # Guards can modify incidents they reported
            if user.has_group(self.roles['guard']):
                return context and context.get('reported_by') == user.guard_id.id
        elif action == 'create':
            # All users can create incidents
            return True
        elif action == 'delete':
            # Only admins can delete incidents
            return user.has_group(self.roles['admin'])
        
        return False
    
    def _check_site_permission(self, user, action, context):
        """Check site permissions"""
        if action == 'read':
            return True
        elif action == 'write':
            # Only managers can modify sites
            return user.has_group(self.roles['manager'])
        elif action == 'create':
            # Only managers can create sites
            return user.has_group(self.roles['manager'])
        elif action == 'delete':
            # Only admins can delete sites
            return user.has_group(self.roles['admin'])
        
        return False
```

### Record-Level Security

```python
# Record-Level Security Rules
class GuardProRecordSecurity:
    def __init__(self, env):
        self.env = env
    
    def get_guard_domain(self, user_id):
        """Get domain for guard records based on user access"""
        user = self.env['res.users'].browse(user_id)
        
        if user.has_group('guardpro.group_guardpro_admin'):
            return []
        elif user.has_group('guardpro.group_guardpro_manager'):
            return [('site_ids', 'in', user.site_ids.ids)]
        elif user.has_group('guardpro.group_guardpro_supervisor'):
            return [('site_ids', 'in', user.site_ids.ids)]
        elif user.has_group('guardpro.group_guardpro_guard'):
            return [('id', '=', user.guard_id.id)]
        else:
            return [('id', '=', False)]
    
    def get_shift_domain(self, user_id):
        """Get domain for shift records based on user access"""
        user = self.env['res.users'].browse(user_id)
        
        if user.has_group('guardpro.group_guardpro_admin'):
            return []
        elif user.has_group('guardpro.group_guardpro_manager'):
            return [('site_id', 'in', user.site_ids.ids)]
        elif user.has_group('guardpro.group_guardpro_supervisor'):
            return [('site_id', 'in', user.site_ids.ids)]
        elif user.has_group('guardpro.group_guardpro_guard'):
            return [('guard_id', '=', user.guard_id.id)]
        else:
            return [('id', '=', False)]
    
    def get_incident_domain(self, user_id):
        """Get domain for incident records based on user access"""
        user = self.env['res.users'].browse(user_id)
        
        if user.has_group('guardpro.group_guardpro_admin'):
            return []
        elif user.has_group('guardpro.group_guardpro_manager'):
            return [('site_id', 'in', user.site_ids.ids)]
        elif user.has_group('guardpro.group_guardpro_supervisor'):
            return [('site_id', 'in', user.site_ids.ids)]
        elif user.has_group('guardpro.group_guardpro_guard'):
            return [('reported_by', '=', user.guard_id.id)]
        elif user.has_group('guardpro.group_guardpro_client'):
            return [('site_id', 'in', user.client_site_ids.ids)]
        else:
            return [('id', '=', False)]
    
    def get_site_domain(self, user_id):
        """Get domain for site records based on user access"""
        user = self.env['res.users'].browse(user_id)
        
        if user.has_group('guardpro.group_guardpro_admin'):
            return []
        elif user.has_group('guardpro.group_guardpro_manager'):
            return [('id', 'in', user.site_ids.ids)]
        elif user.has_group('guardpro.group_guardpro_supervisor'):
            return [('id', 'in', user.site_ids.ids)]
        elif user.has_group('guardpro.group_guardpro_guard'):
            return [('id', 'in', user.guard_id.site_ids.ids)]
        elif user.has_group('guardpro.group_guardpro_client'):
            return [('id', 'in', user.client_site_ids.ids)]
        else:
            return [('id', '=', False)]
```

## Data Protection

### Encryption System

```python
# Data Encryption System
class GuardProEncryption:
    def __init__(self, env):
        self.env = env
        self.encryption_key = self._get_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
    
    def encrypt_sensitive_data(self, data):
        """Encrypt sensitive data"""
        if not data:
            return data
        
        try:
            encrypted_data = self.cipher_suite.encrypt(data.encode())
            return encrypted_data.decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt_sensitive_data(self, encrypted_data):
        """Decrypt sensitive data"""
        if not encrypted_data:
            return encrypted_data
        
        try:
            decrypted_data = self.cipher_suite.decrypt(encrypted_data.encode())
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise
    
    def _get_encryption_key(self):
        """Get encryption key from system parameters"""
        key = self.env['ir.config_parameter'].sudo().get_param('guardpro.encryption_key')
        
        if not key:
            # Generate new key
            key = Fernet.generate_key()
            self.env['ir.config_parameter'].sudo().set_param('guardpro.encryption_key', key.decode())
        
        return key.encode()
    
    def encrypt_field(self, record, field_name):
        """Encrypt field value"""
        if hasattr(record, field_name):
            value = getattr(record, field_name)
            if value:
                encrypted_value = self.encrypt_sensitive_data(value)
                setattr(record, field_name, encrypted_value)
    
    def decrypt_field(self, record, field_name):
        """Decrypt field value"""
        if hasattr(record, field_name):
            value = getattr(record, field_name)
            if value:
                decrypted_value = self.decrypt_sensitive_data(value)
                setattr(record, field_name, decrypted_value)
```

### Data Masking

```python
# Data Masking System
class GuardProDataMasking:
    def __init__(self, env):
        self.env = env
    
    def mask_sensitive_data(self, data, mask_type='partial'):
        """Mask sensitive data based on type"""
        if not data:
            return data
        
        if mask_type == 'full':
            return '*' * len(str(data))
        elif mask_type == 'partial':
            return self._partial_mask(str(data))
        elif mask_type == 'email':
            return self._mask_email(str(data))
        elif mask_type == 'phone':
            return self._mask_phone(str(data))
        elif mask_type == 'ssn':
            return self._mask_ssn(str(data))
        
        return data
    
    def _partial_mask(self, data):
        """Partially mask data"""
        if len(data) <= 2:
            return '*' * len(data)
        
        visible_chars = max(1, len(data) // 4)
        masked_chars = len(data) - (2 * visible_chars)
        
        return data[:visible_chars] + '*' * masked_chars + data[-visible_chars:]
    
    def _mask_email(self, email):
        """Mask email address"""
        if '@' not in email:
            return self._partial_mask(email)
        
        local, domain = email.split('@', 1)
        masked_local = self._partial_mask(local)
        
        return f"{masked_local}@{domain}"
    
    def _mask_phone(self, phone):
        """Mask phone number"""
        # Remove non-digit characters
        digits = ''.join(filter(str.isdigit, phone))
        
        if len(digits) >= 10:
            return f"{digits[:3]}***{digits[-4:]}"
        else:
            return self._partial_mask(phone)
    
    def _mask_ssn(self, ssn):
        """Mask social security number"""
        # Remove non-digit characters
        digits = ''.join(filter(str.isdigit, ssn))
        
        if len(digits) == 9:
            return f"***-**-{digits[-4:]}"
        else:
            return '***-**-****'
    
    def get_masked_field_value(self, record, field_name, user_id):
        """Get masked field value based on user permissions"""
        user = self.env['res.users'].browse(user_id)
        
        # Check if user has permission to see unmasked data
        if self._can_see_unmasked_data(user, record, field_name):
            return getattr(record, field_name)
        
        # Return masked data
        value = getattr(record, field_name)
        return self.mask_sensitive_data(value, self._get_mask_type(field_name))
    
    def _can_see_unmasked_data(self, user, record, field_name):
        """Check if user can see unmasked data"""
        # Admin can see all unmasked data
        if user.has_group('guardpro.group_guardpro_admin'):
            return True
        
        # Managers can see unmasked data for their sites
        if user.has_group('guardpro.group_guardpro_manager'):
            if hasattr(record, 'site_id'):
                return record.site_id.id in user.site_ids.ids
        
        # Guards can see their own unmasked data
        if user.has_group('guardpro.group_guardpro_guard'):
            if hasattr(record, 'guard_id'):
                return record.guard_id.id == user.guard_id.id
        
        return False
    
    def _get_mask_type(self, field_name):
        """Get mask type for field"""
        mask_types = {
            'email': 'email',
            'phone': 'phone',
            'mobile': 'phone',
            'ssn': 'ssn',
            'social_security_number': 'ssn'
        }
        
        return mask_types.get(field_name, 'partial')
```

## Audit & Compliance

### Audit Trail System

```python
# Audit Trail System
class GuardProAuditTrail:
    def __init__(self, env):
        self.env = env
    
    def log_audit_event(self, event_type, user_id, resource_type, resource_id, 
                       action, old_values=None, new_values=None, context=None):
        """Log audit event"""
        audit_record = self.env['guard.audit.trail'].create({
            'event_type': event_type,
            'user_id': user_id,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'action': action,
            'old_values': old_values,
            'new_values': new_values,
            'ip_address': self._get_client_ip(),
            'user_agent': self._get_user_agent(),
            'timestamp': fields.Datetime.now(),
            'context': context
        })
        
        return audit_record
    
    def log_data_access(self, user_id, resource_type, resource_id, action):
        """Log data access"""
        self.log_audit_event(
            event_type='data_access',
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action
        )
    
    def log_data_modification(self, user_id, resource_type, resource_id, 
                            action, old_values, new_values):
        """Log data modification"""
        self.log_audit_event(
            event_type='data_modification',
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            old_values=old_values,
            new_values=new_values
        )
    
    def log_security_event(self, user_id, event_type, description, severity='medium'):
        """Log security event"""
        self.env['guard.security.event'].create({
            'user_id': user_id,
            'event_type': event_type,
            'description': description,
            'severity': severity,
            'ip_address': self._get_client_ip(),
            'user_agent': self._get_user_agent(),
            'timestamp': fields.Datetime.now()
        })
    
    def get_audit_trail(self, resource_type=None, resource_id=None, 
                       user_id=None, start_date=None, end_date=None):
        """Get audit trail records"""
        domain = []
        
        if resource_type:
            domain.append(('resource_type', '=', resource_type))
        if resource_id:
            domain.append(('resource_id', '=', resource_id))
        if user_id:
            domain.append(('user_id', '=', user_id))
        if start_date:
            domain.append(('timestamp', '>=', start_date))
        if end_date:
            domain.append(('timestamp', '<=', end_date))
        
        return self.env['guard.audit.trail'].search(domain, order='timestamp desc')
    
    def generate_compliance_report(self, start_date, end_date, report_type):
        """Generate compliance report"""
        report_data = {
            'start_date': start_date,
            'end_date': end_date,
            'report_type': report_type,
            'generated_at': fields.Datetime.now(),
            'generated_by': self.env.user.id
        }
        
        if report_type == 'access_log':
            report_data['access_logs'] = self._get_access_logs(start_date, end_date)
        elif report_type == 'data_modifications':
            report_data['modifications'] = self._get_data_modifications(start_date, end_date)
        elif report_type == 'security_events':
            report_data['security_events'] = self._get_security_events(start_date, end_date)
        
        return report_data
    
    def _get_access_logs(self, start_date, end_date):
        """Get access logs for period"""
        return self.env['guard.audit.trail'].search([
            ('event_type', '=', 'data_access'),
            ('timestamp', '>=', start_date),
            ('timestamp', '<=', end_date)
        ])
    
    def _get_data_modifications(self, start_date, end_date):
        """Get data modifications for period"""
        return self.env['guard.audit.trail'].search([
            ('event_type', '=', 'data_modification'),
            ('timestamp', '>=', start_date),
            ('timestamp', '<=', end_date)
        ])
    
    def _get_security_events(self, start_date, end_date):
        """Get security events for period"""
        return self.env['guard.security.event'].search([
            ('timestamp', '>=', start_date),
            ('timestamp', '<=', end_date)
        ])
```

### Compliance Monitoring

```python
# Compliance Monitoring System
class GuardProComplianceMonitor:
    def __init__(self, env):
        self.env = env
    
    def monitor_data_access(self, user_id, resource_type, resource_id):
        """Monitor data access for compliance"""
        user = self.env['res.users'].browse(user_id)
        
        # Check if access is authorized
        if not self._is_access_authorized(user, resource_type, resource_id):
            self._log_unauthorized_access(user, resource_type, resource_id)
            return False
        
        # Log authorized access
        self._log_authorized_access(user, resource_type, resource_id)
        
        # Check for suspicious patterns
        self._check_suspicious_patterns(user, resource_type, resource_id)
        
        return True
    
    def monitor_data_modification(self, user_id, resource_type, resource_id, 
                                old_values, new_values):
        """Monitor data modification for compliance"""
        user = self.env['res.users'].browse(user_id)
        
        # Check if modification is authorized
        if not self._is_modification_authorized(user, resource_type, resource_id):
            self._log_unauthorized_modification(user, resource_type, resource_id)
            return False
        
        # Check for sensitive data changes
        self._check_sensitive_data_changes(old_values, new_values)
        
        # Log authorized modification
        self._log_authorized_modification(user, resource_type, resource_id, old_values, new_values)
        
        return True
    
    def _is_access_authorized(self, user, resource_type, resource_id):
        """Check if access is authorized"""
        # Implement authorization logic based on user roles and resource access rules
        return True  # Simplified for example
    
    def _is_modification_authorized(self, user, resource_type, resource_id):
        """Check if modification is authorized"""
        # Implement authorization logic based on user roles and resource modification rules
        return True  # Simplified for example
    
    def _check_suspicious_patterns(self, user, resource_type, resource_id):
        """Check for suspicious access patterns"""
        # Check for excessive access
        recent_access = self.env['guard.audit.trail'].search([
            ('user_id', '=', user.id),
            ('resource_type', '=', resource_type),
            ('timestamp', '>=', fields.Datetime.now() - timedelta(hours=1))
        ])
        
        if len(recent_access) > 100:  # Threshold for suspicious activity
            self._alert_suspicious_activity(user, 'excessive_access', {
                'resource_type': resource_type,
                'access_count': len(recent_access)
            })
    
    def _check_sensitive_data_changes(self, old_values, new_values):
        """Check for sensitive data changes"""
        sensitive_fields = ['email', 'phone', 'ssn', 'password']
        
        for field in sensitive_fields:
            if field in old_values and field in new_values:
                if old_values[field] != new_values[field]:
                    self._alert_sensitive_data_change(field, old_values[field], new_values[field])
    
    def _alert_suspicious_activity(self, user, activity_type, details):
        """Alert on suspicious activity"""
        self.env['guard.security.alert'].create({
            'user_id': user.id,
            'alert_type': 'suspicious_activity',
            'activity_type': activity_type,
            'details': details,
            'severity': 'high',
            'status': 'open',
            'timestamp': fields.Datetime.now()
        })
    
    def _alert_sensitive_data_change(self, field, old_value, new_value):
        """Alert on sensitive data change"""
        self.env['guard.security.alert'].create({
            'alert_type': 'sensitive_data_change',
            'field': field,
            'old_value': old_value,
            'new_value': new_value,
            'severity': 'medium',
            'status': 'open',
            'timestamp': fields.Datetime.now()
        })
```

## API Security

### API Access Control

```python
# API Access Control
class GuardProAPISecurity:
    def __init__(self, env):
        self.env = env
    
    def validate_api_request(self, request):
        """Validate API request"""
        # Check authentication
        if not self._authenticate_api_request(request):
            raise AccessDenied(_("API authentication required"))
        
        # Check authorization
        if not self._authorize_api_request(request):
            raise AccessDenied(_("API access denied"))
        
        # Check rate limiting
        if not self._check_rate_limit(request):
            raise AccessDenied(_("Rate limit exceeded"))
        
        # Log API access
        self._log_api_access(request)
        
        return True
    
    def _authenticate_api_request(self, request):
        """Authenticate API request"""
        # Check for API key or token
        api_key = request.headers.get('X-API-Key')
        auth_token = request.headers.get('Authorization')
        
        if api_key:
            return self._validate_api_key(api_key)
        elif auth_token:
            return self._validate_auth_token(auth_token)
        
        return False
    
    def _validate_api_key(self, api_key):
        """Validate API key"""
        api_key_record = self.env['guard.api.key'].search([
            ('key', '=', api_key),
            ('active', '=', True),
            ('expires_at', '>', fields.Datetime.now())
        ])
        
        return bool(api_key_record)
    
    def _validate_auth_token(self, auth_token):
        """Validate authentication token"""
        # Remove 'Bearer ' prefix if present
        if auth_token.startswith('Bearer '):
            auth_token = auth_token[7:]
        
        # Validate token
        session = self.env['guard.user.session'].search([
            ('token', '=', auth_token),
            ('status', '=', 'active'),
            ('expires_at', '>', fields.Datetime.now())
        ])
        
        return bool(session)
    
    def _authorize_api_request(self, request):
        """Authorize API request"""
        # Check if user has permission for the requested resource and action
        user_id = self._get_user_from_request(request)
        resource = request.path_info.split('/')[-1]
        action = request.method.lower()
        
        return self.env['guardpro.rbac'].check_permission(user_id, resource, action)
    
    def _check_rate_limit(self, request):
        """Check API rate limit"""
        user_id = self._get_user_from_request(request)
        ip_address = self._get_client_ip(request)
        
        # Check rate limit for user
        if not self._check_user_rate_limit(user_id):
            return False
        
        # Check rate limit for IP
        if not self._check_ip_rate_limit(ip_address):
            return False
        
        return True
    
    def _check_user_rate_limit(self, user_id):
        """Check user rate limit"""
        # Get user rate limit configuration
        user = self.env['res.users'].browse(user_id)
        rate_limit = user.api_rate_limit or 1000  # requests per hour
        
        # Count requests in last hour
        one_hour_ago = fields.Datetime.now() - timedelta(hours=1)
        request_count = self.env['guard.api.request'].search_count([
            ('user_id', '=', user_id),
            ('timestamp', '>=', one_hour_ago)
        ])
        
        return request_count < rate_limit
    
    def _check_ip_rate_limit(self, ip_address):
        """Check IP rate limit"""
        # Get IP rate limit configuration
        ip_rate_limit = self.env['ir.config_parameter'].sudo().get_param('guardpro.ip_rate_limit', '5000')
        ip_rate_limit = int(ip_rate_limit)
        
        # Count requests from IP in last hour
        one_hour_ago = fields.Datetime.now() - timedelta(hours=1)
        request_count = self.env['guard.api.request'].search_count([
            ('ip_address', '=', ip_address),
            ('timestamp', '>=', one_hour_ago)
        ])
        
        return request_count < ip_rate_limit
    
    def _log_api_access(self, request):
        """Log API access"""
        self.env['guard.api.request'].create({
            'user_id': self._get_user_from_request(request),
            'endpoint': request.path_info,
            'method': request.method,
            'ip_address': self._get_client_ip(request),
            'user_agent': request.headers.get('User-Agent'),
            'timestamp': fields.Datetime.now()
        })
```

## Best Practices

### Security Best Practices

1. **Authentication & Authorization**
   - Implement strong password policies
   - Use multi-factor authentication
   - Implement proper session management
   - Use role-based access control

2. **Data Protection**
   - Encrypt sensitive data at rest and in transit
   - Implement data masking for sensitive fields
   - Use secure backup procedures
   - Implement data retention policies

3. **Audit & Compliance**
   - Maintain comprehensive audit trails
   - Monitor for suspicious activity
   - Implement compliance reporting
   - Regular security assessments

4. **Network Security**
   - Use HTTPS for all communications
   - Implement proper firewall rules
   - Use VPN for remote access
   - Monitor network traffic

### Implementation Guidelines

1. **Security Configuration**
   - Configure security parameters properly
   - Use secure default settings
   - Regular security updates
   - Monitor security logs

2. **User Management**
   - Implement proper user provisioning
   - Regular access reviews
   - Immediate deactivation of inactive users
   - Strong password policies

3. **Data Security**
   - Classify data by sensitivity
   - Implement appropriate protection measures
   - Regular data backups
   - Secure data disposal

4. **Incident Response**
   - Develop incident response procedures
   - Regular security training
   - Test incident response plans
   - Maintain security documentation

---

*GuardPro Security: Comprehensive Protection for Sensitive Security Data*