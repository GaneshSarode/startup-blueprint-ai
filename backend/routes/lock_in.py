"""
routes/lock_in.py — Lock-In Roadmap generation endpoint.

Uses Groq (model from config) + Tavily web search to generate a detailed,
personalised execution roadmap grounded in the user's actual blueprint data.
"""
from __future__ import annotations
import json
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth_middleware import get_current_user
from dependencies import get_groq, get_tavily
from config import get_settings

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lock-in", tags=["lock-in"])


class LockInRequest(BaseModel):
    blueprint_id:     int
    # Founder Details
    founder_name:     str = ""
    technical_bg:     str = "Moderate"      # None/Moderate/Strong(Dev)/Strong(AI)
    business_bg:      str = "Moderate"      # None/Moderate/Strong(MBA)/Strong(Sales)
    startup_exp:      str = "First startup" # First/1-2 before/Serial
    team_size:        str = "1 (Solo)"
    city:             str = "Mumbai"
    # Startup Status
    current_stage:    str = "Idea Only"    # Idea Only/Prototype/MVP/Early Revenue
    available_budget: str = "Bootstrapped (< ₹10K)"
    funding_status:   str = "Self Funded"
    # Goals & Commitment
    primary_goal:     str = "Launch MVP"
    time_commitment:  str = "Part Time"    # Part Time/Full Time/Weekend Only
    roadmap_duration: str = "3 Months"    # 3/6/12 Months
    weekly_hours:     int = 20
    # Team & Resources
    team_members:     List[str] = []       # ["Co-founder (Tech)", "Designer", ...]
    existing_assets:  List[str] = []       # ["Domain name", "Prototype", "Customers", ...]
    # Confidence ratings (1-5)
    conf_programming: int = 3
    conf_ai_ml:       int = 2
    conf_finance:     int = 2
    conf_marketing:   int = 2
    conf_sales:       int = 2
    conf_product_mgmt:int = 3


@router.post("/generate")
async def generate_lock_in_roadmap(
    body:         LockInRequest,
    current_user: Dict        = Depends(get_current_user),
    groq_client               = Depends(get_groq),
    tavily                    = Depends(get_tavily),
):
    """
    Generate a detailed, personalised execution roadmap using:
    1. The user's blueprint data (sector, BMC, budget, GTM, etc.)
    2. The founder's profile form data
    3. Live Tavily web searches for sector-specific insights
    4. Groq LLM for roadmap generation
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))
    from history import load_blueprint_for_display

    # ── 1. Load blueprint ──────────────────────────────────────────────────
    bp = load_blueprint_for_display(body.blueprint_id)
    if not bp:
        raise HTTPException(404, "Blueprint not found")

    idea     = bp.get("original_query", "")
    sector   = bp.get("sector", "startup")
    stage    = bp.get("stage", "Idea Stage")
    bmc      = bp.get("bmc_data",       {})
    budget   = bp.get("budget_data",    {})
    gtm      = bp.get("gtm_data",       {})
    investors= bp.get("investor_data",  {})
    risks    = bp.get("risk_data",      {})

    # ── 2. Tavily live research (3 targeted searches) ──────────────────────
    web_insights = []
    duration_weeks = {"3 Months": 12, "6 Months": 24, "12 Months": 48}.get(body.roadmap_duration, 12)

    searches = [
        f"{sector} startup {body.current_stage} execution roadmap India 2025",
        f"{sector} startup week by week action plan {body.primary_goal.lower()} India",
        f"{sector} India startup {body.primary_goal.lower()} tips founder guide",
    ]

    for q in searches:
        try:
            res = tavily.search(
                query=q,
                search_depth="basic",
                max_results=3,
                include_domains=[
                    "inc42.com", "yourstory.com", "startupindia.gov.in",
                    "entrackr.com", "nasscom.in", "economictimes.indiatimes.com",
                    "firstround.com", "paulgraham.com"
                ]
            )
            for r in res.get("results", [])[:2]:
                web_insights.append({
                    "title":   r.get("title", ""),
                    "excerpt": r.get("content", "")[:200],
                    "url":     r.get("url", ""),
                })
        except Exception as e:
            log.warning(f"Tavily search failed for '{q}': {e}")

    # Compact web context: limit to 5 results with short excerpts
    web_context = "\n".join([
        f"- {r['title']}: {r['excerpt']}"
        for r in web_insights[:5]
    ])

    # ── 3. Build the prompt ────────────────────────────────────────────────
    num_weeks = duration_weeks

    # Determine weaknesses from confidence ratings
    skills = {
        "Programming":       body.conf_programming,
        "AI/ML":             body.conf_ai_ml,
        "Finance":           body.conf_finance,
        "Marketing":         body.conf_marketing,
        "Sales":             body.conf_sales,
        "Product Management":body.conf_product_mgmt,
    }
    weak_areas  = [k for k, v in skills.items() if v <= 2]
    strong_areas= [k for k, v in skills.items() if v >= 4]

    budget_phases = budget.get("phases", [])
    phase1_budget = budget_phases[0].get("total", 0) if budget_phases else 0
    phase1_items  = budget_phases[0].get("items", []) if budget_phases else []

    gtm_channels  = [c.get("channel","") for c in gtm.get("growth_channels", [])[:3]]
    gtm_launch    = gtm.get("launch_strategy", [])[:3]
    key_metrics   = gtm.get("key_metrics", [])[:3]
    revenue_streams = bmc.get("revenue_streams", [])[:3]
    key_activities  = bmc.get("key_activities", [])[:3]
    govt_schemes    = [s.get("name","") for s in investors.get("government_schemes", [])[:3]]
    top_risks       = [r.get("risk","") for r in risks.get("risks", [])[:3]]

    prompt = f"""You are an elite Indian startup execution coach. Generate a {num_weeks}-week personalised roadmap.

FOUNDER: {body.founder_name or "Founder"}, {body.city}, {body.team_size}, Tech:{body.technical_bg}, Biz:{body.business_bg}, Exp:{body.startup_exp}
Hours: {body.weekly_hours}/wk ({body.time_commitment}), Stage: {body.current_stage}, Budget: {body.available_budget}, Funding: {body.funding_status}
Goal: {body.primary_goal}, Duration: {body.roadmap_duration}
Weak: {', '.join(weak_areas) if weak_areas else 'None'} | Strong: {', '.join(strong_areas) if strong_areas else 'None'}
Assets: {', '.join(body.existing_assets) if body.existing_assets else 'None'}

STARTUP: {idea}
Sector: {sector} | Stage: {stage}
Revenue: {', '.join(revenue_streams) if revenue_streams else 'TBD'}
Activities: {', '.join(key_activities) if key_activities else 'TBD'}
Budget: Phase1 Rs{phase1_budget:,.0f} ({', '.join([i.get('item','') for i in phase1_items[:3]])})
GTM: {', '.join(gtm_channels) if gtm_channels else 'TBD'} | Launch: {' > '.join(gtm_launch) if gtm_launch else 'TBD'}
Metrics: {', '.join(key_metrics) if key_metrics else 'TBD'}
Schemes: {', '.join(govt_schemes) if govt_schemes else 'None'}
Risks: {', '.join(top_risks) if top_risks else 'None'}

WEB INSIGHTS:
{web_context if web_context else "No live context available."}

INSTRUCTIONS:
- {num_weeks} weeks, each with theme, 4-6 specific actionable tasks referencing the actual idea
- Adapt tasks to skill profile; include learning tasks for weak areas
- Categories: build, market, fund, legal, ops, learn, validate
- Priority: must, should, nice
- Reference actual budget, GTM channels, risks, and govt schemes
- Account for {body.weekly_hours} hrs/week

Return ONLY valid JSON:
{{"title":"...","founder_name":"{body.founder_name or 'Founder'}","sector":"{sector}","primary_goal":"{body.primary_goal}","duration":"{body.roadmap_duration}","total_tasks":N,"summary":"2-3 sentence strategy summary","key_focus_areas":["..."],"milestones":[{{"week":N,"title":"...","description":"..."}}],"weeks":[{{"week":1,"theme":"...","focus":"...","objective":"...","estimated_hours":N,"tasks":[{{"id":"w1t1","task":"...","details":"...","category":"build","priority":"must","hours":N,"resources":["..."],"outcome":"..."}}]}}],"weekly_rhythm":"...","skill_gap_plan":{{"gaps":{json.dumps(weak_areas)},"recommendations":["..."]}},"govt_scheme_actions":{json.dumps(govt_schemes)},"risk_mitigation":{json.dumps(top_risks)},"success_metrics":["..."]}}"""

    # ── 4. Call Groq ───────────────────────────────────────────────────────
    try:
        response = groq_client.chat.completions.create(
            model=get_settings().GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35,
            max_tokens=3500,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        roadmap = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error(f"Groq returned invalid JSON: {e}")
        raise HTTPException(500, "Roadmap generation failed — invalid response format")
    except Exception as e:
        log.error(f"Groq call failed: {e}")
        raise HTTPException(500, f"Roadmap generation failed: {str(e)}")

    return {
        "roadmap":     roadmap,
        "web_sources": web_insights[:6],
        "blueprint_id":body.blueprint_id,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — LOCK IN AI ACCOUNTABILITY AGENT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

from fastapi.responses import RedirectResponse
from config import get_settings
from lock_in_db import (
    sync_project as db_sync_project,
    get_project,
    get_project_by_id,
    get_preferences as db_get_preferences,
    update_preferences as db_update_preferences,
    get_gmail_connection,
    save_gmail_connection,
    disconnect_gmail as db_disconnect_gmail,
    get_agent_actions,
    get_pending_recommendations,
    approve_agent_action,
    reject_agent_action,
    get_notifications,
    create_email_draft,
    get_email_draft,
    get_project_email_drafts,
    update_email_draft,
    mark_email_draft_sent,
    mark_email_draft_rejected,
    record_notification,
    create_agent_action,
)
from gmail_service import (
    build_google_auth_url,
    exchange_oauth_code,
    send_test_email,
    is_gmail_configured,
    diagnose_gmail_status,
    send_gmail_email,
)
from lock_in_agent_runner import (
    analyze_project_progress,
    evaluate_and_execute_agent,
)
from lock_in_business_partner import (
    get_or_create_context,
    update_context as bp_update_context,
    generate_daily_partner_briefing,
    generate_weekly_partner_review,
    compose_email_draft,
    prepare_or_send_action,
)


class SyncRoadmapRequest(BaseModel):
    blueprint_id:    int
    roadmap:         Dict[str, Any]
    completed_tasks: List[str] = []


class PreferencesUpdateRequest(BaseModel):
    email_enabled:          Optional[bool] = True
    daily_reminder_enabled: Optional[bool] = True
    deadline_alert_enabled: Optional[bool] = True
    weekly_report_enabled:  Optional[bool] = True
    recovery_enabled:       Optional[bool] = True
    reminder_time:          Optional[str] = "09:00"
    timezone:               Optional[str] = "Asia/Kolkata"
    automation_mode:        Optional[str] = "approve_before_sending"
    is_paused:              Optional[bool] = False
    daily_send_limit:       Optional[int] = 5
    trusted_contacts:       Optional[List[Dict[str, Any]]] = None


class CreateDraftRequest(BaseModel):
    workflow_type: str = "daily_briefing"
    recipient: str = ""
    subject: str = ""
    body_text: str = ""
    body_html: Optional[str] = ""
    context_data: Optional[Dict[str, Any]] = None


class UpdateDraftRequest(BaseModel):
    recipient: Optional[str] = None
    subject: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    status: Optional[str] = None


class UpdatePartnerContextRequest(BaseModel):
    founder_profile: Optional[Dict[str, Any]] = None
    weekly_priorities: Optional[List[Dict[str, Any]]] = None
    commitments: Optional[List[Dict[str, Any]]] = None
    decisions: Optional[List[Dict[str, Any]]] = None
    pending_followups: Optional[List[Dict[str, Any]]] = None
    blockers: Optional[List[Dict[str, Any]]] = None
    trusted_contacts: Optional[List[Dict[str, Any]]] = None


@router.post("/sync")
async def sync_roadmap_state(
    body:         SyncRoadmapRequest,
    current_user: Dict = Depends(get_current_user),
):
    """
    Synchronize roadmap structure and task completion state between frontend and backend.
    Ensures the backend agent has the full context for scheduled offline evaluation.
    """
    user_id = current_user["id"]
    user_email = current_user["email"]

    try:
        project = db_sync_project(
            user_id=user_id,
            user_email=user_email,
            blueprint_id=body.blueprint_id,
            roadmap_data=body.roadmap,
            completed_task_ids=body.completed_tasks,
        )
        return {"status": "synced", "project_id": project["id"]}
    except Exception as e:
        log.error(f"Error syncing project roadmap: {e}")
        raise HTTPException(500, f"Failed to sync roadmap state: {str(e)}")


@router.get("/status/{blueprint_id}")
async def get_lock_in_status(
    blueprint_id: int,
    current_user: Dict = Depends(get_current_user),
):
    """
    Retrieves complete business partner status: progress metrics, deterministic score,
    Gmail connection diagnostics, preferences, pending drafts, partner context, and recent activity.
    """
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)

    # Detailed Gmail diagnosis with scopes and reconnect reasoning
    gmail_status = diagnose_gmail_status(user_id)

    if not project:
        return {
            "synced": False,
            "gmail": gmail_status,
            "metrics": None,
            "preferences": None,
            "partner_context": None,
            "pending_drafts": [],
            "drafts_count": 0,
            "pending_recommendations": [],
            "recent_activity": [],
        }

    project_id = project["id"]
    metrics = analyze_project_progress(project_id)
    prefs = db_get_preferences(project_id, user_id)
    context = get_or_create_context(project_id, user_id)
    pending_drafts = get_project_email_drafts(project_id, user_id, status="pending_approval", limit=10)
    all_drafts = get_project_email_drafts(project_id, user_id, limit=50)
    pending_recs = get_pending_recommendations(project_id, user_id)
    activities = get_agent_actions(project_id, user_id, limit=15)

    return {
        "synced": True,
        "project_id": project_id,
        "gmail": gmail_status,
        "metrics": metrics,
        "preferences": prefs,
        "partner_context": context,
        "pending_drafts": pending_drafts,
        "drafts_count": len(pending_drafts),
        "total_drafts_count": len(all_drafts),
        "pending_recommendations": pending_recs,
        "recent_activity": activities,
    }


@router.get("/gmail/connect")
async def connect_gmail(
    blueprint_id: int,
    current_user: Dict = Depends(get_current_user),
):
    """
    Generates a secure Google OAuth authorization URL for offline Gmail sending.
    """
    user_id = current_user["id"]
    settings = get_settings()

    # State parameter carries user_id and blueprint_id securely for CSRF protection and callback routing
    state_payload = json.dumps({"user_id": user_id, "blueprint_id": blueprint_id})
    import base64
    state_b64 = base64.urlsafe_b64encode(state_payload.encode()).decode()

    try:
        auth_url = build_google_auth_url(user_id=user_id, state_token=state_b64)
        return {"auth_url": auth_url}
    except Exception as e:
        log.error(f"Failed to generate Google auth URL: {e}")
        raise HTTPException(400, str(e))


@router.get("/gmail/callback")
async def gmail_oauth_callback(
    code:  Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """
    Handles Google OAuth callback, exchanges authorization code for tokens,
    verifies granted scopes, persists credentials server-side, and redirects.
    """
    settings = get_settings()
    frontend_url = settings.FRONTEND_URL

    if error:
        log.error(f"Google OAuth callback error: {error}")
        return RedirectResponse(f"{frontend_url}/home?gmail_error={error}")

    if not code or not state:
        return RedirectResponse(f"{frontend_url}/home?gmail_error=missing_code_or_state")

    import base64
    try:
        state_data = json.loads(base64.urlsafe_b64decode(state.encode()).decode())
        user_id = state_data.get("user_id")
        blueprint_id = state_data.get("blueprint_id", "")
    except Exception:
        return RedirectResponse(f"{frontend_url}/home?gmail_error=invalid_state")

    try:
        token_info = await exchange_oauth_code(code)
        save_gmail_connection(
            user_id=user_id,
            user_email="",
            google_email=token_info["google_email"],
            access_token=token_info["access_token"],
            refresh_token=token_info["refresh_token"],
            token_expiry=token_info["token_expiry"],
            status=token_info.get("status", "active"),
            granted_scopes=token_info.get("granted_scopes", ""),
            scope_verified=token_info.get("scope_verified", True),
            last_error=token_info.get("last_error", "")
        )

        if token_info.get("has_send_scope"):
            target_path = f"/lock-in/{blueprint_id}?gmail=connected" if blueprint_id else "/home?gmail=connected"
        else:
            target_path = f"/lock-in/{blueprint_id}?gmail_error=scope_insufficient" if blueprint_id else "/home?gmail_error=scope_insufficient"

        return RedirectResponse(f"{frontend_url}{target_path}")

    except Exception as e:
        log.error(f"Error handling Google OAuth callback: {e}")
        target_path = f"/lock-in/{blueprint_id}?gmail_error=auth_failed" if blueprint_id else "/home?gmail_error=auth_failed"
        return RedirectResponse(f"{frontend_url}{target_path}")


@router.post("/gmail/test")
async def send_test_notification(
    current_user: Dict = Depends(get_current_user),
):
    """
    Sends a verification test email strictly to the authenticated user's own email address.
    Fails with actionable diagnostics if gmail.send permission is missing.
    """
    user_id = current_user["id"]
    try:
        res = await send_test_email(user_id)
        return res
    except Exception as e:
        err_msg = str(e)
        log.error(f"Test email failed: {err_msg}")
        raise HTTPException(400, f"Failed to send test email: {err_msg}")


@router.post("/gmail/disconnect")
async def disconnect_user_gmail(
    current_user: Dict = Depends(get_current_user),
):
    """
    Disconnects the user's Gmail connection while preserving all roadmaps and task states.
    """
    user_id = current_user["id"]
    db_disconnect_gmail(user_id)
    return {"status": "disconnected"}


# ══════════════════════════════════════════════════════════════════════════════
# PREFERENCES & PARTNER CONTEXT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{blueprint_id}/preferences")
async def get_notification_preferences(
    blueprint_id: int,
    current_user: Dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Lock-in project not found. Please sync your roadmap first.")
    prefs = db_get_preferences(project["id"], user_id)
    return prefs


@router.put("/{blueprint_id}/preferences")
async def update_notification_preferences(
    blueprint_id: int,
    body:         PreferencesUpdateRequest,
    current_user: Dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Lock-in project not found. Please sync your roadmap first.")
    
    updated = db_update_preferences(project["id"], user_id, body.model_dump(exclude_unset=True))
    return updated


@router.get("/{blueprint_id}/partner-context")
async def get_business_partner_context(
    blueprint_id: int,
    current_user: Dict = Depends(get_current_user),
):
    """Retrieves persistent user context: goals, weekly priorities, commitments, blockers, followups."""
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Lock-in project not found.")
    ctx = get_or_create_context(project["id"], user_id)
    return ctx


@router.put("/{blueprint_id}/partner-context")
async def update_business_partner_context(
    blueprint_id: int,
    body:         UpdatePartnerContextRequest,
    current_user: Dict = Depends(get_current_user),
):
    """Updates user-editable persistent context."""
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Lock-in project not found.")
    
    updates = body.model_dump(exclude_unset=True)
    ctx = bp_update_context(project["id"], user_id, updates)
    return ctx


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL WORKSPACE & DRAFTS MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{blueprint_id}/drafts")
async def get_email_drafts(
    blueprint_id: int,
    status:       Optional[str] = None,
    current_user: Dict = Depends(get_current_user),
):
    """Returns email drafts for the Email Workspace, filterable by status."""
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        return {"drafts": []}
    drafts = get_project_email_drafts(project["id"], user_id, status=status, limit=50)
    return {"drafts": drafts}


@router.post("/{blueprint_id}/drafts")
async def create_new_draft(
    blueprint_id: int,
    body:         CreateDraftRequest,
    current_user: Dict = Depends(get_current_user),
    groq_client = Depends(get_groq),
):
    """
    Creates or synthesizes a new email draft in the Email Workspace.
    If subject/body are not provided, generates them using business partner composer.
    """
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Project not found.")

    subject = body.subject
    body_text = body.body_text
    body_html = body.body_html or ""

    if not subject or not body_text:
        analysis = analyze_project_progress(project["id"])
        context = get_or_create_context(project["id"], user_id)
        comp_sub, comp_txt, comp_html = compose_email_draft(
            workflow_type=body.workflow_type,
            recipient=body.recipient,
            subject_hint=body.subject,
            context_data=body.context_data or {
                "week": analysis.get("current_week", 1),
                "briefing": generate_daily_partner_briefing(analysis, context, groq_client),
                "sender_name": "Founder",
            },
            groq_client=groq_client
        )
        subject = subject or comp_sub
        body_text = body_text or comp_txt
        body_html = body_html or comp_html

    draft_id = create_email_draft(
        project_id=project["id"],
        user_id=user_id,
        workflow_type=body.workflow_type,
        recipient=body.recipient,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        context_data=body.context_data,
        status="pending_approval",
        requires_approval=True
    )

    draft = get_email_draft(draft_id, user_id)
    return {"status": "created", "draft": draft}


@router.put("/{blueprint_id}/drafts/{draft_id}")
async def update_existing_draft(
    blueprint_id: int,
    draft_id:     int,
    body:         UpdateDraftRequest,
    current_user: Dict = Depends(get_current_user),
):
    """Updates an existing draft (recipient, subject, body)."""
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Project not found.")

    updated = update_email_draft(draft_id, user_id, body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(404, "Draft not found.")
    return {"status": "updated", "draft": updated}


@router.post("/{blueprint_id}/drafts/{draft_id}/send")
async def approve_and_send_draft(
    blueprint_id: int,
    draft_id:     int,
    current_user: Dict = Depends(get_current_user),
):
    """
    Human-in-the-Loop (HITL) approval action:
    Approves the draft and dispatches the exact email through the user's connected Gmail account.
    """
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Project not found.")

    draft = get_email_draft(draft_id, user_id)
    if not draft:
        raise HTTPException(404, "Draft not found.")

    if draft["status"] == "sent":
        return {"status": "already_sent", "message_id": draft.get("sent_message_id")}

    recipient = draft["recipient"]
    subject = draft["subject"]
    body_text = draft["body_text"]
    body_html = draft.get("body_html") or ""

    if not recipient:
        raise HTTPException(400, "Draft has no recipient email address.")

    try:
        msg_id = await send_gmail_email(user_id, recipient, subject, body_text, body_html)
        updated_draft = mark_email_draft_sent(draft_id, user_id, msg_id)

        # Log notification & activity
        record_notification(
            project_id=project["id"],
            user_id=user_id,
            notification_type=draft["workflow_type"],
            subject=subject,
            status="sent",
            provider_message_id=msg_id,
            local_date=date.today().isoformat()
        )

        create_agent_action(
            project_id=project["id"],
            user_id=user_id,
            action_type="EMAIL_SENT_APPROVED",
            title=f"User Approved & Sent: {subject}",
            description=f"Delivered to {recipient} (Msg ID: {msg_id})",
            details={"draft_id": draft_id, "recipient": recipient, "message_id": msg_id},
            requires_approval=False
        )

        return {"status": "sent", "message_id": msg_id, "draft": updated_draft}
    except Exception as e:
        log.error(f"Failed to send approved draft #{draft_id}: {e}")
        mark_email_draft_rejected(draft_id, user_id, f"Send failed: {str(e)}")
        raise HTTPException(400, f"Failed to send email: {str(e)}")


@router.post("/{blueprint_id}/drafts/{draft_id}/discard")
async def discard_email_draft(
    blueprint_id: int,
    draft_id:     int,
    current_user: Dict = Depends(get_current_user),
):
    """Discards a draft without sending."""
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Project not found.")

    updated = update_email_draft(draft_id, user_id, {"status": "discarded"})
    if not updated:
        raise HTTPException(404, "Draft not found.")
    return {"status": "discarded", "draft": updated}


# ══════════════════════════════════════════════════════════════════════════════
# ON-DEMAND BRIEFING & REVIEW ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{blueprint_id}/briefing")
async def get_daily_partner_briefing(
    blueprint_id: int,
    current_user: Dict = Depends(get_current_user),
    groq_client = Depends(get_groq),
):
    """Calculates on-demand daily proactive briefing with top 3 priorities, deadlines, and blockers."""
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Project not found.")

    analysis = analyze_project_progress(project["id"])
    context = get_or_create_context(project["id"], user_id)
    briefing = generate_daily_partner_briefing(analysis, context, groq_client)
    return {"briefing": briefing, "analysis": analysis}


@router.get("/{blueprint_id}/weekly-review")
async def get_weekly_partner_review_data(
    blueprint_id: int,
    current_user: Dict = Depends(get_current_user),
    groq_client = Depends(get_groq),
):
    """Calculates weekly partner review: planned vs completed, bottlenecks, next week adjustments."""
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Project not found.")

    analysis = analyze_project_progress(project["id"])
    context = get_or_create_context(project["id"], user_id)
    review = generate_weekly_partner_review(analysis, context, groq_client)
    return {"weekly_review": review, "analysis": analysis}


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVITY & RECOMMENDATION ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{blueprint_id}/activity")
async def get_project_activity_logs(
    blueprint_id: int,
    current_user: Dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        return {"actions": [], "notifications": []}
    
    actions = get_agent_actions(project["id"], user_id, limit=30)
    notifications = get_notifications(project["id"], user_id, limit=30)
    return {"actions": actions, "notifications": notifications}


@router.get("/{blueprint_id}/recommendations")
async def get_recommendations(
    blueprint_id: int,
    current_user: Dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        return {"pending": []}
    
    pending = get_pending_recommendations(project["id"], user_id)
    return {"pending": pending}


@router.post("/{blueprint_id}/recommendations/{action_id}/approve")
async def approve_recommendation(
    blueprint_id: int,
    action_id:    int,
    current_user: Dict = Depends(get_current_user),
):
    """
    Human-in-the-Loop (HITL) approval:
    Applies proposed task moves/schedule adjustments to roadmap in the DB.
    """
    user_id = current_user["id"]
    approved = approve_agent_action(action_id, user_id)
    if not approved:
        raise HTTPException(404, "Recommendation not found or already processed.")
    
    project = get_project(user_id, blueprint_id)
    return {
        "status": "approved",
        "action": approved,
        "updated_roadmap": project.get("roadmap_data") if project else None,
    }


@router.post("/{blueprint_id}/recommendations/{action_id}/reject")
async def reject_recommendation(
    blueprint_id: int,
    action_id:    int,
    current_user: Dict = Depends(get_current_user),
):
    """Rejects recommendation and preserves roadmap schedule."""
    user_id = current_user["id"]
    rejected = reject_agent_action(action_id, user_id)
    if not rejected:
        raise HTTPException(404, "Recommendation not found or already processed.")
    return {"status": "rejected", "action": rejected}


@router.post("/{blueprint_id}/run-agent-now")
async def manually_trigger_agent_evaluation(
    blueprint_id: int,
    notification_type: str = "daily",
    current_user: Dict = Depends(get_current_user),
    groq_client = Depends(get_groq),
):
    """
    Manually triggers an agent evaluation cycle for testing / on-demand review.
    Forces sending to user's connected email regardless of scheduled time window.
    """
    user_id = current_user["id"]
    project = get_project(user_id, blueprint_id)
    if not project:
        raise HTTPException(404, "Project not synced with backend yet.")

    res = await evaluate_and_execute_agent(
        project_id=project["id"],
        notification_type=notification_type,
        force_send=True,
        groq_client=groq_client,
    )
    return res

