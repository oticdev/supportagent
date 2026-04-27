"""
Google Calendar integration via direct REST API.

Used by both the chat agent (function_tool wrappers in tools.py) and the
voice router (/api/voice/tool dispatch). Single implementation, no MCP.
"""

import asyncio
import datetime
import logging
import time
from typing import Optional

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

import config

logger = logging.getLogger(__name__)

# ── OAuth token cache ─────────────────────────────────────────────────────────

_cached_token: Optional[str] = None
_token_expiry: float = 0.0
_TOKEN_BUFFER_SECONDS = 300  # refresh 5 min before actual expiry


def _sync_get_access_token() -> str:
    """Blocking OAuth refresh — always call via get_access_token() in async code."""
    global _cached_token, _token_expiry

    now = time.monotonic()
    if _cached_token and now < _token_expiry:
        return _cached_token

    if not config.GOOGLE_OAUTH_REFRESH_TOKEN:
        raise RuntimeError(
            "GOOGLE_OAUTH_REFRESH_TOKEN is not set. "
            "Calendar tools are unavailable until Google OAuth is configured."
        )

    creds = Credentials(
        token=None,
        refresh_token=config.GOOGLE_OAUTH_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.GOOGLE_CLIENT_ID,
        client_secret=config.GOOGLE_CLIENT_SECRET,
    )
    creds.refresh(Request())

    _cached_token = creds.token
    if creds.expiry:
        seconds_until_expiry = (
            creds.expiry.replace(tzinfo=datetime.timezone.utc)
            - datetime.datetime.now(datetime.timezone.utc)
        ).total_seconds()
        _token_expiry = now + max(0, seconds_until_expiry - _TOKEN_BUFFER_SECONDS)
    else:
        _token_expiry = now + 3300  # default: 55 min

    logger.debug("Google OAuth token refreshed, valid ~%.0fs", _token_expiry - now)
    return _cached_token


async def get_access_token() -> str:
    """Non-blocking async wrapper around the token refresh."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_get_access_token)


# ── Calendar operations ───────────────────────────────────────────────────────

async def check_availability(preferred_date: str) -> dict:
    """
    Return up to 5 free 30-minute slots within 7 days of preferred_date
    (weekdays, 09:00–17:00 UTC).

    Returns {"result": str, "slots": list[dict]} on success,
    or {"result": str} (with error text) on failure.
    """
    token = await get_access_token()
    now = datetime.datetime.now(datetime.timezone.utc)

    try:
        start = datetime.datetime.fromisoformat(preferred_date).replace(
            tzinfo=datetime.timezone.utc
        )
    except (ValueError, TypeError):
        start = now

    end = start + datetime.timedelta(days=7)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.googleapis.com/calendar/v3/freeBusy",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "items": [{"id": "primary"}],
            },
            timeout=10,
        )
        resp.raise_for_status()

    busy = resp.json().get("calendars", {}).get("primary", {}).get("busy", [])

    # Walk 30-min candidates within business hours
    slots: list[dict] = []
    candidate = start.replace(hour=9, minute=0, second=0, microsecond=0)
    if candidate < now:
        candidate = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)

    while len(slots) < 5 and candidate < end:
        if candidate.weekday() >= 5:                        # skip weekend
            candidate += datetime.timedelta(days=1)
            candidate = candidate.replace(hour=9, minute=0)
            continue
        if candidate.hour < 9 or candidate.hour >= 17:      # skip outside hours
            candidate = candidate.replace(hour=9, minute=0) + datetime.timedelta(days=1)
            continue

        slot_end = candidate + datetime.timedelta(minutes=30)
        overlap = any(
            datetime.datetime.fromisoformat(b["start"].replace("Z", "+00:00")) < slot_end
            and datetime.datetime.fromisoformat(b["end"].replace("Z", "+00:00")) > candidate
            for b in busy
        )
        if not overlap:
            slots.append({
                "start": candidate.isoformat(),
                "end": slot_end.isoformat(),
                "display": candidate.strftime("%A %d %B at %I:%M %p UTC"),
            })

        candidate += datetime.timedelta(minutes=30)

    if not slots:
        return {"result": "No available slots found in the next 7 days."}

    lines = "\n".join(f"- {s['display']} (start={s['start']})" for s in slots)
    return {"result": f"Available slots:\n{lines}", "slots": slots}


async def create_event(
    attendee_email: str,
    start_time: str,
    summary: str = "RelayPay Support Call",
    description: str = "RelayPay customer support call",
) -> dict:
    """
    Create a 30-minute calendar event and send the invite to attendee_email.

    Returns {"result": str, "event_id": str, "html_link": str} on success.
    """
    token = await get_access_token()

    try:
        start_dt = datetime.datetime.fromisoformat(start_time)
    except (ValueError, TypeError):
        return {"result": "Invalid start_time format. Use ISO 8601, e.g. 2025-06-10T14:00:00."}

    end_dt = start_dt + datetime.timedelta(minutes=30)

    event_body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
        "attendees": [{"email": attendee_email}],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            json=event_body,
            params={"sendUpdates": "all"},
            timeout=10,
        )
        resp.raise_for_status()

    event = resp.json()
    return {
        "result": f"Calendar event created. Event ID: {event['id']}",
        "event_id": event["id"],
        "html_link": event.get("htmlLink", ""),
    }
