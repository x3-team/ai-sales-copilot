"""DaData party lookup — INN resolution with active-entity check."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

INACTIVE_STATE_STATUSES = frozenset({
    "LIQUIDATED",
    "LIQUIDATING",
    "BANKRUPT",
    "REORGANIZING",
})


def is_configured() -> bool:
    return bool(os.environ.get("DADATA_API_KEY", "").strip())


def resolve_party_inn(employer_name: str) -> Dict[str, Any]:
    """
    Match employer name to INN via DaData suggest/party.
    Returns inn (empty if no confident match or inactive entity).
    """
    name = (employer_name or "").strip()
    if not name:
        return {"inn": "", "matched_name": "", "active": False, "reason": "empty_name"}
    if not is_configured():
        return {"inn": "", "matched_name": "", "active": False, "reason": "dadata_missing"}

    try:
        url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {os.environ['DADATA_API_KEY'].strip()}",
        }
        resp = requests.post(
            url,
            json={"query": name, "count": 5, "status": ["ACTIVE"]},
            headers=headers,
            timeout=10,
        )
        if resp.status_code != 200:
            return {
                "inn": "",
                "matched_name": "",
                "active": False,
                "reason": f"dadata_http_{resp.status_code}",
            }
        suggestions = resp.json().get("suggestions") or []
        if not suggestions:
            return {"inn": "", "matched_name": "", "active": False, "reason": "no_match"}

        clean_query = _normalize_name(name)
        for suggestion in suggestions:
            data = suggestion.get("data") or {}
            inn = (data.get("inn") or "").strip()
            if not inn:
                continue
            state = data.get("state") or {}
            status = (state.get("status") or "").upper()
            if status in INACTIVE_STATE_STATUSES:
                continue
            matched = (suggestion.get("value") or "").strip()
            if _names_match(clean_query, _normalize_name(matched)):
                return {
                    "inn": inn,
                    "matched_name": matched,
                    "active": True,
                    "reason": "matched",
                }
        top = suggestions[0]
        data = top.get("data") or {}
        inn = (data.get("inn") or "").strip()
        state = data.get("state") or {}
        status = (state.get("status") or "").upper()
        if inn and status not in INACTIVE_STATE_STATUSES:
            matched = (top.get("value") or "").strip()
            if _loose_names_match(name, matched):
                return {
                    "inn": inn,
                    "matched_name": matched,
                    "active": True,
                    "reason": "loose_match",
                }
        return {"inn": "", "matched_name": "", "active": False, "reason": "no_confident_match"}
    except Exception:
        return {"inn": "", "matched_name": "", "active": False, "reason": "dadata_error"}


def _normalize_name(value: str) -> str:
    import re

    text = (value or "").lower()
    for token in ("ооо", "оао", "пао", "ао", "ип", "«", "»", '"'):
        text = text.replace(token, " ")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _names_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a[:8] in b or b[:8] in a:
        return True
    ta = [t for t in a.split() if len(t) > 2]
    tb = [t for t in b.split() if len(t) > 2]
    if not ta or not tb:
        return False
    overlap = sum(1 for t in ta if t in b)
    return overlap >= min(2, len(ta))


def _loose_names_match(query: str, matched: str) -> bool:
    return _names_match(_normalize_name(query), _normalize_name(matched))


def find_party_by_inn(inn: str) -> Dict[str, Any]:
    """
    Lookup legal entity by INN via DaData findById/party.
    Returns normalized fields or empty result with reason.
    """
    clean = "".join(ch for ch in (inn or "") if ch.isdigit())
    if len(clean) not in (10, 12):
        return {
            "inn": clean,
            "name": "",
            "ceo": "",
            "ceo_post": "",
            "active": False,
            "reason": "bad_inn",
        }
    if not is_configured():
        return {
            "inn": clean,
            "name": "",
            "ceo": "",
            "ceo_post": "",
            "active": False,
            "reason": "dadata_missing",
        }

    try:
        url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {os.environ['DADATA_API_KEY'].strip()}",
        }
        resp = requests.post(url, json={"query": clean}, headers=headers, timeout=10)
        if resp.status_code != 200:
            return {
                "inn": clean,
                "name": "",
                "ceo": "",
                "ceo_post": "",
                "active": False,
                "reason": f"dadata_http_{resp.status_code}",
            }
        suggestions = resp.json().get("suggestions") or []
        if not suggestions:
            return {
                "inn": clean,
                "name": "",
                "ceo": "",
                "ceo_post": "",
                "active": False,
                "reason": "not_found",
            }
        item = suggestions[0]
        data = item.get("data") or {}
        state = data.get("state") or {}
        status = (state.get("status") or "").upper()
        if status in INACTIVE_STATE_STATUSES:
            return {
                "inn": clean,
                "name": (item.get("value") or "").strip(),
                "ceo": "",
                "ceo_post": "",
                "active": False,
                "reason": "inactive",
            }
        management = data.get("management") or {}
        ceo = ""
        ceo_post = ""
        if isinstance(management, dict):
            ceo = (management.get("name") or "").strip()
            ceo_post = (management.get("post") or "").strip()
        return {
            "inn": (data.get("inn") or clean).strip(),
            "name": (item.get("value") or "").strip(),
            "ceo": ceo,
            "ceo_post": ceo_post,
            "active": True,
            "reason": "ok",
        }
    except Exception:
        return {
            "inn": clean,
            "name": "",
            "ceo": "",
            "ceo_post": "",
            "active": False,
            "reason": "dadata_error",
        }
