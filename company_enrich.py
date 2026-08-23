"""DaData CEO enrichment for demand cards — registry only, no invented contacts."""
from __future__ import annotations

from typing import Any, Dict, Optional

import company_status


def _has_real_ceo(people: list[Dict[str, Any]]) -> bool:
    for person in people:
        if (person.get("stakeholder") or "") != "ceo":
            continue
        if company_status.is_real_name(person.get("fio")):
            return True
    for person in people:
        if company_status.is_real_name(person.get("fio")):
            return True
    return False


def ensure_ceo_from_dadata(inn: str) -> Optional[Dict[str, str]]:
    """
    If memory has no real director, fetch CEO from DaData ЕГРЮЛ and store.
    Does not set profile_url or reachable — name only for «с кого начать».
    """
    import dadata_company
    import memory_store

    clean = "".join(ch for ch in (inn or "") if ch.isdigit())
    if not clean:
        return None
    row = memory_store.get_company(clean)
    if not row:
        return None
    people = memory_store.list_people(clean)
    if _has_real_ceo(people):
        return None
    if not dadata_company.is_configured():
        return None

    party = dadata_company.find_party_by_inn(clean)
    if not party.get("active") or party.get("reason") != "ok":
        return None
    ceo = (party.get("ceo") or "").strip()
    if not company_status.is_real_name(ceo):
        return None

    role = (party.get("ceo_post") or "руководитель").strip() or "руководитель"
    legal_name = (party.get("name") or row.get("name") or "").strip()
    if legal_name:
        memory_store.upsert_company(clean, name=legal_name)

    memory_store.upsert_person(
        company_inn=clean,
        stakeholder="ceo",
        fio=ceo,
        role=role,
        sources=["dadata", "egrul"],
        meta={"enrich_source": "dadata_findById"},
    )
    memory_store.refresh_company_status(clean, ceo_name=ceo)
    return {
        "name": ceo,
        "role": role,
        "source": "ЕГРЮЛ / DaData",
    }
