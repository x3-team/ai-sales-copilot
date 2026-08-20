"""
Seed 1C buyer companies with Habr Career demand triggers (signal, in_work).

Run: python3 scripts/seed_habr_buyers.py
Idempotent — safe on every startup.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Any, Dict, List

import company_status
from live_companies import is_integrator


def habr_buyer_records() -> List[Dict[str, Any]]:
    """Verified buyer INNs + Habr vacancy URLs. Integrators excluded."""
    return [
        {
            "inn": "7706729736",
            "name": "АО «Гринатом»",
            "vacancy_url": "https://career.habr.com/vacancies/1000167774",
            "note": "В тексте вакансии также АО ТВЭЛ-СТРОЙ",
        },
        {
            "inn": "7702235133",
            "name": "Банк России",
            "vacancy_url": "https://career.habr.com/vacancies/1000162592",
        },
        {
            "inn": "7812014560",
            "name": "ПАО «МегаФон»",
            "vacancy_url": "https://career.habr.com/vacancies/1000162686",
        },
        {
            "inn": "7705986635",
            "name": "АО «УК Аэропорты Регионов»",
            "vacancy_url": "https://career.habr.com/vacancies/1000158493",
        },
        {
            "inn": "6165115558",
            "name": "АО «Автоформула»",
            "vacancy_url": "https://career.habr.com/vacancies/1000166450",
        },
        {
            "inn": "7708400979",
            "name": "ООО «МКК А ДЕНЬГИ»",
            "vacancy_url": "https://career.habr.com/vacancies/1000168274",
        },
        {
            "inn": "6670381056",
            "name": "ООО «Екатеринбург Яблоко»",
            "vacancy_url": "https://career.habr.com/vacancies/1000166904",
            "note": "розничный оператор витрины, IT-юрлицо группы не подтверждено",
        },
        {
            "inn": "7736279160",
            "name": "ООО «Облачные технологии»",
            "vacancy_url": "https://career.habr.com/vacancies/1000167159",
            "note": "Cloud.ru",
        },
        {
            "inn": "7707067683",
            "name": "ПАО «СК Росгосстрах»",
            "vacancy_url": "https://career.habr.com/vacancies/1000167629",
        },
        {
            "inn": "9710089137",
            "name": "ООО «ГРИ»",
            "vacancy_url": "https://career.habr.com/vacancies/1000167917",
        },
        {
            "inn": "5401305707",
            "name": "ООО «НЛ Континент»",
            "vacancy_url": "https://career.habr.com/vacancies/1000167989",
        },
        {
            "inn": "4217204769",
            "name": "АО «СГМК»",
            "vacancy_url": "https://career.habr.com/vacancies/1000168025",
        },
    ]


def apply_habr_buyers_seed(memory_store: Any) -> Dict[str, Any]:
    """Write Habr trigger-only buyer records; no contacts, no profile_url."""
    memory_store.ensure_schema()
    results: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []

    for rec in habr_buyer_records():
        inn = rec["inn"]
        if is_integrator(inn):
            skipped.append({"inn": inn, "name": rec["name"], "reason": "integrator"})
            continue

        memory_store.upsert_from_habr_vacancy(
            inn,
            rec["name"],
            rec["vacancy_url"],
            note=rec.get("note"),
        )
        row = memory_store.get_company(inn)
        people = memory_store.list_people(inn)
        status = row.get("card_status") or company_status.STATUS_SIGNAL
        if status == company_status.STATUS_REACHABLE:
            status = company_status.STATUS_NAMED if any(
                company_status.is_real_name(p.get("fio")) for p in people
            ) else company_status.STATUS_SIGNAL
            memory_store.upsert_company(inn, name=rec["name"], card_status=status)

        results.append(
            {
                "inn": inn,
                "name": rec["name"],
                "card_status": status,
                "queue": company_status.queue_for_status(status),
                "triggers": row.get("triggers") or [],
                "people_count": len(people),
                "note": rec.get("note"),
            }
        )

    return {"seeded": len(results), "skipped": skipped, "companies": results}


def main() -> None:
    import memory_store

    summary = apply_habr_buyers_seed(memory_store)
    print(f"Seeded {summary['seeded']} Habr buyer companies")
    for c in summary["companies"]:
        print(f"  {c['inn']} {c['name']}: {c['card_status']} ({c['queue']})")
    if summary["skipped"]:
        print(f"Skipped integrators: {len(summary['skipped'])}")


if __name__ == "__main__":
    main()
