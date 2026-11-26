# app/pipelines/grouping_images.py

from typing import List, Optional, Dict
from langchain.schema import Document


def load_text_chunks_for_document(text_chunks: List[Document]) -> Dict[int, List[Document]]:
    pages: Dict[int, List[Document]] = {}

    for doc in text_chunks:
        page = doc.metadata.get("page")
        if page is None:
            continue
        pages.setdefault(page, []).append(doc)

    for page in pages:
        pages[page] = sorted(
            pages[page],
            key=lambda d: d.metadata.get("group_order", 999999),
        )

    return pages


def find_nearest_text_group_for_image(
    image_page: Optional[int],
    text_chunks_by_page: Dict[int, List[Document]],
) -> Optional[Document]:

    if image_page is None:
        return None

    # Same page
    if image_page in text_chunks_by_page:
        return text_chunks_by_page[image_page][-1]

    # Previous page
    if image_page - 1 in text_chunks_by_page:
        return text_chunks_by_page[image_page - 1][-1]

    # Next page
    if image_page + 1 in text_chunks_by_page:
        return text_chunks_by_page[image_page + 1][0]

    return None


def assign_group_to_image_chunk(
    image_doc: Document,
    nearest_text_chunk: Optional[Document],
):
    # No parent → place in its own group
    if nearest_text_chunk is None:
        image_doc.metadata.update({
            "group_id": f"image_orphan_{image_doc.metadata.get('page', 'X')}",
            "group_type": "image_block",
            "group_order": 1.0,
            "role_in_document": "image",
        })
        return

    parent_group_id = nearest_text_chunk.metadata.get("group_id")
    parent_group_type = nearest_text_chunk.metadata.get("group_type")
    parent_order = nearest_text_chunk.metadata.get("group_order", 0)

    # Fractional stacking for images:
    # Text = group_order N
    # Image = N + 0.01, N + 0.02, ...
    next_fraction = 0.01

    image_doc.metadata.update({
        "group_id": parent_group_id,
        "group_type": parent_group_type,
        "group_order": parent_order + next_fraction,
        "role_in_document": "image",
    })
