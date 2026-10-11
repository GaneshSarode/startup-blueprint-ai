"""
routes/blueprint.py — Blueprint generation endpoints.

POST /api/blueprint/generate         → SSE stream of CRAG + generation progress
GET  /api/blueprint/{blueprint_id}   → fetch a single saved blueprint
GET  /api/blueprint/news             → live startup news (public)
"""

from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from auth_middleware import get_current_user
from config import get_settings
from dependencies import (
    get_collections,
    get_gemini,
    get_granite,
    get_groq,
    get_gpt_oss,
    get_reranker,
    get_tavily,
)
from models.blueprint import BlueprintRequest, BlueprintResponse, SSEEvent, RetrySectionRequest
from core.crag import _repair_section, _normalize_blueprint

log      = logging.getLogger(__name__)
router   = APIRouter(prefix="/api/blueprint", tags=["blueprint"])
settings = get_settings()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _sse(
    event: str,
    step: str = "",
    node: str = "",
    stage: str = "",
    section: str = "",
    progress: int = 0,
    data=None,
    error: str = "",
    generation_id: str = "",
) -> str:
    """Format a single SSE frame."""
    payload = SSEEvent(
        event=event,
        step=step,
        node=node or stage or section,
        stage=stage,
        section=section,
        progress=progress,
        data=data,
        error=error,
        generation_id=generation_id,
    ).model_dump(mode="json")
    return f"data: {json.dumps(payload)}\n\n"


def _format_event_payload(payload: dict) -> str:
    """Format a raw event dictionary from CRAG callback into an SSE frame."""
    event_name = payload.get("event", "progress")
    return f"data: {json.dumps(payload)}\n\n"


async def _stream_blueprint(
    request: Request,
    body: BlueprintRequest,
    user: Dict,
    collections: Dict,
    reranker,
    granite,
    tavily,
    groq_client,
    gemini,
    gpt_oss,
) -> AsyncGenerator[str, None]:
    """
    Async generator that runs the CRAG pipeline and yields SSE frames in genuine real-time.
    Uses an asyncio.Queue to stream incremental stage and section events from the worker thread.
    """
    import sys, os, uuid, time, threading, asyncio
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

    generation_id = f"gen_{uuid.uuid4().hex[:12]}"
    t_init = time.time()
    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue = asyncio.Queue()
    cancel_event = threading.Event()

    log.info(f"[CRAG Stream] Starting generation_id={generation_id} for user={user.get('email')}")

    try:
        # Initial event notifying client of generation start
        yield _sse(
            event="generation_started",
            generation_id=generation_id,
            step="Initializing blueprint generation pipeline…",
            progress=2,
            data={"generation_id": generation_id, "idea": body.idea},
        )

        from crag import run_crag

        def _event_cb(ev_type: str, payload: dict):
            payload["generation_id"] = generation_id
            if "event" not in payload:
                payload["event"] = ev_type
            loop.call_soon_threadsafe(event_queue.put_nowait, payload)

        def _run():
            return run_crag(
                query=body.idea,
                sector=body.sector,
                stage=body.stage,
                model_type=body.model_type,
                target_city=body.target_city,
                collections=collections,
                reranker=reranker,
                granite=granite,
                tavily=tavily,
                groq_client=groq_client,
                gemini_client=gemini,
                gpt_oss_client=gpt_oss,
                event_callback=_event_cb,
                cancel_event=cancel_event,
                generation_id=generation_id,
            )

        fut = loop.run_in_executor(None, _run)

        # Stream events from queue as they arrive
        while not fut.done() or not event_queue.empty():
            if await request.is_disconnected():
                log.info(f"[CRAG Stream] Client disconnected for generation_id={generation_id}. Signalling cancellation.")
                cancel_event.set()
                return

            try:
                ev_payload = await asyncio.wait_for(event_queue.get(), timeout=8.0)
                yield _format_event_payload(ev_payload)
            except asyncio.TimeoutError:
                # Reverse-proxy keepalive comment to prevent Railway/Vercel timeout
                yield ": keepalive\n\n"

        # Obtain final result
        crag_result = await fut
        if cancel_event.is_set():
            return

        confidence = crag_result.get("confidence", "")
        blueprint_data = {}
        if crag_result.get("should_generate_blueprint"):
            bp = crag_result.get("blueprint", {})
            blueprint_data = {
                "bmc":         bp.get("bmc", {}),
                "budget":      bp.get("budget", {}),
                "gtm":         bp.get("gtm", {}),
                "investors":   bp.get("investors", {}),
                "funding":     bp.get("investors", {}),
                "competitors": bp.get("competitors", {}),
                "risks":       bp.get("risks", {}),
                "crag_trace":  bp.get("crag_trace", {}),
            }

        # ── Database persistence ──────────────────────────────────────────────
        yield _sse(
            event="stage_started",
            stage="save",
            node="save",
            step="Saving blueprint to history…",
            progress=97,
            generation_id=generation_id,
        )

        bp = crag_result.get("blueprint", {})
        failed_sections = bp.get("failed_sections", [])
        bp_status = bp.get("status", "partial" if failed_sections else "success")

        t0_db = time.time()
        blueprint_id = None
        try:
            from history import save_blueprint_to_history
            blueprint_id = save_blueprint_to_history(
                idea=body.idea, sector=body.sector, stage=body.stage,
                business_model=body.model_type, market=body.target_city,
                user_email=user["email"], crag_result=crag_result,
                bmc_data=blueprint_data.get("bmc", {}),
                budget_data=blueprint_data.get("budget", {}),
                gtm_data=blueprint_data.get("gtm", {}),
                investor_data=blueprint_data.get("investors", {}),
                competitor_data=blueprint_data.get("competitors", {}),
                risk_data=blueprint_data.get("risks", {}),
                crag_trace_data=blueprint_data.get("crag_trace", {}),
                explore_results=crag_result.get("explore_results", []),
                failed_sections=failed_sections,
                status=bp_status,
            )
        except Exception as e:
            log.warning(f"Failed to save blueprint to history: {e}")

        t_db = time.time() - t0_db
        timings = crag_result.get("timings", {})
        timings["request_init_s"] = round(time.time() - t_init, 2)
        timings["database_persistence_s"] = round(t_db, 2)

        # ── Final complete event ──────────────────────────────────────────────
        now_ts = datetime.utcnow().isoformat()
        response = BlueprintResponse(
            blueprint_id=blueprint_id,
            id=blueprint_id,
            generation_id=generation_id,
            idea=body.idea,
            original_query=body.idea,
            sector=body.sector,
            model_type=body.model_type,
            business_model=body.model_type,
            stage=body.stage,
            target_city=body.target_city,
            market=body.target_city,
            status=bp_status,
            failed_sections=failed_sections,
            crag_result=crag_result,
            confidence=crag_result.get("confidence", ""),
            summary=crag_result.get("summary", ""),
            sources=crag_result.get("sources", []),
            keywords=crag_result.get("keywords", []),
            raw_logits=crag_result.get("raw_logits", []),
            timings=timings,
            blueprint=blueprint_data,
            bmc_data=blueprint_data.get("bmc", {}),
            budget_data=blueprint_data.get("budget", {}),
            gtm_data=blueprint_data.get("gtm", {}),
            investor_data=blueprint_data.get("investors", {}),
            funding_data=blueprint_data.get("funding", {}),
            competitor_data=blueprint_data.get("competitors", {}),
            risk_data=blueprint_data.get("risks", {}),
            generated_at=now_ts,
            timestamp=now_ts,
        )

        yield _sse(
            event="generation_completed",
            step="Blueprint ready!",
            progress=100,
            data=response.model_dump(mode="json"),
            generation_id=generation_id,
        )

    except Exception as e:
        log.error(f"Blueprint generation failed: {e}", exc_info=True)
        yield _sse(
            event="generation_failed",
            error=str(e),
            progress=0,
            generation_id=generation_id,
        )


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/generate")
async def generate_blueprint(
    request: Request,
    body: BlueprintRequest,
    current_user: Dict = Depends(get_current_user),
    collections  = Depends(get_collections),
    reranker     = Depends(get_reranker),
    granite      = Depends(get_granite),
    tavily       = Depends(get_tavily),
    groq_client  = Depends(get_groq),
    gemini       = Depends(get_gemini),
    gpt_oss      = Depends(get_gpt_oss),
):
    """
    Stream blueprint generation progress as Server-Sent Events.

    Frontend connects with:
        const ctrl = generateBlueprint(payload, { onProgress, onSection, onStage, onComplete, onError })

    Each SSE frame is a JSON object matching the SSEEvent schema:
        { event, step, node, stage, section, progress, data, error, generation_id }
    """
    return StreamingResponse(
        _stream_blueprint(
            request=request,
            body=body,
            user=current_user,
            collections=collections,
            reranker=reranker,
            granite=granite,
            tavily=tavily,
            groq_client=groq_client,
            gemini=gemini,
            gpt_oss=gpt_oss,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control":      "no-cache",
            "X-Accel-Buffering":  "no",    # disable Nginx buffering (Railway)
            "Connection":         "keep-alive",
        },
    )


@router.get("/{blueprint_id}", response_model=BlueprintResponse)
async def get_blueprint(
    blueprint_id: int,
    current_user: Dict = Depends(get_current_user),
):
    """Fetch a saved blueprint by ID (user must own it)."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

    try:
        from history import load_blueprint_for_display
        bp = load_blueprint_for_display(blueprint_id)
        if not bp or (bp.get("user_email") and bp.get("user_email").lower() != current_user["email"].lower()):
            raise HTTPException(status_code=404, detail="Blueprint not found")
        return bp
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/feed")
async def get_news(q: str = "India startup funding"):
    """Live startup news — public endpoint (no auth required)."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

    try:
        from news_feed import get_startup_news
        articles = get_startup_news(settings.NEWS_API_KEY, query=q, page_size=9)
        return {"articles": articles}
    except Exception as e:
        log.warning(f"News fetch failed: {e}")
        return {"articles": []}


@router.post("/retry-section")
@router.post("/{blueprint_id}/retry-section")
async def retry_section(
    body: RetrySectionRequest,
    blueprint_id: Optional[int] = None,
    current_user: Dict = Depends(get_current_user),
    groq_client  = Depends(get_groq),
    gpt_oss      = Depends(get_gpt_oss),
):
    """
    Regenerate ONLY the requested blueprint section without rerunning the entire pipeline.
    Preserves all other successfully generated sections.
    """
    sec_name = body.section.lower().strip()
    # Map common aliases
    if sec_name in ("funding", "investor", "investors"):
        sec_name = "investors"
    elif sec_name in ("competitor", "competitors"):
        sec_name = "competitors"
    elif sec_name in ("risk", "risks"):
        sec_name = "risks"

    b_id = blueprint_id or body.blueprint_id
    idea_text = body.idea or ""
    evidence_text = f"Sector: {body.sector}. Model: {body.model_type}. Target City: {body.target_city}."
    sources_text = "Official Indian Policy Documents & Regulations"

    if b_id:
        try:
            from history import load_blueprint_for_display, history_db
            existing_bp = load_blueprint_for_display(b_id)
            if existing_bp:
                idea_text = existing_bp.get("original_query") or existing_bp.get("idea") or idea_text
                crag_res = existing_bp.get("crag_result") or {}
                evidence_text = crag_res.get("summary") or crag_res.get("internal_context") or evidence_text
                sources_text = ", ".join(existing_bp.get("sources") or []) or sources_text
        except Exception as e:
            log.warning(f"Could not load existing blueprint {b_id} for section retry: {e}")

    if not idea_text:
        raise HTTPException(status_code=400, detail="Idea is required for section regeneration.")

    try:
        new_sec_data = _repair_section(sec_name, idea_text, evidence_text, sources_text, groq_client, gpt_oss)
        partial_bp = {sec_name: new_sec_data}
        norm_bp = _normalize_blueprint(partial_bp)
        canonical_sec = norm_bp.get(sec_name, new_sec_data)

        if b_id:
            try:
                from history import history_db
                bp_record = history_db.get_blueprint(b_id)
                if bp_record and bp_record.get("sections"):
                    secs = dict(bp_record["sections"])
                    secs[sec_name] = canonical_sec
                    if sec_name == "investors":
                        secs["funding"] = canonical_sec
                    failed_list = [f for f in secs.get("failed_sections", []) if f != sec_name]
                    secs["failed_sections"] = failed_list
                    secs["status"] = "partial" if failed_list else "success"
                    history_db.update_blueprint(b_id, sections=secs)
            except Exception as upd_err:
                log.warning(f"Could not persist retried section {sec_name} to db: {upd_err}")

        return {
            "success": True,
            "status": "success",
            "section": sec_name,
            "data": canonical_sec,
            "blueprint_id": b_id,
        }
    except Exception as err:
        log.error(f"Failed to retry section {sec_name}: {err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Section regeneration failed: {err}")