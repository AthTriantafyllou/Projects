# app/pipelines/ocr_utils.py

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
from typing import List, Optional


OCR_LANG_MAP = {
    "en": "eng",
    "el": "ell",
    "pl": "pol",
}

DEFAULT_OCR_LANG = "eng"


def resolve_tesseract_lang(lang_codes: Optional[List[str]]) -> str:
    """
    Convert app language codes → Tesseract language string.

    Example:
        ["el", "en"] → "ell+eng"
        None → "eng"
    """
    if not lang_codes:
        return DEFAULT_OCR_LANG

    langs = []
    for code in lang_codes:
        t_lang = OCR_LANG_MAP.get(code)
        if t_lang:
            langs.append(t_lang)

    return "+".join(sorted(set(langs))) or DEFAULT_OCR_LANG


def ocr_pdf_page(
    pdf_path: str,
    page_index: int,
    lang_codes: Optional[List[str]] = None,
) -> str:
    """
    OCR fallback for ONE PDF page.
    Used only when text extraction fails or is insufficient.
    """

    lang = resolve_tesseract_lang(lang_codes)

    doc = fitz.open(pdf_path)
    page = doc[page_index]

    # Render page to image
    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")

    image = Image.open(io.BytesIO(img_bytes))

    text = pytesseract.image_to_string(
        image,
        lang=lang,
        config="--psm 6",
    )

    return text.strip()
