# app/pipelines/table_extractor.py

import os
from dataclasses import dataclass
from typing import List

@dataclass
class ExtractedTable:
    page: int
    html: str  # raw HTML from PyMuPDF extraction


def extract_tables_from_pdf(path: str) -> List[ExtractedTable]:
    """
    Extract tables ONLY from PDF using PyMuPDF.
    For docx/txt → returns empty list.
    """
    ext = os.path.splitext(path)[1].lower()

    # Only PDFs support table extraction
    if ext != ".pdf":
        return []

    try:
        import fitz  # PyMuPDF
    except Exception as e:
        print("❌ PyMuPDF not installed:", e)
        return []

    tables: List[ExtractedTable] = []

    try:
        doc = fitz.open(path)
    except Exception as e:
        print("❌ ERROR opening PDF in PyMuPDF:", e)
        return []

    # Iterate pages
    for page_index in range(len(doc)):
        try:
            page = doc.load_page(page_index)
            blocks = page.get_text("blocks")  # each block may contain HTML

            for block in blocks:
                text = block[4]  # PyMuPDF returns (x0, y0, x1, y1, text, block_no)
                if not isinstance(text, str):
                    continue

                if "<table" in text.lower():  # crude detection of tables
                    tables.append(
                        ExtractedTable(
                            page=page_index + 1,
                            html=text,
                        )
                    )

        except Exception as e:
            print(f"⚠️ Error extracting tables from page {page_index+1}: {e}")
            continue

    return tables
