import os
from fastapi import FastAPI, APIRouter, Depends, UploadFile, File, HTTPException, Request, Form, BackgroundTasks
import psycopg2
import redis
import tempfile, shutil
import requests
import json
import uuid

from urllib.parse import urlencode, quote
from fastapi.responses import RedirectResponse, JSONResponse

from openai import OpenAI
# ---------- NEW INGESTION PIPELINE IMPORTS ----------
from utils.parser import load_universal_no_split
from pipelines.stats import analyze_document_stats
from pipelines.orchestrator import select_pipeline_mode, run_ingestion_pipeline
from pipelines.background_ingest import background_ingest
from vectorstores.summaries_store import get_summaries_vector_store_for_user
from vectorstores.entities_store import get_entities_vector_store_for_user
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from typing import List, Dict, Any

from db_users import (
    get_vector_store_for_user,
    get_user_collection,
    get_user_by_email,
    create_user,
    get_or_create_google_user,
    ensure_user_collection
)
from auth import (
    get_user_id_from_token,
    hash_password,
    verify_password,
    create_access_token
)

from db import get_connection

from document_loader import load_and_split_universal

from datetime import datetime, timedelta
import pytz

# LangChain imports (ONLY what we need)
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_qdrant import Qdrant
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from learn.learn import router as learn_router
from pipelines.rag_llm import run_rag_flow, run_rag_flow_teacher 


class CalendarEvent(BaseModel):
    summary: str
    description: str | None = None
    start: str
    end: str
    timezone: str = "Europe/Athens"


class CalendarBatch(BaseModel):
    events: List[CalendarEvent]


class PlanRequest(BaseModel):
    plan: str
    

# ------------------------------------------------------
# BASIC APP SETUP
# ------------------------------------------------------

app = FastAPI(title="MyAI Pro API")

app.include_router(learn_router, prefix="/learn", tags=["Learn"])

POSTGRES_USER = os.getenv("POSTGRES_USER", "myuser")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mypass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "myai")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
llm_model = os.getenv("MODEL_NAME", "gpt-4o-mini")

client = OpenAI(api_key=OPENAI_API_KEY)

GOOGLE_CALENDAR_REDIRECT_URI = os.getenv("GOOGLE_CALENDAR_REDIRECT_URI")
GOOGLE_CALENDAR_SCOPES = os.getenv("GOOGLE_CALENDAR_SCOPES")

GOOGLE_GMAIL_REDIRECT_URI = os.getenv("GOOGLE_GMAIL_REDIRECT_URI")
GOOGLE_GMAIL_SCOPE = os.getenv("GOOGLE_GMAIL_SCOPE")


# ---------------------------------------------------------
# 🔥 ΠΡΟΣΘΗΚΗ ΤΟΥ ROUTER ΜΕ ΟΛΑ ΤΑ GOOGLE ENDPOINTS
# ---------------------------------------------------------

from google_routes import router as google_router
app.include_router(google_router)

# ------------------------------------------------------
# HEALTH CHECK
# ------------------------------------------------------

@app.get("/health")
def health():
    # Postgres check
    try:
        conn = psycopg2.connect(
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            connect_timeout=2,
        )
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

    # Redis check
    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    # Qdrant check
    try:
        qc = QdrantClient(url=QDRANT_URL, timeout=2.0)
        _ = qc.get_collections()
        qdrant_ok = True
    except Exception:
        qdrant_ok = False

    return {
        "status": "ok" if (db_ok and redis_ok and qdrant_ok) else "degraded",
        "postgres": db_ok,
        "redis": redis_ok,
        "qdrant": qdrant_ok
    }


@app.get("/")
def root():
    return {"message": "MyAI Pro API up & running"}


# ------------------------------------------------------
# RAG: per-user ONLY (NO GLOBAL RETRIEVER ANYMORE)
# ------------------------------------------------------

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=OPENAI_API_KEY
)

qdrant_client = QdrantClient(url=QDRANT_URL)


# ------------------------------------------------------
# /learn - add plain text
# ------------------------------------------------------

@app.post("/learn")
def learn(data: dict, user_id: int = Depends(get_user_id_from_token)):
    text = data.get("text")
    if not text:
        return {"error": "Missing text"}

    metadata = {
    "user_id": user_id,
    "document_id": document_id,
    "asset_id": asset.asset_id,
    "asset_type": asset.asset_type,
    "page": asset.page,
    "order": asset.order,
    "source": "asset_text",
    }
            
    vector_store = get_vector_store_for_user(user_id)
    vector_store.add_texts([text])

    return {"status": "stored", "user_id": user_id}


# ------------------------------------------------------
# /ask - The main RAG endpoint (clean)
# ------------------------------------------------------



# def detect_query_type(question: str) -> str:
    # """
    # Πολύ απλό heuristic για να καταλάβουμε τι ζητάει η ερώτηση:
    # - factual: names, dates, locations, counts, lists
    # - semantic: explain/describe/summarize
    # - narrative: ό,τι άλλο (ιστορία, context, νομική ανάλυση κλπ)
    # """
    # q = (question or "").lower()

    # factual_keywords = [
        # "who", "where", "when", "which", "list",
        # "names", "dates", "locations", "amounts",
        # "numbers", "how many", "how much", "entities"
    # ]
    # if any(kw in q for kw in factual_keywords):
        # return "factual"

    # semantic_keywords = [
        # "explain", "describe", "summarize", "summary",
        # "compare", "meaning", "purpose", "what is", "analyze"
    # ]
    # if any(kw in q for kw in semantic_keywords):
        # return "semantic"

    # # default
    # return "narrative"



# def get_weights(query_type: str, assistant_type: str):
    # # default weights
    # W = {
        # "raw": 1.0,
        # "summary": 0.9,
        # "image": 0.6,
        # "equation": 0.6,
        # "table": 0.6,
    # }

    # # Teacher assistant → πιο “math” & “image-driven”
    # if assistant_type == "teacher":
        # if query_type == "math":
            # W["equation"] = 1.8
            # W["raw"] = 1.2
            # W["summary"] = 0.8
        # if query_type == "image":
            # W["image"] = 1.6
        # if query_type == "table":
            # W["table"] = 1.5

    # # Lawyer assistant → θέλει raw heavy, λιγότερο multimodal
    # if assistant_type == "lawyer":
        # W["raw"] = 1.5
        # W["summary"] = 1.2
        # W["image"] = 0.3
        # W["table"] = 1.4

    # # Social content creator → summary + images
    # if assistant_type == "social":
        # W["raw"] = 0.8
        # W["summary"] = 1.5
        # W["image"] = 1.7

    # # Art director → mostly images
    # if assistant_type == "art_director":
        # W["image"] = 2.0
        # W["summary"] = 1.2
        # W["raw"] = 0.4

    # return W




### NEW

@app.post("/ask")
async def ask(
    data: dict,
    request: Request,
    user_id: int = Depends(get_user_id_from_token)
):
    print("🔥 ASK called with:", data)

    question = data.get("question")
    mode = data.get("mode", "general")
    conversation_id = data.get("conversation_id")  # μπορεί να είναι None

    if not question:
        return {"error": "Missing question"}

    # -----------------------------------------------------
    # 1. Φόρτωση assistant config (system_prompt, persona, tone, chat_enabled)
    # -----------------------------------------------------
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT u.assistant_id,
               u.chat,
               a.system_prompt,
               a.persona,
               a.tone,
               a.name
        FROM users u
        LEFT JOIN assistants a ON a.id = u.assistant_id
        WHERE u.id = %s
        """,
        (user_id,),
    )
    row = cur.fetchone()

    if not row or not row[2]:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="User has no assistant selected")

    assistant_id = row[0]
    chat_enabled = bool(row[1])
    base_system_prompt = row[2] or ""
    persona = row[3] or ""
    tone = row[4] or ""
    assistant_name = row[5] or ""

    # Load mode prompt
    cur.execute(
        """
        SELECT prompt
        FROM assistant_modes
        WHERE assistant_id = %s AND mode = %s
        """,
        (assistant_id, mode),
    )
    row_mode = cur.fetchone()
    mode_prompt = row_mode[0] if row_mode else ""

    cur.close()
    conn.close()

    # -----------------------------------------------------
    # 2. SPECIAL MODES (ΔΕΝ ΠΑΝΕ RAG)
    # -----------------------------------------------------

    # 2.1 EMAIL SEARCH MODE
    if mode == "email_search":
        print("📧 EMAIL SEARCH MODE activated")

        query_builder_prompt = f"""
You convert natural language to Gmail search operators.

User question: "{question}"

Examples:
- "email from Giannis" -> from:giannis
- "email with attachment" -> has:attachment
- "What emails have I had in the last 2 days?" -> newer_than:2d
- "messages about the project X" -> subject:"project X"

Return ONLY the Gmail search query. Nothing else.
"""

        llm_small = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=OPENAI_API_KEY,
        )

        gmail_query = llm_small.invoke(query_builder_prompt).content.strip()
        print("📮 Gmail Query =", gmail_query)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        bearer = auth_header.split(" ")[1]

        api_url = f"http://localhost:8000/google-gmail/search?q={gmail_query}"
        gmail_resp = requests.get(
            api_url,
            headers={"Authorization": f"Bearer {bearer}"},
        )

        if gmail_resp.status_code != 200:
            return {
                "assistant": assistant_name,
                "mode": mode,
                "answer": f"Email search failed: {gmail_resp.text}",
            }

        results = gmail_resp.json().get("results", [])
        if not results:
            final_answer = "No relevant emails found."
        else:
            email_context = "\n\n".join(
                [
                    f"Subject: {r['subject']}\n"
                    f"From: {r['from']}\n"
                    f"Date: {r['date']}\n"
                    f"Snippet: {r['snippet']}"
                    for r in results
                ]
            )

            summarizer_prompt = f"""
Summarize these Gmail results in Greek:

User question:
{question}

Emails:
{email_context}

Write a clear, structured answer.
"""

            final_llm = ChatOpenAI(
                model=llm_model,
                temperature=0,
                api_key=OPENAI_API_KEY,
            )

            final_answer = final_llm.invoke(summarizer_prompt).content

        # Προαιρετικά: αποθήκευση απάντησης στη συζήτηση
        if conversation_id:
            try:
                conn = get_connection()
                cur = conn.cursor()
                # user message
                cur.execute(
                    """
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s, 'user', %s)
                    """,
                    (conversation_id, question),
                )
                # assistant message
                cur.execute(
                    """
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s, 'assistant', %s)
                    """,
                    (conversation_id, final_answer),
                )
                cur.execute(
                    """
                    UPDATE conversations
                    SET updated_at = NOW(), last_message_at = NOW()
                    WHERE id = %s
                    """,
                    (conversation_id,),
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print("❌ Error saving EMAIL_SEARCH messages:", e)

        return {
            "assistant": assistant_name,
            "mode": mode,
            "answer": final_answer,
            "conversation_id": conversation_id,
        }

    # 2.2 MONTH PLANNER (calendar overview)
    if mode == "month_planner":
        print("🌞 MONTH PLANNER MODE active")

        weekday_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        month_names = {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        }

        try:
            auth_header = request.headers.get("Authorization")
            bearer = auth_header.split(" ")[1] if auth_header else None

            cal_resp = requests.get(
                "http://localhost:8000/google-calendar/events",
                headers={"Authorization": f"Bearer {bearer}"},
            )

            if cal_resp.status_code != 200:
                print("Calendar error:", cal_resp.text)
                rag_context = "No calendar data available."
            else:
                events = cal_resp.json().get("events", [])

                if not events:
                    rag_context = "You have no scheduled events in the next days."
                else:
                    formatted = []
                    for ev in events:
                        start_raw = ev.get("start")
                        end_raw = ev.get("end")
                        summary = ev.get("summary", "Untitled Event")
                        location = ev.get("location", "")

                        if start_raw and "T" not in start_raw:
                            dt = datetime.strptime(start_raw, "%Y-%m-%d").date()
                            weekday = weekday_names[dt.weekday()]
                            month = month_names[dt.month]
                            date_line = f"{weekday}, {dt.day} {month} {dt.year} (all day)"
                            time_line = "Time: All day"
                        else:
                            if start_raw:
                                s = start_raw.replace("Z", "+00:00")
                                dt_s = datetime.fromisoformat(s)
                                weekday = weekday_names[dt_s.weekday()]
                                month = month_names[dt_s.month]
                                date_line = f"{weekday}, {dt_s.day} {month} {dt_s.year}"

                                if end_raw:
                                    e = end_raw.replace("Z", "+00:00")
                                    dt_e = datetime.fromisoformat(e)
                                    time_line = (
                                        f"Time: {dt_s.strftime('%H:%M')} - {dt_e.strftime('%H:%M')}"
                                    )
                                else:
                                    time_line = f"Time: {dt_s.strftime('%H:%M')}"
                            else:
                                date_line = "Date: [unknown]"
                                time_line = "Time: [unknown]"

                        loc_line = f"Location: {location or '[Not determined]'}"

                        formatted.append(
                            f"- **{summary}**\n"
                            f"  - {date_line}\n"
                            f"  - {time_line}\n"
                            f"  - {loc_line}"
                        )

                    rag_context = "\n\n".join(formatted)

            full_system_prompt = f"""
{base_system_prompt}

Persona: {persona}
Tone: {tone}

Mode: {mode}

Mode instructions:
{mode_prompt}

Always answer in clean Markdown format.
"""

            FullPrompt = ChatPromptTemplate.from_messages(
                [
                    ("system", full_system_prompt),
                    ("human", "Question: {question}\n\nCalendar:\n{context}"),
                ]
            )

            llm = ChatOpenAI(
                model=llm_model,
                temperature=0,
                api_key=OPENAI_API_KEY,
            )

            planner_chain = (
                {
                    "question": RunnablePassthrough(),
                    "context": lambda _: rag_context,
                }
                | FullPrompt
                | llm
                | StrOutputParser()
            )

            answer = planner_chain.invoke(question)

            # save in conversation
            if conversation_id:
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO messages (conversation_id, role, content)
                        VALUES (%s, 'user', %s)
                        """,
                        (conversation_id, question),
                    )
                    cur.execute(
                        """
                        INSERT INTO messages (conversation_id, role, content)
                        VALUES (%s, 'assistant', %s)
                        """,
                        (conversation_id, answer),
                    )
                    cur.execute(
                        """
                        UPDATE conversations
                        SET updated_at=NOW(), last_message_at=NOW()
                        WHERE id = %s
                        """,
                        (conversation_id,),
                    )
                    conn.commit()
                    cur.close()
                    conn.close()
                except Exception as e:
                    print("❌ Error saving MONTH_PLANNER messages:", e)

            return {
                "assistant": assistant_name,
                "mode": mode,
                "answer": answer,
                "conversation_id": conversation_id,
            }

        except Exception as e:
            print("❌ MONTH PLANNER ERROR:", e)
            return {
                "assistant": assistant_name,
                "mode": mode,
                "answer": "Calendar data unavailable due to internal error.",
                "conversation_id": conversation_id,
            }

    # 2.3 CALENDAR EVENT CREATION
    if mode == "calendar_create_event":
        print("📅 calendar_create_event MODE ACTIVE")

        now = datetime.now()
        current_date = now.date().isoformat()
        current_year = now.year
        current_day = now.strftime("%A")
        timezone = "Europe/Athens"

        full_prompt = f"""
{mode_prompt}

You must convert the user's request into a calendar event.

Today's real date reference:
- current_date: {current_date}
- current_year: {current_year}
- current_day_of_week: {current_day}
- timezone: {timezone}

Use these to correctly compute natural-language dates such as:
"tomorrow", "next Monday", "tonight", "this evening", "next week".

Return ONLY valid JSON in this structure:

{{
  "summary": "...",
  "description": "...",
  "start": "YYYY-MM-DDTHH:MM:SS",
  "end": "YYYY-MM-DDTHH:MM:SS",
  "timezone": "{timezone}"
}}

No text, no markdown, no explanation. Only the JSON.

User request: "{question}"
"""

        llm = ChatOpenAI(
            model=llm_model,
            temperature=0,
            api_key=OPENAI_API_KEY,
        )

        result = llm.invoke(full_prompt).content.strip()

        if conversation_id:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s, 'user', %s)
                    """,
                    (conversation_id, question),
                )
                cur.execute(
                    """
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s, 'assistant', %s)
                    """,
                    (conversation_id, result),
                )
                cur.execute(
                    """
                    UPDATE conversations
                    SET updated_at=NOW(), last_message_at=NOW()
                    WHERE id = %s
                    """,
                    (conversation_id,),
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print("❌ Error saving CALENDAR_CREATE_EVENT messages:", e)

        return {
            "assistant": assistant_name,
            "mode": mode,
            "answer": result,
            "conversation_id": conversation_id,
        }

    # 2.4 SOCIAL POST → CALENDAR BATCH
    if mode == "calendar_social_post_batch":
        print("📅 calendar_social_post_batch MODE ACTIVE")

        now = datetime.now()
        current_date = now.date().isoformat()
        current_year = now.year
        current_day = now.strftime("%A")
        timezone = "Europe/Athens"

        full_prompt = f"""
{mode_prompt}

Convert the user's social media posting plan into calendar events.

Today's reference:
- current_date: {current_date}
- current_year: {current_year}
- current_day_of_week: {current_day}
- timezone: {timezone}

Rules:
- Convert relative terms ("Day 1", "Monday", "Next Friday") into actual dates.
- If no time exists → default is 10:00–10:30.
- Duration: always 30 minutes unless otherwise stated.
- Output ONLY valid JSON: an array of event objects.

Example:
[
  {{
    "summary": "Instagram Post",
    "description": "Photo of the new product",
    "start": "2025-03-01T10:00:00",
    "end": "2025-03-01T10:30:00",
    "timezone": "{timezone}"
  }}
]

IMPORTANT:
- No markdown
- No text outside JSON
- No explanations

User plan:
"{question}"
"""

        llm = ChatOpenAI(
            model=llm_model,
            temperature=0,
            api_key=OPENAI_API_KEY,
        )

        result = llm.invoke(full_prompt).content.strip()

        if conversation_id:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s, 'user', %s)
                    """,
                    (conversation_id, question),
                )
                cur.execute(
                    """
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s, 'assistant', %s)
                    """,
                    (conversation_id, result),
                )
                cur.execute(
                    """
                    UPDATE conversations
                    SET updated_at=NOW(), last_message_at=NOW()
                    WHERE id = %s
                    """,
                    (conversation_id,),
                )
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print("❌ Error saving CALENDAR_SOCIAL_POST_BATCH messages:", e)

        return {
            "assistant": assistant_name,
            "mode": mode,
            "answer": result,
            "conversation_id": conversation_id,
        }

    # -----------------------------------------------------
    # 3. NORMAL MODES → MULTIMODAL RAG
    # -----------------------------------------------------
    
    print("🔥 ASK called with assistant:", assistant_name)
    if assistant_name == "Teacher Assistant":
        from pipelines.retrieve_teacher_context import (
            retrieve_teacher_context
        )

        result = retrieve_teacher_context(
            user_id=user_id,
            question=question,
            k=3,
        )

        teacher_context = result["context"]
        print("🔥 ASK with teacher context:", teacher_context)
        
        
        if not teacher_context:
            return {
                "answer": "Δεν βρήκα σχετικό υλικό στα έγγραφά σου.",
                "context_found": False,
            }
            
            conversation_id = _save_conversation_and_messages(
                user_id=user_id,
                conversation_id=conversation_id,
                question=question,
                answer=answer,
            )

            return {
                "answer": answer,
                "conversation_id": conversation_id,
                "context_found": False,
                "used_chunks": {},
            }

    # 👉 Εδώ καλείς LLM ΜΟΝΟ με αυτό το context

        rag_result = await run_rag_flow_teacher(
            user_id=user_id,
            assistant_name=assistant_name,
            mode=mode,
            question=question,
            chat_enabled=chat_enabled,
            conversation_id=conversation_id,
            base_system_prompt=base_system_prompt,
            persona=persona,
            tone=tone,
            mode_prompt=mode_prompt,
            teacher_context=teacher_context,
        )
    
    else:
        rag_result = await run_rag_flow(
            user_id=user_id,
            assistant_name=assistant_name,
            mode=mode,
            question=question,
            chat_enabled=chat_enabled,
            conversation_id=conversation_id,
            base_system_prompt=base_system_prompt,
            persona=persona,
            tone=tone,
            mode_prompt=mode_prompt,
        )

    return {
        "assistant": assistant_name,
        "mode": mode,
        "answer": rag_result["answer"],
        "conversation_id": rag_result["conversation_id"],
        "context_found": rag_result["context_found"],
        "used_chunks": rag_result["used_chunks"],
    }


# ------------------------------------------------------
# /upload - Universal Document Loader (PDF, DOCX, TXT, OCR)
# ------------------------------------------------------
# ------------------------------------------------------
# /upload - Dynamic Large-Document Ingestion
# ------------------------------------------------------

@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_user_id_from_token),
    file: UploadFile = File(...),
    assistant_type: str = Form("general"),
):
    """
    /upload:
    - saves temp file
    - creates document_id
    - schedules background ingest
    - returns immediately
    """
    try:
        original_name = file.filename
        ext = os.path.splitext(original_name)[1].lower()

        # ----------------------------
        # 1) Save to temp file
        # ----------------------------
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        print(f"📁 Upload received: {original_name} → temp={tmp_path}")

        # ----------------------------
        # 2) Generate document_id
        # ----------------------------
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        print(f"📄 Assigned document_id={document_id}")

        # ----------------------------
        # 3) Schedule background task
        # ----------------------------
        background_tasks.add_task(
            background_ingest,
            tmp_path,
            original_name,
            user_id,
            assistant_type,
            document_id,        # MUST pass!
        )

        return {
            "status": "queued",
            "file": original_name,
            "document_id": document_id,
            "user_id": user_id,
            "processing": True,
        }

    except Exception as e:
        print("❌ ERROR in /upload:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------------------------------
# /learn_url
# ------------------------------------------------------

@app.post("/learn_url")
def learn_url(
    data: dict,
    user_id: int = Depends(get_user_id_from_token)
):
    url = data.get("url")
    if not url:
        return {"error": "Missing URL."}

    vector_store = get_vector_store_for_user(user_id)

    docs = load_and_split_universal(url=url)
    if not docs:
        return {"error": "Αποτυχία ανάγνωσης από το URL."}

    vector_store.add_documents(docs)

    return {"status": "ok", "chunks": len(docs), "url": url, "user_id": user_id}


# ------------------------------------------------------
# USER AUTH + GOOGLE AUTH + ASSISTANT LOGIC
# (UNCHANGED)
# ------------------------------------------------------
# -- USERS ---
from fastapi import Depends
from db_users import get_user_by_email, create_user
from fastapi import HTTPException
from qdrant_client.http.models import Distance, VectorParams

@app.get("/users/test")
def test_user():
    user = get_user_by_email("test@example.com")
    if not user:
        user = create_user("test@example.com", name="Demo User")
    return {"user": user}


@app.post("/register")
def register_user(data: dict):
    email = data.get("email")
    password = data.get("password")
    name = data.get("name", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")

    conn = get_connection()
    cur = conn.cursor()

    # Check if exists
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    # Δημιουργία hash (με ασφάλεια για max 72 bytes)
    try:
        hashed = hash_password(password)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Password hashing error: {str(e)}")

    # Create user
    cur.execute(
        """
        INSERT INTO users (email, password, name, role, chat)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (email, hashed, name, "register", False)
    )

    user_id = cur.fetchone()[0]

    # ---------------------------
    # CREATE PERSONAL QDRANT COLLECTION
    # ---------------------------
    #user_collection = f"user_{user_id}_vectors"
    user_collection = f"user_{user_id}_units"

    qdrant_client.create_collection(
        collection_name=user_collection,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

    # store in DB
    cur.execute(
        "UPDATE users SET vector_collection = %s WHERE id = %s",
        (user_collection, user_id)
    )

    conn.commit()
    conn.close()

    # token
    token = create_access_token({"sub": email, "user_id": user_id})
    return {"status": "ok", "token": token, "user_id": user_id, "collection": user_collection}


@app.post("/login")
def login_user(data: dict):
    email = data.get("email")
    password = data.get("password")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, password FROM users WHERE email = %s", (email,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id, hashed = row
    if not verify_password(password, hashed):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Δημιουργία JWT token
    token = create_access_token({"sub": email, "user_id": user_id})
    return {"status": "ok", "token": token, "user_id": user_id}


@app.get("/auth/google/login")
def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_REDIRECT_URI:
        return {"error": "Google OAuth not configured on server."}

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }

    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    # Κάνουμε redirect απευθείας στο Google
    return RedirectResponse(url)


from fastapi import Request

@app.get("/auth/google/callback")
def google_callback(request: Request, code: str | None = None, error: str | None = None):
    if error:
        return {"error": f"Google OAuth error: {error}"}

    if not code:
        return {"error": "Missing 'code' in Google callback."}

    # 1) Ανταλλαγή code -> tokens
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(GOOGLE_TOKEN_URL, data=data)
    if token_resp.status_code != 200:
        return {"error": "Failed to exchange code for token", "details": token_resp.text}

    token_json = token_resp.json()
    access_token = token_json.get("access_token")

    if not access_token:
        return {"error": "No access_token in Google response"}

    # 2) Παίρνουμε user info από Google
    userinfo_resp = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if userinfo_resp.status_code != 200:
        return {"error": "Failed to fetch user info from Google", "details": userinfo_resp.text}

    userinfo = userinfo_resp.json()
    # Συνήθως: sub, email, name, picture, given_name, family_name
    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name")

    if not email:
        return {"error": "Google did not provide an email."}

    # 3) Βρίσκουμε ή δημιουργούμε χρήστη
    user = get_or_create_google_user(google_id=google_id, email=email, name=name)
    user_id = user[0]

    # Βεβαιωνόμαστε ότι έχει προσωπική συλλογή Qdrant
    ensure_user_collection(user_id)

    # 4) Δημιουργούμε JWT όπως στο /login
    token = create_access_token({"sub": email, "user_id": user_id})

    # 5) Redirect στο frontend, με token + email στο query
    frontend_url = f"https://myaips.cloud/?token={quote(token)}&email={quote(email)}"
    return RedirectResponse(frontend_url)


# NEW - CONNECT WITH ASSISTANT

@app.get("/assistants")
def list_assistants():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, description, persona, tone
        FROM assistants
        ORDER BY id
    """)

    rows = cur.fetchall()
    conn.close()

    assistants = []
    for r in rows:
        assistants.append({
            "id": r[0],
            "name": r[1],
            "description": r[2],
            "persona": r[3],
            "tone": r[4],
        })

    return {"assistants": assistants}


@app.post("/select_assistant")
def select_assistant(data: dict, user_id: int = Depends(get_user_id_from_token)):
    assistant_id = data.get("assistant_id")
    if not assistant_id:
        return {"error": "Missing assistant_id"}

    conn = get_connection()
    cur = conn.cursor()

    # Check if assistant exists
    cur.execute("SELECT id FROM assistants WHERE id = %s", (assistant_id,))
    if not cur.fetchone():
        conn.close()
        return {"error": "Assistant does not exist"}

    # Update user's assistant
    cur.execute(
        "UPDATE users SET assistant_id = %s, updated_at = NOW() WHERE id = %s",
        (assistant_id, user_id)
    )
    conn.commit()
    conn.close()

    return {"status": "ok", "message": "Assistant selected", "assistant_id": assistant_id}


@app.get("/assistant")
def get_my_assistant(user_id: int = Depends(get_user_id_from_token)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT a.id, a.name, a.description, a.persona, a.tone, a.system_prompt
        FROM assistants a
        JOIN users u ON u.assistant_id = a.id
        WHERE u.id = %s
    """, (user_id,))

    row = cur.fetchone()
    conn.close()

    if not row:
        return {"assistant": None}

    return {
        "assistant": {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "persona": row[3],
            "tone": row[4],
            "system_prompt": row[5],
        }
    }

@app.get("/modes")
def get_modes(user_id: int = Depends(get_user_id_from_token)):
    conn = get_connection()
    cur = conn.cursor()

    # Fetch the user's assistant_id
    cur.execute("""
        SELECT assistant_id
        FROM users
        WHERE id = %s
    """, (user_id,))
    row = cur.fetchone()

    if not row or not row[0]:
        cur.close()
        conn.close()
        return {"modes": []}

    assistant_id = row[0]

    # Fetch the modes for this assistant
    cur.execute("""
        SELECT mode, title, prompt
        FROM assistant_modes
        WHERE assistant_id = %s order by id
    """, (assistant_id,))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    modes = [
        {"mode": r[0], "title": r[1], "prompt": r[2]}
        for r in rows
    ]

    return {"modes": modes}

@app.get("/user_settings")
def user_settings(user_id: int = Depends(get_user_id_from_token)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT chat FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    return {"chat_enabled": bool(row[0]) if row else False}

@app.get("/google_settings")
def google_settings(user_id: int = Depends(get_user_id_from_token)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT google FROM users WHERE id = %s", (user_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()

    return {"google_enabled": bool(row[0]) if row else False}
    
@app.post("/toggle_chat")
def toggle_chat(data: dict, user_id: int = Depends(get_user_id_from_token)):
    enable = data.get("enabled")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE users SET chat = %s WHERE id = %s", (enable, user_id))
    conn.commit()

    cur.close()
    conn.close()

    return {"chat_enabled": enable}



@app.post("/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    user_id: int = Depends(get_user_id_from_token)  # <- προστατεύουμε το endpoint
):
    try:
        # Read binary audio
        audio_bytes = await file.read()

        # Call Whisper (OpenAI STT)
        response = client.audio.transcriptions.create(
            model="whisper-1",  # ή gpt-4o-mini-tts όταν ενεργοποιηθεί STT
            file=("audio.webm", audio_bytes, file.content_type),
            language=None  # force auto-detection
        )

        text = response.text.strip()

        return JSONResponse({"text": text})

    except Exception as e:
        print("❌ STT ERROR:", e)
        raise HTTPException(status_code=500, detail=f"Speech-to-text failed: {str(e)}")
       
@app.post("/conversations")
def create_conversation(data: dict, user_id: int = Depends(get_user_id_from_token)):
    title = data.get("title", "New Conversation")

    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        INSERT INTO conversations (user_id, title)
        VALUES (%s, %s)
        RETURNING id, title, created_at, updated_at
    """, (user_id, title))

    row = cur.fetchone()
    conn.commit()
    conn.close()

    return {"conversation": row}


@app.get("/conversations")
def list_conversations(user_id: int = Depends(get_user_id_from_token)):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT id, title, created_at, updated_at, last_message_at
        FROM conversations
        WHERE user_id = %s
        ORDER BY last_message_at DESC NULLS LAST, updated_at DESC
    """, (user_id,))

    rows = cur.fetchall()
    conn.close()

    return {"conversations": rows}


@app.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user_id: int = Depends(get_user_id_from_token)):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, created_at, updated_at, last_message_at
        FROM conversations
        WHERE id = %s AND user_id = %s
    """, (conversation_id, user_id))

    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, "Conversation not found")

    return {"conversation": row}

@app.get("/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: str, 
    user_id: int = Depends(get_user_id_from_token)
):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Ensure user owns this conversation
    cur.execute("""
        SELECT id 
        FROM conversations 
        WHERE id = %s AND user_id = %s
    """, (conversation_id, user_id))

    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Conversation not found or unauthorized.")

    # Fetch messages
    cur.execute("""
        SELECT id, conversation_id, role, content, created_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC
    """, (conversation_id,))

    rows = cur.fetchall()
    conn.close()

    return {"messages": rows}

@app.post("/messages")
def add_message(data: dict, user_id: int = Depends(get_user_id_from_token)):
    conversation_id = data.get("conversation_id")
    role = data.get("role")  # 'user' | 'assistant'
    content = data.get("content")

    if not conversation_id or not role or not content:
        raise HTTPException(400, "Missing required fields")

    conn = get_connection()
    cur = conn.cursor()

    # Ensure conversation belongs to user
    cur.execute("""
        SELECT id FROM conversations
        WHERE id = %s AND user_id = %s
    """, (conversation_id, user_id))

    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Conversation not found")

    # Insert message
    cur.execute("""
        INSERT INTO messages (conversation_id, role, content)
        VALUES (%s, %s, %s)
        RETURNING id, created_at
    """, (conversation_id, role, content))

    row = cur.fetchone()
    conn.commit()
    conn.close()

    return {"message": row}

@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user_id: int = Depends(get_user_id_from_token)):

    conn = get_connection()
    cur = conn.cursor()

    # Check ownership
    cur.execute("""
        SELECT id FROM conversations
        WHERE id = %s AND user_id = %s
    """, (conversation_id, user_id))

    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Conversation not found or not owned by user")

    # Delete messages
    cur.execute("""
        DELETE FROM messages
        WHERE conversation_id = %s
    """, (conversation_id,))

    # Delete conversation
    cur.execute("""
        DELETE FROM conversations
        WHERE id = %s
    """, (conversation_id,))

    conn.commit()
    conn.close()

    return {"status": "ok", "deleted_conversation": conversation_id}


@app.post("/toggle_google")
def toggle_google(data: dict, user_id: int = Depends(get_user_id_from_token)):
    enable = data.get("enabled")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE users SET google = %s WHERE id = %s", (enable, user_id))
    conn.commit()

    cur.close()
    conn.close()

    return {"google_enabled": enable}



