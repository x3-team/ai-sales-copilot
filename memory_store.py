"""
Persistent memory for companies, people, contacts, and power maps.

Primary backend: PostgreSQL via DATABASE_URL (Render internal URL in production).
Fallback: SQLite at COPILOT_MEMORY_DB_PATH or data/copilot_memory.db for local tests.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple

import company_status
from storage_paths import resolve_sqlite_path

SLOT_ORDER = ("ceo", "lpr", "lvr", "ldpr")
SLOT_ALIASES = {"hr": "ldpr", "ldpr": "ldpr"}
PLACEHOLDER_NAMES = frozenset(
    {"", "—", "-", "Контакт не найден", "Руководитель", "Руководитель (ЕГРЮЛ)"}
)
EMPTY_CONTACT = frozenset({"", "—", "-", None})

_RENDER_DISK_DIR = "/var/data"
_DEFAULT_DIR = os.path.join(os.path.dirname(__file__), "data")

_migrations_applied = False


def _now_ts() -> float:
    return time.time()


def _normalize_stakeholder(raw: str) -> str:
    key = (raw or "lpr").lower().strip()
    return SLOT_ALIASES.get(key, key if key in SLOT_ORDER else "lpr")


def _is_real_name(name: Optional[str]) -> bool:
    return bool(name and name.strip() not in PLACEHOLDER_NAMES)


def _is_real_contact(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in EMPTY_CONTACT
    return bool(value)


def _null_if_empty(value: Any) -> Optional[str]:
    if not _is_real_contact(value):
        return None
    return str(value).strip()


def db_backend() -> str:
    if os.environ.get("DATABASE_URL"):
        return "postgres"
    return "sqlite"


def sqlite_path() -> str:
    return resolve_sqlite_path("COPILOT_MEMORY_DB_PATH", "copilot_memory.db")


def is_configured() -> bool:
    return bool(os.environ.get("DATABASE_URL")) or os.path.isfile(sqlite_path())


def store_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {"backend": db_backend(), "configured": is_configured()}
    if db_backend() == "postgres":
        info["database_url_set"] = True
    else:
        info["path"] = sqlite_path()
    return info


def _migration_sql_path() -> str:
    base = os.path.join(os.path.dirname(__file__), "migrations")
    if db_backend() == "postgres":
        return os.path.join(base, "001_initial.sql")
    return os.path.join(base, "001_initial_sqlite.sql")


def _ensure_sqlite_status_columns(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(companies)")}
    if "card_status" not in cols:
        conn.execute(
            "ALTER TABLE companies ADD COLUMN card_status TEXT NOT NULL DEFAULT 'signal'"
        )
    if "triggers" not in cols:
        conn.execute(
            "ALTER TABLE companies ADD COLUMN triggers TEXT NOT NULL DEFAULT '[]'"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_companies_card_status ON companies(card_status)"
    )


def ensure_schema() -> None:
    global _migrations_applied
    if _migrations_applied:
        return
    base = os.path.join(os.path.dirname(__file__), "migrations")
    if db_backend() == "postgres":
        files = ["001_initial.sql", "003_company_status.sql"]
        for fname in files:
            path = os.path.join(base, fname)
            with open(path, "r", encoding="utf-8") as fh:
                sql = fh.read()
            import psycopg2

            conn = psycopg2.connect(os.environ["DATABASE_URL"])
            try:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(sql)
            finally:
                conn.close()
    else:
        path = os.path.join(base, "001_initial_sqlite.sql")
        with open(path, "r", encoding="utf-8") as fh:
            sql = fh.read()
        db = sqlite_path()
        os.makedirs(os.path.dirname(db) or ".", exist_ok=True)
        conn = sqlite3.connect(db)
        try:
            conn.executescript(sql)
            _ensure_sqlite_status_columns(conn)
            conn.commit()
        finally:
            conn.close()
    _migrations_applied = True


@contextmanager
def _connection() -> Iterator[Any]:
    ensure_schema()
    if db_backend() == "postgres":
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(sqlite_path())
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_load(raw: Any, default: Any = None) -> Any:
    if raw is None or raw == "":
        return default if default is not None else {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default if default is not None else {}


def _pg_placeholder(n: int = 1) -> str:
    return "%s" if db_backend() == "postgres" else "?"


def upsert_company(
    inn: str,
    *,
    name: str = "",
    website: Optional[str] = None,
    sources: Optional[List[str]] = None,
    card_status: Optional[str] = None,
    triggers: Optional[List[str]] = None,
) -> None:
    inn = inn.strip()
    if not inn:
        return
    now = _now_ts()
    src = sources or []
    existing = get_company(inn)
    prev_status = (existing or {}).get("card_status") or company_status.STATUS_SIGNAL
    if card_status is not None:
        final_status = company_status.merge_status(prev_status, card_status)
    else:
        final_status = prev_status
    merged_triggers = list((existing or {}).get("triggers") or [])
    for t in triggers or []:
        if t and t not in merged_triggers:
            merged_triggers.append(t)
    with _connection() as conn:
        if db_backend() == "postgres":
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO companies (inn, name, website, sources, card_status, triggers, created_at, updated_at)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s::jsonb, NOW(), NOW())
                ON CONFLICT (inn) DO UPDATE SET
                    name = COALESCE(NULLIF(EXCLUDED.name, ''), companies.name),
                    website = COALESCE(EXCLUDED.website, companies.website),
                    sources = (
                        SELECT COALESCE(jsonb_agg(DISTINCT elem), '[]'::jsonb)
                        FROM (
                            SELECT jsonb_array_elements_text(companies.sources) AS elem
                            UNION
                            SELECT jsonb_array_elements_text(EXCLUDED.sources)
                        ) s
                    ),
                    card_status = EXCLUDED.card_status,
                    triggers = EXCLUDED.triggers,
                    updated_at = NOW()
                """,
                (
                    inn,
                    name or "",
                    website,
                    _json_dump(src),
                    final_status,
                    _json_dump(merged_triggers),
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO companies (inn, name, website, sources, card_status, triggers, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (inn) DO UPDATE SET
                    name = COALESCE(NULLIF(excluded.name, ''), companies.name),
                    website = COALESCE(excluded.website, companies.website),
                    sources = excluded.sources,
                    card_status = excluded.card_status,
                    triggers = excluded.triggers,
                    updated_at = excluded.updated_at
                """,
                (
                    inn,
                    name or "",
                    website,
                    _json_dump(src),
                    final_status,
                    _json_dump(merged_triggers),
                    now,
                    now,
                ),
            )


def upsert_person(
    *,
    company_inn: str,
    stakeholder: str,
    fio: str = "",
    role: str = "",
    profile_url: Optional[str] = None,
    platform: Optional[str] = None,
    sources: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
    reset_profile_url: bool = False,
) -> int:
    slot = _normalize_stakeholder(stakeholder)
    now = _now_ts()
    src = sources or []
    meta_obj = meta or {}
    profile_sql_pg = (
        "profile_url = EXCLUDED.profile_url"
        if reset_profile_url
        else "profile_url = COALESCE(NULLIF(EXCLUDED.profile_url, ''), people.profile_url)"
    )
    meta_sql_pg = (
        "meta = EXCLUDED.meta"
        if reset_profile_url
        else "meta = people.meta || EXCLUDED.meta"
    )
    profile_sql_sq = (
        "profile_url = excluded.profile_url"
        if reset_profile_url
        else "profile_url = COALESCE(NULLIF(excluded.profile_url, ''), people.profile_url)"
    )
    meta_sql_sq = (
        "meta = excluded.meta"
        if reset_profile_url
        else "meta = excluded.meta"
    )
    if not reset_profile_url:
        meta_sql_sq = "meta = people.meta || excluded.meta"
    with _connection() as conn:
        if db_backend() == "postgres":
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO people (
                    fio, role, company_inn, stakeholder, profile_url, platform, sources, meta,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, NOW(), NOW())
                ON CONFLICT (company_inn, stakeholder) DO UPDATE SET
                    fio = COALESCE(NULLIF(EXCLUDED.fio, ''), people.fio),
                    role = COALESCE(NULLIF(EXCLUDED.role, ''), people.role),
                    {profile_sql_pg},
                    platform = COALESCE(NULLIF(EXCLUDED.platform, ''), people.platform),
                    sources = (
                        SELECT COALESCE(jsonb_agg(DISTINCT elem), '[]'::jsonb)
                        FROM (
                            SELECT jsonb_array_elements_text(people.sources) AS elem
                            UNION
                            SELECT jsonb_array_elements_text(EXCLUDED.sources)
                        ) s
                    ),
                    {meta_sql_pg},
                    updated_at = NOW()
                RETURNING id
                """,
                (
                    fio or "",
                    role or "",
                    company_inn,
                    slot,
                    profile_url or None,
                    platform or None,
                    _json_dump(src),
                    _json_dump(meta_obj),
                ),
            )
            row = cur.fetchone()
            person_id = int(row[0])
        else:
            conn.execute(
                f"""
                INSERT INTO people (
                    fio, role, company_inn, stakeholder, profile_url, platform, sources, meta,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (company_inn, stakeholder) DO UPDATE SET
                    fio = COALESCE(NULLIF(excluded.fio, ''), people.fio),
                    role = COALESCE(NULLIF(excluded.role, ''), people.role),
                    {profile_sql_sq},
                    platform = COALESCE(NULLIF(excluded.platform, ''), people.platform),
                    sources = excluded.sources,
                    {meta_sql_sq},
                    updated_at = excluded.updated_at
                """,
                (
                    fio or "",
                    role or "",
                    company_inn,
                    slot,
                    profile_url,
                    platform,
                    _json_dump(src),
                    _json_dump(meta_obj),
                    now,
                    now,
                ),
            )
            cur = conn.execute(
                "SELECT id FROM people WHERE company_inn = ? AND stakeholder = ?",
                (company_inn, slot),
            )
            person_id = int(cur.fetchone()[0])
        _update_power_map_slot(conn, company_inn, slot, person_id)
        return person_id


def _update_power_map_slot(conn: Any, company_inn: str, slot: str, person_id: int) -> None:
    col = f"{slot}_person_id"
    now = _now_ts()
    if db_backend() == "postgres":
        cur = conn.cursor()
        cur.execute(
            f"""
            INSERT INTO power_maps (inn, {col}, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (inn) DO UPDATE SET
                {col} = EXCLUDED.{col},
                updated_at = NOW()
            """,
            (company_inn, person_id),
        )
    else:
        conn.execute(
            f"""
            INSERT INTO power_maps (inn, {col}, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (inn) DO UPDATE SET
                {col} = excluded.{col},
                updated_at = excluded.updated_at
            """,
            (company_inn, person_id, now),
        )


def upsert_contact(
    person_id: int,
    contact_type: str,
    value: str,
    *,
    source_url: Optional[str] = None,
    found_at: Optional[float] = None,
) -> None:
    ctype = contact_type.lower().strip()
    if ctype not in ("email", "phone", "telegram"):
        return
    val = _null_if_empty(value)
    if not val:
        return
    ts = found_at or _now_ts()
    with _connection() as conn:
        if db_backend() == "postgres":
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO contacts (person_id, type, value, source_url, found_at)
                VALUES (%s, %s, %s, %s, to_timestamp(%s))
                ON CONFLICT (person_id, type, value) DO NOTHING
                """,
                (person_id, ctype, val, source_url, ts),
            )
        else:
            conn.execute(
                """
                INSERT OR IGNORE INTO contacts (person_id, type, value, source_url, found_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (person_id, ctype, val, source_url, ts),
            )


def upsert_from_inbound_candidate(
    company_inn: str,
    company_name: str,
    candidate: Dict[str, Any],
) -> Optional[int]:
    """Persist one normalized inbound webhook candidate."""
    if not company_inn:
        return None
    upsert_company(
        company_inn,
        name=company_name or candidate.get("company") or "",
        sources=[candidate.get("source") or "lpr_webhook"],
    )
    hint = _normalize_stakeholder(candidate.get("stakeholder_hint") or "lpr")
    person_id = upsert_person(
        company_inn=company_inn,
        stakeholder=hint,
        fio=(candidate.get("name") or "").strip(),
        role=(candidate.get("role") or "").strip(),
        profile_url=candidate.get("profile_url"),
        platform=candidate.get("profile_platform") or candidate.get("platform"),
        sources=[candidate.get("source") or "lpr_webhook"],
        meta={
            "source_type": candidate.get("source_type"),
            "confidence_base": candidate.get("confidence_base"),
            "profile_resolved": candidate.get("profile_resolved"),
        },
    )
    source_url = candidate.get("profile_url")
    for ctype in ("email", "phone", "telegram"):
        upsert_contact(person_id, ctype, candidate.get(ctype) or "", source_url=source_url)
    return person_id


def upsert_from_inbound(
    company_inn: str,
    company_name: str,
    candidates: List[Dict[str, Any]],
) -> int:
    count = 0
    for cand in candidates:
        if upsert_from_inbound_candidate(company_inn, company_name, cand) is not None:
            count += 1
    refresh_company_status(company_inn)
    return count


def upsert_from_hh_vacancy(
    company_inn: str,
    company_name: str,
    vacancy: Dict[str, Any],
) -> Optional[int]:
    """Persist open HH vacancy contact fields; empty slots stay empty."""
    if not company_inn:
        return None
    url = (vacancy.get("url") or "").strip()
    if not url:
        vid = str(vacancy.get("id") or vacancy.get("vacancy_id") or "").replace("hh-", "")
        if vid:
            url = f"https://hh.ru/vacancy/{vid}"

    contact_name = (
        vacancy.get("contact_name")
        or vacancy.get("hr_name")
        or ""
    ).strip()
    contact_email = (
        vacancy.get("contact_email")
        or vacancy.get("hr_email")
        or ""
    ).strip()
    contact_phone = (
        vacancy.get("contact_phone")
        or vacancy.get("hr_phone")
        or ""
    ).strip()
    title = (vacancy.get("title") or "Вакансия").strip()
    trigger = f"HH: {url}" if url else f"HH: {title}"

    upsert_company(
        company_inn,
        name=company_name or "",
        sources=["hh.ru"],
        triggers=[trigger],
    )

    person_id: Optional[int] = None
    if contact_name or contact_email or contact_phone:
        person_id = upsert_person(
            company_inn=company_inn,
            stakeholder="ldpr",
            fio=contact_name,
            role=f"HR / Контактное лицо (вакансия «{title[:60]}»)",
            profile_url=None,
            platform="hh",
            sources=["hh.ru"],
            meta={
                "source_type": "hh_vacancy",
                "vacancy_url": url,
                "contacts_hidden": bool(vacancy.get("contacts_hidden")),
            },
        )
        if contact_email:
            upsert_contact(person_id, "email", contact_email, source_url=url or None)
        if contact_phone:
            upsert_contact(person_id, "phone", contact_phone, source_url=url or None)

    refresh_company_status(company_inn, ceo_name=None)
    return person_id


def refresh_company_status(inn: str, *, ceo_name: Optional[str] = None) -> Dict[str, Any]:
    row = get_company(inn) or {}
    people = list_people(inn)
    computed = company_status.compute_card_status(
        people=people,
        ceo_name=ceo_name,
        triggers=row.get("triggers") or [],
    )
    upsert_company(inn, name=row.get("name") or "", card_status=computed)
    return company_status.card_status_payload(computed, triggers=row.get("triggers") or [])


def get_company(inn: str) -> Optional[Dict[str, Any]]:
    with _connection() as conn:
        if db_backend() == "postgres":
            import psycopg2.extras

            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM companies WHERE inn = %s", (inn,))
            row = cur.fetchone()
        else:
            cur = conn.execute("SELECT * FROM companies WHERE inn = ?", (inn,))
            row = cur.fetchone()
        if not row:
            return None
        data = dict(row)
        data["sources"] = _json_load(data.get("sources"), [])
        data["enrich_payload"] = _json_load(data.get("enrich_payload"))
        data["triggers"] = _json_load(data.get("triggers"), [])
        data["card_status"] = data.get("card_status") or company_status.STATUS_SIGNAL
        return data


def sync_status_from_payload(inn: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    card = company_status.compute_from_enrich_payload(payload)
    upsert_company(
        inn,
        name=(payload.get("dadata_legal_profile") or {}).get("name") or "",
        website=(payload.get("dadata_legal_profile") or {}).get("website"),
        card_status=card["status"],
        triggers=card.get("triggers"),
    )
    return card


def list_companies(
    *,
    queue: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    include_inactive: bool = False,
) -> List[Dict[str, Any]]:
    from live_companies import INACTIVE_COMPANY_INNS, is_active_company
    with _connection() as conn:
        if db_backend() == "postgres":
            import psycopg2.extras

            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = "SELECT inn, name, website, card_status, triggers, updated_at FROM companies"
            clauses: List[str] = []
            params: List[Any] = []
            if status:
                clauses.append("card_status = %s")
                params.append(status)
            elif queue == company_status.QUEUE_REACHABLE:
                clauses.append("card_status = %s")
                params.append(company_status.STATUS_REACHABLE)
            elif queue == company_status.QUEUE_IN_WORK:
                clauses.append("card_status IN (%s, %s)")
                params.extend([company_status.STATUS_SIGNAL, company_status.STATUS_NAMED])
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY updated_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        else:
            sql = "SELECT inn, name, website, card_status, triggers, updated_at FROM companies"
            clauses: List[str] = []
            params: List[Any] = []
            if status:
                clauses.append("card_status = ?")
                params.append(status)
            elif queue == company_status.QUEUE_REACHABLE:
                clauses.append("card_status = ?")
                params.append(company_status.STATUS_REACHABLE)
            elif queue == company_status.QUEUE_IN_WORK:
                clauses.append("card_status IN (?, ?)")
                params.extend([company_status.STATUS_SIGNAL, company_status.STATUS_NAMED])
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            cur = conn.execute(sql, tuple(params))
            rows = cur.fetchall()
    out = []
    for row in rows:
        item = dict(row)
        inn = item.get("inn") or ""
        if not include_inactive and not is_active_company(inn):
            continue
        st = item.get("card_status") or company_status.STATUS_SIGNAL
        item["triggers"] = _json_load(item.get("triggers"), [])
        item["status_label"] = company_status.status_label(st)
        item["queue"] = company_status.queue_for_status(st)
        item["active"] = inn not in INACTIVE_COMPANY_INNS
        out.append(item)
    return out


def list_people(company_inn: str) -> List[Dict[str, Any]]:
    with _connection() as conn:
        if db_backend() == "postgres":
            import psycopg2.extras

            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT * FROM people WHERE company_inn = %s ORDER BY id",
                (company_inn,),
            )
            rows = cur.fetchall()
        else:
            cur = conn.execute(
                "SELECT * FROM people WHERE company_inn = ? ORDER BY id",
                (company_inn,),
            )
            rows = cur.fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["sources"] = _json_load(item.get("sources"), [])
            item["meta"] = _json_load(item.get("meta"), {})
            item["contacts"] = list_contacts(int(item["id"]))
            out.append(item)
        return out


def list_contacts(person_id: int) -> List[Dict[str, Any]]:
    with _connection() as conn:
        if db_backend() == "postgres":
            import psycopg2.extras

            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                "SELECT id, person_id, type, value, source_url, found_at FROM contacts WHERE person_id = %s ORDER BY type, id",
                (person_id,),
            )
            rows = cur.fetchall()
        else:
            cur = conn.execute(
                "SELECT id, person_id, type, value, source_url, found_at FROM contacts WHERE person_id = ? ORDER BY type, id",
                (person_id,),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_power_map(inn: str) -> Optional[Dict[str, Any]]:
    with _connection() as conn:
        if db_backend() == "postgres":
            import psycopg2.extras

            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM power_maps WHERE inn = %s", (inn,))
            row = cur.fetchone()
        else:
            cur = conn.execute("SELECT * FROM power_maps WHERE inn = ?", (inn,))
            row = cur.fetchone()
        if not row:
            return None
        pm = dict(row)
        for slot in SLOT_ORDER:
            pid = pm.get(f"{slot}_person_id")
            pm[slot] = _person_brief(conn, pid) if pid else None
        return pm


def _person_brief(conn: Any, person_id: int) -> Optional[Dict[str, Any]]:
    if not person_id:
        return None
    if db_backend() == "postgres":
        import psycopg2.extras

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM people WHERE id = %s", (person_id,))
        row = cur.fetchone()
    else:
        cur = conn.execute("SELECT * FROM people WHERE id = ?", (person_id,))
        row = cur.fetchone()
    if not row:
        return None
    item = dict(row)
    item["contacts"] = list_contacts(int(item["id"]))
    return item


def save_enrich_payload(inn: str, payload: Dict[str, Any]) -> None:
    company = payload.get("dadata_legal_profile") or {}
    upsert_company(
        inn,
        name=company.get("name") or company.get("full_name") or "",
        website=company.get("website"),
        sources=["enrich-company"],
    )
    lprs = (payload.get("lpr_matrix") or {}).get("lprs") or []
    slot_keys_ui = ("ceo", "lpr", "lvr", "hr")
    for idx, entry in enumerate(lprs):
        slot_ui = slot_keys_ui[idx] if idx < len(slot_keys_ui) else "lpr"
        slot = _normalize_stakeholder(slot_ui)
        if not _is_real_name(entry.get("name")) and not entry.get("profile_url"):
            continue
        contacts = entry.get("contacts") or {}
        person_id = upsert_person(
            company_inn=inn,
            stakeholder=slot,
            fio=entry.get("name") or "",
            role=entry.get("role") or "",
            profile_url=entry.get("profile_url"),
            platform=_platform_from_entry(entry),
            sources=[entry.get("source") or entry.get("identity_source") or "enrich"],
            meta={
                "profile_resolved": entry.get("profile_resolved"),
                "profile_confidence": entry.get("profile_confidence"),
                "power_type": entry.get("power_type"),
            },
        )
        source_url = entry.get("profile_url")
        for ctype, key in (("email", "email"), ("phone", "phone"), ("telegram", "telegram")):
            upsert_contact(person_id, ctype, contacts.get(key) or "", source_url=source_url)

    with _connection() as conn:
        if db_backend() == "postgres":
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE companies SET enrich_payload = %s::jsonb, updated_at = NOW()
                WHERE inn = %s
                """,
                (_json_dump(payload), inn),
            )
        else:
            conn.execute(
                "UPDATE companies SET enrich_payload = ?, updated_at = ? WHERE inn = ?",
                (_json_dump(payload), _now_ts(), inn),
            )
    sync_status_from_payload(inn, payload)


def get_enrich_payload(inn: str) -> Optional[Dict[str, Any]]:
    row = get_company(inn)
    if not row:
        return None
    payload = row.get("enrich_payload")
    if isinstance(payload, dict) and payload:
        out = dict(payload)
        out["memory_hit"] = True
        out["cache_hit"] = True
        row = get_company(inn)
        if row:
            out["company_card"] = company_status.card_status_payload(
                row.get("card_status") or company_status.STATUS_SIGNAL,
                triggers=row.get("triggers") or [],
            )
        return out
    rebuilt = rebuild_enrich_from_memory(inn)
    if rebuilt:
        rebuilt["memory_hit"] = True
        rebuilt["cache_hit"] = True
    return rebuilt


def rebuild_enrich_from_memory(inn: str) -> Optional[Dict[str, Any]]:
    people = list_people(inn)
    if not people:
        return None
    company = get_company(inn) or {}
    lprs = [_person_to_lpr_entry(p) for p in sorted(people, key=_slot_sort_key)]
    if not lprs:
        return None
    return {
        "dadata_legal_profile": {
            "inn": inn,
            "name": company.get("name") or "",
            "website": company.get("website"),
        },
        "lpr_matrix": {"total_lprs": len(lprs), "lprs": lprs},
        "demo_mode": False,
    }


def _slot_sort_key(person: Dict[str, Any]) -> int:
    slot = person.get("stakeholder") or "lpr"
    try:
        return SLOT_ORDER.index(slot)
    except ValueError:
        return 99


def _platform_from_entry(entry: Dict[str, Any]) -> Optional[str]:
    platform = (entry.get("profile_platform") or "").lower()
    if platform:
        return platform.split(".")[0] if "." in platform else platform
    url = entry.get("profile_url") or ""
    for name in ("tenchat", "setka", "linkedin", "hh"):
        if name in url.lower():
            return name
    return None


def _person_to_lpr_entry(person: Dict[str, Any]) -> Dict[str, Any]:
    slot = person.get("stakeholder") or "lpr"
    meta = person.get("meta") or {}
    contacts_raw = person.get("contacts") or []
    contact_map = {c["type"]: c["value"] for c in contacts_raw if c.get("value")}
    platform = person.get("platform") or ""
    platform_label = {
        "tenchat": "TenChat",
        "linkedin": "LinkedIn",
        "setka": "Setka",
        "hh": "HH.ru",
        "site": "Site",
    }.get(platform.lower(), platform or "")
    profile_url = person.get("profile_url") or ""
    resolved = bool(meta.get("profile_resolved") or profile_url)
    email = contact_map.get("email")
    phone = contact_map.get("phone")
    telegram = contact_map.get("telegram")
    power_types = {
        "ceo": "Собственник / CEO",
        "lpr": "ЛПР (Бизнес-заказчик)",
        "lvr": "ЛВР (Технический эксперт)",
        "ldpr": "ЛДПР / Инициатор",
    }
    return {
        "power_type": meta.get("power_type") or power_types.get(slot, power_types["lpr"]),
        "role": person.get("role") or "",
        "name": person.get("fio") or "",
        "source": (person.get("sources") or ["memory"])[0],
        "source_type": meta.get("source_type") or "memory",
        "identity_source": (person.get("sources") or ["memory"])[0],
        "profile_url": profile_url,
        "profile_resolved": resolved,
        "profile_platform": platform_label,
        "profile_confidence": meta.get("profile_confidence") or 0,
        "profile_search_engine": meta.get("profile_search_engine") or "memory",
        "dork_query": "",
        "pitch_focus": "",
        "contacts": {
            "phone": phone,
            "phone_type": "memory" if phone else None,
            "email": email,
            "email_status": "memory" if email else None,
            "email_badge": "Memory" if email else None,
            "is_verified": bool(email),
            "telegram": telegram,
            "search_link_tenchat": profile_url if "tenchat" in profile_url else "",
            "search_link_linkedin": profile_url if "linkedin" in profile_url else "",
            "profile_badge": "Memory" if resolved else "Smart Search",
            "profile_resolved": resolved,
        },
    }


def _entry_is_complete(entry: Dict[str, Any]) -> bool:
    if not _is_real_name(entry.get("name")):
        return False
    if entry.get("profile_resolved") and entry.get("profile_url"):
        return True
    contacts = entry.get("contacts") or {}
    return any(_is_real_contact(contacts.get(k)) for k in ("email", "phone", "telegram"))


def merge_lpr_lists(stored: List[Dict[str, Any]], fresh: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prefer stored data for filled fields; fill gaps from fresh search."""
    merged: List[Dict[str, Any]] = []
    for idx, fresh_entry in enumerate(fresh):
        stored_entry = stored[idx] if idx < len(stored) else None
        if stored_entry and _entry_is_complete(stored_entry):
            merged.append(stored_entry)
            continue
        if not stored_entry:
            merged.append(fresh_entry)
            continue
        combined = dict(fresh_entry)
        for key in ("name", "role", "source", "source_type", "identity_source", "profile_url",
                    "profile_resolved", "profile_platform", "profile_confidence", "power_type"):
            stored_val = stored_entry.get(key)
            fresh_val = fresh_entry.get(key)
            if key == "name":
                combined[key] = stored_val if _is_real_name(stored_val) else fresh_val
            elif stored_val not in (None, "", "—", "-"):
                combined[key] = stored_val
            elif fresh_val not in (None, "", "—", "-"):
                combined[key] = fresh_val
        sc = stored_entry.get("contacts") or {}
        fc = fresh_entry.get("contacts") or {}
        cc = dict(fc)
        for ck in ("phone", "email", "telegram", "phone_type", "email_status", "email_badge"):
            if _is_real_contact(sc.get(ck)):
                cc[ck] = sc[ck]
            elif _is_real_contact(fc.get(ck)):
                cc[ck] = fc[ck]
            else:
                cc[ck] = None
        cc["is_verified"] = bool(_is_real_contact(cc.get("email")))
        cc["profile_resolved"] = combined.get("profile_resolved") or sc.get("profile_resolved")
        combined["contacts"] = cc
        merged.append(combined)
    return merged


def lprs_by_slot(lprs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    slot_keys_ui = ("ceo", "lpr", "lvr", "hr")
    out: Dict[str, Dict[str, Any]] = {}
    for idx, slot in enumerate(slot_keys_ui):
        if idx < len(lprs) and lprs[idx]:
            out[slot] = lprs[idx]
    return out


def slots_needing_search(stored_lprs: List[Dict[str, Any]]) -> List[str]:
    """Return stakeholder slots that still need external search."""
    slot_keys_ui = ("ceo", "lpr", "lvr", "hr")
    missing = []
    for idx, slot_ui in enumerate(slot_keys_ui):
        entry = stored_lprs[idx] if idx < len(stored_lprs) else None
        if not entry or not _entry_is_complete(entry):
            missing.append(slot_ui)
    return missing
