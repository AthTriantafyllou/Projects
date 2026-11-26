import uuid
from typing import List, Dict, Any, Tuple
from langchain.text_splitter import RecursiveCharacterTextSplitter

from pipelines.structural_parser import DocumentStructure
from pipelines.semantic_models import SemanticUnit


def _union_bbox(bboxes: List[List[float]]) -> List[float] | None:
    """
    Union of multiple [x0,y0,x1,y1] bboxes.
    Returns None if no valid bbox.
    """
    valid = [b for b in bboxes if b and len(b) == 4]
    if not valid:
        return None
    x0 = min(b[0] for b in valid)
    y0 = min(b[1] for b in valid)
    x1 = max(b[2] for b in valid)
    y1 = max(b[3] for b in valid)
    return [x0, y0, x1, y1]


def build_smart_semantic_units(structure: DocumentStructure) -> List[SemanticUnit]:
    """
    Builds semantic chunks, but ALSO produces deterministic mapping:
    - which TextBlocks participate in each chunk
    - pages covered
    - union bbox per page (optional but very useful for asset linking)

    Output:
      SemanticUnit.meta contains:
        - chunk_index
        - block_ids: List[str]
        - pages: List[int]
        - bboxes_by_page: Dict[int, List[float]]  (union bbox)
    """

    # 1) Sort text blocks by page/order
    sorted_blocks = sorted(structure.text_blocks, key=lambda x: (x.page, x.order))

    if not sorted_blocks:
        return []

    # 2) Build full_text AND keep deterministic spans per block
    # Each span: (start_char, end_char, block_id, page, bbox)
    spans: List[Tuple[int, int, str, int, List[float] | None]] = []

    full_text_parts: List[str] = []
    cursor = 0

    for b in sorted_blocks:
        block_text = (b.text or "").strip()
        if not block_text:
            continue

        # Keep separator stable
        payload = block_text + "\n\n"
        start = cursor
        end = cursor + len(payload)

        full_text_parts.append(payload)
        spans.append((start, end, b.block_id, b.page, b.bbox))

        cursor = end

    full_text = "".join(full_text_parts).strip()
    if not full_text:
        return []

    # 3) Split
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    raw_chunks = splitter.split_text(full_text)
    if not raw_chunks:
        return []

    # 4) Convert chunks -> units with deterministic (start,end) scanning
    units: List[SemanticUnit] = []
    search_from = 0

    for i, chunk_text in enumerate(raw_chunks):
        chunk_text = chunk_text.strip()
        if not chunk_text:
            continue

        # Deterministic-ish location in full_text using progressive search.
        # Still not perfect for repeated text, but much safer than always searching from 0.
        start_idx = full_text.find(chunk_text, search_from)
        if start_idx == -1:
            # fallback: assume continuous
            start_idx = search_from

        end_idx = start_idx + len(chunk_text)
        search_from = max(start_idx + 1, end_idx - 50)  # keep forward progress

        # 5) Find overlapping blocks via spans
        block_ids: List[str] = []
        pages_set = set()
        bboxes_by_page: Dict[int, List[List[float]]] = {}

        for s_start, s_end, block_id, page, bbox in spans:
            # overlap condition
            if s_end <= start_idx:
                continue
            if s_start >= end_idx:
                break  # spans are ordered; we can early break

            block_ids.append(block_id)
            pages_set.add(page)

            if bbox and len(bbox) == 4:
                bboxes_by_page.setdefault(page, []).append(bbox)

        pages = sorted(pages_set) if pages_set else [1]
        page_start = pages[0]
        page_end = pages[-1]

        # Union bbox per page
        union_by_page: Dict[int, List[float]] = {}
        for p, bb_list in bboxes_by_page.items():
            u = _union_bbox(bb_list)
            if u:
                union_by_page[p] = u

        units.append(
            SemanticUnit(
                unit_id=f"unit_{uuid.uuid4().hex[:10]}",
                user_id=structure.user_id,
                assistant_type="general",
                document_id=structure.document_id,
                unit_type="chunk",
                primary_text=chunk_text,
                page_start=page_start,
                page_end=page_end,
                assets=[],
                meta={
                    "chunk_index": i,
                    "block_ids": block_ids,
                    "pages": pages,
                    "bboxes_by_page": union_by_page,
                },
            )
        )

    return units
