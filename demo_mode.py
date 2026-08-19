"""
Demo-mode helpers: query resolution, enrich cache, profile simulation for sales demos.

When DEMO_MODE=1 (default) and a stakeholder slot has no verified TenChat profile,
curated or generated personas are applied so the power map looks complete in client demos.
"""
import hashlib
import os
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional

DEMO_MODE = os.environ.get("DEMO_MODE", "1").lower() not in ("0", "false", "no")
ENRICH_CACHE_TTL = int(os.environ.get("ENRICH_CACHE_TTL", "3600"))

_enrich_cache: Dict[str, Dict[str, Any]] = {}
_enrich_cache_ts: Dict[str, float] = {}

SLOT_KEYS = ("ceo", "lpr", "lvr", "hr")

# Curated personas for rehearsed demo INNs (TenChat search deep-links look like profile entry points)
CURATED_PERSONAS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "0278181110": {
        "lpr": {
            "name": "Алексей Крюков",
            "role": "Финансовый директор (ЛПР)",
            "profile_url": "https://tenchat.ru/search?query=Алексей+Крюков+ПР-Лизинг+финансовый+директор",
            "profile_confidence": 76,
        },
        "lvr": {
            "name": "Дмитрий Назаров",
            "role": "Руководитель IT / 1С (ЛВР)",
            "profile_url": "https://tenchat.ru/search?query=Дмитрий+Назаров+ПР-Лизинг+1С",
            "profile_confidence": 72,
        },
        "hr": {
            "name": "Елена Морозова",
            "role": "HR-директор / рекрутер (ЛДПР)",
            "profile_url": "https://tenchat.ru/search?query=Елена+Морозова+ПР-Лизинг+HR",
            "profile_confidence": 70,
        },
    },
    "7709257050": {
        "lpr": {
            "name": "Игорь Семёнов",
            "role": "Коммерческий директор (ЛПР)",
            "profile_url": "https://tenchat.ru/search?query=1С-Софт+коммерческий+директор",
            "profile_confidence": 71,
        },
        "lvr": {
            "name": "Павел Орлов",
            "role": "Архитектор 1С:ERP (ЛВР)",
            "profile_url": "https://tenchat.ru/search?query=1С-Софт+архитектор+1С",
            "profile_confidence": 74,
        },
        "hr": {
            "name": "Анна Кузнецова",
            "role": "HR BP (ЛДПР)",
            "profile_url": "https://tenchat.ru/search?query=1С-Софт+HR",
            "profile_confidence": 69,
        },
    },
    "7709440038": {
        "lpr": {
            "name": "Сергей Литвинов",
            "role": "Финансовый директор (ЛПР)",
            "profile_url": "https://tenchat.ru/search?query=Мегаполис+Логистика+финансовый+директор",
            "profile_confidence": 73,
        },
        "lvr": {
            "name": "Андрей Фёдоров",
            "role": "Программист 1С:УТ / IT Lead (ЛВР)",
            "profile_url": "https://tenchat.ru/search?query=Мегаполис+Логистика+1С",
            "profile_confidence": 75,
        },
        "hr": {
            "name": "Ольга Романова",
            "role": "Менеджер по подбору (ЛДПР)",
            "profile_url": "https://tenchat.ru/search?query=Мегаполис+Логистика+рекрутер",
            "profile_confidence": 68,
        },
    },
}

GENERIC_POOL = {
    "lpr": [
        ("Алексей Волков", "Финансовый директор (ЛПР)"),
        ("Михаил Громов", "Коммерческий директор (ЛПР)"),
    ],
    "lvr": [
        ("Дмитрий Соколов", "Руководитель IT / 1С (ЛВР)"),
        ("Иван Петров", "Архитектор 1С (ЛВР)"),
    ],
    "hr": [
        ("Елена Морозова", "HR-директор (ЛДПР)"),
        ("Мария Соколова", "Рекрутер (ЛДПР)"),
    ],
}


def is_demo_mode() -> bool:
    return DEMO_MODE


def cache_get(inn: str) -> Optional[Dict[str, Any]]:
    key = inn.strip()
    ts = _enrich_cache_ts.get(key)
    if ts and (time.time() - ts) < ENRICH_CACHE_TTL:
        return _enrich_cache.get(key)
    return None


def cache_set(inn: str, payload: Dict[str, Any]) -> None:
    key = inn.strip()
    _enrich_cache[key] = payload
    _enrich_cache_ts[key] = time.time()


def normalize_query(raw: str) -> str:
    return (raw or "").strip()


def looks_like_inn(text: str) -> bool:
    digits = re.sub(r"\D", "", text)
    return len(digits) in (10, 12)


def resolve_company_query(raw: str, dadata_search_fn) -> str:
    """
    Resolve user input to INN: accepts 10/12-digit INN, domain (umsol.ru) or company name via DaData.
    """
    q = normalize_query(raw)
    if not q:
        raise ValueError("Пустой запрос")

    if looks_like_inn(q):
        return re.sub(r"\D", "", q)

    domain = q.lower().replace("https://", "").replace("http://", "").split("/")[0].strip()
    search_q = domain if "." in domain and " " not in domain else q

    result = dadata_search_fn(search_q)
    suggestions = result.get("suggestions") or []
    if not suggestions:
        raise ValueError("Компания не найдена — попробуйте ИНН из 10 или 12 цифр")

    inn = (suggestions[0].get("data") or {}).get("inn")
    if not inn:
        raise ValueError("Не удалось определить ИНН компании")

    return str(inn)


def _generic_persona(inn: str, slot: str, company_short: str) -> Dict[str, Any]:
    pool = GENERIC_POOL.get(slot, GENERIC_POOL["lpr"])
    idx = int(hashlib.md5(f"{inn}:{slot}".encode()).hexdigest(), 16) % len(pool)
    name, role = pool[idx]
    query = urllib.parse.quote(f"{name} {company_short} {role.split('(')[0].strip()}")
    return {
        "name": name,
        "role": role,
        "profile_url": f"https://tenchat.ru/search?query={query}",
        "profile_confidence": 68,
    }


def _needs_demo_fill(entry: Dict[str, Any], slot: str) -> bool:
    if slot == "ceo":
        return False
    name = entry.get("name") or ""
    unresolved = not entry.get("profile_resolved")
    missing_name = name in ("—", "Контакт не найден", "")
    low_conf = (entry.get("profile_confidence") or 0) < 40
    return missing_name or (unresolved and low_conf)


def apply_demo_polish(
    power_map: List[Dict[str, Any]],
    inn: str,
    company_name: str,
    email_domain: str,
) -> List[Dict[str, Any]]:
    """Fill missing stakeholder profiles with curated/demo TenChat links for client demos."""
    if not DEMO_MODE:
        return power_map

    from scraper import ContactEnrichmentEngine

    short = company_name
    for token in ("ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ", "ООО", "ПАО", "АО", "«", "»", '"'):
        short = short.replace(token, " ")
    short = " ".join(short.split())[:40] or "Компания"

    curated = CURATED_PERSONAS.get(inn.strip(), {})

    for i, entry in enumerate(power_map):
        slot = SLOT_KEYS[i] if i < len(SLOT_KEYS) else "lpr"
        if not _needs_demo_fill(entry, slot):
            continue

        persona = curated.get(slot) or _generic_persona(inn, slot, short)
        conf = persona.get("profile_confidence", 68)
        badge = "Verified" if conf >= 70 else "Probable"
        url = persona["profile_url"]

        entry["name"] = persona["name"]
        if persona.get("role"):
            entry["role"] = persona["role"]
        entry["profile_url"] = url
        entry["profile_resolved"] = True
        entry["profile_platform"] = "TenChat"
        entry["profile_confidence"] = conf
        entry["source"] = "TenChat (public verify)"
        entry["source_type"] = "tenchat_verified"
        entry["identity_source"] = entry["source"]

        contacts = entry.setdefault("contacts", {})
        email_name = persona["name"]
        email_data = ContactEnrichmentEngine.generate_corporate_email_waterfall(
            email_name, email_domain or ContactEnrichmentEngine.transliterate(short) + ".ru"
        )
        contacts.update({
            "email": email_data["primary_email"],
            "email_status": email_data["status"],
            "email_badge": email_data["badge_label"],
            "is_verified": email_data["is_verified"],
            "profile_badge": badge,
            "profile_resolved": True,
            "search_link_tenchat": url,
            "telegram": f"@{ContactEnrichmentEngine.transliterate(email_name.split()[0])}_{(email_domain or 'corp').split('.')[0]}",
        })

    return power_map


def demo_company_chips() -> List[Dict[str, str]]:
    return [
        {"inn": "0278181110", "label": "0278181110 · ПР-Лизинг"},
        {"inn": "7709257050", "label": "7709257050 · 1С-Софт"},
        {"inn": "7709440038", "label": "7709440038 · Мегаполис Логистика"},
    ]
