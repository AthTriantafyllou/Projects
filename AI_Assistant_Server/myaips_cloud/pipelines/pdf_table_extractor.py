# app/pipelines/pdf_table_extractor.py

from dataclasses import dataclass
from typing import List, Optional, Any
import fitz  # PyMuPDF


@dataclass
class ExtractedTable:
    page: int
    order: float
    markdown: str
    bbox: Optional[tuple] = None  # (x0, y0, x1, y1)


def _to_markdown(table_matrix: List[List[Any]]) -> str:
    """
    Convert a 2D matrix to a Markdown table.
    If the matrix is empty or too irregular, fallback to TSV-like text.
    """
    if not table_matrix:
        return ""

    # Normalize rows to strings and same length
    max_cols = max((len(r) for r in table_matrix), default=0)
    if max_cols == 0:
        return ""

    rows: List[List[str]] = []
    for r in table_matrix:
        rr = [(str(c).strip() if c is not None else "") for c in r]
        if len(rr) < max_cols:
            rr += [""] * (max_cols - len(rr))
        rows.append(rr)

    # If only 1 row, return as TSV-like (not a real table)
    if len(rows) == 1:
        return "\t".join(rows[0])

    header = rows[0]
    body = rows[1:]

    md = []
    md.append("| " + " | ".join(header) + " |")
    md.append("| " + " | ".join(["---"] * max_cols) + " |")
    for r in body:
        md.append("| " + " | ".join(r) + " |")

    return "\n".join(md)


def extract_tables_from_pdf(pdf_path: str) -> List[ExtractedTable]:
    """
    Extract tables from PDF using PyMuPDF table detector (if available).

    Returns a list of ExtractedTable with page/order/markdown/bbox.
    Does NOT create images. Tables remain structured text.
    """

    doc = fitz.open(pdf_path)
    out: List[ExtractedTable] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_number = page_index + 1

        # PyMuPDF table extraction exists in newer versions.
        # If not available, simply skip (no crash).
        find_tables = getattr(page, "find_tables", None)
        if not callable(find_tables):
            continue

        try:
            tables = page.find_tables()
        except Exception:
            continue

        # tables.tables is a list of detected table objects
        detected = getattr(tables, "tables", None) or []
        if not detected:
            continue

        # Sort by y0 (top-to-bottom) for stable "order"
        def _y0(t):
            bbox = getattr(t, "bbox", None)
            if bbox is None:
                return 0
            try:
                return float(bbox.y0)
            except Exception:
                return 0

        detected_sorted = sorted(detected, key=_y0)

        base_order = 0.50  # keep away from image order (0.01..)
        step = 0.01

        for i, t in enumerate(detected_sorted):
            # Extract matrix
            matrix = []
            try:
                # Preferred: extract() returns list-of-lists
                matrix = t.extract()
            except Exception:
                matrix = []

            md = _to_markdown(matrix).strip()
            if not md:
                continue

            bbox = None
            try:
                bb = getattr(t, "bbox", None)
                if bb is not None:
                    bbox = (float(bb.x0), float(bb.y0), float(bb.x1), float(bb.y1))
            except Exception:
                bbox = None

            out.append(
                ExtractedTable(
                    page=page_number,
                    order=base_order + i * step,
                    markdown=md,
                    bbox=bbox,
                )
            )

    return out
