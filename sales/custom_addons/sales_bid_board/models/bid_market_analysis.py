import json
import re
from urllib import error, request
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Legacy Serper / external key before dedicated External Gemini API key existed.
_LEGACY_EXTERNAL_MARKET_API_KEY_PARAM = "sales_bid_board.external_market_api_key"


def _normalize_google_studio_api_key(raw):
    """Strip whitespace, BOM, and matching ASCII/curly quotes often pasted around API keys."""
    if raw in (False, None):
        return ""
    key = str(raw).strip()
    if not key:
        return ""
    key = key.lstrip("\ufeff")
    quote_pairs = (
        ('"', '"'),
        ("'", "'"),
        ("\u201c", "\u201d"),
        ("\u2018", "\u2019"),
    )
    for open_q, close_q in quote_pairs:
        if len(key) >= 2 and key[0] == open_q and key[-1] == close_q:
            key = key[1:-1].strip()
            break
    return key.strip()


def _is_google_ai_studio_gemini_api_key(raw):
    """True for keys issued by Google AI Studio for the Gemini REST API (classic AIza… or newer AQ.… keys)."""
    kn = _normalize_google_studio_api_key(raw)
    return bool(kn) and (kn.startswith("AIza") or kn.startswith("AQ."))


class BidBoardSettingsMarketAnalysis(models.Model):
    _inherit = "bid.board.settings"

    _MARKET_ANALYSIS_ENABLED_KEY = "sales_bid_board.market_analysis_enabled"
    _MARKET_ANALYSIS_MODEL_KEY = "sales_bid_board.market_analysis_model"
    _MARKET_ANALYSIS_API_KEY = "sales_bid_board.market_analysis_api_key"
    _MARKET_ANALYSIS_TIMEOUT_KEY = "sales_bid_board.market_analysis_timeout_seconds"
    _MARKET_ANALYSIS_PROMPT_VERSION_KEY = "sales_bid_board.market_analysis_prompt_version"
    _MARKET_ANALYSIS_PROMPT_TEMPLATE_KEY = "sales_bid_board.market_analysis_prompt_template"
    _EXTERNAL_MARKET_ENABLED_KEY = "sales_bid_board.external_market_enabled"
    _EXTERNAL_MARKET_GEMINI_API_KEY = "sales_bid_board.external_market_gemini_api_key"
    _EXTERNAL_MARKET_GEMINI_MODEL_KEY = "sales_bid_board.external_market_gemini_model"
    _EXTERNAL_MARKET_TIMEOUT_KEY = "sales_bid_board.external_market_timeout_seconds"

    market_analysis_enabled = fields.Boolean(
        string="Enable AI market analysis",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_enabled",
        readonly=False,
        help="Enable manual AI market analysis generation on bid/project records.",
    )
    market_analysis_model = fields.Char(
        string="Gemini model",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_model",
        readonly=False,
        help="Google Gemini model id (for example gemini-1.5-flash). Must match a model with quota in AI Studio.",
    )
    market_analysis_api_key = fields.Char(
        string="Google AI Studio API key",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_api_key",
        readonly=False,
        help="Google AI Studio Gemini API key (typically starts with AIza… or AQ…). Used for AI market analysis and "
        "as fallback for external market data when the external key is empty.",
    )
    market_analysis_timeout_seconds = fields.Integer(
        string="Request timeout (seconds)",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_timeout_seconds",
        readonly=False,
        help="HTTP timeout for AI market analysis requests.",
    )
    market_analysis_prompt_version = fields.Char(
        string="Prompt version",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_prompt_version",
        readonly=False,
        help="Version label for the active market analysis prompt contract.",
    )
    market_analysis_prompt_template = fields.Text(
        string="Prompt template override",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_market_analysis_prompt_template",
        readonly=False,
        help="Optional override for the default system prompt used by market analysis.",
    )
    external_market_enabled = fields.Boolean(
        string="Enable external market data",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_external_market_enabled",
        readonly=False,
        help="When enabled, the external strategic intelligence block uses Google Gemini only "
        "(internal bid snapshot plus optional client website field). No web search APIs.",
    )
    external_market_gemini_api_key = fields.Char(
        string="External Gemini API key",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_external_market_gemini_api_key",
        readonly=False,
        help="Google AI Studio Gemini API key (typically AIza… or AQ…) for external market intelligence. "
        "If empty, the AI Market Analysis API key is used when it is also a valid AI Studio key with a Gemini model.",
    )
    external_market_gemini_model = fields.Char(
        string="External Gemini model",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_external_market_gemini_model",
        readonly=False,
        help="Gemini model id from Google AI Studio (for example gemini-1.5-flash). Pick a model that shows "
        "non-zero RPM/TPM in your project rate limits; many free tiers have no quota for gemini-2.0-flash.",
    )
    external_market_timeout_seconds = fields.Integer(
        string="External fetch timeout (seconds)",
        compute="_compute_market_analysis_settings",
        inverse="_inverse_external_market_timeout_seconds",
        readonly=False,
        help="HTTP timeout for external Gemini requests.",
    )

    def _compute_market_analysis_settings(self):
        for rec in self:
            rec.market_analysis_enabled = rec.get_market_analysis_enabled()
            rec.market_analysis_model = rec.get_market_analysis_model()
            rec.market_analysis_api_key = rec.get_market_analysis_api_key()
            rec.market_analysis_timeout_seconds = rec.get_market_analysis_timeout_seconds()
            rec.market_analysis_prompt_version = rec.get_market_analysis_prompt_version()
            rec.market_analysis_prompt_template = rec.get_market_analysis_prompt_template()
            rec.external_market_enabled = rec.get_external_market_enabled()
            rec.external_market_gemini_api_key = rec.get_external_market_gemini_api_key()
            rec.external_market_gemini_model = rec.get_external_market_gemini_model()
            rec.external_market_timeout_seconds = rec.get_external_market_timeout_seconds()

    def _inverse_market_analysis_enabled(self):
        for rec in self:
            rec.set_market_analysis_enabled(bool(rec.market_analysis_enabled))

    def _inverse_market_analysis_model(self):
        for rec in self:
            rec.set_market_analysis_model(
                rec.market_analysis_model or rec.get_market_analysis_model()
            )

    def _inverse_market_analysis_api_key(self):
        for rec in self:
            incoming = _normalize_google_studio_api_key(rec.market_analysis_api_key)
            rec.set_market_analysis_api_key(incoming)

    def _inverse_market_analysis_timeout_seconds(self):
        for rec in self:
            rec.set_market_analysis_timeout_seconds(rec.market_analysis_timeout_seconds)

    def _inverse_market_analysis_prompt_version(self):
        for rec in self:
            rec.set_market_analysis_prompt_version(
                rec.market_analysis_prompt_version or rec.get_market_analysis_prompt_version()
            )

    def _inverse_market_analysis_prompt_template(self):
        for rec in self:
            incoming = rec.market_analysis_prompt_template
            if incoming not in (False, None, ""):
                rec.set_market_analysis_prompt_template(incoming)

    def _inverse_external_market_enabled(self):
        for rec in self:
            rec.set_external_market_enabled(bool(rec.external_market_enabled))

    def _inverse_external_market_gemini_api_key(self):
        for rec in self:
            incoming = _normalize_google_studio_api_key(rec.external_market_gemini_api_key)
            rec.set_external_market_gemini_api_key(incoming)

    def _inverse_external_market_gemini_model(self):
        for rec in self:
            rec.set_external_market_gemini_model(rec.external_market_gemini_model or "")

    def _inverse_external_market_timeout_seconds(self):
        for rec in self:
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
    def get_market_analysis_model(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._MARKET_ANALYSIS_MODEL_KEY, default="gemini-1.5-flash")
        )
        value = (raw or "").strip()
        if not value:
            return "gemini-1.5-flash"
        return value

    @api.model
    def set_market_analysis_model(self, value):
        current = self.get_market_analysis_model()
        model_name = (value or "").strip() or current or "gemini-1.5-flash"
        self.env["ir.config_parameter"].sudo().set_param(self._MARKET_ANALYSIS_MODEL_KEY, model_name)

    @api.model
    def get_market_analysis_api_key(self):
        return _normalize_google_studio_api_key(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._MARKET_ANALYSIS_API_KEY, default="")
        )

    @api.model
    def set_market_analysis_api_key(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            self._MARKET_ANALYSIS_API_KEY, _normalize_google_studio_api_key(value)
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
    def get_external_market_gemini_api_key(self):
        return _normalize_google_studio_api_key(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._EXTERNAL_MARKET_GEMINI_API_KEY, default="")
        )

    @api.model
    def set_external_market_gemini_api_key(self, value):
        self.env["ir.config_parameter"].sudo().set_param(
            self._EXTERNAL_MARKET_GEMINI_API_KEY, _normalize_google_studio_api_key(value)
        )

    @api.model
    def get_external_market_gemini_model(self):
        raw = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(self._EXTERNAL_MARKET_GEMINI_MODEL_KEY, default="gemini-1.5-flash")
        )
        return (raw or "").strip() or "gemini-1.5-flash"

    @api.model
    def set_external_market_gemini_model(self, value):
        model = (value or "").strip() or "gemini-1.5-flash"
        self.env["ir.config_parameter"].sudo().set_param(self._EXTERNAL_MARKET_GEMINI_MODEL_KEY, model)

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

    def _external_intel_canonical_title(self, project):
        """Headline shown at top of external intel (enforced server-side so layout stays consistent)."""
        project.ensure_one()
        client_name = (project.client_name or "").strip() or _("Unknown client")
        today = fields.Date.context_today(project)
        y0 = today.year
        y1 = y0 + 1
        return f"{client_name}: Strategic Intel ({y0}\u2013{y1})"

    def _provider_display_name(self, provider_code):
        return {
            "gemini_direct": _("Google Gemini (direct)"),
            "google_search_api": _("Google Search API"),
            "google_news_rss": _("Google News RSS"),
        }.get(provider_code, provider_code or "")

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

    def _gemini_direct_intel_prompt(self, project, external_snapshot):
        client_name = (project.client_name or "").strip() or "Unknown client"
        industry = project._market_analysis_selection_display("industry") or "target sector"
        contract_type = project._market_analysis_selection_display("contract_type") or "contract"
        title_example = self._external_intel_canonical_title(project)
        return (
            "You are a commercial strategy analyst supporting UAE facilities and soft-services bids.\n\n"
            "Create a competitor-focused strategic intelligence brief for a bid team, written like a polished "
            "internal memo (numbered sections, narrative paragraphs, and clear thematic labels).\n"
            "You do not have live web search results. Use only the INTERNAL_PROJECT_SNAPSHOT JSON inside the payload "
            "(and treat client_website as an optional label only—do not claim you retrieved that website).\n"
            "You may add cautious UAE / sector perspective where it helps the bid; label it clearly when it is not "
            "from the snapshot.\n"
            "Do not invent named contracts, clients, rankings, or audited financials.\n\n"
            "Return strict JSON with exactly these keys: "
            "title, key_contract_wins_focus_areas, good, bad, research_gaps, execution_prompt, strategic_tip, bottom_line.\n"
            "Optional key \"position\" is allowed as a short paragraph (string) for scope/context before section 1.\n\n"
            f"The JSON field \"title\" MUST be exactly this string (including the en dash between years): {json.dumps(title_example)}\n\n"
            "Field requirements:\n"
            "- key_contract_wins_focus_areas: array of strings. Do NOT paste internal scope_mix percentages "
            "(cleaning/security splits) as if they were named contract wins—use the snapshot only to infer where "
            "the competitor likely concentrates effort, framed as cautious narrative. First item(s) should orient the "
            "reader; later items should use \"Theme: paragraph\" when helpful (for example \"Recent Wins: …\", "
            "\"Anchor Clients: …\", \"Technology Edge: …\"). Each string may be several sentences.\n"
            "- good: array of strings for competitive advantages; prefer \"Theme: paragraph\" lines (for example "
            "\"Sustainability Leadership: …\").\n"
            "- bad: array of strings for weaknesses or risks to exploit; prefer \"Theme: paragraph\" lines.\n"
            "- research_gaps: array of short strings listing what still needs validation (optional but preferred).\n"
            "- execution_prompt: one multi-line string that a human can paste into a search-capable tool. Include "
            "placeholders in square brackets such as [Insert Sector] or [Insert Service] where the bid team must "
            "substitute context.\n"
            "- strategic_tip: one multi-line string with concrete bid positioning (you may use short paragraphs or "
            "\"If the client values …\" framing).\n"
            "- bottom_line: one sharp closing sentence.\n\n"
            f"Client name: {client_name}\n"
            f"Sector context: {industry}\n"
            f"Contract context: {contract_type}\n\n"
            "PAYLOAD JSON:\n"
            f"{json.dumps(external_snapshot, indent=2, sort_keys=True)}"
        )

    def _is_direct_gemini_model(self, model_name, api_key):
        model = (model_name or "").strip().lower()
        key = _normalize_google_studio_api_key(api_key)
        return _is_google_ai_studio_gemini_api_key(key) and (
            model.startswith("gemini-") or model.startswith("models/gemini-")
        )

    def _api_key_mismatch_explanation(self, label, raw_key):
        """Explain why a stored key is not valid for generativelanguage.googleapis.com (no secret leakage)."""
        kn = _normalize_google_studio_api_key(raw_key)
        if not kn or _is_google_ai_studio_gemini_api_key(kn):
            return None
        return _(
            "%(label)s: use an API key from Google AI Studio (https://aistudio.google.com/apikey). "
            "It should start with AIza or AQ."
        ) % {"label": label}

    def _gemini_credentials_diagnosis(self, settings):
        """Short hint for UserError when Gemini credentials validation fails (no secrets leaked)."""
        icp = settings.env["ir.config_parameter"].sudo()
        m_key = _normalize_google_studio_api_key(settings.get_market_analysis_api_key())
        ext_key = _normalize_google_studio_api_key(settings.get_external_market_gemini_api_key())
        leg = _normalize_google_studio_api_key(icp.get_param(_LEGACY_EXTERNAL_MARKET_API_KEY_PARAM, default=""))
        m_model = (settings.get_market_analysis_model() or "").strip().lower()
        ext_model = (settings.get_external_market_gemini_model() or "").strip().lower()
        hints = []
        if not m_key and not ext_key and not leg:
            hints.append(_("No API key is stored yet under AI Market Analysis or External Market Data."))
        else:
            for label, k in (
                (_("AI Market Analysis"), m_key),
                (_("External Market Data"), ext_key),
                (_("legacy External API key field"), leg),
            ):
                msg = self._api_key_mismatch_explanation(label, k)
                if msg:
                    hints.append(msg)
        for label, m in ((_("AI Market Analysis"), m_model), (_("External Market Data"), ext_model)):
            if m and not (m.startswith("gemini-") or m.startswith("models/gemini-")):
                hints.append(
                    _("Under %(label)s the model must look like gemini-1.5-flash (stored value contains: %(frag)s).")
                    % {"label": label, "frag": m[:40]}
                )
        if not hints:
            hints.append(
                _("Confirm the model id starts with gemini- and the key is from Google AI Studio (AIza… or AQ.…).")
            )
        return " ".join(hints)

    def _raise_user_error_from_gemini_http(self, http_exc, body, requested_model):
        code = http_exc.code
        snippet = ""
        if body:
            try:
                parsed = json.loads(body)
                err = parsed.get("error") or {}
                snippet = (err.get("message") or "").strip()
            except (json.JSONDecodeError, TypeError, AttributeError):
                snippet = (body or "").strip()
        snippet = (snippet or _("No details returned."))[:900]
        if code == 429:
            raise UserError(
                _(
                    "Google Gemini refused the request (HTTP %(code)s): quota or rate limit was exceeded "
                    "for model \"%(model)s\".\n\n"
                    "If the API text mentions the free tier with limit: 0, this Google Cloud project has no free "
                    "Generative Language quota for that model—a new API key in the same project will not fix it. "
                    "Open Google AI Studio → Rate limits (or Usage), find a model that still shows non-zero RPM/RPD "
                    "for your tier, and set that exact model id in Bid Board Settings (for example gemini-2.5-flash or "
                    "gemini-2.5-flash-lite; names depend on your account).\n\n"
                    "Otherwise you may have hit a daily or per-minute cap: wait until quotas reset (often midnight "
                    "Pacific for daily caps), try a lighter model, or enable billing on the Cloud project linked to "
                    "this key for paid-tier limits.\n\n"
                    "References: https://ai.google.dev/gemini-api/docs/rate-limits — "
                    "https://ai.dev/rate-limit\n\n"
                    "API message (truncated): %(snippet)s"
                )
                % {"code": code, "model": requested_model or "?", "snippet": snippet}
            )
        raise UserError(
            _("Gemini request failed with HTTP %(code)s: %(details)s")
            % {"code": code, "details": snippet}
        )

    def _call_gemini_generate_content(
        self, api_key, model_name, timeout_seconds, prompt_text, response_mime_json=False
    ):
        model = (model_name or "gemini-1.5-flash").strip()
        if model.startswith("models/"):
            model = model.split("/", 1)[1]
        safe_key = quote(str(api_key), safe="")
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={safe_key}"
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
            self._raise_user_error_from_gemini_http(exc, body, model)
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

    def _external_brief_push_body_lines(self, lines, items):
        """Append narrative body: one paragraph per item, blank line between items."""
        first = True
        for raw in items:
            chunk = (raw or "").strip()
            if not chunk:
                continue
            if not first:
                lines.append("")
            lines.append(chunk)
            first = False

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
            lines.append(position)
            lines.append("")

        section_num = 1
        if wins_focus:
            lines.append(
                _("%(n)d. Key Contract Wins & Focus Areas")
                % {"n": section_num}
            )
            section_num += 1
            lines.append("")
            self._external_brief_push_body_lines(lines, wins_focus)
            lines.append("")

        if strengths:
            lines.append(
                _("%(n)d. The \"Good\" (Their Competitive Advantages)")
                % {"n": section_num}
            )
            section_num += 1
            lines.append("")
            self._external_brief_push_body_lines(lines, strengths)
            lines.append("")

        if weak_points:
            lines.append(
                _("%(n)d. The \"Bad\" (Potential Weaknesses to Capitalize On)")
                % {"n": section_num}
            )
            section_num += 1
            lines.append("")
            self._external_brief_push_body_lines(lines, weak_points)
            lines.append("")

        if research_gaps:
            lines.append(_("Research gaps to validate"))
            lines.append("")
            self._external_brief_push_body_lines(lines, research_gaps)
            lines.append("")

        if execution_prompt:
            lines.append(_("Execution Prompt for Deep Research"))
            lines.append("")
            intro = _(
                "Use this prompt in a dedicated search tool or an AI with live web access to get the "
                "\"nitty-gritty\" details for your specific sector:"
            )
            lines.append(intro)
            lines.append("")
            lines.append(execution_prompt)
            lines.append("")

        if strategic_tip:
            lines.append(_("Strategic Tip for Your Bid"))
            lines.append("")
            lines.append(strategic_tip)
            lines.append("")

        if bottom_line:
            lines.append(bottom_line.strip())

        return "\n".join(lines).strip()

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
            raise UserError(_("Gemini returned an unexpected market analysis payload."))
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

    def _market_analysis_gemini_credentials(self, settings):
        """Prefer AI Market Analysis key/model; else legacy external param; else External Gemini fields."""
        icp = settings.env["ir.config_parameter"].sudo()
        m_key = _normalize_google_studio_api_key(settings.get_market_analysis_api_key())
        if not m_key:
            m_key = _normalize_google_studio_api_key(
                icp.get_param(_LEGACY_EXTERNAL_MARKET_API_KEY_PARAM, default="")
            )
        m_model = (settings.get_market_analysis_model() or "").strip()
        if self._is_direct_gemini_model(m_model, m_key):
            return m_key, m_model
        ext_key = _normalize_google_studio_api_key(settings.get_external_market_gemini_api_key())
        ext_model = (settings.get_external_market_gemini_model() or "").strip()
        if self._is_direct_gemini_model(ext_model, ext_key):
            return ext_key, ext_model
        return m_key, m_model

    def analyze_project(self, project):
        project.ensure_one()
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        if not settings.get_market_analysis_enabled():
            raise UserError(_("Enable AI market analysis in Bid Board Settings before generating it."))
        api_key, model_name = self._market_analysis_gemini_credentials(settings)
        if not self._is_direct_gemini_model(model_name, api_key):
            raise UserError(
                _(
                    "AI market analysis uses Google Gemini only. Set a Google AI Studio API key (AIza… or AQ…) "
                    "and a Gemini model (for example gemini-2.0-flash) under AI Market Analysis, **or** "
                    "under External Market Data if you use the same key there."
                )
            )
        timeout_seconds = settings.get_market_analysis_timeout_seconds()
        snapshot = project._market_analysis_build_snapshot()
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._user_prompt(snapshot)},
        ]
        prompt_text = (messages[0].get("content") or "").strip() + "\n\n" + (
            messages[1].get("content") or ""
        ).strip()
        content = self._call_gemini_generate_content(
            api_key, model_name, timeout_seconds, prompt_text, response_mime_json=True
        )
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

    def _external_gemini_credentials(self, settings):
        """Prefer External Gemini fields; else legacy external API param; else AI Market Analysis."""
        icp = settings.env["ir.config_parameter"].sudo()
        ext_key = _normalize_google_studio_api_key(settings.get_external_market_gemini_api_key())
        if not ext_key:
            ext_key = _normalize_google_studio_api_key(
                icp.get_param(_LEGACY_EXTERNAL_MARKET_API_KEY_PARAM, default="")
            )
        ext_model = (settings.get_external_market_gemini_model() or "").strip()
        if self._is_direct_gemini_model(ext_model, ext_key):
            return ext_key, ext_model
        m_key = _normalize_google_studio_api_key(settings.get_market_analysis_api_key())
        m_model = (settings.get_market_analysis_model() or "").strip()
        if self._is_direct_gemini_model(m_model, m_key):
            return m_key, m_model
        return ext_key, ext_model

    def _collect_external_market_data_gemini_direct(self, project):
        project.ensure_one()
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        timeout_seconds = settings.get_external_market_timeout_seconds()
        api_key, model_name = self._external_gemini_credentials(settings)
        if not self._is_direct_gemini_model(model_name, api_key):
            diag = self._gemini_credentials_diagnosis(settings)
            raise UserError(
                _(
                    "External market intelligence needs a Google AI Studio API key (AIza… or AQ…) and a "
                    "Gemini model id (for example gemini-2.0-flash).\n\n"
                    "Set them under Bid Board Settings → External Market Data, **or** under AI Market Analysis "
                    "(the same key and Gemini model are reused when the External Market Data fields are empty).\n\n"
                    "Details: %(diag)s"
                )
                % {"diag": diag}
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
        parsed["title"] = self._external_intel_canonical_title(project)
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
        return self._collect_external_market_data_gemini_direct(project)

    def analyze_project_combined(self, project):
        project.ensure_one()
        if project.market_external_status != "ready":
            raise UserError(_("Fetch external market data first, then run combined analysis."))
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        if not settings.get_market_analysis_enabled():
            raise UserError(_("Enable AI market analysis in Bid Board Settings before generating it."))
        api_key, model_name = self._market_analysis_gemini_credentials(settings)
        if not self._is_direct_gemini_model(model_name, api_key):
            raise UserError(
                _(
                    "AI market analysis uses Google Gemini only. Set a Google AI Studio API key (AIza… or AQ…) "
                    "and a Gemini model under AI Market Analysis, **or** under External Market Data."
                )
            )
        timeout_seconds = settings.get_market_analysis_timeout_seconds()
        snapshot = project._market_analysis_build_snapshot()
        external_snapshot = project._market_analysis_external_snapshot()
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._user_prompt_combined(snapshot, external_snapshot)},
        ]
        prompt_text = (messages[0].get("content") or "").strip() + "\n\n" + (
            messages[1].get("content") or ""
        ).strip()
        content = self._call_gemini_generate_content(
            api_key, model_name, timeout_seconds, prompt_text, response_mime_json=True
        )
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
