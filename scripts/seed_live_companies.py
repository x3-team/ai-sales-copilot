"""
Seed verified live company facts into persistent memory (idempotent).

Run: python3 scripts/seed_live_companies.py
Uses DATABASE_URL (Postgres) or COPILOT_MEMORY_DB_PATH / data/copilot_memory.db.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Any, Dict, List

import company_status

# Verified facts only — no TenChat profile_url, Checko phones are company-level.


def live_company_records() -> List[Dict[str, Any]]:
    return [
        {
            "inn": "4217184336",
            "name": "ООО «СУПЕР СИЛА»",
            "triggers": [],
            "people": [
                {
                    "stakeholder": "ceo",
                    "fio": "Мальцев Максим Робертович",
                    "role": "директор",
                    "registry_url": "https://www.rusprofile.ru/id/11095765",
                    "sources": ["rusprofile", "checko"],
                    "phones": [
                        ("+7 800 301-10-32", "https://checko.ru/company/super-sila-1174205018239"),
                        ("+7 951 606-26-02", "https://checko.ru/company/super-sila-1174205018239"),
                    ],
                    "emails": [],
                }
            ],
        },
        {
            "inn": "771579995573",
            "name": "ИП Елисеев М.А.",
            "triggers": [],
            "people": [
                {
                    "stakeholder": "ceo",
                    "fio": "Елисеев Максим Анатольевич",
                    "role": "ИП · деятельность прекращена 27.01.2025",
                    "registry_url": "https://sbis.ru/contragents/771579995573",
                    "sources": ["sbis"],
                    "phones": [],
                    "emails": [],
                    "meta_extra": {"status_note": "деятельность прекращена 27.01.2025"},
                }
            ],
        },
        {
            "inn": "7801711200",
            "name": "АО «ИМ»",
            "triggers": ["HH: https://hh.ru/vacancy/135527588"],
            "people": [
                {
                    "stakeholder": "ceo",
                    "fio": "Аристов Алексей",
                    "role": "директор",
                    "registry_url": "https://www.rusprofile.ru/id/1227800047496",
                    "sources": ["rusprofile", "checko", "hh.ru"],
                    "phones": [
                        ("+7 917 295-90-29", "https://checko.ru/company/im-1227800047496"),
                    ],
                    "emails": [],
                    "meta_extra": {
                        "hh_employer": "https://hh.ru/employer/11435141",
                        "hh_vacancy": "https://hh.ru/vacancy/135527588",
                    },
                }
            ],
        },
        {
            "inn": "9709052492",
            "name": "ООО «МОЛОЧНЫЙ ДОМ»",
            "triggers": [],
            "brand_website": "http://kzorka.ddbq.ru/",
            "brand_website_note": "бренд Зорька — ИНН на странице не указан",
            "people": [
                {
                    "stakeholder": "ceo",
                    "fio": "Хажаев Дамир Гаяревич",
                    "role": "генеральный директор",
                    "registry_url": "https://sbis.ru/contragents/9709052492/400101001",
                    "sources": ["sbis", "checko"],
                    "phones": [
                        ("+7 484 413-40-56", "https://checko.ru/company/molochny-dom-1197746487641"),
                        ("+7 906 643-70-48", "https://checko.ru/company/molochny-dom-1197746487641"),
                        (
                            "8 800 550-76-69",
                            "http://kzorka.ddbq.ru/",
                        ),
                    ],
                    "phone_notes": {
                        "8 800 550-76-69": "бренд Зорька, ИНН на странице нет",
                    },
                    "emails": [],
                }
            ],
        },
        {
            "inn": "9103100540",
            "name": "ООО «РУСЬ»",
            "triggers": [],
            "people": [
                {
                    "stakeholder": "ceo",
                    "fio": "",
                    "role": "управляющая организация ООО «МРИЯ» (ИНН 9103007830) с 22.01.2025",
                    "registry_url": "https://www.rusprofile.ru/id/1229100013713",
                    "sources": ["rusprofile", "checko", "companian.ru"],
                    "phones": [],
                    "emails": [
                        (
                            "kanc@ooorus.net",
                            "https://checko.ru/company/rus-1229100013713",
                        ),
                        (
                            "kanc@ooorus.net",
                            "https://companian.ru/id/1229100013713-rus",
                        ),
                    ],
                    "meta_extra": {"management_inn": "9103007830", "management_since": "2025-01-22"},
                }
            ],
        },
    ]


def apply_live_seed(memory_store: Any) -> Dict[str, Any]:
    """Write verified records; recompute status from people (never reachable for Checko phones)."""
    memory_store.ensure_schema()
    results: List[Dict[str, Any]] = []

    for rec in live_company_records():
        inn = rec["inn"]
        sources = ["live_seed_verified"]
        if rec.get("brand_website"):
            sources.append(rec["brand_website"])

        memory_store.upsert_company(
            inn,
            name=rec["name"],
            website=rec.get("brand_website"),
            sources=sources,
            triggers=rec.get("triggers") or [],
        )

        for person in rec.get("people") or []:
            meta = {
                "registry_url": person.get("registry_url"),
                "profile_resolved": False,
                "seed": "live_verified",
            }
            if person.get("meta_extra"):
                meta.update(person["meta_extra"])
            if person.get("phone_notes"):
                meta["phone_notes"] = person["phone_notes"]

            pid = memory_store.upsert_person(
                company_inn=inn,
                stakeholder=person["stakeholder"],
                fio=person.get("fio") or "",
                role=person.get("role") or "",
                profile_url=None,
                platform=None,
                sources=person.get("sources") or ["live_seed"],
                meta=meta,
                reset_profile_url=True,
            )

            for phone, src in person.get("phones") or []:
                memory_store.upsert_contact(pid, "phone", phone, source_url=src)
            for item in person.get("emails") or []:
                if isinstance(item, tuple):
                    email, src = item
                else:
                    email, src = item, None
                memory_store.upsert_contact(pid, "email", email, source_url=src)

        people = memory_store.list_people(inn)
        computed = company_status.compute_card_status(
            people=people,
            triggers=rec.get("triggers") or [],
            ceo_name=next((p.get("fio") for p in rec.get("people") or [] if p.get("fio")), None),
        )
        if computed == company_status.STATUS_REACHABLE:
            computed = company_status.STATUS_NAMED if any(
                company_status.is_real_name(p.get("fio")) for p in rec.get("people") or []
            ) else company_status.STATUS_SIGNAL
        memory_store.upsert_company(
            inn,
            name=rec["name"],
            card_status=computed,
            triggers=rec.get("triggers") or [],
        )
        row = memory_store.get_company(inn)
        results.append(
            {
                "inn": inn,
                "name": rec["name"],
                "card_status": row.get("card_status"),
                "queue": company_status.queue_for_status(row.get("card_status") or computed),
                "people_count": len(people),
                "contacts_count": sum(len(p.get("contacts") or []) for p in people),
            }
        )

    return {"seeded": len(results), "companies": results}


def main() -> None:
    import memory_store

    summary = apply_live_seed(memory_store)
    print(f"Seeded {summary['seeded']} companies")
    for c in summary["companies"]:
        print(f"  {c['inn']} {c['name']}: {c['card_status']} ({c['queue']}) contacts={c['contacts_count']}")


if __name__ == "__main__":
    main()
