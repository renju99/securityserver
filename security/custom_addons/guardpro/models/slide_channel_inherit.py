import logging
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SlideChannel(models.Model):
    """Extend eLearning Courses with Guard-specific features."""
    
    _inherit = 'slide.channel'
    
    # Override field security to allow guardpro groups access
    channel_partner_ids = fields.One2many(
        'slide.channel.partner',
        'channel_id',
        string='Members',
        groups='base.group_user,guardpro.group_guardpro_guard_portal,'
               'guardpro.group_guardpro_supervisor,guardpro.group_guardpro_manager,'
               'guardpro.group_guardpro_admin'
    )
    
    # Guard Training Specific Fields
    is_guard_training = fields.Boolean(
        string='Guard Training Course',
        default=False,
        help='Mark this course as a security guard training program'
    )
    
    training_category = fields.Selection([
        ('basic', 'Basic Security Training'),
        ('advanced', 'Advanced Security'),
        ('emergency', 'Emergency Response'),
        ('technical', 'Technical Skills'),
        ('safety', 'Health & Safety'),
        ('customer_service', 'Customer Service'),
        ('legal', 'Legal & Compliance'),
        ('specialized', 'Specialized Training')
    ], string='Training Category', help='Category of guard training')
    
    is_mandatory_for_guards = fields.Boolean(
        string='Mandatory for All Guards',
        default=False,
        help='All guards must complete this course'
    )
    
    certification_validity_months = fields.Integer(
        string='Certificate Validity (months)',
        default=12,
        help='Number of months the certificate remains valid. 0 = lifetime'
    )
    
    required_for_sites = fields.Many2many(
        'client.site',
        'course_site_rel',
        'course_id',
        'site_id',
        string='Required for Sites',
        help='Sites that require this training'
    )
    
    minimum_passing_score = fields.Integer(
        string='Minimum Passing Score (%)',
        default=80,
        help='Minimum score required to pass and receive certification'
    )
    
    # Statistics
    enrolled_guards_count = fields.Integer(
        string='Enrolled Guards',
        compute='_compute_guard_statistics'
    )
    
    completed_guards_count = fields.Integer(
        string='Completed by Guards',
        compute='_compute_guard_statistics'
    )
    
    certification_expiring_count = fields.Integer(
        string='Certifications Expiring Soon',
        compute='_compute_expiring_certifications',
        help='Number of certifications expiring within 30 days'
    )
    
    @api.depends('channel_partner_ids.partner_id')
    def _compute_guard_statistics(self):
        """Compute guard-specific enrollment statistics."""
        for record in self:
            if record.is_guard_training:
                # Get guard partners
                guard_partners = self.env['guard.profile'].search([]).mapped('user_id.partner_id')
                
                # Filter enrollments to only guards
                guard_enrollments = record.channel_partner_ids.filtered(
                    lambda cp: cp.partner_id in guard_partners
                )
                
                record.enrolled_guards_count = len(guard_enrollments)
                record.completed_guards_count = len(
                    guard_enrollments.filtered(lambda e: e.member_status == 'completed')
                )
            else:
                record.enrolled_guards_count = 0
                record.completed_guards_count = 0
    
    def _compute_expiring_certifications(self):
        """Compute certifications expiring within 30 days."""
        for record in self:
            if record.is_guard_training and record.certification_validity_months > 0:
                # Find completed enrollments
                expiring_count = 0
                completed_enrollments = record.channel_partner_ids.filtered(
                    lambda cp: cp.member_status == 'completed'
                )
                
                # Check expiration dates
                warning_date = fields.Datetime.now() + timedelta(days=30)
                
                for enrollment in completed_enrollments:
                    completion_slide = enrollment.partner_id.slide_partner_ids.filtered(
                        lambda sp: sp.channel_id == record and sp.completed
                    ).sorted('write_date', reverse=True)
                    
                    if completion_slide:
                        completion_date = completion_slide[0].write_date
                        expiry_date = completion_date + relativedelta(
                            months=record.certification_validity_months
                        )
                        
                        if expiry_date.replace(tzinfo=None) <= warning_date:
                            expiring_count += 1
                
                record.certification_expiring_count = expiring_count
            else:
                record.certification_expiring_count = 0
    
    def action_view_enrolled_guards(self):
        """View guards enrolled in this course."""
        self.ensure_one()
        guard_partners = self.env['guard.profile'].search([]).mapped('user_id.partner_id')
        
        return {
            'name': _('Enrolled Guards: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'slide.channel.partner',
            'view_mode': 'list,form',
            'domain': [
                ('channel_id', '=', self.id),
                ('partner_id', 'in', guard_partners.ids)
            ],
            'context': {
                'default_channel_id': self.id,
            }
        }
    
    def action_enroll_all_guards(self):
        """Enroll all active guards in this course."""
        self.ensure_one()
        if not self.is_guard_training:
            raise ValidationError(_('This is not a guard training course.'))
        
        guards = self.env['guard.profile'].search([('status', '=', 'active')])
        enrolled_count = 0
        
        for guard in guards:
            # Skip guards without user accounts
            if not guard.user_id or not guard.user_id.partner_id:
                continue
            
            # Check if already enrolled
            existing = self.channel_partner_ids.filtered(
                lambda cp: cp.partner_id == guard.user_id.partner_id
            )
            
            if not existing:
                self.env['slide.channel.partner'].create({
                    'channel_id': self.id,
                    'partner_id': guard.user_id.partner_id.id,
                })
                enrolled_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%s guards enrolled successfully.') % enrolled_count,
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.constrains('minimum_passing_score')
    def _check_passing_score(self):
        """Validate passing score is between 0 and 100."""
        for record in self:
            if record.minimum_passing_score < 0 or record.minimum_passing_score > 100:
                raise ValidationError(
                    _('Minimum passing score must be between 0 and 100.')
                )


class SlideChannelPartner(models.Model):
    """Extend eLearning Enrollments with Guard Training tracking."""
    
    _inherit = 'slide.channel.partner'
    
    # Guard-specific fields
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        compute='_compute_guard_id',
        store=True,
        index=True
    )
    
    certification_issued_date = fields.Date(
        string='Certification Date',
        compute='_compute_certification_date',
        store=True
    )
    
    certification_expiry_date = fields.Date(
        string='Certification Expiry',
        compute='_compute_certification_expiry',
        store=True
    )
    
    certification_status = fields.Selection([
        ('none', 'Not Certified'),
        ('valid', 'Valid'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired')
    ], string='Certification Status', compute='_compute_certification_status')
    
    final_score = fields.Float(
        string='Final Score (%)',
        compute='_compute_final_score',
        help='Average score across all quizzes'
    )
    
    passed_course = fields.Boolean(
        string='Passed',
        compute='_compute_passed_course',
        store=True
    )
    
    pass_status_text = fields.Char(
        string='Status',
        compute='_compute_pass_status_text',
        help='Shows Correct or Not Correct based on pass status'
    )
    
    quiz_response_ids = fields.Many2many(
        'slide.slide.partner',
        compute='_compute_quiz_responses',
        string='Detailed Quiz Responses'
    )
    
    quiz_response_count = fields.Integer(
        string='Quiz Attempts',
        compute='_compute_quiz_responses'
    )
    
    @api.depends('channel_id', 'partner_id')
    def _compute_quiz_responses(self):
        """Find all quiz completion records for this enrollment."""
        for record in self:
            quiz_responses = self.env['slide.slide.partner'].search([
                ('channel_id', '=', record.channel_id.id),
                ('partner_id', '=', record.partner_id.id),
                ('slide_id.slide_category', '=', 'quiz')
            ])
            record.quiz_response_ids = quiz_responses
            record.quiz_response_count = len(quiz_responses)
    
    @api.depends('partner_id')
    def _compute_guard_id(self):
        """Link to guard profile if partner is a guard."""
        for record in self:
            guard = self.env['guard.profile'].search([
                ('user_id.partner_id', '=', record.partner_id.id)
            ], limit=1)
            record.guard_id = guard.id if guard else False
    
    @api.depends('member_status', 'write_date')
    def _compute_certification_date(self):
        """Set certification date when course is completed."""
        for record in self:
            if record.member_status == 'completed':
                record.certification_issued_date = record.write_date.date()
            else:
                record.certification_issued_date = False
    
    @api.depends('certification_issued_date', 'channel_id.certification_validity_months')
    def _compute_certification_expiry(self):
        """Calculate certification expiry date."""
        for record in self:
            if (record.certification_issued_date and 
                record.channel_id.certification_validity_months > 0):
                record.certification_expiry_date = (
                    record.certification_issued_date + 
                    relativedelta(months=record.channel_id.certification_validity_months)
                )
            else:
                record.certification_expiry_date = False
    
    @api.depends('certification_expiry_date')
    def _compute_certification_status(self):
        """Determine certification status."""
        for record in self:
            if record.member_status != 'completed':
                record.certification_status = 'none'
            elif not record.certification_expiry_date:
                record.certification_status = 'valid'
            elif record.certification_expiry_date < date.today():
                record.certification_status = 'expired'
            elif record.certification_expiry_date <= date.today() + timedelta(days=30):
                record.certification_status = 'expiring'
            else:
                record.certification_status = 'valid'
    
    @api.depends('channel_id.slide_ids', 'partner_id', 'member_status')
    def _compute_final_score(self):
        """Calculate average quiz score (as fraction 0.0-1.0)."""
        for record in self:
            # Get all quiz slides for this channel
            quiz_slides = record.channel_id.slide_ids.filtered(
                lambda s: s.slide_category == 'quiz'
            )
            
            if not quiz_slides:
                record.final_score = 0.0
                continue
            
            # Get partner's quiz results
            quiz_results = self.env['slide.slide.partner'].search([
                ('slide_id', 'in', quiz_slides.ids),
                ('partner_id', '=', record.partner_id.id),
                ('completed', '=', True)
            ])
            
            if quiz_results:
                # Calculate average score if scores are recorded
                scores = []
                # Check if the field exists in the model registry and the table
                has_quiz_score = 'quiz_score' in quiz_results._fields
                
                for res in quiz_results:
                    score = 0.0
                    if has_quiz_score:
                        try:
                            # Use getattr with default to be safe, but Odoo might still crash 
                            # if the column is missing in DB during fetch.
                            score = res.quiz_score
                        except Exception:
                            # Fallback if column is missing in DB
                            score = 0.0
                    
                    # If it's > 1.0, assume it was stored as percentage and convert to fraction
                    if score > 1.0:
                        score = score / 100.0
                    elif score == 0.0 and res.completed:
                        # Fallback: if completed but no score, assume passing (minimum)
                        score = record.channel_id.minimum_passing_score / 100.0
                    scores.append(score)
                
                if scores:
                    record.final_score = sum(scores) / len(quiz_slides)
                else:
                    record.final_score = len(quiz_results) / len(quiz_slides)
            else:
                record.final_score = 0.0
    
    @api.depends('final_score', 'channel_id.minimum_passing_score', 'member_status')
    def _compute_passed_course(self):
        """Determine if guard passed the course."""
        for record in self:
            if record.member_status == 'completed':
                # Convert final_score (0-1) to percentage (0-100) for comparison
                record.passed_course = (
                    (record.final_score * 100.0) >= record.channel_id.minimum_passing_score
                )
            else:
                record.passed_course = False
    
    @api.depends('passed_course', 'member_status')
    def _compute_pass_status_text(self):
        """Convert pass status to user-friendly text."""
        for record in self:
            if record.member_status != 'completed':
                record.pass_status_text = '-'
            elif record.passed_course:
                record.pass_status_text = 'Correct'
            else:
                record.pass_status_text = 'Not Correct'
    
    def action_view_all_quiz_responses(self):
        """View all question-level responses across all quizzes in this enrollment."""
        self.ensure_one()
        
        # Get all quiz line IDs from all quiz attempts in this enrollment
        quiz_line_ids = []
        for quiz_response in self.quiz_response_ids:
            quiz_line_ids.extend(quiz_response.quiz_line_ids.ids)
        
        return {
            'name': _('Quiz Responses: %s - %s') % (self.partner_id.name, self.channel_id.name),
            'type': 'ir.actions.act_window',
            'res_model': 'slide.slide.partner.quiz.line',
            'view_mode': 'list,form',
            'domain': [('id', 'in', quiz_line_ids)],
            'context': {'default_slide_partner_id': False},
            'target': 'current',
        }
    
    def action_renew_certification(self):
        """Renew an expired certification by re-enrolling."""
        for record in self:
            if record.certification_status in ['expired', 'expiring']:
                # Reset enrollment status
                record.write({
                    'member_status': 'joined',
                    'completion': 0,
                    'completed_slides_count': 0,
                })
                
                # Reset slide completions
                self.env['slide.slide.partner'].search([
                    ('channel_id', '=', record.channel_id.id),
                    ('partner_id', '=', record.partner_id.id)
                ]).write({'completed': False})
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Certification renewal initiated. Please complete the course again.'),
                'type': 'success',
                'sticky': False,
            }
        }




class SlideSlide(models.Model):
    """Extend eLearning Slides/Lessons."""
    
    _inherit = 'slide.slide'
    
    # Add guard-specific metadata if needed
    is_guard_specific = fields.Boolean(
        string='Guard-Specific Content',
        default=False,
        help='This content is specifically for guard training'
    )


class SlideSlidePartner(models.Model):
    """Track individual slide scores for guards."""
    
    _inherit = 'slide.slide.partner'
    
    quiz_score = fields.Float(
        string='Quiz Score (%)',
        compute='_compute_quiz_stats',
        store=True,
        help='Score achieved by the guard for this specific quiz'
    )
    
    correct_count = fields.Integer(
        string='Correct Answers',
        compute='_compute_quiz_stats',
        store=True
    )
    
    total_count = fields.Integer(
        string='Total Questions',
        compute='_compute_quiz_stats',
        store=True
    )
    
    quiz_summary = fields.Char(
        string='Score (Correct/Total)',
        compute='_compute_quiz_stats',
        store=True
    )
    
    quiz_status = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed')
    ], string='Status', compute='_compute_quiz_stats', store=True)

    quiz_line_ids = fields.One2many(
        'slide.slide.partner.quiz.line',
        'slide_partner_id',
        string='Quiz Responses'
    )
    
    @api.depends('quiz_line_ids', 'completed', 'channel_id.minimum_passing_score')
    def _compute_quiz_stats(self):
        """Compute quiz performance statistics."""
        for record in self:
            if record.quiz_line_ids:
                total = len(record.quiz_line_ids)
                correct = len(record.quiz_line_ids.filtered(lambda l: l.is_correct))
                record.total_count = total
                record.correct_count = correct
                record.quiz_score = (correct / total) if total > 0 else 0.0
                record.quiz_summary = f"{correct}/{total}"
                record.quiz_status = 'passed' if record.completed else 'failed'
            elif record.completed:
                # Fallback for legacy/demo data without detailed lines
                record.total_count = 0
                record.correct_count = 0
                record.quiz_score = record.channel_id.minimum_passing_score / 100.0
                record.quiz_summary = _("Passed (No details)")
                record.quiz_status = 'passed'
            else:
                record.total_count = 0
                record.correct_count = 0
                record.quiz_score = 0.0
                record.quiz_summary = "-"
                record.quiz_status = 'failed'


class SlideSlidePartnerQuizLine(models.Model):
    """Store individual question responses for a quiz attempt."""
    
    _name = 'slide.slide.partner.quiz.line'
    _description = 'Guard Quiz Response'
    _order = 'id'
    
    slide_partner_id = fields.Many2one(
        'slide.slide.partner',
        string='Slide Partner',
        required=True,
        ondelete='cascade'
    )
    
    question_id = fields.Many2one(
        'slide.question',
        string='Question',
        required=True
    )
    
    # Use question_id name directly instead of related if it causes issues
    question_text = fields.Text(
        string='Question Text',
        compute='_compute_question_text',
        store=True
    )
    
    @api.depends('question_id')
    def _compute_question_text(self):
        for record in self:
            if record.question_id:
                record.question_text = (
                    getattr(record.question_id, 'question', None) or 
                    getattr(record.question_id, 'name', None) or 
                    str(record.question_id.id)
                )
            else:
                record.question_text = False

    answer_ids = fields.Many2many(
        'slide.answer',
        string='Selected Answers'
    )
    
    answer_text = fields.Text(
        string='Short Answer Text'
    )
    
    is_correct = fields.Boolean(
        string='Is Correct',
        default=False
    )
    
    status = fields.Selection([
        ('correct', 'Correct'),
        ('incorrect', 'Incorrect')
    ], string='Result', compute='_compute_status', store=True)

    score = fields.Float(
        string='Score',
        default=0.0
    )
    
    @api.depends('is_correct')
    def _compute_status(self):
        """Compute the text status of the answer."""
        for record in self:
            record.status = 'correct' if record.is_correct else 'incorrect'

