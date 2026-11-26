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
            if not asset.text:
                continue

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
                "text": asset.text,
            }

            # --------------------------------------------------
            # MERGE ASSET META (CRITICAL FIX)
            # --------------------------------------------------
            if asset.meta:
                for key, value in asset.meta.items():
                    # avoid overwriting core fields by accident
                    if key not in metadata:
                        metadata[key] = value

            docs.append(
                Document(
                    page_content=asset.text,
                    metadata=metadata,
                )
            )

        if docs:
            self.vector_store.add_documents(docs)
