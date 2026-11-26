# app/pipelines/orchestrator.py

from enum import Enum

from pipelines.small_pipeline import run_small_pipeline
from pipelines.large_pipeline import run_large_pipeline


class PipelineMode(str, Enum):
    SMALL = "small"
    LARGE = "large"


def select_pipeline_mode(stats) -> PipelineMode:
    """
    Επιλογή pipeline αποκλειστικά με βάση το μέγεθος του PDF.
    - SMALL: έως και 10 σελίδες
    - LARGE: πάνω από 10 σελίδες (και ενεργοποιούμε summaries)
    """
    pages = stats["page_count"]

    if pages <= 10:
        return PipelineMode.SMALL

    return PipelineMode.LARGE


async def run_ingestion_pipeline(
    mode: PipelineMode,
    raw_docs,
    vector_store,
    user_id: int,
    assistant_type: str,
    document_id: str,
    pdf_path: str,
):

    """
    Orchestrator: καλεί το σωστό pipeline ανάλογα με το mode.
    Σημείωση: το mode έχει ήδη αποφασιστεί από select_pipeline_mode().
    """

    if mode == PipelineMode.SMALL:
        return await run_small_pipeline(
            raw_docs=raw_docs,
            vector_store=vector_store,
            user_id=user_id,
            assistant_type=assistant_type,
            document_id=document_id,
            pdf_path=pdf_path,
        )

    # default: LARGE
    return await run_large_pipeline(
        raw_docs=raw_docs,
        vector_store=vector_store,
        user_id=user_id,
        assistant_type=assistant_type,
        document_id=document_id,
        pdf_path=pdf_path,
    )
