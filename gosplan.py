"""Gosplan REST API — EIS 44/223/615 without SOAP."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

TEST_BASE = "https://v2test.gosplan.info"
PROD_BASE = "https://v2.gosplan.info"
DEFAULT_DAYS = "30d"


def _api_key() -> str:
    return os.environ.get("GOSPLAN_API_KEY", "").strip()


def _base_url() -> str:
    explicit = os.environ.get("GOSPLAN_API_BASE", "").strip().rstrip("/")
    if explicit:
        return explicit
    return PROD_BASE if _api_key() else TEST_BASE


def is_configured() -> bool:
    """Prod key set, or test server available without key."""
    return bool(_api_key()) or _base_url() == TEST_BASE


def session_status() -> Dict[str, Any]:
    base = _base_url()
    mode = "prod" if base == PROD_BASE and _api_key() else "test"
    if _api_key() and base == PROD_BASE:
        return {
            "available": True,
            "configured": True,
            "mode": "prod",
            "base_url": base,
            "message": "Gosplan API ключ задан (ЕИС 44/223 через REST)",
        }
    return {
        "available": True,
        "configured": True,
        "mode": mode,
        "base_url": base,
        "message": (
            f"Gosplan test API ({TEST_BASE.replace('https://', '')}) без ключа, с лимитами. "
            "Прод: GOSPLAN_API_KEY (7 дней trial — wiki.gosplan.info)."
        ),
    }


def probe_api() -> Dict[str, Any]:
    """Lightweight health check for sources-status and startup diagnostics."""
    base = _base_url()
    mode = "prod" if base == PROD_BASE and _api_key() else "test"
    host = base.replace("https://", "").replace("http://", "")
    try:
        data, err = _get_json(
            "/fz44/purchases",
            {
                "object_info": "поставка",
                "published_forpast": "7d",
                "limit": 1,
                "skip": 0,
            },
        )
        if err == "http_429":
            return {
                "available": True,
                "reachable": True,
                "configured": True,
                "mode": mode,
                "base_url": base,
                "rate_limited": True,
                "message": f"Gosplan ({host}): API доступен, но лимит запросов (429). Повторите через минуту.",
            }
        if err:
            if err == "http_401" and not _api_key():
                detail = f"Gosplan ({host}): нужен GOSPLAN_API_KEY или GOSPLAN_API_BASE={TEST_BASE}"
            else:
                detail = f"Gosplan ({host}): ошибка {err}"
            return {
                "available": False,
                "reachable": False,
                "configured": mode == "test" or bool(_api_key()),
                "mode": mode,
                "base_url": base,
                "message": detail,
            }
        found = len(data) if isinstance(data, list) else 0
        return {
            "available": True,
            "reachable": True,
            "configured": True,
            "mode": mode,
            "base_url": base,
            "sample_count": found,
            "message": f"Gosplan ({host}, {mode}): API отвечает",
        }
    except Exception as exc:
        return {
            "available": False,
            "reachable": False,
            "configured": mode == "test" or bool(_api_key()),
            "mode": mode,
            "base_url": base,
            "message": f"Gosplan ({host}): {exc}",
        }


def _headers() -> Dict[str, str]:
    key = _api_key()
    if not key:
        return {"Accept": "application/json"}
    return {"Accept": "application/json", "apikey": key}


def _search_query(keyword: str) -> str:
    q = (keyword or "").strip()
    if len(q) >= 3:
        return q
    lower = q.lower()
    if "1" in lower and "с" in lower:
        return "1С предприятие"
    if q:
        return f"{q} закупка"
    return "поставка"


def _get_json(path: str, params: Dict[str, Any]) -> Tuple[Any, Optional[str]]:
    url = f"{_base_url()}{path}"
    try:
        resp = requests.get(url, params=params, headers=_headers(), timeout=25)
        if resp.status_code == 429:
            return None, "http_429"
        if resp.status_code in (401, 403):
            return None, f"http_{resp.status_code}"
        if resp.status_code == 422:
            return None, "validation_error"
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}"
        return resp.json(), None
    except requests.RequestException as exc:
        return None, exc.__class__.__name__


def _customer_inn(item: Dict[str, Any], law: str) -> str:
    if law == "fz223":
        raw = item.get("customer") or item.get("placer") or ""
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        return "".join(ch for ch in str(raw) if ch.isdigit())
    customers = item.get("customers") or []
    if isinstance(customers, list) and customers:
        inn = "".join(ch for ch in str(customers[0]) if ch.isdigit())
        if len(inn) in (10, 12):
            return inn
    responsible = item.get("responsible") or ""
    return "".join(ch for ch in str(responsible) if ch.isdigit())


def _zakupki_url(purchase_number: str, law: str) -> str:
    reg = (purchase_number or "").strip()
    if not reg:
        return ""
    if law == "fz223" or (reg.isdigit() and reg.startswith("3") and len(reg) <= 12):
        return (
            "https://zakupki.gov.ru/epz/order/notice/notice223/view/common-info.html"
            f"?regNumber={reg}"
        )
    return (
        "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html"
        f"?regNumber={reg}"
    )


def _org_name(inn: str, law: str, cache: Dict[str, str]) -> str:
    if not inn or inn in cache:
        return cache.get(inn, "")
    path = f"/{law}/organizations"
    data, err = _get_json(path, {"inn": inn, "limit": 1})
    if err or not isinstance(data, list) or not data:
        cache[inn] = ""
        return ""
    source = data[0].get("source") or {}
    if law == "fz223":
        main = source.get("mainInfo") or {}
        name = (main.get("shortName") or main.get("fullName") or "").strip()
    else:
        name = (source.get("shortName") or source.get("fullName") or "").strip()
        if not name and isinstance(source.get("name"), str):
            name = source["name"].strip()
    cache[inn] = name
    return name


def normalize_item(
    item: Dict[str, Any],
    *,
    law: str,
    org_cache: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    inn = _customer_inn(item, law)
    if len(inn) not in (10, 12):
        return None
    cache = org_cache if org_cache is not None else {}
    name = _org_name(inn, law, cache) or "Заказчик"
    reg = str(item.get("purchase_number") or "").strip()
    title = (item.get("object_info") or "").strip() or f"Закупка {reg}"
    max_price = item.get("max_price")
    price_text = ""
    if max_price not in (None, ""):
        try:
            price_text = str(float(max_price))
        except (TypeError, ValueError):
            price_text = str(max_price)
    return {
        "inn": inn,
        "name": name,
        "title": title,
        "reg_number": reg,
        "price_text": price_text,
        "url": _zakupki_url(reg, law),
        "source": "gosplan",
        "law": law,
    }


def search_purchases(
    query: str,
    *,
    limit: int = 30,
    days: str = DEFAULT_DAYS,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Search fz44 + fz223 by object_info. Returns raw purchase dicts tagged with _law."""
    q = _search_query(query)
    params = {
        "object_info": q,
        "published_forpast": days,
        "limit": min(max(limit, 1), 100),
        "skip": 0,
    }
    merged: List[Dict[str, Any]] = []
    last_err: Optional[str] = None
    for law in ("fz44", "fz223"):
        data, err = _get_json(f"/{law}/purchases", params)
        if err:
            last_err = err
            continue
        if not isinstance(data, list):
            last_err = "bad_payload"
            continue
        for row in data:
            if isinstance(row, dict):
                tagged = dict(row)
                tagged["_law"] = law
                merged.append(tagged)
    if not merged and last_err:
        return [], last_err
    return merged, None


def scan_for_offer(
    product_keyword: str,
    *,
    limit: int = 5,
) -> Dict[str, Any]:
    status = session_status()
    if not status.get("available"):
        return {
            "scan_status": "gosplan_missing",
            "scan_message": "Gosplan недоступен",
            "items": [],
            "raw_count": 0,
        }

    raw_items, err = search_purchases(product_keyword, limit=max(limit * 4, 20))
    if err:
        msg = f"Gosplan не ответил ({err})"
        if err == "http_429":
            msg = (
                f"Gosplan test ({TEST_BASE.replace('https://', '')}): лимит запросов (429). "
                "Подождите минуту или задайте GOSPLAN_API_KEY для prod."
            )
        elif err == "http_401" and not _api_key():
            msg = (
                f"Gosplan prod требует GOSPLAN_API_KEY "
                f"(test без ключа: GOSPLAN_API_BASE={TEST_BASE})"
            )
        return {
            "scan_status": "gosplan_unreachable",
            "scan_message": msg,
            "items": [],
            "raw_count": 0,
        }

    org_cache: Dict[str, str] = {}
    out: List[Dict[str, Any]] = []
    seen_inns: set[str] = set()
    skipped_no_inn = 0
    for raw in raw_items:
        law = raw.get("_law") or "fz44"
        norm = normalize_item(raw, law=law, org_cache=org_cache)
        if not norm:
            skipped_no_inn += 1
            continue
        if norm["inn"] in seen_inns:
            continue
        seen_inns.add(norm["inn"])
        out.append(norm)
        if len(out) >= limit:
            break

    mode = status.get("mode") or "test"
    if not raw_items:
        return {
            "scan_status": "gosplan_empty",
            "scan_message": f"Gosplan ({mode}): закупок по запросу не найдено",
            "items": [],
            "raw_count": 0,
        }
    if not out:
        return {
            "scan_status": "no_inn_matches",
            "scan_message": (
                f"Gosplan ({mode}) вернул {len(raw_items)} закупок, но без ИНН заказчика"
            ),
            "items": [],
            "raw_count": len(raw_items),
        }
    return {
        "scan_status": "ok",
        "scan_message": f"Gosplan ({mode}): найдено {len(out)} заказчиков с ИНН",
        "items": out,
        "raw_count": len(raw_items),
    }
