from typing import Dict, Any, List
from collections import defaultdict

from pipelines.retrieve_units import retrieve_units
from pipelines.build_teacher_context import build_teacher_context
from db_users import get_vector_store_for_user_asset_text

from qdrant_client.http.models import (
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
)


def retrieve_teacher_context(user_id: int, question: str, k: int = 5) -> Dict[str, Any]:
    units = retrieve_units(user_id, question, k=k)

    print("\n===== DEBUG UNITS =====")
    for i, u in enumerate(units):
        m = u.metadata or {}
        print(
            f"[{i}] unit_id={m.get('unit_id')} doc={m.get('document_id')} "
            f"page_start={m.get('page_start')} pages={m.get('pages')} "
            f"linked_asset_ids={m.get('linked_asset_ids')}"
        )
    print("=======================\n")

    if not units:
        return {"context": "", "units": [], "assets": []}

    # ---------------------------------------------------------
    # 1) Gather linked asset IDs from unit metadata
    # ---------------------------------------------------------
    doc_to_asset_ids = defaultdict(set)  # document_id -> set(asset_id)

    for u in units:
        meta = u.metadata or {}
        d_id = meta.get("document_id")
        linked = meta.get("linked_asset_ids") or []

        if d_id and isinstance(linked, list):
            for aid in linked:
                if aid:
                    doc_to_asset_ids[str(d_id)].add(str(aid))

    # ---------------------------------------------------------
    # 2) Fetch assets by (user_id, document_id, asset_id IN linked_ids)
    # ---------------------------------------------------------
    all_assets = []
    store = get_vector_store_for_user_asset_text(user_id)

    for d_id, asset_ids in doc_to_asset_ids.items():
        if not asset_ids:
            continue

        flt = Filter(
            must=[
                FieldCondition(
                    key="metadata.user_id",
                    match=MatchValue(value=int(user_id)),
                ),
                FieldCondition(
                    key="metadata.document_id",
                    match=MatchValue(value=str(d_id)),
                ),
                FieldCondition(
                    key="metadata.asset_id",
                    match=MatchAny(any=list(asset_ids)),
                ),
            ]
        )

        results, _ = store.client.scroll(
            collection_name=store.collection_name,
            scroll_filter=flt,
            limit=300,
            with_payload=True,
            with_vectors=False,
        )
        all_assets.extend(results)

    print("\n===== DEBUG ASSETS (LINKED FETCH) =====")
    for a in all_assets:
        payload = getattr(a, "payload", {}) or {}
        md = payload.get("metadata", {}) or {}
        print(
            f"asset_id={md.get('asset_id')} type={md.get('asset_type')} "
            f"doc={md.get('document_id')} page={md.get('page')} order={md.get('order')} "
            f"url={md.get('url')} linked_unit_ids={md.get('linked_unit_ids')}"
        )
    print("======================================\n")

    print(f"DEBUG: linked assets found? {bool(all_assets)} (count={len(all_assets)})")

    # ---------------------------------------------------------
    # 3) Fallback (older docs): if no linked assets, fetch by pages
    # ---------------------------------------------------------
    if not all_assets:
        doc_to_pages = defaultdict(set)
        for u in units:
            meta = u.metadata or {}
            d_id = meta.get("document_id")
            pages = meta.get("pages") or []

            if d_id and pages:
                for p in pages:
                    try:
                        doc_to_pages[str(d_id)].add(int(p))
                    except Exception:
                        pass
            else:
                p_num = meta.get("page_start") or meta.get("page")
                if d_id and p_num is not None:
                    doc_to_pages[str(d_id)].add(int(p_num))

        for d_id, pages_set in doc_to_pages.items():
            if not pages_set:
                continue

            flt = Filter(
                must=[
                    FieldCondition(
                        key="metadata.user_id",
                        match=MatchValue(value=int(user_id)),
                    ),
                    FieldCondition(
                        key="metadata.document_id",
                        match=MatchValue(value=str(d_id)),
                    ),
                    FieldCondition(
                        key="metadata.page",
                        match=MatchAny(any=[int(p) for p in pages_set]),
                    ),
                ]
            )

            results, _ = store.client.scroll(
                collection_name=store.collection_name,
                scroll_filter=flt,
                limit=300,
                with_payload=True,
                with_vectors=False,
            )
            all_assets.extend(results)

    # ---------------------------------------------------------
    # 4) Deduplicate assets by asset_id
    # ---------------------------------------------------------
    dedup = {}
    for a in all_assets:
        payload = getattr(a, "payload", {}) or {}
        md = payload.get("metadata", {}) or {}
        aid = md.get("asset_id") or getattr(a, "id", None)
        if aid:
            dedup[str(aid)] = a

    final_assets = list(dedup.values())

    # ---------------------------------------------------------
    # 5) Rerank + GATE + Deterministic selection (top-1 or top-2)
    # ---------------------------------------------------------
    candidate_asset_ids = []
    for a in final_assets:
        payload = getattr(a, "payload", {}) or {}
        md = payload.get("metadata", {}) or {}
        aid = md.get("asset_id")
        if aid:
            candidate_asset_ids.append(str(aid))

    rel_by_asset_id = {}

    # --- rerank inside candidates
    if candidate_asset_ids:
        flt_assets = Filter(
            must=[
                FieldCondition(
                    key="metadata.user_id",
                    match=MatchValue(value=int(user_id)),
                ),
                FieldCondition(
                    key="metadata.asset_id",
                    match=MatchAny(any=candidate_asset_ids),
                ),
            ]
        )

        try:
            scored = store.similarity_search_with_relevance_scores(
                query=question,
                k=min(12, len(candidate_asset_ids)),
                filter=flt_assets,
            )

            for doc, rel in scored:
                aid = doc.metadata.get("asset_id")
                if aid:
                    rel_by_asset_id[str(aid)] = float(rel)

            def _rel(a):
                md = (getattr(a, "payload", {}) or {}).get("metadata", {}) or {}
                return float(rel_by_asset_id.get(str(md.get("asset_id")), 0.0))

            #final_assets.sort(key=_rel, reverse=True)
            final_assets.sort(key=_order)
            
        except Exception as e:
            print(f"DEBUG: asset rerank failed, keeping original order. reason={e}")

    # --- helper: score by record
    def _get_rel_record(a) -> float:
        md = (getattr(a, "payload", {}) or {}).get("metadata", {}) or {}
        return float(rel_by_asset_id.get(str(md.get("asset_id")), 0.0))

    # --- DOMAIN-AGNOSTIC GATE:
    # If the best candidate is weakly related to the question, show NO visuals.
    # This prevents irrelevant images when the question has no related asset.
    ASSET_MIN_RELEVANCE = 0.26   # tune 0.22..0.32
    ASSET_SECOND_MIN = 0.22      # minimum relevance for including second
    SCORE_GAP = 0.07             # include second if close to first

    # if final_assets and rel_by_asset_id:
        # s1 = _get_rel_record(final_assets[0])

        # if s1 < ASSET_MIN_RELEVANCE:
            # final_assets = []
        # else:
            # selected = [final_assets[0]]

            # if len(final_assets) >= 2:
                # s2 = _get_rel_record(final_assets[1])
                # if (s1 - s2) <= SCORE_GAP and s2 >= ASSET_SECOND_MIN:
                    # selected.append(final_assets[1])

            # final_assets = selected
    # else:
        # # conservative fallback: at most 1 asset
        # final_assets = final_assets[:1]

    # print("DEBUG: final selected assets:", [
        # ((getattr(a, "payload", {}) or {}).get("metadata", {}) or {}).get("asset_id")
        # for a in final_assets
    # ])
    if final_assets and rel_by_asset_id:
        try:
            print("DEBUG: final selected scores:", [round(_get_rel_record(a), 4) for a in final_assets])
        except Exception:
            pass

    # selected = []
    # if final_assets and rel_by_asset_id:
        # for a in final_assets:
            # s = _get_rel_record(a)
            # if s >= ASSET_MIN_RELEVANCE:
                # selected.append(a)
    # if selected and rel_by_asset_id:
        # try:
            # print("DEBUG: final selected scores:", [round(_get_rel_record(a), 4) for a in selected])
        # except Exception:
            # pass           
            
        
    # ---------------------------------------------------------
    # 6) Build final teacher context
    # ---------------------------------------------------------
    context = build_teacher_context(units, final_assets)

    return {
        "context": context,
        "units": units,
        "assets": final_assets,
    }
