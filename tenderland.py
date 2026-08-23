"""Tenderland search API — cheapest JSON aggregator for RF tenders."""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

SEARCH_URL = "https://tenderland.ru/Api/v1/Search/Find"


def is_configured() -> bool:
    return bool(os.environ.get("TENDERLAND_API_KEY", "").strip())


def session_status() -> Dict[str, Any]:
    if not is_configured():
        return {
            "available": False,
            "configured": False,
            "message": (
                "TENDERLAND_API_KEY не задан. Бесплатный тест 3 дня: tenderland.ru "
                "(скажите менеджеру, что нужен API-ключ)."
            ),
        }
    return {
        "available": True,
        "configured": True,
        "message": "Tenderland API ключ задан",
    }


def _api_key() -> str:
    return os.environ.get("TENDERLAND_API_KEY", "").strip()


def search_tenders(
    query: str,
    *,
    days: int = 30,
    pagesize: int = 20,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """POST Search/Find. Returns items or an error code."""
    if not is_configured():
        return [], "not_configured"
    q = (query or "").strip()
    if not q:
        return [], "empty_query"
    since = date.today() - timedelta(days=max(1, days))
    payload = {
        "fields": [
            "tender_regNumber",
            "tender_name",
            "tender_beginPrice",
            "tender_customerInn",
            "tender_customerName",
        ],
        "filters": {
            "and": [
                {
                    "id": 101,
                    "name": "file_content",
                    "type": "text",
                    "include": q.replace(" ", "++"),
                },
                {
                    "id": 110,
                    "name": "tender_publishDate",
                    "type": "range",
                    "from": f"{since.isoformat()} ",
                    "to": f"{date.today().isoformat()} ",
                },
            ]
        },
        "pagesize": min(pagesize, 50),
        "skip": 0,
    }
    try:
        resp = requests.post(
            SEARCH_URL,
            params={"apiKey": _api_key()},
            json=payload,
            timeout=25,
        )
        if resp.status_code in (401, 403):
            return [], f"http_{resp.status_code}"
        if resp.status_code != 200:
            return [], f"http_{resp.status_code}"
        data = resp.json() if resp.content else {}
        items = data.get("items") or data.get("Items") or []
        if not isinstance(items, list):
            return [], "bad_payload"
        return items, None
    except requests.RequestException as exc:
        return [], exc.__class__.__name__


def _pick(item: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        val = item.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text and text.lower() not in ("none", "null"):
            return text
    return ""


def normalize_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    inn = "".join(ch for ch in _pick(item, "tender_customerInn", "customerInn", "inn") if ch.isdigit())
    if len(inn) not in (10, 12):
        return None
    name = _pick(item, "tender_customerName", "customerName", "organizerName") or "Заказчик"
    title = _pick(item, "tender_name", "name")
    reg = _pick(item, "tender_regNumber", "regNumber")
    price_raw = _pick(item, "tender_beginPrice", "beginPrice", "nmck")
    url = ""
    if reg.startswith("0") or (reg.isdigit() and len(reg) >= 18):
        url = (
            "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html"
            f"?regNumber={reg}"
        )
    elif reg:
        url = (
            "https://zakupki.gov.ru/epz/order/notice/notice223/view/common-info.html"
            f"?regNumber={reg}"
        )
    return {
        "inn": inn,
        "name": name,
        "title": title or f"Закупка {reg}",
        "reg_number": reg,
        "price_text": price_raw,
        "url": url,
    }


def scan_for_offer(
    product_keyword: str,
    *,
    limit: int = 5,
) -> Dict[str, Any]:
    status = session_status()
    if not status.get("configured"):
        return {
            "scan_status": "tenderland_missing",
            "scan_message": status.get("message"),
            "items": [],
            "raw_count": 0,
        }
    items, err = search_tenders(product_keyword, pagesize=30)
    if err:
        return {
            "scan_status": "tenderland_unreachable",
            "scan_message": f"Tenderland не ответил ({err})",
            "items": [],
            "raw_count": 0,
        }
    out: List[Dict[str, Any]] = []
    seen = set()
    for raw in items:
        norm = normalize_item(raw)
        if not norm or norm["inn"] in seen:
            continue
        seen.add(norm["inn"])
        out.append(norm)
        if len(out) >= limit:
            break
    if not items:
        return {
            "scan_status": "tenderland_empty",
            "scan_message": "Tenderland доступен, закупок по запросу не найдено",
            "items": [],
            "raw_count": 0,
        }
    if not out:
        return {
            "scan_status": "no_inn_matches",
            "scan_message": (
                f"Tenderland вернул {len(items)} закупок, но без ИНН заказчика"
            ),
            "items": [],
            "raw_count": len(items),
        }
    return {
        "scan_status": "ok",
        "scan_message": f"Найдено {len(out)} заказчиков с ИНН",
        "items": out,
        "raw_count": len(items),
    }
