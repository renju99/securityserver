#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GuardLink Email Template - Send Test Emails
This script sends test emails for all templates to verify they work correctly.

Usage in Odoo shell:
    cd /home/ranjith/odoo/custom_addons/guardpro
    # Then run in Python console with odoo context
"""

import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

# Test email address (CHANGE THIS TO YOUR EMAIL)
TEST_EMAIL = "your.email@example.com"  # <<< CHANGE THIS

def create_or_get_test_data(env):
    """Create or get test data for email testing"""
    test_data = {}
    
    # 1. Get or create test client
    client = env['res.partner'].search([('is_company', '=', True)], limit=1)
    if not client:
        client = env['res.partner'].create({
            'name': 'Test Security Client',
            'is_company': True,
            'email': TEST_EMAIL,
            'phone': '+1234567890',
        })
    test_data['client'] = client
    
    # 2. Get or create test site
    site = env['client.site'].search([], limit=1)
    if not site:
        site = env['client.site'].create({
            'name': 'Test Security Site',
            'client_id': client.id,
            'site_email': TEST_EMAIL,
            'site_phone': '+1234567890',
            'street': '123 Test Street',
            'city': 'Test City',
            'zip': '12345',
        })
    test_data['site'] = site
    
    # 3. Get or create test guard
    guard = env['guard.profile'].search([], limit=1)
    if not guard:
        # Create user first
        user = env['res.users'].create({
            'name': 'Test Guard',
            'login': 'test.guard@test.com',
            'email': TEST_EMAIL,
        })
        guard = env['guard.profile'].create({
            'name': 'Test Guard',
            'employee_id': 'TG001',
            'user_id': user.id,
            'email': TEST_EMAIL,
            'phone': '+1234567890',
        })
    test_data['guard'] = guard
    
    # 4. Get or create test shift
    shift = env['guard.shift'].search([], limit=1)
    if not shift:
        shift = env['guard.shift'].create({
            'guard_id': guard.id,
            'site_id': site.id,
            'start_datetime': datetime.now() + timedelta(days=1),
            'end_datetime': datetime.now() + timedelta(days=1, hours=8),
            'status': 'scheduled',
        })
    test_data['shift'] = shift
    
    # 5. Get or create test incident
    incident = env['incident.report'].search([], limit=1)
    if not incident:
        category = env['incident.category'].search([], limit=1)
        if not category:
            category = env['incident.category'].create({
                'name': 'Test Category',
                'severity': 'medium',
            })
        incident = env['incident.report'].create({
            'title': 'Test Incident Report',
            'description': 'This is a test incident for email template testing.',
            'severity': 'medium',
            'category_id': category.id,
            'site_id': site.id,
            'guard_id': guard.id,
            'incident_datetime': datetime.now(),
            'location': 'Main Entrance',
        })
    test_data['incident'] = incident
    
    # 6. Get or create test task
    task = env['guard.task'].search([], limit=1)
    if not task:
        task = env['guard.task'].create({
            'name': 'Test Security Task',
            'description': 'Test task description',
            'task_type': 'patrol',
            'priority': '1',
            'assigned_to': guard.id,
            'site_id': site.id,
            'due_date': datetime.now() + timedelta(days=2),
        })
    test_data['task'] = task
    
    # 7. Get or create test package
    package = env['package.management'].search([], limit=1)
    if not package:
        package = env['package.management'].create({
            'recipient_name': 'Test Recipient',
            'recipient_email': TEST_EMAIL,
            'package_type': 'parcel',
            'site_id': site.id,
            'received_by': guard.id,
            'received_date': datetime.now(),
            'tracking_number': 'TEST123456',
            'description': 'Test package',
        })
    test_data['package'] = package
    
    # 8. Get or create test visitor
    visitor = env['visitor.management'].search([], limit=1)
    if not visitor:
        visitor = env['visitor.management'].create({
            'visitor_name': 'Test Visitor',
            'email': TEST_EMAIL,
            'phone': '+1234567890',
            'host_name': 'Test Host',
            'host_email': TEST_EMAIL,
            'site_id': site.id,
            'purpose': 'Testing email templates',
            'expected_arrival': datetime.now() + timedelta(hours=2),
        })
    test_data['visitor'] = visitor
    
    # 9. Get or create test credential
    credential = env['guard.credential'].search([], limit=1)
    if not credential:
        cred_type = env['guard.credential.type'].search([], limit=1)
        if not cred_type:
            cred_type = env['guard.credential.type'].create({
                'name': 'Test License',
                'renewal_period': 365,
            })
        credential = env['guard.credential'].create({
            'guard_id': guard.id,
            'credential_type_id': cred_type.id,
            'credential_number': 'TEST-CRED-001',
            'issue_date': datetime.now().date() - timedelta(days=300),
            'expiry_date': datetime.now().date() + timedelta(days=65),
            'issuing_authority': 'Test Authority',
        })
    test_data['credential'] = credential
    
    return test_data

def send_test_emails(env, test_email=TEST_EMAIL):
    """Send test emails for all templates"""
    print("\n" + "="*80)
    print("GuardLink Email Template - Test Email Sender".center(80))
    print("="*80 + "\n")
    print(f"Test Email Address: {test_email}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Create/get test data
    print("Creating test data...")
    test_data = create_or_get_test_data(env)
    print(f"✓ Test data created successfully\n")
    
    # Define template-to-model mapping
    template_mapping = {
        'Incident Report Notification': ('incident.report', test_data.get('incident')),
        'Shift Reminder': ('guard.shift', test_data.get('shift')),
        'Daily Activity Report to Client': ('daily.activity.report', None),  # Skip if no DAR
        'Resident Portal Access Invitation': ('tenant.resident', None),  # Skip if no resident
        'Incident Status Update Notification': ('incident.status.update', None),  # Skip
        'Task Assignment Notification': ('guard.task', test_data.get('task')),
        'Shift Change Notification': ('guard.shift', test_data.get('shift')),
        'Emergency Broadcast Alert': ('emergency.broadcast', None),  # Skip
        'Package Arrival Notification': ('package.management', test_data.get('package')),
        'Package Collection Confirmation': ('package.management', test_data.get('package')),
        'Audit Finding Notification': ('compliance.audit', None),  # Skip
        'Compliance Violation Alert': ('guard.profile', test_data.get('guard')),
        'Performance Review Notification': ('guard.performance.review', None),  # Skip
        'Credential Expiry Warning': ('guard.credential', test_data.get('credential')),
        'Visitor Arrival Notification': ('visitor.management', test_data.get('visitor')),
        'SLA Performance Breach Alert': ('sla.definition', None),  # Skip
        'Overdue Key Return Notification': ('key.register', None),  # Skip
    }
    
    # Search for all GuardLink templates
    templates = env['mail.template'].search([
        '|', '|', '|', '|',
        ('model', 'ilike', 'guard'),
        ('model', 'ilike', 'incident'),
        ('model', 'ilike', 'shift'),
        ('model', 'ilike', 'visitor'),
        ('model', 'ilike', 'package'),
    ])
    
    print(f"Found {len(templates)} email templates to test\n")
    print("-"*80)
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for idx, template in enumerate(templates, 1):
        print(f"\n{idx}. {template.name}")
        print(f"   Model: {template.model}")
        
        try:
            # Get test record
            model_obj = env[template.model]
            test_record = model_obj.search([], limit=1)
            
            if not test_record:
                print(f"   ⚠ SKIPPED - No test data available")
                skip_count += 1
                continue
            
            # Generate email
            mail_values = template.generate_email(test_record.id)
            
            # Override recipient
            mail_values['email_to'] = test_email
            
            # Create and send
            mail = env['mail.mail'].sudo().create(mail_values)
            mail.send()
            
            print(f"   ✓ SUCCESS - Test email sent to {test_email}")
            success_count += 1
            
        except Exception as e:
            print(f"   ✗ ERROR - {str(e)}")
            error_count += 1
            _logger.exception(f"Error sending test email for template {template.name}")
    
    # Summary
    print("\n" + "="*80)
    print("Test Summary".center(80))
    print("="*80)
    print(f"Total Templates:  {len(templates)}")
    print(f"✓ Success:        {success_count}")
    print(f"⚠ Skipped:        {skip_count}")
    print(f"✗ Errors:         {error_count}")
    print("="*80 + "\n")
    
    if error_count == 0:
        print("🎉 All available templates tested successfully!")
        print(f"📧 Check your inbox at: {test_email}\n")
    else:
        print(f"⚠ {error_count} template(s) had errors. Check logs for details.\n")
    
    return {
        'success': success_count,
        'skip': skip_count,
        'error': error_count,
        'total': len(templates)
    }

# Example usage in Odoo shell:
"""
# 1. Open Odoo shell
sudo -u odoo /usr/bin/odoo shell -c /etc/odoo/odoo.conf -d your_database_name

# 2. Set your test email
TEST_EMAIL = "your.email@example.com"

# 3. Run the function
exec(open('/home/ranjith/odoo/custom_addons/guardpro/scripts/send_test_emails.py').read())
results = send_test_emails(env, TEST_EMAIL)

# 4. Check results
print(results)
"""

if __name__ == '__main__':
    print("This script must be run in Odoo shell context")
    print("\nUsage:")
    print("sudo -u odoo /usr/bin/odoo shell -c /etc/odoo/odoo.conf -d your_database")
    print(">>> TEST_EMAIL = 'your@email.com'")
    print(">>> exec(open('/home/ranjith/odoo/custom_addons/guardpro/scripts/send_test_emails.py').read())")
    print(">>> results = send_test_emails(env, TEST_EMAIL)")










