from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timedelta
import requests
import pytz
import json
from urllib.parse import urlencode


# imports από main.py
from main import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    GOOGLE_CALENDAR_REDIRECT_URI, GOOGLE_CALENDAR_SCOPES,
    GOOGLE_GMAIL_REDIRECT_URI, GOOGLE_GMAIL_SCOPE,
    GOOGLE_AUTH_URL, GOOGLE_TOKEN_URL, GOOGLE_USERINFO_URL,
)

from google_utils import google_refresh_access_token, refresh_google_access_token


from main import (
    CalendarEvent, CalendarBatch, PlanRequest
)

from db import get_connection

from auth import get_user_id_from_token

router = APIRouter(tags=["Google API"])
# prefix το αφήνω κενό γιατί έχεις διαφορετικά subpaths (google-calendar / google-gmail)
# αν θες μπορώ να το οργανώσω π.χ. prefix="/google"


# -------------------------------------------------------------------
# GOOGLE CALENDAR CONNECT
# -------------------------------------------------------------------


from fastapi.responses import RedirectResponse

@router.get("/google-calendar/connect")
def google_calendar_connect(request: Request):
    token = request.query_params.get("token")
    user_id = get_user_id_from_token(token)

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_CALENDAR_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_CALENDAR_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": str(user_id)
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(auth_url)


@router.get("/google-calendar/callback")
def google_calendar_callback(code: str = None, state: str = None):

    if not code:
        return {"error": "Missing authorization code"}

    user_id = int(state)

    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_CALENDAR_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(GOOGLE_TOKEN_URL, data=data)

    if token_resp.status_code != 200:
        return {"error": "Failed to exchange authorization code", "details": token_resp.text}

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET google_calendar_access_token=%s,
            google_calendar_refresh_token=%s
        WHERE id=%s
    """, (access_token, refresh_token, user_id))
    conn.commit()
    conn.close()

    return RedirectResponse("https://myaips.cloud/?calendar_connected=1")


@router.get("/google-calendar/events")
def google_calendar_events(user_id: int = Depends(get_user_id_from_token)):

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT google_calendar_access_token,
               google_calendar_refresh_token,
               google_calendar_token_expiry
        FROM users WHERE id=%s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(400, "User not found")

    access_token, refresh_token, expiry = row

    if not refresh_token:
        raise HTTPException(400, "Calendar not connected")

    now = datetime.utcnow()

    if not access_token or not expiry or now >= expiry:
        new_token, expires_in = google_refresh_access_token(refresh_token)
        if not new_token:
            raise HTTPException(400, "Failed to refresh access token")

        access_token = new_token
        expiry = now + timedelta(seconds=expires_in or 3600)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET google_calendar_access_token=%s,
                google_calendar_token_expiry=%s
            WHERE id=%s
        """, (access_token, expiry, user_id))
        conn.commit()
        conn.close()

    time_min = now.replace(microsecond=0).isoformat() + "Z"
    time_max = (now + timedelta(days=30)).replace(microsecond=0).isoformat() + "Z"

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    params = {
        "singleEvents": "true",
        "orderBy": "startTime",
        "timeMin": time_min,
        "timeMax": time_max,
    }

    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, params=params)

    if resp.status_code == 401:
        new_token, expires_in = google_refresh_access_token(refresh_token)
        if not new_token:
            raise HTTPException(400, "Token refresh failed")

        access_token = new_token
        expiry = now + timedelta(seconds=expires_in or 3600)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET google_calendar_access_token=%s,
                google_calendar_token_expiry=%s
            WHERE id=%s
        """, (access_token, expiry, user_id))
        conn.commit()
        conn.close()

        resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, params=params)

    if resp.status_code != 200:
        raise HTTPException(400, f"Google API error: {resp.text}")

    items = resp.json().get("items", [])

    events = []
    for item in items:
        start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
        end = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
        events.append({
            "summary": item.get("summary", "(no title)"),
            "start": start,
            "end": end
        })

    return {"events": events}


# -------------------------------------------------------------------
# CREATE SINGLE CALENDAR EVENT
# -------------------------------------------------------------------

@router.post("/calendar/create-event")
def create_calendar_event(event: CalendarEvent, request: Request):

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]
    user_id = get_user_id_from_token(token)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT google_calendar_refresh_token
        FROM users WHERE id=%s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(400, "Google Calendar not connected")

    refresh_token = row[0]
    access_token = refresh_google_access_token(refresh_token)

    if not access_token:
        raise HTTPException(400, "Failed to refresh token")

    google_event = {
        "summary": event.summary,
        "description": event.description,
        "start": {"dateTime": event.start, "timeZone": event.timezone},
        "end": {"dateTime": event.end, "timeZone": event.timezone},
    }

    resp = requests.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {access_token}"},
        json=google_event
    )

    if resp.status_code not in (200, 201):
        raise HTTPException(400, f"Google API Error: {resp.text}")

    return {"message": "Event created", "event": resp.json()}


# -------------------------------------------------------------------
# BATCH CREATE EVENTS
# -------------------------------------------------------------------

@router.post("/calendar/batch-create-events")
def calendar_batch_create_events(payload: CalendarBatch, request: Request):

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(401, "Missing Authorization")

    token = auth_header.replace("Bearer ", "")
    user_id = get_user_id_from_token(token)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT google_calendar_refresh_token
        FROM users WHERE id=%s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(400, "Google Calendar not connected")

    refresh_token = row[0]
    access_token = refresh_google_access_token(refresh_token)

    if not access_token:
        raise HTTPException(400, "Failed to refresh access token")

    created, failed = 0, 0
    results = []

    for ev in payload.events:
        google_event = {
            "summary": ev.summary,
            "description": ev.description,
            "start": {"dateTime": ev.start, "timeZone": ev.timezone},
            "end": {"dateTime": ev.end, "timeZone": ev.timezone},
        }

        resp = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            json=google_event
        )

        if resp.status_code in (200, 201):
            created += 1
            results.append(resp.json())
        else:
            failed += 1

    return {"status": "ok", "created": created, "failed": failed, "events": results}


# -------------------------------------------------------------------
# PARSE CALENDAR PLAN
# -------------------------------------------------------------------

from langchain_openai import ChatOpenAI

@router.post("/calendar/parse-plan")
def parse_calendar_plan(req: PlanRequest):

    plan_text = req.plan.strip()

    if not plan_text:
        return {"valid": False, "reason": "Empty plan"}

    full_prompt = f"""
You are a calendar event extraction engine.

Extract ALL social media post tasks that include a date or time from the user's plan.

Return ONLY valid JSON with:

{{
  "events": [
    {{
      "summary": "...",
      "description": "...",
      "start": "YYYY-MM-DDTHH:MM:SS",
      "end": "YYYY-MM-DDTHH:MM:SS",
      "timezone": "Europe/Athens"
    }}
  ]
}}

Rules:
- If no time: default 09:00–09:30.
- If date only: 09:00–09:30.
- If ranges: use them.
- If day names: convert to next occurrence.
- If nothing: return {{ "events": [] }}

User plan:
{plan_text}
"""

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    try:
        raw = llm.invoke(full_prompt).content.strip()
        data = json.loads(raw)
        events = data.get("events", [])
        if not events:
            return {"valid": False, "reason": "No events found"}

        return {"valid": True, "events": events}

    except Exception:
        return {"valid": False, "reason": "Failed to parse plan"}


# -------------------------------------------------------------------
# GMAIL CONNECT
# -------------------------------------------------------------------

@router.get("/google-gmail/connect")
def gmail_connect(request: Request):

    token = request.query_params.get("token")
    user_id = get_user_id_from_token(token)

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_GMAIL_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_GMAIL_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": str(user_id)
    }

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(auth_url)


@router.get("/google-gmail/callback")
def gmail_callback(code: str = None, state: str = None):

    if not code:
        return {"error": "Missing authorization code"}

    user_id = int(state)

    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_GMAIL_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    resp = requests.post(GOOGLE_TOKEN_URL, data=data)

    if resp.status_code != 200:
        return {"error": "Failed to exchange code", "details": resp.text}

    token_data = resp.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    expiry = datetime.utcnow() + timedelta(seconds=expires_in or 3600)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET gmail_access_token=%s,
            gmail_refresh_token=%s,
            gmail_token_expiry=%s
        WHERE id=%s
    """, (access_token, refresh_token, expiry, user_id))
    conn.commit()
    conn.close()

    return RedirectResponse("https://myaips.cloud/?gmail_connected=1")


@router.get("/google-gmail/check")
def gmail_check(user_id: int = Depends(get_user_id_from_token)):

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT gmail_access_token, gmail_refresh_token, gmail_token_expiry
        FROM users WHERE id=%s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(400, "User not found")

    access_token, refresh_token, expiry = row

    if not refresh_token:
        raise HTTPException(400, "Gmail not connected")

    now = datetime.utcnow().replace(tzinfo=pytz.UTC)

    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=pytz.UTC)

    if not access_token or not expiry or now >= expiry:
        new_token, expires_in = refresh_google_access_token(refresh_token)
        if not new_token:
            raise HTTPException(400, "Failed to refresh")

        access_token = new_token
        expiry = now + timedelta(seconds=expires_in or 3600)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET gmail_access_token=%s,
                gmail_token_expiry=%s
            WHERE id=%s
        """, (access_token, expiry, user_id))
        conn.commit()
        conn.close()

    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=5"
    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})

    if resp.status_code != 200:
        return {"error": "Gmail API error", "details": resp.text}

    return resp.json()


@router.get("/google-gmail/messages")
def gmail_messages(limit: int = 20, user_id: int = Depends(get_user_id_from_token)):

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT gmail_access_token, gmail_refresh_token, gmail_token_expiry
        FROM users WHERE id=%s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(400, "User not found")

    access_token, refresh_token, expiry = row

    if not refresh_token:
        raise HTTPException(400, "Gmail not connected")

    now = datetime.utcnow().replace(tzinfo=pytz.UTC)

    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=pytz.UTC)

    if not access_token or not expiry or now >= expiry:
        new_token, expires_in = refresh_google_access_token(refresh_token)
        if not new_token:
            raise HTTPException(400, "Failed to refresh token")

        access_token = new_token
        expiry = now + timedelta(seconds=expires_in or 3600)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET gmail_access_token=%s,
                gmail_token_expiry=%s
            WHERE id=%s
        """, (access_token, expiry, user_id))
        conn.commit()
        conn.close()

    list_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults={limit}"
    list_resp = requests.get(list_url, headers={"Authorization": f"Bearer {access_token}"})


    if list_resp.status_code != 200:
        return {"error": list_resp.text}

    message_ids = list_resp.json().get("messages", [])
    full_messages = []

    for msg in message_ids:
        msg_id = msg["id"]
        detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=full"
        detail_resp = requests.get(detail_url, headers={"Authorization": f"Bearer {access_token}"})

        if detail_resp.status_code != 200:
            continue

        data = detail_resp.json()
        headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}

        subject = headers.get("Subject", "")
        sender = headers.get("From", "")
        date = headers.get("Date", "")
        snippet = data.get("snippet", "")

        full_messages.append({
            "id": msg_id,
            "subject": subject,
            "from": sender,
            "date": date,
            "snippet": snippet,
        })

    return {"messages": full_messages}


@router.get("/google-gmail/search")
def gmail_search(q: str, user_id: int = Depends(get_user_id_from_token)):

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT gmail_access_token, gmail_refresh_token, gmail_token_expiry
        FROM users WHERE id=%s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(400, "User not found")

    access_token, refresh_token, expiry = row

    if not refresh_token:
        raise HTTPException(400, "Gmail not connected")

    now = datetime.utcnow().replace(tzinfo=pytz.UTC)

    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=pytz.UTC)

    if not access_token or not expiry or now >= expiry:
        new_token, expires_in = refresh_google_access_token(refresh_token)
        if not new_token:
            raise HTTPException(400, "Token refresh failed")

        access_token = new_token
        expiry = now + timedelta(seconds=expires_in or 3600)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET gmail_access_token=%s,
                gmail_token_expiry=%s
            WHERE id=%s
        """, (access_token, expiry, user_id))
        conn.commit()
        conn.close()


    search_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={q}&maxResults=20"
    list_resp = requests.get(search_url, headers={"Authorization": f"Bearer {access_token}"})

    if list_resp.status_code != 200:
        return {"error": list_resp.text}

    messages = list_resp.json().get("messages", [])
    full_messages = []

    for msg in messages:
        msg_id = msg["id"]
        detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=full"
        detail_resp = requests.get(detail_url, headers={"Authorization": f"Bearer {access_token}"})

        if detail_resp.status_code != 200:
            continue

        data = detail_resp.json()
        headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}

        full_messages.append({
            "id": msg_id,
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "snippet": data.get("snippet", ""),
        })

    return {"results": full_messages}


@router.post("/logout")
def logout(user_id: int = Depends(get_user_id_from_token)):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET 
            google_calendar_access_token = NULL,
            google_calendar_refresh_token = NULL,
            google_calendar_token_expiry = NULL,
            gmail_access_token = NULL,
            gmail_refresh_token = NULL,
            gmail_token_expiry = NULL,
            google = FALSE
        WHERE id = %s
    """, (user_id,))

    conn.commit()
    conn.close()

    return {"status": "ok"}
