# app/pipelines/medium_pipeline.py

import asyncio
from typing import List
from datetime import datetime

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

from pipelines.llm_helpers import summarize_chunk
from vectorstores.summaries_store import get_summaries_vector_store_for_user

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
from pipelines.equation_chunks import (
    looks_like_equation, 
    extract_equation_docs_from_text_chunk,
)

SUMMARY_BATCH = 10


async def run_in_batches(tasks, batch_size):
    results = []
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        batch_results = await asyncio.gather(*batch)
        results.extend(batch_results)
    return results



async def run_medium_pipeline(
    raw_docs,
    vector_store,
    user_id,
    assistant_type,
    document_id,
    pdf_path,
):
    # -----------------------------------
    # 1) TEXT CHUNKING
    # -----------------------------------
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=5000,
        chunk_overlap=250,
    )
    text_docs: List[Document] = splitter.split_documents(raw_docs)

    for d in text_docs:
        base = d.metadata or {}
        d.metadata = {
            "user_id": user_id,
            "assistant_type": assistant_type,
            "pipeline_mode": "medium",
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

    # -----------------------------------
    # 2) SEMANTIC GROUPING
    # -----------------------------------
    text_only = filter_text_chunks(text_docs)
    grouped_text = apply_grouping_to_text_chunks(text_only, assistant_type)
    grouped_map = {id(d): d for d in grouped_text}
    final_docs = [grouped_map.get(id(d), d) for d in text_docs]

    # -----------------------------------
    # 3) IMAGE EXTRACTION
    # -----------------------------------
    image_docs = await build_image_documents_for_pdf(
        pdf_path=pdf_path,
        user_id=user_id,
        assistant_type=assistant_type,
        document_id=document_id,
    )

    # -----------------------------------
    # 4) GROUP IMAGES
    # -----------------------------------
    if image_docs:
        text_for_group = load_text_chunks_for_document(grouped_text)
        for img in image_docs:
            nearest = find_nearest_text_group_for_image(
                image_page=img.metadata.get("page"),
                text_chunks_by_page=text_for_group,
            )
            assign_group_to_image_chunk(img, nearest)
            final_docs.append(img)

    # -----------------------------------
    # 5) SAVE RAW (text + images)
    # -----------------------------------
    extracted_tables = extract_tables_from_pdf(pdf_path)
        table_docs = build_table_docs_for_pdf(
            extracted_tables,
            user_id,
            assistant_type,
            document_id,
            group_mapping_fn=some_group_mapping_function
        )

    vector_store.add_documents(final_docs)
    vector_store.add_documents(text_docs)
    vector_store.add_documents(image_docs)
    vector_store.add_documents(table_docs)


    # -----------------------------------
    # 6) SUMMARIES
    # -----------------------------------
    summary_tasks = [summarize_chunk(d.page_content) for d in final_docs]
    summaries = await run_in_batches(summary_tasks, SUMMARY_BATCH)

    summary_store = get_summaries_vector_store_for_user(user_id)

    summary_docs = []
    for orig, summary in zip(final_docs, summaries):
        md = orig.metadata.copy()
        md.update({
            "modality_type": "summary",
            "pipeline_mode": "medium",
            "role_in_document": "summary",
            "created_at": datetime.utcnow().isoformat(),
        })
        summary_docs.append(Document(
            page_content=summary,
            metadata=md,
        ))

    summary_store.add_documents(summary_docs)

    return {
        "chunks": len(final_docs),
        "summaries": len(summary_docs),
        "image_chunks": len(image_docs),
    }
