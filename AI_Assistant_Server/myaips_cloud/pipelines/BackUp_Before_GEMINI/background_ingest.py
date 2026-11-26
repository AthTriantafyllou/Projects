# app/pipelines/background_ingest.py

import os

from pipelines.structural_parser import build_structure_from_pdf
from pipelines.structural_parser_text import build_structure_from_text_file
from pipelines.asset_enrichment import enrich_assets
from pipelines.asset_text_index import AssetTextIndexer
from pipelines.semantic_units import build_page_level_units
from pipelines.docx_to_pdf import convert_docx_to_pdf



from langchain.schema import Document

from db_users import (
    get_vector_store_for_user_units,
    get_vector_store_for_user_asset_text,
)


async def background_ingest(
    tmp_path: str,
    original_name: str,
    user_id: int,
    assistant_type: str,
    document_id: str,
):
    print("\n==============================")
    print("🚀 INGEST START")
    print(f"user={user_id} assistant={assistant_type}")
    print(f"document_id={document_id}")
    print("==============================\n")

    try:
        ext = os.path.splitext(original_name)[1].lower()

        if ext == ".pdf":
            pdf_path = tmp_path

        elif ext.lower() in [".docx", ".doc"]:
            print("📄 Converting DOCX → PDF")
            pdf_path = convert_docx_to_pdf(tmp_path)

        elif ext in (".txt",):
            structure = build_structure_from_text_file(
                path=tmp_path,
                user_id=user_id,
                document_id=document_id,
                original_name=original_name,
            )
            pdf_path = None

        else:
            raise ValueError(f"Unsupported file type: {ext}")

        # PDF-based ingestion (native PDF OR converted DOCX)
        if pdf_path:
            structure = build_structure_from_pdf(
                pdf_path=pdf_path,
                user_id=user_id,
                document_id=document_id,
                original_name=original_name,
            )

        print(f"📄 text_blocks = {len(structure.text_blocks)}")
        print(f"🖼️ assets = {len(structure.assets)}")

        # --------------------------------------------------
        # 2) ASSET ENRICHMENT (PDF only)
        # --------------------------------------------------
        if structure.assets:
            structure.assets = await enrich_assets(structure.assets, user_id=user_id)

        # --------------------------------------------------
        # 3) SEMANTIC ANALYSIS (Teacher)
        # --------------------------------------------------
        
        units = build_page_level_units(structure)

        print(f"📦 semantic units = {len(units)}")

        if not units:
            print("⚠️ No semantic units produced.")
            return

        # --------------------------------------------------
        # 4) STORE SEMANTIC UNITS
        # --------------------------------------------------
        units_store = get_vector_store_for_user_units(user_id)


        unit_docs = []

        for u in units:
            unit_docs.append(
                Document(
                    page_content=u.primary_text,
                    metadata={
                        "user_id": u.user_id,
                        "assistant_type": u.assistant_type,
                        "document_id": u.document_id,
                        "unit_id": u.unit_id,
                        "unit_type": u.unit_type,
                        "page_start": u.page_start,
                        "page_end": u.page_end,
                    }
                )
            )

        units_store.add_documents(unit_docs)


        # --------------------------------------------------
        # 5) STORE ASSET TEXT (PDF only)
        # --------------------------------------------------
        if structure.assets:
            asset_store = get_vector_store_for_user_asset_text(user_id)
            AssetTextIndexer(asset_store).index_assets(
                assets=structure.assets,
                user_id=user_id,
                document_id=document_id,
            )

        print("\n🎉 INGEST COMPLETED")

    except Exception as e:
        print("❌ INGEST ERROR:", e)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            print(f"🧹 temp file deleted: {tmp_path}")

        print("==============================")
        print("🏁 INGEST FINISHED")
        print("==============================\n")
