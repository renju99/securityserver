import json
import re
import time
from html import unescape
from xml.etree import ElementTree as ET
from urllib import error, request
from urllib.parse import quote_plus, urlparse

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class BidBoardSettingsMarketAnalysis(models.Model):
    _inherit = "bid.board.settings"

    _MARKET_ANALYSIS_ENABLED_KEY = "sales_bid_board.market_analysis_enabled"
    _MARKET_ANALYSIS_PROVIDER_KEY = "sales_bid_board.market_analysis_provider"
    _MARKET_ANALYSIS_MODEL_KEY = "sales_bid_board.market_analysis_model"
    _MARKET_ANALYSIS_API_KEY = "sales_bid_board.market_analysis_api_key"
    _MARKET_ANALYSIS_TIMEOUT_KEY = "sales_bid_board.market_analysis_timeout_seconds"
    _MARKET_ANALYSIS_PROMPT_VERSION_KEY = "sales_bid_board.market_analysis_prompt_version"
    _MARKET_ANALYSIS_PROMPT_TEMPLATE_KEY = "sales_bid_board.market_analysis_prompt_template"
    _EXTERNAL_MARKET_ENABLED_KEY = "sales_bid_board.external_market_enabled"
    _EXTERNAL_MARKET_PROVIDER_KEY = "sales_bid_board.external_market_provider"
    _EXTERNAL_MARKET_GEMINI_DIRECT_KEY = "sales_bid_board.external_market_gemini_direct"
    _EXTERNAL_MARKET_API_KEY = "sales_bid_board.external_market_api_key"
    _EXTERNAL_MARKET_NEWS_LIMIT_KEY = "sales_bid_board.external_market_news_limit"
    _EXTERNAL_MARKET_TIMEOUT_KEY = "sales_bid_board.external_market_timeout_seconds"

    market_analysis_enabled = fields.Boolean(
        string="Enable AI market analysis",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="Enable manual AI market analysis generation on bid/project records.",
    )
    market_analysis_provider = fields.Selection(
        [("openrouter", "OpenRouter")],
        string="AI provider",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="Provider used for market analysis requests.",
    )
    market_analysis_model = fields.Char(
        string="Model name",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="Configured AI model identifier, for example openai/gpt-oss-120b:free.",
    )
    market_analysis_api_key = fields.Char(
        string="API key",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="API key used for the external AI provider.",
    )
    market_analysis_timeout_seconds = fields.Integer(
        string="Request timeout (seconds)",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="HTTP timeout for AI market analysis requests.",
    )
    market_analysis_prompt_version = fields.Char(
        string="Prompt version",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="Version label for the active market analysis prompt contract.",
    )
    market_analysis_prompt_template = fields.Text(
        string="Prompt template override",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="Optional override for the default system prompt used by market analysis.",
    )
    external_market_enabled = fields.Boolean(
        string="Enable external market data",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="When enabled, refreshes the external / strategic intelligence block on the project before "
        "combined analysis. Use “Gemini only” to skip search APIs.",
    )
    external_market_gemini_direct = fields.Boolean(
        string="Gemini only (no web search)",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="When enabled, strategic intelligence is generated with Google Gemini using only this bid record "
        "(and optional client website as text). No Serper, Google Search API, or RSS calls.",
    )
    external_market_provider = fields.Selection(
        [
            ("google_search_api", "Google Search API"),
            ("google_news_rss", "Google News RSS"),
        ],
        string="External provider",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="Used only when “Gemini only” is off: choose Serper/Google Search API or Google News RSS.",
    )
    external_market_api_key = fields.Char(
        string="External API key",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="API key for Google Search API / Serper when that external provider is selected. "
        "Not used for Gemini (direct).",
    )
    external_market_news_limit = fields.Integer(
        string="External results limit",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="Maximum news items to keep per fetch.",
    )
    external_market_timeout_seconds = fields.Integer(
        string="External fetch timeout (seconds)",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_settings",
        readonly=False,
        help="HTTP timeout for external market data fetch.",
    )

    def _compute_market_analysis_settings(self):
        for rec in self:
            rec.market_analysis_enabled = rec.get_market_analysis_enabled()
            rec.market_analysis_provider = rec.get_market_analysis_provider()
            rec.market_analysis_model = rec.get_market_analysis_model()
            rec.market_analysis_api_key = rec.get_market_analysis_api_key()
            rec.market_analysis_timeout_seconds = rec.get_market_analysis_timeout_seconds()
            rec.market_analysis_prompt_version = rec.get_market_analysis_prompt_version()
            rec.market_analysis_prompt_template = rec.get_market_analysis_prompt_template()
            rec.external_market_enabled = rec.get_external_market_enabled()
            rec.external_market_gemini_direct = rec.get_external_market_gemini_direct()
            rec.external_market_provider = rec.get_external_market_provider()
            rec.external_market_api_key = rec.get_external_market_api_key()
            rec.external_market_news_limit = rec.get_external_market_news_limit()
            rec.external_market_timeout_seconds = rec.get_external_market_timeout_seconds()

    def _inverse_market_analysis_settings(self):
        for rec in self:
            rec.set_market_analysis_enabled(bool(rec.market_analysis_enabled))
            rec.set_market_analysis_provider(
                (rec.market_analysis_provider or rec.get_market_analysis_provider())
            )
            rec.set_market_analysis_model(
                (rec.market_analysis_model or rec.get_market_analysis_model())
            )
            incoming_api_key = (rec.market_analysis_api_key or "").strip()
            if incoming_api_key:
                rec.set_market_analysis_api_key(incoming_api_key)
            rec.set_market_analysis_timeout_seconds(rec.market_analysis_timeout_seconds)
            rec.set_market_analysis_prompt_version(
                (rec.market_analysis_prompt_version or rec.get_market_analysis_prompt_version())
            )
            incoming_prompt_template = rec.market_analysis_prompt_template
            if incoming_prompt_template not in (False, None, ""):
                rec.set_market_analysis_prompt_template(incoming_prompt_template)

            rec.set_external_market_enabled(bool(rec.external_market_enabled))
            rec.set_external_market_gemini_direct(bool(rec.external_market_gemini_direct))
            rec.set_external_market_provider(
                (rec.external_market_provider or rec.get_external_market_provider())
            )
            incoming_external_api_key = (rec.external_market_api_key or "").strip()
            if incoming_external_api_key:
                rec.set_external_market_api_key(incoming_external_api_key)
            rec.set_external_market_news_limit(rec.external_market_news_limit)
            rec.set_external_market_timeout_seconds(rec.external_market_timeout_seconds)

    @api.model
    def get_market_analysis_enabled(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._MARKET_ANALYSIS_ENABLED_KEY, default="False")
        )
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    @api.model
    def set_market_analysis_enabled(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            self._MARKET_ANALYSIS_ENABLED_KEY, "True" if bool(value) else "False"
        )

    @api.model
    def get_market_analysis_provider(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._MARKET_ANALYSIS_PROVIDER_KEY, default="openrouter")
        )
        value = (raw or "").strip().lower()
        if value != "openrouter":
            return "openrouter"
        return value

    @api.model
    def set_market_analysis_provider(self, value):
        provider = (value or "openrouter").strip().lower()
        if provider != "openrouter":
            raise ValidationError(_("Only OpenRouter is supported for AI market analysis right now."))
        self.env["ir.config_parameter"].sudo().set_param(self._MARKET_ANALYSIS_PROVIDER_KEY, provider)

    @api.model
    def get_market_analysis_model(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                self._MARKET_ANALYSIS_MODEL_KEY, default="openai/gpt-oss-120b:free"
            )
        )
        value = (raw or "").strip()
        if not value:
            return "openai/gpt-oss-120b:free"
        return value

    @api.model
    def set_market_analysis_model(self, value):
        current = self.get_market_analysis_model()
        model_name = (value or "").strip() or current or "openai/gpt-oss-120b:free"
        self.env["ir.config_parameter"].sudo().set_param(self._MARKET_ANALYSIS_MODEL_KEY, model_name)

    @api.model
    def get_market_analysis_api_key(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._MARKET_ANALYSIS_API_KEY, default="")
        ) or ""

    @api.model
    def set_market_analysis_api_key(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            self._MARKET_ANALYSIS_API_KEY, (value or "").strip()
        )

    @api.model
    def get_market_analysis_timeout_seconds(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._MARKET_ANALYSIS_TIMEOUT_KEY, default="45")
        )
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = 45
        return max(10, min(180, value))

    @api.model
    def set_market_analysis_timeout_seconds(self, value):
        raw = str(value or "").strip().replace(",", ".")
        try:
            parsed = float(raw) if raw else float(self.get_market_analysis_timeout_seconds())
            timeout_seconds = int(parsed)
        except (TypeError, ValueError):
            timeout_seconds = self.get_market_analysis_timeout_seconds()
        timeout_seconds = max(10, min(180, timeout_seconds))
        self.env["ir.config_parameter"].sudo().set_param(
            self._MARKET_ANALYSIS_TIMEOUT_KEY, str(timeout_seconds)
        )

    @api.model
    def get_market_analysis_prompt_version(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._MARKET_ANALYSIS_PROMPT_VERSION_KEY, default="v1")
        )
        return (raw or "").strip() or "v1"

    @api.model
    def set_market_analysis_prompt_version(self, value):
        version = (value or "").strip() or self.get_market_analysis_prompt_version() or "v1"
        self.env["ir.config_parameter"].sudo().set_param(
            self._MARKET_ANALYSIS_PROMPT_VERSION_KEY, version
        )

    @api.model
    def get_market_analysis_prompt_template(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._MARKET_ANALYSIS_PROMPT_TEMPLATE_KEY, default="")
        )
        return (raw or "").strip()

    @api.model
    def set_market_analysis_prompt_template(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            self._MARKET_ANALYSIS_PROMPT_TEMPLATE_KEY, (value or "").strip()
        )

    @api.model
    def get_external_market_enabled(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._EXTERNAL_MARKET_ENABLED_KEY, default="False")
        )
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    @api.model
    def set_external_market_enabled(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            self._EXTERNAL_MARKET_ENABLED_KEY, "True" if bool(value) else "False"
        )

    @api.model
    def get_external_market_gemini_direct(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._EXTERNAL_MARKET_GEMINI_DIRECT_KEY, default="False")
        )
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    @api.model
    def set_external_market_gemini_direct(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            self._EXTERNAL_MARKET_GEMINI_DIRECT_KEY, "True" if bool(value) else "False"
        )

    @api.model
    def get_external_market_provider(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._EXTERNAL_MARKET_PROVIDER_KEY, default="google_search_api")
        )
        provider = (raw or "").strip().lower()
        if provider == "gemini_direct":
            return "google_search_api"
        if provider in ("google_search_api", "google_news_rss"):
            return provider
        return "google_search_api"

    @api.model
    def set_external_market_provider(self, value):
        provider = (value or "google_search_api").strip().lower()
        if provider == "gemini_direct":
            self.set_external_market_gemini_direct(True)
            provider = "google_search_api"
        if provider not in ("google_search_api", "google_news_rss"):
            raise ValidationError(_("Unsupported external market provider."))
        self.env["ir.config_parameter"].sudo().set_param(self._EXTERNAL_MARKET_PROVIDER_KEY, provider)

    @api.model
    def get_external_market_api_key(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._EXTERNAL_MARKET_API_KEY, default="")
        ) or ""

    @api.model
    def set_external_market_api_key(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            self._EXTERNAL_MARKET_API_KEY, (value or "").strip()
        )

    @api.model
    def get_external_market_news_limit(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._EXTERNAL_MARKET_NEWS_LIMIT_KEY, default="10")
        )
        try:
            limit = int(raw)
        except (TypeError, ValueError):
            limit = 10
        return max(3, min(25, limit))

    @api.model
    def set_external_market_news_limit(self, value):
        try:
            limit = int(float(value or 0))
        except (TypeError, ValueError):
            limit = 10
        limit = max(3, min(25, limit))
        self.env["ir.config_parameter"].sudo().set_param(self._EXTERNAL_MARKET_NEWS_LIMIT_KEY, str(limit))

    @api.model
    def get_external_market_timeout_seconds(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._EXTERNAL_MARKET_TIMEOUT_KEY, default="20")
        )
        try:
            timeout = int(raw)
        except (TypeError, ValueError):
            timeout = 20
        return max(10, min(120, timeout))

    @api.model
    def set_external_market_timeout_seconds(self, value):
        try:
            timeout = int(float(value or 0))
        except (TypeError, ValueError):
            timeout = 20
        timeout = max(10, min(120, timeout))
        self.env["ir.config_parameter"].sudo().set_param(self._EXTERNAL_MARKET_TIMEOUT_KEY, str(timeout))


class BidMarketAnalysisService(models.AbstractModel):
    _name = "bid.market.analysis.service"
    _description = "Bid Market Analysis Service"

    _OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    _CLIENT_STOPWORDS = {
        "llc",
        "l.l.c",
        "ltd",
        "limited",
        "services",
        "service",
        "group",
        "company",
        "co",
        "uae",
        "the",
        "and",
    }
    _LOW_QUALITY_HINTS = {
        "linkedin",
        "linkedin.com",
        "linkedin.com/jobs",
        "linkedin.com/posts",
        "linkedin.",
        "youtube.com",
        "youtu.be",
        "youtube",
        "facebook.com",
        "instagram.com",
        "tiktok.com",
        "j360",
        "job",
        "careers",
        "vacancy",
    }
    _HIGH_QUALITY_HINTS = {
        "knowledge graph",
        "official website",
        "reuters.com",
        "zawya.com",
        "jll.com",
        "meed.com",
        "gov.ae",
        "dubai.gov.ae",
        "etenders",
        "tender",
    }
    _CLIENT_PAGE_HINTS = {
        "about": 2,
        "services": 2,
        "service": 1,
        "projects": 3,
        "project": 2,
        "clients": 3,
        "client": 1,
        "case study": 3,
        "case studies": 3,
        "award": 2,
        "awards": 2,
        "news": 1,
        "profile": 1,
    }

    def _provider_display_name(self, provider_code):
        return {
            "gemini_direct": _("Google Gemini (direct)"),
            "google_search_api": _("Google Search API"),
            "google_news_rss": _("Google News RSS"),
            "openrouter": _("OpenRouter"),
        }.get(provider_code, provider_code or "")

    def _item_text(self, item):
        return " ".join(
            [
                (item.get("title") or "").lower(),
                (item.get("source") or "").lower(),
                (item.get("link") or "").lower(),
                (item.get("snippet") or "").lower(),
            ]
        )

    def _source_from_url(self, url):
        domain = urlparse(url or "").netloc.lower()
        if not domain:
            return ""
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _normalized_client_domain(self, project):
        website = (project.client_website or "").strip()
        if not website:
            return ""
        if "://" not in website:
            website = f"https://{website}"
        return self._source_from_url(website)

    def _system_prompt(self):
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        template_override = settings.get_market_analysis_prompt_template()
        if template_override:
            return template_override
        return (
            "You are an enterprise bid market-analysis assistant. "
            "You must analyze only the internal project fields that are provided to you. "
            "Do not use external market facts, web research, or assumptions presented as facts. "
            "If information is missing, list it explicitly in missing_information. "
            "Return strict JSON with exactly these keys: "
            "summary, opportunity_signals, risk_signals, competition_view, pricing_pressure_view, "
            "bid_recommendation_support, missing_information, confidence_level, disclaimer. "
            "Use concise business language. "
            "Always anchor the analysis to the exact client_name provided in input. "
            "If client_name is missing, mention it under missing_information. "
            "opportunity_signals and risk_signals must be arrays of short strings. "
            "missing_information must be an array of short strings. "
            "confidence_level must be one of: low, medium, high."
        )

    def _user_prompt(self, snapshot):
        prompt_version = (
            self.env["bid.board.settings"].sudo().get_singleton().get_market_analysis_prompt_version()
        )
        client_name = (snapshot.get("client_name") or "").strip() or "Unknown client"
        return (
            "Analyze this bid/project record using only the provided internal fields.\n"
            "The purpose is to help a bid team understand likely market position, price pressure, "
            "and information gaps before bidding.\n"
            f"Prompt version: {prompt_version}\n\n"
            f"Client name (must be used as the primary account context): {client_name}\n\n"
            "PROJECT SNAPSHOT JSON:\n"
            f"{json.dumps(snapshot, indent=2, sort_keys=True)}"
        )

    def _user_prompt_combined(self, snapshot, external_snapshot):
        prompt_version = (
            self.env["bid.board.settings"].sudo().get_singleton().get_market_analysis_prompt_version()
        )
        client_name = (snapshot.get("client_name") or "").strip() or "Unknown client"
        return (
            "Analyze this bid/project using both internal and external current market signals.\n"
            "Clearly separate externally observed facts from internal assumptions.\n"
            "Use source-backed evidence from the provided external payload only.\n"
            f"Prompt version: {prompt_version}\n\n"
            f"Client name (must be used as the primary account context): {client_name}\n\n"
            "INTERNAL PROJECT SNAPSHOT JSON:\n"
            f"{json.dumps(snapshot, indent=2, sort_keys=True)}\n\n"
            "EXTERNAL MARKET SNAPSHOT JSON:\n"
            f"{json.dumps(external_snapshot, indent=2, sort_keys=True)}"
        )

    def _external_brief_prompt(self, project, external_snapshot):
        client_name = (project.client_name or "").strip() or "Unknown client"
        industry = project._market_analysis_selection_display("industry") or "target sector"
        contract_type = project._market_analysis_selection_display("contract_type") or "contract"
        return (
            "Create a competitor-focused strategic intelligence brief for a bid team.\n"
            "Use only the provided external evidence. Do not invent contracts, clients, rankings, staff issues, or claims.\n"
            "Prefer company-specific evidence over general market commentary.\n"
            "If a point comes from softer signals such as reviews or commentary, label it as market feedback.\n"
            "You may include informed strategic inferences when evidence strongly points to them.\n"
            "For inferred points, phrase them as likely risk/opportunity rather than confirmed fact.\n"
            "If a section is not supported by evidence, say so briefly instead of guessing.\n"
            "Return strict JSON with exactly these keys: "
            "title, key_contract_wins_focus_areas, good, bad, research_gaps, execution_prompt, strategic_tip, bottom_line.\n"
            "The array fields key_contract_wins_focus_areas, good, bad, and research_gaps must be arrays of short strings.\n"
            "execution_prompt should be a reusable 5-8 line deep-research prompt for sector-specific investigation.\n"
            "strategic_tip should be a concise advisory paragraph for how to position the bid.\n"
            "bottom_line should be one concise concluding sentence.\n\n"
            f"Client name: {client_name}\n\n"
            f"Sector context: {industry}\n"
            f"Contract context: {contract_type}\n\n"
            "EXTERNAL EVIDENCE JSON:\n"
            f"{json.dumps(external_snapshot, indent=2, sort_keys=True)}"
        )

    def _gemini_direct_intel_prompt(self, project, external_snapshot):
        client_name = (project.client_name or "").strip() or "Unknown client"
        industry = project._market_analysis_selection_display("industry") or "target sector"
        contract_type = project._market_analysis_selection_display("contract_type") or "contract"
        return (
            "You are a commercial strategy analyst supporting UAE facilities and soft-services bids.\n\n"
            "Create a competitor-focused strategic intelligence brief for a bid team.\n"
            "You do not have live web search results. Use only the INTERNAL_PROJECT_SNAPSHOT JSON inside the payload "
            "(and treat client_website as an optional label only—do not claim you retrieved that website).\n"
            "You may add cautious UAE / sector perspective where it helps the bid; label it clearly when it is not "
            "from the snapshot.\n"
            "Do not invent named contracts, clients, rankings, or audited financials.\n"
            "Return strict JSON with exactly these keys: "
            "title, key_contract_wins_focus_areas, good, bad, research_gaps, execution_prompt, strategic_tip, bottom_line.\n"
            "Optional key \"position\" is allowed as a short paragraph (string).\n"
            "The array fields key_contract_wins_focus_areas, good, bad, and research_gaps must be arrays of short strings.\n"
            "execution_prompt should be a reusable 5-8 line deep-research prompt for follow-up investigation.\n"
            "strategic_tip should be a concise advisory paragraph for how to position the bid.\n"
            "bottom_line should be one concise concluding sentence.\n\n"
            f"Client name: {client_name}\n"
            f"Sector context: {industry}\n"
            f"Contract context: {contract_type}\n\n"
            "PAYLOAD JSON:\n"
            f"{json.dumps(external_snapshot, indent=2, sort_keys=True)}"
        )

    def _is_direct_gemini_model(self, model_name, api_key):
        model = (model_name or "").strip().lower()
        key = (api_key or "").strip()
        return bool(key) and key.startswith("AIza") and (
            model.startswith("gemini-") or model.startswith("models/gemini-")
        )

    def _call_gemini_generate_content(
        self, api_key, model_name, timeout_seconds, prompt_text, response_mime_json=False
    ):
        model = (model_name or "gemini-2.0-flash").strip()
        if model.startswith("models/"):
            model = model.split("/", 1)[1]
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        generation_config = {"temperature": 0.35}
        if response_mime_json:
            generation_config["responseMimeType"] = "application/json"
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": generation_config,
        }
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                response_json = json.loads(response.read().decode("utf-8", errors="replace"))
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            details = body[:500] if body else _("No response body returned.")
            raise UserError(_("Gemini request failed with HTTP %(code)s: %(details)s") % {
                "code": exc.code,
                "details": details,
            })
        candidates = response_json.get("candidates") or []
        if not candidates:
            raise UserError(_("Gemini returned no candidates for strategic intelligence generation."))
        parts = (((candidates[0].get("content") or {}).get("parts")) or [])
        text_chunks = []
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                text_chunks.append(part.get("text"))
        content = "\n".join([chunk for chunk in text_chunks if chunk]).strip()
        if not content:
            raise UserError(_("Gemini returned an empty strategic intelligence response."))
        return content

    def _build_external_queries(self, project):
        project.ensure_one()
        client = (project.client_name or "").strip()
        emirate = project._market_analysis_selection_display("emirate") or "UAE"
        domain = self._normalized_client_domain(project)
        queries = []
        if client:
            if domain:
                client_queries = [
                    f"site:{domain} \"{client}\" about",
                    f"site:{domain} \"{client}\" services",
                    f"site:{domain} \"{client}\" projects",
                    f"site:{domain} \"{client}\" clients",
                    f"site:{domain} \"{client}\" case studies",
                    f"site:{domain} \"{client}\" awards OR news",
                ]
            else:
                client_queries = [
                    f"\"{client}\" {emirate} UAE official website",
                    f"\"{client}\" UAE company profile",
                    f"\"{client}\" UAE services",
                    f"\"{client}\" UAE projects clients",
                    f"\"{client}\" UAE case studies",
                    f"\"{client}\" UAE awards news",
                ]
            for query in client_queries:
                queries.append({"scope": "client_specific", "query": query})
        return queries

    def _client_tokens(self, project):
        raw = (project.client_name or "").lower()
        parts = re.findall(r"[a-z0-9]+", raw)
        return [p for p in parts if len(p) >= 4 and p not in self._CLIENT_STOPWORDS]

    def _industry_tokens(self, project):
        label = (project._market_analysis_selection_display("industry") or "").lower()
        return [p for p in re.findall(r"[a-z0-9]+", label) if len(p) >= 4]

    def _score_external_item(self, project, item):
        text = self._item_text(item)
        score = 0
        client_tokens = self._client_tokens(project)
        industry_tokens = self._industry_tokens(project)
        emirate = (project._market_analysis_selection_display("emirate") or "").lower()
        if "uae" in text or "dubai" in text or "abu dhabi" in text or emirate in text:
            score += 2
        for tok in client_tokens:
            if tok in text:
                score += 4
        for tok in industry_tokens[:4]:
            if tok in text:
                score += 1
        for hint in self._HIGH_QUALITY_HINTS:
            if hint in text:
                score += 2
        for hint, points in self._CLIENT_PAGE_HINTS.items():
            if hint in text:
                score += points
        source = (item.get("source") or "").strip().lower()
        if source == "google knowledge graph":
            score += 8
        domain = urlparse(item.get("link") or "").netloc.lower()
        client_domain = self._normalized_client_domain(project)
        if client_domain and client_domain in domain:
            score += 10
        if domain and all(hint not in domain for hint in self._LOW_QUALITY_HINTS):
            for tok in client_tokens[:2]:
                if tok in domain:
                    score += 5
                    break
        for hint in self._LOW_QUALITY_HINTS:
            if hint in text:
                score -= 4
        return score

    def _has_client_token_match(self, project, item):
        text = self._item_text(item)
        for tok in self._client_tokens(project):
            if tok in text:
                return True
        return False

    def _is_authoritative_client_item(self, project, item):
        source = (item.get("source") or "").strip().lower()
        if source == "google knowledge graph":
            return True
        domain = urlparse(item.get("link") or "").netloc.lower()
        client_domain = self._normalized_client_domain(project)
        if client_domain and client_domain in domain:
            return True
        if not domain:
            return False
        if any(hint in domain for hint in self._LOW_QUALITY_HINTS):
            return False
        for tok in self._client_tokens(project)[:2]:
            if tok in domain:
                return True
        text = self._item_text(item)
        if self._has_client_token_match(project, item):
            for hint in self._CLIENT_PAGE_HINTS:
                if hint in text:
                    return True
        return False

    def _dedupe_external_items(self, items):
        seen = set()
        deduped = []
        for item in items:
            key = (
                (item.get("link") or "").strip().lower()
                or (item.get("title") or "").strip().lower()
            )
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _is_fetchable_external_item(self, item):
        link = (item.get("link") or "").strip()
        if not link:
            return False
        parsed = urlparse(link)
        if parsed.scheme not in ("http", "https"):
            return False
        text = self._item_text(item)
        if any(hint in text for hint in self._LOW_QUALITY_HINTS):
            return False
        return True

    def _fetch_webpage_text(self, url, timeout_seconds):
        req = request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": "OdooBidBoard/1.0",
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
            },
        )
        with request.urlopen(req, timeout=timeout_seconds) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and "html" not in content_type and "text/plain" not in content_type:
                return ""
            raw = response.read(250000).decode("utf-8", errors="replace")
        cleaned = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
        cleaned = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", cleaned)
        cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
        cleaned = re.sub(r"(?i)</p>|</div>|</section>|</article>|</li>|</h[1-6]>", "\n", cleaned)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = unescape(cleaned)
        cleaned = re.sub(r"[ \t\r\f\v]+", " ", cleaned)
        cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
        return cleaned.strip()[:6000]

    def _collect_external_page_evidence(self, client_items, market_items, timeout_seconds):
        pages = []
        candidates = []
        for scope, items in (("client_specific", client_items),):
            for item in items[:6]:
                if self._is_fetchable_external_item(item):
                    candidates.append((scope, item))
        seen = set()
        for scope, item in candidates:
            link = (item.get("link") or "").strip()
            if not link or link in seen:
                continue
            seen.add(link)
            try:
                page_text = self._fetch_webpage_text(link, timeout_seconds)
            except Exception:
                page_text = ""
            if not page_text:
                continue
            excerpt = page_text[:2500]
            item["page_excerpt"] = excerpt
            pages.append(
                {
                    "scope": scope,
                    "title": item.get("title") or "",
                    "source": item.get("source") or "",
                    "link": link,
                    "excerpt": excerpt,
                }
            )
            if len(pages) >= 6:
                break
        return pages

    def _format_external_item_summary(self, item):
        source = (item.get("source") or "").strip() or _("Unknown source")
        published_at = (item.get("published_at") or "").strip()
        snippet = re.sub(r"\s+", " ", (item.get("snippet") or "").strip())
        if len(snippet) > 180:
            snippet = snippet[:177].rstrip() + "..."
        parts = [f"- {source}"]
        if published_at:
            parts.append(f"({published_at})")
        title = (item.get("title") or "").strip()
        if title:
            parts.append(f": {title}")
        line = " ".join(parts)
        if snippet:
            line = f"{line}. {snippet}"
        return line

    def _build_external_summary(self, project, client_items, market_items):
        lines = []
        client_name = (project.client_name or "").strip()
        if client_name:
            authoritative_client_items = [
                item for item in client_items if self._is_authoritative_client_item(project, item)
            ]
            if authoritative_client_items:
                lines.append(_("Client intelligence for %s:") % client_name)
                for item in authoritative_client_items[:4]:
                    lines.append(self._format_external_item_summary(item))
            else:
                lines.append(
                    _(
                        "No verified company-specific external sources were found for %s."
                    )
                    % client_name
                )
                if not self._normalized_client_domain(project):
                    lines.append("")
                    lines.append(
                        _(
                            "Add Client Website on the project to target the company domain directly."
                        )
                    )
        return "\n".join(lines).strip()

    def _format_external_brief(self, brief):
        title = (brief.get("title") or "").strip()
        position = (brief.get("position") or "").strip()
        wins_focus = self._normalize_bullets(
            brief.get("key_contract_wins_focus_areas") or brief.get("notable_contracts_clients")
        )
        strengths = self._normalize_bullets(brief.get("good") or brief.get("strengths"))
        weak_points = self._normalize_bullets(brief.get("bad") or brief.get("weak_points"))
        research_gaps = self._normalize_bullets(brief.get("research_gaps"))
        execution_prompt = (brief.get("execution_prompt") or "").strip()
        strategic_tip = (brief.get("strategic_tip") or brief.get("verdict") or "").strip()
        bottom_line = (brief.get("bottom_line") or "").strip()

        lines = []
        if title:
            lines.append(title)
            lines.append("")
        if position:
            lines.append(_("Position:"))
            lines.append(position)
            lines.append("")
        if wins_focus:
            lines.append(_("Key Contract Wins & Focus Areas:"))
            lines.extend([f"- {item}" for item in wins_focus])
            lines.append("")
        if strengths:
            lines.append(_("The Good:"))
            lines.extend([f"- {item}" for item in strengths])
            lines.append("")
        if weak_points:
            lines.append(_("The Bad:"))
            lines.extend([f"- {item}" for item in weak_points])
            lines.append("")
        if research_gaps:
            lines.append(_("Research Gaps:"))
            lines.extend([f"- {item}" for item in research_gaps])
            lines.append("")
        if execution_prompt:
            lines.append(_("Execution Prompt for Deep Research:"))
            lines.append(execution_prompt)
            lines.append("")
        if strategic_tip:
            lines.append(_("Strategic Tip for Your Bid:"))
            lines.append(strategic_tip)
            lines.append("")
        if bottom_line:
            lines.append(_("Bottom line:"))
            lines.append(bottom_line)
        return "\n".join(lines).strip()

    def _generate_external_brief(
        self, project, provider_code, sources, client_items, market_items, page_evidence, timeout_seconds
    ):
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        provider = settings.get_market_analysis_provider()
        api_key = settings.get_market_analysis_api_key()
        model_name = settings.get_market_analysis_model()
        if not settings.get_market_analysis_enabled() or not api_key or provider != "openrouter":
            return self._build_external_summary(project, client_items, market_items)

        external_snapshot = {
            "provider": self._provider_display_name(provider_code),
            "client_name": project.client_name,
            "sources": [],
            "page_evidence": page_evidence[:6],
        }
        for block in sources:
            external_snapshot["sources"].append(
                {
                    "scope": block.get("scope"),
                    "query": block.get("query"),
                    "items": (block.get("items") or [])[:4],
                }
            )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a bid intelligence analyst. Use only supplied evidence. "
                    "Never state unsupported contracts, rankings, or client names as facts."
                ),
            },
            {"role": "user", "content": self._external_brief_prompt(project, external_snapshot)},
        ]
        try:
            if self._is_direct_gemini_model(model_name, api_key):
                prompt_text = (
                    "You are a commercial strategy analyst for UAE facilities management bids.\n\n"
                    + messages[1]["content"]
                )
                content = self._call_gemini_generate_content(
                    api_key, model_name, timeout_seconds, prompt_text, response_mime_json=True
                )
            else:
                response_json = self._call_openrouter(api_key, model_name, timeout_seconds, messages)
                content = self._extract_message_content(response_json)
            parsed = json.loads(self._extract_json_block(content))
            if not isinstance(parsed, dict):
                raise ValueError("External brief response was not a JSON object")
            return self._format_external_brief(parsed)
        except Exception:
            return self._build_external_summary(project, client_items, market_items)

    def _filter_external_items(self, project, items, scope="market_context"):
        scored = []
        for item in items:
            text = self._item_text(item)
            if any(hint in text for hint in self._LOW_QUALITY_HINTS):
                continue
            s = self._score_external_item(project, item)
            if scope == "client_specific" and not self._has_client_token_match(project, item):
                continue
            if scope == "client_specific" and s < 6 and not self._is_authoritative_client_item(project, item):
                continue
            if s >= 2:
                scored.append((s, item))
        scored.sort(key=lambda row: row[0], reverse=True)
        return [item for _, item in scored]

    def _fetch_google_news_rss(self, query, limit, timeout_seconds):
        q = quote_plus(query)
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        req = request.Request(url, method="GET", headers={"User-Agent": "OdooBidBoard/1.0"})
        with request.urlopen(req, timeout=timeout_seconds) as response:
            xml_text = response.read().decode("utf-8", errors="replace")
        root = ET.fromstring(xml_text)
        items = []
        for item in root.findall("./channel/item")[:limit]:
            items.append(
                {
                    "title": (item.findtext("title") or "").strip(),
                    "link": (item.findtext("link") or "").strip(),
                    "published_at": (item.findtext("pubDate") or "").strip(),
                    "source": (item.findtext("source") or "").strip(),
                }
            )
        return [it for it in items if it.get("title")]

    def _fetch_google_search_api(self, api_key, query, limit, timeout_seconds):
        payload = {"q": query, "num": max(3, min(20, limit))}
        req = request.Request(
            "https://google.serper.dev/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
                "User-Agent": "OdooBidBoard/1.0",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        items = []
        knowledge_graph = data.get("knowledgeGraph") or {}
        if isinstance(knowledge_graph, dict) and (
            knowledge_graph.get("title") or knowledge_graph.get("description")
        ):
            attributes = knowledge_graph.get("attributes") or {}
            attribute_parts = []
            if isinstance(attributes, dict):
                for key, value in list(attributes.items())[:5]:
                    if value:
                        attribute_parts.append(f"{key}: {value}")
            description_parts = [knowledge_graph.get("description") or ""]
            if attribute_parts:
                description_parts.append("; ".join(attribute_parts))
            items.append(
                {
                    "title": (knowledge_graph.get("title") or "").strip(),
                    "link": (
                        knowledge_graph.get("website")
                        or knowledge_graph.get("websiteUrl")
                        or knowledge_graph.get("source")
                        or ""
                    ).strip(),
                    "published_at": "",
                    "source": "Google Knowledge Graph",
                    "snippet": ". ".join(
                        [part.strip() for part in description_parts if part and part.strip()]
                    ),
                }
            )
        for row in (data.get("organic") or [])[:limit]:
            items.append(
                {
                    "title": (row.get("title") or "").strip(),
                    "link": (row.get("link") or "").strip(),
                    "published_at": "",
                    "source": (
                        row.get("source")
                        or row.get("displayLink")
                        or self._source_from_url(row.get("link") or "")
                    ).strip(),
                    "snippet": (row.get("snippet") or "").strip(),
                }
            )
        for row in (data.get("news") or [])[:limit]:
            items.append(
                {
                    "title": (row.get("title") or "").strip(),
                    "link": (row.get("link") or "").strip(),
                    "published_at": (row.get("date") or "").strip(),
                    "source": (
                        row.get("source") or self._source_from_url(row.get("link") or "")
                    ).strip(),
                    "snippet": (row.get("snippet") or "").strip(),
                }
            )
        return [it for it in items if it.get("title")]

    def _call_openrouter(self, api_key, model_name, timeout_seconds, messages):
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": (
                self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
                or "https://odoo.local"
            ),
            "X-Title": "Sales Bid Board",
        }
        req = request.Request(self._OPENROUTER_URL, data=data, headers=headers, method="POST")
        retries = 2
        for attempt in range(retries + 1):
            try:
                with request.urlopen(req, timeout=timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    body = ""
                if exc.code == 429 and attempt < retries:
                    # Free routed models can be transiently throttled; short backoff usually clears it.
                    time.sleep(2 * (attempt + 1))
                    continue
                if exc.code == 429:
                    raise UserError(
                        _(
                            "AI provider is temporarily rate-limited for this free model (HTTP 429). "
                            "Please retry in a few seconds or switch to another free routed model."
                        )
                    )
                if exc.code == 404:
                    raise UserError(
                        _(
                            "Configured model endpoint is unavailable on provider (HTTP 404). "
                            "Update Model name in Bid Board Settings to an active free routed model."
                        )
                    )
                details = body[:500] if body else _("No response body returned.")
                raise UserError(
                    _("Market analysis request failed with HTTP %(code)s: %(details)s")
                    % {"code": exc.code, "details": details}
                )
            except error.URLError as exc:
                reason = getattr(exc, "reason", exc)
                if attempt < retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise UserError(_("Market analysis request could not reach the provider: %s") % reason)
            except TimeoutError:
                if attempt < retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise UserError(_("Market analysis request timed out. Please try again."))
        raise UserError(_("Market analysis request failed after retries. Please try again."))

    def _extract_message_content(self, response_json):
        choices = response_json.get("choices") or []
        if not choices:
            raise UserError(_("AI provider returned no choices for market analysis."))
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text") or "")
            content = "\n".join([part for part in parts if part])
        if not isinstance(content, str) or not content.strip():
            raise UserError(_("AI provider returned an empty market analysis response."))
        return content.strip()

    def _extract_json_block(self, content):
        text = (content or "").strip()
        if text.startswith("```"):
            first_brace = text.find("{")
            last_brace = text.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                return text[first_brace : last_brace + 1]
        return text

    def _normalize_text(self, value):
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            return "\n".join([f"- {item}" for item in cleaned])
        if value in (False, None):
            return ""
        return str(value).strip()

    def _normalize_confidence(self, value):
        confidence = str(value or "").strip().lower()
        if confidence not in ("low", "medium", "high"):
            confidence = "medium"
        return confidence

    def _normalize_bullets(self, value):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value in (False, None, ""):
            return []
        return [str(value).strip()]

    def _parse_analysis_content(self, content):
        json_text = self._extract_json_block(content)
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as exc:
            repaired = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", json_text)
            try:
                parsed = json.loads(repaired)
            except json.JSONDecodeError:
                # Free routed models may occasionally output malformed JSON despite instructions.
                # Persist a readable fallback instead of failing the whole user flow.
                return {
                    "market_analysis_summary": (content or "").strip()[:4000],
                    "market_analysis_opportunity_signals": "",
                    "market_analysis_risk_signals": "",
                    "market_analysis_competition_view": "",
                    "market_analysis_pricing_view": "",
                    "market_analysis_bid_support": "",
                    "market_analysis_missing_info": _(
                        "Model did not return strict JSON; review summary text and regenerate if needed."
                    ),
                    "market_analysis_confidence": "medium",
                    "market_analysis_disclaimer": _(
                        "AI-assisted analysis generated with fallback text parsing due to malformed model output."
                    ),
                    "market_analysis_output_json": json.dumps(
                        {"raw_text": (content or "").strip(), "parse_error": str(exc)},
                        indent=2,
                        sort_keys=True,
                    ),
                }
        if not isinstance(parsed, dict):
            raise UserError(_("AI provider returned an unexpected market analysis payload."))
        disclaimer = self._normalize_text(parsed.get("disclaimer"))
        if not disclaimer:
            disclaimer = _(
                "AI-assisted analysis based only on the internal project fields captured in this record."
            )
        return {
            "market_analysis_summary": self._normalize_text(parsed.get("summary")),
            "market_analysis_opportunity_signals": self._normalize_text(
                parsed.get("opportunity_signals")
            ),
            "market_analysis_risk_signals": self._normalize_text(parsed.get("risk_signals")),
            "market_analysis_competition_view": self._normalize_text(
                parsed.get("competition_view")
            ),
            "market_analysis_pricing_view": self._normalize_text(
                parsed.get("pricing_pressure_view")
            ),
            "market_analysis_bid_support": self._normalize_text(
                parsed.get("bid_recommendation_support")
            ),
            "market_analysis_missing_info": self._normalize_text(
                parsed.get("missing_information")
            ),
            "market_analysis_confidence": self._normalize_confidence(
                parsed.get("confidence_level")
            ),
            "market_analysis_disclaimer": disclaimer,
            "market_analysis_output_json": json.dumps(parsed, indent=2, sort_keys=True),
        }

    def analyze_project(self, project):
        project.ensure_one()
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        if not settings.get_market_analysis_enabled():
            raise UserError(_("Enable AI market analysis in Bid Board Settings before generating it."))
        api_key = settings.get_market_analysis_api_key()
        if not api_key:
            raise UserError(_("Set the AI market analysis API key in Bid Board Settings first."))
        provider = settings.get_market_analysis_provider()
        if provider != "openrouter":
            raise UserError(_("Unsupported AI market analysis provider: %s") % provider)
        model_name = settings.get_market_analysis_model()
        timeout_seconds = settings.get_market_analysis_timeout_seconds()
        snapshot = project._market_analysis_build_snapshot()
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._user_prompt(snapshot)},
        ]
        if self._is_direct_gemini_model(model_name, api_key):
            prompt_text = (messages[0].get("content") or "").strip() + "\n\n" + (
                messages[1].get("content") or ""
            ).strip()
            content = self._call_gemini_generate_content(
                api_key, model_name, timeout_seconds, prompt_text, response_mime_json=True
            )
        else:
            response_json = self._call_openrouter(api_key, model_name, timeout_seconds, messages)
            content = self._extract_message_content(response_json)
        values = self._parse_analysis_content(content)
        values.update(
            {
                "market_analysis_status": "ready",
                "market_analysis_generated_on": fields.Datetime.now(),
                "market_analysis_generated_by": self.env.user.id,
                "market_analysis_model": model_name,
                "market_analysis_input_json": json.dumps(snapshot, indent=2, sort_keys=True),
                "market_analysis_includes_external": False,
                "market_analysis_last_error": False,
            }
        )
        return values

    def _collect_external_market_data_gemini_direct(self, project):
        project.ensure_one()
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        timeout_seconds = settings.get_external_market_timeout_seconds()
        if not settings.get_market_analysis_enabled():
            raise UserError(
                _("Enable AI market analysis and configure your Gemini API key and model name.")
            )
        api_key = settings.get_market_analysis_api_key()
        model_name = settings.get_market_analysis_model()
        if not self._is_direct_gemini_model(model_name, api_key):
            raise UserError(
                _(
                    "Direct Gemini (no web search) needs a Google AI Studio API key (starts with AIza…) "
                    "and a Gemini model id (for example gemini-2.5-flash-lite) under AI Market Analysis."
                )
            )
        if not (project.client_name or "").strip():
            raise UserError(
                _("Set a client name on the project before generating strategic market intelligence.")
            )
        snapshot = project._market_analysis_build_snapshot()
        external_snapshot = {
            "mode": "direct_gemini_no_web",
            "client_website": (project.client_website or "").strip(),
            "internal_project_snapshot": snapshot,
        }
        prompt = self._gemini_direct_intel_prompt(project, external_snapshot)
        content = self._call_gemini_generate_content(
            api_key, model_name, timeout_seconds, prompt, response_mime_json=True
        )
        try:
            parsed = json.loads(self._extract_json_block(content))
        except json.JSONDecodeError as exc:
            raise UserError(_("Gemini returned invalid JSON for strategic intelligence: %s") % exc) from exc
        if not isinstance(parsed, dict):
            raise UserError(_("Gemini strategic intelligence response was not a JSON object."))
        highlights = self._format_external_brief(parsed)
        sources = [{"scope": "direct_gemini", "query": "", "items": []}]
        return {
            "market_external_status": "ready",
            "market_external_provider": self._provider_display_name("gemini_direct"),
            "market_external_query": False,
            "market_external_sources_json": json.dumps(sources, indent=2, sort_keys=True),
            "market_external_summary": highlights,
            "market_external_fetched_on": fields.Datetime.now(),
            "market_external_last_error": False,
        }

    def collect_external_market_data(self, project):
        project.ensure_one()
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        if not settings.get_external_market_enabled():
            raise UserError(_("Enable external market data in Bid Board Settings first."))
        if settings.get_external_market_gemini_direct():
            return self._collect_external_market_data_gemini_direct(project)
        provider = settings.get_external_market_provider()
        external_api_key = settings.get_external_market_api_key()
        if provider == "google_search_api" and not external_api_key:
            raise UserError(_("Set External API key in settings for Google Search API provider."))
        timeout_seconds = settings.get_external_market_timeout_seconds()
        limit = settings.get_external_market_news_limit()
        queries = self._build_external_queries(project)
        if not queries:
            raise UserError(
                _("Set a client name first. Add Client Website on the project for better company research.")
            )
        sources = []
        errors = []
        client_specific_hits = []
        market_context_hits = []
        for block in queries:
            query = block.get("query")
            scope = block.get("scope") or "market_context"
            try:
                if provider == "google_search_api":
                    items = self._fetch_google_search_api(
                        external_api_key, query, limit, timeout_seconds
                    )
                elif provider == "google_news_rss":
                    items = self._fetch_google_news_rss(query, limit, timeout_seconds)
                else:
                    raise UserError(_("Unsupported external market provider: %s") % provider)
            except Exception as exc:
                errors.append(f"{query}: {exc}")
                continue
            filtered = self._filter_external_items(project, items, scope=scope)
            sources.append({"scope": scope, "query": query, "items": filtered})
            if scope == "client_specific":
                client_specific_hits.extend(filtered[:limit])
            else:
                market_context_hits.extend(filtered[:limit])
        client_specific_hits = self._dedupe_external_items(client_specific_hits)
        market_context_hits = self._dedupe_external_items(market_context_hits)
        page_evidence = self._collect_external_page_evidence(
            client_specific_hits, market_context_hits, timeout_seconds
        )
        if not any(block.get("items") for block in sources):
            msg = _("External market fetch returned no items.")
            if errors:
                msg = _("%s Errors: %s") % (msg, "; ".join(errors[:3]))
            raise UserError(msg)
        if not client_specific_hits:
            return {
                "market_external_status": "ready",
                "market_external_provider": self._provider_display_name(provider),
                "market_external_query": False,
                "market_external_sources_json": json.dumps(sources, indent=2, sort_keys=True),
                "market_external_summary": self._build_external_summary(
                    project, client_specific_hits, []
                ),
                "market_external_fetched_on": fields.Datetime.now(),
                "market_external_last_error": False,
            }
        highlights = self._generate_external_brief(
            project,
            provider,
            sources,
            client_specific_hits,
            [],
            page_evidence,
            timeout_seconds,
        )
        return {
            "market_external_status": "ready",
            "market_external_provider": self._provider_display_name(provider),
            "market_external_query": False,
            "market_external_sources_json": json.dumps(sources, indent=2, sort_keys=True),
            "market_external_summary": highlights,
            "market_external_fetched_on": fields.Datetime.now(),
            "market_external_last_error": False,
        }

    def analyze_project_combined(self, project):
        project.ensure_one()
        if project.market_external_status != "ready":
            raise UserError(_("Fetch external market data first, then run combined analysis."))
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        if not settings.get_market_analysis_enabled():
            raise UserError(_("Enable AI market analysis in Bid Board Settings before generating it."))
        api_key = settings.get_market_analysis_api_key()
        if not api_key:
            raise UserError(_("Set the AI market analysis API key in Bid Board Settings first."))
        model_name = settings.get_market_analysis_model()
        timeout_seconds = settings.get_market_analysis_timeout_seconds()
        snapshot = project._market_analysis_build_snapshot()
        external_snapshot = project._market_analysis_external_snapshot()
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._user_prompt_combined(snapshot, external_snapshot)},
        ]
        if self._is_direct_gemini_model(model_name, api_key):
            prompt_text = (messages[0].get("content") or "").strip() + "\n\n" + (
                messages[1].get("content") or ""
            ).strip()
            content = self._call_gemini_generate_content(
                api_key, model_name, timeout_seconds, prompt_text, response_mime_json=True
            )
        else:
            response_json = self._call_openrouter(api_key, model_name, timeout_seconds, messages)
            content = self._extract_message_content(response_json)
        values = self._parse_analysis_content(content)
        values.update(
            {
                "market_analysis_status": "ready",
                "market_analysis_generated_on": fields.Datetime.now(),
                "market_analysis_generated_by": self.env.user.id,
                "market_analysis_model": model_name,
                "market_analysis_input_json": json.dumps(
                    {"internal": snapshot, "external": external_snapshot},
                    indent=2,
                    sort_keys=True,
                ),
                "market_analysis_includes_external": True,
                "market_analysis_last_error": False,
            }
        )
        return values


class BidProjectMarketAnalysis(models.Model):
    _inherit = "bid.project"

    client_website = fields.Char(
        copy=False,
        help="Official client website or company domain used to target company-specific external research.",
    )
    market_analysis_status = fields.Selection(
        [
            ("not_generated", "Not Generated"),
            ("ready", "Ready"),
            ("failed", "Failed"),
        ],
        default="not_generated",
        copy=False,
        help="Generation state of the stored AI market analysis snapshot.",
    )
    market_analysis_generated_on = fields.Datetime(copy=False)
    market_analysis_generated_by = fields.Many2one("res.users", copy=False)
    market_analysis_model = fields.Char(copy=False)
    market_analysis_input_json = fields.Text(copy=False)
    market_analysis_output_json = fields.Text(copy=False)
    market_analysis_summary = fields.Text(copy=False)
    market_analysis_opportunity_signals = fields.Text(copy=False)
    market_analysis_risk_signals = fields.Text(copy=False)
    market_analysis_competition_view = fields.Text(copy=False)
    market_analysis_pricing_view = fields.Text(copy=False)
    market_analysis_bid_support = fields.Text(copy=False)
    market_analysis_missing_info = fields.Text(copy=False)
    market_analysis_confidence = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        copy=False,
    )
    market_analysis_includes_external = fields.Boolean(copy=False)
    market_analysis_disclaimer = fields.Text(copy=False)
    market_analysis_last_error = fields.Text(copy=False)
    market_external_status = fields.Selection(
        [("not_fetched", "Not Fetched"), ("ready", "Ready"), ("failed", "Failed")],
        default="not_fetched",
        copy=False,
    )
    market_external_fetched_on = fields.Datetime(copy=False)
    market_external_provider = fields.Char(copy=False)
    market_external_query = fields.Text(copy=False)
    market_external_summary = fields.Text(copy=False)
    market_external_sources_json = fields.Text(copy=False)
    market_external_last_error = fields.Text(copy=False)

    def _market_analysis_selection_display(self, field_name):
        self.ensure_one()
        field = self._fields[field_name]
        selection = field.selection
        if callable(selection):
            selection = selection(self)
        return dict(selection or []).get(getattr(self, field_name), getattr(self, field_name) or "")

    def _market_analysis_non_empty_scope(self):
        self.ensure_one()
        values = {
            "cleaning": self.scope_cleaning,
            "maintenance": self.scope_maintenance,
            "security": self.scope_security,
            "landscaping": self.scope_landscaping,
            "laundry": self.scope_laundry,
            "support": self.scope_support,
            "others": self.scope_others,
        }
        return {key: value for key, value in values.items() if value}

    def _market_analysis_scorecard_signals(self):
        self.ensure_one()
        lines = []
        for line in self.criteria_line_ids:
            lines.append(
                {
                    "category": self.env["bid.project.criteria"]._fields["category"].selection
                    and dict(self.env["bid.project.criteria"]._fields["category"].selection).get(
                        line.category, line.category
                    )
                    or line.category,
                    "criterion": line.name,
                    "score": int(line.score or 0),
                    "comment": (line.comment or "").strip(),
                }
            )
        return lines

    def _market_analysis_build_snapshot(self):
        self.ensure_one()
        snapshot = {
            "project_name": self.name,
            "project_code": self.code,
            "client_name": self.client_name,
            "client_website": self.client_website,
            "industry": self._market_analysis_selection_display("industry"),
            "sector": self._market_analysis_selection_display("sector"),
            "emirate": self._market_analysis_selection_display("emirate"),
            "contract_duration": self._market_analysis_selection_display("contract_duration"),
            "contract_type": self._market_analysis_selection_display("contract_type"),
            "threshold": self._market_analysis_selection_display("threshold"),
            "contract_value": self.contract_value,
            "project_structure": self._market_analysis_selection_display("project_structure"),
            "age_of_facility": self.age_of_facility,
            "assets_list_provided": self._market_analysis_selection_display("assets_list_provided"),
            "spare_consumables": self._market_analysis_selection_display("spare_consumables"),
            "subcontractors": self._market_analysis_selection_display("subcontractors"),
            "input_output_based": self._market_analysis_selection_display("input_output_based"),
            "tender_bond": self._market_analysis_selection_display("tender_bond"),
            "performance_bond": self._market_analysis_selection_display("performance_bond"),
            "kpi_flag": self._market_analysis_selection_display("kpi"),
            "kpi_penalty_mechanism": self.kpi_penalty_mechanism,
            "rfp_received_date": str(self.rfp_received_date) if self.rfp_received_date else "",
            "site_visit_date": str(self.site_visit_date) if self.site_visit_date else "",
            "deadline_datetime": (
                fields.Datetime.to_string(self.deadline_datetime) if self.deadline_datetime else ""
            ),
            "progress": self.progress,
            "description": self.description,
            "scope_breakdown_percent": self._market_analysis_non_empty_scope(),
            "scope_total_percent": self.scope_total,
            "score_overall_percent": round(self.score_overall or 0.0, 2),
            "score_by_category_percent": {
                "strategy": round(self.score_strategy or 0.0, 2),
                "customer": round(self.score_customer or 0.0, 2),
                "commercial": round(self.score_commercial or 0.0, 2),
                "finance": round(self.score_finance or 0.0, 2),
                "operations": round(self.score_operations or 0.0, 2),
            },
            "system_decision": self._market_analysis_selection_display("decision_final"),
            "system_recommendation_text": self.recommendation_text,
            "system_recommendation_note": self.recommendation_note,
            "review_status": self._market_analysis_selection_display("review_status"),
            "scorecard_signals": self._market_analysis_scorecard_signals(),
        }
        return self._market_analysis_prune_empty(snapshot)

    def _market_analysis_external_snapshot(self):
        self.ensure_one()
        data = {}
        try:
            data = json.loads(self.market_external_sources_json or "{}")
        except Exception:
            data = {}
        condensed_sources = []
        for block in data if isinstance(data, list) else []:
            query = block.get("query")
            scope = block.get("scope") or "market_context"
            for item in (block.get("items") or [])[:4]:
                condensed_sources.append(
                    {
                        "scope": scope,
                        "query": query,
                        "title": (item.get("title") or "")[:240],
                        "source": item.get("source") or "",
                        "published_at": item.get("published_at") or "",
                        "link": item.get("link") or "",
                        "excerpt": (item.get("page_excerpt") or item.get("snippet") or "")[:500],
                    }
                )
        condensed_sources = condensed_sources[:12]
        return self._market_analysis_prune_empty(
            {
                "provider": self.market_external_provider,
                "fetched_on": fields.Datetime.to_string(self.market_external_fetched_on)
                if self.market_external_fetched_on
                else "",
                "query": self.market_external_query,
                "summary": self.market_external_summary,
                "sources": condensed_sources,
            }
        )

    def _market_analysis_prune_empty(self, value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                cleaned = self._market_analysis_prune_empty(item)
                if cleaned in (None, "", [], {}):
                    continue
                result[key] = cleaned
            return result
        if isinstance(value, list):
            cleaned_items = [self._market_analysis_prune_empty(item) for item in value]
            return [item for item in cleaned_items if item not in (None, "", [], {})]
        return value

    def _market_analysis_check_editable(self):
        self.ensure_one()
        if self._bid_board_locked_for_record_edit() and not self._can_bypass_approved_project_lock():
            raise ValidationError(
                _(
                    "This enquiry is locked while it is pending CSO review, or after CSO approval or decline. "
                    "Only CSO approvers, Bid Board managers, or administrators can generate market analysis then."
                )
            )

    def _market_analysis_notification_action(
        self, title, message, message_type="success", sticky=False, reload_after=False
    ):
        action = {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": message_type,
                "sticky": sticky,
            },
        }
        if reload_after:
            action["params"]["next"] = {"type": "ir.actions.client", "tag": "reload"}
        return action

    def action_generate_market_analysis(self):
        self.ensure_one()
        self._market_analysis_check_editable()
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        service = self.env["bid.market.analysis.service"]
        try:
            if settings.get_external_market_enabled():
                # Keep combined analysis current by refreshing external signals on each regenerate.
                external_values = service.collect_external_market_data(self)
                self.write(external_values)
                values = service.analyze_project_combined(self)
            else:
                values = service.analyze_project(self)
        except UserError as exc:
            self.write(
                {
                    "market_analysis_status": "failed",
                    "market_analysis_last_error": str(exc),
                }
            )
            return self._market_analysis_notification_action(
                _("Market Analysis"), str(exc), message_type="warning", sticky=True
            )
        except Exception:
            error_message = _(
                "Unexpected error while generating market analysis. Please review server logs."
            )
            self.write(
                {
                    "market_analysis_status": "failed",
                    "market_analysis_last_error": error_message,
                }
            )
            return self._market_analysis_notification_action(
                _("Market Analysis"), error_message, message_type="warning", sticky=True
            )
        self.write(values)
        self.message_post(
            body=_("AI market analysis generated using model %s.") % (self.market_analysis_model or "")
        )
        return self._market_analysis_notification_action(
            _("Market Analysis"), _("AI market analysis generated successfully."), reload_after=True
        )

    def action_fetch_external_market_data(self):
        self.ensure_one()
        self._market_analysis_check_editable()
        try:
            values = self.env["bid.market.analysis.service"].collect_external_market_data(self)
        except UserError as exc:
            self.write(
                {
                    "market_external_status": "failed",
                    "market_external_last_error": str(exc),
                }
            )
            return self._market_analysis_notification_action(
                _("External Market Data"), str(exc), message_type="warning", sticky=True
            )
        self.write(values)
        self.message_post(body=_("External market signals fetched successfully."))
        return self._market_analysis_notification_action(
            _("External Market Data"),
            _("External market data fetched successfully."),
            reload_after=True,
        )

    def action_generate_combined_market_analysis(self):
        self.ensure_one()
        self._market_analysis_check_editable()
        service = self.env["bid.market.analysis.service"]
        try:
            # Always refresh external market snapshot before combined generation.
            external_values = service.collect_external_market_data(self)
            self.write(external_values)
            values = service.analyze_project_combined(self)
        except UserError as exc:
            self.write(
                {
                    "market_analysis_status": "failed",
                    "market_analysis_last_error": str(exc),
                }
            )
            return self._market_analysis_notification_action(
                _("Combined Market Analysis"), str(exc), message_type="warning", sticky=True
            )
        self.write(values)
        self.message_post(
            body=_("Combined market analysis generated using model %s.") % (self.market_analysis_model or "")
        )
        return self._market_analysis_notification_action(
            _("Combined Market Analysis"),
            _("Combined market analysis generated successfully."),
            reload_after=True,
        )
