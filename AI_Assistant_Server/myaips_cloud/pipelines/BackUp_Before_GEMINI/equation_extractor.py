import re
import uuid
from typing import List

from pipelines.models import TextBlock, Asset


# --------------------------------------------------
# Heuristics
# --------------------------------------------------

MATH_SYMBOLS = r"[=+\-*/^√∑∫≈≠≤≥]"
LATEX_HINTS = r"(\\frac|\\sum|\\int|\\sqrt|\$)"


def classify_equation_layout(line: str) -> str:
    """
    Decide whether an equation is inline or block.

    Returns:
        "block" | "inline"
    """

    stripped = line.strip()

    # Αν όλη η γραμμή είναι καθαρά εξίσωση → block
    if stripped == line and len(stripped.split()) <= 4:
        return "block"

    # Διαφορετικά → inline
    return "inline"


def looks_like_equation(line: str) -> bool:
    """
    STRICT heuristic for equation detection (ingestion-time).

    RULES:
    - MUST contain '='
    - MUST NOT be bullet / list item
    - MUST NOT be API / tool enumeration
    - MUST NOT be long natural-language sentence
    """

    if not line:
        return False

    line = line.strip()

    # --------------------------------------------------
    # 1) Mandatory '='
    # --------------------------------------------------
    if "=" not in line:
        return False

    # --------------------------------------------------
    # 2) Reject bullets / lists
    # --------------------------------------------------
    if line.startswith(("•", "-", "–", "*")):
        return False

    # --------------------------------------------------
    # 3) Reject obvious API / tool enumerations
    # --------------------------------------------------
    lower = line.lower()

    if any(token in lower for token in ["api", "sdk", "http", "https"]):
        return False

    # pattern: word / word / word (Notion / Slack / Trello)
    if re.search(r"\b\w+\s*/\s*\w+", line):
        return False

    # --------------------------------------------------
    # 4) Reject long natural language
    # --------------------------------------------------
    words = line.split()
    if len(words) > 6:
        return False

    # --------------------------------------------------
    # 5) Basic math sanity check
    # --------------------------------------------------
    if not re.search(r"[0-9a-zA-Z]", line):
        return False

    return True


# --------------------------------------------------
# Public API
# --------------------------------------------------

def extract_equations_from_text_blocks(
    text_blocks: List[TextBlock],
) -> List[Asset]:
    """
    Extract equations from text blocks.
    Each equation becomes a standalone Asset.
    """

    assets: List[Asset] = []

    for block in text_blocks:
        lines = block.text.splitlines()
        local_order = 0.01

        for line in lines:
            if not looks_like_equation(line):
                continue

            layout = classify_equation_layout(line)

            assets.append(
                Asset(
                    asset_id=f"eq_{uuid.uuid4().hex[:8]}",
                    page=block.page,
                    asset_type="equation",
                    order=local_order,
                    text=line.strip(),
                    url=None,
                    meta={
                        "source": "text",
                        "layout": layout,        # ✅ INLINE | BLOCK
                        "confidence": 0.9,
                    },
                )
            )

            local_order += 0.01

    return assets
