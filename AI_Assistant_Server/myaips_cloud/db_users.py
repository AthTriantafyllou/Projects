from db import get_connection
from fastapi import HTTPException
from qdrant_client import QdrantClient
from langchain_qdrant import Qdrant
from langchain_openai import OpenAIEmbeddings
from qdrant_client.http.models import Distance, VectorParams
import os


# --------------------------------------------------
# Qdrant + Embeddings (shared)
# --------------------------------------------------

qdrant_client = QdrantClient(url=os.getenv("QDRANT_URL", "http://qdrant:6333"))

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

VECTOR_SIZE = 1536


# --------------------------------------------------
# USERS (unchanged)
# --------------------------------------------------

def get_user_by_email(email: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            return cur.fetchone()


def create_user(email: str, name: str = None, google_id: str = None,
                password: str = None, role: str = "register",
                chat: bool = False):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, name, google_id, password, role, chat)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (email, name, google_id, password, role, chat)
            )
            conn.commit()
            return cur.fetchone()


def update_user_goal(user_id: int, goal: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET goal = %s, updated_at = NOW() WHERE id = %s RETURNING *;",
                (goal, user_id)
            )
            conn.commit()
            return cur.fetchone()


def get_user_by_google_id(google_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
            return cur.fetchone()


# --------------------------------------------------
# LEGACY: single user collection (KEEP AS-IS)
# --------------------------------------------------

def get_user_collection(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT vector_collection FROM users WHERE id = %s", (int(user_id),))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=500, detail=f"User {user_id} not found")

    collection = row[0]
    if not collection:
        raise HTTPException(status_code=500, detail=f"Vector collection not set for user {user_id}")

    return collection


def get_vector_store_for_user(user_id: int):
    collection = get_user_collection(user_id)
    return Qdrant(
        client=qdrant_client,
        collection_name=collection,
        embeddings=embeddings,
    )


def ensure_user_collection(user_id: int) -> str:
    """
    LEGACY: single collection per user (do not remove).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT vector_collection FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            current = row[0] if row else None

            if current:
                return current

            collection_name = f"user_{user_id}_vectors"
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )

            cur.execute(
                "UPDATE users SET vector_collection = %s WHERE id = %s",
                (collection_name, user_id)
            )
            conn.commit()
            return collection_name


# --------------------------------------------------
# ✅ NEW: UNITS VECTOR STORE
# --------------------------------------------------

def get_vector_store_for_user_units(user_id: int):
    collection_name = f"user_{user_id}_units"

    if not qdrant_client.collection_exists(collection_name):
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    return Qdrant(
        client=qdrant_client,
        collection_name=collection_name,
        embeddings=embeddings,
    )


# --------------------------------------------------
# ✅ NEW: ASSET TEXT VECTOR STORE
# --------------------------------------------------

def get_vector_store_for_user_asset_text(user_id: int):
    collection_name = f"user_{user_id}_asset_text"

    if not qdrant_client.collection_exists(collection_name):
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    return Qdrant(
        client=qdrant_client,
        collection_name=collection_name,
        embeddings=embeddings,
    )


# --------------------------------------------------
# GOOGLE LOGIN (unchanged)
# --------------------------------------------------

def get_or_create_google_user(google_id: str, email: str, name: str | None = None):
    user = get_user_by_google_id(google_id)
    if user:
        return user

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
            if row:
                user_id = row[0]
                cur.execute(
                    "UPDATE users SET google_id = %s, name = COALESCE(name, %s) WHERE id = %s",
                    (google_id, name, user_id)
                )
                conn.commit()
                return row

    new_user = create_user(
        email=email,
        name=name,
        google_id=google_id,
        password=None,
        role="google",
        chat=False,
    )

    ensure_user_collection(new_user[0])
    return new_user
