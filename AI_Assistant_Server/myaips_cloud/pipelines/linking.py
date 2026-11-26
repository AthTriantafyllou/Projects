# app/pipelines/linking.py

from typing import List, Dict, Any, Tuple, Optional

from pipelines.semantic_models import SemanticUnit
from pipelines.models import Asset


def _area(b: List[float]) -> float:
    return max(0.0, (b[2] - b[0])) * max(0.0, (b[3] - b[1]))


def _intersect(a: List[float], b: List[float]) -> float:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def _iou(a: List[float], b: List[float]) -> float:
    inter = _intersect(a, b)
    if inter <= 0:
        return 0.0
    union = _area(a) + _area(b) - inter
    return inter / union if union > 0 else 0.0


def _center(b: List[float]) -> Tuple[float, float]:
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


def _distance(a: List[float], b: List[float]) -> float:
    ax, ay = _center(a)
    bx, by = _center(b)
    dx = ax - bx
    dy = ay - by
    return (dx * dx + dy * dy) ** 0.5


def link_units_and_assets(
    units: List[SemanticUnit],
    assets: List[Asset],
    top_k_units_per_asset: int = 2,
) -> Tuple[List[SemanticUnit], List[Asset]]:
    """
    Creates bidirectional links:
      unit.meta["linked_asset_ids"] = [...]
      asset.meta["linked_unit_ids"] = [...]

    Heuristic:
      - same page required
      - if IOU exists -> strong score
      - else -> inverse distance score
    """

    # Initialize containers
    for u in units:
        u.meta = u.meta or {}
        u.meta.setdefault("linked_asset_ids", [])

    for a in assets:
        if a.meta is None:
            a.meta = {}
        a.meta.setdefault("linked_unit_ids", [])

    # Build quick index: page -> units with bbox coverage
    page_to_units: Dict[int, List[Tuple[SemanticUnit, List[float]]]] = {}

    for u in units:
        bboxes_by_page = (u.meta or {}).get("bboxes_by_page", {}) or {}
        # bboxes_by_page keys might be strings if serialized; normalize
        for p_key, ub in bboxes_by_page.items():
            try:
                p = int(p_key)
            except Exception:
                continue
            if not ub or len(ub) != 4:
                continue
            page_to_units.setdefault(p, []).append((u, ub))

    # Link each asset to best units on same page
    for a in assets:
        if not a.bbox or len(a.bbox) != 4:
            continue

        candidates = page_to_units.get(int(a.page), [])
        if not candidates:
            continue

        scored: List[Tuple[float, SemanticUnit]] = []
        for u, ub in candidates:
            # Score: prefer overlap, else proximity
            iou = _iou(a.bbox, ub)
            if iou > 0:
                score = 10.0 + iou  # overlap dominates
            else:
                dist = _distance(a.bbox, ub)
                score = 1.0 / (1.0 + dist)  # closer is higher
            scored.append((score, u))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_units = [u for _, u in scored[:top_k_units_per_asset] if _ > 0]

        if not best_units:
            continue

        for u in best_units:
            # asset -> unit
            a.meta["linked_unit_ids"].append(u.unit_id)

            # unit -> asset
            u.meta["linked_asset_ids"].append(a.asset_id)

    # Deduplicate
    for u in units:
        u.meta["linked_asset_ids"] = sorted(set(u.meta.get("linked_asset_ids", [])))

    for a in assets:
        a.meta["linked_unit_ids"] = sorted(set(a.meta.get("linked_unit_ids", [])))

    return units, assets
