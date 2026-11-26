# app/pipelines/small_pipeline.py

import os
from typing import List
from datetime import datetime

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

from pipelines.grouping import (
    apply_grouping_to_text_chunks,
    filter_text_chunks,
)

from pipelines.grouping_images import (
    load_text_chunks_for_document,
    find_nearest_text_group_for_image,
    assign_group_to_image_chunk,
)

from pipelines.image_chunks import build_image_documents_for_pdf
from pipelines.equation_chunks import extract_equation_docs_from_text_chunk

from pipelines.table_extractor import extract_tables_from_pdf
from pipelines.table_chunks import build_table_documents_for_pdf


async def run_small_pipeline(
    raw_docs,
    vector_store,
    user_id: int,
    assistant_type: str,
    document_id: str,
    pdf_path: str,
):
    print("SMALL PIPELINE: ENTER")
    print("raw_docs count =", len(raw_docs))

    # Detect extension
    first_meta = raw_docs[0].metadata or {}
    source_name = first_meta.get("source", "")
    ext = os.path.splitext(source_name)[1].lower()

    # --------------------------------------------------
    # 1) TEXT CHUNKING
    # --------------------------------------------------
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )
    text_docs: List[Document] = splitter.split_documents(raw_docs)
    print("TEXT DOCS =", len(text_docs))

    for d in text_docs:
        base = d.metadata or {}
        d.metadata = {
            "user_id": user_id,
            "assistant_type": assistant_type,
            "pipeline_mode": "small",
            "modality_type": "text",
            "document_id": document_id,
            "page": base.get("page"),
            "group_id": None,
            "group_type": None,
            "group_order": None,
            "role_in_document": "paragraph",
            "subject_tags": None,
            "language": None,
            "created_at": datetime.utcnow().isoformat(),
        }

    # --------------------------------------------------
    # 2) SEMANTIC GROUPING
    # --------------------------------------------------
    text_only = filter_text_chunks(text_docs)
    final_text_docs = apply_grouping_to_text_chunks(text_only, assistant_type)
    print("GROUPED TEXT DOCS =", len(final_text_docs))

    # --------------------------------------------------
    # 3) IMAGES + EQUATIONS FROM IMAGES (LIMIT = 20)
    # --------------------------------------------------
    image_docs = []
    equation_from_images = []

    if ext == ".pdf":
        img_docs, eq_from_img = await build_image_documents_for_pdf(
            pdf_path=pdf_path,
            user_id=user_id,
            assistant_type=assistant_type,
            document_id=document_id,
        )

        # --- LIMIT IMAGES ---
        MAX_IMAGES = 20
        if len(img_docs) > MAX_IMAGES:
            print(f"LARGE-PIPE: Image limit reached. Keeping first {MAX_IMAGES} images.")
            img_docs = img_docs[:MAX_IMAGES]

        # --- LIMIT EQUATIONS FROM IMAGES ---
        MAX_EQ = 20
        if len(eq_from_img) > MAX_EQ:
            print(f"LARGE-PIPE: Equation-from-image limit reached. Keeping first {MAX_EQ}.")
            eq_from_img = eq_from_img[:MAX_EQ]

        image_docs = img_docs
        equation_from_images = eq_from_img

        print("IMAGE DOCS =", len(image_docs))
        print("EQ-FROM-IMAGES =", len(equation_from_images))

        if image_docs:
            text_per_page = load_text_chunks_for_document(final_text_docs)
            for img in image_docs:
                nearest = find_nearest_text_group_for_image(
                    image_page=img.metadata.get("page"),
                    text_chunks_by_page=text_per_page,
                )
                assign_group_to_image_chunk(img, nearest)

    # --------------------------------------------------
    # 4) TABLE EXTRACTION (PDF ONLY)
    # --------------------------------------------------
    table_docs: List[Document] = []
    if ext == ".pdf":
        try:
            extracted_tables = extract_tables_from_pdf(pdf_path)
            table_docs = build_table_documents_for_pdf(
                extracted_tables=extracted_tables,
                user_id=user_id,
                assistant_type=assistant_type,
                document_id=document_id,
            )

            if table_docs:
                text_per_page = load_text_chunks_for_document(final_text_docs)

                for tbl_doc in table_docs:
                    page = tbl_doc.metadata.get("page")
                    nearest = find_nearest_text_group_for_image(
                        image_page=page,
                        text_chunks_by_page=text_per_page
                    )
                    if nearest is None:
                        tbl_doc.metadata.update({
                            "group_id": f"table_orphan_{page}",
                            "group_type": "table_block",
                            "group_order": 1.0,
                        })
                    else:
                        parent_group_id = nearest.metadata.get("group_id")
                        parent_group_type = nearest.metadata.get("group_type")
                        parent_order = nearest.metadata.get("group_order", 0)

                        tbl_doc.metadata.update({
                            "group_id": parent_group_id,
                            "group_type": parent_group_type,
                            "group_order": parent_order + 0.02,
                        })

        except Exception as e:
            print(f"❌ ERROR in extract_tables_from_pdf (SMALL): {e}")
            table_docs = []

    # --------------------------------------------------
    # 5) EQUATIONS FROM TEXT + IMAGES
    # --------------------------------------------------
    all_equation_docs = []

    for chunk in final_text_docs:
        eq_docs = extract_equation_docs_from_text_chunk(
            chunk=chunk,
            user_id=user_id,
            assistant_type=assistant_type,
            document_id=document_id,
        )
        all_equation_docs.extend(eq_docs)

    # Add equations that came from images
    all_equation_docs.extend(equation_from_images)

    # --------------------------------------------------
    # 6) MERGE ALL
    # --------------------------------------------------
    all_docs = []
    all_docs.extend(final_text_docs)
    all_docs.extend(image_docs)
    all_docs.extend(table_docs)
    all_docs.extend(all_equation_docs)

    print("SMALL-PIPE: FINAL COUNTS")
    print("text_docs     =", len(final_text_docs))
    print("image_docs    =", len(image_docs))
    print("table_docs    =", len(table_docs))
    print("equation_docs =", len(all_equation_docs))
    print("ALL =", len(all_docs))

    if all_docs:
        vector_store.add_documents(all_docs)

    return {
        "chunks": len(final_text_docs),
        "image_chunks": len(image_docs),
        "table_chunks": len(table_docs),
        "equation_chunks": len(all_equation_docs),
    }
