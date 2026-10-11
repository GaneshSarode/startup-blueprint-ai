"""
lock_in_business_partner.py — Proactive AI Business Partner Engine for LOCK IN.

Key Capabilities:
  1. Persistent User Context: Goals, weekly priorities, commitments, decisions, follow-ups, blockers.
  2. Proactive Daily Planning: Top 3 priorities, next actions, deadlines, blockers, practical recommendations.
  3. Weekly Review & Replanning: Planned vs completed, bottlenecks, next week adjustments.
  4. Natural Human Professional Gmail Communication: Reusable workflows (follow-up, meeting request, progress update, outreach, etc.).
  5. Strict Safety & Approval Gate:
     - 'draft_only'
     - 'approve_before_sending' (Default)
     - 'trusted_automation' (Requires explicit opt-in, trusted recipient check, daily limits, and zero sensitive commitments).
"""

from __future__ import annotations
import json
import logging
import re
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
import zoneinfo

from config import get_settings
from lock_in_db import (
    get_project_by_id,
    get_project_tasks,
    get_preferences,
    get_gmail_connection,
    get_partner_context,
    update_partner_context as db_update_partner_context,
    create_email_draft,
    get_email_draft,
    get_project_email_drafts,
    update_email_draft,
    mark_email_draft_sent,
    mark_email_draft_rejected,
    record_notification,
    create_agent_action,
)
from gmail_service import send_gmail_email

log = logging.getLogger(__name__)

# List of sensitive keywords requiring mandatory human approval even in trusted automation
SENSITIVE_COMMITMENT_PATTERNS = [
    r"\b(contract|agreement|nda|legal|term sheet|equity|convertible note)\b",
    r"\b(wire transfer|bank account|payment|invoice|\$\d+|₹\d+|rs\.\s*\d+)\b",
    r"\b(hire|job offer|salary|equity grant|employment)\b",
    r"\b(guarantee|liable|indemnif|settlement)\b"
]


# ══════════════════════════════════════════════════════════════════════════════
# 1. PERSISTENT PARTNER CONTEXT MANAGER
# ══════════════════════════════════════════════════════════════════════════════

def get_or_create_context(project_id: int, user_id: str) -> dict:
    """Loads existing context or initializes default structure for project."""
    ctx = get_partner_context(project_id, user_id)
    return ctx


def update_context(project_id: int, user_id: str, updates: dict) -> dict:
    """User-editable context update: adds/updates/corrects priorities, blockers, followups, decisions."""
    current = get_partner_context(project_id, user_id)
    merged = {**current, **updates}
    return db_update_partner_context(project_id, user_id, merged)


def add_blocker(project_id: int, user_id: str, title: str, description: str, impact: str = "medium") -> dict:
    """Records a new blocker in persistent context."""
    ctx = get_partner_context(project_id, user_id)
    blockers = ctx.get("blockers", [])
    new_blocker = {
        "id": f"blk_{int(datetime.now(timezone.utc).timestamp())}",
        "title": title,
        "description": description,
        "impact": impact,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    blockers.append(new_blocker)
    return update_context(project_id, user_id, {"blockers": blockers})


def resolve_blocker(project_id: int, user_id: str, blocker_id: str, resolution_notes: str = "") -> dict:
    """Marks a blocker as resolved in persistent context."""
    ctx = get_partner_context(project_id, user_id)
    blockers = ctx.get("blockers", [])
    for b in blockers:
        if b.get("id") == blocker_id:
            b["status"] = "resolved"
            b["resolved_at"] = datetime.now(timezone.utc).isoformat()
            b["resolution_notes"] = resolution_notes
    return update_context(project_id, user_id, {"blockers": blockers})


def add_followup(project_id: int, user_id: str, contact_name: str, contact_email: str, reason: str, due_date: str = "") -> dict:
    """Records a pending follow-up in persistent context."""
    ctx = get_partner_context(project_id, user_id)
    followups = ctx.get("pending_followups", [])
    new_fu = {
        "id": f"fu_{int(datetime.now(timezone.utc).timestamp())}",
        "contact_name": contact_name,
        "contact_email": contact_email,
        "reason": reason,
        "due_date": due_date,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    followups.append(new_fu)
    return update_context(project_id, user_id, {"pending_followups": followups})


def complete_followup(project_id: int, user_id: str, followup_id: str) -> dict:
    """Marks a pending follow-up as completed."""
    ctx = get_partner_context(project_id, user_id)
    followups = ctx.get("pending_followups", [])
    for f in followups:
        if f.get("id") == followup_id:
            f["status"] = "completed"
            f["completed_at"] = datetime.now(timezone.utc).isoformat()
    return update_context(project_id, user_id, {"pending_followups": followups})


# ══════════════════════════════════════════════════════════════════════════════
# 2. PROACTIVE DAILY BRIEFING GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_daily_partner_briefing(analysis: Dict[str, Any], context: Dict[str, Any], groq_client=None) -> Dict[str, Any]:
    """
    Generates a structured, concise daily business briefing containing:
      1. Today's top three priorities
      2. Specific next actions grounded in actual deliverables
      3. Important upcoming deadlines & milestones
      4. Pending follow-ups
      5. Potential blockers
      6. One practical tactical recommendation
      7. Progress achieved since yesterday
    """
    current_week = analysis.get("current_week", 1)
    total_weeks = analysis.get("total_weeks", 12)
    score = analysis.get("lock_in_score", 0)
    streak = analysis.get("current_streak", 0)
    title = analysis.get("title", "Roadmap")
    priority_tasks = analysis.get("priority_tasks", [])
    overdue_tasks = analysis.get("overdue_tasks", [])
    milestone = analysis.get("current_milestone")
    completed_today = analysis.get("tasks_completed_today", 0)

    # Context items
    active_blockers = [b for b in context.get("blockers", []) if b.get("status") == "active"]
    pending_followups = [f for f in context.get("pending_followups", []) if f.get("status") == "pending"]
    weekly_priorities = context.get("weekly_priorities", [])

    # Extract Top 3 Priorities
    top_3 = []
    if active_blockers:
        top_3.append({
            "title": f"Clear Blocker: {active_blockers[0].get('title')}",
            "details": active_blockers[0].get("description", "Resolve roadblock to unblock execution pace."),
            "type": "blocker_resolution"
        })
    for t in priority_tasks:
        if len(top_3) >= 3:
            break
        top_3.append({
            "title": t.get("title", "Task"),
            "details": t.get("description", ""),
            "type": "roadmap_task",
            "hours": t.get("hours", 2),
            "category": t.get("category", "ops")
        })

    # Tactical practical recommendation based on state and blockers
    if active_blockers:
        recommendation = f"Immediate Bottleneck: Address '{active_blockers[0].get('title')}' first before starting new tasks. Seek outside feedback or break it into smaller 30-minute chunks."
    elif overdue_tasks:
        recommendation = f"Catch-up Focus: You have {len(overdue_tasks)} task(s) from earlier weeks. Focus exclusively on the single highest-impact overdue item today to eliminate backlog drag."
    elif milestone and milestone.get("week") == current_week:
        recommendation = f"Milestone Sprint: Week {current_week} targets deliverable '{milestone.get('title')}'. Validate core assumptions with end users before locking in code."
    elif streak >= 3:
        recommendation = "Maintain Cadence: Solid consistency! Knock out today's primary deliverable early in your work block while energy is highest."
    else:
        recommendation = "Execution Rhythm: Focus on concrete, ship-ready outputs today. Done is better than perfect."

    # Next actions list
    next_actions = []
    for p in top_3:
        hrs_str = f" (~{p.get('hours')}h)" if p.get("hours") else ""
        next_actions.append(f"{p['title']}{hrs_str}")

    deadline_str = f"Week {milestone.get('week')} Milestone: {milestone.get('title')}" if milestone else f"Week {current_week} Deliverables"

    briefing_data = {
        "date": date.today().isoformat(),
        "week": current_week,
        "total_weeks": total_weeks,
        "score": score,
        "streak": streak,
        "top_three_priorities": top_3,
        "specific_next_actions": next_actions,
        "important_deadlines": [deadline_str],
        "pending_followups": pending_followups[:3],
        "potential_blockers": active_blockers[:3],
        "practical_recommendation": recommendation,
        "recent_progress": f"{completed_today} task(s) completed today · Week pace: {analysis.get('current_week_pct', 0)}%"
    }

    return briefing_data


# ══════════════════════════════════════════════════════════════════════════════
# 3. WEEKLY BUSINESS REVIEW & REPLANNING
# ══════════════════════════════════════════════════════════════════════════════

def generate_weekly_partner_review(analysis: Dict[str, Any], context: Dict[str, Any], groq_client=None) -> Dict[str, Any]:
    """
    Summarizes:
      - Planned vs completed tasks
      - Missed deadlines and identified causes
      - Progress toward milestone goals
      - Recorded decisions & commitments
      - Bottlenecks
      - Recommended schedule adjustments for next week
    """
    current_week = analysis.get("current_week", 1)
    tasks_done_this_week = analysis.get("tasks_completed_this_week", 0)
    total_week_tasks = analysis.get("current_week_tasks_count", 0)
    week_pct = analysis.get("current_week_pct", 0)
    overdue = analysis.get("overdue_tasks", [])
    active_blockers = [b for b in context.get("blockers", []) if b.get("status") == "active"]
    decisions = context.get("decisions", [])
    commitments = context.get("commitments", [])

    # Identify causes of missed tasks without unfair penalization
    causes = []
    if active_blockers:
        causes.append(f"Recorded Blockers: {', '.join([b.get('title') for b in active_blockers])}")
    if len(overdue) > 0:
        causes.append(f"Overdue Dependencies: {len(overdue)} earlier items required attention")

    # Replanning advice
    if len(overdue) >= 3 or week_pct < 40:
        adjustment = f"Recommend rescheduling {min(2, len(overdue))} lower-priority items into Week {current_week + 1} to reset bandwidth and protect focus."
    elif week_pct >= 80:
        adjustment = "Excellent pace! Plan is well-balanced. Transition cleanly into next week's focus areas."
    else:
        adjustment = "Pacing is steady. Finalize the remaining 1-2 deliverables before opening next week's backlog."

    return {
        "week": current_week,
        "planned_tasks_count": total_week_tasks,
        "completed_tasks_count": tasks_done_this_week,
        "completion_rate_pct": week_pct,
        "overdue_tasks_count": len(overdue),
        "identified_causes": causes,
        "milestone_progress": f"Targeting {analysis.get('current_milestone', {}).get('title', 'Weekly targets')}",
        "decisions_recorded": len(decisions),
        "outstanding_commitments": len([c for c in commitments if c.get("status") != "completed"]),
        "active_bottlenecks": [b.get("title") for b in active_blockers],
        "recommended_adjustment": adjustment,
        "lock_in_score": analysis.get("lock_in_score", 0),
        "trend": analysis.get("progress_trend", "Steady pace"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. NATURAL HUMAN PROFESSIONAL GMAIL COMMUNICATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def compose_email_draft(
    workflow_type: str,
    recipient: str = "",
    subject_hint: str = "",
    context_data: Dict[str, Any] = None,
    groq_client=None
) -> Tuple[str, str, str]:
    if context_data is None:
        context_data = {}
    """
    Composes a natural, concise, professional email draft.
    Writing principles:
      - Sounds like a competent human professional / founder
      - Concise, natural subject line
      - Zero generic AI buzzwords or filler ('I hope this email finds you well')
      - Grounded strictly in provided facts
      - Includes clear next step and realistic timeline
    Returns: (subject, text_body, html_body)
    """
    settings = get_settings()

    # Pre-structure based on workflow type
    if workflow_type == "daily_briefing":
        subject = f"Daily Briefing — Week {context_data.get('week')}, Day Focus ({date.today().strftime('%b %d')})"
        briefing = context_data.get("briefing", {})
        priorities = briefing.get("top_three_priorities", [])
        p_lines = [f"• {p['title']}" for p in priorities]
        p_text = "\n".join(p_lines) if p_lines else "• Continue executing scheduled week deliverables"

        text_body = f"""{subject}

Here is your daily execution focus for today:

Top Priorities:
{p_text}

Deadlines & Milestones:
• {', '.join(briefing.get('important_deadlines', ['Maintain weekly pace']))}

Partner Recommendation:
{briefing.get('practical_recommendation', 'Focus on concrete output today.')}

Execution Score: {briefing.get('score', 0)}/100 · Streak: {briefing.get('streak', 0)} days

— LOCK IN AI Business Partner
"""
        html_body = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0c1222; color: #f1f5f9; padding: 24px; border-radius: 14px; max-width: 580px; border: 1px solid rgba(59,130,246,0.3);">
          <div style="font-size: 11px; font-weight: 800; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px;">LOCK IN AI · Business Partner Briefing</div>
          <h2 style="font-size: 19px; font-weight: 800; color: #f8fafc; margin: 6px 0 16px 0;">{subject}</h2>
          
          <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 14px; margin-bottom: 16px;">
            <div style="font-size: 12px; font-weight: 800; color: #60a5fa; margin-bottom: 8px;">TOP PRIORITIES FOR TODAY</div>
            <div style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">
              {("<br/>").join(p_lines) if p_lines else "Keep moving forward on current milestones."}
            </div>
          </div>

          <div style="font-size: 13px; color: #94a3b8; line-height: 1.5; margin-bottom: 16px;">
            <strong style="color: #e2e8f0;">Practical Recommendation:</strong><br/>
            {briefing.get('practical_recommendation', 'Execute high-leverage deliverables first.')}
          </div>

          <div style="border-top: 1px solid rgba(255,255,255,0.06); padding-top: 12px; font-size: 11px; color: #64748b;">
            Score: <strong style="color:#38bdf8;">{briefing.get('score', 0)}/100</strong> · Streak: <strong style="color:#fb923c;">{briefing.get('streak', 0)}d</strong> · Sent securely via Gmail
          </div>
        </div>
        """
        return subject, text_body, html_body

    elif workflow_type == "followup":
        contact_name = context_data.get("contact_name", "Partner")
        topic = context_data.get("topic", "our recent discussion")
        specific_ask = context_data.get("specific_ask", "checking in on next steps")
        sender_name = context_data.get("sender_name", "Founder")

        subject = subject_hint or f"Quick follow-up regarding {topic}"
        text_body = f"""Hi {contact_name},

Following up on {topic}.

Wanted to check if you had a chance to review this, and whether {specific_ask}.

Happy to sync briefly if you have questions or want to align on timing.

Best regards,
{sender_name}
"""
        html_body = f"""<div style="font-family: sans-serif; font-size: 14px; line-height: 1.6; color: #1e293b;">
<p>Hi {contact_name},</p>
<p>Following up on {topic}.</p>
<p>Wanted to check if you had a chance to review this, and whether {specific_ask}.</p>
<p>Happy to sync briefly if you have questions or want to align on timing.</p>
<p>Best regards,<br/><strong>{sender_name}</strong></p>
</div>"""
        return subject, text_body, html_body

    elif workflow_type == "meeting_request":
        contact_name = context_data.get("contact_name", "Partner")
        agenda = context_data.get("agenda", "discussing project milestones and collaboration")
        proposed_times = context_data.get("proposed_times", "later this week")
        sender_name = context_data.get("sender_name", "Founder")

        subject = subject_hint or f"Sync on {agenda}"
        text_body = f"""Hi {contact_name},

I would like to propose a short 15-20 minute conversation to discuss {agenda}.

Would {proposed_times} work on your calendar? If another time is more convenient for you, please let me know what suits you best.

Best regards,
{sender_name}
"""
        html_body = f"""<div style="font-family: sans-serif; font-size: 14px; line-height: 1.6; color: #1e293b;">
<p>Hi {contact_name},</p>
<p>I would like to propose a short 15-20 minute conversation to discuss {agenda}.</p>
<p>Would <strong>{proposed_times}</strong> work on your calendar? If another time is more convenient, please let me know what suits you best.</p>
<p>Best regards,<br/><strong>{sender_name}</strong></p>
</div>"""
        return subject, text_body, html_body

    elif workflow_type == "progress_update":
        contact_name = context_data.get("contact_name", "Advisor")
        project_name = context_data.get("project_name", "Startup")
        wins = context_data.get("wins", ["Completed scheduled sprint deliverables", "Maintained execution targets"])
        next_steps = context_data.get("next_steps", ["Launch customer validation", "Begin next milestone"])
        sender_name = context_data.get("sender_name", "Founder")

        wins_str = "\n".join([f"• {w}" for w in wins])
        next_str = "\n".join([f"• {n}" for n in next_steps])

        subject = subject_hint or f"{project_name} — Progress Update"
        text_body = f"""Hi {contact_name},

Sharing a concise update on our recent progress with {project_name}:

Recent Deliverables Completed:
{wins_str}

Immediate Next Steps:
{next_str}

We appreciate your ongoing support. Feel free to let me know if you have feedback or suggestions.

Best regards,
{sender_name}
"""
        html_body = f"""<div style="font-family: sans-serif; font-size: 14px; line-height: 1.6; color: #1e293b;">
<p>Hi {contact_name},</p>
<p>Sharing a concise update on our recent progress with <strong>{project_name}</strong>:</p>
<p><strong>Recent Deliverables Completed:</strong><br/>{('<br/>').join(['• ' + w for w in wins])}</p>
<p><strong>Immediate Next Steps:</strong><br/>{('<br/>').join(['• ' + n for n in next_steps])}</p>
<p>We appreciate your ongoing support. Feel free to reply with any thoughts or advice.</p>
<p>Best regards,<br/><strong>{sender_name}</strong></p>
</div>"""
        return subject, text_body, html_body

    elif workflow_type == "networking_outreach":
        contact_name = context_data.get("contact_name", "Mentor")
        mutual_interest = context_data.get("mutual_interest", "your work in the startup ecosystem")
        startup_summary = context_data.get("startup_summary", "building Startup Blueprint AI")
        specific_question = context_data.get("specific_question", "one specific question on early-stage go-to-market execution")
        sender_name = context_data.get("sender_name", "Founder")

        subject = subject_hint or f"Introduction & Question regarding {mutual_interest}"
        text_body = f"""Hi {contact_name},

I've been following {mutual_interest} and really value your insights.

I am currently {startup_summary}. As we tackle our current roadmap, I would deeply value your perspective on {specific_question}.

If you have 10 minutes for a brief exchange, I would be grateful. If your schedule is currently full, I completely understand as well.

Best regards,
{sender_name}
"""
        html_body = f"""<div style="font-family: sans-serif; font-size: 14px; line-height: 1.6; color: #1e293b;">
<p>Hi {contact_name},</p>
<p>I've been following {mutual_interest} and value your perspective.</p>
<p>I am currently {startup_summary}. As we tackle our current milestones, I would value your input on <strong>{specific_question}</strong>.</p>
<p>If you have 10 minutes for a brief exchange, I would be very grateful. No problem at all if your schedule is packed.</p>
<p>Best regards,<br/><strong>{sender_name}</strong></p>
</div>"""
        return subject, text_body, html_body

    # Default fallback
    subject = subject_hint or "Message from Founder"
    text_body = f"Hi {recipient},\n\n{context_data.get('body_content', 'Following up on our startup roadmap deliverables.')}\n\nBest regards,\nFounder"
    html_body = f"<p>Hi {recipient},</p><p>{context_data.get('body_content', 'Following up on our startup roadmap deliverables.')}</p><p>Best regards,<br/>Founder</p>"
    return subject, text_body, html_body


# ══════════════════════════════════════════════════════════════════════════════
# 5. APPROVAL & AUTONOMY GATE
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_safety_and_approval(
    project_id: int,
    user_id: str,
    recipient: str,
    subject: str,
    body_text: str,
    workflow_type: str,
) -> Tuple[bool, str]:
    """
    Evaluates whether an email draft can be dispatched automatically or requires mandatory human approval.
    Rules:
      1. If preferences 'automation_mode' == 'draft_only' -> NEVER SEND (Requires approval / Save draft).
      2. If preferences 'automation_mode' == 'approve_before_sending' (DEFAULT) -> REQUIRES APPROVAL.
      3. If preferences 'is_paused' is True -> NEVER SEND.
      4. If recipient is NOT in user's 'trusted_contacts' -> REQUIRES APPROVAL.
      5. If body contains sensitive commitments (contract, financial, legal, hiring) -> REQUIRES APPROVAL.
      6. If daily outbound count exceeds 'daily_send_limit' -> REQUIRES APPROVAL.
    Returns: (can_auto_send: bool, reason: str)
    """
    prefs = get_preferences(project_id, user_id)
    mode = prefs.get("automation_mode", "approve_before_sending")
    is_paused = prefs.get("is_paused", False)
    trusted_contacts = prefs.get("trusted_contacts", [])
    trusted_emails = [c.get("email", "").lower().strip() for c in trusted_contacts if isinstance(c, dict)]

    if is_paused:
        return False, "Agent sending is currently paused by emergency stop preference."

    if mode == "draft_only":
        return False, "Automation mode is set to 'Draft only'. User review required."

    # Identify if recipient is authenticated user's own email (self-accountability)
    conn = get_gmail_connection(user_id)
    user_self_email = ""
    if conn:
        user_self_email = (conn.get("google_email") or conn.get("user_email") or "").lower().strip()
    is_self_send = bool(recipient and user_self_email and recipient.lower().strip() == user_self_email)

    if is_self_send:
        # Self-accountability briefing or milestone reminder to the user's own verified address
        return True, "Authorized self-accountability briefing dispatch to authenticated user."

    # External email policy:
    if mode == "approve_before_sending":
        return False, "Default safety policy: 'Approve before sending' requires user authorization for external emails."

    # In 'trusted_automation' mode for external recipients:
    if recipient.lower().strip() not in trusted_emails:
        return False, f"Recipient {recipient} is not in your configured Trusted Contacts list."

    # Check for sensitive commitments
    full_text = f"{subject} {body_text}".lower()
    for pattern in SENSITIVE_COMMITMENT_PATTERNS:
        if re.search(pattern, full_text):
            return False, "Message contains sensitive financial, contractual, or employment commitments requiring manual verification."

    # Check daily send limits
    limit = prefs.get("daily_send_limit", 5)
    today_drafts = get_project_email_drafts(project_id, user_id, status="sent", limit=50)
    today_date = date.today()
    sends_today = 0
    for d in today_drafts:
        sent_at = d.get("sent_at")
        if sent_at and str(sent_at)[:10] == today_date.isoformat():
            sends_today += 1

    if sends_today >= limit:
        return False, f"Daily trusted sending limit ({limit} emails) reached for today."

    return True, "Authorized by trusted automation rules."


async def prepare_or_send_action(
    project_id: int,
    user_id: str,
    workflow_type: str,
    recipient: str,
    subject: str,
    body_text: str,
    body_html: str = "",
    context_data: dict = None,
    force_send: bool = False
) -> Dict[str, Any]:
    """
    Controlled observable action handler:
      1. Evaluates approval safety rules
      2. If approval is required or force_send is False: creates draft with status 'pending_approval'
      3. If auto-send is authorized or force_send is True: dispatches email via Gmail REST API
      4. Updates activity log and notification history
    """
    can_auto_send, reason = evaluate_safety_and_approval(
        project_id=project_id,
        user_id=user_id,
        recipient=recipient,
        subject=subject,
        body_text=body_text,
        workflow_type=workflow_type
    )

    should_send = force_send or can_auto_send

    if not should_send:
        # Create draft requiring human approval
        draft_id = create_email_draft(
            project_id=project_id,
            user_id=user_id,
            workflow_type=workflow_type,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            context_data=context_data,
            status="pending_approval",
            requires_approval=True
        )

        create_agent_action(
            project_id=project_id,
            user_id=user_id,
            action_type="EMAIL_DRAFT_PENDING_APPROVAL",
            title=f"Prepared Draft for {recipient}: {subject}",
            description=f"Requires user approval. Policy: {reason}",
            details={"draft_id": draft_id, "recipient": recipient, "workflow": workflow_type},
            requires_approval=True
        )

        return {
            "status": "pending_approval",
            "draft_id": draft_id,
            "requires_approval": True,
            "reason": reason,
            "recipient": recipient,
            "subject": subject
        }

    # Dispatch email
    try:
        msg_id = await send_gmail_email(user_id, recipient, subject, body_text, body_html)
        
        draft_id = create_email_draft(
            project_id=project_id,
            user_id=user_id,
            workflow_type=workflow_type,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            context_data=context_data,
            status="sent",
            requires_approval=False
        )
        mark_email_draft_sent(draft_id, user_id, msg_id)

        record_notification(
            project_id=project_id,
            user_id=user_id,
            notification_type=workflow_type,
            subject=subject,
            status="sent",
            provider_message_id=msg_id,
            local_date=date.today().isoformat()
        )

        create_agent_action(
            project_id=project_id,
            user_id=user_id,
            action_type="EMAIL_SENT_AUTOMATED",
            title=f"Sent {workflow_type.replace('_', ' ').capitalize()} to {recipient}",
            description=f"Message ID: {msg_id}",
            details={"message_id": msg_id, "recipient": recipient, "workflow": workflow_type},
            requires_approval=False
        )

        return {
            "status": "sent",
            "message_id": msg_id,
            "draft_id": draft_id,
            "recipient": recipient,
            "subject": subject
        }

    except Exception as e:
        log.error(f"[PARTNER ENGINE] Failed to dispatch email to {recipient}: {e}")
        draft_id = create_email_draft(
            project_id=project_id,
            user_id=user_id,
            workflow_type=workflow_type,
            recipient=recipient,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            context_data=context_data,
            status="failed",
            requires_approval=False
        )
        return {
            "status": "failed",
            "error": str(e),
            "draft_id": draft_id,
            "recipient": recipient
        }
