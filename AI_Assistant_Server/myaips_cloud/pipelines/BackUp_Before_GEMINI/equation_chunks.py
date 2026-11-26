# app/pipelines/equation_chunks.py

import re
from langchain.schema import Document
from datetime import datetime

MATH_CHARS = set("=+-/*^_()[]{}<>∑∫≈≃≅≤≥πλμ·⋅")


def looks_like_equation(line: str) -> bool:
    line = line.strip()
    if len(line) < 3:
        return False
    if not any(ch in line for ch in MATH_CHARS):
        return False
    if len(line.split()) > 10:
        return False
    if "=" in line:
        return True
    math_count = sum(1 for ch in line if ch in MATH_CHARS)
    return math_count >= max(2, len(line) * 0.15)



def extract_equation_docs_from_text_chunk(
    chunk: Document,
    user_id: int,
    assistant_type: str,
    document_id: str,
):
    eq_docs = []
    seen = set()

    page = chunk.metadata.get("page")
    group_id = chunk.metadata.get("group_id")
    group_type = chunk.metadata.get("group_type")
    order_base = chunk.metadata.get("group_order", 0)

    base_meta = {
        "user_id": user_id,
        "assistant_type": assistant_type,
        "document_id": document_id,
        "page": page,
        "group_id": group_id,
        "group_type": group_type,
        "role_in_document": "equation",
        "modality_type": "equation",
        "subject_tags": chunk.metadata.get("subject_tags"),
        "language": chunk.metadata.get("language"),
        "created_at": datetime.utcnow().isoformat(),
    }

    local_index = 0
    for line in chunk.page_content.split("\n"):
        if looks_like_equation(line):
            eq = line.strip()
            if eq in seen:
                continue
            seen.add(eq)

            meta = base_meta.copy()
            meta["group_order"] = order_base + (local_index + 1) * 0.01
            meta["latex"] = eq

            eq_docs.append(Document(page_content=eq, metadata=meta))
            local_index += 1

    return eq_docs
