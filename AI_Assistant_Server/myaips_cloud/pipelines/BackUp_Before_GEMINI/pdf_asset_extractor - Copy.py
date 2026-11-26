# app/pipelines/pdf_asset_extractor.py

import fitz  # PyMuPDF
import uuid
from typing import List

from pipelines.models import Asset


def _merge_rects(rects: List[fitz.Rect]) -> fitz.Rect:
    """
    Merge multiple rectangles into one bounding box.
    """
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    x1 = max(r.x1 for r in rects)
    y1 = max(r.y1 for r in rects)
    return fitz.Rect(x0, y0, x1, y1)


def extract_assets_from_pdf(
    pdf_path: str,
    user_id: int,
    document_id: str,
) -> List[Asset]:
    """
    Extract visual assets from PDF:
    - Raster images (embedded images)
    - Diagrams (vector drawings, cropped)
    Tables remain TEXT and are NOT extracted as images.
    """

    assets: List[Asset] = []
    doc = fitz.open(pdf_path)

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_number = page_index + 1

        local_order = 0.01  # ✅ ΤΟ ΜΟΝΟ ΠΟΥ ΕΛΕΙΠΕ

        # -------------------------------------------------
        # 1) RASTER IMAGES (embedded images)
        # -------------------------------------------------
        images = page.get_images(full=True)

        for img in images:
            xref = img[0]

            try:
                base_image = doc.extract_image(xref)
            except Exception:
                continue

            image_bytes = base_image.get("image")
            if not image_bytes:
                continue

            assets.append(
                Asset(
                    asset_id=f"asset_{uuid.uuid4().hex[:8]}",
                    page=page_number,
                    asset_type="image",
                    order=local_order,          # ✅ FIX
                    image_bytes=image_bytes,
                    text=None,
                    url=None,
                )
            )

            local_order += 0.01

        # -------------------------------------------------
        # 2) DIAGRAMS (vector drawings → cropped image)
        # -------------------------------------------------
        drawings = page.get_drawings()

        # Heuristic:
        # - diagrams usually have MANY drawing objects
        # - tables / text decoration have few
        if len(drawings) < 5:
            continue

        rects: List[fitz.Rect] = []
        for d in drawings:
            rect = d.get("rect")
            if rect:
                rects.append(fitz.Rect(rect))

        if not rects:
            continue

        diagram_rect = _merge_rects(rects)

        page_rect = page.rect
        area_ratio = diagram_rect.get_area() / page_rect.get_area()

        # If diagram covers almost whole page, probably not a diagram
        if area_ratio > 0.85:
            continue

        try:
            pix = page.get_pixmap(clip=diagram_rect, dpi=200)
            image_bytes = pix.tobytes("png")
        except Exception:
            continue

        assets.append(
            Asset(
                asset_id=f"asset_{uuid.uuid4().hex[:8]}",
                page=page_number,
                asset_type="diagram",
                order=local_order,          # ✅ FIX
                image_bytes=image_bytes,
                text=None,
                url=None,
            )
        )

    return assets
