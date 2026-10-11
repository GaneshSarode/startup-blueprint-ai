"""
test_latency_optimization.py
Comprehensive automated test suite validating latency optimizations,
CrossEncoder grading, JSON extraction resilience, parallel section execution,
structured timing instrumentation, and streaming SSE event mechanics.
"""

import json
import os
import sys
import threading
import time
import types
from unittest.mock import MagicMock, patch
import pytest

# Path setup
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core"))

# Stub out packages not present in local test environment before importing crag
_google_pkg = sys.modules.get("google") or types.ModuleType("google")
_google_pkg.__path__ = getattr(_google_pkg, "__path__", [])
sys.modules.setdefault("google", _google_pkg)

if "google.generativeai" not in sys.modules:
    _genai_stub = types.ModuleType("google.generativeai")
    _genai_stub.configure = MagicMock()
    _genai_stub.GenerationConfig = MagicMock()
    _genai_stub.GenerativeModel = MagicMock()
    sys.modules["google.generativeai"] = _genai_stub
    setattr(_google_pkg, "generativeai", _genai_stub)

if "google.genai" not in sys.modules:
    _genai_new_stub = types.ModuleType("google.genai")
    _genai_new_stub.Client = MagicMock()
    sys.modules["google.genai"] = _genai_new_stub
    setattr(_google_pkg, "genai", _genai_new_stub)

for _mod in ["chromadb", "ibm_watsonx_ai", "ibm_watsonx_ai.foundation_models",
             "sentence_transformers", "tavily", "groq"]:
    if _mod not in sys.modules:
        _stub = types.ModuleType(_mod)
        if _mod == "chromadb":
            _stub.PersistentClient = MagicMock()
        elif _mod == "ibm_watsonx_ai.foundation_models":
            _stub.ModelInference = MagicMock()
        elif _mod == "sentence_transformers":
            _stub.CrossEncoder = MagicMock()
        elif _mod == "tavily":
            _stub.TavilyClient = MagicMock()
        elif _mod == "groq":
            _stub.Groq = MagicMock()
        sys.modules[_mod] = _stub
        if "." in _mod:
            parent, child = _mod.rsplit(".", 1)
            if parent in sys.modules:
                setattr(sys.modules[parent], child, _stub)

from core.crag import (
    _clean_json_str,
    _find_balanced_json_spans,
    _parse_inr_amount,
    _parse_blueprint_json,
    _gen_budget,
    _gen_investors,
    node_eval_each_doc,
    _select_top_docs,
    node_generate_blueprint,
    _normalize_blueprint,
    run_crag,
)
from models.blueprint import SSEEvent, BlueprintResponse


# ==============================================================================
# 1. JSON Extraction & Currency Parsing Resilience Tests
# ==============================================================================

class TestJsonExtractionAndResilience:
    def test_clean_json_str_strips_comments_and_trailing_commas(self):
        dirty = """
        {
            // Single line comment
            "key1": "value1", /* multi-line
            comment */
            "key2": [1, 2, 3,],
            "key3": 100,
        }
        """
        cleaned = _clean_json_str(dirty)
        data = json.loads(cleaned)
        assert data["key1"] == "value1"
        assert data["key2"] == [1, 2, 3]
        assert data["key3"] == 100

    def test_find_balanced_json_spans(self):
        text = "Conversational preamble with {not json}.\n```json\n{\"real\": [1, 2, 3]}\n```\nExtra notes."
        spans = _find_balanced_json_spans(text)
        assert len(spans) > 0
        parsed = json.loads(spans[0])
        assert parsed == {"real": [1, 2, 3]}

    def test_parse_inr_amount_variations(self):
        assert _parse_inr_amount(250000) == 250000
        assert _parse_inr_amount(250000.5) == 250000
        assert _parse_inr_amount("250000") == 250000
        assert _parse_inr_amount("₹2,50,000") == 250000
        assert _parse_inr_amount("2.5 Lakh") == 250000
        assert _parse_inr_amount("2.5L") == 250000
        assert _parse_inr_amount("1.5 Cr") == 15000000
        assert _parse_inr_amount("1.5 Crore") == 15000000
        assert _parse_inr_amount("Rs. 50,000 / month") == 50000
        assert _parse_inr_amount(None, default=1000) == 1000

    def test_parse_blueprint_json_handles_preamble_and_markdown(self):
        raw_output = """
        Here is the requested Business Model Canvas for your textile startup:
        ```json
        {
            "value_propositions": ["AI matching", "Automated compliance"],
            "customer_segments": ["SME textile exporters"],
            "revenue_streams": ["SaaS subscription"]
        }
        ```
        Let me know if you would like more details!
        """
        parsed = _parse_blueprint_json(raw_output)
        assert isinstance(parsed, dict)
        assert "value_propositions" in parsed
        assert parsed["value_propositions"][0] == "AI matching"

    def test_budget_section_preserves_string_amounts_and_calculates_totals(self):
        mock_budget_dict = {
            "phases": [
                {
                    "name": "Phase 1: MVP & Setup",
                    "items": [
                        {"item": "Cloud Infrastructure", "amount": "₹1,50,000", "description": "Hosting"},
                        {"item": "UI/UX & Frontend", "amount": "2.5L", "description": "Design"}
                    ]
                },
                {
                    "name": "Phase 2: Market Launch",
                    "items": [
                        {"item": "Performance Marketing", "amount": "₹3,00,000", "description": "Growth ads"}
                    ]
                }
            ],
            "assumptions": ["2 developers", "Lean operations"]
        }
        with patch("core.crag._call_section_llm", return_value=mock_budget_dict):
            budget_result = _gen_budget("query brief", "evidence text", MagicMock(), MagicMock())
            assert "phases" in budget_result
            assert len(budget_result["phases"]) == 2
            # Phase 1 items: 150,000 + 250,000 = 400,000
            assert budget_result["phases"][0]["phase_total"] == 400000
            # Phase 2 item: 300,000
            assert budget_result["phases"][1]["phase_total"] == 300000
            # Total 12 months: 700,000
            assert budget_result["total_12_months"] == 700000
            assert "700,000" in budget_result["total_12_months_inr"]

    def test_investors_section_normalizes_synonym_keys(self):
        mock_investors_dict = {
            "investor_landscape": [
                {"type": "Angel Networks", "stage": "Pre-seed", "names": ["Indian Angel Network"]}
            ],
            "relevant_incubators": [
                {"name": "NASSCOM 10k Startups", "focus": "Tech SaaS"}
            ],
            "government_schemes": [
                {"name": "Startup India Seed Fund Scheme", "benefits": "Up to ₹50 Lakhs grant"}
            ],
            "funding_roadmap": [
                {"phase": "Pre-seed", "target": "₹50L"}
            ]
        }
        with patch("core.crag._call_section_llm", return_value=mock_investors_dict):
            investors_result = _gen_investors("query brief", "evidence text", MagicMock(), MagicMock())
            assert "investor_types" in investors_result
            assert len(investors_result["investor_types"]) == 1
            assert "incubators" in investors_result
            assert len(investors_result["incubators"]) == 1
            assert len(investors_result["government_schemes"]) == 1


# ==============================================================================
# 2. Optimized CrossEncoder Grading Tests
# ==============================================================================

class TestCrossEncoderGradingOptimization:
    def test_eval_mode_and_truncation_applied(self):
        # 10 candidate docs, one with excessive length (> 2000 chars)
        docs = [f"Doc {i} content " + "word " * 100 for i in range(5)]
        long_doc = "Very long document text. " * 200  # > 4000 chars
        docs.append(long_doc)

        mock_model = MagicMock()
        mock_reranker = MagicMock()
        mock_reranker.model = mock_model
        # Return predictable logits
        mock_reranker.predict.return_value = [-2.0, -3.5, -4.0, -5.0, -6.0, -1.5]

        scores, raw_logits, confidence, max_logit = node_eval_each_doc(
            "Fintech lending platform in India", docs, mock_reranker
        )

        # Model eval() must have been called
        mock_model.eval.assert_called()

        # Check call args to predict: doc length should be truncated to <= 1500 chars
        call_pairs = mock_reranker.predict.call_args[0][0]
        assert len(call_pairs) == 6
        for query_str, doc_str in call_pairs:
            assert len(doc_str) <= 1500

        # Max logit is -1.5 >= -4.0 (CORRECT)
        assert confidence == "CORRECT"
        assert max_logit == -1.5

    def test_crag_correct_branch_single_pass_guarantee(self):
        docs = [f"Relevant doc {i}" for i in range(6)]
        raw_logits = [-1.0, -2.5, -3.0, -6.0, -8.0, -9.0]
        # _select_top_docs must reuse raw_logits without re-running reranker
        selected = _select_top_docs(docs, raw_logits, top_k=3)
        assert isinstance(selected, str)
        # First doc has highest logit (-1.0)
        assert "Relevant doc 0" in selected


# ==============================================================================
# 3. Parallel Section Execution & Deterministic Assembly Tests
# ==============================================================================

class TestParallelSectionExecution:
    def test_deterministic_assembly_order_and_independent_failures(self):
        # Mock section generators where 'risks' fails but other 5 succeed
        def mock_bmc(*args, **kwargs):
            return {"value_propositions": ["VP1"]}
        def mock_budget(*args, **kwargs):
            return {"phases": [], "total_12_months": 500000}
        def mock_gtm(*args, **kwargs):
            return {"target_market": "India"}
        def mock_investors(*args, **kwargs):
            return {"investor_types": []}
        def mock_competitors(*args, **kwargs):
            return {"competitors": []}
        def mock_risks(*args, **kwargs):
            raise RuntimeError("API timeout on risks section")

        completed_sections = []
        def on_section_complete(sec_name, sec_data):
            completed_sections.append(sec_name)

        with patch("core.crag._gen_bmc", side_effect=mock_bmc), \
             patch("core.crag._gen_budget", side_effect=mock_budget), \
             patch("core.crag._gen_gtm", side_effect=mock_gtm), \
             patch("core.crag._gen_investors", side_effect=mock_investors), \
             patch("core.crag._gen_competitors", side_effect=mock_competitors), \
             patch("core.crag._gen_risks", side_effect=mock_risks):

            blueprint = node_generate_blueprint(
                structured_brief="AI Textile Exporter",
                granite_summary="Policy brief",
                web_context="Market context",
                sector="Fintech",
                model_type="B2B",
                stage="Idea Stage",
                target_city="Pan India",
                groq_client=MagicMock(),
                gpt_oss_client=MagicMock(),
                on_section_complete=on_section_complete,
            )

            # Deterministic order of keys
            expected_keys = ["bmc", "budget", "gtm", "investors", "competitors", "risks", "crag_trace"]
            for k in expected_keys:
                assert k in blueprint

            # 5 successful sections preserved despite risks failing
            assert blueprint["bmc"]["value_propositions"] == ["VP1"]
            assert blueprint["budget"]["total_12_months"] == 500000
            assert "risks" in blueprint.get("failed_sections", [])
            # risks failed gracefully to empty dict
            assert blueprint["risks"] == {} or blueprint["risks"] == {"risks": []}


# ==============================================================================
# 4. Structured Timing & Run CRAG Lifecycle Tests
# ==============================================================================

class TestCRAGTimingAndStreamingLifecycle:
    def test_run_crag_records_detailed_timings_and_id(self):
        mock_reranker = MagicMock()
        mock_reranker.predict.return_value = [-2.0, -3.0]

        mock_rewrite = {
            "structured_brief": "Structured brief",
            "keywords": ["textile", "export"],
            "retrieval_queries": ["textile export"],
            "search_context": "search context"
        }

        with patch("core.crag.node_rewrite_query", return_value=mock_rewrite), \
             patch("core.crag.node_retrieve", return_value=(["Doc 1", "Doc 2"], [{"source": "src1"}, {"source": "src2"}])), \
             patch("core.crag.node_eval_each_doc", return_value=([0.8, 0.7], [-2.0, -3.0], "CORRECT", -2.0)), \
             patch("core.crag.node_generate_summary", return_value="Granite policy brief"), \
             patch("core.crag.node_web_search", return_value=[{"title": "t1", "content": "c1", "url": "u1", "score": 1}]), \
             patch("core.crag.node_generate_blueprint", return_value={
                 "bmc": {"value_propositions": ["VP1"]},
                 "budget": {"phases": [], "total_12_months": 500000},
                 "gtm": {"target_market": "India"},
                 "investors": {"investor_types": []},
                 "competitors": {"competitors": []},
                 "risks": {"risks": []},
                 "crag_trace": {},
                 "_section_timings": {"bmc": 1.2}
             }):

            events_emitted = []
            def track_events(event_type, payload):
                events_emitted.append((event_type, payload.get("stage") or payload.get("node")))

            result = run_crag(
                query="AI textile export SaaS",
                sector="Fintech",
                stage="Idea Stage",
                model_type="B2B",
                target_city="Pan India",
                collections={"text": MagicMock(), "table": MagicMock(), "visual": MagicMock()},
                reranker=mock_reranker,
                granite=MagicMock(),
                tavily=MagicMock(),
                groq_client=MagicMock(),
                gemini_client=MagicMock(),
                gpt_oss_client=MagicMock(),
                event_callback=track_events,
                generation_id="gen-test-1234",
            )

            # Generation ID correlation
            assert result.get("generation_id") == "gen-test-1234"

            # Check timings structure
            timings = result.get("timings", {})
            assert "generation_id" in timings
            assert timings["generation_id"] == "gen-test-1234"
            assert "query_rewrite_s" in timings
            assert "chromadb_retrieve_s" in timings
            assert "crossencoder_grade_s" in timings
            assert "crag_routing_s" in timings
            assert "granite_summary_s" in timings
            assert "tavily_research_s" in timings
            assert "sections_total_wall_s" in timings
            assert "total_end_to_end_s" in timings
            assert timings["total_end_to_end_s"] >= 0

            # Events emitted properly
            event_types = [t[0] for t in events_emitted]
            assert "stage_started" in event_types
            assert "stage_completed" in event_types

    def test_cancellation_event_halts_generation(self):
        cancel_event = threading.Event()
        cancel_event.set()  # Pre-cancelled

        result = run_crag(
            query="Startup idea",
            sector="Fintech",
            stage="Idea Stage",
            model_type="B2B",
            target_city="Pan India",
            collections={"text": MagicMock(), "table": MagicMock(), "visual": MagicMock()},
            reranker=MagicMock(),
            granite=MagicMock(),
            tavily=MagicMock(),
            groq_client=MagicMock(),
            gemini_client=MagicMock(),
            gpt_oss_client=MagicMock(),
            cancel_event=cancel_event
        )
        # Should return early without running retrieval or generation
        assert result.get("confidence") == ""
        assert result.get("should_generate_blueprint") is False


# ==============================================================================
# 5. Focused Regression Tests for Budget Normalization Robustness
# ==============================================================================

class TestBudgetNormalizationRobustness:
    def test_string_budget_items_normalized_to_valid_dicts(self):
        raw_output = {
            "budget": {
                "phases": [
                    {
                        "name": "Phase 1: MVP",
                        "items": [
                            "Cloud Hosting & DevOps: 150000",
                            "UI/UX Design Frontend",
                            "Incorporation and FSSAI Compliance",
                        ]
                    }
                ]
            }
        }
        normalized = _normalize_blueprint(raw_output)
        phases = normalized["budget"]["phases"]
        assert len(phases) == 1
        items = phases[0]["items"]
        assert len(items) == 3

        for it in items:
            assert isinstance(it, dict)
            assert "item" in it
            assert "description" in it
            assert isinstance(it["amount"], (int, float))

        # Check that the string with an embedded number was parsed or given safe amount
        assert items[0]["amount"] == 150000
        assert items[0]["item"] == "Cloud Hosting & DevOps: 150000"
        assert items[1]["amount"] == 0
        assert items[1]["description"] == "UI/UX Design Frontend"

    def test_dict_budget_items_with_invalid_amounts(self):
        raw_output = {
            "budget": {
                "phases": [
                    {
                        "name": "Phase 2: Growth",
                        "items": [
                            {"item": "Server Cluster", "amount": None, "note": "keep this"},
                            {"item": "Ad Spend", "amount": "invalid_string"},
                            {"item": "Hiring", "amount": "₹2,50,000"},
                            {"item": "Legal Reserve", "amount": "1.5L"},
                        ]
                    }
                ]
            }
        }
        normalized = _normalize_blueprint(raw_output)
        phase = normalized["budget"]["phases"][0]
        items = phase["items"]

        assert items[0]["amount"] == 0
        assert items[0].get("note") == "keep this"  # Preserved extra valid field
        assert items[1]["amount"] == 0
        assert items[2]["amount"] == 250000
        assert items[3]["amount"] == 150000

        # Totals calculated correctly without crashing
        assert phase["total"] == 400000
        assert phase["phase_total"] == 400000
        assert normalized["budget"]["total_12_months"] == 400000

    def test_malformed_phase_entries(self):
        raw_output = {
            "budget": {
                "phases": [
                    "Phase 1: Seed Setup - ₹5,00,000",
                    {"name": "Phase 2: Scaling", "items": "A single string instead of a list"},
                    123456,
                ]
            }
        }
        normalized = _normalize_blueprint(raw_output)
        phases = normalized["budget"]["phases"]
        assert len(phases) == 3

        # Every phase must be a dictionary with required schema keys
        for p in phases:
            assert isinstance(p, dict)
            assert "name" in p
            assert "duration" in p
            assert isinstance(p["items"], list)
            assert "total" in p
            assert "phase_total" in p

        # Check phase 1 parsed string phase
        assert phases[0]["name"] == "Phase 1: Seed Setup - ₹5,00,000"
        assert phases[0]["total"] == 500000

        # Check phase 2 normalized string item into list
        assert len(phases[1]["items"]) == 1
        assert phases[1]["items"][0]["item"] == "A single string instead of a list"

        # Check overall budget total
        assert normalized["budget"]["total_12_months"] >= 500000
        assert "total_12_months_inr" in normalized["budget"]


class TestSectionNormalizationAndGrounding:
    def test_investors_section_unnests_funding_wrapper_and_preserves_schemes(self):
        raw_output = {
            "funding": {
                "funding_roadmap": [
                    {"stage": "Pre-Seed", "timeline": "Month 1-3", "source": "SISFS", "amount": "₹20L"}
                ],
                "government_schemes": [
                    {"name": "SISFS", "benefit": "Prototype grant", "amount": "₹20L"}
                ]
            }
        }
        normalized = _normalize_blueprint(raw_output)
        assert "investors" in normalized
        assert "funding" in normalized
        assert len(normalized["investors"]["funding_roadmap"]) == 1
        assert normalized["investors"]["funding_roadmap"][0]["stage"] == "Pre-Seed"
        assert len(normalized["investors"]["government_schemes"]) == 1
        assert normalized["investors"]["government_schemes"][0]["name"] == "SISFS"

    def test_competitors_market_share_normalization_and_differentiators(self):
        raw_output = {
            "competitors": [
                {"name": "Comp 1", "market_share": "7%", "strength": "Scale"},
                {"name": "Comp 2", "market_share": "25%%", "strength": "Brand"},
            ],
            "differentiators": ["AI-first architecture", "Instant settlement"],
            "gaps": ["High latency in existing tools"],
        }
        normalized = _normalize_blueprint(raw_output)
        comps = normalized["competitors"]["competitors"]
        assert len(comps) == 2
        # Clean market share: never double percent
        assert comps[0]["market_share"] == "7%"
        assert comps[1]["market_share"] == "25%"
        # Differentiators and gaps preserved from synonym keys
        assert len(normalized["competitors"]["our_differentiators"]) == 2
        assert "AI-first architecture" in normalized["competitors"]["our_differentiators"]
        assert len(normalized["competitors"]["market_gaps"]) == 1

    def test_risks_severity_and_probability_enums_normalized(self):
        raw_output = {
            "risks": [
                {"category": "Market", "severity": "very high", "probability": "Low chance", "risk": "Adoption risk"},
                {"category": "Tech", "severity": "minimal", "probability": "high likelihood", "risk": "Uptime risk"},
            ]
        }
        normalized = _normalize_blueprint(raw_output)
        risks = normalized["risks"]["risks"]
        assert len(risks) == 2
        assert risks[0]["severity"] == "HIGH"
        assert risks[0]["probability"] == "LOW"
        assert risks[1]["severity"] == "LOW"
        assert risks[1]["probability"] == "HIGH"

