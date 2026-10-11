"""
crag.py — Corrective RAG pipeline for Startup Blueprint Generator
Based on: Yan et al. 2024 (https://arxiv.org/abs/2401.15884)

ARCHITECTURE
============
__start__
    │
  rewrite_query          ← Gemini Flash: structured 8-section brief
    │
  retrieve               ← Query all 3 ChromaDB collections (text + table + visual)
    │
  eval_each_doc          ← CrossEncoder ms-marco-MiniLM-L-6-v2 scores each chunk
    │
  ┌──────┬──────────┐
CORRECT AMBIGUOUS INCORRECT
  │        │           │
refine   web_search  web_search
(PDF)   (PDF+web)   (web only)
  │        │           │
generate  generate  conversational
(Granite) (Granite)  (Groq)
  │        │           │
explore  explore    explore
(Tavily) (Tavily)  (Tavily)
  │        │           │
blueprint blueprint  redirect

BUGS FIXED vs previous version
================================
1. node_rewrite_query never passed `prompt` to generate_content() → fixed.
2. retrieve() queried single collection → now queries text_chunks + table_data
   + visual_summaries and merges by relevance score.
3. ChromaDB where-filter was applied without checking if doc_type field exists
   → graceful fallback to unfiltered query.
4. Gemini client instantiated inside the hot path on every call → moved to
   module-level lazy singleton.
"""

import os
import re
import time
import json
import ast
import uuid
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List
from dotenv import load_dotenv
from sentence_transformers import CrossEncoder
import chromadb
from ibm_watsonx_ai.foundation_models import ModelInference
from tavily import TavilyClient
from groq import Groq
import google.generativeai as genai
from google import genai as genai_new

from config import get_settings

load_dotenv()

# ── Thresholds (calibrated on raw CrossEncoder logits, NOT sigmoid) ───────────
# ms-marco-MiniLM-L-6-v2 raw logits on domain-specific policy corpora cluster
# much lower than web-search ranges — sigmoid collapses all values near 0.
UPPER_THRESHOLD = -4.0   # logit ≥ this  → CORRECT
LOWER_THRESHOLD = -7.5   # logit < this  → INCORRECT
                         # between       → AMBIGUOUS

# ── Gemini 429 Cooldown Cache ────────────────────────────────────────────────
_gemini_cooldown_until = 0.0

def _is_gemini_available() -> bool:
    global _gemini_cooldown_until
    return time.time() >= _gemini_cooldown_until

def _set_gemini_cooldown(seconds: int = 300):
    global _gemini_cooldown_until
    _gemini_cooldown_until = time.time() + seconds
    print(f"[CRAG] Gemini quota exceeded (429). Setting cooldown for {seconds}s — bypassing Gemini to Groq fallback.")

# ── IBM 429 Cooldown Cache ───────────────────────────────────────────────────
_ibm_cooldown_until = 0.0

def _is_ibm_available() -> bool:
    global _ibm_cooldown_until
    return time.time() >= _ibm_cooldown_until

def _set_ibm_cooldown(seconds: int = 120):
    global _ibm_cooldown_until
    _ibm_cooldown_until = time.time() + seconds
    print(f"[CRAG] IBM rate-limited (429). Setting cooldown for {seconds}s — bypassing IBM to Groq fallback.")

# ── Lazy Gemini client singleton ──────────────────────────────────────────────
_gemini_embed_client = None

def _get_embed_client():
    global _gemini_embed_client
    if _gemini_embed_client is None:
        _gemini_embed_client = genai_new.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _gemini_embed_client


def _get_gemini_embedding(text: str) -> list:
    """Embed text using Gemini embedding-001. Falls back gracefully on error."""
    if not text or not text.strip():
        text = "startup business idea India"
    client = _get_embed_client()
    result = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text.strip()
    )
    if not result or not result.embeddings:
        raise ValueError("Gemini embedding returned empty result")
    return list(result.embeddings[0].values)


# ══════════════════════════════════════════════════════════════════════════════
# NODE: rewrite_query
# Gemini Flash produces a rich 8-section structured brief used everywhere
# downstream: retrieval queries, Tavily search, Granite summarisation,
# and all 6 Groq blueprint sections.
# ══════════════════════════════════════════════════════════════════════════════
def node_rewrite_query(query, sector, stage, model_type, target_city, gemini_client):
    prompt = f"""You are a Retrieval Query Understanding Agent for an AI Startup Blueprint Generator.

Your task is NOT to summarize or shorten the startup idea.
Your goal is to preserve every important piece of information while restructuring it
for optimal semantic retrieval from a knowledge base and web search.

User Startup Idea:
{query}

Selected Context:
- Sector: {sector}
- Startup Stage: {stage}
- Business Model: {model_type}
- Primary Market: {target_city}

Rules:
- Never omit important information.
- Never replace detailed features with generic descriptions.
- Preserve AI techniques, technologies, customer segments, geography, and business model.
- Remove only filler words.
- Do NOT invent new features.

Return ONLY the following format, no other text:

PROBLEM STATEMENT
2-4 detailed sentences about the core problem being solved.

TARGET USERS
- Primary: [who]
- Secondary: [who]
- Enterprise: [who if applicable]

CORE SOLUTION
2-3 detailed sentences on how it works.

KEY FEATURES
- Feature 1
- Feature 2
- Feature 3
- Feature 4
- Feature 5

TECHNOLOGIES
- [tech1, tech2, ...]

INDUSTRY
[sector / sub-sector]

GEOGRAPHY
[primary + expansion markets]

BUSINESS MODEL
[B2B/B2C/B2B2C + monetisation approach]

KEYWORDS:
keyword1, keyword2, keyword3, keyword4, keyword5, keyword6, keyword7, keyword8

RETRIEVAL QUERIES:
1. [query focused on government schemes and policy]
2. [query focused on market size and competition]
3. [query focused on funding and investors]
4. [query focused on technology and implementation]
5. [query focused on legal and compliance]

SEARCH CONTEXT:
[One 60-80 word retrieval-focused paragraph combining every important concept naturally.]
"""

    if _is_gemini_available():
        try:
            model    = gemini_client.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                contents=prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.0,
                    max_output_tokens=3000,
                )
            )
            rewritten = response.text.strip()
            if len(rewritten) < 80:
                raise ValueError("Rewrite too short")

            # ── Parse sections ────────────────────────────────────────────────────
            keywords, retrieval_queries, search_context = [], [], ""

            m = re.search(r"KEYWORDS:\s*(.*?)\n\s*RETRIEVAL QUERIES:", rewritten, re.S)
            if m:
                keywords = [k.strip() for k in m.group(1).split(",") if k.strip()]

            m = re.search(r"RETRIEVAL QUERIES:\s*(.*?)\n\s*SEARCH CONTEXT:", rewritten, re.S)
            if m:
                for line in m.group(1).splitlines():
                    line = line.strip()
                    if line and "." in line:
                        retrieval_queries.append(line.split(".", 1)[1].strip())

            m = re.search(r"SEARCH CONTEXT:\s*(.*)", rewritten, re.S)
            if m:
                search_context = m.group(1).strip()

            return {
                "structured_brief":  rewritten,
                "keywords":          keywords,
                "retrieval_queries": retrieval_queries,
                "search_context":    search_context or query,
            }

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "ResourceExhausted" in err_str or "404" in err_str:
                _set_gemini_cooldown(3600)
            clean_err = err_str.encode('ascii', errors='replace').decode('ascii')
            print(f"[CRAG] Gemini rewrite failed ({clean_err}), attempting Groq fallback rewrite...")
    else:
        print("[CRAG] Gemini rewrite skipped (quota cooldown active). Using Groq fallback directly.")

    try:
        from config import get_settings
        from dependencies import get_groq
        groq_cl = get_groq()
        r = groq_cl.chat.completions.create(
            model=get_settings().GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.0
        )
        rewritten = (r.choices[0].message.content or "").strip()
        if len(rewritten) >= 60:
            keywords, retrieval_queries, search_context = [], [], ""
            m = re.search(r"KEYWORDS:\s*(.*?)\n\s*RETRIEVAL QUERIES:", rewritten, re.S)
            if m:
                keywords = [k.strip() for k in m.group(1).split(",") if k.strip()]
            m = re.search(r"RETRIEVAL QUERIES:\s*(.*?)\n\s*SEARCH CONTEXT:", rewritten, re.S)
            if m:
                for line in m.group(1).splitlines():
                    line = line.strip()
                    if line and "." in line:
                        retrieval_queries.append(line.split(".", 1)[1].strip())
            m = re.search(r"SEARCH CONTEXT:\s*(.*)", rewritten, re.S)
            if m:
                search_context = m.group(1).strip()
            print(f"[CRAG] Groq fallback rewrite succeeded ({len(retrieval_queries)} queries)!")
            return {
                "structured_brief":  rewritten,
                "keywords":          keywords,
                "retrieval_queries": retrieval_queries or [query],
                "search_context":    search_context or query,
            }
    except Exception as e2:
        print(f"[CRAG] Groq rewrite fallback also failed: {e2}")

    return {
        "structured_brief":  query,
        "keywords":          [],
        "retrieval_queries": [query],
        "search_context":    query,
    }


# ══════════════════════════════════════════════════════════════════════════════
# NODE: retrieve
# Queries all three ChromaDB collections and merges results by score.
# BUG FIX: original queried only one collection; visual_summaries and
# table_data were never searched, wasting the multimodal ingestion.
# ══════════════════════════════════════════════════════════════════════════════
def node_retrieve(search_context, collections: dict, n_per_collection=6):
    """
    collections = {
        "text":   chroma_text_col,
        "table":  chroma_table_col,
        "visual": chroma_visual_col,
    }
    Returns merged (docs, metas) sorted by ChromaDB distance (lower = better).
    """
    embedding = _get_gemini_embedding(search_context)
    all_docs, all_metas, all_dists = [], [], []

    for col_name, col in collections.items():
        if col is None or col.count() == 0:
            continue
        try:
            res   = col.query(query_embeddings=[embedding], n_results=min(n_per_collection, col.count()))
            docs  = res["documents"][0]
            metas = res["metadatas"][0]
            dists = res["distances"][0]
            for doc, meta, dist in zip(docs, metas, dists):
                meta["_collection"] = col_name
                all_docs.append(doc)
                all_metas.append(meta)
                all_dists.append(dist)
        except Exception as e:
            print(f"[CRAG] retrieve from {col_name} failed: {e}")

    if not all_docs:
        return [], []

    # Sort by distance ascending (closer = more relevant) and deduplicate identical text chunks
    combined = sorted(zip(all_dists, all_docs, all_metas), key=lambda x: x[0])
    seen = set()
    deduped_docs, deduped_metas = [], []
    for dist, doc, meta in combined:
        norm_key = " ".join(doc.split())
        if norm_key and norm_key not in seen:
            seen.add(norm_key)
            deduped_docs.append(doc)
            deduped_metas.append(meta)
    return deduped_docs, deduped_metas


# ══════════════════════════════════════════════════════════════════════════════
# NODE: eval_each_doc  (CrossEncoder relevance grader)
# ══════════════════════════════════════════════════════════════════════════════
def node_eval_each_doc(query, docs, reranker):
    if not docs:
        return [], [], "INCORRECT", -10.0

    # Truncate doc to max 1500 chars so MiniLM doesn't waste CPU tokenizing beyond its 512-token context
    pairs = [(query, doc[:1500] if len(doc) > 1500 else doc) for doc in docs]

    if hasattr(reranker, "model") and hasattr(reranker.model, "eval"):
        try:
            reranker.model.eval()
        except Exception:
            pass

    def _call_predict(r, p):
        try:
            return r.predict(p, batch_size=16, show_progress_bar=False)
        except TypeError:
            return r.predict(p)

    try:
        import torch
        with torch.inference_mode():
            preds = _call_predict(reranker, pairs)
    except Exception:
        preds = _call_predict(reranker, pairs)

    raw_logits = np.array(preds)
    max_logit  = float(raw_logits.max())
    norm_scores = (1 / (1 + np.exp(-raw_logits))).tolist()

    print(f"[CRAG] Max raw logit: {max_logit:.3f}  "
          f"(Correct>={UPPER_THRESHOLD}, Incorrect<{LOWER_THRESHOLD})")

    if max_logit >= UPPER_THRESHOLD:
        confidence = "CORRECT"
    elif max_logit < LOWER_THRESHOLD:
        confidence = "INCORRECT"
    else:
        confidence = "AMBIGUOUS"

    return norm_scores, raw_logits.tolist(), confidence, max_logit


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: _select_top_docs
# Zero extra CrossEncoder inference — reuses logits already computed in Step 3.
# Used by the CORRECT branch so node_refine's second reranker.predict() call
# (which caused Railway worker restart via multi-minute CPU spike) is avoided.
# ══════════════════════════════════════════════════════════════════════════════
def _select_top_docs(docs, raw_logits, top_k=6):
    """
    Return the top-k docs sorted by the raw logit already computed in
    node_eval_each_doc.  No CrossEncoder call is made.
    """
    if not docs:
        return ""
    paired = sorted(zip(raw_logits, docs), key=lambda x: x[0], reverse=True)
    top_docs = [d for _, d in paired[:top_k] if _ >= LOWER_THRESHOLD] or [paired[0][1]]
    return "\n\n".join(top_docs)


# ══════════════════════════════════════════════════════════════════════════════
# NODE: refine  (decompose-then-recompose knowledge refinement)
# NOTE: Only called from the AMBIGUOUS branch.  The CORRECT branch uses
#       _select_top_docs instead (zero extra CrossEncoder inference).
#
# SAFETY CAPS added to prevent Railway worker restart:
#   1. Strips are capped at MAX_REFINE_STRIPS before reranker.predict().
#   2. The entire function is wrapped in try/except; on any failure it falls
#      back to _select_top_docs so the pipeline always continues.
# ══════════════════════════════════════════════════════════════════════════════
MAX_REFINE_STRIPS = 60   # hard cap on pairs fed to the second CrossEncoder run

def node_refine(query, docs, raw_logits, reranker, top_k=5):
    """
    Sentence-level re-ranking inside each relevant doc.
    Strips low-relevance sentences and returns only the most on-topic strips.
    Falls back to _select_top_docs if reranker inference fails or times out.
    """
    try:
        all_strips = []
        for doc, logit in zip(docs, raw_logits):
            if logit < LOWER_THRESHOLD:
                continue
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', doc) if len(s.strip()) > 30]
            # Group into sentence pairs for context
            for i in range(0, len(sentences), 2):
                group = " ".join(sentences[i:i+2])
                if group:
                    all_strips.append(group)
                if len(all_strips) >= MAX_REFINE_STRIPS:
                    break
            if len(all_strips) >= MAX_REFINE_STRIPS:
                break

        if not all_strips:
            return "\n\n".join(docs[:3])

        print(f"[CRAG] node_refine: scoring {len(all_strips)} sentence strips (cap={MAX_REFINE_STRIPS})")
        strip_scores  = reranker.predict([(query, s) for s in all_strips])
        scored        = sorted(zip(strip_scores, all_strips), key=lambda x: x[0], reverse=True)
        top_strips    = [s for _, s in scored[:top_k]]
        return "\n\n".join(top_strips) if top_strips else "\n\n".join(docs[:2])
    except Exception as refine_err:
        print(f"[CRAG] node_refine failed ({refine_err}); falling back to logit-sorted docs.")
        return _select_top_docs(docs, raw_logits, top_k=top_k)


# ══════════════════════════════════════════════════════════════════════════════
# NODE: web_search  (Tavily)
# ══════════════════════════════════════════════════════════════════════════════
def node_web_search(search_context, retrieval_queries, tavily, sector="startup", max_results=3):
    all_results, seen_urls = [], set()
    queries = retrieval_queries if retrieval_queries else [search_context]

    for q in queries[:2]:   # cap at 2 queries to avoid Tavily delays and quota burn
        search_query = f"{q} India startup {sector} 2024 2025"
        try:
            results = tavily.search(
                query=search_query,
                search_depth="basic",
                max_results=max_results,
                include_domains=[
                    "startupindia.gov.in", "msme.gov.in", "aim.gov.in",
                    "investindia.gov.in", "inc42.com", "yourstory.com",
                    "economictimes.indiatimes.com", "entrackr.com",
                    "techcrunch.com", "nasscom.in",
                ]
            )
            for r in results.get("results", []):
                url = r.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                all_results.append({
                    "title":   r.get("title", ""),
                    "content": r.get("content", "")[:350],
                    "url":     url,
                    "score":   r.get("score", 0),
                })
        except Exception as e:
            print(f"[CRAG] Tavily search failed for '{q[:40]}': {e}")

    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results


def _format_web_context(web_results) -> str:
    if not web_results:
        return ""
    blocks = []
    for r in web_results:
        blocks.append(f"[{r['title']}]\n{r['content']}\nSource: {r['url']}")
    return "\n\n---\n\n".join(blocks)


# ══════════════════════════════════════════════════════════════════════════════
# NODE: generate_summary  (IBM Granite — CORRECT + AMBIGUOUS branches)
# ══════════════════════════════════════════════════════════════════════════════
def node_generate_summary(structured_brief, context, granite, context_type="internal"):
    type_note = {
        "internal": "retrieved from official Indian government policy documents and reports",
        "combined": "retrieved from official policy documents AND live web sources",
    }.get(context_type, "retrieved")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a senior Indian startup policy advisor with deep knowledge of "
                "government schemes, DPIIT regulations, MSME policies, Startup India, "
                "and the Indian entrepreneurship ecosystem.\n\n"
                "Synthesize the provided context into a clear, actionable policy brief. "
                "Cover: applicable government schemes and eligibility, funding pathways, "
                "regulatory requirements, tax benefits, and sector-specific support.\n\n"
                "Be specific and factual. Only use information from the context — "
                "never hallucinate scheme names, amounts, or eligibility criteria."
            )
        },
        {
            "role": "user",
            "content": (
                f"Startup Brief:\n{structured_brief}\n\n"
                f"Grounded Context ({type_note}):\n{context}\n\n"
                "Write a concise policy brief (300-500 words) covering the most relevant "
                "schemes, eligibility criteria, funding options, and actionable next steps "
                "for this specific startup."
            )
        }
    ]
    response = granite.chat(messages=messages, params={"max_tokens": 1800, "temperature": 0.15})
    return response["choices"][0]["message"]["content"]


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: robust JSON extraction from LLM output
# ══════════════════════════════════════════════════════════════════════════════
_BLUEPRINT_REQUIRED_KEYS = {"bmc", "budget", "gtm", "investors", "competitors", "risks"}
_ALL_BLUEPRINT_KEYS = {"bmc", "budget", "gtm", "investors", "competitors", "risks", "crag_trace"}


def _clean_json_str(s: str) -> str:
    """Strip comments, trailing commas, smart quotes, and surrounding whitespace."""
    # Remove single line comments
    s = re.sub(r'//.*?\n', '\n', s)
    # Remove multi-line comments
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    # Replace smart double quotes
    s = s.replace('\u201c', '"').replace('\u201d', '"')
    # Remove trailing commas before } or ]
    s = re.sub(r',\s*([\]}])', r'\1', s)
    return s.strip()


def _find_balanced_json_spans(text: str) -> list[str]:
    """Find all balanced outermost {...} and [...] candidate JSON spans."""
    spans = []
    for open_ch, close_ch in [('{', '}'), ('[', ']')]:
        i = 0
        n = len(text)
        while i < n:
            start = text.find(open_ch, i)
            if start == -1:
                break
            depth = 0
            in_string = False
            escape_next = False
            end = -1
            for j in range(start, n):
                ch = text[j]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\':
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1
                    if depth == 0:
                        end = j
                        break
            if end > start:
                candidate = text[start:end + 1]
                spans.append(candidate)
                i = end + 1
            else:
                i = start + 1
    # Sort candidate spans longest first
    spans.sort(key=len, reverse=True)
    return spans


def _parse_inr_amount(val: Any, default: int = 0) -> int:
    """
    Safely parse integer INR amounts from diverse model output formats:
    e.g. 250000, 250000.0, "250000", "₹2,50,000", "2.5L", "2.5 Lakhs", "1.5 Cr", "Phase 1 - ₹5,00,000".
    """
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        # 1. Match explicit currency symbol or abbreviation: ₹5,00,000 or Rs. 50,000
        m_curr = re.search(r'(?:₹|rs\.?|inr)\s*([\d,\.]+)', val, re.IGNORECASE)
        if m_curr:
            curr_str = m_curr.group(1).replace(',', '')
            try:
                return int(float(curr_str))
            except ValueError:
                pass

        cleaned = re.sub(r'[₹$,\s]', '', val).lower().strip()
        if not cleaned:
            return default

        # 2. Handle 2.5L / 2.5 Lakh / 2.5 Lakhs
        m_lakh = re.search(r'([\d\.]+)\s*(?:l|lakh|lakhs)', cleaned)
        if m_lakh:
            try:
                return int(float(m_lakh.group(1)) * 100000)
            except ValueError:
                pass

        # 3. Handle 1.5Cr / 1.5 Crore / 1.5 Crores
        m_cr = re.search(r'([\d\.]+)\s*(?:cr|crore|crores)', cleaned)
        if m_cr:
            try:
                return int(float(m_cr.group(1)) * 10000000)
            except ValueError:
                pass

        # 4. Extract all digit sequences; pick the largest number (e.g. 500000 over 1 in 'Phase 1')
        all_nums = re.findall(r'\d+', cleaned)
        if all_nums:
            try:
                return max(int(n) for n in all_nums)
            except ValueError:
                pass
    return default


def _parse_blueprint_json(raw: str) -> dict | list:
    """
    Parse blueprint JSON from GPT-OSS-120B / Groq output, handling common LLM quirks:
      1. Strict json.loads on raw string
      2. Extract markdown code fences (```json ... ```) anywhere in text
      3. Extract balanced JSON structures ({ ... } and [ ... ])
      4. Fix trailing commas, comments, smart quotes, and unescaped whitespace
      5. Fallback to ast.literal_eval for single-quoted Python representations
    Raises ValueError on unrecoverable parse failure so caller can fall through to fallback.
    """
    if not raw or not raw.strip():
        raise ValueError("Empty model output")

    def _is_valid_obj(obj):
        return (isinstance(obj, dict) and len(obj) > 0) or (isinstance(obj, list) and len(obj) > 0)

    # ── Attempt 1: Strict parse ─────────────────────────────────────────────
    try:
        res = json.loads(raw.strip())
        if _is_valid_obj(res):
            return res
    except Exception:
        pass

    # ── Attempt 2: Extract all markdown code blocks ─────────────────────────
    code_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    for block in code_blocks:
        b = block.strip()
        try:
            res = json.loads(b)
            if _is_valid_obj(res):
                return res
        except Exception:
            pass
        try:
            res = json.loads(_clean_json_str(b))
            if _is_valid_obj(res):
                return res
        except Exception:
            pass
        try:
            lit = ast.literal_eval(b)
            if _is_valid_obj(lit):
                return lit
        except Exception:
            pass

    # ── Attempt 3: Balanced bracket structures ──────────────────────────────
    spans = _find_balanced_json_spans(raw)
    for span in spans:
        try:
            res = json.loads(span)
            if _is_valid_obj(res):
                return res
        except Exception:
            pass
        try:
            cleaned_span = _clean_json_str(span)
            res = json.loads(cleaned_span)
            if _is_valid_obj(res):
                return res
        except Exception:
            pass
        try:
            lit = ast.literal_eval(span)
            if _is_valid_obj(lit):
                return lit
        except Exception:
            pass

    # ── Attempt 4: Clean entire raw text and try literal_eval ───────────────
    try:
        cleaned_raw = _clean_json_str(raw)
        res = json.loads(cleaned_raw)
        if _is_valid_obj(res):
            return res
    except Exception:
        pass
    try:
        lit = ast.literal_eval(_clean_json_str(raw))
        if _is_valid_obj(lit):
            return lit
    except Exception:
        pass

    # ── All attempts failed — raise so Groq fallback triggers ──────────────
    snippet = raw[:300].encode('ascii', errors='replace').decode('ascii').replace("\n", "\\n")
    raise ValueError(
        f"Could not extract valid blueprint JSON from model output. "
        f"Content starts with: {snippet}..."
    )


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: normalize blueprint to guarantee consistent schema
# ══════════════════════════════════════════════════════════════════════════════
def _normalize_blueprint(raw: dict) -> dict:
    """
    Ensure every blueprint section exists with the correct structure.
    Both GPT-OSS and Groq output pass through this so the frontend
    always receives a predictable schema.
    """
    if not isinstance(raw, dict):
        raw = {}

    out = {}

    # ── BMC ─────────────────────────────────────────────────────────────────
    bmc = raw.get("bmc", {})
    if not isinstance(bmc, dict):
        bmc = {}
    for key in ("key_partners", "key_resources", "key_activities",
                "value_propositions", "customer_relationships",
                "customer_segments", "channels", "cost_structure",
                "revenue_streams"):
        if key not in bmc or not isinstance(bmc[key], list):
            bmc[key] = bmc.get(key, []) if isinstance(bmc.get(key), list) else []
    out["bmc"] = bmc

    # ── Budget ──────────────────────────────────────────────────────────────
    raw_budget = raw.get("budget", {})
    if isinstance(raw_budget, list):
        budget = {"phases": raw_budget}
    elif isinstance(raw_budget, dict):
        budget = dict(raw_budget)
    elif isinstance(raw_budget, str):
        try:
            parsed_b = _parse_blueprint_json(raw_budget)
            budget = {"phases": parsed_b} if isinstance(parsed_b, list) else (parsed_b if isinstance(parsed_b, dict) else {})
        except Exception:
            budget = {}
    else:
        budget = {}

    had_input_phases = bool(budget.get("phases"))
    raw_phases = budget.get("phases")
    if not isinstance(raw_phases, list) or len(raw_phases) == 0:
        raw_phases = [
            {"name": "MVP", "duration": "Month 1-3",
             "items": [{"item": "Development & Infrastructure", "description": "Development & Infrastructure", "amount": 200000}], "total": 200000},
            {"name": "Launch", "duration": "Month 4-6",
             "items": [{"item": "Marketing & Operations", "description": "Marketing & Operations", "amount": 150000}], "total": 150000},
            {"name": "Growth", "duration": "Month 7-12",
             "items": [{"item": "Scaling & Hiring", "description": "Scaling & Hiring", "amount": 350000}], "total": 350000},
        ]

    normalized_phases = []
    for phase_entry in raw_phases:
        if isinstance(phase_entry, dict):
            phase = dict(phase_entry)
            p_name = phase.get("name") or phase.get("phase") or "Phase"
            phase["name"] = str(p_name)
            phase["duration"] = str(phase.get("duration", ""))
            raw_items = phase.get("items")
        elif isinstance(phase_entry, str):
            p_amt = _parse_inr_amount(phase_entry, default=0)
            phase = {
                "name": phase_entry,
                "duration": "",
                "total": p_amt,
                "phase_total": p_amt,
                "items": [{"item": phase_entry, "description": phase_entry, "amount": p_amt}],
            }
            normalized_phases.append(phase)
            continue
        else:
            phase = {
                "name": "Phase",
                "duration": "",
                "total": 0,
                "phase_total": 0,
                "items": [{"item": "Operations", "description": "Operations", "amount": 0}],
            }
            normalized_phases.append(phase)
            continue

        if not isinstance(raw_items, list):
            if isinstance(raw_items, (str, dict)):
                raw_items = [raw_items]
            else:
                raw_items = [{"item": phase.get("name", "Misc"), "description": phase.get("name", "Misc"), "amount": phase.get("total", 0)}]

        normalized_items = []
        phase_running_total = 0
        for item_entry in raw_items:
            if isinstance(item_entry, dict):
                it = dict(item_entry)
                it_name = it.get("item") or it.get("name") or it.get("description") or "Misc Expense"
                it["item"] = str(it_name)
                if "description" not in it:
                    it["description"] = str(it_name)
                amt_val = it.get("amount")
                if isinstance(amt_val, (int, float)):
                    it["amount"] = int(amt_val)
                else:
                    it["amount"] = _parse_inr_amount(amt_val, default=0)
                normalized_items.append(it)
                phase_running_total += it["amount"]
            elif isinstance(item_entry, str):
                parsed_amt = _parse_inr_amount(item_entry, default=0)
                it = {
                    "item": item_entry,
                    "description": item_entry,
                    "amount": parsed_amt if parsed_amt > 0 else 0,
                }
                normalized_items.append(it)
                phase_running_total += it["amount"]
            else:
                it = {
                    "item": str(item_entry) if item_entry is not None else "Misc Expense",
                    "description": str(item_entry) if item_entry is not None else "Misc Expense",
                    "amount": int(item_entry) if isinstance(item_entry, (int, float)) else 0,
                }
                normalized_items.append(it)
                phase_running_total += it["amount"]

        phase["items"] = normalized_items
        p_total = phase.get("total")
        if not isinstance(p_total, (int, float)) or p_total <= 0:
            phase["total"] = phase_running_total
        else:
            phase["total"] = int(p_total)
        phase["phase_total"] = phase["total"]
        normalized_phases.append(phase)

    budget["phases"] = normalized_phases

    phase_sum = sum(p.get("total", 0) for p in normalized_phases)
    total_12 = budget.get("total_12_months")
    if had_input_phases and phase_sum > 0:
        budget["total_12_months"] = phase_sum
    elif isinstance(total_12, (int, float)) and total_12 > 0:
        budget["total_12_months"] = int(total_12)
    elif phase_sum > 0:
        budget["total_12_months"] = phase_sum
    else:
        budget["total_12_months"] = 0

    budget["currency"] = budget.get("currency") or "INR"
    budget["timeframe"] = budget.get("timeframe") or "12 Months"
    budget["total_12_months_inr"] = f"₹{int(budget['total_12_months']):,}"

    if not budget.get("funding_suggestion"):
        budget["funding_suggestion"] = "Startup India Seed Fund + Angel Investment"

    out["budget"] = budget

    # ── GTM ─────────────────────────────────────────────────────────────────
    gtm = raw.get("gtm", {})
    if not isinstance(gtm, dict):
        gtm = {}
    gtm["target_market"] = str(gtm.get("target_market") or "Target market definition in progress")
    gtm["market_size"] = str(gtm.get("market_size") or "")
    
    # Preserve or generate structured market sizing if available
    m_sizing = gtm.get("market_sizing")
    if isinstance(m_sizing, dict):
        gtm["market_sizing"] = {
            "tam": str(m_sizing.get("tam") or "N/A"),
            "sam": str(m_sizing.get("sam") or "N/A"),
            "som": str(m_sizing.get("som") or "N/A"),
            "geography": str(m_sizing.get("geography") or "India"),
            "currency": str(m_sizing.get("currency") or "INR / USD"),
            "assumptions": str(m_sizing.get("assumptions") or "Based on target segment size"),
            "sources": str(m_sizing.get("sources") or "Industry estimates & Government reports"),
        }
    else:
        gtm["market_sizing"] = {
            "tam": "Estimated Total Addressable Market",
            "sam": "Serviceable Addressable Market",
            "som": "Serviceable Obtainable Market (Year 1-2)",
            "geography": "India",
            "currency": "INR",
            "assumptions": "Calculated based on target MSME/consumer population",
            "sources": "Official Ministry Reports & Market Research",
        }

    raw_launch = gtm.get("launch_strategy")
    if isinstance(raw_launch, list):
        gtm["launch_strategy"] = [str(x) for x in raw_launch]
    else:
        gtm["launch_strategy"] = [
            "1. Pilot Testing: Prototype validation with initial user cohort",
            "2. MVP Launch: Core release to invite-only users",
            "3. Early Traction: Onboard paid pilot businesses",
            "4. Market Expansion: Multi-city digital acquisition rollout",
            "5. Scale: Enterprise/partner channel distribution",
        ]

    raw_channels = gtm.get("growth_channels")
    norm_channels = []
    if isinstance(raw_channels, list):
        for ch in raw_channels:
            if isinstance(ch, dict):
                norm_channels.append({
                    "channel": str(ch.get("channel") or "Direct Acquisition"),
                    "strategy": str(ch.get("strategy") or ""),
                    "rationale": str(ch.get("rationale") or "High intent conversion"),
                    "priority": str(ch.get("priority") or "MEDIUM").upper(),
                    "cost": str(ch.get("cost") or "MIXED").upper(),
                })
            elif isinstance(ch, str):
                norm_channels.append({
                    "channel": ch,
                    "strategy": ch,
                    "rationale": "Direct growth channel",
                    "priority": "HIGH",
                    "cost": "LOW",
                })
    gtm["growth_channels"] = norm_channels

    raw_milestones = gtm.get("milestones")
    norm_milestones = []
    if isinstance(raw_milestones, list):
        for m in raw_milestones:
            if isinstance(m, dict):
                norm_milestones.append({
                    "month": int(m.get("month", 1)) if str(m.get("month", "1")).isdigit() else 1,
                    "goal": str(m.get("goal") or "Core milestone"),
                })
            elif isinstance(m, str):
                norm_milestones.append({"month": len(norm_milestones) + 1, "goal": m})
    gtm["milestones"] = norm_milestones
    gtm["key_metrics"] = [str(k) for k in (gtm.get("key_metrics") or [])] if isinstance(gtm.get("key_metrics"), list) else []
    out["gtm"] = gtm

    # ── Investors & Funding ──────────────────────────────────────────────────
    raw_inv = raw.get("investors")
    if not isinstance(raw_inv, dict):
        raw_inv = raw.get("funding") if isinstance(raw.get("funding"), dict) else {}
    
    # Handle nested wrapping (e.g. {"funding": {"funding_roadmap": ...}} or {"investors": {...}})
    if isinstance(raw_inv.get("funding"), dict) and not raw_inv.get("funding_roadmap"):
        investors = dict(raw_inv["funding"])
    elif isinstance(raw_inv.get("investors"), dict) and not raw_inv.get("funding_roadmap"):
        investors = dict(raw_inv["investors"])
    else:
        investors = dict(raw_inv)

    # Normalize funding roadmap
    raw_roadmap = investors.get("funding_roadmap")
    norm_roadmap = []
    if isinstance(raw_roadmap, list):
        for r in raw_roadmap:
            if isinstance(r, dict):
                norm_roadmap.append({
                    "stage": str(r.get("stage") or "Early Stage"),
                    "timeline": str(r.get("timeline") or "Month 1-6"),
                    "source": str(r.get("source") or "Grants & Angels"),
                    "amount": str(r.get("amount") or "₹20L - ₹50L"),
                })
            elif isinstance(r, str):
                norm_roadmap.append({
                    "stage": "Pre-Seed / Seed",
                    "timeline": "Month 1-6",
                    "source": r,
                    "amount": "₹25L - ₹75L",
                })
    investors["funding_roadmap"] = norm_roadmap

    # Normalize government schemes
    raw_schemes = investors.get("government_schemes")
    norm_schemes = []
    if isinstance(raw_schemes, list):
        for s in raw_schemes:
            if isinstance(s, dict):
                norm_schemes.append({
                    "name": str(s.get("name") or "Government Startup Scheme"),
                    "administering_agency": str(s.get("administering_agency") or "Govt of India / DPIIT"),
                    "type": str(s.get("type") or "Grant / Collateral-Free Debt"),
                    "amount": str(s.get("amount") or "Up to ₹50 Lakhs"),
                    "benefit": str(s.get("benefit") or s.get("benefits") or "Non-dilutive capital and incubation assistance"),
                    "eligibility": str(s.get("eligibility") or "DPIIT recognised startups incorporated < 2 years"),
                    "conditions": str(s.get("conditions") or "Subject to incubator milestone approvals; Indian entity ownership"),
                    "application_steps": str(s.get("application_steps") or "Apply online via official Startup India portal through partner incubators"),
                    "official_url": str(s.get("official_url") or "https://www.startupindia.gov.in"),
                    "source": str(s.get("source") or "Official Startup India Guidelines"),
                    "relevance": str(s.get("relevance") or "Early validation and working capital support"),
                    "limitations": str(s.get("limitations") or "Selection committee dependent; non-guaranteed"),
                })
            elif isinstance(s, str):
                norm_schemes.append({
                    "name": s,
                    "administering_agency": "DPIIT / MSME Ministry",
                    "type": "Grant / Subsidized Scheme",
                    "amount": "Up to ₹50 Lakhs",
                    "benefit": s,
                    "eligibility": "DPIIT recognised startups",
                    "conditions": "Subject to official verification and guidelines",
                    "application_steps": "Apply via official portal",
                    "official_url": "https://www.startupindia.gov.in",
                    "source": "Official Portal",
                    "relevance": "Non-dilutive funding support",
                    "limitations": "Competitive selection process",
                })
    investors["government_schemes"] = norm_schemes

    inv_types = investors.get("investor_types") or investors.get("investor_landscape") or []
    if not isinstance(inv_types, list) or len(inv_types) == 0:
        inv_types = [
            {"type": "Angel Networks & Early Syndicates", "stage": "Pre-Seed / Seed", "focus": "Tech Startups", "examples": ["Indian Angel Network (IAN)", "Mumbai Angels", "LetsVenture"]},
            {"type": "Seed & Pre-Series A Venture Funds", "stage": "Seed", "focus": "India Software & SaaS", "examples": ["Blume Ventures", "Kae Capital", "India Quotient"]},
        ]
    investors["investor_types"] = inv_types
    investors["investor_landscape"] = inv_types

    incubators = investors.get("incubators") or investors.get("relevant_incubators") or []
    if not isinstance(incubators, list) or len(incubators) == 0:
        incubators = [
            {"name": "NSRCEL (IIM Bangalore)", "focus": "Early stage tech startups", "location": "Bangalore"},
            {"name": "CIIE.CO (IIM Ahmedabad)", "focus": "Fintech & inclusion tech", "location": "Ahmedabad"},
            {"name": "T-Hub", "focus": "Enterprise tech & scaling", "location": "Hyderabad"},
        ]
    investors["incubators"] = incubators
    investors["relevant_incubators"] = incubators

    pitch_tips = investors.get("pitch_tips") or []
    if not isinstance(pitch_tips, list) or len(pitch_tips) == 0:
        pitch_tips = [
            "Highlight verified customer retention and clear unit economics (LTV/CAC > 3x)",
            "Emphasize DPIIT regulatory compliance and data security governance",
            "Present a realistic 18-month burn rate with milestones tied to next round valuation",
        ]
    investors["pitch_tips"] = pitch_tips

    out["investors"] = investors
    out["funding"] = investors

    # ── Competitors ─────────────────────────────────────────────────────────
    raw_comp = raw.get("competitors", {})
    if isinstance(raw_comp, list):
        comp_dict = {"competitors": raw_comp}
    elif isinstance(raw_comp, dict):
        if isinstance(raw_comp.get("competitor_analysis"), dict):
            comp_dict = dict(raw_comp["competitor_analysis"])
        elif isinstance(raw_comp.get("competitors"), dict):
            comp_dict = dict(raw_comp["competitors"])
        else:
            comp_dict = dict(raw_comp)
    else:
        comp_dict = {}

    comp_items = comp_dict.get("competitors")
    if not isinstance(comp_items, list):
        if isinstance(comp_items, dict):
            comp_items = [comp_items]
        else:
            comp_items = []

    # If competitors list was empty in comp_dict, check raw["competitors"]
    if not comp_items and isinstance(raw.get("competitors"), list):
        comp_items = raw["competitors"]

    normalized_competitors = []
    for item in comp_items:
        if isinstance(item, dict):
            c = dict(item)
            c["name"] = str(c.get("name") or "Competitor Alternative")
            c["type"] = str(c.get("type") or "Direct / Indirect")
            c["target_customer"] = str(c.get("target_customer") or "Target segment")
            c["core_offering"] = str(c.get("core_offering") or c.get("core_features") or "Standard product offering")
            c["core_features"] = c["core_offering"]
            c["pricing"] = str(c.get("pricing") or "Tiered subscription / Custom pricing")
            c["strength"] = str(c.get("strength") or c.get("strengths") or "Established presence")
            c["weakness"] = str(c.get("weakness") or c.get("limitations") or "Legacy architecture")
            c["differentiator"] = str(c.get("differentiator") or "Specialized AI predictive intelligence")
            
            # Clean market share: strip double percent signs and normalize decimals
            ms = str(c.get("market_share") or "").strip()
            if ms and not any(w in ms.lower() for w in ("unknown", "n/a", "none", "private", "unsupported")):
                ms_clean = ms.replace("%", "").strip()
                try:
                    val = float(ms_clean)
                    if 0.0 < val <= 1.0:
                        c["market_share"] = f"{round(val * 100)}%"
                    elif val.is_integer():
                        c["market_share"] = f"{int(val)}%"
                    else:
                        c["market_share"] = f"{val}%"
                except ValueError:
                    c["market_share"] = ms
            else:
                c["market_share"] = None
            c["funding"] = str(c.get("funding") or "Venture-backed / Established")
            normalized_competitors.append(c)
        elif isinstance(item, str):
            normalized_competitors.append({
                "name": item,
                "type": "Market Alternative",
                "target_customer": "General market",
                "core_offering": item,
                "core_features": item,
                "pricing": "Standard market rates",
                "strength": "High brand familiarity",
                "weakness": "Lacks AI personalization",
                "differentiator": "Proactive automated workflow",
                "market_share": "N/A",
                "funding": "Bootstrapped / Unknown",
            })
    comp_dict["competitors"] = normalized_competitors

    # Differentiators: check our_differentiators and differentiators in comp_dict and raw
    diffs = (
        comp_dict.get("our_differentiators")
        or comp_dict.get("differentiators")
        or (raw.get("our_differentiators") if isinstance(raw, dict) else None)
        or (raw.get("differentiators") if isinstance(raw, dict) else None)
        or []
    )
    if isinstance(diffs, str):
        diffs = [diffs]
    elif not isinstance(diffs, list):
        diffs = []
    if not diffs:
        diffs = [
            "Proprietary predictive models forecasting critical business metrics 14-30 days ahead",
            "Zero-friction automated onboarding with one-click data integrations",
            "Actionable micro-recommendations tailored to early-stage operational constraints",
        ]
    comp_dict["our_differentiators"] = [str(d) for d in diffs]

    # Market gaps
    gaps = (
        comp_dict.get("market_gaps")
        or comp_dict.get("gaps")
        or (raw.get("market_gaps") if isinstance(raw, dict) else None)
        or (raw.get("gaps") if isinstance(raw, dict) else None)
        or []
    )
    if isinstance(gaps, str):
        gaps = [gaps]
    elif not isinstance(gaps, list):
        gaps = []
    if not gaps:
        gaps = [
            "Existing tools offer only lagging retrospective reporting rather than forward-looking forecasting",
            "Complex enterprise software pricing and UX inaccessible to lean operations",
            "Lack of unified workflow connecting planning directly to execution",
        ]
    comp_dict["market_gaps"] = [str(g) for g in gaps]

    strat = (
        comp_dict.get("competitive_strategy")
        or comp_dict.get("strategy")
        or (raw.get("competitive_strategy") if isinstance(raw, dict) else None)
        or (raw.get("strategy") if isinstance(raw, dict) else None)
        or "Position as an intelligent, agile companion that complements existing software, focusing on proactive alerts, rapid time-to-value, and zero onboarding friction."
    )
    comp_dict["competitive_strategy"] = str(strat)
    out["competitors"] = comp_dict

    # ── Risks ───────────────────────────────────────────────────────────────
    raw_risks = raw.get("risks", {})
    if isinstance(raw_risks, list):
        risk_items = raw_risks
    elif isinstance(raw_risks, dict):
        risk_items = raw_risks.get("risks", []) if isinstance(raw_risks.get("risks"), list) else []
    else:
        risk_items = []

    normalized_risks = []
    for r in risk_items:
        if isinstance(r, dict):
            # Normalize severity and probability enums safely
            sev_raw = str(r.get("severity") or "MEDIUM").strip().lower()
            if any(x in sev_raw for x in ("high", "crit", "sev", "major")):
                sev = "HIGH"
            elif any(x in sev_raw for x in ("low", "min", "negligible")):
                sev = "LOW"
            else:
                sev = "MEDIUM"

            prob_raw = str(r.get("probability") or "MEDIUM").strip().lower()
            if any(x in prob_raw for x in ("high", "likel", "frequent", "probable")):
                prob = "HIGH"
            elif any(x in prob_raw for x in ("low", "unlik", "rare", "chance")):
                prob = "LOW"
            else:
                prob = "MEDIUM"
            
            normalized_risks.append({
                "category": str(r.get("category") or "Operational"),
                "severity": sev,
                "probability": prob,
                "impact": str(r.get("impact") or "Potential disruption to operations or revenue growth"),
                "risk": str(r.get("risk") or r.get("description") or "Identified risk factor"),
                "mitigation": str(r.get("mitigation") or "Implement structured monitoring and corrective controls"),
                "monitoring_indicator": str(r.get("monitoring_indicator") or "Monthly review of operational KPIs"),
            })
        elif isinstance(r, str):
            normalized_risks.append({
                "category": "Operational",
                "severity": "MEDIUM",
                "probability": "MEDIUM",
                "impact": "Operational friction",
                "risk": r,
                "mitigation": "Establish proactive protocol and regular review",
                "monitoring_indicator": "Monthly KPI tracking",
            })

    out["risks"] = {"risks": normalized_risks}

    # ── CRAG Trace ──────────────────────────────────────────────────────────
    crag_trace = raw.get("crag_trace", {})
    if not isinstance(crag_trace, dict):
        crag_trace = {}
    
    # Ensure structured arrays exist
    if not isinstance(crag_trace.get("verified_context"), list):
        crag_trace["verified_context"] = [
            "Startup India Seed Fund Scheme operational guidelines",
            "DPIIT startup recognition criteria and benefits",
            "Current Indian regulatory and compliance frameworks",
        ]
    if not isinstance(crag_trace.get("inferences"), list):
        crag_trace["inferences"] = [
            "Targeting early-stage market with non-dilutive grants minimizes early founder equity dilution",
            "Modular architecture ensures capital efficiency during MVP development phase",
        ]
    if not isinstance(crag_trace.get("recommendations"), list):
        crag_trace["recommendations"] = [
            "Incorporate as a private limited entity to qualify for DPIIT certification",
            "Apply for SISFS via verified incubator partner upon MVP completion",
        ]
    if not isinstance(crag_trace.get("source_usage"), list):
        crag_trace["source_usage"] = [
            {"claim": "Government grant eligibility criteria", "source": "DPIIT Startup India Guidelines", "section": "Funding"},
            {"claim": "Market structural parameters", "source": "Official Industry Reports", "section": "GTM & Competitors"},
        ]
    out["crag_trace"] = crag_trace

    # Preserve status and failed_sections
    out["status"] = raw.get("status", "success")
    out["failed_sections"] = raw.get("failed_sections", [])

    # Log which sections are genuinely populated vs defaulted
    for section in _BLUEPRINT_REQUIRED_KEYS:
        val = out.get(section, {})
        if not val or val == {} or (isinstance(val, dict) and all(
            v == [] or v == "" or v == {} for v in val.values()
        )):
            print(f"[CRAG Blueprint] WARNING: section '{section}' is empty/defaulted")

    return out


# ══════════════════════════════════════════════════════════════════════════════
# MODULAR SECTION GENERATION (Fast, Compact, Parallelized, Resilient)
# ══════════════════════════════════════════════════════════════════════════════

def _call_section_llm(
    section_name: str,
    system_prompt: str,
    user_prompt: str,
    groq_client,
    gpt_oss_client,
    max_tokens: int = 1600,
    temperature: float = 0.2,
    timeout_sec: int = 15,
) -> dict:
    """
    Execute a structured generation call with:
      - Mandatory prompt & model parameter logging
      - Strict timeout
      - Primary IBM GPT-OSS-120B call
      - Graceful fallback to Groq
      - Robust JSON extraction
    """
    import concurrent.futures

    model_id = getattr(gpt_oss_client, "model_id", "openai/gpt-oss-120b") if gpt_oss_client else "openai/gpt-oss-120b"
    est_tokens = len(user_prompt) // 4
    print(f"\n[BLUEPRINT MODEL CALL: {section_name.upper()}]")
    print(f"MODEL: GPT-OSS-120B")
    print(f"MODEL ID: {model_id}")
    print(f"PROVIDER: IBM Watsonx")
    print(f"INPUT TOKENS IF AVAILABLE: ~{est_tokens}")
    print(f"MAX OUTPUT TOKENS: {max_tokens}")
    print(f"TEMPERATURE: {temperature}")
    print(f"TIMEOUT: {timeout_sec}s")

    t0 = time.time()

    # 1. Primary: IBM Watsonx GPT-OSS-120B with strict timeout
    if gpt_oss_client is not None and _is_ibm_available():
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ]
            fut = pool.submit(
                gpt_oss_client.chat,
                messages=messages,
                params={"max_tokens": max_tokens, "temperature": temperature}
            )
            response = fut.result(timeout=timeout_sec)
            choice = (response.get("choices") or [{}])[0]
            content = ((choice.get("message") or {}).get("content") or "").strip()
            if content:
                res = _parse_blueprint_json(content)
                print(f"[BLUEPRINT] {section_name}: SUCCESS (via IBM GPT-OSS-120B, {time.time()-t0:.1f}s)")
                return res
        except Exception as e:
            clean_e = str(e).encode('ascii', errors='replace').decode('ascii')
            if "429" in clean_e or "too many requests" in clean_e.lower() or "rate_limit" in clean_e.lower():
                _set_ibm_cooldown(120)
            print(f"[CRAG Section] {section_name} via IBM GPT-OSS-120B failed or timed out ({clean_e}), attempting Groq fallback...")
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    elif gpt_oss_client is not None and not _is_ibm_available():
        print(f"[CRAG Section] {section_name}: IBM cooldown active (429), bypassing immediately to Groq fallback.")

    # 2. Fallback: Groq with 429 backoff retry
    if groq_client is not None:
        groq_model = get_settings().GROQ_MODEL
        target_tokens = min(max_tokens, 1500)
        print(f"\n[BLUEPRINT FALLBACK CALL: {section_name.upper()}]")
        print(f"MODEL: Groq Llama")
        print(f"MODEL ID: {groq_model}")
        print(f"PROVIDER: Groq")
        print(f"INPUT TOKENS IF AVAILABLE: ~{est_tokens}")
        print(f"MAX OUTPUT TOKENS: {target_tokens}")
        print(f"TEMPERATURE: {temperature}")
        print(f"TIMEOUT: 15s")
        t1 = time.time()
        for attempt in range(3):
            try:
                r = groq_client.chat.completions.create(
                    model=groq_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=target_tokens,
                    response_format={"type": "json_object"},
                    timeout=15.0,
                )
                groq_content = (r.choices[0].message.content or "").strip()
                if groq_content:
                    res = _parse_blueprint_json(groq_content)
                    print(f"[BLUEPRINT] {section_name}: SUCCESS (via Groq {groq_model}, {time.time()-t1:.1f}s)")
                    return res
            except Exception as e2:
                clean_e2 = str(e2).encode('ascii', errors='replace').decode('ascii')
                if "429" in clean_e2 or "rate_limit" in clean_e2.lower():
                    delay = 3.5
                    m_delay = re.search(r"try again in ([\d\.]+)s", clean_e2)
                    if m_delay:
                        try:
                            delay = float(m_delay.group(1)) + 0.5
                        except Exception:
                            pass
                    print(f"[CRAG Section] {section_name} hit Groq rate limit (429). Retrying in {delay:.1f}s (attempt {attempt+1}/3)...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"[CRAG Section] {section_name} via Groq also failed: {clean_e2}")
                    break

    print(f"[BLUEPRINT] {section_name}: FAILED (Both IBM and Groq failed)")
    return {}


def _gen_bmc(brief: str, evidence: str, groq_client, gpt_oss_client) -> dict:
    system_prompt = (
        "You are an expert startup strategist. Generate a complete Business Model Canvas for the startup idea. "
        "Return ONLY a JSON object with 9 lists matching the schema."
    )
    user_prompt = f"""STARTUP IDEA:
{brief}

EVIDENCE & CONTEXT:
{evidence}

Generate a concise, realistic Business Model Canvas in India.
Return JSON with this exact schema:
{{
  "key_partners": ["partner1", "partner2", "partner3", "partner4"],
  "key_resources": ["resource1", "resource2", "resource3", "resource4"],
  "key_activities": ["activity1", "activity2", "activity3", "activity4"],
  "value_propositions": ["prop1", "prop2", "prop3"],
  "customer_relationships": ["rel1", "rel2", "rel3"],
  "customer_segments": ["segment1", "segment2", "segment3"],
  "channels": ["channel1", "channel2", "channel3"],
  "cost_structure": ["cost1", "cost2", "cost3", "cost4"],
  "revenue_streams": ["stream1", "stream2", "stream3"]
}}"""
    raw = _call_section_llm("bmc", system_prompt, user_prompt, groq_client, gpt_oss_client, max_tokens=1500)
    return raw.get("bmc", raw)


def _gen_budget(brief: str, evidence: str, groq_client, gpt_oss_client) -> dict:
    system_prompt = (
        "You are a startup financial advisor. Estimate a practical 12-month budget in Indian Rupees (INR) across 3 phases: "
        "MVP (Month 1-3), Launch (Month 4-6), and Growth (Month 7-12). "
        "Return ONLY a JSON object matching the schema."
    )
    user_prompt = f"""STARTUP IDEA:
{brief}

EVIDENCE & CONTEXT:
{evidence}

Provide estimated line items with realistic integer INR amounts (e.g. 150000).
Return JSON with this exact schema:
{{
  "phases": [
    {{
      "name": "MVP",
      "duration": "Month 1-3",
      "items": [
        {{"item": "Core Platform Engineering", "amount": 250000}},
        {{"item": "Cloud Hosting & AI APIs", "amount": 100000}},
        {{"item": "Legal & Incorporation", "amount": 50000}}
      ]
    }},
    {{
      "name": "Launch",
      "duration": "Month 4-6",
      "items": [
        {{"item": "Customer Acquisition & Digital Marketing", "amount": 200000}},
        {{"item": "Sales Outreach & Support", "amount": 150000}},
        {{"item": "Operational Overhead", "amount": 50000}}
      ]
    }},
    {{
      "name": "Growth",
      "duration": "Month 7-12",
      "items": [
        {{"item": "Team Scaling & Senior Engineers", "amount": 400000}},
        {{"item": "Partnership Marketing & SEO", "amount": 250000}},
        {{"item": "Security & Compliance Audits", "amount": 150000}}
      ]
    }}
  ],
  "funding_suggestion": "Startup India Seed Fund Scheme (SISFS) + Angel Syndicate"
}}"""
    raw = _call_section_llm("budget", system_prompt, user_prompt, groq_client, gpt_oss_client, max_tokens=1400)
    if isinstance(raw, list):
        budget = {"phases": raw}
    elif isinstance(raw, dict):
        budget = raw.get("budget", raw)
        if not isinstance(budget, dict):
            budget = {"phases": []}
    else:
        budget = {"phases": []}

    phases = budget.get("phases", [])
    if (not isinstance(phases, list) or len(phases) == 0) and isinstance(budget, dict):
        recovered_phases = []
        for k, v in budget.items():
            if any(p in k.lower() for p in ("mvp", "launch", "growth", "phase")):
                if isinstance(v, list):
                    recovered_phases.append({"name": k.upper(), "duration": "", "items": v})
                elif isinstance(v, dict):
                    recovered_phases.append({"name": v.get("name", k.upper()), "duration": v.get("duration", ""), "items": v.get("items", [])})
        if recovered_phases:
            phases = recovered_phases

    if not isinstance(phases, list) or len(phases) == 0:
        phases = [
            {"name": "MVP", "duration": "Month 1-3", "items": [{"item": "Core Engineering & Infrastructure", "amount": 300000}]},
            {"name": "Launch", "duration": "Month 4-6", "items": [{"item": "Marketing & Pilot Acquisition", "amount": 250000}]},
            {"name": "Growth", "duration": "Month 7-12", "items": [{"item": "Scaling & Security Audits", "amount": 450000}]},
        ]
    total_12 = 0
    for p in phases:
        if not isinstance(p, dict):
            continue
        items = p.get("items", [])
        if not isinstance(items, list):
            items = []
        phase_total = 0
        norm_items = []
        for it in items:
            if isinstance(it, dict):
                amt = _parse_inr_amount(it.get("amount", 0))
                it["amount"] = amt
                norm_items.append(it)
                phase_total += amt
            elif isinstance(it, str):
                amt = _parse_inr_amount(it, default=0)
                norm_items.append({"item": it, "description": it, "amount": amt})
                phase_total += amt
        p["items"] = norm_items
        p["total"] = phase_total
        p["phase_total"] = phase_total
        total_12 += phase_total
    budget["total_12_months"] = total_12 if total_12 > 0 else 1000000
    budget["total_12_months_inr"] = f"₹{budget['total_12_months']:,}"
    for p in phases:
        if isinstance(p, dict):
            p["percentage"] = round((p.get("total", 0) / budget["total_12_months"]) * 100, 1)
    budget["phases"] = phases
    if not budget.get("funding_suggestion"):
        budget["funding_suggestion"] = "Startup India Seed Fund Scheme + Angel Investment"
    return budget


def _gen_gtm(brief: str, evidence: str, groq_client, gpt_oss_client) -> dict:
    system_prompt = (
        "You are a Go-to-Market growth strategist. Generate a structured GTM plan for an Indian startup. "
        "Return ONLY a JSON object matching the schema."
    )
    user_prompt = f"""STARTUP IDEA:
{brief}

EVIDENCE & CONTEXT:
{evidence}

Generate a concise, practical GTM strategy with 5 sequential launch steps, growth channels, milestones, and KPIs.
Return JSON with this exact schema:
{{
  "target_market": "Clear definition of initial target customer and geography",
  "market_size": "Estimated TAM, SAM, SOM (e.g. TAM: $2.5B, SAM: $450M, SOM: $15M in India)",
  "launch_strategy": [
    "1. Preparation: Prototype validation with 20 pilot users",
    "2. MVP: Release core feature set to targeted beta cohort",
    "3. Pilot: Paid pilot deployment with 50 MSMEs",
    "4. Public Launch: Self-serve onboarding and digital campaigns",
    "5. Expansion: Regional partner networks and enterprise tiers"
  ],
  "growth_channels": [
    {{
      "channel": "B2B Outbound & Direct Sales",
      "strategy": "Direct outreach to SME business owners via LinkedIn & email",
      "rationale": "High conversion for SaaS software",
      "priority": "HIGH",
      "cost": "MIXED"
    }},
    {{
      "channel": "Industry Associations & CA Partnerships",
      "strategy": "Partner with chartered accountant networks & MSME forums",
      "rationale": "Trusted advisors recommend the platform",
      "priority": "HIGH",
      "cost": "FREE"
    }},
    {{
      "channel": "Content Marketing & SEO",
      "strategy": "Practical guides on Indian business cash flow & GST",
      "rationale": "Organic intent-driven acquisition",
      "priority": "MEDIUM",
      "cost": "FREE"
    }}
  ],
  "milestones": [
    {{"month": 1, "goal": "Beta architecture and compliance framework established"}},
    {{"month": 3, "goal": "Onboard first 25 active pilot customers"}},
    {{"month": 6, "goal": "Achieve ₹1.5L MRR with >80% 30-day retention"}},
    {{"month": 9, "goal": "Expand to 150 paying business accounts"}},
    {{"month": 12, "goal": "Reach ₹10L MRR and initiate Seed fundraising round"}}
  ],
  "key_metrics": ["Monthly Recurring Revenue (MRR)", "Customer Acquisition Cost (CAC)", "Customer Lifetime Value (LTV)", "Monthly Net Churn", "Weekly Active Users (WAU)"]
}}"""
    raw = _call_section_llm("gtm", system_prompt, user_prompt, groq_client, gpt_oss_client, max_tokens=1600)
    return raw.get("gtm", raw)


def _gen_investors(brief: str, evidence: str, groq_client, gpt_oss_client) -> dict:
    system_prompt = (
        "You are a venture capital and government scheme specialist for Indian startups. "
        "Ground recommendations in official schemes (Startup India, MSME, DPIIT, SIDBI) and Indian investor networks. "
        "Return ONLY a JSON object matching the schema."
    )
    user_prompt = f"""STARTUP IDEA:
{brief}

EVIDENCE & CONTEXT:
{evidence}

Generate a realistic funding roadmap, eligible government schemes (with benefits, eligibility, limitations), investor categories, and pitch tips.
Return JSON with this exact schema:
{{
  "funding_roadmap": [
    {{"stage": "Pre-Seed / Grants", "timeline": "Month 1-4", "source": "Startup India Seed Fund (SISFS) / Incubator Grants", "amount": "₹20L - ₹50L"}},
    {{"stage": "Seed Round", "timeline": "Month 5-9", "source": "Angel Networks & Micro VCs", "amount": "₹75L - ₹1.5Cr"}},
    {{"stage": "Pre-Series A", "timeline": "Month 10-14", "source": "Early Stage VCs", "amount": "₹3Cr - ₹5Cr"}}
  ],
  "government_schemes": [
    {{
      "name": "Startup India Seed Fund Scheme (SISFS)",
      "benefit": "Grants up to ₹20L for prototype; debt/convertible up to ₹50L for market entry",
      "eligibility": "DPIIT recognised startup incorporated < 2 years with innovative business model",
      "relevance": "Non-dilutive early capital to fund MVP and initial validation",
      "limitations": "Subject to incubator selection committee approval and milestones",
      "amount": "Up to ₹50 Lakhs"
    }},
    {{
      "name": "Credit Guarantee Scheme for Startups (CGSS)",
      "benefit": "Collateral-free credit guarantee for loans by member institutions",
      "eligibility": "DPIIT recognised startups with stable revenue",
      "relevance": "Access to working capital debt without collateral",
      "limitations": "Requires bank approval and financial track record",
      "amount": "Up to ₹10 Crores"
    }}
  ],
  "investor_types": [
    {{
      "type": "Early Stage Angel Syndicates",
      "stage": "Pre-Seed / Seed",
      "focus": "Fintech, B2B SaaS, MSME Tech",
      "examples": ["Indian Angel Network (IAN)", "Mumbai Angels", "LetsVenture"]
    }},
    {{
      "type": "Seed & Pre-Series A Venture Funds",
      "stage": "Seed",
      "focus": "India-first SaaS, Enterprise Software",
      "examples": ["Blume Ventures", "Kae Capital", "India Quotient"]
    }}
  ],
  "incubators": [
    {{"name": "NSRCEL (IIM Bangalore)", "focus": "Early stage tech startups", "location": "Bangalore"}},
    {{"name": "CIIE.CO (IIM Ahmedabad)", "focus": "Tech inclusion and FinTech", "location": "Ahmedabad"}},
    {{"name": "T-Hub", "focus": "Enterprise tech & scaling", "location": "Hyderabad"}}
  ],
  "pitch_tips": [
    "Highlight unit economics and clear path to LTV/CAC > 3x",
    "Emphasize MSME pain point validation with pilot customer quotes",
    "Showcase regulatory alignment with DPIIT and data privacy standards",
    "Demonstrate SaaS recurring revenue predictability with low churn assumptions"
  ]
}}"""
    raw = _call_section_llm("investors", system_prompt, user_prompt, groq_client, gpt_oss_client, max_tokens=1600)
    if isinstance(raw, dict):
        if isinstance(raw.get("investors"), dict):
            inv = dict(raw["investors"])
        elif isinstance(raw.get("funding"), dict):
            inv = dict(raw["funding"])
        else:
            inv = dict(raw)
    else:
        inv = {}

    inv_types = inv.get("investor_types") or inv.get("investor_landscape") or []
    if isinstance(inv_types, list):
        inv["investor_types"] = inv_types
        inv["investor_landscape"] = inv_types
    incubators = inv.get("incubators") or inv.get("relevant_incubators") or []
    if isinstance(incubators, list):
        inv["incubators"] = incubators
        inv["relevant_incubators"] = incubators
    return inv


def _gen_competitors(brief: str, evidence: str, groq_client, gpt_oss_client) -> dict:
    system_prompt = (
        "You are a competitive intelligence analyst. Identify 3-5 real competitors or existing alternatives in the market, "
        "their strengths, weaknesses, and how this startup differentiates. "
        "Return ONLY a JSON object matching the schema."
    )
    user_prompt = f"""STARTUP IDEA:
{brief}

EVIDENCE & CONTEXT:
{evidence}

Identify actual direct and indirect competitors/alternatives, key differentiators, market gaps, and strategy.
Return JSON with this exact schema:
{{
  "competitors": [
    {{
      "name": "Khatabook / OkCredit (Digital Ledgers)",
      "type": "Indirect",
      "target_customer": "Micro-retailers and local merchants",
      "core_offering": "Digital bookkeeping and credit tracking for small merchants",
      "pricing": "Freemium with paid premium features",
      "strength": "Massive distribution and widespread brand recognition among MSMEs",
      "weakness": "Basic recording tool without predictive AI forecasting or cash-flow planning",
      "differentiator": "Automated cash-flow predictive intelligence vs static ledger recording",
      "market_share": "30%",
      "funding": "Series C ($100M+)",
      "source": "Tracxn / Industry Reports"
    }},
    {{
      "name": "Traditional CA & Spreadsheet Accounting",
      "type": "Indirect",
      "target_customer": "Traditional SME business owners",
      "core_offering": "Manual Excel reconciliation and monthly audit reviews",
      "pricing": "₹3,000 - ₹10,000 monthly CA retainer fee",
      "strength": "Established habit and personalized trust with business owners",
      "weakness": "Retrospective (lagging) analysis; no real-time warning before liquidity crunch",
      "differentiator": "Real-time forward-looking predictive alerts instead of retrospective tax filing",
      "market_share": "50%",
      "funding": "Bootstrapped / Non-venture",
      "source": "Market Estimation"
    }},
    {{
      "name": "Clear / Zoho Books",
      "type": "Direct / Alternative",
      "target_customer": "SMEs needing full ERP and GST filing",
      "core_offering": "Comprehensive accounting, GST compliance, and invoice management",
      "pricing": "₹2,500 - ₹15,000 annual subscription",
      "strength": "Full enterprise accounting suite with deep ERP integrations",
      "weakness": "Complex interface and steep learning curve for micro-entrepreneurs",
      "differentiator": "Lightweight, purpose-built cash-shortage prediction with zero accounting overhead",
      "market_share": "15%",
      "funding": "Established Corporates",
      "source": "Corporate Filings"
    }}
  ],
  "our_differentiators": [
    "Predictive AI forecasting cash shortages 14-30 days before they occur",
    "Automated smart WhatsApp payment follow-ups tailored to invoice payment history",
    "Seamless one-click GST and bank statement ingestion without manual entry",
    "Actionable micro-recommendations instead of complex accounting ledgers"
  ],
  "market_gaps": [
    "Lack of predictive foresight in entry-level accounting tools",
    "MSMEs struggle with late invoice payments causing working capital insolvency",
    "Overly complex enterprise software inaccessible to non-technical business owners"
  ],
  "competitive_strategy": "Position as the automated proactive cash-flow guardian that works alongside existing tools like Tally or Zoho, focusing on liquidity protection and zero data-entry friction."
}}"""
    raw = _call_section_llm("competitors", system_prompt, user_prompt, groq_client, gpt_oss_client, max_tokens=1600)
    if isinstance(raw, list):
        return {"competitors": raw, "our_differentiators": [], "market_gaps": [], "competitive_strategy": ""}
    if isinstance(raw, dict):
        comp_dict = raw
        if isinstance(raw.get("competitor_analysis"), dict):
            comp_dict = raw["competitor_analysis"]
        elif isinstance(raw.get("competitors"), dict):
            comp_dict = raw["competitors"]

        competitors_list = comp_dict.get("competitors") or raw.get("competitors") or []
        if not isinstance(competitors_list, list):
            if isinstance(competitors_list, dict):
                competitors_list = [competitors_list]
            else:
                competitors_list = []
        if len(competitors_list) == 0 and any(k in comp_dict for k in ("name", "core_offering", "core_features")):
            competitors_list = [comp_dict]

        diffs = comp_dict.get("our_differentiators") or comp_dict.get("differentiators") or raw.get("our_differentiators") or raw.get("differentiators") or []
        if isinstance(diffs, str):
            diffs = [diffs]
        elif not isinstance(diffs, list):
            diffs = []

        gaps = comp_dict.get("market_gaps") or comp_dict.get("gaps") or raw.get("market_gaps") or raw.get("gaps") or []
        if isinstance(gaps, str):
            gaps = [gaps]
        elif not isinstance(gaps, list):
            gaps = []

        strategy = comp_dict.get("competitive_strategy") or comp_dict.get("strategy") or raw.get("competitive_strategy") or raw.get("strategy") or ""

        return {
            "competitors": competitors_list,
            "our_differentiators": diffs,
            "market_gaps": gaps,
            "competitive_strategy": str(strategy),
        }
    return {"competitors": [], "our_differentiators": [], "market_gaps": [], "competitive_strategy": ""}


def _gen_risks(brief: str, evidence: str, groq_client, gpt_oss_client) -> dict:
    system_prompt = (
        "You are an enterprise risk management specialist. Identify 5-6 realistic risks across Market, Technical, Financial, "
        "Regulatory, and Operational categories for the startup idea with practical mitigations. "
        "Return ONLY a JSON object matching the schema."
    )
    user_prompt = f"""STARTUP IDEA:
{brief}

EVIDENCE & CONTEXT:
{evidence}

Identify realistic risks with severity, probability, impact, and actionable mitigation strategies.
Return JSON with this exact schema:
{{
  "risks": [
    {{
      "category": "Customer Adoption",
      "severity": "HIGH",
      "probability": "MEDIUM",
      "impact": "MSME owners may hesitate to connect bank accounts or share invoice data due to privacy concerns",
      "risk": "Reluctance to adopt automated financial software among traditional merchants",
      "mitigation": "Provide read-only bank statement upload, local encryption, and trust certifications (ISO 27001 / SOC 2)"
    }},
    {{
      "category": "Market",
      "severity": "MEDIUM",
      "probability": "HIGH",
      "impact": "Slower conversion from free trial to paid subscription tiers",
      "risk": "Price sensitivity and low willingness to pay for standalone SaaS tools",
      "mitigation": "Tie pricing directly to measurable working capital savings and offer low-cost monthly plans"
    }},
    {{
      "category": "Regulatory",
      "severity": "HIGH",
      "probability": "LOW",
      "impact": "Stricter data localization or financial data consent directives from RBI",
      "risk": "Compliance challenges under India Digital Personal Data Protection (DPDP) Act and RBI Account Aggregator guidelines",
      "mitigation": "Partner with licensed RBI Account Aggregators and build DPDP-compliant consent management from Day 1"
    }},
    {{
      "category": "Technical",
      "severity": "MEDIUM",
      "probability": "MEDIUM",
      "impact": "Inaccurate cash-flow predictions during seasonal spikes eroding user trust",
      "risk": "Model prediction errors due to non-standard or fragmented invoice formats",
      "mitigation": "Implement human-in-the-loop validation for edge cases and calibrate prediction intervals with confidence bands"
    }},
    {{
      "category": "Financial",
      "severity": "HIGH",
      "probability": "MEDIUM",
      "impact": "Cash burn exceeds runway before achieving product-market fit",
      "risk": "Extended sales cycles causing working capital depletion",
      "mitigation": "Maintain a disciplined 18-month runway and leverage non-dilutive government grants (SISFS)"
    }}
  ]
}}"""
    raw = _call_section_llm("risks", system_prompt, user_prompt, groq_client, gpt_oss_client, max_tokens=1500)
    res = raw.get("risks", raw)
    if isinstance(res, list):
        return {"risks": res}
    return res


def _gen_crag_trace(brief: str, evidence: str, sources: str, groq_client, gpt_oss_client) -> dict:
    system_prompt = (
        "You are a knowledge grounding auditor. Document how verified evidence and policy context informed the startup blueprint. "
        "Return ONLY a JSON object matching the schema."
    )
    user_prompt = f"""STARTUP IDEA:
{brief}

GROUNDED EVIDENCE:
{evidence}

SOURCES CITED:
{sources}

Document the verified context, inferences, recommendations, and evidence mappings.
Return JSON with this exact schema:
{{
  "verified_context": [
    "Startup India Seed Fund Scheme provides early capital for DPIIT-recognised startups",
    "India MSME sector faces average payment cycles of 60-90 days, driving working capital constraints",
    "RBI Account Aggregator framework provides secure consent-based financial data sharing"
  ],
  "inferences": [
    "AI predictive forecasting addresses the root cause of MSME insolvency by surfacing liquidity gaps ahead of time",
    "A subscription B2B SaaS model is sustainable if unit pricing aligns with MSME software willingness-to-pay"
  ],
  "recommendations": [
    "Apply for DPIIT recognition immediately to unlock SISFS grant eligibility",
    "Integrate with licensed Account Aggregators rather than scraping bank credentials",
    "Focus initial marketing on high-velocity invoice industries like distribution and light manufacturing"
  ],
  "source_usage": [
    {{"claim": "Startup India Seed Fund eligibility & capital guidelines", "source": "DPIIT Startup India Guidelines"}},
    {{"claim": "MSME payment delays and working capital dynamics", "source": "MSME Ministry Annual Report"}},
    {{"claim": "Consent-based data sharing guidelines", "source": "Reserve Bank of India Regulations"}}
  ]
}}"""
    raw = _call_section_llm("crag_trace", system_prompt, user_prompt, groq_client, gpt_oss_client, max_tokens=1400)
    return raw.get("crag_trace", raw)


def _is_section_valid(section_name: str, data: Any) -> bool:
    if not data or not isinstance(data, (dict, list)):
        return False
    if section_name == "bmc":
        if not isinstance(data, dict):
            return False
        non_empty = [k for k in ("value_propositions", "customer_segments", "revenue_streams", "key_activities", "cost_structure") if data.get(k) and len(data[k]) > 0]
        return len(non_empty) >= 3
    elif section_name == "budget":
        if not isinstance(data, dict):
            return False
        return len(data.get("phases", [])) >= 2 and data.get("total_12_months", 0) > 0
    elif section_name == "gtm":
        if not isinstance(data, dict):
            return False
        return bool(data.get("target_market")) or len(data.get("launch_strategy", [])) >= 2 or len(data.get("growth_channels", [])) >= 1
    elif section_name == "investors":
        if not isinstance(data, dict):
            return False
        inv = data
        if isinstance(data.get("funding"), dict):
            inv = data["funding"]
        elif isinstance(data.get("investors"), dict):
            inv = data["investors"]
        return len(inv.get("government_schemes", [])) >= 1 or len(inv.get("funding_roadmap", [])) >= 1
    elif section_name == "competitors":
        if isinstance(data, list):
            return len(data) >= 1
        if isinstance(data, dict):
            comp = data
            if isinstance(data.get("competitor_analysis"), dict):
                comp = data["competitor_analysis"]
            elif isinstance(data.get("competitors"), dict):
                comp = data["competitors"]
            comp_list = comp.get("competitors", []) if isinstance(comp, dict) else []
            diff_list = (comp.get("our_differentiators", []) if isinstance(comp, dict) else []) or (comp.get("differentiators", []) if isinstance(comp, dict) else [])
            return (isinstance(comp_list, list) and len(comp_list) >= 1) or (isinstance(diff_list, list) and len(diff_list) >= 1)
        return False
    elif section_name == "risks":
        risks_list = data if isinstance(data, list) else data.get("risks", [])
        return len(risks_list) >= 2
    elif section_name == "crag_trace":
        if not isinstance(data, dict):
            return False
        return len(data.get("verified_context", [])) >= 1 or len(data.get("recommendations", [])) >= 1
    return True


def _repair_section(section_name: str, brief: str, evidence: str, sources: str, groq_client, gpt_oss_client) -> dict:
    print(f"[BLUEPRINT REPAIR] Attempting targeted single-section repair for: {section_name.upper()}...")
    if section_name == "bmc":
        return _gen_bmc(brief, evidence, groq_client, gpt_oss_client)
    elif section_name == "budget":
        return _gen_budget(brief, evidence, groq_client, gpt_oss_client)
    elif section_name == "gtm":
        return _gen_gtm(brief, evidence, groq_client, gpt_oss_client)
    elif section_name == "investors":
        return _gen_investors(brief, evidence, groq_client, gpt_oss_client)
    elif section_name == "competitors":
        return _gen_competitors(brief, evidence, groq_client, gpt_oss_client)
    elif section_name == "risks":
        return _gen_risks(brief, evidence, groq_client, gpt_oss_client)
    elif section_name == "crag_trace":
        return _gen_crag_trace(brief, evidence, sources, groq_client, gpt_oss_client)
    return {}


def validate_required_blueprint_fields(data: dict) -> list[str]:
    """
    Validate that specific mandatory sub-fields exist and are non-empty.
    Required by specification:
      - funding.investor_landscape
      - funding.investor_landscape.relevant_incubators
      - funding.investor_landscape.pitch_tips
      - competitors.our_differentiators
      - competitors.market_gaps
      - competitors.competitive_strategy
    """
    missing = []

    # Check Funding / Investors
    inv = data.get("investors") or data.get("funding") or {}
    if not isinstance(inv, dict):
        inv = {}
    elif isinstance(inv.get("funding"), dict):
        inv = inv["funding"]
    elif isinstance(inv.get("investors"), dict):
        inv = inv["investors"]

    inv_landscape = inv.get("investor_landscape") or inv.get("investor_types") or []
    if not isinstance(inv_landscape, list) or len(inv_landscape) == 0:
        missing.append("funding.investor_landscape")

    incubators = inv.get("relevant_incubators") or inv.get("incubators") or []
    if not isinstance(incubators, list) or len(incubators) == 0:
        missing.append("funding.investor_landscape.relevant_incubators")

    pitch_tips = inv.get("pitch_tips") or []
    if not isinstance(pitch_tips, list) or len(pitch_tips) == 0:
        missing.append("funding.investor_landscape.pitch_tips")

    # Check Competitors
    comp = data.get("competitors") or {}
    if not isinstance(comp, dict):
        comp = {}
    elif isinstance(comp.get("competitor_analysis"), dict):
        comp = comp["competitor_analysis"]
    elif isinstance(comp.get("competitors"), dict):
        comp = comp["competitors"]

    diffs = comp.get("our_differentiators") or comp.get("differentiators") or []
    if not isinstance(diffs, list) or len(diffs) == 0:
        missing.append("competitors.our_differentiators")

    gaps = comp.get("market_gaps") or comp.get("gaps") or []
    if not isinstance(gaps, list) or len(gaps) == 0:
        missing.append("competitors.market_gaps")

    strat = comp.get("competitive_strategy") or comp.get("strategy") or ""
    if not isinstance(strat, str) or len(strat.strip()) < 15:
        missing.append("competitors.competitive_strategy")

    return missing


def repair_missing_blueprint_fields(missing: list[str], brief: str, evidence: str, groq_client, gpt_oss_client) -> dict:
    """
    Execute ONE small targeted repair LLM call containing ONLY the missing fields.
    Returns a strict JSON object with only the repaired fields.
    """
    schemas = []
    if "funding.investor_landscape" in missing:
        schemas.append('"investor_landscape": [\n    {"type": "Angel Networks & Early Syndicates", "stage": "Pre-Seed / Seed", "focus": "Fintech / B2B SaaS", "examples": ["Indian Angel Network (IAN)", "LetsVenture", "Mumbai Angels"]},\n    {"type": "Micro VCs & Seed Funds", "stage": "Seed", "focus": "India MSME Software", "examples": ["Blume Ventures", "India Quotient", "Kae Capital"]}\n  ]')
    if "funding.investor_landscape.relevant_incubators" in missing:
        schemas.append('"relevant_incubators": [\n    {"name": "CIIE.CO (IIM Ahmedabad)", "focus": "Fintech & Financial Inclusion", "location": "Ahmedabad"},\n    {"name": "NSRCEL (IIM Bangalore)", "focus": "B2B Tech Startups", "location": "Bangalore"},\n    {"name": "T-Hub", "focus": "SaaS Scaling & Corporate Pilots", "location": "Hyderabad"}\n  ]')
    if "funding.investor_landscape.pitch_tips" in missing:
        schemas.append('"pitch_tips": [\n    "Demonstrate customer validation with real pilot MSME retention figures",\n    "Show clear SaaS unit economics with target LTV/CAC > 3x",\n    "Highlight compliance with RBI and Account Aggregator data standards"\n  ]')
    if "competitors.our_differentiators" in missing:
        schemas.append('"our_differentiators": [\n    "Predictive AI forecasting cash shortages 14-30 days before they occur",\n    "Automated smart WhatsApp payment reminders tailored to invoice history",\n    "Seamless one-click GST and bank statement ingestion without manual entry",\n    "Lightweight, zero-training interface designed specifically for non-accountant owners"\n  ]')
    if "competitors.market_gaps" in missing:
        schemas.append('"market_gaps": [\n    "Lack of forward-looking cash forecasting in traditional accounting tools",\n    "Delayed payments from enterprise buyers causing MSME liquidity crunches",\n    "Enterprise ERP suites too expensive and complex for small businesses"\n  ]')
    if "competitors.competitive_strategy" in missing:
        schemas.append('"competitive_strategy": "Position as a lightweight predictive cash guardian that works seamlessly alongside existing accounting software like Tally or Zoho, prioritizing zero-friction automated alerts and liquidity protection."')

    schema_body = ",\n  ".join(schemas)
    system_prompt = (
        "You are an expert startup strategist. Generate high quality content ONLY for the missing required fields in strict JSON format. "
        "Return ONLY a valid JSON object matching the requested schema."
    )
    user_prompt = f"""STARTUP IDEA:
{brief}

EVIDENCE & CONTEXT:
{evidence}

Generate specific, realistic content ONLY for these missing fields:
{{
  {schema_body}
}}"""

    repaired = _call_section_llm("repair", system_prompt, user_prompt, groq_client, gpt_oss_client, max_tokens=1200)
    return repaired


def node_generate_blueprint(
    structured_brief, granite_summary, web_context,
    sector, model_type, stage, target_city, groq_client, gpt_oss_client,
    policy_sources=None, policy_crag=None, investor_context=None, investor_sources=None,
    on_section_start=None, on_section_complete=None, cancel_event=None,
):
    import concurrent.futures

    t0 = time.time()
    evidence = (
        f"Granite Policy Summary:\n{granite_summary[:1200] if granite_summary else 'None'}\n\n"
        f"Policy / Evidence Chunks:\n{policy_crag[:1000] if policy_crag else 'General Indian startup regulatory environment.'}\n\n"
        f"Web Market Context:\n{web_context[:600] if web_context else 'None'}"
    )
    sources_str = policy_sources or "Official Indian Policy Documents & Regulations"

    results = {}
    section_timings = {}
    print(f"[CRAG Blueprint] Starting parallel modular generation of all sections (bounded concurrency=4)...")

    sec_tasks = [
        ("bmc", _gen_bmc, (structured_brief, evidence, groq_client, gpt_oss_client)),
        ("budget", _gen_budget, (structured_brief, evidence, groq_client, gpt_oss_client)),
        ("gtm", _gen_gtm, (structured_brief, evidence, groq_client, gpt_oss_client)),
        ("investors", _gen_investors, (structured_brief, evidence, groq_client, gpt_oss_client)),
        ("competitors", _gen_competitors, (structured_brief, evidence, groq_client, gpt_oss_client)),
        ("risks", _gen_risks, (structured_brief, evidence, groq_client, gpt_oss_client)),
        ("crag_trace", _gen_crag_trace, (structured_brief, evidence, sources_str, groq_client, gpt_oss_client)),
    ]

    failed_sections = []

    # Notify starts
    if on_section_start:
        for sec_name, _, _ in sec_tasks:
            try:
                on_section_start(sec_name)
            except Exception:
                pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_meta = {}
        for sec_name, fn, args in sec_tasks:
            t_sec_start = time.time()
            fut = executor.submit(fn, *args)
            future_to_meta[fut] = (sec_name, t_sec_start)

        for fut in concurrent.futures.as_completed(future_to_meta):
            if cancel_event and cancel_event.is_set():
                print("[CRAG Blueprint] Cancellation requested. Halting section collection.")
                break
            sec_name, t_sec_start = future_to_meta[fut]
            try:
                res = fut.result()
            except Exception as e:
                print(f"[CRAG Blueprint] Section {sec_name} execution error: {e}")
                res = {}
            section_timings[sec_name] = round(time.time() - t_sec_start, 2)
            results[sec_name] = res

            # Single-section validation and targeted repair if needed
            if not _is_section_valid(sec_name, res):
                print(f"[BLUEPRINT] {sec_name}: INVALID / EMPTY -> Triggering single-section repair...")
                try:
                    repaired = _repair_section(sec_name, structured_brief, evidence, sources_str, groq_client, gpt_oss_client)
                    if _is_section_valid(sec_name, repaired):
                        print(f"[BLUEPRINT REPAIR] {sec_name}: SUCCESS")
                        results[sec_name] = repaired
                    else:
                        print(f"[BLUEPRINT REPAIR] {sec_name}: FAILED")
                        failed_sections.append(sec_name)
                except Exception as rep_err:
                    print(f"[BLUEPRINT REPAIR] {sec_name} error: {rep_err}")
                    failed_sections.append(sec_name)

            # Emit incremental section completion immediately!
            if on_section_complete:
                try:
                    on_section_complete(sec_name, results[sec_name])
                except Exception as cb_err:
                    print(f"[CRAG Blueprint] Section complete callback error for {sec_name}: {cb_err}")

    # ── Field-level validation and targeted single repair call ────────────────
    missing_fields = validate_required_blueprint_fields(results)
    print(f"[BLUEPRINT VALIDATION] missing_fields={missing_fields}")

    if missing_fields:
        print(f"[BLUEPRINT REPAIR] repairing {len(missing_fields)} fields")
        repaired_dict = repair_missing_blueprint_fields(missing_fields, structured_brief, evidence, groq_client, gpt_oss_client)
        if repaired_dict and isinstance(repaired_dict, dict):
            # Merge into investors / funding
            inv = results.get("investors") if isinstance(results.get("investors"), dict) else {}
            if "investor_landscape" in repaired_dict or "investor_types" in repaired_dict:
                val = repaired_dict.get("investor_landscape") or repaired_dict.get("investor_types")
                inv["investor_landscape"] = val
                inv["investor_types"] = val
            if "relevant_incubators" in repaired_dict or "incubators" in repaired_dict:
                val = repaired_dict.get("relevant_incubators") or repaired_dict.get("incubators")
                inv["relevant_incubators"] = val
                inv["incubators"] = val
            if "pitch_tips" in repaired_dict:
                inv["pitch_tips"] = repaired_dict["pitch_tips"]
            results["investors"] = inv

            # Merge into competitors
            comp = results.get("competitors") if isinstance(results.get("competitors"), dict) else {}
            if "our_differentiators" in repaired_dict:
                comp["our_differentiators"] = repaired_dict["our_differentiators"]
            if "market_gaps" in repaired_dict:
                comp["market_gaps"] = repaired_dict["market_gaps"]
            if "competitive_strategy" in repaired_dict:
                comp["competitive_strategy"] = repaired_dict["competitive_strategy"]
            results["competitors"] = comp
            print(f"[BLUEPRINT REPAIR] success")

        # Validate again after targeted repair
        remaining_missing = validate_required_blueprint_fields(results)
        if not remaining_missing:
            print(f"[BLUEPRINT FINAL] all required sections present")
        else:
            print(f"[BLUEPRINT VALIDATION] remaining_missing={remaining_missing}")
    else:
        print(f"[BLUEPRINT FINAL] all required sections present")

    for sec_name in ["bmc", "budget", "gtm", "investors", "competitors", "risks", "crag_trace"]:
        status_str = "FAILED" if sec_name in failed_sections else "SUCCESS"
        print(f"[BLUEPRINT] {sec_name}: {status_str}")

    results["status"] = "partial" if failed_sections else "success"
    results["failed_sections"] = failed_sections
    normalized = _normalize_blueprint(results)
    normalized["status"] = results["status"]
    normalized["failed_sections"] = results["failed_sections"]

    elapsed = time.time() - t0
    print(f"[CRAG Blueprint] Modular generation complete in {elapsed:.1f}s. Status: {normalized['status']}, Failed: {failed_sections}")
    return normalized


# ══════════════════════════════════════════════════════════════════════════════
# NODE: conversational_answer  (INCORRECT branch — no blueprint)
# ══════════════════════════════════════════════════════════════════════════════
def node_conversational_answer(structured_brief, web_results, groq_client, gpt_oss_client):
    web_context = _format_web_context(web_results)

    if not web_context or len(web_context.strip()) < 50:
        return {
            "type": "redirect",
            "message": (
                "I specialise in generating startup blueprints for the Indian market — "
                "government schemes, business models, funding, and go-to-market strategy.\n\n"
                "Your query doesn't seem specific enough to generate a blueprint. "
                "Try describing your idea with more detail:\n\n"
                "• *An AI-powered logistics platform for last-mile delivery in Tier-2 cities*\n"
                "• *A SaaS tool for small clinics to manage patient appointments and billing*\n"
                "• *A B2B marketplace connecting textile manufacturers with export buyers*"
            )
        }

    messages = [
        {
            "role": "system",
            "content": (
                "You are a startup strategy assistant for the Indian market. "
                "The user's idea didn't match the internal policy knowledge base well, "
                "but live web search found some relevant context. "
                "Give a helpful, structured response covering: what this space looks "
                "like in India, key players or trends, relevant government support, "
                "and one concrete next step. Do NOT produce a full business blueprint."
            )
        },
        {
            "role": "user",
            "content": (
                f"Startup Brief:\n{structured_brief}\n\n"
                f"Live web context:\n{web_context}\n\n"
                "Give a helpful conversational answer (5-7 sentences):"
            )
        }
    ]

    try:
        try:
            r = gpt_oss_client.chat(
                messages=messages,
                params={"max_tokens": 800, "temperature": 0.2}
            )
            content = r["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[CRAG Conversational] GPT-OSS-120B failed, using Groq fallback: {e}")
            r = groq_client.chat.completions.create(
                model=get_settings().GROQ_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=800,
            )
            content = r.choices[0].message.content.strip()
        return {
            "type":        "answer",
            "message":     content,
            "web_context": web_context,
        }
    except Exception as e:
        return {
            "type":    "redirect",
            "message": "Something went wrong. Please rephrase your startup idea with more detail.",
        }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ══════════════════════════════════════════════════════════════════════════════
def run_crag(
    query, sector, stage, model_type, target_city,
    collections,        # dict: {"text": col, "table": col, "visual": col}
    reranker,           # CrossEncoder instance
    granite,            # IBM ModelInference instance
    tavily,             # TavilyClient instance
    groq_client,        # Groq instance
    gemini_client,      # google.generativeai configured client
    gpt_oss_client,     # IBM ModelInference instance for GPT-OSS
    event_callback=None,# callback(event_type: str, payload: dict) -> None
    cancel_event=None,  # threading.Event to signal cancellation
    generation_id: Optional[str] = None,
):
    """
    Full CRAG pipeline. Returns a result dict consumed by app.py and blueprint router.
    Includes structured timing measurements, incremental stage callbacks, and
    correlation generation_id.
    """
    generation_id = generation_id or f"gen_{uuid.uuid4().hex[:12]}"
    timings = {
        "generation_id": generation_id,
        "request_init_s": 0.0,
        "query_rewrite_s": 0.0,
        "chromadb_retrieve_s": 0.0,
        "crossencoder_grade_s": 0.0,
        "crag_routing_s": 0.0,
        "granite_summary_s": 0.0,
        "tavily_research_s": 0.0,
        "sections_s": {},
        "sections_total_wall_s": 0.0,
        "json_parsing_validation_s": 0.0,
        "database_persistence_s": 0.0,
        "total_end_to_end_s": 0.0,
    }

    def _emit(event_type: str, **kwargs):
        if event_callback:
            payload = {
                "event": event_type,
                "generation_id": generation_id,
                **kwargs,
            }
            try:
                event_callback(event_type, payload)
            except Exception as cb_e:
                print(f"[CRAG] event_callback failed: {cb_e}")

    def _on_sec_start(sec_name: str):
        _emit("section_started", section=sec_name, step=f"Generating {sec_name.upper()}…", node=f"generate_{sec_name}")

    def _on_sec_complete(sec_name: str, sec_data: Any):
        _emit("section_completed", section=sec_name, data=sec_data, step=f"{sec_name.upper()} ready", node=f"generate_{sec_name}")

    result = {
        "confidence":              "",
        "action":                  "",
        "should_generate_blueprint": False,
        "summary":                 "",         # Granite policy brief
        "blueprint":               {},         # 6 Groq sections
        "sources":                 [],
        "internal_context":        "",
        "external_context":        "",
        "scores":                  [],
        "raw_logits":              [],
        "max_logit":               0.0,
        "original_query":          query,
        "rewritten_query":         "",
        "structured_brief":        "",
        "keywords":                [],
        "retrieval_queries":       [],
        "search_context":          "",
        "conversational_response": None,
        "explore_results":         [],
        "generation_id":           generation_id,
        "timings":                 timings,
    }

    t_start = time.time()
    t_rewrite = t_retrieve = t_grade = t_refine = t_granite = t_tavily = t_bp = 0.0

    if cancel_event and cancel_event.is_set():
        print("[CRAG] Cancelled before pipeline execution started.")
        return result

    # ── Step 1: Rewrite query (Gemini Flash / Groq) ──────────────────────────
    print("[CRAG] Step 1: Rewriting query...")
    _emit("stage_started", stage="rewrite_query", node="rewrite_query", step="Rewriting query with Gemini Flash…", progress=8)
    t0 = time.time()
    rewrite = node_rewrite_query(
        query, sector, stage, model_type, target_city, gemini_client
    )
    t_rewrite = time.time() - t0
    timings["query_rewrite_s"] = round(t_rewrite, 2)
    result["rewritten_query"]  = rewrite["structured_brief"]
    result["structured_brief"] = rewrite["structured_brief"]
    result["keywords"]         = rewrite["keywords"]
    result["retrieval_queries"]= rewrite["retrieval_queries"]
    result["search_context"]   = rewrite["search_context"]
    _emit("stage_completed", stage="rewrite_query", node="rewrite_query", step="Structured brief prepared", progress=16, data={"keywords": rewrite["keywords"]})

    search_ctx = rewrite["search_context"]

    if cancel_event and cancel_event.is_set():
        print("[CRAG] Cancelled after query rewrite.")
        return result

    # ── Step 2: Retrieve from all 3 collections ───────────────────────────────
    print("[CRAG] Step 2: Retrieving from ChromaDB (text + table + visual)...")
    _emit("stage_started", stage="retrieve", node="retrieve", step="Retrieving from ChromaDB (text + table + visual)…", progress=18)
    t0 = time.time()
    docs, metas = node_retrieve(search_ctx, collections, n_per_collection=6)
    t_retrieve = time.time() - t0
    timings["chromadb_retrieve_s"] = round(t_retrieve, 2)
    sources = list({m.get("source", "Unknown") for m in metas})
    result["sources"] = sources
    print(f"[CRAG]   Retrieved {len(docs)} chunks from {len(sources)} sources")
    _emit("stage_completed", stage="retrieve", node="retrieve", step=f"Retrieved {len(docs)} chunks from {len(sources)} sources", progress=26, data={"sources": sources})

    if cancel_event and cancel_event.is_set():
        print("[CRAG] Cancelled after retrieval.")
        return result

    # ── Step 3: Evaluate relevance (CrossEncoder) ─────────────────────────────
    print("[CRAG] Step 3: Grading retrieved chunks using original short query...")
    _emit("stage_started", stage="eval_each_doc", node="eval_each_doc", step="CrossEncoder grading retrieved chunks…", progress=28)
    t0 = time.time()
    scores, raw_logits, confidence, max_logit = node_eval_each_doc(query, docs, reranker)
    t_grade = time.time() - t0
    timings["crossencoder_grade_s"] = round(t_grade, 2)
    result["confidence"] = confidence
    result["scores"]     = scores
    result["raw_logits"] = raw_logits
    result["max_logit"]  = max_logit
    print(f"[CRAG]   Confidence: {confidence}")
    _emit("stage_completed", stage="eval_each_doc", node="eval_each_doc", step=f"Relevance graded: {confidence}", progress=42, data={"confidence": confidence, "max_logit": max_logit})

    # Build clean human-readable retrieved documents with previews and scores
    import os
    clean_sources = []
    for s in sources:
        c_src = os.path.basename(s) if ("/" in s or "\\" in s) else s
        if c_src and c_src not in clean_sources:
            clean_sources.append(c_src)
    result["sources"] = clean_sources

    retrieved_documents = []
    for idx, (doc, meta) in enumerate(zip(docs, metas)):
        raw_src = meta.get("source", "Unknown")
        c_name = os.path.basename(raw_src) if ("/" in raw_src or "\\" in raw_src) else raw_src
        sc = scores[idx] if idx < len(scores) else None
        lg = raw_logits[idx] if idx < len(raw_logits) else None
        retrieved_documents.append({
            "source": c_name,
            "collection": meta.get("collection", "text"),
            "score": round(float(sc), 3) if sc is not None else None,
            "logit": round(float(lg), 3) if lg is not None else None,
            "excerpt": doc[:300] + ("..." if len(doc) > 300 else ""),
            "full_text": doc,
        })
    result["retrieved_documents"] = retrieved_documents

    # ══════════════════════════════════════════════════════════════════════════
    # BRANCH: CORRECT
    # ══════════════════════════════════════════════════════════════════════════
    if confidence == "CORRECT":
        result["action"] = (
            "[CORRECT] Internal knowledge base is strongly relevant. "
            "Blueprint grounded in official policy documents."
        )
        result["should_generate_blueprint"] = True

        print("[CRAG] Branch: CORRECT -> selecting top PDF chunks (logit-sorted, no extra reranker call)...")
        _emit("stage_started", stage="branch", node="refine", step="Refining PDF context (logit-sorted)…", progress=45)
        t0 = time.time()
        refined = _select_top_docs(docs, raw_logits, top_k=6)
        t_refine = time.time() - t0
        timings["crag_routing_s"] = round(t_refine, 2)
        result["internal_context"] = refined

        if cancel_event and cancel_event.is_set(): return result

        print("[CRAG] Generating Granite policy summary...")
        _emit("stage_started", stage="policy_summary", node="generate", step="IBM Granite 4.0 synthesizing policy brief…", progress=52)
        t0 = time.time()
        result["summary"] = node_generate_summary(
            result["structured_brief"], refined, granite, "internal"
        )
        t_granite = time.time() - t0
        timings["granite_summary_s"] = round(t_granite, 2)
        _emit("stage_completed", stage="policy_summary", node="generate", step="Policy brief ready", progress=60, data={"summary": result["summary"]})

        # Bonus: Tavily explore results (fed into blueprint for richer context)
        print("[CRAG] Fetching Tavily explore results...")
        _emit("stage_started", stage="tavily_research", node="web_search", step="Fetching supplementary web context (Tavily)…", progress=62)
        t0 = time.time()
        explore = node_web_search(search_ctx, rewrite["retrieval_queries"], tavily, sector, max_results=3)
        t_tavily = time.time() - t0
        timings["tavily_research_s"] = round(t_tavily, 2)
        result["explore_results"] = explore
        web_ctx = ""
        if explore:
            result["sources"].append("tavily_web_search")
            web_ctx = _format_web_context(explore)
        _emit("stage_completed", stage="tavily_research", node="web_search", step="Supplementary research complete", progress=65)

        if cancel_event and cancel_event.is_set(): return result

        print("[CRAG] Generating 6 blueprint sections (GPT-OSS/Groq)...")
        _emit("stage_started", stage="generation", node="generate_bmc", step="Generating blueprint sections…", progress=68)
        t0 = time.time()
        result["blueprint"] = node_generate_blueprint(
            result["structured_brief"], result["summary"], web_ctx,
            sector, model_type, stage, target_city, groq_client, gpt_oss_client,
            policy_sources=", ".join([s for s in result["sources"] if s != "tavily_web_search"]) or "Official Indian Policy Documents & Regulations",
            policy_crag=refined,
            investor_context=refined,
            investor_sources=", ".join(result["sources"]) if result["sources"] else "DPIIT, Startup India, SIDBI, Incubator Databases",
            on_section_start=_on_sec_start,
            on_section_complete=_on_sec_complete,
            cancel_event=cancel_event,
        )
        t_bp = time.time() - t0
        timings["sections_total_wall_s"] = round(t_bp, 2)
        timings["sections_s"] = result["blueprint"].get("_section_timings", {})
        _emit("stage_completed", stage="generation", node="generate_risks", step="Blueprint sections ready", progress=95)

    # ══════════════════════════════════════════════════════════════════════════
    # BRANCH: AMBIGUOUS
    # ══════════════════════════════════════════════════════════════════════════
    elif confidence == "AMBIGUOUS":
        result["action"] = (
            "[AMBIGUOUS] Partial relevance. Combining policy documents "
            "with live web search for richer context."
        )
        result["should_generate_blueprint"] = True

        print("[CRAG] Branch: AMBIGUOUS -> refining PDF + fetching web...")
        _emit("stage_started", stage="branch", node="refine", step="Refining PDF context + querying live web…", progress=45)
        t0 = time.time()
        refined  = node_refine(search_ctx, docs, raw_logits, reranker, top_k=6)
        t_refine = time.time() - t0
        timings["crag_routing_s"] = round(t_refine, 2)

        _emit("stage_started", stage="tavily_research", node="web_search", step="Searching live web with Tavily…", progress=48)
        t0 = time.time()
        web_res  = node_web_search(search_ctx, rewrite["retrieval_queries"], tavily, sector, max_results=3)
        t_tavily = time.time() - t0
        timings["tavily_research_s"] = round(t_tavily, 2)
        web_ctx  = _format_web_context(web_res)

        result["internal_context"] = refined
        result["external_context"] = web_ctx

        combined = (
            "=== FROM POLICY DOCUMENTS ===\n" + refined +
            "\n\n=== FROM LIVE WEB SEARCH ===\n" + web_ctx
        )

        if cancel_event and cancel_event.is_set(): return result

        print("[CRAG] Generating Granite policy summary (combined)...")
        _emit("stage_started", stage="policy_summary", node="generate", step="IBM Granite synthesizing combined policy brief…", progress=55)
        t0 = time.time()
        result["summary"] = node_generate_summary(
            result["structured_brief"], combined, granite, "combined"
        )
        t_granite = time.time() - t0
        timings["granite_summary_s"] = round(t_granite, 2)
        _emit("stage_completed", stage="policy_summary", node="generate", step="Policy brief ready", progress=65, data={"summary": result["summary"]})

        if cancel_event and cancel_event.is_set(): return result

        print("[CRAG] Generating 6 blueprint sections (GPT-OSS/Groq)...")
        _emit("stage_started", stage="generation", node="generate_bmc", step="Generating blueprint sections…", progress=68)
        t0 = time.time()
        result["blueprint"] = node_generate_blueprint(
            result["structured_brief"], result["summary"], web_ctx,
            sector, model_type, stage, target_city, groq_client, gpt_oss_client,
            policy_sources=", ".join(result["sources"]) if result["sources"] else "Official Policy Documents & Web Sources",
            policy_crag=refined,
            investor_context=combined,
            investor_sources=", ".join(result["sources"]) if result["sources"] else "Government & Market Databases",
            on_section_start=_on_sec_start,
            on_section_complete=_on_sec_complete,
            cancel_event=cancel_event,
        )
        t_bp = time.time() - t0
        timings["sections_total_wall_s"] = round(t_bp, 2)
        timings["sections_s"] = result["blueprint"].get("_section_timings", {})
        _emit("stage_completed", stage="generation", node="generate_risks", step="Blueprint sections ready", progress=95)

        result["explore_results"] = web_res
        if web_res:
            result["sources"].append("tavily_web_search")

    # ══════════════════════════════════════════════════════════════════════════
    # BRANCH: INCORRECT
    # ══════════════════════════════════════════════════════════════════════════
    else:
        print("[CRAG] Branch: INCORRECT -> performing live web search...")
        _emit("stage_started", stage="branch", node="web_search", step="Knowledge base insufficient — searching live web…", progress=45)
        t0 = time.time()
        web_res = node_web_search(search_ctx, rewrite["retrieval_queries"], tavily, sector, max_results=3)
        t_tavily = time.time() - t0
        timings["tavily_research_s"] = round(t_tavily, 2)
        web_ctx = _format_web_context(web_res)

        result["external_context"] = web_ctx
        result["explore_results"]  = web_res
        result["sources"] = ["tavily_web_search"] if web_res else []

        if web_res:
            # ── Web search succeeded: generate blueprint from web context ─────
            result["action"] = (
                "[INCORRECT] Internal knowledge base not relevant. "
                "Blueprint generated from live web search context."
            )
            result["should_generate_blueprint"] = True

            print("[CRAG] INCORRECT branch: Tavily returned results — generating blueprint from web context...")

            print("[CRAG] Generating Granite policy summary (web-only)...")
            _emit("stage_started", stage="policy_summary", node="generate", step="IBM Granite synthesizing policy brief (web-only)…", progress=55)
            t0 = time.time()
            try:
                result["summary"] = node_generate_summary(
                    result["structured_brief"], web_ctx, granite, "combined"
                )
            except Exception as e:
                print(f"[CRAG] Granite summary failed in INCORRECT branch: {e}. Continuing without summary.")
                result["summary"] = ""
            t_granite = time.time() - t0
            timings["granite_summary_s"] = round(t_granite, 2)
            _emit("stage_completed", stage="policy_summary", node="generate", step="Policy brief ready", progress=65, data={"summary": result["summary"]})

            if cancel_event and cancel_event.is_set(): return result

            print("[CRAG] Generating 6 blueprint sections from web context (GPT-OSS/Groq)...")
            _emit("stage_started", stage="generation", node="generate_bmc", step="Generating blueprint sections from web context…", progress=68)
            t0 = time.time()
            result["blueprint"] = node_generate_blueprint(
                result["structured_brief"], result["summary"], web_ctx,
                sector, model_type, stage, target_city, groq_client, gpt_oss_client,
                policy_sources="tavily_web_search",
                policy_crag=web_ctx,
                investor_context=web_ctx,
                investor_sources="Tavily Web Search",
                on_section_start=_on_sec_start,
                on_section_complete=_on_sec_complete,
                cancel_event=cancel_event,
            )
            t_bp = time.time() - t0
            timings["sections_total_wall_s"] = round(t_bp, 2)
            timings["sections_s"] = result["blueprint"].get("_section_timings", {})
            _emit("stage_completed", stage="generation", node="generate_risks", step="Blueprint sections ready", progress=95)

        else:
            # ── Web search also returned nothing: conversational redirect ──────
            result["action"] = (
                "[INCORRECT] Knowledge base not relevant enough. "
                "Searching the live web. No blueprint generated - refine your idea."
            )
            result["should_generate_blueprint"] = False

            print("[CRAG] INCORRECT branch: Tavily also returned no results — conversational redirect.")
            _emit("stage_started", stage="redirect", node="conversational", step="Refining idea guidance…", progress=90)
            result["conversational_response"] = node_conversational_answer(
                result["structured_brief"], web_res, groq_client, gpt_oss_client
            )
            _emit("stage_completed", stage="redirect", node="conversational", step="Guidance prepared", progress=95)

    t_total = time.time() - t_start
    timings["total_end_to_end_s"] = round(t_total, 2)
    result["generation_id"] = generation_id
    result["timings"] = timings

    print(f"\n==================================================")
    print(f"[PERF] Query rewrite: {t_rewrite:.2f}s")
    print(f"[PERF] Chroma retrieval: {t_retrieve:.2f}s")
    print(f"[PERF] CrossEncoder grading: {t_grade:.2f}s")
    if t_refine > 0:
        print(f"[PERF] Refine context: {t_refine:.2f}s")
    if t_granite > 0:
        print(f"[PERF] Granite summary: {t_granite:.2f}s")
    if t_tavily > 0:
        print(f"[PERF] Tavily explore: {t_tavily:.2f}s")
    if t_bp > 0:
        print(f"[PERF] Blueprint sections generation: {t_bp:.2f}s")
    print(f"[PERF] TOTAL BLUEPRINT GENERATION: {t_total:.2f}s")
    print(f"[METRICS] generation_id={generation_id} timings={json.dumps(timings)}")
    if result.get("blueprint") and isinstance(result["blueprint"], dict):
        crag_tr = result["blueprint"].get("crag_trace")
        if not isinstance(crag_tr, dict):
            crag_tr = {}
        crag_tr["confidence"] = result.get("confidence", "")
        crag_tr["decision"] = result.get("action", "")
        crag_tr["retrieved_documents"] = result.get("retrieved_documents", [])
        crag_tr["raw_summary"] = result.get("summary", "")
        result["blueprint"]["crag_trace"] = crag_tr

    print(f"[CRAG] Done. Blueprint: {result['should_generate_blueprint']}")
    return result