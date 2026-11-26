# app/pipelines/structural_parser.py

import uuid
from typing import List

from PyPDF2 import PdfReader

from pipelines.models import TextBlock, Asset, DocumentStructure
from pipelines.pdf_asset_extractor import extract_assets_from_pdf
from pipelines.pdf_table_extractor import extract_tables_from_pdf
from pipelines.equation_extractor import extract_equations_from_text_blocks
from pipelines.ocr_utils import ocr_pdf_page


# --------------------------------------------------
# Structural parser for PDF (FINAL + OCR + TABLES)
# --------------------------------------------------

def build_structure_from_pdf(
    pdf_path: str,
    user_id: int,
    document_id: str,
    original_name: str,
) -> DocumentStructure:
    """
    FINAL PDF STRUCTURAL PARSER (STABLE)

    GUARANTEES:
    - Every page -> exactly ONE TextBlock
    - Text stays TEXT (OCR fallback if scanned)
    - Images / diagrams via pdf_asset_extractor
    - Tables extracted as STRUCTURED TEXT
    - Equations extracted ONLY from text
    - No screenshots, no duplication
    """
    
    ##LANGUAGES GIA OCR
    lang_codes = ["en", "el", "pl"]
    
    text_blocks: List[TextBlock] = []
    assets: List[Asset] = []

    reader = PdfReader(pdf_path)
    global_order = 1.0

    # --------------------------------------------------
    # 1) TEXT BLOCKS (TEXT → OCR FALLBACK)
    # --------------------------------------------------
    for page_index, page in enumerate(reader.pages):
        page_number = page_index + 1

        extracted_text = ""

        try:
            extracted_text = page.extract_text() or ""
        except Exception:
            extracted_text = ""

        extracted_text = extracted_text.strip()

        # OCR fallback ONLY if text is missing / meaningless
        if len(extracted_text) < 30:
            try:
                extracted_text = ocr_pdf_page(pdf_path, page_index,lang_codes)
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
    # 1.5) EQUATIONS (FROM TEXT ONLY)
    # --------------------------------------------------
    equation_assets = extract_equations_from_text_blocks(text_blocks)
    assets.extend(equation_assets)

    # --------------------------------------------------
    # 2) VISUAL ASSETS (IMAGES + DIAGRAMS ONLY)
    # --------------------------------------------------
    visual_assets = extract_assets_from_pdf(
        pdf_path=pdf_path,
        user_id=user_id,
        document_id=document_id,
    )
    assets.extend(visual_assets)

    # --------------------------------------------------
    # 3) TABLES (STRUCTURED TEXT, NOT IMAGES)
    # --------------------------------------------------
    tables = extract_tables_from_pdf(pdf_path)

    for t in tables:
        assets.append(
            Asset(
                asset_id=f"table_{uuid.uuid4().hex[:8]}",
                page=t.page,
                asset_type="table",
                order=t.order,
                text=t.markdown,
                url=None,
                meta={
                    "source": "pdf_table_extractor",
                    "bbox": t.bbox,
                },
            )
        )

    return DocumentStructure(
        document_id=document_id,
        user_id=user_id,
        text_blocks=text_blocks,
        assets=assets,
    )
