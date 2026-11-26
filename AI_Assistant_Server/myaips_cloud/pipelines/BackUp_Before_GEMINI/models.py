# app/pipelines/models.py

from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class TextBlock:
    block_id: str
    page: int
    order: float
    text: str


@dataclass
class Asset:
    asset_id: str
    asset_type: str          # image | diagram
    page: int
    order: float
    image_bytes: Optional[bytes] = None
    url: Optional[str] = None
    text: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


@dataclass
class DocumentStructure:
    document_id: str
    user_id: int
    text_blocks: List[TextBlock]
    assets: List[Asset]
