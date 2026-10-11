"""
deep_research_db.py — psycopg2 persistence for deep research cache.
Matches the same pattern as history_db.py exactly.
"""

import psycopg2
import psycopg2.extras
import json
import os


def _get_secret(key: str, default: str = None) -> str:
    val = os.environ.get(key)
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


def _conn():
    return psycopg2.connect(
        host=_get_secret("DB_HOST"),
        port=_get_secret("DB_PORT", "5432"),
        database=_get_secret("DB_NAME"),
        user=_get_secret("DB_USER"),
        password=_get_secret("DB_PASSWORD"),
        sslmode="require",
        connect_timeout=10,
    )


def init_deep_research_table() -> None:
    """Create deep_research table if it doesn't exist, and add report_json column if missing."""
    with _conn() as c:
        cur = c.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS deep_research (
            id              SERIAL PRIMARY KEY,
            blueprint_id    INTEGER UNIQUE REFERENCES blueprints(id) ON DELETE CASCADE,
            user_email      TEXT,
            competitor_data TEXT,
            market_sizing   TEXT,
            swot            TEXT,
            funding         TEXT,
            news_pulse      TEXT,
            sentiment       TEXT,
            report_json     TEXT,
            created_at      TIMESTAMPTZ DEFAULT now()
        );
        """)
        try:
            cur.execute("ALTER TABLE deep_research ADD COLUMN IF NOT EXISTS report_json TEXT;")
        except Exception:
            pass
        c.commit()


def save_deep_research(blueprint_id: int, user_email: str, data: dict) -> bool:
    """Upsert deep research results including full report_json. Returns True on success."""
    try:
        init_deep_research_table()
        with _conn() as c:
            cur = c.cursor()
            cur.execute("""
                INSERT INTO deep_research
                    (blueprint_id, user_email, competitor_data, market_sizing,
                     swot, funding, news_pulse, sentiment, report_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (blueprint_id) DO UPDATE SET
                    competitor_data = EXCLUDED.competitor_data,
                    market_sizing   = EXCLUDED.market_sizing,
                    swot            = EXCLUDED.swot,
                    funding         = EXCLUDED.funding,
                    news_pulse      = EXCLUDED.news_pulse,
                    sentiment       = EXCLUDED.sentiment,
                    report_json     = EXCLUDED.report_json,
                    created_at      = now()
            """, (
                blueprint_id,
                user_email or "",
                json.dumps(data.get("competitor_intelligence", data.get("competitors", {}))),
                json.dumps(data.get("market_landscape", data.get("market_sizing", {}))),
                json.dumps(data.get("critical_analysis", data.get("swot", {}))),
                json.dumps(data.get("funding_landscape", data.get("funding", {}))),
                json.dumps(data.get("market_pulse", {})),
                data.get("news_pulse", {}).get("sentiment", "Neutral") if isinstance(data.get("news_pulse"), dict) else "Neutral",
                json.dumps(data),
            ))
            c.commit()
        return True
    except Exception as e:
        print(f"[deep_research_db] Save failed: {e}")
        return False


def load_deep_research(blueprint_id: int) -> dict | None:
    """Load cached deep research. Returns None if not found."""
    try:
        init_deep_research_table()
        with _conn() as c:
            cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM deep_research WHERE blueprint_id=%s",
                (blueprint_id,)
            )
            row = cur.fetchone()
            if row is None:
                return None
            if row.get("report_json"):
                try:
                    return json.loads(row["report_json"])
                except Exception:
                    pass
            return {
                "competitors":   json.loads(row.get("competitor_data") or "{}"),
                "market_sizing": json.loads(row.get("market_sizing")   or "{}"),
                "swot":          json.loads(row.get("swot")            or "{}"),
                "funding":       json.loads(row.get("funding")         or "{}"),
                "news_pulse":    json.loads(row.get("news_pulse")      or "{}"),
            }
    except Exception as e:
        print(f"[deep_research_db] Load failed: {e}")
        return None