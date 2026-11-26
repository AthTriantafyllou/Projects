# app/pipelines/grouping.py

import re
from uuid import uuid4
from typing import List, Optional
from langchain.schema import Document


def extract_chunk_text(doc: Document) -> str:
    return (doc.page_content or "").strip()


def detect_group_type(text: str, assistant_type: str) -> Optional[str]:
    low = text.lower().strip()

    # Teacher
    if assistant_type == "teacher":
        if low.startswith(("άσκηση", "exercise", "ερώτηση", "δραστηριότητα", "activity")):
            return "exercise"

    # Lawyer
    if assistant_type == "lawyer":
        if low.startswith(("clause", "section", "article")):
            return "clause"

    # Social creator
    if assistant_type in ("social", "social_creator", "social_content_creator"):
        if low.startswith(("guideline", "section", "brand")):
            return "section"

    # Art director
    if assistant_type == "art_director":
        if low.startswith(("scene", "int.", "ext.")):
            return "scene"

    return None


class GroupState:
    def __init__(self):
        self.current_group_id: Optional[str] = None
        self.current_group_type: Optional[str] = None
        self.order: float = 0.0

    def new_group(self, group_type: str):
        self.current_group_type = group_type
        self.current_group_id = f"{group_type}_{uuid4().hex[:8]}"
        self.order = 1.0

    def next_item(self):
        self.order += 1.0


def apply_grouping_to_text_chunks(
    text_chunks: List[Document],
    assistant_type: str,
) -> List[Document]:

    state = GroupState()
    grouped_docs = []

    sorted_docs = sorted(
        text_chunks,
        key=lambda d: (
            d.metadata.get("page", 999999),
            d.metadata.get("chunk_index", 0),
        )
    )

    for doc in sorted_docs:
        text = extract_chunk_text(doc)
        detected_type = detect_group_type(text, assistant_type)

        if detected_type:
            state.new_group(detected_type)
        else:
            if state.current_group_id is None:
                state.new_group("block")
            else:
                state.next_item()

        meta = doc.metadata or {}
        meta["group_id"] = state.current_group_id
        meta["group_type"] = state.current_group_type
        meta["group_order"] = state.order
        doc.metadata = meta

        grouped_docs.append(doc)

    return grouped_docs


def filter_text_chunks(docs: List[Document]) -> List[Document]:
    text_docs = []
    for d in docs:
        modality = d.metadata.get("modality_type")
        if modality in (None, "text", "summary"):
            text_docs.append(d)
    return text_docs
