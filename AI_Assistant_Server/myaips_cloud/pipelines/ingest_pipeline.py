# app/pipelines/ingest_pipeline.py

import os
import asyncio
from typing import List

from pipelines.structural_parser import build_structure_from_pdf
from pipelines.semantic_units import SemanticUnit
from pipelines.teacher_analyzer import TeacherAnalyzer

# Στο μέλλον θα προσθέσεις κι άλλους εδώ
ANALYZER_REGISTRY = {
    "teacher": TeacherAnalyzer(),
    # "lawyer": LawyerAnalyzer(),
    # "art_director": ArtDirectorAnalyzer(),
}


def get_analyzer(assistant_type: str):
    return ANALYZER_REGISTRY.get(assistant_type, ANALYZER_REGISTRY["teacher"])


async def ingest_document(
    tmp_path: str,
    original_name: str,
    user_id: int,
    assistant_type: str,
    document_id: str,
    vector_store_units,
):
    """
    Unified ingestion pipeline.
    One logic, multiple analyzers.
    """

    print("\n==============================")
    print("🚀 INGEST V2 START")
    print(f"user={user_id} | assistant={assistant_type}")
    print(f"document_id={document_id}")
    print("==============================\n")

    # --------------------------------------------------
    # 1) Build common structure (assistant-agnostic)
    # --------------------------------------------------
    structure = build_structure_from_pdf(
        pdf_path=tmp_path,
        user_id=user_id,
        document_id=document_id,
        original_name=original_name,
    )

    print(f"📄 Text blocks: {len(structure.text_blocks)}")
    print(f"🖼️ Assets: {len(structure.assets)}")

    # --------------------------------------------------
    # 2) Semantic analysis (assistant-specific)
    # --------------------------------------------------
    analyzer = get_analyzer(assistant_type)
    units: List[SemanticUnit] = analyzer.extract_units(structure)

    print(f"🧠 Semantic units extracted: {len(units)}")

    if not units:
        print("⚠️ No semantic units produced. Abort.")
        return {"units": 0}

    # --------------------------------------------------
    # 3) Store units in Qdrant (UNITS collection)
    # --------------------------------------------------
    docs_for_qdrant = []

    for u in units:
        docs_for_qdrant.append({
            "page_content": u.primary_text,
            "metadata": {
                "user_id": u.user_id,
                "assistant_type": u.assistant_type,
                "document_id": u.document_id,
                "unit_id": u.unit_id,
                "unit_type": u.unit_type,
                "page_start": u.page_start,
                "page_end": u.page_end,
            }
        })

    # LangChain-style add
    vector_store_units.add_documents(docs_for_qdrant)

    print("✅ Units stored in Qdrant")

    return {
        "units": len(units),
        "assets": len(structure.assets),
    }
