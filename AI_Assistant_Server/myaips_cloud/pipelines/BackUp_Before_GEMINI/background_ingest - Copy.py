import os
from typing import List
from langchain.schema import Document

from utils.parser import load_universal_no_split
from pipelines.stats import analyze_document_stats
from pipelines.orchestrator import select_pipeline_mode, run_ingestion_pipeline
from db_users import get_vector_store_for_user


async def background_ingest(
    tmp_path: str,
    original_name: str,
    user_id: int,
    assistant_type: str,
    document_id: str,
):
    try:
        print("\n\n==============================")
        print(f"🚀 [BG] START ingest: {original_name}")
        print(f"👤 user={user_id}, assistant_type={assistant_type}")
        print(f"📄 document_id={document_id}")
        print("==============================\n")

        # 1) Load RAW docs
        raw_docs: List[Document] = load_universal_no_split(tmp_path, original_name)
        if not raw_docs:
            print(f"❌ [BG] No readable content in {original_name}")
            return

        print(f"📄 Loaded RAW docs = {len(raw_docs)}")

        # 2) Stats → select pipeline
        stats = analyze_document_stats(raw_docs)
        mode = select_pipeline_mode(stats)
        print(f"🔥 Selected pipeline mode = {mode}")

        # 3) Vector store
        vector_store = get_vector_store_for_user(user_id)

        # 4) Run ingestion pipeline (ΜΟΝΟ με pdf_path)
        result = await run_ingestion_pipeline(
            mode=mode,
            raw_docs=raw_docs,
            vector_store=vector_store,
            user_id=user_id,
            assistant_type=assistant_type,
            document_id=document_id,
            pdf_path=tmp_path,    # <-- μοναδικό όνομα!
        )

        print("\n🎉 [BG] Pipeline COMPLETED!")
        print(f"📦 Result = {result}")

    except Exception as e:
        print("❌ [BG] ERROR in background_ingest:", e)

    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                print(f"🧹 Temp PDF deleted: {tmp_path}")
            except:
                pass

        print("==============================")
        print(f"🏁 FINISHED ingest: {original_name}")
        print("==============================\n")
