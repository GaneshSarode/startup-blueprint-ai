"""
models/blueprint.py — Pydantic schemas for blueprint generation endpoints.

Used by routes/blueprint.py for request validation, SSE event formatting,
and the final BlueprintResponse shape.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class BlueprintRequest(BaseModel):
    idea: str = Field(..., min_length=10, description="Startup idea description")
    sector: str = Field(default="Fintech", description="Industry sector")
    model_type: str = Field(default="B2B", description="Business model type")
    stage: str = Field(default="Idea Stage", description="Startup stage")
    target_city: str = Field(default="Pan India", description="Target market/city")

    model_config = ConfigDict(protected_namespaces=())


class SSEEvent(BaseModel):
    """Single SSE frame sent during blueprint generation streaming."""
    event: str = Field(..., description="Event type: generation_started | stage_started | stage_completed | section_started | section_completed | progress | generation_completed | complete | generation_failed | error")
    generation_id: str = ""
    step: str = ""
    node: str = ""
    stage: str = ""
    section: str = ""
    progress: int = 0
    data: Optional[Any] = None
    error: str = ""


# ── Section Specific Schemas ───────────────────────────────────────────────────

class BMCSection(BaseModel):
    key_partners: List[str] = Field(default_factory=list)
    key_activities: List[str] = Field(default_factory=list)
    key_resources: List[str] = Field(default_factory=list)
    value_propositions: List[str] = Field(default_factory=list)
    customer_relationships: List[str] = Field(default_factory=list)
    channels: List[str] = Field(default_factory=list)
    customer_segments: List[str] = Field(default_factory=list)
    cost_structure: List[str] = Field(default_factory=list)
    revenue_streams: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class BudgetItem(BaseModel):
    item: str = "Expense"
    description: str = ""
    amount: int = 0
    timeframe: str = "12-month"

    model_config = ConfigDict(extra="allow")


class BudgetPhase(BaseModel):
    name: str = "Phase"
    duration: str = ""
    items: List[BudgetItem] = Field(default_factory=list)
    total: int = 0
    phase_total: Optional[int] = 0

    model_config = ConfigDict(extra="allow")


class BudgetSection(BaseModel):
    phases: List[BudgetPhase] = Field(default_factory=list)
    total_12_months: int = 0
    total_12_months_inr: str = "₹0"
    currency: str = "INR"
    timeframe: str = "12 Months"
    assumptions: str = "Based on early-stage lean execution"
    funding_suggestion: str = "Startup India Seed Fund + Angel Investment"

    model_config = ConfigDict(extra="allow")


class MarketSizing(BaseModel):
    tam: str = "N/A"
    sam: str = "N/A"
    som: str = "N/A"
    geography: str = "India"
    currency: str = "INR / USD"
    assumptions: str = ""
    sources: str = ""

    model_config = ConfigDict(extra="allow")


class GrowthChannel(BaseModel):
    channel: str = ""
    strategy: Optional[str] = ""
    rationale: str = ""
    priority: str = "MEDIUM"
    cost: str = "MIXED"

    model_config = ConfigDict(extra="allow")


class Milestone(BaseModel):
    month: int = 1
    goal: str = ""

    model_config = ConfigDict(extra="allow")


class GTMSection(BaseModel):
    target_market: str = ""
    market_size: str = ""
    market_sizing: Optional[MarketSizing] = None
    launch_strategy: List[str] = Field(default_factory=list)
    growth_channels: List[GrowthChannel] = Field(default_factory=list)
    milestones: List[Milestone] = Field(default_factory=list)
    key_metrics: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class GovernmentScheme(BaseModel):
    name: str
    administering_agency: Optional[str] = "Govt of India"
    type: str = "Grant / Debt"
    amount: Optional[str] = "N/A"
    benefit: Optional[str] = ""
    eligibility: str = "DPIIT recognised startups"
    conditions: Optional[str] = "Subject to incubator or nodal committee approval"
    application_steps: Optional[Any] = "Apply online via official portal"
    official_url: Optional[str] = "https://www.startupindia.gov.in"
    source: Optional[str] = "Official Startup India Portal"
    relevance: Optional[str] = ""
    limitations: Optional[str] = ""

    model_config = ConfigDict(extra="allow")


class FundingRoadmapStage(BaseModel):
    stage: str
    timeline: Optional[str] = "Month 1-6"
    source: Optional[str] = "Angel / Incubator"
    amount: Optional[str] = "₹20 Lakhs"

    model_config = ConfigDict(extra="allow")


class InvestorType(BaseModel):
    type: Optional[str] = "Angel / Seed VC"
    name: Optional[str] = None
    stage: Optional[str] = "Seed"
    focus: Optional[str] = "Tech Startups"
    examples: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class Incubator(BaseModel):
    name: str
    focus: str = "Incubation"
    location: str = "India"

    model_config = ConfigDict(extra="allow")


class FundingSection(BaseModel):
    funding_roadmap: List[FundingRoadmapStage] = Field(default_factory=list)
    government_schemes: List[GovernmentScheme] = Field(default_factory=list)
    investor_types: List[Any] = Field(default_factory=list)
    investor_landscape: Optional[List[Any]] = None
    incubators: List[Incubator] = Field(default_factory=list)
    relevant_incubators: Optional[List[Incubator]] = None
    pitch_tips: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class CompetitorItem(BaseModel):
    name: str
    type: str = "Direct"
    target_customer: Optional[str] = ""
    core_offering: Optional[str] = ""
    core_features: Optional[str] = ""
    pricing: Optional[str] = ""
    strength: Optional[str] = ""
    weakness: Optional[str] = ""
    differentiator: Optional[str] = ""
    market_share: Optional[str] = "N/A"
    funding: Optional[str] = ""
    source: Optional[str] = ""

    model_config = ConfigDict(extra="allow")


class CompetitorsSection(BaseModel):
    competitors: List[CompetitorItem] = Field(default_factory=list)
    our_differentiators: List[str] = Field(default_factory=list)
    market_gaps: List[str] = Field(default_factory=list)
    competitive_strategy: str = ""

    model_config = ConfigDict(extra="allow")


class RiskItem(BaseModel):
    category: str = "Operational"
    severity: str = "MEDIUM"      # HIGH | MEDIUM | LOW
    probability: str = "MEDIUM"   # HIGH | MEDIUM | LOW
    impact: str = ""
    risk: str = ""
    mitigation: str = ""
    monitoring_indicator: Optional[str] = ""

    model_config = ConfigDict(extra="allow")


class RisksSection(BaseModel):
    risks: List[RiskItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class SourceDocument(BaseModel):
    source: str
    collection: str = "text"
    score: Optional[float] = None
    logit: Optional[float] = None
    excerpt: str = ""
    full_text: Optional[str] = ""

    model_config = ConfigDict(extra="allow")


class SourceUsage(BaseModel):
    claim: str
    source: str
    section: Optional[str] = ""

    model_config = ConfigDict(extra="allow")


class CRAGTraceSection(BaseModel):
    confidence: str = ""
    decision: str = ""
    verified_context: List[str] = Field(default_factory=list)
    inferences: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    source_usage: List[SourceUsage] = Field(default_factory=list)
    retrieved_documents: List[SourceDocument] = Field(default_factory=list)
    fallback_events: List[str] = Field(default_factory=list)
    raw_summary: str = ""

    model_config = ConfigDict(extra="allow")


class RetrySectionRequest(BaseModel):
    section: str = Field(..., description="Section to retry: bmc | budget | gtm | investors | competitors | risks | crag_trace")
    blueprint_id: Optional[int] = None
    idea: Optional[str] = ""
    sector: Optional[str] = "Fintech"
    model_type: Optional[str] = "B2B"
    stage: Optional[str] = "Idea Stage"
    target_city: Optional[str] = "Pan India"

    model_config = ConfigDict(protected_namespaces=())


class BlueprintResponse(BaseModel):
    """
    Full response returned on SSE 'complete' event and GET /api/blueprint/{id}.
    Contains both nested 'blueprint' object and flat section fields so all
    consumers (Dashboard, Blueprint view, History, Mentor) receive consistent data.
    """
    blueprint_id: Optional[int] = None
    id: Optional[int] = None
    generation_id: Optional[str] = None
    idea: str = ""
    original_query: str = ""
    title: str = ""
    sector: str = ""
    model_type: str = ""
    business_model: str = ""
    stage: str = ""
    target_city: str = ""
    market: str = ""
    generated_at: str = ""
    timestamp: str = ""

    # Status and failure metadata
    status: str = "success"
    failed_sections: List[str] = Field(default_factory=list)

    # CRAG pipeline result
    crag_result: Optional[Dict[str, Any]] = None
    confidence: Optional[str] = ""
    summary: Optional[str] = ""
    sources: Optional[List[Any]] = None
    keywords: Optional[List[str]] = None
    raw_logits: Optional[List[float]] = None
    timings: Optional[Dict[str, Any]] = None

    # Canonical nested blueprint dict
    blueprint: Optional[Dict[str, Any]] = None

    # Flat section access for backwards compatibility
    bmc_data: Optional[Dict[str, Any]] = None
    budget_data: Optional[Dict[str, Any]] = None
    gtm_data: Optional[Dict[str, Any]] = None
    investor_data: Optional[Dict[str, Any]] = None
    funding_data: Optional[Dict[str, Any]] = None
    competitor_data: Optional[Dict[str, Any]] = None
    risk_data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        protected_namespaces=(),
        arbitrary_types_allowed=True,
        extra="allow",
    )
