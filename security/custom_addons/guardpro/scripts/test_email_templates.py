#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GuardPro Email Template Testing Script
Run this script to test all email templates without UI
"""

import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{text.center(80)}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*80}{Colors.END}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def test_template(env, template, test_record=None):
    """Test a single email template"""
    results = {
        'success': True,
        'errors': [],
        'warnings': []
    }
    
    try:
        # Get test record if not provided
        if not test_record and template.model:
            model = env[template.model]
            test_record = model.search([], limit=1)
            if not test_record:
                results['warnings'].append(f"No test records available for model {template.model}")
                test_record = model  # Empty recordset
        
        # Test subject
        try:
            subject = template._render_field('subject', test_record.ids if test_record else [0])
            print_success(f"Subject: OK")
        except Exception as e:
            results['errors'].append(f"Subject: {str(e)}")
            results['success'] = False
        
        # Test email_from
        try:
            email_from = template._render_field('email_from', test_record.ids if test_record else [0])
            print_success(f"From Email: OK")
        except Exception as e:
            results['errors'].append(f"From Email: {str(e)}")
            results['success'] = False
        
        # Test email_to
        try:
            email_to = template._render_field('email_to', test_record.ids if test_record else [0])
            print_success(f"To Email: OK")
        except Exception as e:
            results['errors'].append(f"To Email: {str(e)}")
            results['success'] = False
        
        # Test body_html
        try:
            body_html = template._render_field('body_html', test_record.ids if test_record else [0])
            char_count = len(str(body_html))
            print_success(f"Body HTML: OK ({char_count} characters)")
        except Exception as e:
            results['errors'].append(f"Body HTML: {str(e)}")
            results['success'] = False
        
    except Exception as e:
        results['errors'].append(f"Critical error: {str(e)}")
        results['success'] = False
        logger.exception(f"Critical error testing template {template.name}")
    
    return results

def main():
    """Main testing function"""
    print_header("GuardPro Email Template Tester")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # Check if running in Odoo context
        try:
            import odoo
            from odoo.api import Environment
            import odoo.tools.config as config
        except ImportError:
            print_error("This script must be run in Odoo environment")
            print("Use: odoo shell -c /etc/odoo/odoo.conf -d your_database < test_email_templates.py")
            sys.exit(1)
        
        # Get environment
        try:
            env = Environment(odoo.api.Environment.cr, odoo.SUPERUSER_ID, {})
        except:
            print_error("Could not get Odoo environment")
            print("Make sure you run this in Odoo shell context")
            sys.exit(1)
        
        # Search for GuardPro templates
        print("Searching for GuardPro email templates...")
        templates = env['mail.template'].search([
            '|', '|', '|',
            ('model', 'ilike', 'guard'),
            ('model', 'ilike', 'incident'),
            ('model', 'ilike', 'shift'),
            ('model', 'ilike', 'visitor'),
        ])
        
        if not templates:
            print_warning("No templates found. Searching all mail templates...")
            templates = env['mail.template'].search([])
        
        templates = templates.sorted(key=lambda t: t.name)
        
        print(f"Found {len(templates)} email templates to test\n")
        
        # Test statistics
        success_count = 0
        error_count = 0
        warning_count = 0
        
        # Test each template
        for idx, template in enumerate(templates, 1):
            print(f"\n{Colors.BOLD}{idx}. {template.name}{Colors.END}")
            print(f"   Model: {template.model} | ID: {template.id}")
            
            results = test_template(env, template)
            
            if results['errors']:
                error_count += 1
                for error in results['errors']:
                    print_error(f"   {error}")
            elif results['warnings']:
                warning_count += 1
                for warning in results['warnings']:
                    print_warning(f"   {warning}")
            else:
                success_count += 1
            
            print("-" * 80)
        
        # Print summary
        print_header("Test Summary")
        print(f"Total Templates:  {len(templates)}")
        print_success(f"Success:          {success_count}")
        if warning_count > 0:
            print_warning(f"Warnings:         {warning_count}")
        if error_count > 0:
            print_error(f"Errors:           {error_count}")
        
        print(f"\n{Colors.BOLD}Test completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}\n")
        
        # Exit with appropriate code
        sys.exit(0 if error_count == 0 else 1)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print_error(f"Fatal error: {str(e)}")
        logger.exception("Fatal error during testing")
        sys.exit(1)

if __name__ == '__main__':
    # Check if running in interactive mode (Odoo shell)
    try:
        # This will only work if we're in Odoo shell context
        import __main__
        if hasattr(__main__, 'env'):
            env = __main__.env
            print_header("GuardPro Email Template Tester (Interactive Mode)")
            
            templates = env['mail.template'].search([
                '|', '|', '|',
                ('model', 'ilike', 'guard'),
                ('model', 'ilike', 'incident'),
                ('model', 'ilike', 'shift'),
                ('model', 'ilike', 'visitor'),
            ])
            
            print(f"Found {len(templates)} templates")
            print("\nTo test all templates, run:")
            print(">>> for template in templates: test_template(env, template)")
        else:
            main()
    except:
        main()










