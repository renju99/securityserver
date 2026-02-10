# -*- coding: utf-8 -*-
"""Guard Performance Scoring System."""

import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class GuardPerformanceCriteria(models.Model):
    """Performance scoring criteria configuration."""

    _name = 'guard.performance.criteria'
    _description = 'Guard Performance Criteria'
    _order = 'sequence, name'

    name = fields.Char(
        string='Criteria Name',
        required=True,
        translate=True,
        help="Name of the performance criteria"
    )
    code = fields.Selection([
        ('punctuality', 'Punctuality'),
        ('tour_completion', 'Tour Completion Rate'),
        ('incident_response', 'Incident Response Quality'),
        ('client_satisfaction', 'Client Satisfaction'),
        ('shift_adherence', 'Shift Adherence'),
        ('training_completion', 'Training Completion'),
        ('equipment_care', 'Equipment Care'),
        ('communication', 'Communication Quality'),
        ('professionalism', 'Professionalism'),
        ('custom', 'Custom Criteria'),
    ], string='Criteria Type', required=True, default='custom')
    description = fields.Text(
        string='Description',
        translate=True,
        help="Detailed description of the criteria"
    )
    weight = fields.Float(
        string='Weight (%)',
        required=True,
        default=10.0,
        help="Weight in overall score calculation (total should be 100%)"
    )
    calculation_method = fields.Selection([
        ('automatic', 'Automatic Calculation'),
        ('manual', 'Manual Entry'),
        ('hybrid', 'Hybrid (Auto + Manual)'),
    ], string='Calculation Method', required=True, default='automatic')
    min_score = fields.Float(string='Minimum Score', default=0.0)
    max_score = fields.Float(string='Maximum Score', default=100.0)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    @api.constrains('weight')
    def _check_weight(self):
        """Validate weight is positive."""
        for record in self:
            if record.weight < 0 or record.weight > 100:
                raise ValidationError(
                    _('Weight must be between 0 and 100%.')
                )

    @api.constrains('min_score', 'max_score')
    def _check_score_range(self):
        """Validate score range."""
        for record in self:
            if record.min_score >= record.max_score:
                raise ValidationError(
                    _('Minimum score must be less than maximum score.')
                )


class GuardPerformanceMetric(models.Model):
    """Individual performance metric score for a guard in a period."""

    _name = 'guard.performance.metric'
    _description = 'Guard Performance Metric'
    _order = 'period_start desc, guard_id, criteria_id'
    _rec_name = 'display_name'

    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        index=True
    )
    criteria_id = fields.Many2one(
        'guard.performance.criteria',
        string='Criteria',
        required=True,
        ondelete='restrict'
    )
    period_start = fields.Date(
        string='Period Start',
        required=True,
        index=True
    )
    period_end = fields.Date(
        string='Period End',
        required=True,
        index=True
    )
    score = fields.Float(
        string='Score',
        required=True,
        help="Score for this criteria in this period"
    )
    weighted_score = fields.Float(
        string='Weighted Score',
        compute='_compute_weighted_score',
        store=True,
        help="Score multiplied by criteria weight"
    )
    calculation_details = fields.Text(
        string='Calculation Details',
        help="Details of how the score was calculated"
    )
    manual_adjustment = fields.Float(
        string='Manual Adjustment',
        default=0.0,
        help="Manual adjustment to the calculated score"
    )
    notes = fields.Text(string='Notes')
    reviewer_id = fields.Many2one(
        'res.users',
        string='Reviewer',
        help="User who reviewed/adjusted this metric"
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='guard_id.company_id',
        store=True
    )

    # Computed criteria type for easy filtering
    criteria_code = fields.Selection(
        related='criteria_id.code',
        string='Criteria Type',
        store=True
    )

    @api.depends('criteria_id.weight', 'score')
    def _compute_weighted_score(self):
        """Calculate weighted score."""
        for record in self:
            if record.criteria_id:
                record.weighted_score = (
                    record.score * record.criteria_id.weight / 100.0
                )
            else:
                record.weighted_score = 0.0

    @api.depends('guard_id', 'criteria_id', 'period_start', 'period_end')
    def _compute_display_name(self):
        """Compute display name."""
        for record in self:
            record.display_name = _(
                '%(guard)s - %(criteria)s (%(start)s to %(end)s)',
                guard=record.guard_id.name,
                criteria=record.criteria_id.name,
                start=record.period_start,
                end=record.period_end
            )

    @api.constrains('period_start', 'period_end')
    def _check_period(self):
        """Validate period dates."""
        for record in self:
            if record.period_start >= record.period_end:
                raise ValidationError(
                    _('Period start date must be before end date.')
                )

    @api.constrains('score')
    def _check_score(self):
        """Validate score is within criteria range."""
        for record in self:
            if record.criteria_id:
                if not (record.criteria_id.min_score <= record.score <=
                        record.criteria_id.max_score):
                    raise ValidationError(
                        _('Score must be between %(min)s and %(max)s for '
                          'this criteria.',
                          min=record.criteria_id.min_score,
                          max=record.criteria_id.max_score)
                    )


class GuardPerformanceReview(models.Model):
    """Performance review for a guard (monthly, quarterly, annual)."""

    _name = 'guard.performance.review'
    _description = 'Guard Performance Review'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'review_date desc, guard_id'

    name = fields.Char(
        string='Review Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        tracking=True,
        index=True
    )
    review_period = fields.Selection([
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('probation', 'Probation Period'),
        ('ad_hoc', 'Ad-Hoc'),
    ], string='Review Period', required=True, default='monthly', tracking=True)
    period_start = fields.Date(
        string='Period Start',
        required=True,
        tracking=True,
        index=True
    )
    period_end = fields.Date(
        string='Period End',
        required=True,
        tracking=True,
        index=True
    )
    review_date = fields.Date(
        string='Review Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)

    # Scores
    metric_ids = fields.One2many(
        'guard.performance.metric',
        compute='_compute_metric_ids',
        search='_search_metric_ids',
        string='Performance Metrics'
    )
    overall_score = fields.Float(
        string='Overall Score',
        compute='_compute_scores',
        store=True,
        help="Weighted average of all criteria scores"
    )
    performance_grade = fields.Selection([
        ('excellent', 'Excellent (90-100)'),
        ('good', 'Good (80-89)'),
        ('satisfactory', 'Satisfactory (70-79)'),
        ('needs_improvement', 'Needs Improvement (60-69)'),
        ('unsatisfactory', 'Unsatisfactory (<60)'),
    ], string='Performance Grade', compute='_compute_scores', store=True)

    # Individual metric scores (computed from metric_ids)
    punctuality_score = fields.Float(
        string='Punctuality',
        compute='_compute_individual_scores',
        store=True
    )
    tour_completion_score = fields.Float(
        string='Tour Completion',
        compute='_compute_individual_scores',
        store=True
    )
    incident_response_score = fields.Float(
        string='Incident Response',
        compute='_compute_individual_scores',
        store=True
    )
    client_satisfaction_score = fields.Float(
        string='Client Satisfaction',
        compute='_compute_individual_scores',
        store=True
    )
    shift_adherence_score = fields.Float(
        string='Shift Adherence',
        compute='_compute_individual_scores',
        store=True
    )

    # Review content
    strengths = fields.Text(
        string='Strengths',
        tracking=True,
        help="Key strengths demonstrated during the period"
    )
    areas_for_improvement = fields.Text(
        string='Areas for Improvement',
        tracking=True,
        help="Areas where improvement is needed"
    )
    goals = fields.Text(
        string='Goals for Next Period',
        tracking=True,
        help="Goals and objectives for the next review period"
    )
    action_plan = fields.Text(
        string='Action Plan',
        tracking=True,
        help="Specific actions to improve performance"
    )
    reviewer_notes = fields.Text(
        string='Reviewer Notes',
        tracking=True
    )
    guard_comments = fields.Text(
        string='Guard Comments',
        help="Comments from the guard being reviewed"
    )

    # Review participants
    reviewer_id = fields.Many2one(
        'res.users',
        string='Reviewer',
        required=True,
        default=lambda self: self.env.user,
        tracking=True
    )
    approver_id = fields.Many2one(
        'res.users',
        string='Approver',
        tracking=True
    )
    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True,
        tracking=True
    )

    # Recommendations
    recommendation = fields.Selection([
        ('continue', 'Continue in Current Position'),
        ('promote', 'Recommend for Promotion'),
        ('additional_training', 'Additional Training Required'),
        ('probation', 'Place on Probation'),
        ('terminate', 'Recommend Termination'),
    ], string='Recommendation', tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='guard_id.company_id',
        store=True
    )

    # Signature/Acknowledgement
    guard_acknowledged = fields.Boolean(
        string='Guard Acknowledged',
        help="Guard has acknowledged and signed the review"
    )
    guard_acknowledged_date = fields.Datetime(
        string='Acknowledged Date',
        readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate sequence."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'guard.performance.review'
                ) or _('New')
        return super().create(vals_list)

    @api.depends('guard_id', 'period_start', 'period_end')
    def _compute_metric_ids(self):
        """Get all metrics for this guard and period."""
        for review in self:
            if review.guard_id and review.period_start and review.period_end:
                review.metric_ids = self.env['guard.performance.metric'].search([
                    ('guard_id', '=', review.guard_id.id),
                    ('period_start', '>=', review.period_start),
                    ('period_end', '<=', review.period_end),
                ])
            else:
                review.metric_ids = False

    def _search_metric_ids(self, operator, value):
        """Search method for metric_ids computed field."""
        return [
            ('guard_id', '!=', False),
            ('period_start', '!=', False),
            ('period_end', '!=', False),
        ]

    @api.depends('metric_ids', 'metric_ids.weighted_score')
    def _compute_scores(self):
        """Calculate overall score and grade."""
        for review in self:
            if review.metric_ids:
                total_weighted = sum(review.metric_ids.mapped('weighted_score'))
                total_weight = sum(
                    review.metric_ids.mapped('criteria_id.weight')
                )
                if total_weight > 0:
                    review.overall_score = round((total_weighted / total_weight * 100), 0)
                else:
                    review.overall_score = 0.0
            else:
                review.overall_score = 0.0

            # Determine grade
            score = review.overall_score
            if score >= 90:
                review.performance_grade = 'excellent'
            elif score >= 80:
                review.performance_grade = 'good'
            elif score >= 70:
                review.performance_grade = 'satisfactory'
            elif score >= 60:
                review.performance_grade = 'needs_improvement'
            else:
                review.performance_grade = 'unsatisfactory'

    @api.depends('metric_ids', 'metric_ids.criteria_code', 'metric_ids.score')
    def _compute_individual_scores(self):
        """Calculate individual criteria scores."""
        for review in self:
            # Initialize all scores
            review.punctuality_score = 0.0
            review.tour_completion_score = 0.0
            review.incident_response_score = 0.0
            review.client_satisfaction_score = 0.0
            review.shift_adherence_score = 0.0

            for metric in review.metric_ids:
                if metric.criteria_code == 'punctuality':
                    review.punctuality_score = round(metric.score, 0)
                elif metric.criteria_code == 'tour_completion':
                    review.tour_completion_score = round(metric.score, 0)
                elif metric.criteria_code == 'incident_response':
                    review.incident_response_score = round(metric.score, 0)
                elif metric.criteria_code == 'client_satisfaction':
                    review.client_satisfaction_score = round(metric.score, 0)
                elif metric.criteria_code == 'shift_adherence':
                    review.shift_adherence_score = round(metric.score, 0)

    @api.constrains('period_start', 'period_end')
    def _check_period(self):
        """Validate period dates."""
        for record in self:
            if record.period_start >= record.period_end:
                raise ValidationError(
                    _('Period start date must be before end date.')
                )

    def action_start_review(self):
        """Start the review process."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft reviews can be started.'))
        self.write({'state': 'in_progress'})
        return True

    def action_complete_review(self):
        """Mark review as completed."""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Only in-progress reviews can be completed.'))
        self.write({'state': 'completed'})
        return True

    def action_approve_review(self):
        """Approve the review."""
        self.ensure_one()
        if self.state != 'completed':
            raise UserError(_('Only completed reviews can be approved.'))
        self.write({
            'state': 'approved',
            'approver_id': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })
        # Send notification to guard
        self._send_review_notification()
        return True

    def action_cancel_review(self):
        """Cancel the review."""
        self.ensure_one()
        self.write({'state': 'cancelled'})
        return True

    def action_reset_to_draft(self):
        """Reset review to draft."""
        self.ensure_one()
        self.write({'state': 'draft'})
        return True

    def action_guard_acknowledge(self):
        """Guard acknowledges the review."""
        self.ensure_one()
        if not self.guard_acknowledged:
            self.write({
                'guard_acknowledged': True,
                'guard_acknowledged_date': fields.Datetime.now(),
            })
        return True

    def action_calculate_metrics(self):
        """Calculate performance metrics for this review period."""
        self.ensure_one()
        self._calculate_all_metrics()
        return True

    def _calculate_all_metrics(self):
        """Calculate all performance metrics for the review period."""
        self.ensure_one()

        # Get all active criteria
        criteria = self.env['guard.performance.criteria'].search([
            ('active', '=', True),
            ('calculation_method', 'in', ['automatic', 'hybrid']),
        ])

        for criterion in criteria:
            score = self._calculate_criterion_score(criterion)
            if score is not None:
                # Create or update metric
                existing = self.env['guard.performance.metric'].search([
                    ('guard_id', '=', self.guard_id.id),
                    ('criteria_id', '=', criterion.id),
                    ('period_start', '=', self.period_start),
                    ('period_end', '=', self.period_end),
                ], limit=1)

                vals = {
                    'guard_id': self.guard_id.id,
                    'criteria_id': criterion.id,
                    'period_start': self.period_start,
                    'period_end': self.period_end,
                    'score': score,
                    'calculation_details': self._get_calculation_details(
                        criterion
                    ),
                }

                if existing:
                    existing.write(vals)
                else:
                    self.env['guard.performance.metric'].create(vals)

    def _calculate_criterion_score(self, criterion):
        """Calculate score for a specific criterion."""
        self.ensure_one()

        if criterion.code == 'punctuality':
            return self._calculate_punctuality_score()
        elif criterion.code == 'tour_completion':
            return self._calculate_tour_completion_score()
        elif criterion.code == 'incident_response':
            return self._calculate_incident_response_score()
        elif criterion.code == 'client_satisfaction':
            return self._calculate_client_satisfaction_score()
        elif criterion.code == 'shift_adherence':
            return self._calculate_shift_adherence_score()
        elif criterion.code == 'training_completion':
            return self._calculate_training_completion_score()
        else:
            return None

    def _calculate_punctuality_score(self):
        """Calculate punctuality score based on attendance records."""
        self.ensure_one()

        attendances = self.env['guard.attendance'].search([
            ('guard_id', '=', self.guard_id.id),
            ('checkin_time', '>=', self.period_start),
            ('checkin_time', '<=', self.period_end),
        ])

        if not attendances:
            return 100.0

        total = len(attendances)
        on_time = 0
        late_minor = 0  # 1-15 minutes late
        late_major = 0  # 16+ minutes late

        for attendance in attendances:
            if attendance.shift_id and attendance.shift_id.start_datetime:
                # Compare check-in time with scheduled start time
                scheduled_start = attendance.shift_id.start_datetime
                actual_checkin = attendance.checkin_time
                
                # Calculate delay in minutes
                delay_minutes = (actual_checkin - scheduled_start).total_seconds() / 60

                if delay_minutes <= 5:  # 5 minute grace period
                    on_time += 1
                elif delay_minutes <= 15:
                    late_minor += 1
                else:
                    late_major += 1
            else:
                on_time += 1  # No scheduled time, count as on-time

        score = (
            (on_time * 100 + late_minor * 80 + late_major * 50) / total
        )
        return round(min(100.0, max(0.0, score)), 0)

    def _calculate_tour_completion_score(self):
        """Calculate tour completion rate score."""
        self.ensure_one()

        # Get assigned tours from shifts
        shifts = self.env['guard.shift'].search([
            ('guard_id', '=', self.guard_id.id),
            ('start_datetime', '>=', self.period_start),
            ('start_datetime', '<=', self.period_end),
        ])

        # Count total number of tours assigned across all shifts
        total_assigned_tours = 0
        for shift in shifts:
            total_assigned_tours += len(shift.tour_ids)

        if total_assigned_tours == 0:
            return 100.0

        # Get completed tours
        tour_logs = self.env['tour.log'].search([
            ('guard_id', '=', self.guard_id.id),
            ('start_time', '>=', self.period_start),
            ('start_time', '<=', self.period_end),
            ('status', '=', 'completed'),
        ])

        completed_tours = len(tour_logs)

        # Calculate completion rate
        completion_rate = (completed_tours / total_assigned_tours) * 100
        return round(min(100.0, completion_rate), 0)

    def _calculate_incident_response_score(self):
        """Calculate incident response quality score."""
        self.ensure_one()

        incidents = self.env['incident.report'].search([
            ('guard_id', '=', self.guard_id.id),
            ('incident_datetime', '>=', self.period_start),
            ('incident_datetime', '<=', self.period_end),
        ])

        if not incidents:
            return 100.0

        total = len(incidents)
        quality_scores = []

        for incident in incidents:
            # Base score starts at 60
            score = 60.0

            # Detailed description: +15 points
            if incident.description:
                desc_length = len(incident.description.strip())
                if desc_length >= 200:
                    score += 15
                elif desc_length >= 100:
                    score += 10
                elif desc_length >= 50:
                    score += 5

            # Has photos: +10 points (scaled by number of photos)
            if incident.photo_ids:
                photo_count = len(incident.photo_ids)
                if photo_count >= 3:
                    score += 10
                elif photo_count >= 2:
                    score += 7
                elif photo_count >= 1:
                    score += 5

            # Timely reporting: +15 points (scaled by response time in minutes)
            if incident.response_time_minutes:
                if incident.response_time_minutes <= 15:
                    score += 15
                elif incident.response_time_minutes <= 30:
                    score += 10
                elif incident.response_time_minutes <= 60:
                    score += 5

            # Proper categorization and severity assessment: +5 points
            if incident.category_id and incident.severity:
                score += 5

            # Follow-up actions documented: +5 points
            if incident.immediate_actions:
                score += 5

            quality_scores.append(min(100.0, score))

        return round(sum(quality_scores) / total, 0) if quality_scores else 100.0

    def _calculate_client_satisfaction_score(self):
        """Calculate client satisfaction score from feedback."""
        self.ensure_one()

        feedbacks = self.env['client.feedback'].search([
            ('guard_id', '=', self.guard_id.id),
            ('feedback_date', '>=', self.period_start),
            ('feedback_date', '<=', self.period_end),
        ])

        if not feedbacks:
            return 80.0  # Default if no feedback

        # Calculate average rating (overall_rating is Selection field with string values '1'-'5')
        # Average rating * 20 to get score out of 100
        total_rating = sum(int(f.overall_rating) for f in feedbacks)
        avg_rating = total_rating / len(feedbacks)
        return round(avg_rating * 20, 0)

    def _calculate_shift_adherence_score(self):
        """Calculate shift adherence score."""
        self.ensure_one()

        shifts = self.env['guard.shift'].search([
            ('guard_id', '=', self.guard_id.id),
            ('start_datetime', '>=', self.period_start),
            ('start_datetime', '<=', self.period_end),
        ])

        if not shifts:
            return 100.0

        total = len(shifts)
        attended = 0
        
        for shift in shifts:
            # Check if guard checked in for this shift
            attendance = self.env['guard.attendance'].search([
                ('guard_id', '=', self.guard_id.id),
                ('shift_id', '=', shift.id),
            ], limit=1)
            if attendance:
                attended += 1

        adherence_rate = (attended / total) * 100
        return round(adherence_rate, 0)

    def _calculate_training_completion_score(self):
        """Calculate training completion score."""
        self.ensure_one()

        # Check eLearning completion
        if hasattr(self.guard_id.employee_id, 'slide_channel_ids'):
            channels = self.guard_id.employee_id.slide_channel_ids
            if channels:
                completion_rates = []
                for channel in channels:
                    partner = self.guard_id.employee_id.user_id.partner_id
                    if partner:
                        completion = channel._get_completion(partner.id)
                        completion_rates.append(completion)
                
                if completion_rates:
                    return round(sum(completion_rates) / len(completion_rates), 0)
        
        return 80.0  # Default if no training data

    def _get_calculation_details(self, criterion):
        """Get calculation details for a criterion."""
        self.ensure_one()
        details = _('Automatically calculated for period %(start)s to %(end)s',
                    start=self.period_start, end=self.period_end)
        return details

    def _send_review_notification(self):
        """Send review notification to guard."""
        self.ensure_one()
        
        if self.guard_id.employee_id.user_id:
            template = self.env.ref(
                'guardpro.email_template_performance_review',
                raise_if_not_found=False
            )
            if template:
                template.send_mail(self.id, force_send=True)

    @api.model
    def _cron_calculate_monthly_performance(self):
        """Cron job to calculate monthly performance for all active guards."""
        _logger.info('Starting monthly performance calculation...')
        
        # Get all active guards
        guards = self.env['guard.profile'].search([('status', '=', 'active')])
        
        # Calculate for previous month
        today = fields.Date.today()
        period_end = today - relativedelta(days=today.day)
        period_start = period_end - relativedelta(day=1)
        
        created_count = 0
        for guard in guards:
            # Check if review already exists for this period
            existing = self.search([
                ('guard_id', '=', guard.id),
                ('period_start', '=', period_start),
                ('period_end', '=', period_end),
            ])
            
            if not existing:
                # Create draft review
                try:
                    review = self.create({
                        'guard_id': guard.id,
                        'review_period': 'monthly',
                        'period_start': period_start,
                        'period_end': period_end,
                        'review_date': today,
                        'reviewer_id': self.env.ref('base.user_admin').id,
                        'state': 'draft',
                    })
                    # Calculate metrics
                    review._calculate_all_metrics()
                    created_count += 1
                except Exception as e:
                    _logger.error(
                        'Error creating performance review for guard %s: %s',
                        guard.name, str(e)
                    )
        
        _logger.info(
            'Monthly performance calculation complete. Created %d reviews.',
            created_count
        )
        return True

    @api.model
    def _cron_send_review_reminders(self):
        """Send reminders for pending performance reviews."""
        _logger.info('Sending performance review reminders...')
        
        # Find draft reviews older than 3 days
        three_days_ago = fields.Date.today() - timedelta(days=3)
        pending_reviews = self.search([
            ('state', '=', 'draft'),
            ('review_date', '<=', three_days_ago),
        ])
        
        for review in pending_reviews:
            try:
                # Create activity for reviewer
                review.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=review.reviewer_id.id,
                    summary=_('Complete Performance Review'),
                    note=_(
                        'Please complete the performance review for %(guard)s '
                        'for the period %(start)s to %(end)s.',
                        guard=review.guard_id.name,
                        start=review.period_start,
                        end=review.period_end
                    ),
                )
            except Exception as e:
                _logger.error(
                    'Error sending reminder for review %s: %s',
                    review.name, str(e)
                )
        
        _logger.info(
            'Sent %d performance review reminders.',
            len(pending_reviews)
        )
        return True


class GuardPerformanceBadge(models.Model):
    """Performance achievement badges for guards."""

    _name = 'guard.performance.badge'
    _description = 'Guard Performance Badge'
    _order = 'earned_date desc'

    name = fields.Char(string='Badge Name', required=True)
    badge_type = fields.Selection([
        ('punctuality', 'Perfect Punctuality'),
        ('attendance', 'Perfect Attendance'),
        ('tour_master', 'Tour Master'),
        ('incident_hero', 'Incident Response Hero'),
        ('client_favorite', 'Client Favorite'),
        ('safety_champion', 'Safety Champion'),
        ('trainer', 'Certified Trainer'),
        ('team_player', 'Team Player'),
        ('innovator', 'Innovator'),
        ('leader', 'Leadership Excellence'),
        ('top_performer', 'Top Performer'),
        ('milestone_1yr', '1 Year Service'),
        ('milestone_3yr', '3 Years Service'),
        ('milestone_5yr', '5 Years Service'),
        ('milestone_10yr', '10 Years Service'),
        ('custom', 'Custom Achievement'),
    ], string='Badge Type', required=True)
    description = fields.Text(string='Description')
    icon = fields.Char(
        string='Icon',
        default='fa-trophy',
        help="FontAwesome icon class"
    )
    color = fields.Char(
        string='Color',
        default='#FFD700',
        help="Badge color in hex format"
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade'
    )
    earned_date = fields.Date(
        string='Earned Date',
        required=True,
        default=fields.Date.context_today
    )
    criteria_met = fields.Text(
        string='Criteria Met',
        help="Details of how the badge was earned"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='guard_id.company_id',
        store=True
    )

    @api.model
    def _cron_auto_award_badges(self):
        """Automatically award badges based on performance criteria."""
        _logger.info('Starting auto-badge award process...')
        
        guards = self.env['guard.profile'].search([('status', '=', 'active')])
        awarded_count = 0
        today = fields.Date.today()
        
        for guard in guards:
            # Check for Perfect Punctuality badge (no late arrivals in 3 months)
            three_months_ago = today - relativedelta(months=3)
            attendances = self.env['guard.attendance'].search([
                ('guard_id', '=', guard.id),
                ('checkin_time', '>=', three_months_ago),
            ])
            
            if len(attendances) >= 30:  # At least 30 shifts
                # Check if all were on time (within 5 min grace period)
                all_on_time = True
                for att in attendances:
                    if att.shift_id and att.shift_id.start_datetime:
                        delay = (att.checkin_time - att.shift_id.start_datetime).total_seconds() / 60
                        if delay > 5:
                            all_on_time = False
                            break
                
                if all_on_time:
                    # Check if badge already exists
                    existing = self.search([
                        ('guard_id', '=', guard.id),
                        ('badge_type', '=', 'punctuality'),
                        ('earned_date', '>=', three_months_ago),
                    ])
                    
                    if not existing:
                        self.create({
                            'name': _('Perfect Punctuality'),
                            'badge_type': 'punctuality',
                            'guard_id': guard.id,
                            'description': _('Perfect on-time record for 3 months'),
                            'icon': 'fa-clock-o',
                            'color': '#4CAF50',
                            'criteria_met': _('No late arrivals in the last 3 months (30+ shifts)'),
                        })
                        awarded_count += 1
            
            # Check for Perfect Attendance badge (no absences in 3 months)
            shifts = self.env['guard.shift'].search([
                ('guard_id', '=', guard.id),
                ('start_datetime', '>=', three_months_ago),
                ('start_datetime', '<=', today),
            ])
            
            if len(shifts) >= 30:
                missed_shifts = 0
                for shift in shifts:
                    attendance = self.env['guard.attendance'].search([
                        ('guard_id', '=', guard.id),
                        ('shift_id', '=', shift.id),
                    ], limit=1)
                    if not attendance:
                        missed_shifts += 1
                
                if missed_shifts == 0:
                    existing = self.search([
                        ('guard_id', '=', guard.id),
                        ('badge_type', '=', 'attendance'),
                        ('earned_date', '>=', three_months_ago),
                    ])
                    
                    if not existing:
                        self.create({
                            'name': _('Perfect Attendance'),
                            'badge_type': 'attendance',
                            'guard_id': guard.id,
                            'description': _('100% attendance for 3 months'),
                            'icon': 'fa-calendar-check-o',
                            'color': '#2196F3',
                            'criteria_met': _('No missed shifts in the last 3 months (30+ shifts)'),
                        })
                        awarded_count += 1
            
            # Check for Tour Master badge (100% tour completion for 1 month)
            one_month_ago = today - relativedelta(months=1)
            reviews = self.env['guard.performance.review'].search([
                ('guard_id', '=', guard.id),
                ('period_start', '>=', one_month_ago),
                ('state', '=', 'approved'),
                ('tour_completion_score', '=', 100.0),
            ])
            
            if reviews:
                existing = self.search([
                    ('guard_id', '=', guard.id),
                    ('badge_type', '=', 'tour_master'),
                    ('earned_date', '>=', one_month_ago),
                ])
                
                if not existing:
                    self.create({
                        'name': _('Tour Master'),
                        'badge_type': 'tour_master',
                        'guard_id': guard.id,
                        'description': _('100% tour completion rate'),
                        'icon': 'fa-map-marker',
                        'color': '#9C27B0',
                        'criteria_met': _('Completed 100% of assigned tours'),
                    })
                    awarded_count += 1
            
            # Check for Client Favorite badge (average rating 4.8+/5 for 3 months)
            feedbacks = self.env['client.feedback'].search([
                ('guard_id', '=', guard.id),
                ('feedback_date', '>=', three_months_ago),
            ])
            
            if len(feedbacks) >= 5:
                total_rating = sum(int(f.overall_rating) for f in feedbacks)
                avg_rating = total_rating / len(feedbacks)
                if avg_rating >= 4.8:  # 4.8+ out of 5
                    existing = self.search([
                        ('guard_id', '=', guard.id),
                        ('badge_type', '=', 'client_favorite'),
                        ('earned_date', '>=', three_months_ago),
                    ])
                    
                    if not existing:
                        self.create({
                            'name': _('Client Favorite'),
                            'badge_type': 'client_favorite',
                            'guard_id': guard.id,
                            'description': _('Outstanding client satisfaction'),
                            'icon': 'fa-thumbs-up',
                            'color': '#FF9800',
                            'criteria_met': _('Average rating of %.1f/5 over 3 months') % avg_rating,
                        })
                        awarded_count += 1
            
            # Check for Safety Champion badge (no incidents in 6 months)
            six_months_ago = today - relativedelta(months=6)
            incidents = self.env['incident.report'].search([
                ('guard_id', '=', guard.id),
                ('incident_datetime', '>=', six_months_ago),
                ('severity', 'in', ['medium', 'high', 'critical']),
            ])
            
            if not incidents and len(attendances) >= 60:  # At least 60 shifts
                existing = self.search([
                    ('guard_id', '=', guard.id),
                    ('badge_type', '=', 'safety_champion'),
                    ('earned_date', '>=', six_months_ago),
                ])
                
                if not existing:
                    self.create({
                        'name': _('Safety Champion'),
                        'badge_type': 'safety_champion',
                        'guard_id': guard.id,
                        'description': _('Incident-free record for 6 months'),
                        'icon': 'fa-shield',
                        'color': '#00BCD4',
                        'criteria_met': _('No medium/high/critical incidents in 6 months'),
                    })
                    awarded_count += 1
            
            # Check for Top Performer badge (90+ average score for 3 months)
            top_reviews = self.env['guard.performance.review'].search([
                ('guard_id', '=', guard.id),
                ('period_start', '>=', three_months_ago),
                ('state', '=', 'approved'),
                ('overall_score', '>=', 90.0),
            ])
            
            if len(top_reviews) >= 3:  # At least 3 months of 90+ scores
                existing = self.search([
                    ('guard_id', '=', guard.id),
                    ('badge_type', '=', 'top_performer'),
                    ('earned_date', '>=', three_months_ago),
                ])
                
                if not existing:
                    self.create({
                        'name': _('Top Performer'),
                        'badge_type': 'top_performer',
                        'guard_id': guard.id,
                        'description': _('Consistently excellent performance'),
                        'icon': 'fa-star',
                        'color': '#FFD700',
                        'criteria_met': _('90+ performance score for 3 consecutive months'),
                    })
                    awarded_count += 1
            
            # Check for Service Milestone badges
            if guard.employee_id and guard.employee_id.first_contract_date:
                service_years = (today - guard.employee_id.first_contract_date).days / 365.25
                
                milestone_badges = [
                    (1, 'milestone_1yr', '1 Year Service', 'fa-certificate', '#8BC34A'),
                    (3, 'milestone_3yr', '3 Years Service', 'fa-certificate', '#FFC107'),
                    (5, 'milestone_5yr', '5 Years Service', 'fa-certificate', '#FF5722'),
                    (10, 'milestone_10yr', '10 Years Service', 'fa-certificate', '#E91E63'),
                ]
                
                for years, badge_type, name, icon, color in milestone_badges:
                    if service_years >= years:
                        # Check if this milestone badge exists
                        existing = self.search([
                            ('guard_id', '=', guard.id),
                            ('badge_type', '=', badge_type),
                        ])
                        
                        if not existing:
                            self.create({
                                'name': _(name),
                                'badge_type': badge_type,
                                'guard_id': guard.id,
                                'description': _('Dedicated service for %d years') % years,
                                'icon': icon,
                                'color': color,
                                'criteria_met': _('Completed %d years of service') % years,
                            })
                            awarded_count += 1
        
        _logger.info('Auto-badge award complete. Awarded %d badges.', awarded_count)
        return True


