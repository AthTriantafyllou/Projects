"""
Group-based layout reconstruction for RAG.

Εδώ υλοποιούμε το expand_group() που:
- παίρνει ένα seed_doc (με group_id)
- φέρνει όλα τα docs του ίδιου group από το Qdrant
- τα ταξινομεί με βάση page, group_order κ.λπ.
- τα μετατρέπει σε "layout-aware" Markdown block:
  - headings
  - paragraphs
  - images
  - equations
  - tables
  - summaries
"""

from typing import List, Dict, Any, Tuple, Optional

from langchain.schema import Document


# ---------------------------------------------------------
# Helper: fetch all documents for a given group_id
# ---------------------------------------------------------
def _fetch_group_docs(
    vector_store,
    base_filter: Dict[str, Any],
    group_id: str,
    k: int = 100,
) -> List[Document]:
    """
    Χρησιμοποιεί το ίδιο vector_store (Qdrant via LangChain)
    αλλά κάνει "dummy" similarity search με filter group_id,
    ώστε να πάρουμε ΟΛΑ τα docs του group.
    """

    # Qdrant filter: base_filter + group_id
    local_filter = {
        "must": list(base_filter.get("must", [])) + [
            {"key": "group_id", "match": {"value": group_id}},
        ]
    }

    try:
        results = vector_store.similarity_search_with_score(
            query="dummy",  # δεν μας ενδιαφέρει η ομοιότητα
            k=k,
            filter=local_filter,
        )
    except Exception:
        # Αν ο client δεν δέχεται "dummy", δοκίμασε κενό string
        results = vector_store.similarity_search_with_score(
            query=" ",
            k=k,
            filter=local_filter,
        )

    docs = [doc for doc, score in results]
    return docs


# ---------------------------------------------------------
# Helper: modality ranking (for stable ordering)
# ---------------------------------------------------------
def _modality_rank(modality: Optional[str]) -> int:
    """
    Δίνει priority ανά modality για να έχουμε σταθερή σειρά
    όταν group_order είναι ίδιο.
    """
    if modality is None:
        return 50

    modality = modality.lower()

    # Πρώτα headings, μετά text, μετά equations, tables, images, summaries
    if modality == "heading":
        return 0
    if modality == "text":
        return 10
    if modality == "equation":
        return 20
    if modality == "table":
        return 30
    if modality == "image":
        return 40
    if modality == "summary":
        return 60

    return 50


# ---------------------------------------------------------
# Helper: sort docs to approximate layout order
# ---------------------------------------------------------
def _sort_docs_layout(docs: List[Document]) -> List[Document]:
    """
    Ταξινομούμε:
    - πρώτα με βάση page (αν υπάρχει)
    - μετά group_order
    - μετά modality rank

    Αν στο μέλλον βάλεις 'bbox' στο metadata (π.χ. {"bbox": [x0,y0,x1,y1]}),
    μπορείς να το χρησιμοποιήσεις ως extra key (π.χ. y0).
    """

    def sort_key(d: Document) -> Tuple[int, float, int]:
        meta = d.metadata or {}
        page = meta.get("page", 999999)
        group_order = float(meta.get("group_order", 0))
        modality = meta.get("modality_type")
        m_rank = _modality_rank(modality)
        return (page, group_order, m_rank)

    return sorted(docs, key=sort_key)


# ---------------------------------------------------------
# Helper: render a single document into Markdown block
# ---------------------------------------------------------
def _render_doc_block(d: Document) -> str:
    meta = d.metadata or {}
    modality = (meta.get("modality_type") or "").lower()
    text = (d.page_content or "").strip()

    # 1) HEADING
    if modality == "heading":
        # heading_level: 1–6, default 2
        level = int(meta.get("heading_level", 2))
        level = max(1, min(level, 6))
        hashes = "#" * level
        return f"{hashes} {text}"

    # 2) TEXT / PARAGRAPH
    if modality in ("text", "", None):
        return text

    # 3) SUMMARY
    if modality == "summary":
        return f"[SUMMARY]\n{text}"

    # 4) EQUATION
    if modality == "equation":
        latex = meta.get("latex")
        if latex:
            return f"[EQUATION]\n$$\n{latex}\n$$"
        else:
            # Αν δεν έχουμε latex, βάζουμε inline την ίδια γραμμή
            return f"[EQUATION]\n`{text}`"

    # 5) TABLE
    if modality == "table":
        table_json = meta.get("table_json")
        if isinstance(table_json, list) and table_json:
            # table_json = [ {col1: val1, col2: val2, ...}, ... ]
            headers = list(table_json[0].keys())
            # Build Markdown table
            header_row = "| " + " | ".join(headers) + " |"
            sep_row = "| " + " | ".join("---" for _ in headers) + " |"
            data_rows = []
            for row in table_json:
                vals = [str(row.get(h, "")) for h in headers]
                data_rows.append("| " + " | ".join(vals) + " |")

            md_table = "\n".join([header_row, sep_row] + data_rows)
            return f"[TABLE]\n{md_table}"
        else:
            # fallback: χρησιμοποιούμε το flat text
            return f"[TABLE]\n{text}"

    # 6) IMAGE
    if modality == "image":
        image_url = meta.get("image_url") or ""
        caption = ""
        # Συνήθως στο page_content έχουμε caption + OCR text μαζί,
        # αλλά αν έχεις ξεχωριστό πεδίο meta["caption"] ή meta["ocr_text"], μπορείς να το εκμεταλλευτείς.
        caption_meta = meta.get("caption")
        ocr_text = meta.get("ocr_text")

        # caption: είτε από meta, είτε από αρχή του text
        if caption_meta:
            caption = caption_meta.strip()
        else:
            # Heuristic: πάρε την πρώτη γραμμή ως caption
            first_line = text.splitlines()[0] if text else ""
            caption = first_line.strip()

        # Markdown εικόνα
        img_md = ""
        if image_url:
            alt = caption or "Image"
            img_md = f"![{alt}]({image_url})"
        else:
            img_md = "[IMAGE]"

        # OCR σε blockquote, αν υπάρχει
        ocr_block = ""
        if ocr_text:
            ocr_block = f"\n> OCR: {ocr_text.strip()}"

        return f"{img_md}{ocr_block}"

    # 7) default fallback
    return text


# ---------------------------------------------------------
# PUBLIC API: expand_group
# ---------------------------------------------------------
def expand_group(
    vector_store,
    base_filter: Dict[str, Any],
    seed_doc: Document,
    k: int = 50,
) -> str:
    """
    Advanced, layout-aware group reconstruction.

    - Χρησιμοποιεί seed_doc.metadata["group_id"]
    - Φέρνει όλα τα docs του group από Qdrant
    - Τα ταξινομεί layout-wise
    - Τα μετατρέπει σε Markdown blocks ανά modality
    - Επιστρέφει ενιαίο string (ένα "learning unit" / "clause" / "scene")
    """

    group_id = seed_doc.metadata.get("group_id")
    if not group_id:
        # Αν δεν υπάρχει group_id, επιστρέφουμε απλά το κείμενο του seed doc
        return seed_doc.page_content or ""

    # 1) Fetch group docs
    docs = _fetch_group_docs(
        vector_store=vector_store,
        base_filter=base_filter,
        group_id=group_id,
        k=k,
    )

    if not docs:
        return seed_doc.page_content or ""

    # 2) Sort them in layout order
    docs_sorted = _sort_docs_layout(docs)

    # 3) Render each doc to Markdown block
    blocks: List[str] = []
    for d in docs_sorted:
        rendered = _render_doc_block(d)
        if rendered.strip():
            blocks.append(rendered.strip())

    # 4) Join everything with clear separation
    return "\n\n".join(blocks)
