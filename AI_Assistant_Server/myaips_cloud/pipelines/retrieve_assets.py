from typing import List, Dict, Any

from qdrant_client.http.models import (
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Range,
)


from db_users import get_vector_store_for_user_asset_text


def retrieve_assets_for_pages(
    user_id: int,
    document_id: str,
    pages: List[int],
) -> List[Dict[str, Any]]:
    """
    Fetch ALL assets for given document + pages.

    IMPORTANT:
    - page is NUMERIC → must use Range, NOT MatchValue
    """

    store = get_vector_store_for_user_asset_text(user_id)
    assets = []


    # Χρησιμοποιούμε MatchAny για να φέρουμε όλες τις σελίδες μαζί
    # Δημιουργία ενός ενιαίου φίλτρου για όλες τις σελίδες
    flt = Filter(
        must=[
            FieldCondition(
                key="metadata.user_id", 
                match=MatchValue(value=int(user_id)) # Force int
            ),
            FieldCondition(
                key="metadata.document_id", 
                match=MatchValue(value=str(document_id)) # Force string
            ),
            FieldCondition(
                key="metadata.page", 
                match=MatchAny(any=[int(p) for p in pages]) # Match οποιαδήποτε σελίδα από τη λίστα
            )
        ]
    )


    results, _ = store.client.scroll(
        collection_name=store.collection_name,
        scroll_filter=flt,
        limit=100,
        with_payload=True, # Σιγουρευόμαστε ότι φέρνουμε το payload
        with_vectors=False
    )

    assets.extend(results)

    return assets
