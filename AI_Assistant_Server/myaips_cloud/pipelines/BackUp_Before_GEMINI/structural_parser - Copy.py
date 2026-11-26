# app/pipelines/structural_parser.py

import uuid
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from PyPDF2 import PdfReader

from pipelines.pdf_asset_extractor import extract_assets_from_pdf
from pipelines.models import TextBlock, Asset, DocumentStructure


# --------------------------------------------------
# Structural parser for PDF (FINAL)
# --------------------------------------------------

def build_structure_from_pdf(
    pdf_path: str,
    user_id: int,
    document_id: str,
    original_name: str,
) -> DocumentStructure:
    """
    FINAL, CLEAN PDF STRUCTURAL PARSER

    GUARANTEES:
    - Every page -> exactly ONE TextBlock
    - Text ALWAYS stays text (never rendered as image)
    - Images / diagrams handled ONLY by pdf_asset_extractor
    - No screenshots, no tables-as-images, no duplication
    """

    text_blocks: List[TextBlock] = []

    reader = PdfReader(pdf_path)
    global_order = 1.0

    # --------------------------------------------------
    # 1) TEXT BLOCKS (ALWAYS, 1 per page)
    # --------------------------------------------------
    for page_index, page in enumerate(reader.pages):
        page_number = page_index + 1

        try:
            extracted_text = page.extract_text() or ""
        except Exception:
            extracted_text = ""

        text_blocks.append(
            TextBlock(
                block_id=f"tb_{uuid.uuid4().hex[:8]}",
                page=page_number,
                order=global_order,
                text=extracted_text.strip(),
            )
        )

        global_order += 1.0

    # --------------------------------------------------
    # 2) VISUAL ASSETS (IMAGES + DIAGRAMS)
    # --------------------------------------------------
    assets = extract_assets_from_pdf(
        pdf_path=pdf_path,
        user_id=user_id,
        document_id=document_id,
    )

    return DocumentStructure(
        document_id=document_id,
        user_id=user_id,
        text_blocks=text_blocks,
        assets=assets,
    )
