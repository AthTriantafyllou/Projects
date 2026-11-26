# app/pipelines/image_chunks.py

import os
from langchain.schema import Document
from datetime import datetime

from pipelines.pdf_image_extractor import extract_images_from_pdf
from pipelines.llm_helpers import describe_image, ocr_image, extract_latex_from_image
from .file_utils import save_image_for_user


async def build_image_documents_for_pdf(
    pdf_path: str,
    user_id: int,
    assistant_type: str,
    document_id: str,
):
    print("IMAGE-PIPE: Extracting images from:", pdf_path)
    extracted_images = extract_images_from_pdf(pdf_path)

    print(f"IMAGE-PIPE: extractor returned {len(extracted_images)} images")
    image_docs = []
    equation_docs = []

    for i, img in enumerate(extracted_images):
        print(f"IMAGE-PIPE: inspecting image #{i}: type={type(img)}")

        # --- normalise image bytes ---
        if hasattr(img, "image_bytes"):
            image_bytes = img.image_bytes
        elif isinstance(img, bytes):
            image_bytes = img
        else:
            print("IMAGE-PIPE WARNING: invalid image object, skipping:", img)
            continue

        if not isinstance(image_bytes, (bytes, bytearray)):
            print("IMAGE-PIPE ERROR: image_bytes is not raw bytes, skipping.")
            continue

        # --- page fallback ---
        page = getattr(img, "page", None)
        try:
            page = int(page)
        except:
            page = None

        # --- save image safely ---
        try:
            image_url = save_image_for_user(user_id, image_bytes)
        except Exception as e:
            print("IMAGE-PIPE ERROR saving image:", e)
            continue

        # --- LLM processing ---
        try:
            caption = await describe_image(image_bytes)
            ocr_text = await ocr_image(image_bytes)
            latex = await extract_latex_from_image(image_bytes)
        except Exception as e:
            print("IMAGE-PIPE ERROR during LLM operations:", e)
            caption = "(image)"
            ocr_text = ""
            latex = None

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
            "page": page,
            "group_id": None,
            "group_type": None,
            "group_order": None,
            "role_in_document": "image",
            "subject_tags": None,
            "language": None,
            "image_url": image_url,
            "created_at": datetime.utcnow().isoformat(),
        }

        image_docs.append(
            Document(page_content=page_content, metadata=metadata)
        )

        # --- EQUATION extraction ---
        if latex and latex not in ("NO_EQUATION", "", None):
            eq_metadata = metadata.copy()
            eq_metadata.update({
                "modality_type": "equation",
                "role_in_document": "equation",
                "latex": latex,
            })

            equation_docs.append(
                Document(page_content=latex, metadata=eq_metadata)
            )

    print(
        f"IMAGE-PIPE DONE: images={len(image_docs)}, equations={len(equation_docs)}"
    )
    return image_docs, equation_docs
