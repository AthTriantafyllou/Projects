# app/pipelines/extract_tables_from_docx.py

from typing import List
from langchain.schema import Document
from docx import Document as DocxDocument


def extract_tables_from_docx(path: str, filename: str) -> List[dict]:
    """
    Extract tables from DOCX file using python-docx.
    Each table becomes:
    {
        "page": None,  # DOCX has no page information
        "table_index": int,
        "table": [ [rowcells...] ]
        "source": filename
    }
    """
    doc = DocxDocument(path)
    tables = []

    for t_index, table in enumerate(doc.tables):
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append(cells)

        tables.append({
            "page": None,
            "table_index": t_index,
            "table": rows,
            "source": filename,
        })

    return tables
