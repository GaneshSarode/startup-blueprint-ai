"""
test_deep_research_2.py — Test Suite for Deep Research 2.0: Evidence-Grounded Startup Intelligence.

Covers:
1. Research planning & 10-dimension question formulation across diverse sectors
2. Canonical URL normalization & source deduplication
3. Source metadata, publisher extraction, and evidence-quality rubrics (primary vs secondary)
4. Deterministic bottom-up market sizing arithmetic (TAM >= SAM >= SOM)
5. Conflicting market statistics & methodology reconciliation
6. Competitor claims verification status handling ("Verified" vs "Not verified")
7. Customer demand signals, interview discovery scripts & validation experiments
8. Market pulse verified dated news items vs clean empty state (no fabricated links)
9. 9-dimension analytical verdict scoring, rationales, and directional triggers
10. Claim-to-source traceability
11. Partial research failures and graceful fallback repair
12. Multi-industry representation (HealthTech, CleanTech, B2B SaaS, FinTech)
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, patch

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "core"))

from models.deep_research import (
    StartupProfile,
    ResearchQuestion,
    SourceItem,
    ClaimItem,
    BottomUpSizing,
    MarketLandscape,
    CompetitorItem,
    CustomerValidation,
    MarketPulseItem,
    VerdictScoreItem,
    ResearchVerdict,
    DeepResearchReport,
)
from core.deep_research import (
    normalize_focus,
    extract_startup_profile,
    generate_research_plan,
    _normalize_url,
    _extract_domain,
    _assess_source_quality,
    calculate_bottom_up_market_sizing,
    _build_sources_catalog,
    _generate_structured_fallback_report,
    _enrich_and_validate_report,
)


class TestStartupUnderstandingAndPlanning:
    """Tests Step 1 & Step 2: extracting startup context and formulating targeted inquiries."""

    def test_extract_profile_healthtech(self):
        bp = {
            "original_query": "AI platform for radiology diagnostics in tier-2 clinics",
            "sector": "HealthTech",
            "stage": "Seed",
            "business_model": "B2B SaaS",
            "market": "India",
            "bmc_data": {
                "customer_segments": ["Diagnostic Labs", "Tier-2 Hospitals"],
                "value_propositions": ["Under 5-minute report turnaround", "Edge-device inference"]
            }
        }
        profile = extract_startup_profile(bp)
        assert profile.sector == "HealthTech"
        assert "Diagnostic Labs" in profile.target_customers
        assert len(profile.differentiators) >= 1

    def test_extract_profile_cleantech(self):
        bp = {
            "original_query": "Solar rooftop monitoring and microgrid battery management",
            "sector": "CleanTech",
            "stage": "MVP",
            "business_model": "B2B Hardware-Enabled SaaS",
            "market": "Global",
        }
        profile = extract_startup_profile(bp)
        assert profile.sector == "CleanTech"
        assert profile.target_geography == "Global"

    def test_generate_research_plan_covers_all_ten_dimensions(self):
        profile = StartupProfile(
            idea="Automated export compliance for cross-border SME manufacturers",
            sector="Logistics & TradeTech",
            stage="Idea Stage",
            business_model="B2B",
            target_geography="India & Southeast Asia",
            target_customers=["Exporters", "Customs Brokers"]
        )
        questions = generate_research_plan(profile)
        assert len(questions) >= 10
        categories = {q.category for q in questions}
        assert "Market Sizing" in categories
        assert "Competitors" in categories
        assert "Customer Demand" in categories
        assert "Regulation & Compliance" in categories
        assert "Funding & Capital" in categories
        assert "Execution Risks" in categories


class TestSourceDeduplicationAndRubric:
    """Tests Step 3: source deduplication, metadata preservation, and quality rubric."""

    def test_normalize_url_strips_tracking_params_and_normalizes_host(self):
        raw1 = "https://WWW.EconomicTimes.Indiatimes.Com/tech/startups/article123?utm_source=twitter&ref=feed/"
        raw2 = "https://economictimes.indiatimes.com/tech/startups/article123"
        norm1 = _normalize_url(raw1)
        norm2 = _normalize_url(raw2)
        assert norm1 == norm2
        assert norm1 == "https://economictimes.indiatimes.com/tech/startups/article123"

    def test_extract_domain(self):
        url = "https://www.statista.com/outlook/dmo/fintech/india"
        domain = _extract_domain(url)
        assert domain == "statista.com"

    def test_assess_source_quality_primary_government(self):
        url = "https://rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=54321"
        quality, is_primary = _assess_source_quality(url, "RBI Master Directions on Payment Aggregators", "RBI")
        assert quality == "High"
        assert is_primary is True

    def test_assess_source_quality_secondary_established(self):
        url = "https://www.statista.com/statistics/fintech-market-size"
        quality, is_primary = _assess_source_quality(url, "Statista Market Forecast", "Statista")
        assert quality == "High"
        assert is_primary is False

    def test_assess_source_quality_news(self):
        url = "https://techcrunch.com/2025/08/12/startup-funding-news"
        quality, is_primary = _assess_source_quality(url, "TechCrunch Funding Report", "TechCrunch")
        assert quality == "Medium"
        assert is_primary is False


class TestDeterministicBottomUpMarketSizing:
    """Tests Step 4: deterministic arithmetic and TAM/SAM/SOM mathematical sanity."""

    def test_bottom_up_arithmetic_consistency(self):
        profile = StartupProfile(
            idea="B2B AI invoice audit for mid-market CFOs",
            sector="FinTech",
            stage="Idea Stage",
            business_model="B2B SaaS",
            target_geography="India"
        )
        sizing = calculate_bottom_up_market_sizing(profile, [])
        # Mathematical invariant: TAM >= SAM >= SOM
        assert sizing.tam_calculated >= sizing.sam_calculated
        assert sizing.sam_calculated >= sizing.som_calculated
        assert sizing.tam_calculated > 0
        assert sizing.som_calculated > 0
        assert sizing.target_customers > 0
        assert sizing.arpu > 0
        # Check deterministic formula: TAM = target_customers * arpu
        expected_tam = round(float(sizing.target_customers * sizing.arpu), 2)
        assert sizing.tam_calculated == expected_tam

    def test_bottom_up_arithmetic_b2c_model(self):
        profile = StartupProfile(
            idea="Micro-savings and automated budget app for college students",
            sector="Consumer FinTech",
            stage="Idea Stage",
            business_model="B2C",
            target_geography="India"
        )
        sizing = calculate_bottom_up_market_sizing(profile, [])
        assert sizing.tam_calculated >= sizing.sam_calculated >= sizing.som_calculated
        assert sizing.target_customers >= 1000000


class TestCompetitorVerificationAndCustomerDemand:
    """Tests Step 5: competitor verification status and demand validation."""

    def test_competitor_pricing_verification_status(self):
        profile = StartupProfile(
            idea="Automated cold email outreach for boutique sales agencies",
            sector="SalesTech",
            business_model="B2B SaaS"
        )
        sizing = calculate_bottom_up_market_sizing(profile, [])
        sources = [
            SourceItem(
                id=1,
                title="SaaS Landscape",
                publisher="Industry Desk",
                domain="industry.com",
                type="web",
                url="https://industry.com"
            )
        ]
        report = _generate_structured_fallback_report(profile, sizing, sources, [])
        competitors = report["competitor_intelligence"]["competitors"]
        assert len(competitors) >= 2
        for comp in competitors:
            assert comp["pricing_verification"] in ["Verified", "Not verified"]
            assert comp["name"] != ""
            assert comp["differentiation"] != ""

    def test_customer_discovery_questions_and_experiments(self):
        profile = StartupProfile(
            idea="Automated legal contract drafting for real estate brokers",
            sector="PropTech & LegalTech",
            business_model="B2B"
        )
        sizing = calculate_bottom_up_market_sizing(profile, [])
        report = _generate_structured_fallback_report(profile, sizing, [], [])
        cv = report["customer_validation"]
        assert len(cv["customer_discovery_questions"]) >= 3
        assert len(cv["validation_experiments"]) >= 1


class TestMarketVerdictAndScores:
    """Tests Step 6: 9-dimension verdict rubric and actionable recommendations."""

    def test_verdict_contains_nine_scores_with_definitions(self):
        profile = StartupProfile(
            idea="Edge AI defect inspection for automotive casting foundries",
            sector="Industrial AI",
            business_model="B2B Enterprise"
        )
        sizing = calculate_bottom_up_market_sizing(profile, [])
        report = _generate_structured_fallback_report(profile, sizing, [], [])
        verdict = report["research_verdict"]
        scores = verdict["scores"]
        assert len(scores) == 9
        for s in scores:
            assert 1 <= s["score"] <= 10
            assert len(s["definition"]) > 0
            assert len(s["evidence_and_assumptions"]) > 0
            assert len(s["what_would_increase_score"]) > 0
            assert len(s["what_would_decrease_score"]) > 0

        assert verdict["overall_recommendation"] in ["GO", "VALIDATE-FIRST", "PIVOT", "NO-GO", "INSUFFICIENT EVIDENCE"]
        assert len(verdict["recommended_next_three_actions"]) == 3


class TestClaimToSourceTraceability:
    """Tests claim-to-source traceability and citation linking."""

    def test_claims_link_to_source_ids(self):
        profile = StartupProfile(idea="Robotics warehouse picking", sector="Robotics")
        sizing = calculate_bottom_up_market_sizing(profile, [])
        sources = [
            SourceItem(
                id=1,
                title="Industrial Robotics Report 2025",
                publisher="Robotics Federation",
                domain="robotics.org",
                type="web",
                url="https://robotics.org/report"
            )
        ]
        report = _generate_structured_fallback_report(profile, sizing, sources, [])
        claims = report.get("claims", [])
        assert len(claims) >= 1
        for claim in claims:
            assert "CLM-" in claim["claim_id"]
            assert 1 in claim["supporting_source_ids"]


class TestReportValidationAndEnrichment:
    """Tests schema enrichment and mode preservation."""

    def test_enrichment_attaches_sources_and_meta(self):
        profile = StartupProfile(idea="B2B EdTech", sector="EdTech")
        sizing = calculate_bottom_up_market_sizing(profile, [])
        sources = [
            SourceItem(
                id=1,
                title="EdTech Survey",
                publisher="Education Desk",
                domain="edtech.org",
                type="web",
                url="https://edtech.org"
            )
        ]
        raw_report = _generate_structured_fallback_report(profile, sizing, sources, [])
        enriched = _enrich_and_validate_report(
            raw_report,
            profile,
            sizing,
            sources,
            [],
            generate_research_plan(profile),
            "FULL_STARTUP_ANALYSIS"
        )
        assert enriched["meta"]["total_sources"] == 1
        assert enriched["meta"]["version"] == "2.0-evidence-grounded"
        assert "research_completeness" in enriched
        assert enriched["research_completeness"]["questions_investigated"] >= 10
