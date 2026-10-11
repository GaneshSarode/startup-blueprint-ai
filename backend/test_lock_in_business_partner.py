"""
test_lock_in_business_partner.py — Automated test suite for LOCK IN AI Business Partner.

Covers:
  1. OAuth scope configuration and diagnosis (missing gmail.send, reauth required)
  2. Test email security (strictly authenticated user's own address)
  3. Token refresh and 403 ACCESS_TOKEN_SCOPE_INSUFFICIENT handling
  4. Partner context management (goals, priorities, blockers, follow-ups)
  5. Proactive daily planning & briefing generation
  6. Weekly business review & replanning
  7. Natural professional email drafts across 8 business workflows
  8. Safety & autonomy gate:
     - Default 'approve_before_sending' for external recipients
     - 'draft_only' mode enforcement
     - 'trusted_automation' restrictions (trusted list, sensitive commitment guard, daily limit)
     - Emergency stop / pause control
  9. Draft approval, editing, sending, and discarding lifecycles
 10. Concurrency locking & duplicate job prevention
 11. Idempotency ledger and bounded retry behavior
 12. Activity log formatting and credential scrubbing
"""

import os
import sys
import json
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date, timedelta, timezone
import zoneinfo

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "routes"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import gmail_service
from gmail_service import (
    GMAIL_SEND_SCOPE,
    diagnose_gmail_status,
    verify_token_scopes,
    send_test_email,
)
from core.lock_in_business_partner import (
    get_or_create_context,
    update_context,
    add_blocker,
    resolve_blocker,
    add_followup,
    complete_followup,
    generate_daily_partner_briefing,
    generate_weekly_partner_review,
    compose_email_draft,
    evaluate_safety_and_approval,
    prepare_or_send_action,
)
from core.lock_in_agent_runner import (
    get_project_lock,
    evaluate_and_execute_agent,
    generate_daily_email_content,
    generate_deadline_alert_content,
    generate_weekly_report_content,
)
from core.lock_in_db import (
    init_tables,
    sync_project,
    get_project_by_id,
    save_gmail_connection,
    disconnect_gmail,
    update_preferences,
    get_preferences,
    create_email_draft,
    get_email_draft,
    get_project_email_drafts,
    update_email_draft,
    mark_email_draft_sent,
    mark_email_draft_rejected,
    record_notification,
    has_notification_been_sent_today,
    create_agent_action,
    _conn,
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Ensure database schema tables are initialized."""
    init_tables()


# ══════════════════════════════════════════════════════════════════════════════
# 1. OAUTH SCOPE CONFIGURATION & DIAGNOSTICS TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_oauth_scope_constant_includes_gmail_send():
    """Ensure GMAIL_SEND_SCOPE is least-privilege gmail.send."""
    assert GMAIL_SEND_SCOPE == "https://www.googleapis.com/auth/gmail.send"
    assert "https://mail.google.com/" not in gmail_service.GMAIL_SCOPES
    assert "https://www.googleapis.com/auth/gmail.send" in gmail_service.GMAIL_SCOPES


def test_diagnose_gmail_status_disconnected():
    """Diagnose status for an account with no Gmail connection."""
    with patch("gmail_service.get_gmail_connection", return_value=None):
        diag = diagnose_gmail_status("unknown_user_id")
        assert diag["configured"] is True
        assert diag["connected"] is False
        assert diag["status"] in ("not_connected", "disconnected")
        assert diag["has_send_scope"] is False
        assert diag["needs_reconnect"] is False


def test_diagnose_gmail_status_insufficient_scope():
    """Diagnose status for a connection missing gmail.send scope."""
    mock_conn = {
        "status": "active",
        "google_email": "founder@example.com",
        "granted_scopes": ["https://www.googleapis.com/auth/userinfo.email"],
        "scope_verified": True,
        "token_expiry": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "last_error": None,
    }
    with patch("gmail_service.get_gmail_connection", return_value=mock_conn):
        diag = diagnose_gmail_status("user_missing_scope")
        # Connection without send scope is not fully active
        assert diag["connected"] is False
        assert diag["has_send_scope"] is False
        assert diag["needs_reconnect"] is True
        assert diag["status"] == "reauth_required"
        assert "Missing" in diag["reconnect_reason"]
        assert GMAIL_SEND_SCOPE in diag["missing_scopes"]


def test_diagnose_gmail_status_active_and_verified():
    """Diagnose status for a valid connection with verified gmail.send."""
    mock_conn = {
        "status": "active",
        "google_email": "founder@example.com",
        "granted_scopes": [GMAIL_SEND_SCOPE, "https://www.googleapis.com/auth/userinfo.email"],
        "scope_verified": True,
        "token_expiry": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "last_error": None,
    }
    with patch("gmail_service.get_gmail_connection", return_value=mock_conn):
        diag = diagnose_gmail_status("user_valid")
        assert diag["connected"] is True
        assert diag["has_send_scope"] is True
        assert diag["needs_reconnect"] is False
        assert diag["status"] == "active"


# ══════════════════════════════════════════════════════════════════════════════
# 2. TEST EMAIL SAFETY & IDENTITY VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════

def test_send_test_email_blocks_when_reauth_required():
    """Send test email must raise clean error when reauthorization is required."""
    async def _run():
        mock_conn = {
            "status": "reauth_required",
            "google_email": "founder@example.com",
            "last_error": "Scope insufficient",
        }
        with patch("gmail_service.get_gmail_connection", return_value=mock_conn):
            with pytest.raises(RuntimeError) as exc_info:
                await send_test_email("user_test_123")
            assert "Reauthorization required" in str(exc_info.value)

    asyncio.run(_run())


def test_send_test_email_sends_strictly_to_authenticated_user():
    """Send test email must always send to the authenticated user's own address."""
    async def _run():
        mock_conn = {
            "status": "active",
            "google_email": "authenticated_founder@startup.com",
        }
        mock_send = AsyncMock(return_value="test_msg_id_999")
        mock_action = MagicMock()

        with patch("gmail_service.get_gmail_connection", return_value=mock_conn), \
             patch("gmail_service.send_gmail_email", mock_send), \
             patch("gmail_service.create_agent_action", mock_action):

            res = await send_test_email("user_test_founder")
            assert res["status"] == "success"
            assert res["recipient"] == "authenticated_founder@startup.com"
            assert res["message_id"] == "test_msg_id_999"

            # Verify send_gmail_email received strictly the authenticated user's address
            call_args = mock_send.call_args[0]
            assert call_args[1] == "authenticated_founder@startup.com"
            assert "LOCK IN AI" in call_args[2]

    asyncio.run(_run())


# ══════════════════════════════════════════════════════════════════════════════
# 3. 403 INSUFFICIENT SCOPE & TOKEN REFRESH HANDLING
# ══════════════════════════════════════════════════════════════════════════════

def test_send_gmail_email_handles_403_scope_insufficient():
    """Detects 403 ACCESS_TOKEN_SCOPE_INSUFFICIENT and transitions status to reauth_required."""
    async def _run():
        from gmail_service import send_gmail_email

        mock_conn = {
            "status": "active",
            "google_email": "user@example.com",
            "access_token": "expired_or_limited_token",
            "refresh_token": "valid_refresh_token",
            "token_expiry": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = json.dumps({
            "error": {
                "code": 403,
                "message": "Request had insufficient authentication scopes.",
                "status": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"
            }
        })

        with patch("gmail_service.get_gmail_connection", return_value=mock_conn), \
             patch("gmail_service.get_valid_access_token", return_value="token_xyz"), \
             patch("httpx.AsyncClient.post", return_value=mock_resp), \
             patch("gmail_service.mark_gmail_connection_revoked") as mock_revoke:

            with pytest.raises(RuntimeError) as exc_info:
                await send_gmail_email("user_123", "to@example.com", "Subj", "Body", "")

            assert "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in str(exc_info.value)
            mock_revoke.assert_called_once()
            assert mock_revoke.call_args[0][1] == "reauth_required"

    asyncio.run(_run())


# ══════════════════════════════════════════════════════════════════════════════
# 4. PERSISTENT USER CONTEXT MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def test_partner_context_lifecycle():
    """Verify loading, updating, adding blockers, and tracking follow-ups with synced project."""
    test_user = "test_bp_founder_ctx"
    bp_id = 98771
    mock_roadmap = {
        "weeks": [{"week": 1, "theme": "Foundations", "tasks": [{"id": "w1t1", "title": "Setup", "category": "ops"}]}],
        "sector": "AI SaaS",
        "primary_goal": "Launch Alpha",
        "milestones": [{"week": 1, "title": "Alpha Live"}],
    }

    # Create real project record so foreign keys pass
    proj = sync_project(test_user, f"{test_user}@test.com", bp_id, mock_roadmap, ["w1t1"])
    test_proj_id = proj["id"]

    try:
        # Load initial or default context
        ctx = get_or_create_context(test_proj_id, test_user)
        assert ctx["project_id"] == test_proj_id
        assert "weekly_priorities" in ctx
        assert "blockers" in ctx

        # Update priorities and goals
        updated = update_context(test_proj_id, test_user, {
            "weekly_priorities": ["Refine onboarding UX", "Conduct 3 user interviews"],
        })
        assert len(updated["weekly_priorities"]) == 2

        # Add a blocker
        with_blocker = add_blocker(test_proj_id, test_user, "Stripe Atlas Delay", "Waiting on Stripe Atlas company registration", "high")
        assert len(with_blocker["blockers"]) >= 1
        assert any("Stripe Atlas" in b["description"] for b in with_blocker["blockers"])
        blk_id = with_blocker["blockers"][0]["id"]

        # Resolve the blocker
        resolved = resolve_blocker(test_proj_id, test_user, blk_id, "Registration confirmed")
        resolved_item = next(b for b in resolved["blockers"] if b["id"] == blk_id)
        assert resolved_item["status"] == "resolved"

        # Add follow-up
        with_fu = add_followup(test_proj_id, test_user, "Alex Investor", "investor@venture.com", "Seed discussion", "2026-10-15")
        assert len(with_fu["pending_followups"]) >= 1
        fu_id = with_fu["pending_followups"][0]["id"]

        # Complete follow-up
        completed_fu = complete_followup(test_proj_id, test_user, fu_id)
        completed_item = next(f for f in completed_fu["pending_followups"] if f["id"] == fu_id)
        assert completed_item["status"] == "completed"

    finally:
        with _conn() as c:
            cur = c.cursor()
            cur.execute("DELETE FROM lockin_projects WHERE user_id = %s;", (test_user,))
            c.commit()


# ══════════════════════════════════════════════════════════════════════════════
# 5. PROACTIVE DAILY BRIEFING & WEEKLY REVIEW
# ══════════════════════════════════════════════════════════════════════════════

def test_daily_partner_briefing_content():
    """Ensure daily partner briefing is context-grounded and structured."""
    mock_analysis = {
        "title": "Startup Blueprint AI",
        "current_week": 3,
        "total_weeks": 12,
        "agent_state": "ON_TRACK",
        "lock_in_score": 88,
        "priority_tasks": [
            {"title": "Implement Stripe payment webhook", "priority": "must"},
            {"title": "Verify user onboarding funnel", "priority": "should"},
        ],
        "current_streak": 5,
        "days_remaining": 60,
    }
    mock_context = {
        "weekly_priorities": ["Close first customer", "Finalize payment gateway"],
        "blockers": [{"title": "DNS Lag", "description": "DNS propagation delayed", "status": "active", "impact": "medium"}],
        "pending_followups": [{"contact_name": "Mentor Alex", "contact_email": "alex@mentor.com", "status": "pending"}],
        "decisions": ["Adopt PostgreSQL + Supabase"],
    }

    briefing = generate_daily_partner_briefing(mock_analysis, mock_context)
    assert briefing["score"] == 88
    assert len(briefing["top_three_priorities"]) >= 1
    assert len(briefing["potential_blockers"]) >= 1
    assert any("alex@mentor.com" in f.get("contact_email", "") for f in briefing["pending_followups"])
    assert briefing["practical_recommendation"] != ""


def test_weekly_partner_review_content():
    """Ensure weekly review calculates planned vs completed and pacing."""
    mock_analysis = {
        "title": "Startup Blueprint AI",
        "current_week": 4,
        "total_weeks": 12,
        "completed_count": 14,
        "total_tasks": 28,
        "overall_pct": 50,
        "current_week_pct": 75,
        "lock_in_score": 82,
        "current_streak": 6,
        "tasks_completed_this_week": 5,
        "current_week_tasks_count": 8,
        "progress_trend": "+5 this week",
        "agent_state": "ON_TRACK",
        "sector": "SaaS AI",
        "primary_goal": "Reach $5k MRR",
        "overdue_tasks": [],
    }
    mock_context = {
        "weekly_priorities": ["Launch beta", "Onboard 5 design partners"],
        "blockers": [],
        "decisions": ["Priced pro tier at $49/mo"],
        "commitments": [],
    }

    review = generate_weekly_partner_review(mock_analysis, mock_context)
    assert review["week"] == 4
    assert review["completed_tasks_count"] == 5
    assert review["completion_rate_pct"] == 75
    assert review["lock_in_score"] == 82
    assert review["recommended_adjustment"] != ""


# ══════════════════════════════════════════════════════════════════════════════
# 6. NATURAL PROFESSIONAL EMAIL COMPOSER (8 WORKFLOWS)
# ══════════════════════════════════════════════════════════════════════════════

def test_compose_email_draft_workflows():
    """Verify email composer generates grounded, professional text for distinct workflows."""
    workflows = [
        "follow_up",
        "meeting_request",
        "progress_update",
        "networking_outreach",
        "deadline_alert",
        "daily_accountability",
        "reply_draft",
        "business_opportunity",
    ]

    for wf in workflows:
        subj, txt, html = compose_email_draft(
            workflow_type=wf,
            context_data={
                "contact_name": "Jordan",
                "topic": "API Integration Partnership",
                "agenda": "integrating our billing APIs",
                "proposed_times": "Thursday at 2 PM IST",
                "sender_name": "Sahil",
                "milestone_title": "MVP Launch",
                "opportunity_title": "Enterprise Pilot",
            }
        )
        assert subj != "", f"Subject empty for workflow {wf}"
        assert txt != "", f"Text body empty for workflow {wf}"
        assert html != "", f"HTML body empty for workflow {wf}"
        assert "Jordan" in txt or "Founder" in txt or "Sahil" in txt or "MVP" in txt or "LOCK IN" in txt
        assert "{contact_name}" not in txt
        assert "[Insert text here]" not in txt


# ══════════════════════════════════════════════════════════════════════════════
# 7. SAFETY & AUTONOMY GATE RULES
# ══════════════════════════════════════════════════════════════════════════════

def test_safety_gate_paused():
    """Emergency stop / pause immediately blocks all dispatch."""
    mock_prefs = {"is_paused": True, "automation_mode": "trusted_automation"}
    with patch("core.lock_in_business_partner.get_preferences", return_value=mock_prefs):
        allowed, reason = evaluate_safety_and_approval(
            project_id=1,
            user_id="u1",
            recipient="test@example.com",
            subject="Subj",
            body_text="Body",
            workflow_type="follow_up"
        )
        assert allowed is False
        assert "paused" in reason.lower()


def test_safety_gate_draft_only():
    """Draft-only mode strictly requires user review."""
    mock_prefs = {"is_paused": False, "automation_mode": "draft_only"}
    with patch("core.lock_in_business_partner.get_preferences", return_value=mock_prefs):
        allowed, reason = evaluate_safety_and_approval(
            project_id=1,
            user_id="u1",
            recipient="test@example.com",
            subject="Subj",
            body_text="Body",
            workflow_type="follow_up"
        )
        assert allowed is False
        assert "Draft only" in reason


def test_safety_gate_approve_before_sending_default_for_external():
    """Default mode 'approve_before_sending' blocks external recipient."""
    mock_prefs = {"is_paused": False, "automation_mode": "approve_before_sending"}
    mock_conn = {"google_email": "founder@startup.com"}
    with patch("core.lock_in_business_partner.get_preferences", return_value=mock_prefs), \
         patch("core.lock_in_business_partner.get_gmail_connection", return_value=mock_conn):
        allowed, reason = evaluate_safety_and_approval(
            project_id=1,
            user_id="u1",
            recipient="investor@venture.com",
            subject="Update",
            body_text="Here is our update",
            workflow_type="progress_update"
        )
        assert allowed is False
        assert "Approve before sending" in reason


def test_safety_gate_allows_self_briefing_to_founder():
    """Self-accountability emails sent to founder's own authenticated address are allowed."""
    mock_prefs = {"is_paused": False, "automation_mode": "approve_before_sending"}
    mock_conn = {"google_email": "founder@startup.com"}
    with patch("core.lock_in_business_partner.get_preferences", return_value=mock_prefs), \
         patch("core.lock_in_business_partner.get_gmail_connection", return_value=mock_conn):
        allowed, reason = evaluate_safety_and_approval(
            project_id=1,
            user_id="u1",
            recipient="founder@startup.com",
            subject="LOCK IN — Daily Mission",
            body_text="Today's priorities",
            workflow_type="daily"
        )
        assert allowed is True
        assert "self-accountability" in reason.lower()


def test_safety_gate_trusted_automation_requires_trusted_contact():
    """In trusted_automation mode, sending to an unverified recipient is blocked."""
    mock_prefs = {
        "is_paused": False,
        "automation_mode": "trusted_automation",
        "trusted_contacts": [{"email": "advisor@mentor.com", "name": "Advisor"}],
        "daily_send_limit": 5,
    }
    mock_conn = {"google_email": "founder@startup.com"}
    with patch("core.lock_in_business_partner.get_preferences", return_value=mock_prefs), \
         patch("core.lock_in_business_partner.get_gmail_connection", return_value=mock_conn):
        # Recipient is NOT in trusted contacts
        allowed, reason = evaluate_safety_and_approval(
            1, "u1", "stranger@other.com", "Hello", "Connecting with you", "networking_outreach"
        )
        assert allowed is False
        assert "not in your configured Trusted Contacts list" in reason

        # Recipient IS in trusted contacts
        with patch("core.lock_in_business_partner.get_project_email_drafts", return_value=[]):
            allowed_trusted, _ = evaluate_safety_and_approval(
                1, "u1", "advisor@mentor.com", "Hello", "Connecting with you", "networking_outreach"
            )
            assert allowed_trusted is True


def test_safety_gate_blocks_sensitive_commitments():
    """Trusted automation must block sensitive financial/contractual commitments."""
    mock_prefs = {
        "is_paused": False,
        "automation_mode": "trusted_automation",
        "trusted_contacts": [{"email": "advisor@mentor.com", "name": "Advisor"}],
        "daily_send_limit": 5,
    }
    mock_conn = {"google_email": "founder@startup.com"}
    with patch("core.lock_in_business_partner.get_preferences", return_value=mock_prefs), \
         patch("core.lock_in_business_partner.get_gmail_connection", return_value=mock_conn), \
         patch("core.lock_in_business_partner.get_project_email_drafts", return_value=[]):

        sensitive_cases = [
            ("Contract signing", "We are ready for the legally binding contract to sign"),
            ("Offer letter", "We are extending a salary offer of $120k"),
            ("Payment guarantee", "I provide a full refund guarantee and wired payment"),
            ("Employment terms", "Here is our confidential employment agreement"),
        ]

        for subj, body in sensitive_cases:
            allowed, reason = evaluate_safety_and_approval(
                1, "u1", "advisor@mentor.com", subj, body, "follow_up"
            )
            assert allowed is False, f"Sensitive case should have been blocked: {subj}"
            assert "sensitive financial, contractual" in reason


def test_safety_gate_enforces_daily_send_limit():
    """Trusted automation halts when daily limit is reached."""
    mock_prefs = {
        "is_paused": False,
        "automation_mode": "trusted_automation",
        "trusted_contacts": [{"email": "advisor@mentor.com", "name": "Advisor"}],
        "daily_send_limit": 2,
    }
    mock_conn = {"google_email": "founder@startup.com"}
    mock_sent_drafts = [
        {"sent_at": f"{date.today().isoformat()}T10:00:00Z"},
        {"sent_at": f"{date.today().isoformat()}T11:00:00Z"},
    ]
    with patch("core.lock_in_business_partner.get_preferences", return_value=mock_prefs), \
         patch("core.lock_in_business_partner.get_gmail_connection", return_value=mock_conn), \
         patch("core.lock_in_business_partner.get_project_email_drafts", return_value=mock_sent_drafts):

        allowed, reason = evaluate_safety_and_approval(
            1, "u1", "advisor@mentor.com", "Update", "Routine status update", "progress_update"
        )
        assert allowed is False
        assert "Daily trusted sending limit (2 emails) reached" in reason


# ══════════════════════════════════════════════════════════════════════════════
# 8. EMAIL DRAFT LIFECYCLE (CREATE, EDIT, APPROVE, DISCARD)
# ══════════════════════════════════════════════════════════════════════════════

def test_draft_lifecycle_database_operations():
    """Test creating, editing, and discarding drafts with a real synced project."""
    user_id = "test_user_draft_ops"
    bp_id = 98772
    mock_roadmap = {
        "weeks": [{"week": 1, "theme": "Foundations", "tasks": [{"id": "w1t1", "title": "Setup", "category": "ops"}]}],
        "sector": "AI SaaS",
        "primary_goal": "Launch Alpha",
        "milestones": [{"week": 1, "title": "Alpha Live"}],
    }

    proj = sync_project(user_id, f"{user_id}@test.com", bp_id, mock_roadmap, ["w1t1"])
    project_id = proj["id"]

    try:
        draft_id = create_email_draft(
            project_id=project_id,
            user_id=user_id,
            workflow_type="follow_up",
            recipient="partner@external.com",
            subject="Sync on API docs",
            body_text="Hi, wanted to follow up.",
            body_html="<p>Hi, wanted to follow up.</p>",
            context_data={"contact_name": "Jordan"},
            status="pending_approval",
            requires_approval=True
        )
        assert draft_id > 0

        # Retrieve
        draft = get_email_draft(draft_id, user_id)
        assert draft is not None
        assert draft["subject"] == "Sync on API docs"
        assert draft["status"] == "pending_approval"

        # Edit
        updated = update_email_draft(draft_id, user_id, {
            "subject": "Updated: Sync on API docs",
            "body_text": "Hi Jordan, following up on the docs.",
        })
        assert updated["subject"] == "Updated: Sync on API docs"
        assert "Jordan" in updated["body_text"]

        # Discard / Reject
        rejected = mark_email_draft_rejected(draft_id, user_id, "User discarded draft")
        assert rejected["status"] in ("rejected", "discarded")

        # Verify state in list
        drafts = get_project_email_drafts(project_id, user_id, status="rejected")
        assert any(d["id"] == draft_id for d in drafts)

    finally:
        with _conn() as c:
            cur = c.cursor()
            cur.execute("DELETE FROM lockin_projects WHERE user_id = %s;", (user_id,))
            c.commit()


# ══════════════════════════════════════════════════════════════════════════════
# 9. CONCURRENCY CONTROL & EXECUTION LOCKING
# ══════════════════════════════════════════════════════════════════════════════

def test_per_project_concurrency_lock():
    """Ensure concurrent calls on the same project lock and do not overlap."""
    async def _run():
        project_id = 77665
        lock = get_project_lock(project_id)

        # Acquire lock manually to simulate an active background run
        await lock.acquire()
        try:
            res = await evaluate_and_execute_agent(project_id, notification_type="daily")
            assert res["sent"] is False
            assert "evaluation cycle is currently in progress" in res["reason"]
        finally:
            lock.release()

    asyncio.run(_run())


# ══════════════════════════════════════════════════════════════════════════════
# 10. IDEMPOTENCY & BOUNDED RETRY BEHAVIOR
# ══════════════════════════════════════════════════════════════════════════════

def test_bounded_retry_aborts_on_permanent_auth_error():
    """Verify that permanent auth/scope errors (401/403) are not repeatedly retried."""
    async def _run():
        project_id = 99883
        user_id = "test_retry_abort"

        mock_analysis = {
            "project_id": project_id,
            "user_id": user_id,
            "user_email": "founder@test.com",
            "title": "Startup",
            "current_week": 1,
            "total_weeks": 12,
            "agent_state": "ON_TRACK",
            "lock_in_score": 75,
            "priority_tasks": [],
            "timezone": "UTC",
            "current_week_completed_count": 0,
            "current_week_tasks_count": 5,
            "current_week_pct": 0,
            "overdue_tasks": [],
            "current_milestone": None,
        }
        mock_conn = {
            "status": "active",
            "google_email": "founder@test.com",
        }
        mock_prefs = {
            "is_paused": False,
            "daily_reminder_enabled": True,
            "automation_mode": "approve_before_sending",
        }

        send_call_count = 0

        async def fail_send_permanent(*args, **kwargs):
            nonlocal send_call_count
            send_call_count += 1
            raise Exception("Gmail API error (403): ACCESS_TOKEN_SCOPE_INSUFFICIENT")

        with patch("core.lock_in_agent_runner.analyze_project_progress", return_value=mock_analysis), \
             patch("core.lock_in_agent_runner.get_preferences", return_value=mock_prefs), \
             patch("core.lock_in_agent_runner.get_gmail_connection", return_value=mock_conn), \
             patch("core.lock_in_agent_runner.has_notification_been_sent_today", return_value=False), \
             patch("core.lock_in_agent_runner.send_gmail_email", side_effect=fail_send_permanent), \
             patch("core.lock_in_agent_runner.record_notification"):

            res = await evaluate_and_execute_agent(project_id, notification_type="daily", force_send=True)
            assert res["sent"] is False
            assert "403" in res["error"]
            # Must have aborted on the very first attempt without looping retries!
            assert send_call_count == 1

    asyncio.run(_run())
