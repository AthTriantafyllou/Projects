# app/pipelines/structural_parser_text.py

import uuid
from typing import List

from langchain.schema import Document
from langchain_community.document_loaders import UnstructuredFileLoader

from pipelines.structural_parser import (
    DocumentStructure,
    TextBlock,
)


def build_structure_from_text_file(
    path: str,
    user_id: int,
    document_id: str,
    original_name: str,
) -> DocumentStructure:
    """
    Structural parsing for TXT / DOCX / HTML.
    No assets, only text blocks.
    """

    loader = UnstructuredFileLoader(path)
    docs: List[Document] = loader.load()

    text_blocks: List[TextBlock] = []
    order = 1.0

    for d in docs:
        text = (d.page_content or "").strip()
        if not text:
            continue

        text_blocks.append(
            TextBlock(
                block_id=f"tb_{uuid.uuid4().hex[:8]}",
                page=1,          # logical page
                order=order,
                text=text,
            )
        )
        order += 1.0

    return DocumentStructure(
        document_id=document_id,
        user_id=user_id,
        text_blocks=text_blocks,
        assets=[],   # ❗ no images for txt/docx
    )
