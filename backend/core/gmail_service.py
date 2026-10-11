"""
gmail_service.py — Robust, secure Google OAuth 2.0 and Gmail API client for LOCK IN AI.

Handles:
  1. Google OAuth consent URL generation (offline access, gmail.send scope)
  2. Authorization code exchange & server-side token persistence with scope verification
  3. Automatic token refresh before expiry and tokeninfo scope validation
  4. Sending RFC 2822 MIME emails via Gmail REST API (users.messages.send)
  5. Disconnection and revoked/insufficient scope error handling
"""

import base64
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import logging
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import httpx

from config import get_settings
from lock_in_db import (
    get_gmail_connection,
    save_gmail_connection,
    update_gmail_access_token,
    update_gmail_scopes,
    mark_gmail_connection_revoked,
    disconnect_gmail as db_disconnect_gmail,
    create_agent_action,
)

log = logging.getLogger(__name__)

# Scopes: Least-privilege — Send emails only + profile email for displaying connected account
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_SCOPES = [
    GMAIL_SEND_SCOPE,
    "https://www.googleapis.com/auth/userinfo.email"
]

GOOGLE_AUTH_ENDPOINT  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL  = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL   = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_SEND_ENDPOINT   = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def is_gmail_configured() -> bool:
    """Check if Google OAuth client credentials are configured in settings or environment."""
    settings = get_settings()
    client_id = settings.GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = settings.GOOGLE_CLIENT_SECRET or os.getenv("GOOGLE_CLIENT_SECRET", "")
    return bool(client_id and client_secret)


def build_google_auth_url(user_id: str, state_token: str, redirect_uri: str = None) -> str:
    """
    Constructs the Google OAuth 2.0 consent URL for server-side offline access.
    Requests least-privilege send-only permission (gmail.send) and email identity.
    """
    settings = get_settings()
    client_id = settings.GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
    r_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI

    if not client_id:
        raise ValueError("GOOGLE_CLIENT_ID is not configured. Please set it in .env")

    params = {
        "client_id": client_id,
        "redirect_uri": r_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # Ensures refresh_token is returned
        "state": state_token,
        "include_granted_scopes": "true",
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


async def verify_token_scopes(access_token: str) -> dict:
    """
    Queries Google's tokeninfo endpoint to verify actual granted scopes and token validity.
    Returns: {"valid": bool, "scopes": list[str], "has_send_scope": bool, "email": str, "expires_in": int}
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{GOOGLE_TOKENINFO_URL}?access_token={access_token}")
            if resp.status_code == 200:
                data = resp.json()
                raw_scope = data.get("scope", "")
                granted_scopes = [s for s in raw_scope.split() if s]
                has_send = "https://www.googleapis.com/auth/gmail.send" in granted_scopes
                return {
                    "valid": True,
                    "scopes": granted_scopes,
                    "raw_scope": raw_scope,
                    "has_send_scope": has_send,
                    "email": data.get("email", ""),
                    "expires_in": int(data.get("expires_in", 0)),
                }
            else:
                return {
                    "valid": False,
                    "scopes": [],
                    "raw_scope": "",
                    "has_send_scope": False,
                    "error": resp.text,
                }
    except Exception as e:
        log.warning(f"[GMAIL] Error querying Google tokeninfo: {e}")
        return {"valid": False, "scopes": [], "raw_scope": "", "has_send_scope": False, "error": str(e)}


async def exchange_oauth_code(code: str, redirect_uri: str = None) -> dict:
    """
    Exchanges the authorization code for access and refresh tokens,
    verifies that the required gmail.send scope was actually granted by the user,
    and fetches the user's connected Google email.
    """
    settings = get_settings()
    client_id = settings.GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = settings.GOOGLE_CLIENT_SECRET or os.getenv("GOOGLE_CLIENT_SECRET", "")
    r_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI

    if not client_id or not client_secret:
        raise ValueError("Google OAuth credentials (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) missing.")

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": r_uri,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)
        if resp.status_code != 200:
            log.error(f"[GMAIL] Google token exchange failed: {resp.text}")
            raise RuntimeError(f"Failed to exchange Google OAuth code: {resp.text}")
        
        token_data = resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        raw_scope = token_data.get("scope", "")

        # Verify granted scopes directly from token response or tokeninfo
        scope_info = await verify_token_scopes(access_token)
        if scope_info.get("valid"):
            granted_scopes_str = scope_info.get("raw_scope", raw_scope)
            has_send_scope = scope_info.get("has_send_scope", False)
        else:
            granted_scopes_str = raw_scope
            has_send_scope = "https://www.googleapis.com/auth/gmail.send" in raw_scope

        # Retrieve the connected Google email address
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_resp = await client.get(GOOGLE_USERINFO_URL, headers=headers)
        google_email = ""
        if userinfo_resp.status_code == 200:
            google_email = userinfo_resp.json().get("email", "")
        elif scope_info.get("email"):
            google_email = scope_info.get("email")

        # Determine connection status based on scope verification
        if has_send_scope:
            status = "active"
            last_error = ""
        else:
            status = "reauth_required"
            last_error = "ACCESS_TOKEN_SCOPE_INSUFFICIENT: Missing https://www.googleapis.com/auth/gmail.send scope. User must reconnect and grant Gmail Send permission."
            log.warning(f"[GMAIL] User {google_email} authorized without gmail.send scope. Marking reauth_required.")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expiry": token_expiry,
            "google_email": google_email,
            "granted_scopes": granted_scopes_str,
            "has_send_scope": has_send_scope,
            "scope_verified": True,
            "status": status,
            "last_error": last_error,
        }


async def get_valid_access_token(user_id: str, force_refresh: bool = False, require_send_scope: bool = True) -> str:
    """
    Retrieves a valid access token for the given user, refreshing it if expired or forced.
    Validates that the token possesses the required send scope when require_send_scope is True.
    Raises RuntimeError if credentials are revoked, expired, or missing required scopes.
    """
    conn = get_gmail_connection(user_id)
    if not conn:
        raise RuntimeError(f"No Gmail connection found for user {user_id}.")

    status = conn.get("status")
    if status in ("reauth_required", "revoked", "disconnected"):
        err = conn.get("last_error") or "Gmail reconnection required."
        raise RuntimeError(f"Gmail reauthorization required: {err}")

    access_token = conn.get("access_token")
    refresh_token = conn.get("refresh_token")
    token_expiry = conn.get("token_expiry")
    granted_scopes = conn.get("granted_scopes", "")
    scope_verified = conn.get("scope_verified", False)

    now = datetime.now(timezone.utc)

    # If token exists, is unexpired (> 90s remaining), and not force_refresh:
    token_time_valid = False
    if access_token and token_expiry:
        if isinstance(token_expiry, str):
            try:
                token_expiry = datetime.fromisoformat(token_expiry)
            except Exception:
                token_expiry = now
        if token_expiry.tzinfo is None:
            token_expiry = token_expiry.replace(tzinfo=timezone.utc)

        if token_expiry > now + timedelta(seconds=90):
            token_time_valid = True

    if not force_refresh and token_time_valid:
        # Check scope verification if not yet checked
        if require_send_scope and not scope_verified:
            scope_info = await verify_token_scopes(access_token)
            if scope_info.get("valid"):
                has_send = scope_info.get("has_send_scope", False)
                update_gmail_scopes(
                    user_id=user_id,
                    granted_scopes=scope_info.get("raw_scope", ""),
                    scope_verified=True,
                    status="active" if has_send else "reauth_required",
                    last_error="" if has_send else "ACCESS_TOKEN_SCOPE_INSUFFICIENT: Missing https://www.googleapis.com/auth/gmail.send scope"
                )
                if not has_send:
                    raise RuntimeError("Gmail Send permission (https://www.googleapis.com/auth/gmail.send) is missing. Please reconnect Gmail.")
            else:
                log.warning(f"[GMAIL] Could not verify token scopes: {scope_info.get('error')}")

        return access_token

    # Token expired or forced refresh needed
    if not refresh_token:
        log.warning(f"[GMAIL] No refresh token for user {user_id}. Marking REAUTH_REQUIRED.")
        mark_gmail_connection_revoked(user_id, "reauth_required", "No refresh token available.")
        raise RuntimeError("Gmail token expired and no refresh token available. Please reconnect Gmail.")

    log.info(f"[GMAIL] Refreshing access token via Google OAuth for user {user_id}")
    settings = get_settings()
    client_id = settings.GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = settings.GOOGLE_CLIENT_SECRET or os.getenv("GOOGLE_CLIENT_SECRET", "")

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(GOOGLE_TOKEN_ENDPOINT, data=data)
        if resp.status_code != 200:
            err_msg = resp.text
            log.error(f"[GMAIL] Failed to refresh Google token for user {user_id}: {err_msg}")
            if "invalid_grant" in err_msg or resp.status_code in (400, 401):
                mark_gmail_connection_revoked(user_id, "reauth_required", f"Refresh failed: {err_msg}")
                raise RuntimeError("Gmail authorization was revoked or expired. Please reconnect Gmail.")
            raise RuntimeError(f"Could not refresh Gmail token: {err_msg}")

        refreshed = resp.json()
        new_access_token = refreshed.get("access_token")
        new_expires_in = refreshed.get("expires_in", 3600)
        new_expiry = now + timedelta(seconds=new_expires_in)
        refreshed_scope = refreshed.get("scope", granted_scopes)

        update_gmail_access_token(user_id, new_access_token, new_expiry)

        # Check scope if refreshed response included scope
        if refreshed_scope:
            has_send = "https://www.googleapis.com/auth/gmail.send" in refreshed_scope
            update_gmail_scopes(
                user_id=user_id,
                granted_scopes=refreshed_scope,
                scope_verified=True,
                status="active" if has_send else "reauth_required",
                last_error="" if has_send else "ACCESS_TOKEN_SCOPE_INSUFFICIENT"
            )
            if require_send_scope and not has_send:
                raise RuntimeError("Gmail Send permission is missing. Please reconnect Gmail.")

        log.info(f"[GMAIL] Access token refreshed successfully for user {user_id}")
        return new_access_token


async def send_gmail_email(user_id: str, to_email: str, subject: str, text_body: str, html_body: str = None) -> str:
    """
    Sends an email using the Gmail REST API (users.messages.send) on behalf of the connected user.
    Enforces least-privilege scope check and handles 401/403 with specific diagnostics.
    Returns the sent message ID.
    """
    log.info(f"[GMAIL] Preparing email send for user {user_id} to recipient {to_email}")
    access_token = await get_valid_access_token(user_id, require_send_scope=True)
    conn = get_gmail_connection(user_id)
    sender_email = conn.get("google_email") if conn else "me"

    message = MIMEMultipart("alternative")
    message["to"] = to_email
    message["from"] = sender_email or "me"
    message["subject"] = subject

    # Plain text part
    message.attach(MIMEText(text_body, "plain", "utf-8"))
    
    # HTML part (if provided)
    if html_body:
        message.attach(MIMEText(html_body, "html", "utf-8"))

    raw_bytes = message.as_bytes()
    raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")
    payload = {"raw": raw_b64}

    async with httpx.AsyncClient(timeout=20.0) as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        resp = await client.post(GMAIL_SEND_ENDPOINT, headers=headers, json=payload)
        
        # If access token was rejected (401), attempt an immediate forced token refresh and retry once
        if resp.status_code == 401:
            log.warning(f"[GMAIL] Received 401 Unauthorized for user {user_id}. Attempting single forced token refresh...")
            try:
                fresh_access_token = await get_valid_access_token(user_id, force_refresh=True, require_send_scope=True)
                retry_headers = {
                    "Authorization": f"Bearer {fresh_access_token}",
                    "Content-Type": "application/json",
                }
                resp = await client.post(GMAIL_SEND_ENDPOINT, headers=retry_headers, json=payload)
            except Exception as refresh_err:
                log.error(f"[GMAIL] Forced token refresh failed during 401 retry: {refresh_err}")
                mark_gmail_connection_revoked(user_id, "reauth_required", f"Token expired/revoked: {refresh_err}")
                raise RuntimeError(f"Gmail token expired/revoked: {refresh_err}")

        # Check for 403 Forbidden specifically (Scope Insufficient vs Quota Exceeded)
        if resp.status_code == 403:
            err_text = resp.text
            log.error(f"[GMAIL] Gmail send 403 error: {err_text}")
            if "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in err_text or "insufficientPermissions" in err_text:
                mark_gmail_connection_revoked(
                    user_id,
                    "reauth_required",
                    "Gmail API error (403): ACCESS_TOKEN_SCOPE_INSUFFICIENT. Missing https://www.googleapis.com/auth/gmail.send scope."
                )
                raise RuntimeError(
                    "Gmail API error (403): ACCESS_TOKEN_SCOPE_INSUFFICIENT. "
                    "Your Google account was connected without the Gmail Send permission. "
                    "Please reconnect Gmail and ensure the Send permission is granted."
                )
            elif "quotaExceeded" in err_text or "rateLimitExceeded" in err_text:
                raise RuntimeError("Gmail API error (403): Daily API quota exceeded. Please try again later.")
            else:
                mark_gmail_connection_revoked(user_id, "error", f"Gmail 403 error: {err_text}")
                raise RuntimeError(f"Gmail API error (403): {err_text}")

        if resp.status_code not in (200, 201):
            log.error(f"[GMAIL] Gmail send API error ({resp.status_code}): {resp.text}")
            raise RuntimeError(f"Gmail API error ({resp.status_code}): {resp.text}")

        res_json = resp.json()
        message_id = res_json.get("id", "sent")
        log.info(f"[GMAIL] Notification sent successfully (Msg ID: {message_id})")
        return message_id


async def send_test_email(user_id: str, to_email: str = None) -> dict:
    """
    Sends a test verification email strictly to the authenticated user's own email address.
    Verifies that the required gmail.send scope is active before sending.
    Records the outcome in the activity log without exposing sensitive contents.
    """
    conn = get_gmail_connection(user_id)
    if not conn:
        raise RuntimeError("No Gmail connection found. Please connect Gmail first.")

    status = conn.get("status", "not_connected")
    if status == "reauth_required":
        last_err = conn.get("last_error") or "Missing Gmail Send permission."
        raise RuntimeError(f"Reauthorization required: {last_err} Please reconnect Gmail.")

    if status != "active":
        raise RuntimeError(f"Gmail connection is not active (status: {status}). Please reconnect Gmail.")

    # Strictly use the authenticated user's own Google email to prevent sending test emails to external parties
    recipient = conn.get("google_email") or conn.get("user_email")
    if not recipient:
        raise ValueError("Authenticated recipient email address not found in connection record.")

    subject = "🔒 LOCK IN AI — Business Partner Connection Verified"
    text_content = (
        "🔒 LOCK IN AI Business Partner — Connection Verified\n\n"
        "Your LOCK IN AI Proactive Business Partner is now connected and operational via Gmail.\n\n"
        "• Daily missions, priority briefings, and deadline alerts will be prepared based on your preferences.\n"
        "• Outbound business communications remain in 'Approve before sending' mode by default for your safety.\n\n"
        "Stay locked in!\n"
        "— Your LOCK IN AI Business Partner"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0f19; color: #f1f5f9; padding: 20px; }}
        .card {{ background: linear-gradient(135deg, #111827 0%, #1e1b4b 100%); border: 1px solid rgba(59,130,246,0.3); border-radius: 16px; padding: 32px; max-width: 580px; margin: 0 auto; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); }}
        .title {{ font-size: 22px; font-weight: 800; color: #60a5fa; margin: 0 0 12px 0; }}
        .badge {{ display: inline-block; background: rgba(16,185,129,0.15); border: 1px solid rgba(16,185,129,0.3); color: #34d399; font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 20px; margin-bottom: 16px; }}
        .text {{ font-size: 14px; line-height: 1.6; color: #cbd5e1; margin-bottom: 14px; }}
        .box {{ background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 14px; margin: 16px 0; font-size: 13px; color: #94a3b8; }}
        .footer {{ font-size: 12px; color: #64748b; margin-top: 24px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="badge">✓ Gmail Send Verified</div>
        <h2 class="title">🔒 LOCK IN AI Proactive Business Partner</h2>
        <p class="text">Your AI business partner is successfully authenticated with your Gmail account (<strong>{recipient}</strong>).</p>
        <div class="box">
          <strong style="color:#f8fafc;">Safety & Control Active:</strong><br/>
          • Outbound communications default to <strong>Approve before sending</strong>.<br/>
          • Daily briefings and task pacing updates will arrive at your scheduled dispatch time.<br/>
          • You maintain complete control over email drafts, schedules, and trusted recipients.
        </div>
        <div class="footer">
          Delivered securely by LOCK IN AI · Startup Blueprint Platform
        </div>
      </div>
    </body>
    </html>
    """

    msg_id = await send_gmail_email(user_id, recipient, subject, text_content, html_content)
    
    return {
        "status": "success",
        "recipient": recipient,
        "message_id": msg_id,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "verified_scopes": ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/userinfo.email"]
    }


def diagnose_gmail_status(user_id: str) -> dict:
    """
    Returns comprehensive diagnostics on the user's Gmail connection state,
    distinguishing Connected, Reauthorization Required, Error, and Disconnected.
    """
    configured = is_gmail_configured()
    conn = get_gmail_connection(user_id)
    if not conn:
        return {
            "configured": configured,
            "connected": False,
            "status": "not_connected",
            "google_email": None,
            "has_send_scope": False,
            "missing_scopes": ["https://www.googleapis.com/auth/gmail.send"],
            "needs_reconnect": False,
            "reconnect_reason": "Gmail is not connected.",
        }

    status = conn.get("status", "not_connected")
    granted_scopes_raw = conn.get("granted_scopes") or ""
    if isinstance(granted_scopes_raw, list):
        granted_list = [str(s).strip() for s in granted_scopes_raw if s]
    else:
        granted_list = [s for s in str(granted_scopes_raw).split() if s]

    has_send = "https://www.googleapis.com/auth/gmail.send" in granted_list

    missing = []
    if not has_send:
        missing.append("https://www.googleapis.com/auth/gmail.send")
        if status == "active":
            status = "reauth_required"

    needs_reconnect = status in ("reauth_required", "revoked") or (not has_send)
    reconnect_reason = ""
    if not has_send:
        reconnect_reason = "Missing Gmail Send permission (https://www.googleapis.com/auth/gmail.send). Please reconnect Gmail and grant send permission."
    elif status == "reauth_required":
        reconnect_reason = conn.get("last_error") or "Google OAuth grant expired or revoked. Reauthorization required."
    elif status == "disconnected":
        reconnect_reason = "Gmail connection was disconnected by the user."

    is_truly_connected = bool(status == "active" and has_send)

    return {
        "configured": configured,
        "connected": is_truly_connected,
        "status": "active" if is_truly_connected else (status if status != "active" else "reauth_required"),
        "google_email": conn.get("google_email"),
        "has_send_scope": has_send,
        "granted_scopes": granted_list,
        "missing_scopes": missing,
        "needs_reconnect": needs_reconnect,
        "reconnect_reason": reconnect_reason,
        "last_error": conn.get("last_error", ""),
    }
