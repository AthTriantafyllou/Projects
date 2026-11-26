# app/pipelines/structural_parser.py

import uuid
from typing import List
from pipelines.models import TextBlock, Asset, DocumentStructure
from pipelines.pdf_asset_extractor import extract_content_unified
from pipelines.pdf_table_extractor import extract_tables_from_pdf
from pipelines.ocr_utils import ocr_pdf_page

def build_structure_from_pdf(pdf_path, user_id, document_id, original_name) -> DocumentStructure:
    # 1. Γλώσσες για OCR
    lang_codes = ["en", "el", "pl"]
    
    # 2. Καλούμε την εξαγωγή (Text + Visual Assets)
    text_blocks, visual_assets = extract_content_unified(pdf_path)
    
    # 3. OCR FALLBACK: Έλεγχος ανά σελίδα αν το κείμενο λείπει
    # Ομαδοποιούμε τα blocks ανά σελίδα για να δούμε αν η σελίδα είναι "άδεια"
    pages_with_text = set(tb.page for tb in text_blocks if len(tb.text.strip()) > 30)
    
    # Βρίσκουμε ποιες σελίδες δεν έχουν καθόλου κείμενο (π.χ. σκαναρισμένες)
    from PyPDF2 import PdfReader
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    
    for p_idx in range(total_pages):
        page_num = p_idx + 1
        if page_num not in pages_with_text:
            # Η σελίδα φαίνεται σκαναρισμένη -> Εκτέλεση OCR
            try:
                print(f"--- Running OCR for page {page_num} ---")
                ocr_text = ocr_pdf_page(pdf_path, p_idx, lang_codes)
                if ocr_text.strip():
                    text_blocks.append(TextBlock(
                        block_id=f"tb_ocr_{uuid.uuid4().hex[:8]}",
                        page=page_num,
                        order=0.0, # Το βάζουμε στην αρχή της σελίδας
                        text=ocr_text.strip()
                    ))
            except Exception as e:
                print(f"Error during OCR on page {page_num}: {e}")

    # 4. Εξαγωγή Πινάκων
    tables = extract_tables_from_pdf(pdf_path)
    
    all_assets = visual_assets

    for t in tables:
        bbox_list = None
        if t.bbox and len(t.bbox) == 4:
            bbox_list = [float(t.bbox[0]), float(t.bbox[1]), float(t.bbox[2]), float(t.bbox[3])]

        all_assets.append(
            Asset(
                asset_id=f"table_{uuid.uuid4().hex[:8]}",
                page=t.page,
                asset_type="table",
                order=t.order,
                text=t.markdown,
                bbox=bbox_list,
                context_text=None,  # optional: can be filled later if you decide
                meta={"bbox": bbox_list, "table_format": "markdown"} if bbox_list else {"table_format": "markdown"},
            )
        )


    return DocumentStructure(
        document_id=document_id,
        user_id=user_id,
        text_blocks=text_blocks,
        assets=all_assets
    )