# app/pipelines/teacher_analyzer.py

import re
import uuid
from typing import List

from pipelines.structural_parser import DocumentStructure, TextBlock, Asset
from pipelines.semantic_models import SemanticUnit


# --------------------------------------------------
# Helpers
# --------------------------------------------------

EXERCISE_PATTERNS = (
    r"^\s*(άσκηση|ασκ\.?|exercise|question|problem)\b",
)


def is_exercise_start(text: str) -> bool:
    low = text.lower().strip()
    for p in EXERCISE_PATTERNS:
        if re.match(p, low):
            return True
    return False


# --------------------------------------------------
# Teacher Analyzer
# --------------------------------------------------

class TeacherAnalyzer(SemanticAnalyzer):
    """
    Extracts exercises and generic theory blocks.
    Produces SemanticUnit objects.
    """

    def extract_units(self, structure: DocumentStructure) -> List[SemanticUnit]:
        blocks = sorted(
            structure.text_blocks,
            key=lambda b: (b.page, b.order),
        )

        units: List[SemanticUnit] = []

        current_blocks: List[TextBlock] = []
        current_type: str = "theory"
        page_start: int = None

        def flush_unit():
            nonlocal current_blocks, current_type, page_start

            if not current_blocks:
                return

            text = "\n\n".join(b.text for b in current_blocks)

            page_end = current_blocks[-1].page

            unit = SemanticUnit(
                unit_id=f"unit_{uuid.uuid4().hex[:10]}",
                document_id=structure.document_id,
                user_id=structure.user_id,
                assistant_type="teacher",
                unit_type=current_type,
                primary_text=text,
                page_start=page_start,
                page_end=page_end,
                meta={},
                assets=[],
            )

            # attach assets (simple proximity rule)
            self._attach_assets(unit, structure.assets)

            units.append(unit)

            current_blocks = []
            current_type = "theory"
            page_start = None

        for block in blocks:
            text = block.text.strip()

            if is_exercise_start(text):
                flush_unit()
                current_type = "exercise"
                page_start = block.page
                current_blocks.append(block)
            else:
                if not current_blocks:
                    current_type = "theory"
                    page_start = block.page
                current_blocks.append(block)

        flush_unit()

        return units

    # --------------------------------------------------
    # Asset linking (teacher-specific, v1)
    # --------------------------------------------------

    def _attach_assets(self, unit: SemanticUnit, assets: List[Asset]):
        """
        Simple deterministic rule:
        - attach assets whose page is between page_start and page_end
        - order assets by page + order
        """

        for asset in assets:
            if unit.page_start <= asset.page <= unit.page_end:
                unit.assets.append({
                    "asset_id": asset.asset_id,
                    "role": "supporting",
                    "order": asset.page + asset.order,
                })

        unit.assets.sort(key=lambda a: a["order"])
