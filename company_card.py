"""Demand card from memory — no DaData required, no invented contacts."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import company_status

PACK_HIRING = "hiring"
PACK_PROCUREMENT = "procurement"
PACK_UNKNOWN = "unknown"

PACK_LABELS = {
    PACK_HIRING: "Найм",
    PACK_PROCUREMENT: "Закупка",
    PACK_UNKNOWN: "Сигнал",
}


def dadata_available() -> bool:
    return bool(os.environ.get("DADATA_API_KEY", "").strip())


def detect_pack(triggers: Optional[List[str]] = None, sources: Optional[List[str]] = None) -> str:
    blob = " ".join(triggers or []).lower()
    src = " ".join(sources or []).lower()
    text = f"{blob} {src}"
    if "zakupki.gov.ru" in text or "закупка:" in text or "procurement" in text:
        return PACK_PROCUREMENT
    if "habr" in text or "hh.ru" in text or blob.startswith("hh:") or blob.startswith("habr:"):
        return PACK_HIRING
    return PACK_UNKNOWN if not (triggers or sources) else PACK_HIRING


def extract_primary_trigger(triggers: Optional[List[str]] = None) -> Dict[str, str]:
    for raw in triggers or []:
        text = (raw or "").strip()
        if not text:
            continue
        url_match = re.search(r"https?://\S+", text)
        url = url_match.group(0).rstrip(").,;") if url_match else ""
        kind = "signal"
        if "zakupki.gov.ru" in text.lower() or text.lower().startswith("закупка"):
            kind = PACK_PROCUREMENT
        elif "habr" in text.lower():
            kind = "habr"
        elif "hh.ru" in text.lower() or text.lower().startswith("hh:"):
            kind = "hh"
        return {"kind": kind, "label": text, "url": url}
    return {"kind": "", "label": "", "url": ""}


def starting_person_from_people(people: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    for person in people:
        fio = (person.get("fio") or "").strip()
        if not company_status.is_real_name(fio):
            continue
        return {
            "name": fio,
            "role": (person.get("role") or "руководитель").strip(),
            "source": "ЕГРЮЛ / реестр (seed)",
        }
    return None


def build_pitch(
    *,
    offer: Optional[Dict[str, Any]] = None,
    company_name: str,
    start_name: str,
    trigger_label: str,
    pack: str,
) -> str:
    offer = offer or {}
    product = (offer.get("product_name") or "наше решение").strip()
    value = (offer.get("value_proposition") or "").strip()
    greet = start_name.split()[0] if start_name else ""
    who = f"{greet}, " if greet else ""
    reason = trigger_label or "открытый сигнал спроса"
    if pack == PACK_PROCUREMENT:
        lead = (
            f"{who}вижу закупку «{company_name}»: {reason}. "
            f"Можем закрыть поставку / работу по профилю «{product}»."
        )
    else:
        lead = (
            f"{who}у «{company_name}» открыт найм: {reason}. "
            f"Это обычно момент, когда быстрее закрыть задачу с подрядчиком «{product}», чем ждать штат."
        )
    if value:
        return f"{lead} {value} Письмо отправляете вы — это черновик первого касания."
    return f"{lead} Готов коротко созвониться и показать, как это выглядит на ваших процессах."


def build_copy_text(card: Dict[str, Any]) -> str:
    lines = [
        card.get("name") or "",
        f"ИНН {card.get('inn')}",
    ]
    person = card.get("starting_person") or {}
    if person.get("name"):
        lines.append(f"Начать с: {person['name']}" + (f", {person['role']}" if person.get("role") else ""))
    trigger = card.get("primary_trigger") or {}
    if trigger.get("label"):
        lines.append(trigger["label"])
    if card.get("pitch"):
        lines.append("")
        lines.append(card["pitch"])
    lines.append("")
    lines.append("Письмо отправляете сами.")
    return "\n".join(line for line in lines if line is not None)


def build_company_card(inn: str, offer: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    import memory_store

    inn = re.sub(r"\D", "", inn or "")
    if not inn:
        return None
    row = memory_store.get_company(inn)
    if not row:
        return None

    people = memory_store.list_people(inn)
    triggers = row.get("triggers") or []
    sources = row.get("sources") or []
    pack = detect_pack(triggers, sources if isinstance(sources, list) else [])
    payload = row.get("enrich_payload") if isinstance(row.get("enrich_payload"), dict) else {}
    note = (payload or {}).get("seed_note") or ""
    person = starting_person_from_people(people)
    trigger = extract_primary_trigger(triggers)
    status = row.get("card_status") or company_status.STATUS_SIGNAL
    pitch = build_pitch(
        offer=offer,
        company_name=row.get("name") or "",
        start_name=(person or {}).get("name") or "",
        trigger_label=trigger.get("label") or "",
        pack=pack,
    )
    bid = None
    if pack == PACK_PROCUREMENT:
        from bid_advice import advise_bid

        bid = advise_bid(
            offer,
            title=trigger.get("label") or "",
            note=note,
        )
    card = {
        "inn": inn,
        "name": row.get("name") or "",
        "card_status": status,
        "status_label": company_status.status_label(status),
        "queue": company_status.queue_for_status(status),
        "demand_pack": pack,
        "demand_pack_label": PACK_LABELS.get(pack, PACK_LABELS[PACK_UNKNOWN]),
        "triggers": triggers,
        "primary_trigger": trigger,
        "note": note,
        "starting_person": person,
        "people_count": len(people),
        "pitch": pitch,
        "bid_advice": bid,
        "dadata_available": dadata_available(),
        "send_yourself": True,
        "message": (
            "Письмо отправляете сами. Личный контакт не собран."
            if person
            else "Директора в карточке нет — пишите на юрлицо по поводу закупки/найма. Письмо отправляете сами."
        ),
    }
    card["copy_text"] = build_copy_text(card)
    return card


def card_as_enrich_payload(card: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a demand card so older enrich UI can render without DaData."""
    person = card.get("starting_person") or {}
    lprs = []
    if person.get("name"):
        lprs.append({
            "power_type": "С кого начать",
            "role": person.get("role") or "руководитель",
            "name": person["name"],
            "source": person.get("source") or "",
            "custom_pitch": card.get("pitch"),
            "profile_url": "",
            "profile_resolved": False,
            "contacts": {},
        })
    return {
        "seller_product_profile": {},
        "dadata_legal_profile": {
            "inn": card.get("inn"),
            "name": card.get("name"),
            "ceo": person.get("name") or "",
            "status": "ACTIVE",
        },
        "lpr_matrix": {"total_lprs": len(lprs), "lprs": lprs},
        "hh_recruitment_profile": {"open_vacancies_count": 0, "vacancies": []},
        "sales_ai_insights": {
            "lead_score": 0,
            "insights": [card.get("note"), card.get("message")],
            "next_steps": ["Скопировать питч", "Отправить письмо самим"],
        },
        "company_card": {
            "status": card.get("card_status"),
            "status_label": card.get("status_label"),
            "queue": card.get("queue"),
            "triggers": card.get("triggers") or [],
        },
        "demand_card": card,
        "cache_hit": True,
        "memory_hit": True,
        "demo_mode": False,
        "sources_status_note": card.get("message"),
    }
