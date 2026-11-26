# app/pipelines/background_ingest.py

import os
from pipelines.structural_parser import build_structure_from_pdf
from pipelines.structural_parser_text import build_structure_from_text_file
from pipelines.asset_enrichment import enrich_assets
from pipelines.asset_text_index import AssetTextIndexer
from pipelines.semantic_units import build_smart_semantic_units
from pipelines.docx_to_pdf import convert_docx_to_pdf
from pipelines.linking import link_units_and_assets


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
    print(f"🚀 INGEST START: {original_name}")
    print(f"User: {user_id} | Doc ID: {document_id}")
    print("==============================\n")

    try:
        ext = os.path.splitext(original_name)[1].lower()
        pdf_path = None

        # 1. Διαχείριση διαφορετικών τύπων αρχείων
        if ext == ".pdf":
            pdf_path = tmp_path
        elif ext in [".docx", ".doc"]:
            print("📄 Converting Word to PDF...")
            pdf_path = convert_docx_to_pdf(tmp_path)
        elif ext == ".txt":
            structure = build_structure_from_text_file(
                path=tmp_path, 
                user_id=user_id, 
                document_id=document_id, 
                original_name=original_name
            )
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        # 2. Structural Parsing (Unified Text & Visual Assets)
        # Χρησιμοποιεί τη νέα μέθοδο που βρίσκει ταυτόχρονα κείμενο και διαγράμματα
        if pdf_path:
            structure = build_structure_from_pdf(
                pdf_path=pdf_path,
                user_id=user_id,
                document_id=document_id,
                original_name=original_name,
            )

        # 3. Εμπλουτισμός Assets (OCR, Captions, Saving)
        if structure.assets:
            print(f"🖼️ Processing {len(structure.assets)} assets (images/diagrams)...")
            structure.assets = await enrich_assets(structure.assets, user_id=user_id)

        # 4. Smart Semantic Chunking (Recursive Splitter)
        # Εδώ εφαρμόζονται οι αλλαγές για το μέγεθος των chunks και τα quotes
        units = build_smart_semantic_units(structure)
        print(f"📦 Created {len(units)} semantic chunks.")

        # ✅ NEW: link units <-> assets (bidirectional)
        if units and structure.assets:
            units, structure.assets = link_units_and_assets(units, structure.assets, top_k_units_per_asset=2)
            print("🔗 Linked units with assets.")

        for u in units:
            if u.meta is None:
                u.meta = {}
            u.meta.setdefault("linked_asset_ids", [])
            
        # 5. Αποθήκευση Chunks στην Qdrant
        if units:
            units_store = get_vector_store_for_user_units(user_id)
            unit_docs = [
                Document(
                    page_content=u.primary_text,
                    metadata={
                        "user_id": u.user_id,
                        "assistant_type": assistant_type,
                        "document_id": u.document_id,
                        "unit_id": u.unit_id,
                        "page_start": u.page_start,
                        "page_end": u.page_end,
                        "chunk_index": u.meta.get("chunk_index", 0),

                        # ✅ NEW: deterministic structure mapping (for asset linking)
                        "pages": u.meta.get("pages", []),
                        "block_ids": u.meta.get("block_ids", []),
                        "bboxes_by_page": u.meta.get("bboxes_by_page", {}),
                        "linked_asset_ids": u.meta.get("linked_asset_ids", []),
                    }
                ) for u in units
            ]
            units_store.add_documents(unit_docs)

        # 6. Indexing Assets για διανυσματική αναζήτηση εικόνων
        if structure.assets:
            asset_store = get_vector_store_for_user_asset_text(user_id)
            AssetTextIndexer(asset_store).index_assets(
                assets=structure.assets,
                user_id=user_id,
                document_id=document_id,
            )

        print("\n🎉 INGEST COMPLETED SUCCESSFULLY")

    except Exception as e:
        print(f"\n❌ INGEST ERROR: {str(e)}")
        # Εδώ αν μελλοντικά φτιάξεις το update_document_status, θα το προσθέσεις
    
    finally:
        # Καθαρισμός προσωρινών αρχείων
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            print(f"🧹 Temporary file deleted: {tmp_path}")
        
        print("==============================")
        print("🏁 INGEST PROCESS FINISHED")
        print("==============================\n")