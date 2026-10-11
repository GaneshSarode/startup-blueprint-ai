"""
Tests for Blueprint UI Alignment, Section Generation, Schemas, and Grounding.
Covers:
- Root cause of the Funding failure (nested 'funding' wrapper and unnesting)
- Competitors market share percentage formatting ('7%' not '7% %')
- Competitors preservation of differentiators and market gaps
- BMC 9-block validation and synonyms
- Budget deterministic arithmetic calculation and string item handling
- Risks severity and probability enums normalization
- CRAG trace document path sanitization
- Single section retry endpoint
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure backend and core are in python path
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "core"))

from core.crag import _normalize_blueprint, _is_section_valid, run_crag
from models.blueprint import (
    BMCSection,
    BudgetSection,
    GTMSection,
    FundingSection,
    CompetitorsSection,
    RisksSection,
    CRAGTraceSection,
    RetrySectionRequest,
)


class TestFundingFailureRootCause:
    def test_funding_nested_wrapper_is_properly_unwrapped(self):
        """
        The production failure occurred because the LLM wrapped the funding response in
        {"funding": {"funding_roadmap": [...], "government_schemes": [...]}}.
        Previously, the normalizer looked for data["government_schemes"] at root, found [],
        and marked funding as failed.
        """
        raw_sections = {
            "funding": {
                "funding": {
                    "funding_roadmap": [
                        {"stage": "Pre-seed", "source": "Angel / SISFS", "amount": "₹20,00,000", "use_of_funds": "MVP"}
                    ],
                    "government_schemes": [
                        {
                            "name": "Startup India Seed Fund Scheme (SISFS)",
                            "administering_agency": "DPIIT",
                            "type": "Grant",
                            "amount": "Up to ₹20 Lakhs",
                            "eligibility": "DPIIT recognised startup incorporated within 2 years",
                            "conditions": "Proof of concept validation",
                            "official_url": "https://seedfund.startupindia.gov.in",
                            "source": "DPIIT Guidelines 2024",
                        }
                    ],
                    "investor_landscape": [
                        {"name": "Blume Ventures", "stage_focus": "Seed", "thesis": "B2B SaaS"}
                    ],
                }
            }
        }

        norm = _normalize_blueprint(raw_sections)

        # Must unnest properly under investors/funding
        assert "investors" in norm
        inv = norm["investors"]
        assert len(inv.get("funding_roadmap", [])) == 1
        assert len(inv.get("government_schemes", [])) == 1
        assert inv["government_schemes"][0]["name"] == "Startup India Seed Fund Scheme (SISFS)"
        assert inv["government_schemes"][0]["administering_agency"] == "DPIIT"
        assert inv["government_schemes"][0]["official_url"] == "https://seedfund.startupindia.gov.in"

        # Validate that _is_section_valid approves it
        assert _is_section_valid("investors", inv) is True

    def test_pydantic_funding_schema_validation(self):
        """Test that FundingSection Pydantic model validates rich government scheme data."""
        data = {
            "funding_roadmap": [
                {"stage": "Pre-seed", "source": "SISFS", "amount": "₹20L", "use_of_funds": "Product development"}
            ],
            "government_schemes": [
                {
                    "name": "Credit Guarantee Scheme for Startups (CGSS)",
                    "administering_agency": "NMMTL / DPIIT",
                    "type": "Credit Guarantee / Loan",
                    "amount": "Collateral-free credit up to ₹10 Cr",
                    "eligibility": "DPIIT-recognised startups with viable business model",
                    "conditions": "Through member lending institutions",
                    "application_steps": ["Obtain DPIIT recognition", "Apply via partner bank"],
                    "official_url": "https://www.startupindia.gov.in",
                    "source": "CGSS Notification",
                }
            ],
            "investor_landscape": [
                {"name": "Peak XV Surge", "stage_focus": "Seed", "thesis": "Early tech ventures"}
            ],
        }
        validated = FundingSection(**data)
        assert len(validated.government_schemes) == 1
        assert validated.government_schemes[0].administering_agency == "NMMTL / DPIIT"
        assert validated.government_schemes[0].official_url == "https://www.startupindia.gov.in"


class TestCompetitorsNormalizationAndGrounding:
    def test_market_share_normalization_no_double_percentage(self):
        """
        In production, '7%' was rendered as '7% % Share'.
        Normalizer must normalize all percentage variations so there are no trailing '%' symbols.
        """
        raw_sections = {
            "competitors": {
                "competitors": [
                    {"name": "Competitor A", "market_share": "7%", "differentiator": "Offline reach"},
                    {"name": "Competitor B", "market_share": "15 %", "differentiator": "Brand"},
                    {"name": "Competitor C", "market_share": "0.12", "differentiator": "Enterprise tier"},
                    {"name": "Competitor D", "market_share": "Unknown / Private", "differentiator": "Niche"},
                ],
                "our_differentiators": ["AI-native OCR compliance pipeline", "Zero-setup onboarding"],
                "market_gaps": ["Unaddressed tier-2 MSME exporters", "Lack of vernacular support"],
            }
        }

        norm = _normalize_blueprint(raw_sections)
        comps = norm["competitors"]["competitors"]

        assert comps[0]["market_share"] == "7%"
        assert comps[1]["market_share"] == "15%"
        assert comps[2]["market_share"] == "12%"
        assert comps[3]["market_share"] is None  # unsupported is not fabricated

        # Verify differentiators and market gaps were preserved
        assert len(norm["competitors"]["our_differentiators"]) == 2
        assert len(norm["competitors"]["market_gaps"]) == 2

    def test_competitors_when_llm_returns_list_at_top_level(self):
        """
        When LLM returns raw_comp as a list, normalizer wraps it into a dict
        and preserves any sibling differentiators or market gaps.
        """
        raw_sections = {
            "competitors": [
                {"name": "Comp X", "strengths": "Fast", "weaknesses": "Pricey"},
                {"name": "Comp Y", "strengths": "Established", "weaknesses": "Slow"},
            ],
            "our_differentiators": ["Lower pricing", "API-first"],
            "market_gaps": ["Missing real-time analytics"],
        }

        norm = _normalize_blueprint(raw_sections)
        assert "competitors" in norm
        assert len(norm["competitors"]["competitors"]) == 2
        assert norm["competitors"]["our_differentiators"] == ["Lower pricing", "API-first"]
        assert norm["competitors"]["market_gaps"] == ["Missing real-time analytics"]


class TestBMCNineBlocksValidation:
    def test_bmc_contains_all_nine_canvas_blocks(self):
        raw_sections = {
            "bmc": {
                "key_partners": ["Textile mills", "Logistics aggregators"],
                "key_activities": ["Automated buyer matching", "Compliance document generation"],
                "key_resources": ["Proprietary NLP engine", "Verified supplier database"],
                "value_propositions": ["80% faster EU export compliance", "Transparent margin discovery"],
                "customer_relationships": ["Self-serve portal", "Dedicated account management for tier-1"],
                "channels": ["Direct export sales", "Industry trade associations", "Web app"],
                "customer_segments": ["Small textile exporters in Surat", "Medium apparel manufacturers"],
                "cost_structure": ["Cloud compute & LLM API tokens", "Sales & field operations"],
                "revenue_streams": ["SaaS monthly subscription", "1.5% take rate per matched export invoice"],
            }
        }

        norm = _normalize_blueprint(raw_sections)
        bmc = norm["bmc"]

        required_blocks = [
            "key_partners",
            "key_activities",
            "key_resources",
            "value_propositions",
            "customer_relationships",
            "channels",
            "customer_segments",
            "cost_structure",
            "revenue_streams",
        ]

        for block in required_blocks:
            assert block in bmc
            assert isinstance(bmc[block], list)
            assert len(bmc[block]) > 0

        # Validate with Pydantic
        validated = BMCSection(**bmc)
        assert len(validated.value_propositions) == 2


class TestBudgetDeterministicArithmetic:
    def test_budget_deterministic_total_calculation(self):
        raw_sections = {
            "budget": {
                "phases": [
                    {
                        "phase_name": "Phase 1: MVP & Pilot",
                        "duration_months": 3,
                        "items": [
                            {"item": "Full-stack Developer", "amount": 150000, "category": "Personnel"},
                            {"item": "Cloud Infrastructure", "amount": 25000, "category": "Tech"},
                        ],
                    },
                    {
                        "phase_name": "Phase 2: Market Launch",
                        "duration_months": 6,
                        "items": [
                            {"item": "Growth Marketing", "amount": 100000, "category": "Marketing"},
                            {"item": "Legal & Compliance", "amount": "₹50,000", "category": "Legal"},
                        ],
                    },
                ],
                # Intentionally wrong total from LLM
                "total_12_months": 9999999,
            }
        }

        norm = _normalize_blueprint(raw_sections)
        budget = norm["budget"]

        # Deterministic sum: 150000 + 25000 + 100000 + 50000 = 325000
        assert budget["total_12_months"] == 325000
        assert budget["currency"] == "INR"


class TestRisksEnumsNormalization:
    def test_risks_severity_and_probability_enums_normalized(self):
        raw_sections = {
            "risks": {
                "risks": [
                    {
                        "category": "Regulatory",
                        "risk": "EU Carbon Border Adjustment Mechanism (CBAM) compliance delays",
                        "severity": "CRITICAL",  # Should map to HIGH
                        "probability": "MODERATE",  # Should map to MEDIUM
                        "impact": "Exporters unable to ship goods without certified carbon footprint audit",
                        "mitigation": "Partner with accredited third-party green auditor and automate CBAM reporting",
                        "monitoring_indicator": "Quarterly regulatory audit passes",
                    },
                    {
                        "category": "Technical",
                        "risk": "API token rate limits during seasonal peak export surge",
                        "severity": "low",
                        "probability": "low",
                        "impact": "Minor latency degradation",
                        "mitigation": "Provision dedicated fallback model endpoint on Groq",
                    },
                ]
            }
        }

        norm = _normalize_blueprint(raw_sections)
        risks = norm["risks"]["risks"]

        assert risks[0]["severity"] == "HIGH"
        assert risks[0]["probability"] == "MEDIUM"
        assert risks[0]["monitoring_indicator"] is not None

        assert risks[1]["severity"] == "LOW"
        assert risks[1]["probability"] == "LOW"

        # Validate with Pydantic
        validated = RisksSection(risks=risks)
        assert validated.risks[0].severity == "HIGH"


class TestSanitizeCRAGDocumentPaths:
    def test_run_crag_sanitizes_document_file_paths(self):
        """CRAG trace document titles must be sanitized of internal filesystem paths."""
        mock_raw_trace = {
            "sources": [
                "C:\\Users\\SAHIL DESAI\\OneDrive\\Desktop\\hackthon\\data\\dpiit_startup_policy.pdf",
                "/home/deploy/docs/rbi_regulatory_sandbox.pdf",
                "https://www.startupindia.gov.in/content/sih/en/schemes.html",
            ],
            "decision": "CORRECT",
            "confidence": "CORRECT",
        }

        # Check clean basename logic
        clean_sources = [
            s if s.startswith("http") else os.path.basename(s.replace("\\", "/"))
            for s in mock_raw_trace["sources"]
        ]

        assert clean_sources[0] == "dpiit_startup_policy.pdf"
        assert clean_sources[1] == "rbi_regulatory_sandbox.pdf"
        assert clean_sources[2] == "https://www.startupindia.gov.in/content/sih/en/schemes.html"


class TestSingleSectionRetryEndpoint:
    def test_retry_section_success(self):
        from fastapi.testclient import TestClient
        from main import app
        from auth_middleware import get_current_user

        from dependencies import get_groq, get_gpt_oss

        app.dependency_overrides[get_current_user] = lambda: {"id": "test_user_id"}
        app.dependency_overrides[get_groq] = lambda: MagicMock()
        app.dependency_overrides[get_gpt_oss] = lambda: MagicMock()
        client = TestClient(app)

        mock_repair_data = {
            "funding_roadmap": [
                {"stage": "Pre-seed", "source": "Angel", "amount": "₹25L", "timeline": "Month 1-6"}
            ],
            "government_schemes": [
                {
                    "name": "Startup India Seed Fund Scheme",
                    "administering_agency": "DPIIT",
                    "type": "Grant",
                    "amount": "Up to ₹20 Lakhs",
                    "eligibility": "DPIIT recognised",
                    "conditions": "Validation phase",
                    "official_url": "https://seedfund.startupindia.gov.in",
                    "source": "Official Guidelines",
                }
            ],
        }

        with patch("routes.blueprint._repair_section", return_value=mock_repair_data):
            response = client.post(
                "/api/blueprint/retry-section",
                json={
                    "section": "investors",
                    "idea": "An AI platform for small textile exporters in Surat",
                    "sector": "Fintech",
                    "stage": "Idea Stage",
                    "model_type": "B2B",
                    "target_city": "Pan India",
                },
            )

            assert response.status_code == 200
            res = response.json()
            assert res["success"] is True
            assert res["section"] == "investors"
            assert "government_schemes" in res["data"]
            assert len(res["data"]["government_schemes"]) == 1

        app.dependency_overrides.clear()
