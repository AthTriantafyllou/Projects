# app/pipelines/build_teacher_context.py

from typing import List
from langchain.schema import Document
import os

BASE_URL = os.getenv("APP_BASE_URL", "https://myaips.cloud/")


def build_teacher_context(units: List[Document], assets: List) -> str:
    blocks: List[str] = []
    relevant_pages = {int(u.metadata.get('page_start') or u.metadata.get('page')) for u in units if (u.metadata.get('page_start') or u.metadata.get('page')) is not None}

    blocks.append("IMPORTANT: If you encounter broken mathematical text, reconstruct it into clean LaTeX using $ symbols.")

    # Κείμενα
    for u in units:
        p_info = u.metadata.get('page_start') or u.metadata.get('page', 'N/A')
        blocks.append(f"[SOURCE: TEXT | PAGE {p_info}]\n{u.page_content.strip()}")

    # Εικόνες (Εδώ η διόρθωση)
    for a in assets:
        # Επειδή το 'a' έρχεται από το Qdrant scroll, είναι ScoredPoint
        # Τα metadata είναι στο a.payload['metadata']
        payload = getattr(a, 'payload', {})
        data = payload.get("metadata", {})
        
        asset_page = data.get("page")
        url = data.get("url", "")
        
        if not url: continue # Αν δεν έχει URL, δεν μπορεί να την δείξει

        full_url = f"{BASE_URL}{url.lstrip('/')}"
        description = data.get("text") or data.get("context_text") or ""

        asset_block = (
            f"--- VISUAL ASSET (PAGE {asset_page}) ---\n"
            f"IMAGE_URL_TO_DISPLAY: {full_url}\n"
            f"CAPTION: {description}\n"
            f"INSTRUCTIONS: Include this image in your response using ![img]({full_url})\n"
            f"-------------------------------"
        )
        blocks.append(asset_block)

    return "\n\n---\n\n".join(blocks).replace("{", "{{").replace("}", "}}")