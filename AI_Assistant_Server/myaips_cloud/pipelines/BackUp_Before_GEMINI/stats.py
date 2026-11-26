# app/pipelines/stats.py

from typing import List, Dict, Any
from langchain.schema import Document

def analyze_document_stats(docs: List[Document]) -> Dict[str, Any]:
    """
    Υπολογίζει:
    - σύνολο χαρακτήρων
    - περίπου tokens
    - πλήθος σελίδων (PDF μόνο)
    - fallback page estimate για DOCX/TXT
    """
    total_chars = 0
    total_pages = set()

    for d in docs:
        text = d.page_content or ""
        total_chars += len(text)

        # PDF loaders δίνουν page/page_number
        page = d.metadata.get("page") or d.metadata.get("page_number")
        if page is not None:
            total_pages.add(page)

    approx_tokens = int(total_chars / 4)

    if total_pages:
        # PDF: έχουμε πραγματικές σελίδες
        page_count = len(total_pages)
    else:
        # DOCX/TXT: εκτίμηση σελίδων
        # industry standard: ~3000 chars per page
        estimated_pages = max(1, round(total_chars / 3000))
        page_count = estimated_pages

    return {
        "total_chars": total_chars,
        "approx_tokens": approx_tokens,
        "page_count": page_count,
        "doc_count": len(docs),
    }
