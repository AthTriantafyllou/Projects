# app/pipelines/table_chunks.py

from typing import List
from datetime import datetime
from langchain.schema import Document
from pipelines.table_extractor import ExtractedTable


def build_table_documents_for_pdf(
    extracted_tables: List[ExtractedTable],
    user_id: int,
    assistant_type: str,
    document_id: str,
) -> List[Document]:
    """
    Convert ExtractedTable objects → LangChain Documents.
    """

    table_docs: List[Document] = []

    for t in extracted_tables:
        meta = {
            "user_id": user_id,
            "assistant_type": assistant_type,
            "pipeline_mode": "table",
            "modality_type": "table",
            "document_id": document_id,
            "page": t.page,
            "group_id": None,
            "group_type": None,
            "group_order": None,
            "role_in_document": "table",
            "created_at": datetime.utcnow().isoformat(),
        }

        # table HTML becomes page_content
        table_docs.append(
            Document(
                page_content=t.html,
                metadata=meta,
            )
        )

    return table_docs
