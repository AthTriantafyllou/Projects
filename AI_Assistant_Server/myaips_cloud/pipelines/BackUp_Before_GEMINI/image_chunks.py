# app/pipelines/image_chunks.py

from langchain.schema import Document
from datetime import datetime

from pipelines.pdf_image_extractor import extract_images_from_pdf
from pipelines.llm_helpers import describe_image, ocr_image, extract_latex_from_image
from .file_utils import save_image_for_user

MAX_IMAGES = 20   # <<<< ---- GLOBAL LIMIT


async def build_image_documents_for_pdf(
    pdf_path: str,
    user_id: int,
    assistant_type: str,
    document_id: str,
):
    print(f"IMAGE-PIPE: Extracting images from: {pdf_path}")
    extracted_images = extract_images_from_pdf(pdf_path)

    print(f"IMAGE-PIPE: extractor returned {len(extracted_images)} images")

    # --------------------------------------------------
    # HARD LIMIT ΠΡΙΝ κάνουμε Vision / OCR
    # --------------------------------------------------
    if len(extracted_images) > MAX_IMAGES:
        print(f"IMAGE-PIPE: LIMIT applied → keeping first {MAX_IMAGES} images")
        extracted_images = extracted_images[:MAX_IMAGES]

    image_docs = []
    equation_docs = []

    for idx, img in enumerate(extracted_images):
        print(f"IMAGE-PIPE: processing image #{idx} (page={img.page})")

        # Save binary
        image_url = save_image_for_user(user_id, img.image_bytes)

        # Vision / OCR
        caption = await describe_image(img.image_bytes)
        ocr_text = await ocr_image(img.image_bytes)
        latex = await extract_latex_from_image(img.image_bytes)

        page_content = (
            f"[IMAGE CAPTION]\n{caption}\n\n"
            f"[OCR TEXT]\n{ocr_text}\n"
        )

        metadata = {
            "user_id": user_id,
            "assistant_type": assistant_type,
            "pipeline_mode": "image",
            "modality_type": "image",
            "document_id": document_id,
            "page": img.page,
            "group_id": None,
            "group_type": None,
            "group_order": None,
            "role_in_document": "image",
            "subject_tags": None,
            "language": None,
            "image_url": image_url,
            "created_at": datetime.utcnow().isoformat(),
        }

        image_docs.append(Document(page_content=page_content, metadata=metadata))

        # Equations
        if latex and latex not in ("NO_EQUATION", "", None):
            eq_metadata = metadata.copy()
            eq_metadata.update({
                "modality_type": "equation",
                "role_in_document": "equation",
                "latex": latex,
            })
            equation_docs.append(
                Document(
                    page_content=latex,
                    metadata=eq_metadata,
                )
            )

    return image_docs, equation_docs
