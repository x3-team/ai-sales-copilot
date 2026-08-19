"""
Company card status: signal → named → reachable (monotonic — never downgrade on re-enrich).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

STATUS_SIGNAL = "signal"
STATUS_NAMED = "named"
STATUS_REACHABLE = "reachable"

STATUS_LABELS = {
    STATUS_SIGNAL: "Сигнал",
    STATUS_NAMED: "Есть имя",
    STATUS_REACHABLE: "Касание",
}

STATUS_RANK = {
    STATUS_SIGNAL: 0,
    STATUS_NAMED: 1,
    STATUS_REACHABLE: 2,
}

QUEUE_REACHABLE = "reachable"
QUEUE_IN_WORK = "in_work"

PLACEHOLDER_NAMES = frozenset(
    {"", "—", "-", "Контакт не найден", "Руководитель", "Руководитель (ЕГРЮЛ)"}
)
EMPTY_CONTACT = frozenset({"", "—", "-", None})

GENERIC_EMAIL_LOCAL_PREFIXES = (
    "kanc",
    "info",
    "office",
    "admin",
    "contact",
    "mail",
    "hello",
    "support",
    "sales",
    "pr",
    "hr",
    "vacancy",
    "buh",
    "accounting",
    "secretary",
    "reception",
    "inbox",
    "zakaz",
    "order",
    "help",
    "service",
    "opt",
    "shop",
)


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, STATUS_LABELS[STATUS_SIGNAL])


def merge_status(current: Optional[str], computed: str) -> str:
    """Repeat search must not downgrade — only upgrade when evidence improves."""
    cur = (current or STATUS_SIGNAL).lower()
    new = (computed or STATUS_SIGNAL).lower()
    if STATUS_RANK.get(new, 0) > STATUS_RANK.get(cur, 0):
        return new
    return cur if cur in STATUS_RANK else STATUS_SIGNAL


def queue_for_status(status: str) -> str:
    return QUEUE_REACHABLE if status == STATUS_REACHABLE else QUEUE_IN_WORK


def is_real_name(name: Optional[str]) -> bool:
    return bool(name and str(name).strip() not in PLACEHOLDER_NAMES)


def is_real_contact(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in EMPTY_CONTACT
    return bool(value)


def is_generic_office_email(email: Optional[str]) -> bool:
    if not email or "@" not in email:
        return False
    local = email.split("@", 1)[0].lower().strip()
    local = re.sub(r"[._+\-]", "", local)
    for prefix in GENERIC_EMAIL_LOCAL_PREFIXES:
        p = prefix.replace("_", "")
        if local == p or local.startswith(p):
            return True
    return False


COMPANY_DIRECTORY_SOURCE_HINTS = (
    "checko.ru/company",
    "checko.ru/",
    "companian.ru/",
    "sbis.ru/contragents",
    "rusprofile.ru/",
    "kzorka.ddbq.ru",
    "ddbq.ru",
)


def is_company_directory_source(source_url: Optional[str]) -> bool:
    if not source_url:
        return False
    u = source_url.lower()
    return any(h in u for h in COMPANY_DIRECTORY_SOURCE_HINTS)


def is_hh_vacancy_source(source_url: Optional[str]) -> bool:
    if not source_url:
        return False
    return "hh.ru/vacancy/" in source_url.lower()


def is_personal_reachable_contact(
    contact_type: str,
    value: Any,
    source_url: Optional[str] = None,
) -> bool:
    """Only direct LPR contacts count — not Checko/SBIS/Rusprofile company phones or office mail."""
    if not is_real_contact(value):
        return False
    if contact_type == "email" and is_generic_office_email(str(value)):
        return False
    if is_hh_vacancy_source(source_url):
        return contact_type in ("phone", "telegram", "email")
    if contact_type in ("phone", "telegram", "email") and is_company_directory_source(source_url):
        return False
    if contact_type == "phone" and source_url and "checko.ru" in source_url.lower():
        return False
    return contact_type in ("phone", "telegram", "email")


def is_personal_profile_url(url: Optional[str]) -> bool:
    """Direct person profile on social — not EGRUL/Checko/SBIS registry pages."""
    if not url or not str(url).startswith("http"):
        return False
    u = url.lower().split("?", 1)[0]
    if any(x in u for x in (
        "rusprofile.ru",
        "checko.ru",
        "sbis.ru",
        "companian.ru",
        "bo.nalog.ru",
        "/search",
        "hh.ru/vacancy",
        "hh.ru/search",
        "hh.ru/employer",
    )):
        return False
    if "linkedin.com/in/" in u:
        return True
    if "setka.ru/users/" in u:
        return True
    if "tenchat.ru" in u:
        path = urlparse(u).path.strip("/").lower()
        if not path:
            return False
        if path.startswith("u/"):
            return True
        if path.startswith("b/") or path.startswith("company"):
            return False
        last = path.split("/")[-1]
        if last.isdigit() or re.fullmatch(r"0\d+", last):
            return False
        if last.startswith("id") and last[2:].isdigit():
            return False
        if "company" in path:
            return False
        if re.search(r"[a-zа-яё]", last, re.I) and len(last) >= 3:
            return True
        return False
    return False


def extract_triggers(
    vacancies: Optional[List[Dict[str, Any]]] = None,
    extra: Optional[List[str]] = None,
) -> List[str]:
    out: List[str] = []
    for v in vacancies or []:
        title = (v.get("title") or "").strip()
        if title:
            out.append(title)
    for item in extra or []:
        text = (item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def compute_card_status(
    *,
    lprs: Optional[List[Dict[str, Any]]] = None,
    vacancies: Optional[List[Dict[str, Any]]] = None,
    ceo_name: Optional[str] = None,
    triggers: Optional[List[str]] = None,
    people: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Derive card status from triggers, names, and person-level contacts.
    Generic office mail (kanc@, info@) does not yield reachable.
    """
    trigger_list = list(triggers or [])
    if not trigger_list:
        trigger_list = extract_triggers(vacancies)
    has_trigger = len(trigger_list) > 0

    has_named = is_real_name(ceo_name)
    has_reachable = False

    entries: List[Dict[str, Any]] = list(lprs or [])
    if people:
        for person in people:
            contacts_raw = person.get("contacts") or []
            entries.append(
                {
                    "name": person.get("fio") or person.get("name"),
                    "profile_url": person.get("profile_url"),
                    "profile_resolved": (person.get("meta") or {}).get("profile_resolved"),
                    "contacts": {
                        "email": next((c["value"] for c in contacts_raw if c.get("type") == "email"), None),
                        "phone": next((c["value"] for c in contacts_raw if c.get("type") == "phone"), None),
                        "telegram": next((c["value"] for c in contacts_raw if c.get("type") == "telegram"), None),
                    },
                    "_all_contacts": contacts_raw,
                }
            )

    for entry in entries:
        if is_real_name(entry.get("name")):
            has_named = True
        contacts = entry.get("contacts") or {}
        all_contacts = entry.get("_all_contacts") or []
        email = contacts.get("email")
        phone = contacts.get("phone")
        telegram = contacts.get("telegram")
        profile_url = entry.get("profile_url") or ""

        for c in all_contacts:
            ctype = c.get("type") or ""
            if is_personal_reachable_contact(ctype, c.get("value"), c.get("source_url")):
                has_reachable = True
        if not all_contacts:
            if is_personal_reachable_contact("phone", phone, None):
                has_reachable = True
            if is_personal_reachable_contact("telegram", telegram, None):
                has_reachable = True
            if is_personal_reachable_contact("email", email, None):
                has_reachable = True
        if entry.get("profile_resolved") and is_personal_profile_url(profile_url):
            has_reachable = True
        elif is_personal_profile_url(profile_url) and is_real_name(entry.get("name")):
            has_reachable = True

    if has_reachable:
        return STATUS_REACHABLE
    if has_named:
        return STATUS_NAMED
    if has_trigger:
        return STATUS_SIGNAL
    return STATUS_SIGNAL


def card_status_payload(
    status: str,
    *,
    triggers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "status_label": status_label(status),
        "queue": queue_for_status(status),
        "queue_label": "Можно касаться" if status == STATUS_REACHABLE else "В работе",
        "triggers": triggers or [],
    }


def compute_from_enrich_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    legal = payload.get("dadata_legal_profile") or {}
    lprs = (payload.get("lpr_matrix") or {}).get("lprs") or []
    vacancies = (payload.get("hh_recruitment_profile") or {}).get("vacancies") or []
    insights = (payload.get("sales_ai_insights") or {}).get("insights") or []
    triggers = extract_triggers(vacancies, insights)
    status = compute_card_status(
        lprs=lprs,
        vacancies=vacancies,
        ceo_name=legal.get("ceo"),
        triggers=triggers,
    )
    return card_status_payload(status, triggers=triggers)
