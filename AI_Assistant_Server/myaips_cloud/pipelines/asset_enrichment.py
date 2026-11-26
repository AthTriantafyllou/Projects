# app/pipelines/asset_enrichment.py

from typing import List

from pipelines.models import Asset
from pipelines.file_utils import save_image_for_user
from pipelines.llm_helpers import describe_image, ocr_image


async def enrich_assets(assets: List[Asset], user_id: int) -> List[Asset]:
    """
    FINAL enrichment step:
    - Save image_bytes to storage
    - Set asset.url
    - Run caption + OCR
    """

    enriched: List[Asset] = []

    for asset in assets:
        # ΜΟΝΟ image / diagram έχουν image_bytes
        if asset.image_bytes:
            # 🔥 ΑΥΤΟ ΕΛΕΙΠΕ
            asset.url = save_image_for_user(user_id, asset.image_bytes)

            # Enrichment
            caption = ""
            ocr_text = ""

            try:
                caption = await describe_image(asset.image_bytes)
            except Exception:
                pass

            try:
                ocr_text = await ocr_image(asset.image_bytes)
            except Exception:
                pass

            parts = []
            if caption:
                parts.append(f"[CAPTION]\n{caption}")
            if ocr_text:
                parts.append(f"[OCR]\n{ocr_text}")

            asset.text = "\n\n".join(parts) if parts else None

            # optional: free memory
            asset.image_bytes = None

        enriched.append(asset)

    return enriched
