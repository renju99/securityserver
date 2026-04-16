"""ICP-backed flags on bid.board.settings for market / external AI (loaded early; keep minimal)."""

from odoo import api, fields, models


class BidBoardSettingsMarketFlags(models.Model):
    _inherit = "bid.board.settings"

    _EXTERNAL_MARKET_GEMINI_DIRECT_KEY = "sales_bid_board.external_market_gemini_direct"

    external_market_gemini_direct = fields.Boolean(
        string="Gemini only (no web search)",
        compute="_compute_external_market_gemini_direct",
        inverse="_inverse_external_market_gemini_direct",
        readonly=False,
        help="When enabled, external strategic intelligence uses Google Gemini with only the bid record "
        "(and optional client website as text). No Serper, Google Search API, or RSS. "
        "Configure the AI API key and Gemini model under Market Analysis.",
    )

    def _compute_external_market_gemini_direct(self):
        for rec in self:
            rec.external_market_gemini_direct = rec.get_external_market_gemini_direct()

    def _inverse_external_market_gemini_direct(self):
        for rec in self:
            rec.set_external_market_gemini_direct(bool(rec.external_market_gemini_direct))

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
