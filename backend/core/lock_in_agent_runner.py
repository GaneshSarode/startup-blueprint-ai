"""
lock_in_agent_runner.py — Decision layer, deterministic metric engine, and LLM generator for LOCK IN AI.

Architecture:
  1. Deterministic Metrics & State Analyzer (Total tasks, completed, current week, overdue, LOCK IN score)
  2. Level 1 Autonomous Actions (Daily accountability, deadline alerts, weekly reports)
  3. Level 2 & 3 Human-in-the-Loop (HITL) Recommendations (Recovery plans & task rescheduling)
  4. Idempotency & notification logging
"""

import json
import logging
from datetime import datetime, date, timedelta, timezone
import zoneinfo
from typing import Dict, Any, List, Optional
from config import get_settings
import os

from lock_in_db import (
    get_project_by_id,
    get_project_tasks,
    get_preferences,
    get_gmail_connection,
    record_notification,
    has_notification_been_sent_today,
    create_agent_action,
    get_pending_recommendations,
    calculate_momentum_and_streak,
)
from gmail_service import send_gmail_email

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DETERMINISTIC METRIC & PROGRESS ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def analyze_project_progress(project_id: int) -> Dict[str, Any]:
    """
    Deterministically computes all execution metrics, momentum, and streaks
    from the database without LLM hallucination.
    """
    project = get_project_by_id(project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    user_id = project.get("user_id")
    prefs = get_preferences(project_id, user_id)
    user_tz_str = prefs.get("timezone") or "Asia/Kolkata"

    try:
        user_tz = zoneinfo.ZoneInfo(user_tz_str)
    except Exception:
        user_tz = zoneinfo.ZoneInfo("UTC")

    tasks = get_project_tasks(project_id)
    roadmap = project.get("roadmap_data", {})
    weeks_list = roadmap.get("weeks", [])
    total_weeks = len(weeks_list) if weeks_list else 12

    # Date calculations
    start_date = project.get("start_date")
    if isinstance(start_date, str):
        try:
            start_date = date.fromisoformat(start_date)
        except Exception:
            start_date = date.today()
    elif isinstance(start_date, datetime):
        start_date = start_date.date()
    elif not start_date:
        start_date = date.today()

    local_now = datetime.now(user_tz)
    today_local = local_now.date()
    days_elapsed = max(0, (today_local - start_date).days)
    current_week = max(1, min(total_weeks, (days_elapsed // 7) + 1))
    
    duration_days = total_weeks * 7
    days_remaining = max(0, duration_days - days_elapsed)

    # Task metrics
    total_tasks = len(tasks)
    completed_tasks = [t for t in tasks if t["status"] == "completed"]
    pending_tasks = [t for t in tasks if t["status"] != "completed"]
    
    overall_pct = round((len(completed_tasks) / total_tasks * 100)) if total_tasks > 0 else 0

    # Current week tasks
    current_week_tasks = [t for t in tasks if t["week_number"] == current_week]
    current_week_completed = [t for t in current_week_tasks if t["status"] == "completed"]
    current_week_pending = [t for t in current_week_tasks if t["status"] != "completed"]
    current_week_pct = (
        round((len(current_week_completed) / len(current_week_tasks) * 100))
        if current_week_tasks else 100
    )

    # Overdue tasks (tasks from previous weeks that are still pending)
    overdue_tasks = [t for t in pending_tasks if t["week_number"] < current_week]

    # Upcoming milestones
    milestones = roadmap.get("milestones", [])
    current_milestone = None
    for m in milestones:
        m_week = m.get("week", 1)
        if m_week == current_week or (m_week == current_week + 1 and days_elapsed % 7 >= 5):
            current_milestone = m
            break

    # ── DETERMINISTIC LOCK IN SCORE ──────────────────────────────────────────
    # Formula:
    #   40% Overall Task Completion
    #   30% Current-Week Completion
    #   20% Deadline Adherence (penalized by overdue tasks)
    #   10% Consistency / Activity Bonus
    adherence_pct = max(0, 100 - (len(overdue_tasks) * 20))
    consistency_bonus = 10 if len(completed_tasks) > 0 else 0
    raw_score = (
        (0.40 * overall_pct) +
        (0.30 * current_week_pct) +
        (0.20 * adherence_pct) +
        consistency_bonus
    )
    lock_in_score = round(min(100, max(0, raw_score)))

    # Compute deterministic momentum and streak metrics
    momentum_data = calculate_momentum_and_streak(project_id, user_tz_str)

    # ── STATE CLASSIFICATION ─────────────────────────────────────────────────
    if overall_pct >= 100:
        agent_state = "ROADMAP_COMPLETED"
    elif len(overdue_tasks) >= 3 or (current_week > 1 and current_week_pct < 35 and len(overdue_tasks) >= 1):
        agent_state = "SIGNIFICANTLY_BEHIND"
    elif len(overdue_tasks) > 0 or (current_week_pct < 60 and days_elapsed % 7 >= 4):
        agent_state = "SLIGHTLY_BEHIND"
    elif current_milestone and current_milestone.get("week") == current_week and current_week_pct < 80:
        agent_state = "MILESTONE_DUE"
    elif momentum_data.get("momentum_state") == "STREAK_AT_RISK":
        agent_state = "STREAK_AT_RISK"
    else:
        agent_state = "ON_TRACK"

    # Today's priority tasks (top 2 must/should tasks from current week or top overdue)
    priority_tasks = []
    if overdue_tasks:
        priority_tasks.extend(overdue_tasks[:2])
    if len(priority_tasks) < 2:
        priority_tasks.extend(current_week_pending[:2 - len(priority_tasks)])

    return {
        "project_id": project_id,
        "blueprint_id": project.get("blueprint_id"),
        "user_id": project.get("user_id"),
        "user_email": project.get("user_email"),
        "title": roadmap.get("title", "Execution Roadmap"),
        "sector": roadmap.get("sector", "Startup"),
        "primary_goal": roadmap.get("primary_goal", "Launch MVP"),
        "total_tasks": total_tasks,
        "completed_count": len(completed_tasks),
        "pending_count": len(pending_tasks),
        "overall_pct": overall_pct,
        "current_week": current_week,
        "total_weeks": total_weeks,
        "current_week_tasks_count": len(current_week_tasks),
        "current_week_completed_count": len(current_week_completed),
        "current_week_pct": current_week_pct,
        "overdue_tasks": overdue_tasks,
        "priority_tasks": priority_tasks,
        "current_milestone": current_milestone,
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "lock_in_score": lock_in_score,
        "agent_state": agent_state,
        "roadmap": roadmap,
        "timezone": user_tz_str,
        # Momentum & Streak fields
        "current_streak": momentum_data["current_streak"],
        "longest_streak": momentum_data["longest_streak"],
        "tasks_completed_today": momentum_data["tasks_completed_today"],
        "tasks_completed_this_week": momentum_data["tasks_completed_this_week"],
        "tasks_completed_last_week": momentum_data["tasks_completed_last_week"],
        "active_days": momentum_data["active_days"],
        "progress_trend": momentum_data["progress_trend"],
        "momentum_state": momentum_data["momentum_state"],
    }


# ══════════════════════════════════════════════════════════════════════════════
# LLM EMAIL & CONTENT GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def _call_llm_json_or_text(groq_client, prompt: str, system: str = "") -> str:
    """Invokes LLM with fallback to structured text generation."""
    if groq_client:
        try:
            resp = groq_client.chat.completions.create(
                model=get_settings().GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system or "You are an elite, highly supportive startup execution coach."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            log.warning(f"Groq generation failed in lock_in_agent_runner: {e}")
    return ""


def generate_daily_email_content(analysis: Dict[str, Any], groq_client=None) -> tuple[str, str, str]:
    """
    Returns (subject, text_body, html_body) for the Smart Daily Accountability Email.
    Grounded strictly in deterministic metrics and tasks without hallucination.
    """
    title = analysis["title"]
    week = analysis["current_week"]
    total_w = analysis["total_weeks"]
    state = analysis["agent_state"]
    score = analysis["lock_in_score"]
    priority_tasks = analysis["priority_tasks"]
    streak = analysis.get("current_streak", 0)
    tasks_this_week = analysis.get("tasks_completed_this_week", 0)
    trend = analysis.get("progress_trend", "Steady pace")
    blueprint_id = analysis.get("blueprint_id", "")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    mission_cta_url = f"{frontend_url}/lock-in/{blueprint_id}" if blueprint_id else f"{frontend_url}/home"

    # Context-aware messaging based on deterministic state
    if state == "ROADMAP_COMPLETED":
        subject = f"🏆 LOCK IN — 100% Roadmap Completed! (Score: {score}/100)"
        state_badge = "<span style='background:rgba(59,130,246,0.2); color:#60a5fa; padding:4px 12px; border-radius:12px; font-weight:800; font-size:12px;'>🏆 ROADMAP COMPLETE</span>"
        personalized_msg = "Outstanding work! You have completed all deliverables across your entire roadmap. Review your achievements and transition into your next growth cycle."
    elif state == "SIGNIFICANTLY_BEHIND":
        subject = f"🔒 LOCK IN — Recovery Mission (Week {week}/{total_w})"
        state_badge = "<span style='background:rgba(239,68,68,0.2); color:#f87171; padding:4px 12px; border-radius:12px; font-weight:800; font-size:12px;'>⚡ RECOVERY PRIORITY</span>"
        personalized_msg = "You are currently behind schedule with accumulated overdue items. Do NOT try to solve everything at once. Focus 100% of your energy solely on the single priority task below to break the logjam."
    elif state == "SLIGHTLY_BEHIND":
        subject = f"🔒 LOCK IN — Today's Focus & Catch-Up (Week {week}/{total_w})"
        state_badge = "<span style='background:rgba(245,158,11,0.2); color:#fbbf24; padding:4px 12px; border-radius:12px; font-weight:800; font-size:12px;'>⏳ CATCH-UP FOCUS</span>"
        personalized_msg = "A couple of items slipped past their scheduled target. Knock out today's mission to get right back on track before the upcoming milestone."
    elif state == "MILESTONE_DUE":
        subject = f"⏰ LOCK IN — Milestone Week {week} Deliverables Due"
        state_badge = "<span style='background:rgba(168,85,247,0.2); color:#c084fc; padding:4px 12px; border-radius:12px; font-weight:800; font-size:12px;'>🎯 MILESTONE CRITICAL</span>"
        milestone_title = analysis.get("current_milestone", {}).get("title", f"Week {week} Milestone") if analysis.get("current_milestone") else f"Week {week} Milestone"
        personalized_msg = f"You are in a crucial milestone phase: '{milestone_title}'. Finalize these core deliverables to secure this week's startup objective."
    elif state == "STREAK_AT_RISK":
        subject = f"🔥 LOCK IN — Keep Your {streak}-Day Streak Alive!"
        state_badge = "<span style='background:rgba(249,115,22,0.2); color:#fb923c; padding:4px 12px; border-radius:12px; font-weight:800; font-size:12px;'>🔥 STREAK AT RISK</span>"
        personalized_msg = f"You've built great momentum with a {streak}-day execution streak. Complete at least one task today to keep your streak burning hot!"
    else: # ON_TRACK
        subject = f"🔒 LOCK IN — Today's Mission (Week {week}/{total_w})"
        state_badge = "<span style='background:rgba(16,185,129,0.2); color:#34d399; padding:4px 12px; border-radius:12px; font-weight:800; font-size:12px;'>✓ ON TRACK</span>"
        personalized_msg = f"Solid execution pace! You're in Week {week} of {total_w}. Here is your primary mission for today:"

    # Format priority tasks
    task_lines_txt = []
    task_lines_html = []
    for i, t in enumerate(priority_tasks, 1):
        t_name = t.get("title", "Task")
        t_hrs = t.get("hours", 2)
        t_cat = t.get("category", "ops").upper()
        t_desc = t.get("description", "")
        task_lines_txt.append(f"{i}. {t_name} (~{t_hrs}h, {t_cat})\n   Details: {t_desc}" if t_desc else f"{i}. {t_name} (~{t_hrs}h, {t_cat})")
        
        is_top = (i == 1)
        border_style = "border: 1px solid rgba(59,130,246,0.4); background: rgba(59,130,246,0.06);" if is_top else "border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.02);"
        top_badge = "<span style='background:#3b82f6; color:#ffffff; font-size:10px; font-weight:800; padding:2px 6px; border-radius:6px; margin-right:6px;'>TOP PRIORITY</span>" if is_top else ""
        
        task_lines_html.append(
            f"<div style='border-radius:10px; padding:12px; margin-bottom:10px; {border_style}'>"
            f"  <div style='display:flex; align-items:center; margin-bottom:4px;'>"
            f"    {top_badge}"
            f"    <strong style='color:#f8fafc; font-size:14px;'>{t_name}</strong>"
            f"    <span style='margin-left:auto; color:#94a3b8; font-size:11px; font-weight:700;'>[{t_cat} · ~{t_hrs}h]</span>"
            f"  </div>"
            f"  <div style='font-size:12px; color:#94a3b8; line-height:1.4;'>{t_desc or 'Focus on delivering concrete output today.'}</div>"
            f"</div>"
        )

    tasks_str_txt = "\n".join(task_lines_txt) if task_lines_txt else "All current week tasks completed! Keep up the momentum."
    tasks_str_html = "".join(task_lines_html) if task_lines_html else "<div style='color:#34d399; font-size:13px;'>✓ All current week tasks completed! Keep moving forward! 🎉</div>"

    remaining_week_tasks = max(0, analysis.get("current_week_tasks_count", 0) - analysis.get("current_week_completed_count", 0))
    milestone_info = analysis.get("current_milestone")
    milestone_str_txt = f"Upcoming Milestone: {milestone_info.get('title')} (Week {milestone_info.get('week')})" if milestone_info else "Milestone: Keep executing weekly targets"

    text_body = f"""{subject}

{personalized_msg}

═══════════════════════════════════════════════
🎯 TODAY'S MISSION & FOCUS
═══════════════════════════════════════════════
{tasks_str_txt}

═══════════════════════════════════════════════
🔥 MOMENTUM & EXECUTION SNAPSHOT
═══════════════════════════════════════════════
• Current Streak: {streak} Days 🔥
• LOCK IN Score: {score} / 100
• Weekly Progress: {analysis['current_week_completed_count']} / {analysis['current_week_tasks_count']} tasks ({analysis['current_week_pct']}%)
• Tasks Completed This Week: {tasks_this_week} ({trend})
• Remaining Tasks for Week {week}: {remaining_week_tasks}
• Status: {state.replace('_', ' ')}
• {milestone_str_txt}

Open your roadmap & log today's progress:
{mission_cta_url}

Stay locked in.
— Your Autonomous LOCK IN AI Accountability Agent
"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #080c16; color: #f1f5f9; padding: 20px; margin: 0; }}
        .card {{ background: #0f172a; border: 1px solid rgba(59,130,246,0.25); border-radius: 18px; padding: 30px; max-width: 600px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
        .title {{ font-size: 22px; font-weight: 900; color: #60a5fa; margin: 0 0 10px 0; letter-spacing: -0.5px; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin: 20px 0; }}
        .metric-card {{ background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 12px 16px; }}
        .metric-label {{ font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }}
        .metric-value {{ font-size: 18px; font-weight: 900; color: #f8fafc; margin-top: 2px; }}
        .cta-btn {{ display: inline-block; background: linear-gradient(135deg, #2563eb, #7c3aed); color: #ffffff !important; font-weight: 800; font-size: 14px; text-decoration: none; padding: 14px 28px; border-radius: 12px; text-align: center; box-shadow: 0 4px 14px rgba(37,99,235,0.4); }}
      </style>
    </head>
    <body>
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
          <div>{state_badge}</div>
          <div style="font-size:12px; font-weight:800; color:#38bdf8;">LOCK IN AI · Week {week}/{total_w}</div>
        </div>

        <h2 class="title">{subject}</h2>
        <p style="font-size:14px; color:#cbd5e1; line-height:1.6; margin-bottom:20px;">{personalized_msg}</p>

        <!-- Momentum Grid -->
        <table style="width:100%; border-collapse:separate; border-spacing:10px 0; margin:16px -10px 20px -10px;">
          <tr>
            <td style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:12px 16px; width:50%;">
              <div style="font-size:11px; font-weight:800; color:#94a3b8; text-transform:uppercase;">🔥 Execution Streak</div>
              <div style="font-size:20px; font-weight:900; color:#fb923c; margin-top:2px;">{streak} <span style="font-size:12px; color:#94a3b8; font-weight:600;">Days Active</span></div>
            </td>
            <td style="background:rgba(59,130,246,0.08); border:1px solid rgba(59,130,246,0.25); border-radius:12px; padding:12px 16px; width:50%;">
              <div style="font-size:11px; font-weight:800; color:#94a3b8; text-transform:uppercase;">🔒 Lock-In Score</div>
              <div style="font-size:20px; font-weight:900; color:#38bdf8; margin-top:2px;">{score} <span style="font-size:12px; color:#64748b; font-weight:600;">/ 100</span></div>
            </td>
          </tr>
        </table>

        <!-- Today's Mission -->
        <div style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); border-radius:14px; padding:18px; margin-bottom:22px;">
          <div style="font-size:12px; font-weight:800; color:#38bdf8; text-transform:uppercase; margin-bottom:12px; letter-spacing:0.5px;">
            🎯 Today's Action Deliverables
          </div>
          {tasks_str_html}
          <div style="font-size:12px; color:#64748b; margin-top:10px;">
            Remaining for Week {week}: <strong>{remaining_week_tasks} tasks</strong> · Pace: <strong>{analysis['current_week_pct']}%</strong>
          </div>
        </div>

        <!-- Call to Action -->
        <div style="text-align:center; margin:26px 0 10px 0;">
          <a href="{mission_cta_url}" class="cta-btn" target="_blank">
            Open Today's Mission →
          </a>
        </div>

        <div style="font-size:11px; color:#475569; text-align:center; margin-top:24px; border-top:1px solid rgba(255,255,255,0.05); padding-top:16px;">
          Sent autonomously by LOCK IN AI Accountability Agent · Never miss startup execution momentum
        </div>
      </div>
    </body>
    </html>
    """
    return subject, text_body, html_body


def generate_deadline_alert_content(analysis: Dict[str, Any]) -> tuple[str, str, str]:
    """Generates a deadline alert when a milestone or critical task is approaching."""
    milestone = analysis["current_milestone"] or {"title": f"Week {analysis['current_week']} Milestone", "description": "Weekly deliverables"}
    m_title = milestone.get("title", "Key Milestone")
    m_desc = milestone.get("description", "")
    week = analysis["current_week"]
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    blueprint_id = analysis.get("blueprint_id", "")
    cta_url = f"{frontend_url}/lock-in/{blueprint_id}" if blueprint_id else f"{frontend_url}/home"

    subject = f"⏰ LOCK IN — Milestone Due: {m_title}"
    text_body = f"""{subject}

Your upcoming milestone for Week {week} is approaching:

MILESTONE: {m_title}
{m_desc}

REMAINING TASKS:
{len(analysis['priority_tasks'])} priority tasks remaining for this milestone.

Focus on these critical items before beginning lower-priority work.

View your roadmap:
{cta_url}

Stay locked in!
— Your LOCK IN AI Accountability Agent
"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, sans-serif; background:#080c16; color:#f1f5f9; padding:20px;">
      <div style="background:#0f172a; border:1px solid rgba(239,68,68,0.4); border-radius:16px; padding:26px; max-width:580px; margin:0 auto;">
        <span style="background:rgba(239,68,68,0.2); color:#f87171; padding:4px 12px; border-radius:12px; font-weight:800; font-size:11px; text-transform:uppercase;">⏰ DEADLINE ALERT</span>
        <h2 style="color:#f87171; margin:14px 0 6px 0;">{m_title}</h2>
        <p style="color:#cbd5e1; font-size:14px; line-height:1.5;">{m_desc}</p>
        <p style="font-size:13px; color:#94a3b8;">Focus on finalizing the remaining Week {week} deliverables before starting new items.</p>
        <div style="margin-top:20px;">
          <a href="{cta_url}" style="background:#ef4444; color:#ffffff; font-weight:800; font-size:13px; text-decoration:none; padding:10px 20px; border-radius:10px; display:inline-block;">Open Roadmap →</a>
        </div>
      </div>
    </body>
    </html>
    """
    return subject, text_body, html_body


def generate_weekly_report_content(analysis: Dict[str, Any]) -> tuple[str, str, str]:
    """Generates the weekly progress report email."""
    week = analysis["current_week"]
    total_w = analysis["total_weeks"]
    score = analysis["lock_in_score"]
    state = analysis["agent_state"].replace("_", " ")
    streak = analysis.get("current_streak", 0)
    tasks_week = analysis.get("tasks_completed_this_week", 0)
    trend = analysis.get("progress_trend", "Steady pace")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    blueprint_id = analysis.get("blueprint_id", "")
    cta_url = f"{frontend_url}/lock-in/{blueprint_id}" if blueprint_id else f"{frontend_url}/home"

    subject = f"📊 LOCK IN — Weekly Progress Report (Week {week}/{total_w})"
    text_body = f"""{subject}

Startup: {analysis['sector']} Startup
Week: {week} of {total_w}
Overall Progress: {analysis['completed_count']} / {analysis['total_tasks']} tasks ({analysis['overall_pct']}%)
Week {week} Completion: {analysis['current_week_pct']}%
Tasks Completed This Week: {tasks_week} ({trend})
Execution Streak: {streak} Days 🔥
Status: {state}
LOCK IN SCORE: {score} / 100

Next week's key priority:
Continue executing milestones towards your primary goal of {analysis['primary_goal']}.

View full report on your roadmap:
{cta_url}

Stay locked in!
— Your LOCK IN AI Accountability Agent
"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, sans-serif; background:#080c16; color:#f1f5f9; padding:20px;">
      <div style="background:#0f172a; border:1px solid rgba(99,102,241,0.4); border-radius:18px; padding:28px; max-width:580px; margin:0 auto;">
        <span style="background:rgba(99,102,241,0.2); color:#a5b4fc; padding:4px 12px; border-radius:12px; font-weight:800; font-size:11px;">📊 WEEKLY AI REPORT</span>
        <h2 style="color:#a5b4fc; margin:12px 0 4px 0;">Week {week} of {total_w} Executive Summary</h2>
        <div style="background:rgba(255,255,255,0.03); border-radius:12px; padding:16px; margin:16px 0; font-size:14px; line-height:1.6;">
          <div>✓ Completed Tasks: <strong>{analysis['completed_count']} / {analysis['total_tasks']}</strong> ({analysis['overall_pct']}%)</div>
          <div>✓ Week {week} Pace: <strong>{analysis['current_week_pct']}%</strong></div>
          <div>✓ Tasks Done This Week: <strong>{tasks_week}</strong> ({trend})</div>
          <div>✓ Execution Streak: <strong>{streak} Days 🔥</strong></div>
          <div>✓ Status: <strong>{state}</strong></div>
          <div style="margin-top:10px; font-size:20px; color:#38bdf8; font-weight:900;">LOCK IN SCORE: {score} / 100</div>
        </div>
        <div style="margin-top:20px; text-align:center;">
          <a href="{cta_url}" style="background:#6366f1; color:#ffffff; font-weight:800; font-size:13px; text-decoration:none; padding:12px 24px; border-radius:10px; display:inline-block;">View Roadmap Report →</a>
        </div>
      </div>
    </body>
    </html>
    """
    return subject, text_body, html_body


# ══════════════════════════════════════════════════════════════════════════════
# HUMAN-IN-THE-LOOP (HITL) RECOVERY RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

def generate_recovery_recommendation_if_needed(analysis: Dict[str, Any], groq_client=None) -> Optional[int]:
    """
    If project is SIGNIFICANTLY_BEHIND and recovery is enabled, creates a HITL recommendation.
    Does NOT modify the roadmap automatically — waits for user approval.
    """
    project_id = analysis["project_id"]
    user_id = analysis["user_id"]
    overdue = analysis["overdue_tasks"]
    current_week = analysis["current_week"]
    total_weeks = analysis["total_weeks"]

    if analysis["agent_state"] != "SIGNIFICANTLY_BEHIND" or not overdue:
        return None

    # Check if there is already an active pending recommendation
    pending = get_pending_recommendations(project_id, user_id)
    if pending:
        log.info(f"Project {project_id} already has a pending recommendation. Skipping creation.")
        return None

    # Identify low/medium priority overdue tasks to recommend moving
    tasks_to_move = [t for t in overdue if t.get("priority") in ("nice", "should")][:2]
    if not tasks_to_move:
        tasks_to_move = overdue[:2]

    target_week = min(total_weeks, current_week + 1)
    moved_task_info = [
        {"task_id": t["task_id"], "title": t["title"], "from_week": t["week_number"], "to_week": target_week}
        for t in tasks_to_move
    ]

    title = f"Move {len(tasks_to_move)} lower-priority task(s) to Week {target_week}"
    description = (
        f"You are currently behind on {len(overdue)} task(s). To regain momentum without burnout, "
        f"we recommend rescheduling {len(tasks_to_move)} lower-priority item(s) to Week {target_week} "
        f"so you can focus 100% on critical path deliverables today."
    )

    details = {
        "current_plan": f"{len(overdue)} overdue tasks accumulating across past weeks.",
        "proposed_change": f"Shift {', '.join([t['title'] for t in tasks_to_move])} to Week {target_week}.",
        "reason": "Prevents cognitive overload and focuses available hours on core MVP validation.",
        "impact": f"Clears immediate bottleneck; estimated 2 focused sessions to reach ON_TRACK status.",
        "moved_tasks": moved_task_info,
    }

    action_id = create_agent_action(
        project_id=project_id,
        user_id=user_id,
        action_type="RECOVERY_RECOMMENDATION_CREATED",
        title=title,
        description=description,
        details=details,
        requires_approval=True
    )
    log.info(f"Created HITL Recommendation #{action_id} for project {project_id}")
    return action_id


# ══════════════════════════════════════════════════════════════════════════════
# MAIN AGENT EXECUTION ENTRYPOINT & CONCURRENCY CONTROL
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
from lock_in_business_partner import (
    get_or_create_context,
    generate_daily_partner_briefing,
    evaluate_safety_and_approval,
)

_project_locks: Dict[int, asyncio.Lock] = {}


def get_project_lock(project_id: int) -> asyncio.Lock:
    """Returns or creates a per-project asyncio lock to prevent concurrent scheduled/manual runs."""
    if project_id not in _project_locks:
        _project_locks[project_id] = asyncio.Lock()
    return _project_locks[project_id]


async def evaluate_and_execute_agent(
    project_id: int,
    notification_type: str = "daily",
    force_send: bool = False,
    groq_client=None
) -> Dict[str, Any]:
    """
    Thread-safe, idempotent entrypoint for the LOCK IN Business Partner Agent.
    Acquires a concurrency lock to guarantee non-overlapping execution.
    """
    lock = get_project_lock(project_id)
    if lock.locked():
        log.warning(f"Project {project_id} execution lock already active. Skipping overlapping run.")
        return {
            "project_id": project_id,
            "notification_type": notification_type,
            "sent": False,
            "reason": "Another agent evaluation cycle is currently in progress for this project.",
        }

    async with lock:
        return await _execute_agent_cycle(
            project_id=project_id,
            notification_type=notification_type,
            force_send=force_send,
            groq_client=groq_client,
        )


async def _execute_agent_cycle(
    project_id: int,
    notification_type: str = "daily",
    force_send: bool = False,
    groq_client=None
) -> Dict[str, Any]:
    """Internal implementation of the business partner evaluation cycle."""
    analysis = analyze_project_progress(project_id)
    user_id = analysis["user_id"]
    user_email = analysis["user_email"]
    prefs = get_preferences(project_id, user_id)
    gmail_conn = get_gmail_connection(user_id)
    user_tz_str = analysis.get("timezone", "Asia/Kolkata")

    try:
        user_tz = zoneinfo.ZoneInfo(user_tz_str)
    except Exception:
        user_tz = zoneinfo.ZoneInfo("UTC")

    local_now = datetime.now(user_tz)
    local_date_str = local_now.date().isoformat()

    result = {
        "project_id": project_id,
        "notification_type": notification_type,
        "analysis": analysis,
        "sent": False,
        "reason": "",
    }

    # 1. Check emergency pause
    if prefs.get("is_paused", False):
        log.info(f"Project {project_id} has agent paused in preferences. Skipping.")
        result["reason"] = "Agent paused by emergency stop preference."
        return result

    # 2. Check Gmail connection
    if not gmail_conn or gmail_conn.get("status") != "active":
        result["reason"] = "Gmail not connected or reauthorization required."
        return result

    recipient = gmail_conn.get("google_email") or user_email
    if not recipient:
        result["reason"] = "No authenticated recipient email found"
        return result

    # 3. Check Idempotency (unless forced)
    if not force_send and has_notification_been_sent_today(project_id, notification_type, local_date_str, user_tz_str):
        log.info(f"Notification '{notification_type}' already sent today for project {project_id}. Skipping.")
        result["reason"] = "Already sent today"
        return result

    # 4. Check user preferences for channel enablement
    if notification_type == "daily" and not prefs.get("daily_reminder_enabled", True) and not force_send:
        result["reason"] = "Daily reminder disabled in preferences"
        return result
    elif notification_type == "deadline" and not prefs.get("deadline_alert_enabled", True) and not force_send:
        result["reason"] = "Deadline alerts disabled in preferences"
        return result
    elif notification_type == "weekly" and not prefs.get("weekly_report_enabled", True) and not force_send:
        result["reason"] = "Weekly report disabled in preferences"
        return result

    # 5. Load persistent partner context and generate content
    context = get_or_create_context(project_id, user_id)

    if notification_type == "daily":
        subject, text_body, html_body = generate_daily_email_content(analysis, groq_client)
        action_type = "DAILY_MISSION_SENT"
    elif notification_type == "deadline":
        subject, text_body, html_body = generate_deadline_alert_content(analysis)
        action_type = "MILESTONE_ALERT_SENT"
    elif notification_type == "weekly":
        subject, text_body, html_body = generate_weekly_report_content(analysis)
        action_type = "WEEKLY_REPORT_SENT"
    else:
        subject, text_body, html_body = generate_daily_email_content(analysis, groq_client)
        action_type = "DAILY_MISSION_SENT"

    # 6. Safety & Approval Gate Check
    can_auto_send, safety_reason = evaluate_safety_and_approval(
        project_id=project_id,
        user_id=user_id,
        recipient=recipient,
        subject=subject,
        body_text=text_body,
        workflow_type=notification_type,
    )

    should_dispatch_directly = force_send or can_auto_send

    # If approval is required (default mode or policy restriction): create draft in Email Workspace
    if not should_dispatch_directly:
        from lock_in_db import create_email_draft
        draft_id = create_email_draft(
            project_id=project_id,
            user_id=user_id,
            workflow_type=notification_type,
            recipient=recipient,
            subject=subject,
            body_text=text_body,
            body_html=html_body,
            context_data={"analysis_summary": f"Score: {analysis['lock_in_score']}, State: {analysis['agent_state']}"},
            status="pending_approval",
            requires_approval=True
        )

        create_agent_action(
            project_id=project_id,
            user_id=user_id,
            action_type="EMAIL_DRAFT_PENDING_APPROVAL",
            title=f"Prepared Draft ({notification_type.capitalize()}): {subject}",
            description=f"Draft queued in Email Workspace. Policy: {safety_reason}",
            details={"draft_id": draft_id, "recipient": recipient, "subject": subject},
            requires_approval=True
        )

        result["sent"] = False
        result["draft_created"] = True
        result["draft_id"] = draft_id
        result["reason"] = f"Draft created in Email Workspace for approval: {safety_reason}"
        return result

    # 7. Direct dispatch with bounded retries for transient errors
    max_retries = 2
    retry_delay = 1.0
    last_exc = None

    for attempt in range(max_retries + 1):
        try:
            msg_id = await send_gmail_email(user_id, recipient, subject, text_body, html_body)
            
            # Record notification in idempotency ledger
            record_notification(
                project_id=project_id,
                user_id=user_id,
                notification_type=notification_type,
                subject=subject,
                status="sent",
                provider_message_id=msg_id,
                local_date=local_date_str,
            )

            # Log activity entry with standardized action types
            create_agent_action(
                project_id=project_id,
                user_id=user_id,
                action_type=action_type,
                title=f"Sent {notification_type.capitalize()} Email: {subject}",
                description=f"Delivered to {recipient} (Score: {analysis['lock_in_score']}/100, Streak: {analysis.get('current_streak', 0)}d, Status: {analysis['agent_state']})",
                details={
                    "message_id": msg_id,
                    "score": analysis["lock_in_score"],
                    "streak": analysis.get("current_streak", 0),
                    "state": analysis["agent_state"],
                    "local_date": local_date_str,
                },
                requires_approval=False
            )

            result["sent"] = True
            result["message_id"] = msg_id
            break

        except Exception as e:
            last_exc = e
            err_str = str(e)
            log.warning(f"[AGENT RUNNER] Send attempt {attempt + 1} failed for project {project_id}: {err_str}")

            # Do NOT retry permanent authorization or scope errors
            if "401" in err_str or "403" in err_str or "reauth" in err_str.lower():
                break

            if attempt < max_retries:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

    if not result["sent"]:
        log.error(f"Failed to send {notification_type} email for project {project_id} after retries: {last_exc}")
        record_notification(
            project_id=project_id,
            user_id=user_id,
            notification_type=notification_type,
            subject=subject,
            status="failed",
            local_date=local_date_str,
            error=str(last_exc)
        )
        result["sent"] = False
        result["error"] = str(last_exc)

    # 8. Check if HITL recovery recommendation is warranted
    if prefs.get("recovery_enabled", True):
        rec_id = generate_recovery_recommendation_if_needed(analysis, groq_client)
        if rec_id:
            result["recommendation_created"] = rec_id

    return result
