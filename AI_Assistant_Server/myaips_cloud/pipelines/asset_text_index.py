# app/pipelines/asset_text_index.py

from typing import List

from langchain.schema import Document
from pipelines.structural_parser import Asset


class AssetTextIndexer:
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def index_assets(
        self,
        assets: List[Asset],
        user_id: int,
        document_id: str,
    ):
        docs = []

        for asset in assets:
            # ✅ Ensure stable meta + linking field (always present)
            if asset.meta is None:
                asset.meta = {}
            asset.meta.setdefault("linked_unit_ids", [])

            # --------------------------------------------------
            # BUILD EMBEDDING TEXT (page_content)
            # --------------------------------------------------
            # Prefer enriched text (CAPTION/OCR). If missing, fallback to a minimal description.
            base_text = (asset.text or "").strip()
            if not base_text:
                base_text = f"Visual asset: {asset.asset_type}"

            parts = [base_text]

            if asset.context_text:
                ctx = asset.context_text.strip()
                if ctx:
                    parts.append("[CONTEXT]\n" + ctx)

            page_content = "\n\n".join(parts).strip()

            # --------------------------------------------------
            # BASE METADATA (always present)
            # --------------------------------------------------
            metadata = {
                "user_id": user_id,
                "document_id": document_id,
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "page": asset.page,
                "order": asset.order,
                "source": "asset_text",
                "url": asset.url,
                "text": asset.text or "",

                # ✅ Always store bbox if available
                "bbox": asset.bbox if asset.bbox else None,

                # ✅ Explicit link field (always present)
                "linked_unit_ids": asset.meta.get("linked_unit_ids", []),
            }

            if asset.context_text:
                metadata["context_text"] = asset.context_text

            # --------------------------------------------------
            # MERGE ASSET META (without overwriting core fields)
            # --------------------------------------------------
            if asset.meta:
                for key, value in asset.meta.items():
                    if key not in metadata:
                        metadata[key] = value

            docs.append(
                Document(
                    page_content=page_content,
                    metadata=metadata,
                )
            )

        if docs:
            self.vector_store.add_documents(docs)
