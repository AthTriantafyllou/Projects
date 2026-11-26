# app/utils/parser.py

import os
from typing import List
from langchain.schema import Document

# --- PDF loader: σταθερό & ελαφρύ ---
from PyPDF2 import PdfReader

# --- Unstructured loader for docx/txt ---
from langchain_community.document_loaders import UnstructuredFileLoader


def load_pdf_with_pypdf2(path: str, filename: str) -> List[Document]:
    """
    Σταθερός PDF loader με PyPDF2.
    Δεν απαιτεί εξωτερικά binaries (poppler/tesseract).
    Λειτουργεί 100% μέσα στο Docker.
    """
    reader = PdfReader(path)
    docs = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": filename,
                    "page": i + 1,
                },
            )
        )

    return docs


def load_universal_no_split(path: str, filename: str) -> List[Document]:
    """
    Ενιαίο loader:
    - PDF → PyPDF2 (σταθερό)
    - Όλα τα άλλα → Unstructured (docx, txt, html)
    Δεν κάνει split. Το split το κάνουν τα pipelines.
    """

    ext = os.path.splitext(filename)[1].lower()

    # --- PDF (σταθερό) ---
    if ext == ".pdf":
        return load_pdf_with_pypdf2(path, filename)

    # --- DOCX / TXT / others ---
    loader = UnstructuredFileLoader(path)
    docs = loader.load()

    # προσθέτουμε source metadata
    for d in docs:
        d.metadata = d.metadata or {}
        d.metadata["source"] = filename

    return docs
