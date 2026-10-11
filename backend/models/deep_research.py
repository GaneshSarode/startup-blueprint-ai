"""
backend/models/deep_research.py — Pydantic schemas for Deep Research 2.0.

Provides rigorous, typed validation for evidence-grounded startup intelligence:
- Startup understanding & multi-domain research questions
- Source metadata & provenance with evidence-quality rubric
- Claim-level traceability
- Executive briefing & Critical Analysis with hidden assumptions
- Deterministic bottom-up market sizing (TAM/SAM/SOM)
- Multi-category competitive matrix with verification status
- Customer demand validation & founder experiments
- Dated market pulse news items
- 9-dimension analytical verdict with actionable recommendations
- Research completeness and evidence gap tracking
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class StartupProfile(BaseModel):
    """Extracted startup profile for focused research."""
    idea: str = Field(..., description="Core startup idea description")
    sector: str = Field("Startup", description="Industry or sector")
    stage: str = Field("Idea Stage", description="Current startup stage")
    business_model: str = Field("B2B", description="Monetization and business model")
    target_geography: str = Field("India", description="Target market and launch geography")
    target_customers: List[str] = Field(default_factory=list, description="Primary customer segments")
    core_problem: str = Field("", description="Problem statement being addressed")
    solution: str = Field("", description="Proposed core solution")
    differentiators: List[str] = Field(default_factory=list, description="Stated or intended differentiators")
    missing_critical_info: List[str] = Field(default_factory=list, description="Material gaps in startup profile")


class ResearchQuestion(BaseModel):
    """Targeted research question formulated during planning."""
    id: str = Field(..., description="Unique question identifier, e.g. RQ-MKT-1")
    category: str = Field(..., description="Research domain category")
    question: str = Field(..., description="The specific inquiry")
    rationale: str = Field("", description="Why this question is critical to validate")
    status: str = Field("Investigated", description="Investigated, Partially Resolved, or Unresolved")


class SourceItem(BaseModel):
    """Traceable evidence source with rich metadata and quality scoring."""
    id: int = Field(..., description="1-indexed unique source ID for citation")
    title: str = Field(..., description="Article or document title")
    publisher: str = Field("Web Source", description="Publishing organization or domain")
    domain: str = Field("", description="Domain hostname")
    type: str = Field("web", description="'web' or 'internal'")
    url: str = Field("", description="Original working URL if web source")
    published_date: str = Field("", description="Publication date or 'Date not verified'")
    retrieval_timestamp: str = Field("", description="Timestamp when evidence was fetched")
    excerpt: str = Field("", description="Relevant evidentiary quote or excerpt")
    category: str = Field("General", description="Market Sizing, Competitors, Customer Demand, Regulation, Funding, Market News")
    evidence_quality: str = Field("Medium", description="'High', 'Medium', or 'Low' based on rubric")
    is_primary: bool = Field(False, description="True if primary research, government, or direct company filing")
    research_question: str = Field("", description="Specific research question this evidence answers")
    claims_supported: List[str] = Field(default_factory=list, description="Claim IDs supported by this source")


class ClaimItem(BaseModel):
    """Structured claim with explicit source attribution and verification status."""
    claim_id: str = Field(..., description="Unique claim identifier, e.g. CLM-1")
    statement: str = Field(..., description="The factual or interpretive claim")
    category: str = Field("General", description="Claim category")
    supporting_source_ids: List[int] = Field(default_factory=list, description="Source IDs directly substantiating the claim")
    contradicting_source_ids: List[int] = Field(default_factory=list, description="Source IDs presenting conflicting data")
    confidence: str = Field("Medium", description="High, Medium, or Low confidence")
    verification_status: str = Field("Supported", description="Verified, Supported, Estimated, Assumption, or Contradicted")
    notes: str = Field("", description="Auditable reasoning or methodological context")


class CriticalAnalysis(BaseModel):
    """Rigorous critical challenge of the startup idea and assumptions."""
    strongest_supporting_evidence: List[str] = Field(default_factory=list, description="Evidence confirming founder thesis")
    strongest_counterarguments: List[str] = Field(default_factory=list, description="Credible counterarguments and failure modes")
    critical_assumptions: List[Dict[str, str]] = Field(default_factory=list, description="Assumptions that must hold true")
    key_unknowns: List[str] = Field(default_factory=list, description="Unresolved unknowns requiring market validation")
    failure_scenarios: List[Dict[str, str]] = Field(default_factory=list, description="Plausible failure mechanisms")
    validation_experiments: List[Dict[str, str]] = Field(default_factory=list, description="Low-cost founder experiments")
    pivot_triggers: List[str] = Field(default_factory=list, description="Signals that would mandate a pivot")


class ExecutiveBriefing(BaseModel):
    """Executive decision briefing distinguishing verified facts from AI assessment."""
    overview: str = Field("", description="Concise executive synthesis")
    startup_summary: str = Field("", description="Target customer, core problem, and proposed solution")
    core_problem_and_alternatives: str = Field("", description="Problem reality and current workarounds")
    market_opportunity_summary: str = Field("", description="Opportunity size and realistic capture")
    customer_demand_evidence: str = Field("", description="Evidence of real demand versus hypothetical interest")
    competitive_intensity: str = Field("Medium", description="High, Medium, or Low competitive pressure")
    business_model_feasibility: str = Field("Moderate", description="Feasibility of monetization and unit economics")
    regulatory_and_execution_risks: str = Field("", description="Key regulatory hurdles and operational dependencies")
    strongest_opportunity: str = Field("", description="The highest-upside strategic wedge")
    biggest_threat: str = Field("", description="The single greatest threat to business survival")
    recommended_next_action: str = Field("", description="Immediate actionable next step for the founder")
    supporting_source_ids: List[int] = Field(default_factory=list, description="Citations supporting briefing conclusions")


class BottomUpSizing(BaseModel):
    """Deterministic bottom-up calculation of market opportunity."""
    formula: str = Field("Target Eligible Customers × Addressable Annual Revenue per Customer (ARPU)", description="Calculation formula")
    currency: str = Field("USD", description="Currency symbol or code")
    target_customers: int = Field(0, description="Total eligible target customer count")
    target_customers_source: str = Field("Industry estimates & census data", description="Source for customer count")
    arpu: float = Field(0.0, description="Realistically addressable annual revenue per customer")
    arpu_source: str = Field("Comparable benchmark pricing", description="Source or benchmark for ARPU")
    sam_reach_ratio: float = Field(0.20, description="Portion of TAM realistically serviceable in initial launch geography")
    som_capture_ratio: float = Field(0.03, description="Realistic obtainable share of SAM over 3 years")
    tam_calculated: float = Field(0.0, description="Deterministic TAM = target_customers * arpu")
    sam_calculated: float = Field(0.0, description="Deterministic SAM = tam_calculated * sam_reach_ratio")
    som_calculated: float = Field(0.0, description="Deterministic SOM = sam_calculated * som_capture_ratio")
    notes: str = Field("", description="Key arithmetic and adoption capacity assumptions")


class MarketLandscape(BaseModel):
    """Market sizing, growth rates, bottom-up model, and conflicting estimates."""
    tam: Dict[str, Any] = Field(default_factory=dict, description="TAM estimate, value, description, sources")
    sam: Dict[str, Any] = Field(default_factory=dict, description="SAM estimate, value, description, sources")
    som: Dict[str, Any] = Field(default_factory=dict, description="SOM estimate, value, description, sources")
    bottom_up: BottomUpSizing = Field(default_factory=BottomUpSizing, description="Deterministic bottom-up arithmetic")
    geographic_scope: str = Field("India & Global", description="Geographic boundaries of the estimates")
    projection_horizon: str = Field("2025–2030", description="Time horizon of market estimates")
    cagr: str = Field("N/A", description="Verified compound annual growth rate with citation")
    drivers: List[str] = Field(default_factory=list, description="Primary structural tailwinds")
    constraints: List[str] = Field(default_factory=list, description="Structural market barriers or headwinds")
    conflicting_estimates: List[Dict[str, Any]] = Field(default_factory=list, description="Documented discrepancies between credible sources")
    uncertainty_rating: str = Field("Medium", description="High, Medium, or Low uncertainty in market estimates")


class CompetitorItem(BaseModel):
    """Individual competitor with verified attributes and verification status."""
    name: str = Field(..., description="Competitor or product name")
    category: str = Field("Direct Competitor", description="Direct, Indirect, Substitute / Manual Workflow, or Emerging")
    product: str = Field("", description="Core product offering")
    target_customer: str = Field("", description="Primary audience served")
    core_capabilities: List[str] = Field(default_factory=list, description="Key features and technical capabilities")
    pricing_model: str = Field("Not verified", description="Pricing tier or 'Not verified'")
    pricing_verification: str = Field("Not verified", description="'Verified' or 'Not verified'")
    distribution: str = Field("Direct sales / Inbound", description="Customer acquisition and distribution channel")
    integration_ecosystem: str = Field("Not verified", description="Key platform integrations")
    geographic_presence: str = Field("Global / India", description="Main operating territories")
    strengths: List[str] = Field(default_factory=list, description="Documented strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Customer-reported weaknesses or limitations")
    differentiation: str = Field("", description="How the startup realistically differentiates")
    source: str = Field("", description="Primary source or 'Company profile'")
    supporting_source_ids: List[int] = Field(default_factory=list, description="Citations supporting competitor claims")


class CompetitorIntelligence(BaseModel):
    """Complete competitive landscape matrix and positioning."""
    competitors: List[CompetitorItem] = Field(default_factory=list, description="List of direct, indirect, substitute competitors")
    positioning_summary: str = Field("", description="Startup competitive position and realistic moats")
    competitive_intensity: str = Field("Medium", description="High, Medium, or Low")
    differentiation_opportunities: List[str] = Field(default_factory=list, description="Uncontested market wedges")


class CustomerValidation(BaseModel):
    """Customer pain point validation, willingness to pay, and discovery plan."""
    target_customer: str = Field("", description="Primary target customer persona")
    evidence_problem_exists: List[Dict[str, Any]] = Field(default_factory=list, description="Verified signals that problem causes pain")
    current_alternatives_and_switching_costs: List[Dict[str, str]] = Field(default_factory=list, description="Existing manual tools and switching friction")
    willingness_to_pay_signals: List[Dict[str, Any]] = Field(default_factory=list, description="Budgets, pricing benchmarks, or commercial willingness to pay")
    unmet_needs_and_complaints: List[Dict[str, Any]] = Field(default_factory=list, description="Customer complaints extracted from forums/reviews")
    strongest_need_segments: List[str] = Field(default_factory=list, description="Segments experiencing the most acute urgency")
    adoption_barriers: List[str] = Field(default_factory=list, description="Trust, integration, or behavior change hurdles")
    customer_discovery_questions: List[str] = Field(default_factory=list, description="10 high-value interview questions for founders")
    validation_experiments: List[Dict[str, str]] = Field(default_factory=list, description="Low-cost demand validation experiments")


class MarketPulseItem(BaseModel):
    """Dated, factual industry news item with working source link."""
    headline: str = Field(..., description="Genuine news headline")
    publisher: str = Field(..., description="Actual media organization or publisher")
    date: str = Field(..., description="Publication date (verified from source)")
    why_it_matters: str = Field(..., description="Specific strategic relevance to this startup")
    source_url: str = Field("", description="Working original source URL")
    is_verified_news: bool = Field(True, description="True if verified dated article")


class VerdictScoreItem(BaseModel):
    """Structured analytical score on a 1–10 scale with explicit criteria."""
    dimension: str = Field(..., description="Evaluation dimension")
    score: int = Field(..., description="Integer score between 1 and 10")
    definition: str = Field(..., description="Meaning of this score")
    evidence_and_assumptions: str = Field(..., description="Factual basis and assumptions supporting score")
    what_would_increase_score: str = Field(..., description="Triggers that would raise this rating")
    what_would_decrease_score: str = Field(..., description="Triggers that would lower this rating")
    evidence_quality: str = Field("Medium", description="Quality of evidence informing the score")


class ResearchVerdict(BaseModel):
    """Comprehensive, auditable market verdict with recommendations."""
    overall_recommendation: str = Field("VALIDATE-FIRST", description="'GO', 'VALIDATE-FIRST', 'PIVOT', 'NO-GO', or 'INSUFFICIENT EVIDENCE'")
    overall_verdict_title: str = Field("", description="Headline verdict statement")
    scores: List[VerdictScoreItem] = Field(default_factory=list, description="9 dimension scores with rationales")
    market_attractiveness_score: int = Field(7, description="Overall market attractiveness (1-10)")
    competitive_position_score: int = Field(6, description="Competitive differentiation (1-10)")
    customer_demand_score: int = Field(7, description="Customer demand validation (1-10)")
    revenue_feasibility_score: int = Field(7, description="Revenue model feasibility (1-10)")
    acquisition_difficulty_score: int = Field(6, description="Customer acquisition ease (1-10)")
    technical_feasibility_score: int = Field(8, description="Technical feasibility (1-10)")
    regulatory_feasibility_score: int = Field(7, description="Regulatory compliance feasibility (1-10)")
    funding_potential_score: int = Field(7, description="Funding accessibility (1-10)")
    execution_risk_score: int = Field(6, description="Execution risk management (1-10)")
    strongest_reasons_to_proceed: List[str] = Field(default_factory=list, description="Top positive drivers")
    strongest_reasons_for_caution: List[str] = Field(default_factory=list, description="Top cautionary indicators")
    key_unresolved_questions: List[str] = Field(default_factory=list, description="Unanswered inquiries before capital deployment")
    recommended_next_three_actions: List[str] = Field(default_factory=list, description="Immediate 30-day founder action plan")
    verdict_reasoning: str = Field("", description="Synthesized analytical justification")


class ResearchCompleteness(BaseModel):
    """Audit of research coverage and remaining uncertainty."""
    questions_investigated: int = Field(0, description="Number of targeted questions addressed")
    questions_unresolved: int = Field(0, description="Number of questions needing further empirical data")
    coverage_by_area: Dict[str, str] = Field(default_factory=dict, description="Domain coverage rating ('Strong', 'Moderate', 'Gap')")
    major_evidence_gaps: List[str] = Field(default_factory=list, description="Explicitly documented evidence gaps")


class DeepResearchReport(BaseModel):
    """Full canonical schema for Deep Research 2.0."""
    title: str = Field("Deep Research 2.0 — Startup Intelligence Report", description="Report title")
    executive_summary: ExecutiveBriefing = Field(default_factory=ExecutiveBriefing)
    critical_analysis: CriticalAnalysis = Field(default_factory=CriticalAnalysis)
    market_landscape: MarketLandscape = Field(default_factory=MarketLandscape)
    competitor_intelligence: CompetitorIntelligence = Field(default_factory=CompetitorIntelligence)
    customer_validation: CustomerValidation = Field(default_factory=CustomerValidation)
    market_pulse: List[MarketPulseItem] = Field(default_factory=list)
    research_verdict: ResearchVerdict = Field(default_factory=ResearchVerdict)
    research_completeness: ResearchCompleteness = Field(default_factory=ResearchCompleteness)
    sources: List[SourceItem] = Field(default_factory=list)
    claims: List[ClaimItem] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)

    # Optional mode-specific extensions preserved for specialized views
    compliance_roadmap: Optional[List[Dict[str, Any]]] = None
    pitch_roadmap: Optional[List[Dict[str, Any]]] = None
    technical_roadmap: Optional[List[Dict[str, Any]]] = None
    regulatory_analysis: Optional[List[Dict[str, Any]]] = None
    funding_landscape: Optional[List[Dict[str, Any]]] = None
