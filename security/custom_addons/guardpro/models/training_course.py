# -*- coding: utf-8 -*-
"""Training Management LMS."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TrainingCourse(models.Model):
    """Training course catalog."""
    
    _name = 'training.course'
    _description = 'Training Course'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Course Name',
        required=True,
        translate=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    code = fields.Char(
        string='Course Code',
        required=True
    )
    
    category_id = fields.Many2one(
        'training.category',
        string='Category'
    )
    
    description = fields.Html(
        string='Description',
        translate=True
    )
    
    duration_hours = fields.Float(
        string='Duration (hours)',
        help='Estimated completion time'
    )
    
    level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced')
    ], string='Level', default='beginner')
    
    is_mandatory = fields.Boolean(
        string='Mandatory',
        help='All guards must complete this course'
    )
    
    validity_months = fields.Integer(
        string='Validity (months)',
        help='Certificate validity period. 0 = never expires'
    )
    
    lesson_ids = fields.One2many(
        'training.lesson',
        'course_id',
        string='Lessons'
    )
    
    quiz_ids = fields.One2many(
        'training.quiz',
        'course_id',
        string='Quizzes'
    )
    
    enrollment_count = fields.Integer(
        string='Enrollments',
        compute='_compute_stats'
    )
    
    completion_count = fields.Integer(
        string='Completions',
        compute='_compute_stats'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    def _compute_stats(self):
        """Compute enrollment statistics."""
        for record in self:
            enrollments = self.env['training.enrollment'].search([
                ('course_id', '=', record.id)
            ])
            record.enrollment_count = len(enrollments)
            record.completion_count = len(enrollments.filtered(lambda e: e.status == 'completed'))
    
    def action_view_enrollments(self):
        """View enrollments for this course."""
        self.ensure_one()
        return {
            'name': _('Enrollments: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'training.enrollment',
            'view_mode': 'list,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id}
        }
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Course code must be unique!'),
    ]


class TrainingCategory(models.Model):
    """Training categories."""
    
    _name = 'training.category'
    _description = 'Training Category'
    _order = 'name'
    
    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True
    )
    
    color = fields.Integer(
        string='Color Index'
    )


class TrainingLesson(models.Model):
    """Training lessons."""
    
    _name = 'training.lesson'
    _description = 'Training Lesson'
    _order = 'course_id, sequence'
    
    name = fields.Char(
        string='Lesson Title',
        required=True,
        translate=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    course_id = fields.Many2one(
        'training.course',
        string='Course',
        required=True,
        ondelete='cascade'
    )
    
    lesson_type = fields.Selection([
        ('text', 'Text Content'),
        ('video', 'Video'),
        ('pdf', 'PDF Document'),
        ('quiz', 'Quiz')
    ], string='Type', required=True, default='text')
    
    content = fields.Html(
        string='Content',
        translate=True
    )
    
    video_url = fields.Char(
        string='Video URL'
    )
    
    pdf_file = fields.Binary(
        string='PDF File',
        attachment=True
    )
    
    pdf_filename = fields.Char(
        string='Filename'
    )
    
    duration_minutes = fields.Integer(
        string='Duration (minutes)'
    )


class TrainingQuiz(models.Model):
    """Training quizzes."""
    
    _name = 'training.quiz'
    _description = 'Training Quiz'
    _order = 'course_id, sequence'
    
    name = fields.Char(
        string='Quiz Title',
        required=True,
        translate=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    course_id = fields.Many2one(
        'training.course',
        string='Course',
        required=True,
        ondelete='cascade'
    )
    
    question_ids = fields.One2many(
        'training.quiz.question',
        'quiz_id',
        string='Questions'
    )
    
    passing_score = fields.Integer(
        string='Passing Score (%)',
        default=80
    )
    
    time_limit_minutes = fields.Integer(
        string='Time Limit (minutes)',
        help='0 = no time limit'
    )


class TrainingQuizQuestion(models.Model):
    """Quiz questions."""
    
    _name = 'training.quiz.question'
    _description = 'Training Quiz Question'
    _order = 'quiz_id, sequence'
    
    quiz_id = fields.Many2one(
        'training.quiz',
        string='Quiz',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    question = fields.Text(
        string='Question',
        required=True,
        translate=True
    )
    
    question_type = fields.Selection([
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer')
    ], string='Type', required=True, default='multiple_choice')
    
    option_ids = fields.One2many(
        'training.quiz.question.option',
        'question_id',
        string='Options'
    )
    
    correct_answer = fields.Text(
        string='Correct Answer',
        help='For short answer questions'
    )


class TrainingQuizQuestionOption(models.Model):
    """Quiz question options."""
    
    _name = 'training.quiz.question.option'
    _description = 'Quiz Question Option'
    _order = 'question_id, sequence'
    
    question_id = fields.Many2one(
        'training.quiz.question',
        string='Question',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    text = fields.Char(
        string='Option Text',
        required=True,
        translate=True
    )
    
    is_correct = fields.Boolean(
        string='Correct Answer',
        default=False
    )


class TrainingEnrollment(models.Model):
    """Guard course enrollments."""
    
    _name = 'training.enrollment'
    _description = 'Training Enrollment'
    _order = 'enroll_date desc'
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade'
    )
    
    course_id = fields.Many2one(
        'training.course',
        string='Course',
        required=True
    )
    
    enroll_date = fields.Date(
        string='Enrollment Date',
        default=fields.Date.today,
        required=True
    )
    
    start_date = fields.Date(
        string='Started On'
    )
    
    completion_date = fields.Date(
        string='Completed On'
    )
    
    expiry_date = fields.Date(
        string='Certificate Expiry',
        compute='_compute_expiry_date',
        store=True
    )
    
    status = fields.Selection([
        ('enrolled', 'Enrolled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='enrolled', required=True)
    
    progress_percentage = fields.Float(
        string='Progress (%)',
        compute='_compute_progress'
    )
    
    quiz_score = fields.Float(
        string='Quiz Score (%)'
    )
    
    passed = fields.Boolean(
        string='Passed',
        compute='_compute_passed',
        store=True
    )
    
    certificate_url = fields.Char(
        string='Certificate'
    )
    
    @api.depends('completion_date', 'course_id.validity_months')
    def _compute_expiry_date(self):
        """Compute certificate expiry date."""
        for record in self:
            if record.completion_date and record.course_id.validity_months > 0:
                from dateutil.relativedelta import relativedelta
                record.expiry_date = record.completion_date + relativedelta(months=record.course_id.validity_months)
            else:
                record.expiry_date = False
    
    def _compute_progress(self):
        """Compute course progress."""
        for record in self:
            # Simplified: based on lessons viewed
            record.progress_percentage = 0.0  # TODO: Implement lesson tracking
    
    @api.depends('quiz_score', 'course_id')
    def _compute_passed(self):
        """Check if guard passed the course."""
        for record in self:
            if record.status == 'completed' and record.course_id.quiz_ids:
                passing_score = record.course_id.quiz_ids[0].passing_score if record.course_id.quiz_ids else 80
                record.passed = record.quiz_score >= passing_score
            else:
                record.passed = False
    
    def action_start_course(self):
        """Start the course."""
        self.write({
            'status': 'in_progress',
            'start_date': fields.Date.today()
        })
    
    def action_complete_course(self):
        """Mark course as completed."""
        self.write({
            'status': 'completed',
            'completion_date': fields.Date.today()
        })

