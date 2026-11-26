from typing import List, Tuple
from langchain.schema import Document

from db_users import get_vector_store_for_user_units
from qdrant_client.http import models as qmodels


def retrieve_units(user_id: int, question: str, k: int = 5) -> List[Document]:
    """
    Returns top-k units (chunks) for a question.

    Uses relevance scores (0..1) when possible, for stable thresholding.
    """
    RELEVANCE_THRESHOLD = 0.40  # tune later if needed
    store = get_vector_store_for_user_units(user_id)

    # Qdrant payload layout in LangChain Qdrant is typically:
    # payload = {"page_content": ..., "metadata": {...}}
    search_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="metadata.user_id",
                match=qmodels.MatchValue(value=int(user_id)),
            )
        ]
    )

    print(f"🔎 DEBUG: retrieve_units user_id={user_id} k={k}")

    # ------------------------------------------------------------
    # Prefer relevance scores (0..1): higher is better
    # ------------------------------------------------------------
    results: List[Tuple[Document, float]] = []

    try:
        # Newer LangChain interface
        results = store.similarity_search_with_relevance_scores(
            question,
            k=k,
            filter=search_filter,
        )
        score_type = "relevance"
    except Exception:
        # Fallback: older interface
        raw_results = store.similarity_search_with_score(
            question,
            k=k,
            filter=search_filter,
        )
        # We cannot be sure if "score" is similarity or distance.
        # Heuristic: treat it as similarity if higher seems better (common in Qdrant),
        # otherwise convert distance->pseudo-relevance.
        scores = [s for _, s in raw_results] if raw_results else []
        score_type = "score"

        def to_relevance(s: float) -> float:
            # If it's already in [0,1], keep it.
            if 0.0 <= s <= 1.0:
                return float(s)
            # If it looks like a distance (positive, potentially >1), invert smoothly.
            # This makes smaller distances -> higher relevance.
            if s >= 0:
                return 1.0 / (1.0 + float(s))
            # If negative weirdness, clamp.
            return 0.0

        results = [(doc, to_relevance(score)) for doc, score in raw_results]

    # ------------------------------------------------------------
    # Manual safety check (defense in depth)
    # ------------------------------------------------------------
    safe_results = [
        (doc, rel) for doc, rel in results
        if int(doc.metadata.get("user_id", -1)) == int(user_id)
    ]

    if not safe_results:
        print("🔎 No results matched user_id after manual check.")
        return []

    best_rel = max([rel for _, rel in safe_results], default=0.0)
    context_found = best_rel >= RELEVANCE_THRESHOLD

    print(f"🔎 score_type={score_type} best_relevance={best_rel:.4f} context_found={context_found}")

    #if not context_found:
    #    return []

    print(f"best_relevance={best_rel:.4f}")

    if best_rel < RELEVANCE_THRESHOLD:
        # return top-k anyway, but fewer (e.g. top 2) to avoid noise
        safe_results.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in safe_results[:2]]


    # Return docs only (keep ordering by relevance)
    safe_results.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in safe_results]
