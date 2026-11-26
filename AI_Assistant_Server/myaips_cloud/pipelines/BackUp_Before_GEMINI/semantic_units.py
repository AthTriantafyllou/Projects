# app/pipelines/semantic_units.py

import uuid
from typing import List

from pipelines.structural_parser import DocumentStructure
from pipelines.semantic_models import SemanticUnit


def build_page_level_units(structure: DocumentStructure) -> List[SemanticUnit]:
    """
    INGESTION RULE (FINAL, STABLE):

    - 1 PDF page -> 1 SemanticUnit
    - No analyzer logic
    - No semantic merging
    - Assistant-agnostic ingestion
    """

    units: List[SemanticUnit] = []

    blocks = sorted(
        structure.text_blocks,
        key=lambda b: (b.page, b.order),
    )

    for block in blocks:
        units.append(
            SemanticUnit(
                unit_id=f"unit_{uuid.uuid4().hex[:10]}",
                user_id=structure.user_id,
                assistant_type="general",
                document_id=structure.document_id,
                unit_type="page",
                primary_text=block.text or "",
                page_start=block.page,
                page_end=block.page,
                meta={
                    "ingestion_mode": "page_level",
                },
                assets=[],  # assets indexed separately
            )
        )

    return units
