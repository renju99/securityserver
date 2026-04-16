import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sales_bid_board")
class TestBidMarketAnalysis(TransactionCase):
    def setUp(self):
        super().setUp()
        self.settings = self.env["bid.board.settings"].sudo().get_singleton()
        self.settings.set_market_analysis_enabled(True)
        self.settings.set_market_analysis_provider("openrouter")
        self.settings.set_market_analysis_model("qwen/qwen-2.5-7b-instruct:free")
        self.settings.set_market_analysis_api_key("test-key")
        self.settings.set_market_analysis_timeout_seconds(30)
        self.settings.set_market_analysis_prompt_version("v-test")
        self.settings.set_market_analysis_prompt_template("")
        self.settings.set_external_market_enabled(False)
        self.settings.set_external_market_gemini_direct(False)
        self.settings.set_external_market_provider("google_search_api")
        self.settings.set_external_market_api_key("external-test-key")
        self.settings.set_external_market_news_limit(5)
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

    def test_market_analysis_snapshot_uses_internal_fields(self):
        snapshot = self.project._market_analysis_build_snapshot()

        self.assertEqual(snapshot["project_name"], "Airport IFM Tender")
        self.assertEqual(snapshot["industry"], "Facilities Management")
        self.assertEqual(snapshot["contract_type"], "IFM")
        self.assertEqual(snapshot["scope_breakdown_percent"]["cleaning"], 40.0)
        self.assertEqual(snapshot["scope_breakdown_percent"]["security"], 25.0)
        self.assertNotIn("market_analysis_output_json", snapshot)
        self.assertIn("scorecard_signals", snapshot)

    def test_build_external_queries_include_company_research_queries(self):
        queries = self.env["bid.market.analysis.service"]._build_external_queries(self.project)
        query_texts = [row["query"] for row in queries]

        self.assertTrue(any("official website" in query for query in query_texts))
        self.assertTrue(any("services" in query for query in query_texts))
        self.assertTrue(any("projects clients" in query or "projects" in query for query in query_texts))
        self.assertTrue(any("case studies" in query for query in query_texts))
        self.assertTrue(any("awards news" in query for query in query_texts))

    def test_build_external_queries_prefer_client_domain_when_set(self):
        self.project.client_website = "https://exampleclient.ae"

        queries = self.env["bid.market.analysis.service"]._build_external_queries(self.project)
        query_texts = [row["query"] for row in queries]

        self.assertTrue(all(query.startswith("site:exampleclient.ae ") for query in query_texts))
        self.assertTrue(any("about" in query for query in query_texts))
        self.assertTrue(any("services" in query for query in query_texts))

    def test_analyze_project_parses_structured_response_and_uses_prompt_version(self):
        service = self.env["bid.market.analysis.service"]
        fake_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
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
                    }
                }
            ]
        }
        with patch.object(type(service), "_call_openrouter", return_value=fake_response) as mocked_call:
            values = service.analyze_project(self.project)

        args = mocked_call.call_args[0]
        messages = args[3]
        self.assertIn("Prompt version: v-test", messages[1]["content"])
        self.assertEqual(values["market_analysis_summary"], "Competitive but winnable opportunity.")
        self.assertIn("- Large multi-year contract value.", values["market_analysis_opportunity_signals"])
        self.assertEqual(values["market_analysis_confidence"], "high")
        self.assertEqual(values["market_analysis_model"], "qwen/qwen-2.5-7b-instruct:free")
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

    def test_collect_external_market_data_curates_summary_and_hides_raw_queries(self):
        service = self.env["bid.market.analysis.service"]
        self.settings.set_external_market_enabled(True)
        fake_items = [
            {
                "title": "Example Client",
                "link": "https://exampleclient.ae",
                "published_at": "",
                "source": "Google Knowledge Graph",
                "snippet": "Facilities management company in Dubai. Headquarters: Dubai; Website: exampleclient.ae",
            },
            {
                "title": "Sales & Commercial Manager - Berkeley Services UAE LLC - LinkedIn",
                "link": "https://linkedin.com/jobs/view/123",
                "published_at": "",
                "source": "LinkedIn",
                "snippet": "Hiring job post.",
            },
            {
                "title": "UAE real estate sector enters 2026 from position of strength",
                "link": "https://www.zawya.com/en/markets/real-estate/uae-real-estate-sector",
                "published_at": "2026-01-15",
                "source": "Zawya",
                "snippet": "The UAE real estate market continues to show strong demand and project activity.",
            },
            {
                "title": "Dubai Housing Market 2026",
                "link": "https://youtube.com/watch?v=demo",
                "published_at": "",
                "source": "YouTube",
                "snippet": "Video commentary.",
            },
        ]
        fake_brief_response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "title": "Example Client - Strategic Intel",
                                "position": "Established FM operator in Dubai with evidence of local operating presence.",
                                "key_contract_wins_focus_areas": [
                                    "No named contracts were verified in the fetched evidence.",
                                    "Company profile evidence points to Dubai-based FM operations.",
                                ],
                                "good": [
                                    "Visible company profile data was found.",
                                    "Market backdrop indicates active sector demand.",
                                ],
                                "bad": [
                                    "Fetched evidence did not confirm flagship contracts.",
                                ],
                                "research_gaps": [
                                    "Named reference clients still need direct validation.",
                                ],
                                "execution_prompt": (
                                    "Act as a commercial strategy analyst for UAE FM bids.\\n"
                                    "Provide sector-specific SWOT for Example Client in IFM.\\n"
                                    "List top contracts and renewal timing from public evidence.\\n"
                                    "Assess pricing posture (premium vs share-buying).\\n"
                                    "Highlight delivery or workforce risk signals from recent sources."
                                ),
                                "strategic_tip": "Position the bid around proven delivery controls until reference accounts are verified.",
                                "bottom_line": "Useful initial signal, but contract proof still needs direct verification.",
                            }
                        )
                    }
                }
            ]
        }
        fetched_page_text = (
            "Example Client provides integrated facilities management services in Dubai, "
            "including cleaning, manpower, and technical operations. Case studies mention "
            "large multi-site delivery programs and aviation-related service environments."
        )
        with patch.object(type(service), "_fetch_google_search_api", return_value=fake_items), patch.object(
            type(service), "_fetch_webpage_text", return_value=fetched_page_text
        ), patch.object(type(service), "_call_openrouter", return_value=fake_brief_response) as mocked_call:
            values = service.collect_external_market_data(self.project)

        messages = mocked_call.call_args[0][3]
        self.assertEqual(values["market_external_provider"], "Google Search API")
        self.assertFalse(values["market_external_query"])
        self.assertIn("Example Client - Strategic Intel", values["market_external_summary"])
        self.assertIn("Position:", values["market_external_summary"])
        self.assertIn("Key Contract Wins & Focus Areas:", values["market_external_summary"])
        self.assertIn("The Good:", values["market_external_summary"])
        self.assertIn("The Bad:", values["market_external_summary"])
        self.assertIn("Research Gaps:", values["market_external_summary"])
        self.assertIn("Execution Prompt for Deep Research:", values["market_external_summary"])
        self.assertIn("Strategic Tip for Your Bid:", values["market_external_summary"])
        self.assertIn("Bottom line:", values["market_external_summary"])
        self.assertIn("aviation-related service environments", messages[1]["content"])
        self.assertNotIn("LinkedIn", values["market_external_summary"])
        self.assertNotIn("YouTube", values["market_external_summary"])

    def test_collect_external_gemini_direct_skips_search_apis(self):
        service = self.env["bid.market.analysis.service"]
        self.settings.set_external_market_enabled(True)
        self.settings.set_external_market_gemini_direct(True)
        self.settings.set_external_market_provider("google_search_api")
        self.settings.set_market_analysis_api_key("AIza-test-key-for-gemini-direct")
        self.settings.set_market_analysis_model("gemini-2.5-flash-lite")
        gemini_json = json.dumps(
            {
                "title": "Example Client - Direct Gemini",
                "position": "Internal snapshot only; no web search.",
                "key_contract_wins_focus_areas": ["Snapshot mentions IFM scope mix."],
                "good": ["Structured internal scoring is available."],
                "bad": ["No live web evidence in this mode."],
                "research_gaps": ["Validate assumptions with primary sources."],
                "execution_prompt": "Deep research prompt lines.",
                "strategic_tip": "Anchor pricing to internal scorecard signals.",
                "bottom_line": "Useful orientation from internal fields only.",
            }
        )
        with patch.object(
            type(service), "_fetch_google_search_api", side_effect=AssertionError("Serper must not be called")
        ), patch.object(
            type(service), "_call_gemini_generate_content", return_value=gemini_json
        ) as mocked_gemini:
            values = service.collect_external_market_data(self.project)

        self.assertTrue(mocked_gemini.called)
        self.assertEqual(values["market_external_provider"], "Google Gemini (direct)")
        self.assertIn("Example Client - Direct Gemini", values["market_external_summary"])
        self.assertIn("Key Contract Wins & Focus Areas:", values["market_external_summary"])
