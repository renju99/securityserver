import io
import json
import re
from unittest.mock import patch
from urllib import error as urllib_error
from urllib import request as urllib_request

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sales_bid_board")
class TestBidMarketAnalysis(TransactionCase):
    def setUp(self):
        super().setUp()
        self.settings = self.env["bid.board.settings"].sudo().get_singleton()
        self.settings.set_market_analysis_enabled(True)
        self.settings.set_market_analysis_model("gemini-1.5-flash")
        self.settings.set_market_analysis_api_key("AIza-test-market-analysis-key")
        self.settings.set_market_analysis_timeout_seconds(30)
        self.settings.set_market_analysis_prompt_version("v-test")
        self.settings.set_market_analysis_prompt_template("")
        self.settings.set_external_market_enabled(False)
        self.settings.set_external_market_gemini_api_key("")
        self.settings.set_external_market_gemini_model("gemini-1.5-flash")
        self.settings.set_external_market_timeout_seconds(20)
        self.project = self.env["bid.project"].create(
            {
                "name": "Airport IFM Tender",
                "client_name": "Example Client",
                "emirate": "dubai",
                "industry": "facilities_management",
                "contract_duration": "3y",
                "contract_value": 3600000.0,
                "contract_type": "ifm",
                "threshold": "high",
                "description": "Integrated facilities management opportunity.",
                "progress": "Bid pack under review.",
                "scope_cleaning": 40.0,
                "scope_maintenance": 35.0,
                "scope_security": 25.0,
                "kpi_penalty_mechanism": "Penalties capped at 5% of monthly invoice.",
            }
        )

    def test_market_analysis_api_key_read_normalizes_quotes_and_bom(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("sales_bid_board.market_analysis_api_key", '\ufeff"AIza-test-normalize"')
        self.assertEqual(self.settings.get_market_analysis_api_key(), "AIza-test-normalize")

    def test_clearing_external_gemini_api_key_via_write_persists_empty(self):
        """Clearing the External Gemini key in the UI must clear storage so AI Market Analysis can be reused."""
        self.settings.set_external_market_gemini_api_key("AIza-should-be-cleared")
        self.assertEqual(self.settings.get_external_market_gemini_api_key(), "AIza-should-be-cleared")
        self.settings.write({"external_market_gemini_api_key": ""})
        self.assertEqual(self.settings.get_external_market_gemini_api_key(), "")

    def test_clearing_market_analysis_api_key_via_write_persists_empty(self):
        self.settings.set_market_analysis_api_key("AIza-clear-me")
        self.settings.write({"market_analysis_api_key": ""})
        self.assertEqual(self.settings.get_market_analysis_api_key(), "")

    def test_market_analysis_snapshot_uses_internal_fields(self):
        snapshot = self.project._market_analysis_build_snapshot()

        self.assertEqual(snapshot["project_name"], "Airport IFM Tender")
        self.assertEqual(snapshot["industry"], "Facilities Management")
        self.assertEqual(snapshot["contract_type"], "IFM")
        self.assertEqual(snapshot["scope_breakdown_percent"]["cleaning"], 40.0)
        self.assertEqual(snapshot["scope_breakdown_percent"]["security"], 25.0)
        self.assertNotIn("market_analysis_output_json", snapshot)
        self.assertIn("scorecard_signals", snapshot)

    def test_analyze_project_parses_structured_response_and_uses_prompt_version(self):
        service = self.env["bid.market.analysis.service"]
        gemini_payload = json.dumps(
            {
                "summary": "Competitive but winnable opportunity.",
                "opportunity_signals": [
                    "Large multi-year contract value.",
                    "Balanced IFM scope mix.",
                ],
                "risk_signals": ["Penalty exposure needs review."],
                "competition_view": "Likely moderate competition.",
                "pricing_pressure_view": "Medium pricing pressure expected.",
                "bid_recommendation_support": "Internal score supports proceeding.",
                "missing_information": ["Named competitor list"],
                "confidence_level": "high",
                "disclaimer": "Based only on internal project fields.",
            }
        )
        with patch.object(
            type(service), "_call_gemini_generate_content", return_value=gemini_payload
        ) as mocked_call:
            values = service.analyze_project(self.project)

        args = mocked_call.call_args[0]
        prompt_text = args[3]
        self.assertIn("Prompt version: v-test", prompt_text)
        self.assertEqual(values["market_analysis_summary"], "Competitive but winnable opportunity.")
        self.assertIn("- Large multi-year contract value.", values["market_analysis_opportunity_signals"])
        self.assertEqual(values["market_analysis_confidence"], "high")
        self.assertEqual(values["market_analysis_model"], "gemini-1.5-flash")
        self.assertIn('"project_name": "Airport IFM Tender"', values["market_analysis_input_json"])

    def test_action_generate_market_analysis_marks_failure_on_user_error(self):
        service = self.env["bid.market.analysis.service"]
        with patch.object(type(service), "analyze_project", side_effect=UserError("Provider limit reached")):
            action = self.project.action_generate_market_analysis()

        values = self.project.read(["market_analysis_status", "market_analysis_last_error"])[0]
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "warning")
        self.assertNotIn("next", action["params"])
        self.assertEqual(values["market_analysis_status"], "failed")
        self.assertIn("Provider limit reached", values["market_analysis_last_error"])

    def test_market_analysis_settings_enable_flags_can_disable(self):
        self.settings.set_market_analysis_enabled(False)
        self.settings.set_external_market_enabled(False)

        self.assertFalse(self.settings.get_market_analysis_enabled())
        self.assertFalse(self.settings.get_external_market_enabled())

    def test_collect_external_market_data_uses_external_gemini_only(self):
        service = self.env["bid.market.analysis.service"]
        self.settings.set_external_market_enabled(True)
        self.settings.set_external_market_gemini_api_key("AIza-test-key-external-gemini")
        self.settings.set_external_market_gemini_model("gemini-1.5-flash")
        gemini_json = json.dumps(
            {
                "title": "Wrong title from model (must be overwritten server-side).",
                "position": "Internal snapshot only; no web search.",
                "key_contract_wins_focus_areas": ["Snapshot mentions IFM scope mix."],
                "good": ["Structured internal scoring is available."],
                "bad": ["No live web evidence in this mode."],
                "research_gaps": ["Validate assumptions with primary sources."],
                "strategic_tip": "Anchor pricing to internal scorecard signals.",
                "bottom_line": "Useful orientation from internal fields only.",
            }
        )
        with patch.object(
            type(service), "_call_gemini_generate_content", return_value=gemini_json
        ) as mocked_gemini:
            values = service.collect_external_market_data(self.project)

        self.assertTrue(mocked_gemini.called)
        args = mocked_gemini.call_args[0]
        self.assertRegex(args[0], r"^(AIza|AQ\.)", "Gemini call must use the external Gemini API key.")
        self.assertEqual(args[1], "gemini-1.5-flash")
        self.assertEqual(values["market_external_provider"], "Google Gemini (direct)")
        self.assertTrue(values.get("market_external_brief_json"))
        summary = values["market_external_summary"]
        self.assertNotIn("Wrong title from model", summary)
        en = "\u2013"
        self.assertRegex(
            summary,
            re.compile(rf"Example Client: Strategic Intel \(\d{{4}}{en}\d{{4}}\)"),
        )
        self.assertIn("Wins & focus", summary)
        self.assertIn("- Snapshot mentions IFM scope mix.", summary)
        self.assertNotIn("Execution Prompt", summary)
        self.assertIn("Bid tip", summary)
        self.project.write(values)
        self.assertIn("Wins & focus", self.project.market_external_summary)
        snap = self.project._market_analysis_external_snapshot()
        self.assertIn("strategic_brief", snap)
        self.assertNotIn("summary", snap)

    def test_external_intel_clamping_shortens_verbose_model_output(self):
        service = self.env["bid.market.analysis.service"]
        long = "word " * 60
        parsed = {
            "title": "ignored",
            "key_contract_wins_focus_areas": [long + " more words after cap.", "short"],
            "good": ["ok"],
            "bad": ["n"],
            "research_gaps": ["g"],
            "strategic_tip": "First sentence here. Second sentence stays. Third sentence must be dropped.",
            "bottom_line": "Closing only. Extra sentence should be removed by clamp.",
            "execution_prompt": "must not appear in formatted summary",
        }
        clamped = service._clamp_external_intel_brief_dict(parsed)
        self.assertNotIn("execution_prompt", clamped)
        self.assertLessEqual(len(clamped["key_contract_wins_focus_areas"][0]), 135)
        self.assertNotIn("Third sentence", clamped["strategic_tip"])
        self.assertNotIn("Extra sentence", clamped["bottom_line"])
        summary = service._format_external_brief(clamped)
        self.assertNotIn("Execution Prompt", summary)
        self.assertIn("Wins & focus", summary)

    def test_collect_external_requires_external_gemini_credentials(self):
        service = self.env["bid.market.analysis.service"]
        self.settings.set_market_analysis_api_key("sk-not-google")
        self.settings.set_market_analysis_model("vendor/other-model")
        self.settings.set_external_market_enabled(True)
        self.settings.set_external_market_gemini_api_key("")
        self.settings.set_external_market_gemini_model("gemini-1.5-flash")
        with self.assertRaises(UserError):
            service.collect_external_market_data(self.project)

    def test_external_gemini_reuses_market_analysis_aiza_when_external_key_empty(self):
        """If External Gemini key is empty but AI Market Analysis has AIza + Gemini, use that pair."""
        service = self.env["bid.market.analysis.service"]
        self.settings.set_external_market_enabled(True)
        self.settings.set_external_market_gemini_api_key("")
        self.settings.set_external_market_gemini_model("gemini-1.5-flash")
        self.settings.set_market_analysis_api_key("AIza-shared-key-test")
        self.settings.set_market_analysis_model("gemini-1.5-flash")
        gemini_json = json.dumps(
            {
                "title": "Brief",
                "good": ["ok"],
                "bad": [],
                "key_contract_wins_focus_areas": [],
                "research_gaps": [],
                "strategic_tip": "y",
                "bottom_line": "z",
            }
        )
        with patch.object(
            type(service), "_call_gemini_generate_content", return_value=gemini_json
        ) as mocked:
            service.collect_external_market_data(self.project)
        args = mocked.call_args[0]
        self.assertEqual(args[0], "AIza-shared-key-test")
        self.assertEqual(args[1], "gemini-1.5-flash")

    def test_gemini_http_429_raises_guidance_user_error(self):
        service = self.env["bid.market.analysis.service"]
        body = b'{"error":{"code":429,"message":"Quota exceeded for test"}}'
        http_exc = urllib_error.HTTPError(
            "https://generativelanguage.googleapis.com/v1beta/models/x:generateContent",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(body),
        )

        def _raise(*_a, **_kw):
            raise http_exc

        with patch.object(urllib_request, "urlopen", side_effect=_raise):
            with self.assertRaises(UserError) as cm:
                service._call_gemini_generate_content(
                    "AIza-test", "gemini-2.0-flash", 30, "{}", response_mime_json=True
                )
        err = str(cm.exception).lower()
        self.assertIn("quota", err)
        self.assertIn("rate limit", err)
        self.assertIn("gemini-2.5-flash", err)

    def test_collect_external_usererror_diagnosis_non_aiza_key(self):
        service = self.env["bid.market.analysis.service"]
        self.settings.set_external_market_enabled(True)
        self.settings.set_external_market_gemini_api_key("")
        self.settings.set_external_market_gemini_model("gemini-1.5-flash")
        self.settings.set_market_analysis_api_key("not-a-google-ai-studio-key-12345")
        self.settings.set_market_analysis_model("vendor/other-model")
        with self.assertRaises(UserError) as cm:
            service.collect_external_market_data(self.project)
        err = str(cm.exception)
        self.assertIn("Google AI Studio", err)
        self.assertRegex(err, r"AIza|AQ\.")

    def test_aq_api_key_accepted_for_gemini_credentials(self):
        """Google AI Studio can issue AQ.… keys; they must pass the same checks as AIza keys."""
        service = self.env["bid.market.analysis.service"]
        self.assertTrue(
            service._is_direct_gemini_model("gemini-1.5-flash", "AQ.Ab8RN6FakeSuffixForTest")
        )
        self.settings.set_market_analysis_api_key("")
        self.settings.set_market_analysis_model("gemini-1.5-flash")
        self.settings.set_external_market_gemini_api_key("AQ.Ab8RN6FakeSuffixForTest")
        self.settings.set_external_market_gemini_model("gemini-1.5-flash")
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        self.assertIsNone(
            service._api_key_mismatch_explanation("External Market Data", "AQ.Ab8RN6FakeSuffixForTest")
        )
        diag = service._gemini_credentials_diagnosis(settings)
        self.assertIn("gemini", diag.lower())
        self.assertNotIn("sk-", diag.lower())
