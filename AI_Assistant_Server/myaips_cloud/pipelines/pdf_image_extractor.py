# app/pipelines/pdf_image_extractor.py

from dataclasses import dataclass
from typing import List, Optional
import fitz  # PyMuPDF
import base64
import json
from uuid import uuid4

from openai import AsyncOpenAI

client = AsyncOpenAI()


@dataclass
class ExtractedImage:
    page: int
    image_bytes: bytes
    image_id: str
    bbox: Optional[tuple] = None  # (x0, y0, x1, y1)


# ---------------------------------------------------------
# 1) IMAGE EXTRACTION FROM PDF
# ---------------------------------------------------------

def extract_images_from_pdf(pdf_path: str) -> List[ExtractedImage]:
    """
    Extracts all raster images from a PDF using PyMuPDF.
    Returns a list of ExtractedImage(page, bytes, id, bbox).
    """

    doc = fitz.open(pdf_path)
    results: List[ExtractedImage] = []

    for page_index in range(len(doc)):
        page = doc[page_index]
        images = page.get_images(full=True)

        for img_index, img in enumerate(images):
            xref = img[0]

            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            image_bytes = base_image.get("image")
            if not image_bytes:
                continue

            image_id = f"img_{page_index+1}_{img_index}_{uuid4().hex[:6]}"

            # NOTE: BBOX extraction will need extra work using layout analysis
            results.append(
                ExtractedImage(
                    page=page_index + 1,   # pages start from 1
                    image_bytes=image_bytes,
                    image_id=image_id,
                    bbox=None,
                )
            )

    return results


# ---------------------------------------------------------
# 2) IMAGE → TABLE JSON EXTRACTION (OPTIONAL)
# ---------------------------------------------------------

async def extract_table_from_image(image_bytes: bytes) -> dict:
    """
    Attempts to extract a table from an image using OpenAI Vision.
    Returns JSON (table) or {}.
    """

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "If this image contains a table, extract it as a JSON array "
                                "of row objects with header keys. "
                                "If no table is present, return {}."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=400,
        )
    except Exception:
        return {}

    out = resp.choices[0].message.content.strip()

    try:
        return json.loads(out)
    except Exception:
        return {}
