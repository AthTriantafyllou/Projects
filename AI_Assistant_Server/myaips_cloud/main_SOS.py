import os
from fastapi import FastAPI, APIRouter, Depends, UploadFile, File, HTTPException, Request, Form, BackgroundTasks
import psycopg2
import redis
import tempfile, shutil
import requests
import json

from qdrant_client import QdrantClient
from urllib.parse import urlencode, quote
from fastapi.responses import RedirectResponse, JSONResponse
from auth import get_user_id_from_query_token
from openai import OpenAI
# ---------- NEW INGESTION PIPELINE IMPORTS ----------
from utils.parser import load_universal_no_split
from pipelines.stats import analyze_document_stats
from pipelines.orchestrator import select_pipeline_mode, run_ingestion_pipeline
from vectorstores.summaries_store import get_summaries_vector_store_for_user
from vectorstores.entities_store import get_entities_vector_store_for_user
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from typing import List
from langchain.schema import Document

from auth import get_user_id_from_token
from db_users import (
    get_vector_store_for_user,
    get_user_collection,
    get_user_by_email,
    create_user,
    get_or_create_google_user,
    ensure_user_collection
)
from auth import (
    get_connection,
    hash_password,
    verify_password,
    create_access_token
)

from document_loader import load_and_split_universal


from datetime import datetime, timedelta
import pytz

# LangChain imports (ONLY what we need)
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_qdrant import Qdrant
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from qdrant_client.http.models import Distance, VectorParams

from learn.learn import router as learn_router



class CalendarEvent(BaseModel):
    summary: str
    description: str | None = None
    start: str  # ISO datetime
    end: str    # ISO datetime
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


# --------------

def generate_conversation_title(question, answer):
    prompt = f"""
Generate a very short, crisp title (max 6 words) for a conversation based on:

User question:
{question}

Assistant answer:
{answer}

Do NOT use quotes. Keep it short.
"""

    llm = ChatOpenAI(
        model="gpt-4o-mini",  # ή όποιο χρησιμοποιείς
        temperature=0.2,
        api_key=OPENAI_API_KEY
    )

    title = llm.invoke(prompt).content.strip()
    return title[:80]  # safety truncation


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

    vector_store = get_vector_store_for_user(user_id)
    vector_store.add_texts([text])

    return {"status": "stored", "user_id": user_id}


# ------------------------------------------------------
# /ask - The main RAG endpoint (clean)
# ------------------------------------------------------

from datetime import datetime  # ήδη το έχεις πιο πάνω, απλά βεβαιώσου

def detect_query_type(question: str) -> str:
    """
    Πολύ απλό heuristic για να καταλάβουμε τι ζητάει η ερώτηση:
    - factual: names, dates, locations, counts, lists
    - semantic: explain/describe/summarize
    - narrative: ό,τι άλλο (ιστορία, context, νομική ανάλυση κλπ)
    """
    q = (question or "").lower()

    factual_keywords = [
        "who", "where", "when", "which", "list",
        "names", "dates", "locations", "amounts",
        "numbers", "how many", "how much", "entities"
    ]
    if any(kw in q for kw in factual_keywords):
        return "factual"

    semantic_keywords = [
        "explain", "describe", "summarize", "summary",
        "compare", "meaning", "purpose", "what is", "analyze"
    ]
    if any(kw in q for kw in semantic_keywords):
        return "semantic"

    # default
    return "narrative"


def get_store_weights(query_type: str):
    """
    Επιστρέφει (RAW_W, SUM_W, ENT_W) ανάλογα με τον τύπο της ερώτησης.
    Δεν εξαρτάται από assistant. Είναι generic & future-proof.
    """
    if query_type == "factual":
        # Θέλουμε entities > summaries > raw
        return 0.7, 1.0, 1.3

    if query_type == "semantic":
        # Θέλουμε summaries > raw > entities
        return 0.7, 1.3, 0.8

    # narrative / default:
    # Θέλουμε raw > summaries > entities
    return 1.3, 1.0, 0.7


@app.post("/ask")
def ask(
    data: dict,
    request: Request,
    user_id: int = Depends(get_user_id_from_token)
):

    print("🔥 ASK called with:", data)

    question = data.get("question")
    mode = data.get("mode", "general")
    conversation_id = data.get("conversation_id")  # <<< NEW

    if not question:
        return {"error": "Missing question"}

    # -----------------------------------------------------
    # A) SAVE USER MESSAGE if conversation_id PROVIDED
    # -----------------------------------------------------
    if conversation_id:
        try:
            conn = get_connection()
            cur = conn.cursor()

            # Check if conversation belongs to user
            cur.execute("""
                SELECT id FROM conversations
                WHERE id = %s AND user_id = %s
            """, (conversation_id, user_id))

            if not cur.fetchone():
                conn.close()
                raise HTTPException(404, "Conversation not found")

            # Insert user message
            #cur.execute("""
            #    INSERT INTO messages (conversation_id, role, content)
            #    VALUES (%s, 'user', %s)
            #""", (conversation_id, question))

            conn.commit()
            conn.close()

        except Exception as e:
            print("❌ Error saving USER message:", e)
            
    # -----------------------------------------------------
    # -----------------------------
    # 1. Load assistant + chat flag
    # -----------------------------
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.assistant_id, u.chat,
               a.system_prompt, a.persona, a.tone, a.name
        FROM users u
        LEFT JOIN assistants a ON a.id = u.assistant_id
        WHERE u.id = %s
    """, (user_id,))
    row = cur.fetchone()

    if not row or not row[2]:
        cur.close()
        conn.close()
        return {"error": "User has no assistant selected"}

    assistant_id = row[0]
    chat_enabled = bool(row[1])
    base_system_prompt = row[2] or ""
    persona = row[3] or ""
    tone = row[4] or ""
    assistant_name = row[5] or ""

    # Load mode prompt
    cur.execute("""
        SELECT prompt
        FROM assistant_modes
        WHERE assistant_id = %s AND mode = %s 
    """, (assistant_id, mode))
    row_mode = cur.fetchone()
    mode_prompt = row_mode[0] if row_mode else ""

    cur.close()
    conn.close()

    # -----------------------------------------------------
    # SPECIAL MODE: EMAIL SEARCH
    # -----------------------------------------------------
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
            api_key=OPENAI_API_KEY
        )

        gmail_query = llm_small.invoke(query_builder_prompt).content.strip()
        print("📮 Gmail Query =", gmail_query)

        api_url = f"http://localhost:8000/google-gmail/search?q={gmail_query}"
        bearer = request.headers.get("Authorization").split(" ")[1]

        gmail_resp = requests.get(
            api_url,
            headers={"Authorization": f"Bearer {bearer}"}
        )

        if gmail_resp.status_code != 200:
            return {
                "assistant": assistant_name,
                "mode": mode,
                "answer": f"Email search failed: {gmail_resp.text}"
            }

        results = gmail_resp.json().get("results", [])
        if not results:
            return {
                "assistant": assistant_name,
                "mode": mode,
                "answer": "No relevant emails found."
            }

        email_context = "\n\n".join([
            f"Subject: {r['subject']}\n"
            f"From: {r['from']}\n"
            f"Date: {r['date']}\n"
            f"Snippet: {r['snippet']}"
            for r in results
        ])

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
            api_key=OPENAI_API_KEY
        )

        final_answer = final_llm.invoke(summarizer_prompt).content
        
        # SAVE ASSISTANT MESSAGE
        if conversation_id:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s, 'assistant', %s)
                """, (conversation_id, answer))
                conn.commit()
                conn.close()
            except Exception as e:
                print("❌ Error saving ASSISTANT message:", e)

        return {
            "assistant": assistant_name,
            "mode": mode,
            "answer": final_answer
        }

    # -----------------------------------------------------
    # SPECIAL MODE: MONTH PLANNER (Google Calendar)
    # -----------------------------------------------------
    if mode == "month_planner":
        print("🌞 month PLANNER MODE ACTIVE")

        weekday_names = [
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
        ]
        month_names = {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December",
        }

        def format_date_greek(date_str: str, all_day: bool = False):
            if "T" in date_str:
                s = date_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(s)
                weekday = weekday_names[dt.weekday()]
                month = month_names[dt.month]
                if all_day:
                    return f"{weekday}, {dt.day} {month} {dt.year} (all day)"
                else:
                    return weekday, month, dt
            else:
                dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                weekday = weekday_names[dt.weekday()]
                month = month_names[dt.month]
                return f"{weekday}, {dt.day} {month} {dt.year} (all day event)"

        try:
            auth_header = request.headers.get("Authorization")
            bearer = auth_header.split(" ")[1] if auth_header else None

            cal_resp = requests.get(
                "http://localhost:8000/google-calendar/events",
                headers={"Authorization": f"Bearer {bearer}"}
            )

            if cal_resp.status_code != 200:
                print("Calendar error:", cal_resp.text)
                rag_context = "No calendar data available."
            else:
                events = cal_resp.json().get("events", [])

                if not events:
                    rag_context = "You have no scheduled events in the next 7 days."
                else:
                    formatted = []
                    for ev in events:
                        start_raw = ev.get("start")
                        end_raw = ev.get("end")
                        summary = ev.get("summary", "Untitled Event")
                        location = ev.get("location", "")

                        if start_raw and "T" not in start_raw:
                            date_line = format_date_greek(start_raw, all_day=True)
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
                                    time_line = f"Time: {dt_s.strftime('%H:%M')} - {dt_e.strftime('%H:%M')}"
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

            print("📅 CALENDAR CONTEXT SENT TO LLM:\n", rag_context)

            full_system_prompt = f"""
{base_system_prompt}

Persona: {persona}
Tone: {tone}

Mode: {mode}

Mode instructions:
{mode_prompt}

Always answer in clean Markdown format.
"""

            FullPrompt = ChatPromptTemplate.from_messages([
                ("system", full_system_prompt),
                ("human", "Question: {question}\n\nCalendar:\n{context}")
            ])

            llm = ChatOpenAI(model=llm_model, temperature=0, api_key=OPENAI_API_KEY)

            planner_chain = (
                {
                    "question": RunnablePassthrough(),
                    "context": lambda _: rag_context
                }
                | FullPrompt
                | llm
                | StrOutputParser()
            )

            answer = planner_chain.invoke(question)
            
            # SAVE ASSISTANT MESSAGE
            if conversation_id:
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO messages (conversation_id, role, content)
                        VALUES (%s, 'assistant', %s)
                    """, (conversation_id, answer))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print("❌ Error saving ASSISTANT message:", e)

            return {
                "assistant": assistant_name,
                "mode": mode,
                "answer": answer
            }

        except Exception as e:
            print("❌ WEEK PLANNER ERROR:", e)
            return {
                "assistant": assistant_name,
                "mode": mode,
                "answer": "Calendar data unavailable due to internal error."
            }

    # -----------------------------------------------------
    # SPECIAL MODE: CALENDAR EVENT CREATION
    # -----------------------------------------------------
    if mode == "calendar_create_event":
        print("📅 calendar_create_event MODE ACTIVE")

        # Dynamic date info
        now = datetime.now()
        current_date = now.date().isoformat()          # 2025-01-19
        current_year = now.year                        # 2025
        current_day = now.strftime("%A")               # Sunday
        timezone = "Europe/Athens"

        # Build full prompt
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
            api_key=OPENAI_API_KEY
        )

        result = llm.invoke(full_prompt).content.strip()

        # Save assistant message
        if conversation_id:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s, 'assistant', %s)
                """, (conversation_id, result))
                conn.commit()
                conn.close()
            except Exception as e:
                print("❌ Error saving ASSISTANT message:", e)

        return {
            "assistant": assistant_name,
            "mode": mode,
            "answer": result,
            "conversation_id": conversation_id
        }   

    # -----------------------------------------------------
    # SPECIAL MODE: SOCIAL POST → CALENDAR BATCH
    # -----------------------------------------------------
    if mode == "calendar_social_post_batch":
        print("📅 calendar_social_post_batch MODE ACTIVE")

        # Dynamic date info
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
    - Output **ONLY valid JSON**: an array of event objects.

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
            api_key=OPENAI_API_KEY
        )

        result = llm.invoke(full_prompt).content.strip()

        # Save assistant message
        if conversation_id:
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO messages (conversation_id, role, content)
                    VALUES (%s, 'assistant', %s)
                """, (conversation_id, result))
                conn.commit()
                conn.close()
            except Exception as e:
                print("❌ Error saving ASSISTANT message:", e)

        return {
            "assistant": assistant_name,
            "mode": mode,
            "answer": result,
            "conversation_id": conversation_id
        }



    # -----------------------------------------------------
    # NORMAL MODES (MULTI-VECTOR RAG + Chat)
    # -----------------------------------------------------
    # 1) ΦΟΡΤΩΝΟΥΜΕ ΚΑΙ ΤΑ 3 STORES
    raw_store = get_vector_store_for_user(user_id)
    summaries_store = get_summaries_vector_store_for_user(user_id)
    entities_store = get_entities_vector_store_for_user(user_id)

    print("🟦 ASK: RAW collection =", raw_store.collection_name)
    print("🟦 ASK: QDRANT URL =", QDRANT_URL)

    # 2) ΡΥΘΜΙΣΕΙΣ ΑΝΑ ASSISTANT / MODE
    assistant_name_lower = (assistant_name or "").lower()
    persona_lower = (persona or "").lower()


# -----------------------------------------------------
# 2) ΡΥΘΜΙΣΕΙΣ ΑΝΑ MODE (ΚΑΘΑΡΗ ΕΚΔΟΣΗ)
# -----------------------------------------------------

    # Explicit modes
    is_script_mode = mode in ["script_breakdown", "scene_visual_direction", "location_visual_design", "character_visual_profile"]
    is_legal_mode  = mode in ["legal_analyze", "legal_summary", "issue_spotting", "questions_to_ask"]
    


    # k-values ανά περίπτωση
    if is_script_mode:
        # Art director / script analysis → θέλει μεγαλύτερο global context
        k_raw = 8
        k_sum = 12
        k_ent = 12
        RAW_THRESHOLD = 0.25

    elif is_legal_mode:
        # Lawyer mode → fact extraction από νομικά έγγραφα
        # Χρειαζόμαστε λίγα summaries/entities και αρκετά RAW
        k_raw = 10
        k_sum = 6
        k_ent = 6
        RAW_THRESHOLD = 0.35

    else:
        # Generic: teacher, social, general assistant
        k_raw = 4
        k_sum = 6
        k_ent = 6
        RAW_THRESHOLD = 0.45


    # 3) ΠΡΩΤΑ RAW RESULTS (για απόφαση context_found)
    raw_results = raw_store.similarity_search_with_score(question, k=k_raw)

    print("🧾 RAW_THRESHOLD:", RAW_THRESHOLD)
    print("📊 RAW results:", [(round(s, 4), d.page_content[:60]) for d, s in raw_results])

    best_raw = max([s for _, s in raw_results], default=0.0)
    #RAW_THRESHOLD = 0.25  # 0.45 παλιά

    context_found = best_raw >= RAW_THRESHOLD

    print(f"🔎 best_raw={best_raw:.4f}, context_found={context_found}, chat_enabled={chat_enabled}")

    # Αν δεν υπάρχει επαρκές context και το chat είναι OFF → ΜΗΝ απαντήσεις "έξυπνα"
    if not context_found and not chat_enabled:
        return {
            "assistant": assistant_name,
            "mode": mode,
            "answer": (
                "I couldn't find any information in your database "
                "related to what you asked. "
                "If you want me to look into external sources of knowledge, "
                "activate chat mode."
            )
        }

    # -----------------------------------------------------
    # 4) Αν είμαστε εδώ:
    #  - είτε έχουμε επαρκές context (context_found=True)
    #  - είτε chat_enabled=True (οπότε επιτρέπεται pure chat).
    #    Σε κάθε περίπτωση, χρησιμοποιούμε και summaries & entities.
    # -----------------------------------------------------
    if context_found:
        sum_results = summaries_store.similarity_search_with_score(question, k=k_sum)
        ent_results = entities_store.similarity_search_with_score(question, k=k_ent)
    else:
        # Δεν βρέθηκε RAW context αλλά chat_enabled=True:
        # μπορούμε να δοκιμάσουμε summaries/entities (εξακολουθούν να είναι local DB)
        sum_results = summaries_store.similarity_search_with_score(question, k=k_sum)
        ent_results = entities_store.similarity_search_with_score(question, k=k_ent)

    print("📊 SUM results:", [(round(s, 4), d.page_content[:60]) for d, s in sum_results])
    print("📊 ENT results:", [(round(s, 4), d.page_content[:60]) for d, s in ent_results])

    # -----------------------------------------------------
    # 5) FUSED CONTEXT ΜΕ WEIGHTS ΑΝΑΛΟΓΑ ΜΕ ΤΟ ΕΙΔΟΣ ΤΗΣ ΕΡΩΤΗΣΗΣ
    # -----------------------------------------------------

    query_type = detect_query_type(question)
    RAW_W, SUM_W, ENT_W = get_store_weights(query_type)

    print(f"🧠 query_type={query_type}, weights = raw:{RAW_W}, sum:{SUM_W}, ent:{ENT_W}")

    def make_result_items(results, source_tag: str):
        items = []
        for doc, score in results:
            items.append(
                {
                    "doc": doc,
                    "score": float(score),
                    "source": source_tag,
                }
            )
        return items

    all_items = []
    all_items.extend(make_result_items(raw_results, "raw"))
    all_items.extend(make_result_items(sum_results, "summary"))
    all_items.extend(make_result_items(ent_results, "entity"))

    def source_weight(src: str) -> float:
        if src == "raw":
            return RAW_W
        if src == "summary":
            return SUM_W
        if src == "entity":
            return ENT_W
        return 1.0

    # Υπολογίζουμε final_score = similarity * store_weight
    for item in all_items:
        w = source_weight(item["source"])
        item["final_score"] = item["score"] * w

    # Sort DESC by final_score
    all_items.sort(key=lambda x: x["final_score"], reverse=True)

    # -----------------------------------------------------
    # 6) DIVERSITY + LIMITS ανά store & συνολικά
    # -----------------------------------------------------
    MAX_RAW_DOCS = 4
    MAX_SUM_DOCS = 4
    MAX_ENT_DOCS = 4
    MAX_TOTAL_DOCS = 12

    counts = {"raw": 0, "summary": 0, "entity": 0}
    seen = set()
    merged_texts = []

    for item in all_items:
        doc = item["doc"]
        src = item["source"]

        if counts[src] >= (MAX_RAW_DOCS if src == "raw" else MAX_SUM_DOCS if src == "summary" else MAX_ENT_DOCS):
            continue

        if len(merged_texts) >= MAX_TOTAL_DOCS:
            break

        txt = (doc.page_content or "").strip()
        if not txt:
            continue

        key = (txt, src)
        if key in seen:
            continue
        seen.add(key)

        # Prefix ανά source για να ξέρει το LLM από πού ήρθε
        prefix = ""
        if src == "summary":
            prefix = "[SUMMARY]\n"
        elif src == "entity":
            prefix = "[ENTITY]\n"

        merged_texts.append(prefix + txt)
        counts[src] += 1

    rag_context = "\n\n---\n\n".join(merged_texts)

    print("🟩 FINAL CONTEXT LENGTH =", len(rag_context))
    print("🧾 FINAL COUNTS:", counts)


    # 6) ΤΕΛΙΚΟ PROMPT (διαφορετικό για legal vs generic)
    # if is_legal_mode:
        # # Legal: ΠΟΤΕ δεν χρησιμοποιεί external knowledge, μόνο τα έγγραφα
        # full_system_prompt = f"""
# {base_system_prompt}

# Persona: {persona}
# Tone: {tone}

# Mode: {mode}

# Mode instructions:
# {mode_prompt}

# You are analyzing legal documents for factual information only.
# Use ONLY the provided context from the user's documents when chat is disabled.
# Never provide legal advice, legal opinions, or recommendations.
# If chat is disabled and the context does not contain enough information,
# you must say that you cannot find the answer in the user's documents.

# You receive context coming from:
# - RAW chunks of the user's documents
# - Hierarchical SUMMARIES
# - Extracted ENTITIES (people, locations, key objects)

# Always answer in clean Markdown format.
# """
    # else: 
    
    
    
    # Generic / teacher / art director κ.λπ.
    full_system_prompt = f"""
{base_system_prompt}

Persona: {persona}
Tone: {tone}

Mode: {mode}

Mode instructions:
{mode_prompt}

You receive context coming from:
- RAW chunks of the user's documents
- Hierarchical SUMMARIES
- Extracted ENTITIES (people, locations, key objects)

Use ONLY this context when chat is disabled.
If chat is disabled and the context does not contain enough information,
you must say that you cannot find the answer in the user's documents.

When chat is enabled you may also use your general knowledge if needed.

Always answer in clean Markdown format.
"""
    #print("❌ full_system_prompt:", full_system_prompt)
    
    # SOS  - EDO pairnei apo tin basi ta general + mode + ayta poy einai sta portokali 
   
# -----------------------------------------------------
# LOAD LAST 10 MESSAGES FROM CONVERSATION  (<<< NEW) --- το αλλαξα σε 3!!!
# -----------------------------------------------------
    history_messages = []

    if conversation_id:
        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT role, content
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at DESC
                LIMIT 3
            """, (conversation_id,))

            rows = cur.fetchall()
            conn.close()

            # reverse so oldest → newest
            rows = rows[::-1]

            for r in rows:
                role = r[0]
                content = r[1]

                if role == "user":
                    history_messages.append(("human", content))
                else:
                    history_messages.append(("assistant", content))

        except Exception as e:
            print("❌ Error loading conversation history:", e)

    print("❌ history_messages:", history_messages)
    
    prompt_messages = [
        ("system", full_system_prompt),
    ]

    # <<< NEW: add previous chat messages
    prompt_messages.extend(history_messages)

    # the final user question
    prompt_messages.append(
        ("human",
         "Question:\n{question}\n\nFused context (raw chunks, summaries, entities):\n{context}")
    )

    FullPrompt = ChatPromptTemplate.from_messages(prompt_messages)

    print("❌ FullPrompt:", FullPrompt)

    llm = ChatOpenAI(model=llm_model, temperature=0, api_key=OPENAI_API_KEY)

    user_rag_chain = (
        {
            "question": RunnablePassthrough(),
            "context": lambda _: rag_context
        }
        | FullPrompt
        | llm
        | StrOutputParser()
    )

    answer = user_rag_chain.invoke(question)
    
    # ============================================
    # AUTO TITLE GENERATION (only if needed)
    # ============================================

    conn = get_connection()
    cur = conn.cursor()

    # if no conversation_id → create a new conversation
    if not conversation_id:
        cur.execute("""
            INSERT INTO conversations (user_id, title, updated_at)
            VALUES (%s, %s, NOW())
            RETURNING id
        """, (user_id, "New chat"))
        
        row = cur.fetchone()
        conversation_id = row[0]  # OK

        # Save user message
        cur.execute("""
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, 'user', %s)
        """, (conversation_id, question))

        # Save assistant message
        cur.execute("""
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, 'assistant', %s)
        """, (conversation_id, answer))

        conn.commit()

        # --- generate title ---
        try:
            auto_title = generate_conversation_title(question, answer)
            cur.execute("""
                UPDATE conversations
                SET title = %s, updated_at = NOW(), last_message_at = NOW()
                WHERE id = %s
            """, (auto_title, conversation_id))
            conn.commit()
        except Exception as e:
            print("Title generation error:", e)

    else:
        # existing conversation → save messages normally
        cur.execute("""
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, 'user', %s)
        """, (conversation_id, question))

        cur.execute("""
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, 'assistant', %s)
        """, (conversation_id, answer))

        # update last updated
        cur.execute("""
            UPDATE conversations
            SET updated_at = NOW(), last_message_at = NOW()
            WHERE id = %s
        """, (conversation_id,))

        conn.commit()

    cur.close()
    conn.close()

    
    # -----------------------------------------------------
    # SAVE ASSISTANT MESSAGE (NORMAL MODES)
    # -----------------------------------------------------
    #if conversation_id:
    #    try:
    #        conn = get_connection()
    #        cur = conn.cursor()
    #        cur.execute("""
     #           INSERT INTO messages (conversation_id, role, content)
    #            VALUES (%s, 'assistant', %s)
     #       """, (conversation_id, answer))
    #        conn.commit()
     #       conn.close()
    #    except Exception as e:
    #        print("❌ Error saving ASSISTANT message:", e)
            
    return {
        "assistant": assistant_name,
        "mode": mode,
        "answer": answer,
        "conversation_id": conversation_id  # <<< NEW
    }

# ------------------------------------------------------
# /upload - Universal Document Loader (PDF, DOCX, TXT, OCR)
# ------------------------------------------------------
# ------------------------------------------------------
# /upload - Dynamic Large-Document Ingestion
# ------------------------------------------------------



async def background_ingest(
    tmp_path: str,
    original_name: str,
    user_id: int,
    assistant_type: str,
):
    try:
        print("\n\n==============================")
        print(f"🚀 [BG] START ingest: {original_name}")
        print(f"👤 user={user_id}, assistant_type={assistant_type}")
        print("==============================\n")

        # 1) Load docs
        raw_docs: List[Document] = load_universal_no_split(tmp_path, original_name)

        if not raw_docs:
            print(f"❌ [BG] No readable content in {original_name}")
            return

        print(f"📄 [BG] Loaded RAW docs = {len(raw_docs)}")
        print(f"📝 [BG] Preview = {raw_docs[0].page_content[:200]!r}")

        # 2) Stats
        stats = analyze_document_stats(raw_docs)
        mode = select_pipeline_mode(stats, assistant_type)

        print(f"📊 [BG] Stats = {stats}")
        print(f"🔥 [BG] Selected mode = {mode}")

        # 3) Pipeline start
        print(f"🏁 [BG] Starting pipeline {mode}...")

        vector_store = get_vector_store_for_user(user_id)

        result = await run_ingestion_pipeline(
            mode=mode,
            raw_docs=raw_docs,
            vector_store=vector_store,
            user_id=user_id,
            assistant_type=assistant_type,
        )

        print("\n🎉 [BG] Pipeline COMPLETED!")
        print(f"📦 [BG] Result = {result}")

    except Exception as e:
        print("❌ [BG] ERROR in background_ingest:", e)

    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                print(f"🧹 [BG] Temp file deleted: {tmp_path}")
            except Exception as e:
                print(f"⚠️ [BG] Temp file cleanup failed: {e}")

        print("\n==============================")
        print(f"🏁 [BG] FINISHED ingest: {original_name}")
        print("==============================\n\n")



@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,                  # 1
    user_id: int = Depends(get_user_id_from_token),     # 2
    file: UploadFile = File(...),                       # 3
    assistant_type: str = Form("general"),              # 4
):
    """
    ΝΕΟ /upload:
    - σώζει προσωρινά το αρχείο
    - ΔΕΝ κάνει πλέον parsing / summaries / entities μέσα στο request
    - βάζει background task (background_ingest)
    - επιστρέφει γρήγορα στο frontend
    """

    try:
        original_name = file.filename
        ext = os.path.splitext(original_name)[1].lower()

        # 1) Save uploaded file to temp path
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        print(f"📁 Upload received: {original_name} → temp: {tmp_path}")
        print(f"👤 user_id={user_id}, assistant_type={assistant_type}")

        # 2) Schedule background ingestion
        background_tasks.add_task(
            background_ingest,
            tmp_path,
            original_name,
            user_id,
            assistant_type,
        )

        # 3) Immediate response
        return {
            "status": "queued",
            "file": original_name,
            "user_id": user_id,
            "processing": True,
            "message": "File accepted for background processing."
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

# ... (όλος ο υπόλοιπος κώδικας από το δικό σου main.py όπως είναι)

# -- USERS ---
from fastapi import Depends
from db_users import get_user_by_email, create_user
from auth import get_connection, hash_password, verify_password, create_access_token
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
    user_collection = f"user_{user_id}_vectors"

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


# NEW Calendar
@app.get("/google-calendar/connect")
def google_calendar_connect(request: Request):

    # 1. Παίρνουμε το JWT από το query
    token = request.query_params.get("token")
    user_id = get_user_id_from_query_token(token)

    # 2. Χτίζουμε το Google OAuth URL
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_CALENDAR_REDIRECT_URI,   # <-- ΣΩΣΤΟ
        "response_type": "code",
        "scope": GOOGLE_CALENDAR_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": str(user_id)
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    return RedirectResponse(auth_url)


@app.get("/google-calendar/callback")
def google_calendar_callback(code: str = None, state: str = None):

    if not code:
        return {"error": "Missing authorization code"}

    user_id = int(state)

    # 1. Ανταλλαγή code → tokens
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_CALENDAR_REDIRECT_URI,   # <-- ΣΩΣΤΟ
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(GOOGLE_TOKEN_URL, data=data)

    if token_resp.status_code != 200:
        return {
            "error": "Failed to exchange authorization code",
            "details": token_resp.text
        }

    token_data = token_resp.json()

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    # 2. Save to DB
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET google_calendar_access_token = %s,
            google_calendar_refresh_token = %s
        WHERE id = %s
    """, (access_token, refresh_token, user_id))
    conn.commit()
    conn.close()

    # 3. Redirect back to app
    return RedirectResponse("https://myaips.cloud/?calendar_connected=1")




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


def google_refresh_access_token(refresh_token: str):
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    resp = requests.post(GOOGLE_TOKEN_URL, data=data)
    if resp.status_code != 200:
        print("❌ Failed to refresh Google token:", resp.text)
        return None, None

    json_resp = resp.json()
    return json_resp.get("access_token"), json_resp.get("expires_in")


@app.get("/google-calendar/events")
def google_calendar_events(user_id: int = Depends(get_user_id_from_token)):

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT google_calendar_access_token,
               google_calendar_refresh_token,
               google_calendar_token_expiry
        FROM users
        WHERE id = %s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=400, detail="User not found")

    access_token, refresh_token, expiry = row

    if not refresh_token:
        raise HTTPException(status_code=400, detail="Calendar not connected")

    now = datetime.utcnow()

    # 1️⃣ Token refresh if needed
    if not access_token or not expiry or now >= expiry:
        print("🔄 Access token expired → refreshing...")
        new_token, expires_in = google_refresh_access_token(refresh_token)
        if not new_token:
            raise HTTPException(status_code=400, detail="Failed to refresh access token")

        access_token = new_token
        expiry = now + timedelta(seconds=expires_in or 3600)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET google_calendar_access_token = %s,
                google_calendar_token_expiry = %s
            WHERE id = %s
        """, (access_token, expiry, user_id))
        conn.commit()
        conn.close()

    # 2️⃣ Correct time range with "Z"
    time_min = now.replace(microsecond=0).isoformat() + "Z"
    time_max = (now + timedelta(days=30)).replace(microsecond=0).isoformat() + "Z"

    events_url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    params = {
        "singleEvents": "true",
        "orderBy": "startTime",
        "timeMin": time_min,
        "timeMax": time_max,
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    # 3️⃣ Call Google Calendar
    response = requests.get(events_url, headers=headers, params=params)

    # 4️⃣ Retry once if token expired
    if response.status_code == 401:
        print("⚠ Google returned 401 → refreshing token and retrying.")

        new_token, expires_in = google_refresh_access_token(refresh_token)
        if not new_token:
            raise HTTPException(status_code=400, detail="Failed to refresh token (401)")

        access_token = new_token
        expiry = now + timedelta(seconds=expires_in or 3600)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET google_calendar_access_token = %s,
                google_calendar_token_expiry = %s
            WHERE id = %s
        """, (access_token, expiry, user_id))
        conn.commit()
        conn.close()

        response = requests.get(events_url, headers={"Authorization": f"Bearer {access_token}"}, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Google API error: {response.text}")

    items = response.json().get("items", [])

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



def refresh_google_access_token(refresh_token: str):
    """
    Refreshes Google access token using refresh_token
    """
    data = {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }

    resp = requests.post(GOOGLE_TOKEN_URL, data=data)

    if resp.status_code != 200:
        print("Failed refresh:", resp.text)
        return None

    return resp.json().get("access_token")


@app.post("/calendar/create-event")
def create_calendar_event(event: CalendarEvent, request: Request):

    # 1. Extract the *real* JWT token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]   # <-- ΜΟΝΟ το JWT
    user_id = get_user_id_from_query_token(token)

    # 2. Get user Google refresh token from DB
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT google_calendar_refresh_token
        FROM users
        WHERE id = %s
    """, (user_id,))

    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")

    refresh_token = row[0]

    # 3. Refresh access token
    access_token = refresh_google_access_token(refresh_token)

    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to refresh Google access token")

    # 4. Prepare Google Calendar event payload
    google_event = {
        "summary": event.summary,
        "description": event.description,
        "start": {
            "dateTime": event.start,
            "timeZone": event.timezone
        },
        "end": {
            "dateTime": event.end,
            "timeZone": event.timezone
        }
    }

    # 5. Create event via Google Calendar API
    resp = requests.post(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {access_token}"},
        json=google_event
    )

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=400, detail=f"Google API Error: {resp.text}")

    return {
        "message": "Event created",
        "event": resp.json()
    }


@app.post("/calendar/batch-create-events")
def calendar_batch_create_events(payload: CalendarBatch, request: Request):

    # 1. AUTH TOKEN
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = auth_header.replace("Bearer ", "")
    user_id = get_user_id_from_token(token)

    # 2. GET USER REFRESH TOKEN
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT google_calendar_refresh_token
        FROM users
        WHERE id = %s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        raise HTTPException(status_code=400, detail="Google Calendar not connected")

    refresh_token = row[0]

    # 3. REFRESH ACCESS TOKEN
    access_token = refresh_google_access_token(refresh_token)
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to refresh Google access token")

    created = 0
    failed = 0
    results = []

    # 4. FOR EACH EVENT → CREATE GOOGLE CALENDAR EVENT
    for ev in payload.events:

        google_event = {
            "summary": ev.summary,
            "description": ev.description,
            "start": {
                "dateTime": ev.start,
                "timeZone": ev.timezone
            },
            "end": {
                "dateTime": ev.end,
                "timeZone": ev.timezone
            }
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

    return {
        "status": "ok",
        "created": created,
        "failed": failed,
        "events": results
    }

@app.post("/calendar/parse-plan")
def parse_calendar_plan(req: PlanRequest):

    plan_text = req.plan.strip()

    if not plan_text:
        return {"valid": False, "reason": "Empty plan input"}

    # Build LLM prompt
    full_prompt = f"""
You are a calendar event extraction engine.

Extract ALL social media post tasks that include a date or time from the user's plan.

Return ONLY valid JSON, with an array called "events".  
Each event MUST follow this strict format:

{{
  "summary": "...",
  "description": "...",
  "start": "YYYY-MM-DDTHH:MM:SS",
  "end": "YYYY-MM-DDTHH:MM:SS",
  "timezone": "Europe/Athens"
}}

Rules:
- If no time is provided, default start time = 09:00 and duration = 30 minutes.
- If only a date is provided, use 09:00–09:30.
- If a range is provided (e.g., “between 17:00 and 18:00”), use those times.
- If a day name is used (“Tuesday”, “Next Friday”), convert to the next occurrence of that weekday.
- Do NOT hallucinate events.
- Do NOT include explanations or markdown.
- If no events can be extracted, return: {{ "events": [] }}

User plan:
<<<PLAN>>>
{plan_text}
    """

    try:
        llm = ChatOpenAI(model=llm_model, temperature=0, api_key=OPENAI_API_KEY)
        raw = llm.invoke(full_prompt).content.strip()

        data = json.loads(raw)
        events = data.get("events", [])

        if not events:
            return {"valid": False, "reason": "No events found in plan"}

        return {
            "valid": True,
            "events": events
        }

    except Exception as e:
        print("❌ LLM PLAN PARSE ERROR:", e)
        return {"valid": False, "reason": "Failed to parse plan"}
        
        
@app.get("/google-gmail/connect")
def gmail_connect(request: Request):

    # 1. Get JWT from query
    token = request.query_params.get("token")
    user_id = get_user_id_from_query_token(token)

    # 2. Build Google OAuth URL
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

@app.get("/google-gmail/callback")
def gmail_callback(code: str = None, state: str = None):

    if not code:
        return {"error": "Missing authorization code"}

    # state = user_id
    user_id = int(state)

    # Exchange code → tokens
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_GMAIL_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(GOOGLE_TOKEN_URL, data=data)

    if token_resp.status_code != 200:
        return {
            "error": "Failed to exchange code",
            "details": token_resp.text
        }

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")

    if not refresh_token:
        print("⚠ No refresh token returned — Google may not have shown consent screen.")

    # Compute expiry timestamp
    expiry = datetime.utcnow() + timedelta(seconds=expires_in or 3600)

    # Save tokens in DB
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET gmail_access_token = %s,
            gmail_refresh_token = %s,
            gmail_token_expiry = %s
        WHERE id = %s
    """, (access_token, refresh_token, expiry, user_id))
    conn.commit()
    conn.close()

    # Redirect to frontend
    return RedirectResponse("https://myaips.cloud/?gmail_connected=1")




@app.get("/google-gmail/check")
def gmail_check(user_id: int = Depends(get_user_id_from_token)):

    # 1. Load tokens from DB
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT gmail_access_token,
               gmail_refresh_token,
               gmail_token_expiry
        FROM users WHERE id = %s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=400, detail="User not found")

    access_token, refresh_token, expiry = row

    if not refresh_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    # 2. Refresh if expired
    now = datetime.utcnow().replace(tzinfo=pytz.UTC)

    if not access_token or not expiry or now >= expiry:
        new_token, expires_in = refresh_google_token(refresh_token)
        if not new_token:
            raise HTTPException(status_code=400, detail="Failed to refresh Gmail token")

        access_token = new_token
        expiry = now + timedelta(seconds=expires_in or 3600)

        # Save
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET gmail_access_token = %s,
                gmail_token_expiry = %s
            WHERE id = %s
        """, (access_token, expiry, user_id))
        conn.commit()
        conn.close()

    # 3. Call Gmail API → list messages
    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=5"

    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})

    if resp.status_code != 200:
        return {
            "error": "Gmail API error",
            "details": resp.text
        }

    return resp.json()


@app.get("/google-gmail/messages")
def gmail_messages(limit: int = 20, user_id: int = Depends(get_user_id_from_token)):

    # 1. Load tokens
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT gmail_access_token,
               gmail_refresh_token,
               gmail_token_expiry
        FROM users WHERE id = %s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=400, detail="User not found")

    access_token, refresh_token, expiry = row

    if not refresh_token:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    # 2. Refresh if expired
    now = datetime.utcnow().replace(tzinfo=pytz.UTC)

    if not access_token or not expiry or now >= expiry:
        new_token, expires_in = refresh_google_token(refresh_token)
        if not new_token:
            raise HTTPException(status_code=400, detail="Failed to refresh Gmail token")

        access_token = new_token
        expiry = now + timedelta(seconds=expires_in or 3600)

        # Save in DB
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users
            SET gmail_access_token = %s,
                gmail_token_expiry = %s
            WHERE id = %s
        """, (access_token, expiry, user_id))
        conn.commit()
        conn.close()

    # 3. List message IDs
    list_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults={limit}"
    list_resp = requests.get(
        list_url,
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if list_resp.status_code != 200:
        return {"error": list_resp.text}

    message_ids = list_resp.json().get("messages", [])
    full_messages = []

    # 4. Fetch each message (full data)
    for msg in message_ids:
        msg_id = msg["id"]
        detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=full"
        detail_resp = requests.get(
            detail_url,
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if detail_resp.status_code != 200:
            continue

        data = detail_resp.json()

        # Extract header fields
        headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}

        subject = headers.get("Subject", "")
        sender = headers.get("From", "")
        date = headers.get("Date", "")

        snippet = data.get("snippet", "")

        # attachments check
        attachments = []
        parts = data.get("payload", {}).get("parts", []) or []
        for part in parts:
            if "filename" in part and part["filename"]:
                attachments.append(part["filename"])

        full_messages.append({
            "id": msg_id,
            "subject": subject,
            "from": sender,
            "date": date,
            "snippet": snippet,
            "attachments": attachments,
        })

    return {"messages": full_messages}


@app.get("/google-gmail/search")
def gmail_search(q: str, user_id: int = Depends(get_user_id_from_token)):

    # 1. Load tokens
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT gmail_access_token,
               gmail_refresh_token,
               gmail_token_expiry
        FROM users WHERE id = %s
    """, (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(400, "User not found")

    access_token, refresh_token, expiry = row

    if not refresh_token:
        raise HTTPException(400, "Gmail not connected")

    # 2. Refresh token if expired
    
    now = datetime.utcnow().replace(tzinfo=pytz.UTC)

    # 🔧 FIX: expiry από PostgreSQL έρχεται NAIVE → το κάνουμε aware
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=pytz.UTC)  
    
    if not access_token or not expiry or now >= expiry:
        new_token, expires_in = refresh_google_token(refresh_token)
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

    # 3. Search Gmail
    search_url = (
        "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        f"?q={q}&maxResults=20"
    )

    list_resp = requests.get(
        search_url,
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if list_resp.status_code != 200:
        return {"error": list_resp.text}

    messages = list_resp.json().get("messages", [])
    full_messages = []

    for msg in messages:
        msg_id = msg["id"]

        detail_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=full"
        detail_resp = requests.get(
            detail_url,
            headers={"Authorization": f"Bearer {access_token}"}
        )

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

