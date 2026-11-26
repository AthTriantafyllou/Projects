from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class SemanticUnit:
    unit_id: str
    document_id: str
    user_id: int
    assistant_type: str
    unit_type: str
    primary_text: str
    page_start: int
    page_end: int
    meta: Dict[str, Any]
    assets: List[Any]
