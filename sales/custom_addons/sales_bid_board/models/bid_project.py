from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Shared with bid.proposal.industry (reporting / filters must stay aligned).
BID_INDUSTRY_SELECTION = [
    ("agriculture_mining", "Agriculture and Mining"),
    ("aviation", "Aviation"),
    ("consulting_services", "Consulting Services"),
    ("defense_military", "Defense/Military"),
    ("energy", "Energy"),
    ("entertainment_events_media", "Entertainment/Events/Media"),
    ("facilities_management", "Facilities Management"),
    ("finance", "Finance"),
    ("food_beverage", "Food and Beverage"),
    ("government_public_admin", "Government and Public Administration"),
    ("healthcare_clinic", "Healthcare/Clinic"),
    ("hospitality_tourism_wellness", "Hospitality/Tourism/Wellness"),
    ("logistic_transportation", "Logistic/Transportation"),
    ("manufacturing", "Manufacturing"),
    ("nonprofit_social_education", "Nonprofit/Social Services/Education"),
    ("other", "Other"),
    ("pharma_biotech", "Pharmaceuticals and Biotech"),
    ("private_client", "Private Client"),
    ("real_estate_property", "Real Estate/Property Management"),
    ("retail_shopping_mall", "Retail - Shopping Mall"),
    ("retail_other", "Retail (excl. Shopping Mall)"),
    ("various_clients", "Various Clients"),
]


class BidProjectStage(models.Model):
    _name = "bid.project.stage"
    _description = "Bid Project Stage"
    _order = "sequence, id"

    name = fields.Char(
        required=True,
        help="Name of this pipeline stage (e.g. Qualification, Proposal). Shown on enquiries.",
    )
    sequence = fields.Integer(
        default=10,
        help="Order of stages in the pipeline: lower numbers appear first.",
    )
    fold = fields.Boolean(
        default=False,
        help="If enabled, this stage can be collapsed in Kanban-style views to reduce clutter.",
    )


class BidProject(models.Model):
    _name = "bid.project"
    _description = "Bid Project"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    # RFP reference: RFP-{seq}-{airport}-{year}; sequence is per (emirate key, calendar year).
    _RFP_EMIRATE_AIRPORT = {
        "abudhabi": "AUH",
        "dubai": "DXB",
        "sharjah": "SHJ",
        "ajman": "AJM",
        "rak": "RAK",
        "fujairah": "FUJ",
        "uaq": "UAQ",
    }

    # Standard Berkeley opportunity scorecard (Strategy / Customer / Commercial / Finance / Operation).
    # Applied when an enquiry has no scorecard lines (create, duplicate, manual action).
    _SCORECARD_TEMPLATE_ROWS = (
        # Strategy
        ("strategy", "Strategic importance", "Low", "Medium", "High"),
        (
            "strategy",
            "Domain of Berkeley's Activity(s)",
            "Outside Domain of Activity (< 40% Alignment)",
            "40% to 70% Alignment",
            "> 70% Alignment",
        ),
        (
            "strategy",
            "Potential for additional works / cross selling other services",
            "No Plans",
            "Limited plans / Potential to influence",
            "Plans in place / Looking of financing & investment",
        ),
        (
            "strategy",
            "Impact on business",
            "Small impact (< 1 Mi AED/Year)",
            "Medium impact (1 - 5 Mi AED/Year)",
            "High impact (> 5 Mi AED/Year)",
        ),
        # Customer
        (
            "customer",
            "Strategic customer",
            "Non-Strategic customer",
            "Important customer",
            "Strategic customer",
        ),
        (
            "customer",
            "Customer Size / Structure",
            "Small Company with very low visibility",
            "Medium Sized Company",
            "Large Company",
        ),
        (
            "customer",
            "Customer's development potential",
            "1-5 Projects",
            "5-10 Projects",
            "> 10 Projects",
        ),
        (
            "customer",
            "Customer's in-house experience",
            "Have an In-House Team",
            "Mix of In-house and Outsource",
            "Completely Outsource",
        ),
        (
            "customer",
            "Customer Portfolio",
            "Limited projects with bias to residential",
            "Medium to good range of portfolio",
            "High end client with premium portfolio",
        ),
        (
            "customer",
            "Contact Strength",
            "Highly competitive and open tender bid",
            "Invitation after pre-qualification",
            "Senior management contact within the client structure",
        ),
        ("customer", "Customer Track Record", "No wins", "Lost at final stage", "Existing client"),
        ("customer", "Maturity of relationship", "< 2 years", "2-5 years", "> 5 years"),
        ("customer", "Quality of relationship", "Normal", "Good", "Excellent"),
        # Commercial
        ("commercial", "Term of contract", "< 2 years", "2 - 3 years", "> 3 years"),
        (
            "commercial",
            "Size of Contract (AED/Year)",
            "< 1 Mi AED",
            "1 - 5 Mi AED",
            "> 5 Mi AED",
        ),
        ("commercial", "Business model", "OSS", "Bundled Services", "IFM"),
        (
            "commercial",
            "RFP Documents",
            "Insufficient Details Provided",
            "Partial Details Provided",
            "Detailed SOW Provided",
        ),
        (
            "commercial",
            "Competitive Landscape",
            "Public Tender > 5 Competitors",
            "< 5 Competitors",
            "Preferred Bidder (1-1 Competitors)",
        ),
        (
            "commercial",
            "Submission schedule",
            "Tight schedule (1-2 weeks)",
            "Suitable schedule (3-4 weeks)",
            "Sufficient time (> 4 weeks)",
        ),
        (
            "commercial",
            "Estimated additional work",
            "< 5% contract revenue",
            "5%-10% contract revenue",
            "> 10% contract revenue",
        ),
        ("commercial", "Competitive advantage", "No advantage", "Equal", "High"),
        ("commercial", "Similar references", "None", "Comparable reference", "Identical and accessible"),
        (
            "commercial",
            "Contractual arrangements",
            "Customer contract without negotiation",
            "Customer contract with negotiation",
            "Berkeley contract",
        ),
        # Finance
        ("finance", "Estimated GM", "< 10%", "10%-12%", "> 12%"),
        ("finance", "Payment Terms", "> 60 days", "30 - 60 days", "30 days"),
        ("finance", "Price risk", "High risk", "Medium risk", "Low risk"),
        (
            "finance",
            "Tender Bond as %ge of Annual Contract Value",
            "> 10%",
            "5 to 10%",
            "0 to 5%",
        ),
        (
            "finance",
            "Performance Bond",
            "5 - 10% of the annual contractual value",
            "< 5% of the annual contractual value",
            "No Performance Bond",
        ),
        (
            "finance",
            "Penalties",
            "> 5% of the annual contractual value",
            "< 5% of the annual contractual value",
            "No Penalty",
        ),
        (
            "finance",
            "Liability of the company",
            "Liability uncapped",
            "Liability capped up to the contract value",
            "Liability capped up to a % of contract value",
        ),
        (
            "finance",
            "Estimated initial investment (Capex)",
            "> 0.5 Mi AED",
            "0.5 Mi - 100K AED",
            "< 100 K AED",
        ),
        # Operation
        (
            "operations",
            "Condition of facilities at start of contract",
            "Average age > 10 years",
            "Average age < 10 years",
            "New or refurbished",
        ),
        (
            "operations",
            "Operational coverage",
            "Support Teams 60-90 minutes away",
            "Support Teams 30-60 minutes away",
            "Support Teams < 30 minutes away",
        ),
        ("operations", "Mobilisation Period", "< 4 weeks", "4 - 8 weeks", "> 8 weeks"),
        ("operations", "Risk of transferring our know-how", "High", "Average", "Limited"),
        (
            "operations",
            "Experience in this field of operation & technology",
            "Tenders submitted for similar projects",
            "Few similar contracts operated",
            "Numerous similar contracts operated",
        ),
    )

    name = fields.Char(
        string="Project Name",
        required=True,
        tracking=True,
        help="Descriptive name of the opportunity or tender (e.g. project or RFP title).",
    )
    code = fields.Char(
        required=True,
        copy=False,
        default="New",
        tracking=True,
        help="Unique reference assigned on create: RFP-NNN-XXX-YYYY (counter per emirate "
        "and calendar year; XXX is AUH, DXB, SHJ, AJM, UAQ, RAK, or FUJ).",
    )
    client_name = fields.Char(
        required=True,
        tracking=True,
        help="Client or organisation issuing or receiving the bid.",
    )
    sales_rep = fields.Many2one(
        "res.users",
        tracking=True,
        default=lambda self: self.env.user,
        help="Salesperson accountable for the opportunity and customer contact.",
    )
    project_lead_id = fields.Many2one(
        "res.users",
        tracking=True,
        default=lambda self: self.env.user,
        help="Internal owner coordinating the bid preparation and submission.",
    )
    team_member_ids = fields.Many2many(
        "bid.team.member",
        "bid_project_bid_team_member_rel",
        "bid_project_id",
        "bid_team_member_id",
        string="Team Members",
        help="Bid team members (from the configured team list) working on this enquiry.",
    )
    emirate = fields.Selection(
        [
            ("abudhabi", "Abu Dhabi"),
            ("dubai", "Dubai"),
            ("sharjah", "Sharjah"),
            ("ajman", "Ajman"),
            ("rak", "Ras Al Khaimah"),
            ("fujairah", "Fujairah"),
            ("uaq", "Umm Al Quwain"),
        ],
        required=True,
        default="dubai",
        tracking=True,
        help="Emirate where the site or client is primarily located.",
    )
    industry = fields.Selection(
        BID_INDUSTRY_SELECTION,
        required=True,
        default="real_estate_property",
        tracking=True,
        help="Industry sector of the client or asset (reporting and filtering).",
    )
    sector = fields.Selection(
        [
            ("private", "Private"),
            ("semi_public", "Semi-Public"),
            ("public", "Public"),
        ],
        tracking=True,
        help="Client / contract sector classification.",
    )
    contract_duration = fields.Selection(
        [
            ("1y", "1 Year"),
            ("2y", "2 Years"),
            ("3y", "3 Years"),
            ("4y", "4 Years"),
            ("5y", "5 Years"),
            ("6y", "6 Years"),
        ],
        required=True,
        default="1y",
        tracking=True,
        help="Expected contract length (years) used in scoring, planning, and proposals.",
    )
    contract_value = fields.Float(
        required=True,
        default=0.0,
        tracking=True,
        help="Estimated total contract value (use your standard currency, e.g. AED).",
    )
    deadline_date = fields.Date(
        compute="_compute_deadline_date",
        store=True,
        help="Date part of the submission deadline (derived from Deadline Datetime).",
    )
    deadline_datetime = fields.Datetime(
        tracking=True,
        help="Full submission deadline including time, for reminders and governance.",
    )
    bid_calendar_start = fields.Datetime(
        string="Calendar date",
        compute="_compute_bid_calendar_display",
        store=True,
        help="Deadline (or created on if no deadline) for calendar views.",
    )
    bid_calendar_color = fields.Integer(
        string="Calendar color",
        compute="_compute_bid_calendar_display",
        store=True,
        help="Color index: 1 overdue, 2 due ≤7d, 3 due ≤30d, 4 later, 11 closed review, 0 no anchor.",
    )
    rfp_received_date = fields.Date(
        string="RFP Received Date",
        tracking=True,
        help="Date the RFP or tender documentation was received.",
    )
    site_visit_date = fields.Date(
        string="Site Visit Date",
        tracking=True,
        help="Date of site visit or walkdown, if applicable.",
    )
    project_structure = fields.Selection(
        [
            ("single_facility", "Single Facility"),
            ("multi_facility_single_location", "Multiple Facilities-Single Location"),
            ("multi_facility_multi_location", "Multiple Facilities-Multiple Locations"),
        ],
        tracking=True,
        help="How facilities are distributed for this opportunity.",
    )
    age_of_facility = fields.Char(
        string="Age of Facility",
        tracking=True,
        help="Describe facility age or vintage (e.g. years since build or last major refurb).",
    )
    assets_list_provided = fields.Selection(
        [
            ("yes", "Yes"),
            ("partial", "Partially Provided"),
            ("no", "No"),
        ],
        string="Assets List Provided",
        tracking=True,
        help="Whether the RFP includes a full asset register or BOQ.",
    )
    spare_consumables = fields.Selection(
        [
            ("na", "N/A"),
            ("cost_plus", "Cost Plus"),
            ("threshold_remarks", "Threshold (specify in remarks)"),
            ("comprehensive", "Comprehensive"),
        ],
        string="Spare/Consumables",
        tracking=True,
    )
    subcontractors = fields.Selection(
        [
            ("na", "N/A"),
            ("cost_plus", "Cost Plus"),
            ("threshold_remarks", "Threshold (specify in remarks)"),
            ("comprehensive", "Comprehensive"),
        ],
        tracking=True,
    )
    input_output_based = fields.Selection(
        [
            ("input_based", "Input Based"),
            ("output_based", "Output Based"),
        ],
        string="Input/Output Based",
        tracking=True,
    )
    contract_type = fields.Selection(
        [("ifm", "IFM"), ("bundled", "Bundled Services"), ("single", "Single Service")],
        required=True,
        default="ifm",
        tracking=True,
        help="Contract shape: IFM (integrated), bundled services, or single service line.",
    )
    threshold = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        required=True,
        default="medium",
        tracking=True,
        help="Internal priority or materiality band for management attention.",
    )
    tender_bond = fields.Selection(
        [
            ("required_remarks", "Required (Specify in Remarks)"),
            ("not_required", "Not Required"),
        ],
        required=True,
        default="not_required",
        tracking=True,
        help="Whether a tender / bid bond is required; add details in project remarks if applicable.",
    )
    performance_bond = fields.Selection(
        [
            ("required_remarks", "Required (Specify in Remarks)"),
            ("not_required", "Not Required"),
        ],
        required=True,
        default="not_required",
        tracking=True,
        help="Whether a performance bond is required after award; add details in remarks if applicable.",
    )
    kpi = fields.Selection(
        [("yes", "Yes"), ("partial", "Partial"), ("no", "No")],
        required=False,
        default="no",
        tracking=True,
        help="Legacy KPI presence flag (optional). Use KPI and Penalty Mechanism for narrative detail.",
    )
    kpi_penalty_mechanism = fields.Text(
        string="KPI and Penalty Mechanism",
        tracking=True,
        help="Describe KPIs, penalties, and maximum penalty exposure (caps) as stated in the RFP.",
    )
    scope_cleaning = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to cleaning (use % so all scope lines sum to 100).",
    )
    scope_maintenance = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to maintenance (%).",
    )
    scope_security = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to security (%).",
    )
    scope_landscaping = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to landscaping (%).",
    )
    scope_laundry = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to laundry (%).",
    )
    scope_support = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to support services (%).",
    )
    scope_others = fields.Float(
        default=0.0,
        help="Share of scope or fee for any other service lines (%).",
    )
    scope_total = fields.Float(
        compute="_compute_scope_total",
        store=True,
        help="Automatic sum of all scope percentage lines (should typically equal 100%).",
    )
    progress = fields.Text(
        tracking=True,
        help="Free-text notes on bid preparation status (e.g. percent complete, milestones, blockers).",
    )
    stage_id = fields.Many2one(
        "bid.project.stage",
        required=True,
        tracking=True,
        default=lambda self: self.env["bid.project.stage"].search([], order="sequence", limit=1),
        help="Current stage in your internal bid pipeline.",
    )
    description = fields.Text(
        help="Free-text notes: scope summary, risks, links, or anything the team should know.",
    )
    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="Source Lead",
        tracking=True,
        copy=False,
        ondelete="set null",
        index=True,
        help="CRM lead this enquiry was created from, if any.",
    )
    criteria_line_ids = fields.One2many(
        "bid.project.criteria",
        "project_id",
        string="Scorecard",
        help="Bid / no-bid scorecard lines. Scores drive the overall % and CSO recommendation.",
    )

    score_strategy = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Weighted score for the Strategy category (computed from scorecard).",
    )
    score_customer = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Weighted score for the Customer category.",
    )
    score_commercial = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Weighted score for the Commercial category.",
    )
    score_finance = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Weighted score for the Finance category.",
    )
    score_operations = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Weighted score for the Operations category.",
    )
    score_overall = fields.Float(
        compute="_compute_scores",
        store=True,
        tracking=True,
        help="Overall scorecard percentage (average of category scores). Feeds Bid vs No Bid recommendation.",
    )

    decision_final = fields.Selection(
        [("bid", "Bid"), ("no_bid", "No Bid")],
        compute="_compute_decisions",
        store=True,
        tracking=True,
        help="System recommendation from the score: Bid if overall score meets the threshold, otherwise No Bid.",
    )
    review_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_review", "Pending Review"),
            ("approved", "Approved"),
            ("declined", "Declined"),
            ("change_requested", "Change Requested"),
        ],
        default="draft",
        tracking=True,
        help="CSO workflow: Draft, pending review, approved, declined, or changes requested.",
    )
    recommendation_text = fields.Char(
        compute="_compute_decisions",
        store=True,
        help="Short label for the recommended decision (Bid / No Bid wording).",
    )
    recommendation_note = fields.Char(
        compute="_compute_decisions",
        store=True,
        help="One-line explanation shown with the recommendation.",
    )

    submission_ids = fields.One2many(
        "bid.submission",
        "project_id",
        help="History of submissions to CSO review for this enquiry.",
    )
    notification_ids = fields.One2many(
        "bid.notification",
        "project_id",
        help="Scheduled deadline reminders linked to this enquiry.",
    )
    change_request_ids = fields.One2many(
        "bid.change.request",
        "project_id",
        help="CSO change requests that must be resolved before re-submission.",
    )
    proposal_ids = fields.One2many(
        "bid.proposal",
        "project_id",
        string="Proposals",
        help="Formal proposals created after a Bid approval (see Proposals menu).",
    )
    proposal_count = fields.Integer(
        compute="_compute_proposal_count",
        store=True,
        help="Number of proposal records linked to this enquiry.",
    )
    reviewed_by_id = fields.Many2one(
        "res.users",
        tracking=True,
        help="CSO (or delegate) who last completed an approval, decline, or change request action.",
    )
    reviewed_on = fields.Datetime(
        tracking=True,
        help="Timestamp of that last CSO review action.",
    )
    cso_decline_justification = fields.Text(
        tracking=True,
        copy=False,
        help="Explanation recorded when CSO declines the enquiry at review.",
    )
    can_cso_review = fields.Boolean(
        compute="_compute_ui_permissions",
        help="True when the current user is allowed to approve, decline, or request changes (CSO role).",
    )
    can_non_cso_actions = fields.Boolean(
        compute="_compute_ui_permissions",
        help="True when draft-style actions (e.g. save draft) are available for this enquiry and user.",
    )
    can_submit_for_review = fields.Boolean(
        compute="_compute_ui_permissions",
        help="True when the score meets the minimum required to submit for CSO review.",
    )
    can_show_submit_review_button = fields.Boolean(
        compute="_compute_ui_permissions",
        help="True when the Submit for Review button should be visible (may still show even if score is low).",
    )

    def _bid_board_ensure_rfp_sequence(self, emirate_key: str, year: int) -> str:
        """Return ir.sequence code for this emirate + year; create sequence row if missing."""
        seq_code = f"bid.project.rfp.{emirate_key}.{year}"
        Seq = self.env["ir.sequence"].sudo()
        if Seq.search([("code", "=", seq_code)], limit=1):
            return seq_code
        try:
            with self.env.cr.savepoint():
                Seq.create(
                    {
                        "name": f"RFP references ({emirate_key}, {year})",
                        "code": seq_code,
                        "implementation": "standard",
                        "padding": 3,
                        "number_next": 1,
                        "number_increment": 1,
                        "company_id": False,
                    }
                )
        except IntegrityError:
            if not Seq.search([("code", "=", seq_code)], limit=1):
                raise
        return seq_code

    def _bid_board_next_rfp_code(self, vals: dict) -> str:
        emirate_key = vals.get("emirate") or "dubai"
        airport = self._RFP_EMIRATE_AIRPORT.get(emirate_key)
        if not airport:
            raise ValidationError(
                _("Unsupported emirate %r for RFP numbering. Contact your administrator.")
                % (emirate_key,)
            )
        year = fields.Date.context_today(self).year
        seq_code = self._bid_board_ensure_rfp_sequence(emirate_key, year)
        next_num = self.env["ir.sequence"].sudo().next_by_code(seq_code)
        if not next_num:
            raise ValidationError(
                _("Could not allocate RFP sequence for emirate %s and year %s.")
                % (emirate_key, year)
            )
        return f"RFP-{next_num}-{airport}-{year}"

    def _bid_board_should_assign_rfp_code(self, vals):
        """True when the web client / API did not supply a real code (only placeholder or empty)."""
        if "code" not in vals:
            return True
        code = vals["code"]
        if code in (False, None):
            return True
        if not isinstance(code, str):
            return False
        s = code.strip()
        return not s or s.lower() == "new"

    @api.model
    def _default_scorecard_line_commands(self):
        """(0, 0, vals) x-2-m commands for the standard scorecard (new form + post-create)."""
        return [
            (
                0,
                0,
                {
                    "category": category,
                    "name": name,
                    "option_1_text": option_1,
                    "option_2_text": option_2,
                    "option_3_text": option_3,
                    "score": "3",
                    "weight": 1.0,
                },
            )
            for category, name, option_1, option_2, option_3 in self._SCORECARD_TEMPLATE_ROWS
        ]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if fields_list is not None and "criteria_line_ids" not in fields_list:
            return res
        if "default_criteria_line_ids" in self.env.context:
            return res
        if res.get("criteria_line_ids"):
            return res
        res["criteria_line_ids"] = self._default_scorecard_line_commands()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._bid_board_should_assign_rfp_code(vals):
                vals["code"] = self._bid_board_next_rfp_code(vals)
        records = super().create(vals_list)
        records._ensure_default_scorecard()
        return records

    def write(self, vals):
        for project in self:
            if project._bid_board_locked_for_record_edit() and not project._can_bypass_approved_project_lock():
                raise ValidationError(
                    _(
                        "This enquiry is locked while it is pending CSO review, or after CSO approval or decline. "
                        "Only CSO approvers, Bid Board managers, or administrators can change it."
                    )
                )
        return super().write(vals)

    def unlink(self):
        for project in self:
            if project._bid_board_locked_for_record_edit() and not project._can_bypass_approved_project_lock():
                raise ValidationError(
                    _(
                        "This enquiry is locked while it is pending CSO review, or after CSO approval or decline. "
                        "Only CSO approvers, Bid Board managers, or administrators can delete it."
                    )
                )
        return super().unlink()

    def copy(self, default=None):
        """Duplicate starts as a new draft enquiry, not an approved clone."""
        default = dict(default or {})
        if "review_status" not in default:
            default["review_status"] = "draft"
        if "reviewed_by_id" not in default:
            default["reviewed_by_id"] = False
        if "reviewed_on" not in default:
            default["reviewed_on"] = False
        if "outcome_status" not in default:
            default["outcome_status"] = "open"
        if "is_priority" not in default:
            default["is_priority"] = False
        # Do not clone CSO workflow history or reminder rows
        if "submission_ids" not in default:
            default["submission_ids"] = []
        if "notification_ids" not in default:
            default["notification_ids"] = []
        if "change_request_ids" not in default:
            default["change_request_ids"] = []
        if "proposal_ids" not in default:
            default["proposal_ids"] = []
        copied = super().copy(default)
        copied._ensure_default_scorecard()
        return copied

    @api.depends("deadline_datetime")
    def _compute_deadline_date(self):
        for rec in self:
            rec.deadline_date = (
                fields.Date.to_date(rec.deadline_datetime) if rec.deadline_datetime else False
            )

    @api.depends(
        "deadline_datetime",
        "create_date",
        "review_status",
    )
    def _compute_bid_calendar_display(self):
        """Calendar anchor + urgency color (Odoo calendar color index 0–11)."""
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.deadline_datetime:
                start = rec.deadline_datetime
                anchor_date = fields.Datetime.to_date(rec.deadline_datetime)
            elif rec.create_date:
                start = rec.create_date
                anchor_date = fields.Date.to_date(rec.create_date)
            else:
                rec.bid_calendar_start = False
                rec.bid_calendar_color = 0
                continue
            rec.bid_calendar_start = start
            if rec.review_status in ("approved", "declined"):
                rec.bid_calendar_color = 11
            elif anchor_date < today:
                rec.bid_calendar_color = 1
            elif anchor_date <= today + timedelta(days=7):
                rec.bid_calendar_color = 2
            elif anchor_date <= today + timedelta(days=30):
                rec.bid_calendar_color = 3
            else:
                rec.bid_calendar_color = 4

    @api.depends("proposal_ids")
    def _compute_proposal_count(self):
        for project in self:
            project.proposal_count = len(project.proposal_ids)

    @api.depends(
        "scope_cleaning",
        "scope_maintenance",
        "scope_security",
        "scope_landscaping",
        "scope_laundry",
        "scope_support",
        "scope_others",
    )
    def _compute_scope_total(self):
        for project in self:
            project.scope_total = (
                project.scope_cleaning
                + project.scope_maintenance
                + project.scope_security
                + project.scope_landscaping
                + project.scope_laundry
                + project.scope_support
                + project.scope_others
            )


    @api.constrains(
        "scope_cleaning",
        "scope_maintenance",
        "scope_security",
        "scope_landscaping",
        "scope_laundry",
        "scope_support",
        "scope_others",
    )
    def _check_scope_total(self):
        for project in self:
            if project.scope_total > 100.0:
                raise ValidationError("Scope of Work total cannot exceed 100%.")


    def _get_submit_review_min_score(self):
        return self.env["bid.board.settings"].get_submit_review_min_score()
