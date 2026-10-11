"""
routes/deep_research.py — Endpoints for Autonomous Startup Deep Research.

Endpoints:
POST /api/deep-research/stream                → POST SSE stream executing multi-module research (Supports Bearer token)
GET  /api/deep-research/stream/{blueprint_id} → GET SSE stream fallback
POST /api/deep-research/start                 → Trigger deep research run (Sync or SSE)
GET  /api/deep-research/{blueprint_id}/results → Fetch cached intelligence report
"""

from __future__ import annotations
import logging
import os
import sys
import json
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth_middleware import get_current_user, get_current_user_optional
from dependencies import get_tavily, get_groq, get_collections

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/deep-research", tags=["deep-research"])


@router.post("/stream")
async def stream_deep_research_post(
    body: dict,
    current_user: Dict = Depends(get_current_user),
    groq_client = Depends(get_groq),
    tavily = Depends(get_tavily),
    collections = Depends(get_collections),
):
    """
    POST SSE Endpoint streaming multi-module research progress and returning
    the synthesized Groq Startup Intelligence Report.
    Uses Bearer authorization header for security.
    """
    blueprint_id = body.get("blueprint_id")
    raw_focus = body.get("research_focus") or body.get("focus", "FULL_STARTUP_ANALYSIS")
    force_refresh = body.get("force_refresh", False)

    if not blueprint_id:
        raise HTTPException(400, "blueprint_id is required")

    from history import load_blueprint_for_display
    from deep_research import run_deep_research_stream, get_cached_report, normalize_focus

    norm_focus = normalize_focus(raw_focus)

    bp = load_blueprint_for_display(blueprint_id)
    if not bp:
        raise HTTPException(404, "Blueprint not found")
    if current_user and current_user.get("email"):
        bp["user_email"] = current_user.get("email")

    cached = get_cached_report(blueprint_id, norm_focus)
    if cached and not force_refresh:
        async def stream_cached():
            data_prog = {"event": "progress", "module": f"Loading Cached {norm_focus} Report", "pct": 100, "status": "completed"}
            yield f"data: {json.dumps(data_prog)}\n\n"
            data_comp = {"event": "complete", "pct": 100, "status": "completed", "data": cached}
            yield f"data: {json.dumps(data_comp)}\n\n"
        return StreamingResponse(
            stream_cached(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
        )

    return StreamingResponse(
        run_deep_research_stream(bp, groq_client, tavily, collections, norm_focus),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
    )


@router.get("/stream/{blueprint_id}")
async def stream_deep_research_get(
    blueprint_id: int,
    focus: str = Query("FULL_STARTUP_ANALYSIS"),
    force_refresh: bool = Query(False),
    current_user: Dict = Depends(get_current_user_optional),
    groq_client = Depends(get_groq),
    tavily = Depends(get_tavily),
    collections = Depends(get_collections),
):
    """
    GET SSE Endpoint for deep research streaming.
    """
    from history import load_blueprint_for_display
    from deep_research import run_deep_research_stream, get_cached_report, normalize_focus

    norm_focus = normalize_focus(focus)

    bp = load_blueprint_for_display(blueprint_id)
    if not bp:
        raise HTTPException(404, "Blueprint not found")

    cached = get_cached_report(blueprint_id, norm_focus)
    if cached and not force_refresh:
        async def stream_cached():
            data_prog = {"event": "progress", "module": f"Loading Cached {norm_focus} Report", "pct": 100, "status": "completed"}
            yield f"data: {json.dumps(data_prog)}\n\n"
            data_comp = {"event": "complete", "pct": 100, "status": "completed", "data": cached}
            yield f"data: {json.dumps(data_comp)}\n\n"
        return StreamingResponse(
            stream_cached(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
        )

    return StreamingResponse(
        run_deep_research_stream(bp, groq_client, tavily, collections, norm_focus),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
    )


@router.post("/start")
@router.post("/run")
async def run_deep_research_endpoint(
    body: dict,
    current_user: Dict = Depends(get_current_user),
    groq_client = Depends(get_groq),
    tavily = Depends(get_tavily),
    collections = Depends(get_collections),
):
    """
    POST endpoint — triggers SSE stream response.
    """
    return await stream_deep_research_post(body, current_user, groq_client, tavily, collections)


@router.get("/{blueprint_id}/results")
async def get_research_results(
    blueprint_id: int,
    focus: str = Query("FULL_STARTUP_ANALYSIS"),
    current_user: Dict = Depends(get_current_user_optional),
):
    """Fetch cached deep research results for a blueprint."""
    from deep_research import get_cached_report, normalize_focus
    norm_focus = normalize_focus(focus)
    cached = get_cached_report(blueprint_id, norm_focus)
    if not cached:
        raise HTTPException(404, f"Deep research report ({norm_focus}) not found for this blueprint")
    return cached
