"""Merge procurement scans from Gosplan + Tenderland."""
from __future__ import annotations

from typing import Any, Dict, List


def _merge_items(scans: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for scan in scans:
        for item in scan.get("items") or []:
            inn = (item.get("inn") or "").strip()
            if not inn or inn in seen:
                continue
            seen.add(inn)
            merged.append(item)
            if len(merged) >= limit:
                return merged
    return merged


def scan_for_offer(product_keyword: str, *, limit: int = 5) -> Dict[str, Any]:
    import gosplan
    import tenderland

    gp = gosplan.scan_for_offer(product_keyword, limit=limit)
    tl = tenderland.scan_for_offer(product_keyword, limit=limit)
    items = _merge_items([gp, tl], limit)
    parts = [gp.get("scan_message") or gp.get("scan_status"), tl.get("scan_message") or tl.get("scan_status")]
    message = " · ".join(p for p in parts if p)

    if items:
        return {
            "scan_status": "ok",
            "scan_message": message or f"Найдено {len(items)} заказчиков с ИНН",
            "items": items,
            "raw_count": int(gp.get("raw_count") or 0) + int(tl.get("raw_count") or 0),
            "sources": {
                "gosplan": gp.get("scan_status"),
                "tenderland": tl.get("scan_status"),
            },
        }

    gp_st = gp.get("scan_status") or ""
    tl_st = tl.get("scan_status") or ""
    if gp_st == "ok" or tl_st == "ok":
        scan_status = "no_inn_matches"
    elif gp_st in ("gosplan_missing",) and tl_st in ("tenderland_missing",):
        scan_status = "procurement_missing"
    elif "unreachable" in gp_st or "unreachable" in tl_st:
        scan_status = "procurement_unreachable"
    elif gp_st.endswith("_empty") and tl_st.endswith("_empty"):
        scan_status = "procurement_empty"
    else:
        scan_status = gp_st or tl_st or "procurement_empty"

    return {
        "scan_status": scan_status,
        "scan_message": message or "Источники закупок не вернули заказчиков с ИНН",
        "items": [],
        "raw_count": int(gp.get("raw_count") or 0) + int(tl.get("raw_count") or 0),
        "sources": {
            "gosplan": gp_st,
            "tenderland": tl_st,
        },
    }
