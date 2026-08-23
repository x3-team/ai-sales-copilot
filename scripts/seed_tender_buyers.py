"""
Seed buyer companies with EIS / zakupki.gov.ru demand triggers (signal, in_work).

Run: python3 scripts/seed_tender_buyers.py
Idempotent — safe on every startup.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Any, Dict, List

import company_status
from live_companies import is_integrator


def _eis_44(reg_number: str) -> str:
    return (
        "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html"
        f"?regNumber={reg_number}"
    )


def _eis_223(reg_number: str) -> str:
    return (
        "https://zakupki.gov.ru/epz/order/notice/notice223/view/common-info.html"
        f"?regNumber={reg_number}"
    )


def tender_buyer_records() -> List[Dict[str, Any]]:
    """Verified customer INNs + official EIS notice URLs. No invented people."""
    return [
        {
            "inn": "3903009923",
            "name": "ГП КО «Водоканал»",
            "title": "Поставка 1С:Предприятие 8.3 КОРП, извещение 32616034890",
            "tender_url": _eis_223("32616034890"),
            "note": "223-ФЗ, закупка ПО 1С у единственного поставщика",
        },
        {
            "inn": "7604031290",
            "name": "Ярославский областной суд",
            "title": "Шкафы металлические, извещение 0171100002226000023",
            "tender_url": _eis_44("0171100002226000023"),
            "note": "44-ФЗ, поставка мебели — пакет «закупка», не найм 1С",
        },
        {
            "inn": "3525432983",
            "name": "АО «Вологдагортеплосеть»",
            "title": "Спецодежда и СИЗ, извещение 32616165568",
            "tender_url": _eis_223("32616165568"),
            "note": "223-ФЗ, поставка спецодежды",
        },
        {
            "inn": "4705006785",
            "name": "ПАО «Завод «Буревестник»",
            "title": "Спецодежда и СИЗ, извещение 32616187423",
            "tender_url": _eis_223("32616187423"),
            "note": "223-ФЗ, поставка СИЗ",
        },
        {
            "inn": "7725010048",
            "name": "ФБУ «НТЦ ЯРБ»",
            "title": "Лицензия 1С:Предприятие 8.3 ПРОФ, извещение 32616184248",
            "tender_url": _eis_223("32616184248"),
            "note": "223-ФЗ, закупка лицензий 1С",
        },
    ]


def apply_tender_buyers_seed(memory_store: Any) -> Dict[str, Any]:
    memory_store.ensure_schema()
    results: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []

    for rec in tender_buyer_records():
        inn = rec["inn"]
        if is_integrator(inn):
            skipped.append({"inn": inn, "name": rec["name"], "reason": "integrator"})
            continue
        memory_store.upsert_from_tender(
            inn,
            rec["name"],
            rec["tender_url"],
            title=rec.get("title") or "",
            note=rec.get("note"),
        )
        row = memory_store.get_company(inn)
        people = memory_store.list_people(inn)
        status = row.get("card_status") or company_status.STATUS_SIGNAL
        if status == company_status.STATUS_REACHABLE:
            status = company_status.STATUS_SIGNAL
            memory_store.upsert_company(inn, name=rec["name"], card_status=status)
        results.append({
            "inn": inn,
            "name": rec["name"],
            "card_status": status,
            "queue": company_status.queue_for_status(status),
            "triggers": row.get("triggers") or [],
            "people_count": len(people),
        })
    return {"seeded": len(results), "skipped": skipped, "companies": results}


def main() -> None:
    import memory_store

    summary = apply_tender_buyers_seed(memory_store)
    print(f"Seeded {summary['seeded']} tender buyer companies")
    for c in summary["companies"]:
        print(f"  {c['inn']} {c['name']}: {c['card_status']}")


if __name__ == "__main__":
    main()
