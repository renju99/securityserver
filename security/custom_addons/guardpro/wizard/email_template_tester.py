# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class EmailTemplateTester(models.TransientModel):
    """Email Template Testing Wizard for GuardLink Module"""
    _name = 'email.template.tester'
    _description = 'Email Template Tester'

    template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        required=True,
        help='Select email template to test'
    )
    test_record_id = fields.Integer(
        string='Test Record ID',
        help='ID of the record to use for testing (optional)'
    )
    test_email = fields.Char(
        string='Test Email Address',
        required=True,
        default=lambda self: self.env.user.email,
        help='Email address to send the test email to'
    )
    result_html = fields.Html(
        string='Test Results',
        readonly=True
    )
    test_mode = fields.Selection([
        ('render', 'Render Only (Check Syntax)'),
        ('send', 'Render and Send Email'),
    ], string='Test Mode', default='render', required=True)

    def action_test_template(self):
        """Test a single email template"""
        self.ensure_one()
        
        result_lines = []
        result_lines.append("<h3>Testing Email Template: %s</h3>" % self.template_id.name)
        result_lines.append("<strong>Model:</strong> %s<br/>" % self.template_id.model)
        
        try:
            # Get a test record
            model = self.env[self.template_id.model]
            
            if self.test_record_id:
                test_record = model.browse(self.test_record_id)
                if not test_record.exists():
                    raise UserError(_('Test record with ID %s does not exist') % self.test_record_id)
            else:
                # Find or create a test record
                test_record = model.search([], limit=1)
                if not test_record:
                    result_lines.append("<p style='color:orange;'><strong>Warning:</strong> No existing records found. Some templates may not render correctly without data.</p>")
                    test_record = model
            
            result_lines.append("<strong>Test Record:</strong> %s (ID: %s)<br/><br/>" % (
                test_record.display_name if test_record else 'N/A',
                test_record.id if test_record else 'N/A'
            ))
            
            # Test subject rendering
            result_lines.append("<h4>1. Testing Subject Line</h4>")
            try:
                subject = self.template_id._render_field('subject', test_record.ids)[test_record.id if test_record else 0]
                result_lines.append("<div style='background:#e8f5e9;padding:10px;margin:5px 0;'><strong>✓ Subject:</strong> %s</div>" % subject)
            except Exception as e:
                result_lines.append("<div style='background:#ffebee;padding:10px;margin:5px 0;'><strong>✗ Subject Error:</strong> %s</div>" % str(e))
                _logger.error("Subject rendering error for template %s: %s", self.template_id.name, str(e))
            
            # Test email_from rendering
            result_lines.append("<h4>2. Testing From Email</h4>")
            try:
                email_from = self.template_id._render_field('email_from', test_record.ids)[test_record.id if test_record else 0]
                result_lines.append("<div style='background:#e8f5e9;padding:10px;margin:5px 0;'><strong>✓ From:</strong> %s</div>" % email_from)
            except Exception as e:
                result_lines.append("<div style='background:#ffebee;padding:10px;margin:5px 0;'><strong>✗ From Email Error:</strong> %s</div>" % str(e))
                _logger.error("From email rendering error for template %s: %s", self.template_id.name, str(e))
            
            # Test email_to rendering
            result_lines.append("<h4>3. Testing To Email</h4>")
            try:
                email_to = self.template_id._render_field('email_to', test_record.ids)[test_record.id if test_record else 0]
                result_lines.append("<div style='background:#e8f5e9;padding:10px;margin:5px 0;'><strong>✓ To:</strong> %s</div>" % (email_to or 'Not specified (uses partner_to)'))
            except Exception as e:
                result_lines.append("<div style='background:#ffebee;padding:10px;margin:5px 0;'><strong>✗ To Email Error:</strong> %s</div>" % str(e))
                _logger.error("To email rendering error for template %s: %s", self.template_id.name, str(e))
            
            # Test body_html rendering
            result_lines.append("<h4>4. Testing Email Body</h4>")
            try:
                body_html = self.template_id._render_field('body_html', test_record.ids)[test_record.id if test_record else 0]
                result_lines.append("<div style='background:#e8f5e9;padding:10px;margin:5px 0;'><strong>✓ Body HTML rendered successfully</strong> (%s characters)</div>" % len(body_html))
                
                # Show preview
                result_lines.append("<h4>5. Email Body Preview:</h4>")
                result_lines.append("<div style='border:2px solid #ddd;padding:15px;margin:10px 0;max-height:400px;overflow:auto;'>%s</div>" % body_html)
            except Exception as e:
                result_lines.append("<div style='background:#ffebee;padding:10px;margin:5px 0;'><strong>✗ Body HTML Error:</strong> %s</div>" % str(e))
                _logger.error("Body HTML rendering error for template %s: %s", self.template_id.name, str(e))
            
            # Actually send email if requested
            if self.test_mode == 'send' and test_record:
                result_lines.append("<h4>6. Sending Test Email</h4>")
                try:
                    # Generate and send email
                    mail_values = self.template_id.generate_email(test_record.id)
                    mail_values['email_to'] = self.test_email
                    
                    mail = self.env['mail.mail'].create(mail_values)
                    mail.send()
                    
                    result_lines.append("<div style='background:#e8f5e9;padding:10px;margin:5px 0;'><strong>✓ Test email sent successfully to:</strong> %s</div>" % self.test_email)
                except Exception as e:
                    result_lines.append("<div style='background:#ffebee;padding:10px;margin:5px 0;'><strong>✗ Email Send Error:</strong> %s</div>" % str(e))
                    _logger.error("Email send error for template %s: %s", self.template_id.name, str(e))
            
            result_lines.append("<div style='background:#4caf50;color:white;padding:15px;margin:20px 0;text-align:center;font-size:18px;'><strong>✓ TEST COMPLETED</strong></div>")
            
        except Exception as e:
            result_lines.append("<div style='background:#f44336;color:white;padding:15px;margin:10px 0;'><strong>CRITICAL ERROR:</strong> %s</div>" % str(e))
            _logger.error("Critical error testing template %s: %s", self.template_id.name, str(e), exc_info=True)
        
        self.result_html = '<br/>'.join(result_lines)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'email.template.tester',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_test_all_templates(self):
        """Test all email templates in the system"""
        templates = self.env['mail.template'].search([
            ('model', 'like', 'guardpro'),
        ]) | self.env['mail.template'].search([
            ('name', 'ilike', 'guard'),
        ]) | self.env['mail.template'].search([
            ('name', 'ilike', 'incident'),
        ]) | self.env['mail.template'].search([
            ('name', 'ilike', 'shift'),
        ])
        
        # Remove duplicates
        templates = templates.sorted(key=lambda t: t.name)
        
        result_lines = []
        result_lines.append("<h2>GuardLink Email Template Test Report</h2>")
        result_lines.append("<p><strong>Total Templates Found:</strong> %s</p>" % len(templates))
        result_lines.append("<p><strong>Test Date:</strong> %s</p><hr/>" % fields.Datetime.now())
        
        success_count = 0
        error_count = 0
        warning_count = 0
        
        for idx, template in enumerate(templates, 1):
            result_lines.append("<h3>%s. %s</h3>" % (idx, template.name))
            result_lines.append("<strong>Model:</strong> %s | <strong>ID:</strong> %s<br/>" % (template.model, template.id))
            
            template_errors = []
            template_warnings = []
            
            try:
                # Get a test record
                if template.model:
                    model = self.env[template.model]
                    test_record = model.search([], limit=1)
                    
                    if not test_record:
                        template_warnings.append("No test records available for model %s" % template.model)
                        test_record = model  # Empty recordset
                    
                    # Test subject
                    try:
                        subject = template._render_field('subject', test_record.ids if test_record else [0])
                        result_lines.append("<small style='color:green;'>✓ Subject renders OK</small><br/>")
                    except Exception as e:
                        template_errors.append("Subject: %s" % str(e))
                    
                    # Test email_from
                    try:
                        email_from = template._render_field('email_from', test_record.ids if test_record else [0])
                        result_lines.append("<small style='color:green;'>✓ From email renders OK</small><br/>")
                    except Exception as e:
                        template_errors.append("From email: %s" % str(e))
                    
                    # Test email_to
                    try:
                        email_to = template._render_field('email_to', test_record.ids if test_record else [0])
                        result_lines.append("<small style='color:green;'>✓ To email renders OK</small><br/>")
                    except Exception as e:
                        template_errors.append("To email: %s" % str(e))
                    
                    # Test body_html
                    try:
                        body_html = template._render_field('body_html', test_record.ids if test_record else [0])
                        result_lines.append("<small style='color:green;'>✓ Body HTML renders OK (%s chars)</small><br/>" % len(str(body_html)))
                    except Exception as e:
                        template_errors.append("Body HTML: %s" % str(e))
                else:
                    template_errors.append("No model specified for template")
                
            except Exception as e:
                template_errors.append("Critical error: %s" % str(e))
                _logger.error("Error testing template %s: %s", template.name, str(e), exc_info=True)
            
            # Summary for this template
            if template_errors:
                error_count += 1
                result_lines.append("<div style='background:#ffebee;padding:10px;margin:10px 0;border-left:4px solid #f44336;'>")
                result_lines.append("<strong style='color:#d32f2f;'>✗ ERRORS FOUND:</strong><br/>")
                for error in template_errors:
                    result_lines.append("• %s<br/>" % error)
                result_lines.append("</div>")
            elif template_warnings:
                warning_count += 1
                result_lines.append("<div style='background:#fff3e0;padding:10px;margin:10px 0;border-left:4px solid #ff9800;'>")
                result_lines.append("<strong style='color:#f57c00;'>⚠ WARNINGS:</strong><br/>")
                for warning in template_warnings:
                    result_lines.append("• %s<br/>" % warning)
                result_lines.append("</div>")
            else:
                success_count += 1
                result_lines.append("<div style='background:#e8f5e9;padding:10px;margin:10px 0;border-left:4px solid #4caf50;'>")
                result_lines.append("<strong style='color:#2e7d32;'>✓ ALL TESTS PASSED</strong>")
                result_lines.append("</div>")
            
            result_lines.append("<hr/>")
        
        # Final summary
        result_lines.append("<div style='background:#2196f3;color:white;padding:20px;margin:20px 0;'>")
        result_lines.append("<h2>TEST SUMMARY</h2>")
        result_lines.append("<p><strong>Total Templates:</strong> %s</p>" % len(templates))
        result_lines.append("<p><strong style='color:#4caf50;'>✓ Success:</strong> %s</p>" % success_count)
        result_lines.append("<p><strong style='color:#ff9800;'>⚠ Warnings:</strong> %s</p>" % warning_count)
        result_lines.append("<p><strong style='color:#f44336;'>✗ Errors:</strong> %s</p>" % error_count)
        result_lines.append("</div>")
        
        self.result_html = ''.join(result_lines)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'email.template.tester',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }










