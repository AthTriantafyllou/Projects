from fastapi import APIRouter, Depends, HTTPException
from auth import get_user_id_from_token
from db import get_connection
from db_users import get_vector_store_for_user
from psycopg2.extras import RealDictCursor

router = APIRouter()


# -----------------------------
# DB HELPERS
# -----------------------------

def mark_message_learned(user_id: int, message_id: str):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO learned_message_refs (user_id, message_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (user_id, message_id))
        conn.commit()


def get_learn_status_batch(user_id: int, message_ids: list):
    conn = get_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT message_id
            FROM learned_message_refs
            WHERE user_id = %s AND message_id = ANY(%s::uuid[])
        """, (user_id, message_ids))
        rows = cur.fetchall()
    return {row["message_id"]: True for row in rows}


def store_shared_message(user_id: int, message_id: str, text: str):
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO shared_messages (user_id, message_id, text)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (user_id, message_id, text))
        share_id = cur.fetchone()[0]
        conn.commit()
    return share_id


def get_shared_message(share_id: str):
    conn = get_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT text
            FROM shared_messages
            WHERE id = %s
        """, (share_id,))
        row = cur.fetchone()
    return row


# -----------------------------
# ROUTES
# -----------------------------

@router.post("/assistant")
def learn_assistant_reply(data: dict, user_id: int = Depends(get_user_id_from_token)):

    text = data.get("text")
    message_id = data.get("message_id")

    if not text or not message_id:
        raise HTTPException(status_code=400, detail="Missing text or message_id.")

    # 1. Store in Qdrant
    vector_store = get_vector_store_for_user(user_id)
    vector_store.add_texts([text])

    # 2. Mark as learned in Postgres
    mark_message_learned(user_id, message_id)

    return {"status": "ok", "learned": True, "message_id": message_id}


@router.post("/status")
def learn_status(data: dict, user_id: int = Depends(get_user_id_from_token)):
    message_ids = data.get("message_ids", [])
    if not message_ids:
        return {"statuses": {}}

    statuses = get_learn_status_batch(user_id, message_ids)
    return {"statuses": statuses}


@router.post("/share")
def share_message(data: dict, user_id: int = Depends(get_user_id_from_token)):

    text = data.get("text")
    message_id = data.get("message_id")

    if not text:
        raise HTTPException(status_code=400, detail="Missing text.")

    share_id = store_shared_message(user_id, message_id, text)

    return {
        "share_id": share_id,
        "share_url": f"https://myaips.cloud/share/{share_id}"
    }


@router.get("/share/{share_id}")
def get_share(share_id: str):
    row = get_shared_message(share_id)
    if not row:
        raise HTTPException(status_code=404, detail="Shared message not found.")
    return {"text": row["text"]}
