
# app/vectorstores/summaries_store.py

from qdrant_client.http.models import Distance, VectorParams
from langchain_qdrant import Qdrant

from db_users import (
    get_user_collection,
    qdrant_client,
    embeddings,
)


EMBEDDING_DIM = 1536  # text-embedding-3-small


def get_summaries_vector_store_for_user(user_id: int) -> Qdrant:
    """
    Επιστρέφει Qdrant vector store για τα summaries του χρήστη.
    Χρησιμοποιεί βάση τη βασική collection του χρήστη + suffix "_summaries".
    Αν η collection δεν υπάρχει, τη δημιουργεί.
    """

    base_collection = get_user_collection(user_id)
    collection_name = f"{base_collection}_summaries"

    # Έλεγχος αν υπάρχει η collection
    existing = [c.name for c in qdrant_client.get_collections().collections]
    if collection_name not in existing:
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
        )

    # Δημιουργία LangChain Qdrant store
    return Qdrant(
        client=qdrant_client,
        collection_name=collection_name,
        embeddings=embeddings,
    )

