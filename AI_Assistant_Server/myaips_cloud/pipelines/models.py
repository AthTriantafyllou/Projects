from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class TextBlock:
    block_id: str
    page: int
    order: float
    text: str
    #bbox: Optional[tuple] = None  # Προσθήκη για το mapping
    bbox: Optional[List[float]] = None

@dataclass
class Asset:
    asset_id: str
    asset_type: str          # image | diagram | table | equation
    page: int
    order: float
    image_bytes: Optional[bytes] = None
    url: Optional[str] = None
    text: Optional[str] = None       # OCR/Caption text
    context_text: Optional[str] = None  # Το κείμενο που το περιβάλλει
    bbox: Optional[List[float]] = None
    meta: Optional[Dict[str, Any]] = None

@dataclass
class DocumentStructure:
    document_id: str
    user_id: int
    text_blocks: List[TextBlock]
    assets: List[Asset]