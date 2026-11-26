import fitz
import uuid
from typing import List, Tuple
from pipelines.models import Asset, TextBlock
import re


# ----------------------------
# Utilities
# ----------------------------

def group_rects(rects: List[fitz.Rect], threshold: float = 6.0) -> List[fitz.Rect]:
    if not rects:
        return []

    groups = []
    remaining = [fitz.Rect(r) for r in rects]

    while remaining:
        current = remaining.pop(0)
        merged = True

        while merged:
            merged = False
            test_rect = current + (-threshold, -threshold, threshold, threshold)
            for i in range(len(remaining) - 1, -1, -1):
                if test_rect.intersects(remaining[i]):
                    current.include_rect(remaining.pop(i))
                    merged = True

        groups.append(current)

    return groups


def text_overlap_ratio(rect: fitz.Rect, text_rects: List[fitz.Rect]) -> float:
    if not rect or not text_rects:
        return 0.0

    overlap = 0.0
    area = rect.get_area()
    if area == 0:
        return 0.0

    for tr in text_rects:
        inter = rect & tr
        if inter:
            overlap += inter.get_area()

    return overlap / area


# ----------------------------
# Main extractor
# ----------------------------

def extract_content_unified(pdf_path: str) -> Tuple[List[TextBlock], List[Asset]]:
    text_blocks: List[TextBlock] = []
    assets: List[Asset] = []

    doc = fitz.open(pdf_path)

    CAPTION_RE = re.compile(
        r"^\s*(Figure|Fig\.|Σχήμα|Table|Πίνακας)\s*\d+([.:)\-]|\s)",
        re.IGNORECASE,
    )

    def is_caption(text: str) -> bool:
        return bool(text and CAPTION_RE.search(text.strip()))

    for page_index, page in enumerate(doc):
        page_num = page_index + 1
        local_order = 0.01
        asset_local_index = 0

        page_text_elements: List[TextBlock] = []
        text_rects_to_avoid: List[fitz.Rect] = []

        # ----------------------------
        # 1. TEXT BLOCKS
        # ----------------------------
        for b in page.get_text("blocks"):
            text = b[4].strip()
            if not text:
                continue

            coords = [float(b[0]), float(b[1]), float(b[2]), float(b[3])]
            tb = TextBlock(
                block_id=f"tb_{uuid.uuid4().hex[:8]}",
                page=page_num,
                order=b[5],
                text=text,
                bbox=coords,
            )

            text_blocks.append(tb)
            page_text_elements.append(tb)

            if len(text) > 10:
                text_rects_to_avoid.append(fitz.Rect(b[:4]))

        def get_context(target_rect: fitz.Rect) -> str:
            if not target_rect:
                return ""

            y0, y1 = float(target_rect.y0), float(target_rect.y1)

            above = [tb for tb in page_text_elements if tb.bbox[3] <= y0 + 5]
            below = [tb for tb in page_text_elements if tb.bbox[1] >= y1 - 5]

            above.sort(key=lambda tb: y0 - tb.bbox[3])
            below.sort(key=lambda tb: tb.bbox[1] - y1)

            candidates = below[:2] + above[:2]
            captions = [tb for tb in candidates if is_caption(tb.text)]
            others = [tb for tb in candidates if not is_caption(tb.text)]

            combined = "\n".join(tb.text.strip() for tb in captions + others)
            return combined[:900]

        def asset_meta(bbox, extractor):
            m = {"extractor": extractor, "asset_local_index": asset_local_index}
            if bbox:
                m["bbox"] = [float(x) for x in bbox]
            return m

        # ----------------------------
        # 2. RASTER IMAGES
        # ----------------------------
        for img in page.get_images(full=True):
            try:
                xref = img[0]
                base = doc.extract_image(xref)
                if base["width"] < 50 or base["height"] < 50:
                    continue

                rects = page.get_image_rects(xref)
                if not rects:
                    continue

                r = rects[0]
                if r.width < 30 or r.height < 30:
                    continue

                asset_local_index += 1

                assets.append(
                    Asset(
                        asset_id=f"img_{uuid.uuid4().hex[:8]}",
                        asset_type="image",
                        page=page_num,
                        order=local_order,
                        image_bytes=base["image"],
                        context_text=get_context(r),
                        bbox=[float(r.x0), float(r.y0), float(r.x1), float(r.y1)],
                        meta=asset_meta(r, "pymupdf_image"),
                    )
                )
                local_order += 0.01

            except Exception:
                continue

        # ----------------------------
        # 3. DRAWINGS / DIAGRAMS
        # ----------------------------
        drawings = page.get_drawings()
        page_width = page.rect.width
        valid_rects: List[fitz.Rect] = []

        for d in drawings:
            r = fitz.Rect(d["rect"])

            if r.width > page_width * 0.7:
                continue

            overlap = text_overlap_ratio(r, text_rects_to_avoid)

            # ❌ Inline notation / text-dominant → ΜΗΝ γίνει asset
            if overlap > 0.45:
                continue

            if r.width < 40 or r.height < 40 or r.get_area() < 1200:
                continue

            valid_rects.append(r)

        grouped = group_rects(valid_rects, threshold=6.0)

        grouped = sorted(grouped, key=lambda rr: rr.get_area(), reverse=True)[:3]

        for r in grouped:
            try:
                padding = 2 if r.height < 120 else 6
                crop = r + (-padding, -padding, padding, padding)
                pix = page.get_pixmap(clip=crop, dpi=220)

                asset_local_index += 1

                assets.append(
                    Asset(
                        asset_id=f"diag_{uuid.uuid4().hex[:8]}",
                        asset_type="diagram",
                        page=page_num,
                        order=local_order,
                        image_bytes=pix.tobytes("png"),
                        context_text=get_context(r),
                        bbox=[float(crop.x0), float(crop.y0), float(crop.x1), float(crop.y1)],
                        meta=asset_meta(r, "pymupdf_drawing"),
                    )
                )
                local_order += 0.01

            except Exception:
                continue

    doc.close()
    return text_blocks, assets
