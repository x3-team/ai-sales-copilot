"""Persistent storage for LPR webhook jobs (Postgres when DATABASE_URL set, else SQLite)."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

_DEFAULT_DIR = os.path.join(os.path.dirname(__file__), "data")
_RENDER_DISK_DIR = "/var/data"
_LOCK = threading.Lock()
_schema_ready = False


def db_backend() -> str:
    return "postgres" if os.environ.get("DATABASE_URL") else "sqlite"


def _resolve_sqlite_path() -> str:
    explicit = os.environ.get("LPR_JOBS_DB_PATH", "").strip()
    if explicit:
        return explicit
    if os.path.isdir(_RENDER_DISK_DIR) and os.access(_RENDER_DISK_DIR, os.W_OK):
        return os.path.join(_RENDER_DISK_DIR, "lpr_jobs.db")
    os.makedirs(_DEFAULT_DIR, exist_ok=True)
    return os.path.join(_DEFAULT_DIR, "lpr_jobs.db")


DB_PATH = _resolve_sqlite_path()


def db_path() -> str:
    return DB_PATH


def store_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {"backend": db_backend(), "configured": True}
    if db_backend() == "postgres":
        info["database_url_set"] = True
    else:
        info["path"] = DB_PATH
    return info


def _migration_sql_path() -> str:
    base = os.path.join(os.path.dirname(__file__), "migrations")
    if db_backend() == "postgres":
        return os.path.join(base, "002_lpr_jobs.sql")
    return os.path.join(base, "002_lpr_jobs_sqlite.sql")


def init_db() -> None:
    global _schema_ready
    if _schema_ready:
        return
    path = _migration_sql_path()
    with open(path, "r", encoding="utf-8") as fh:
        sql = fh.read()
    if db_backend() == "postgres":
        import psycopg2

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql)
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        try:
            conn.executescript(sql)
            conn.commit()
        finally:
            conn.close()
    _schema_ready = True


@contextmanager
def _connection() -> Iterator[Any]:
    init_db()
    if db_backend() == "postgres":
        import psycopg2

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
        directory = os.path.dirname(DB_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
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


def _json_load(val: Any, default: Any) -> Any:
    if val is None or val == "":
        return default
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except (TypeError, json.JSONDecodeError):
        return default


def _to_epoch(val: Any) -> float:
    if val is None:
        return time.time()
    if isinstance(val, (int, float)):
        return float(val)
    if hasattr(val, "timestamp"):
        return float(val.timestamp())
    return float(val)


def _row_to_job(row: Any) -> Dict[str, Any]:
    if isinstance(row, sqlite3.Row):
        data = dict(row)
    else:
        data = dict(row)
    return {
        "job_id": data["job_id"],
        "status": data["status"],
        "prompt": data["prompt"],
        "inn": data.get("inn") or "",
        "company_name": data.get("company_name") or "",
        "platforms": _json_load(data.get("platforms"), []),
        "metadata": _json_load(data.get("metadata"), {}),
        "webhook_url": data.get("webhook_url") or "",
        "result_url": data.get("result_url"),
        "candidates": _json_load(data.get("candidates"), []),
        "error": data.get("error"),
        "created_at": _to_epoch(data.get("created_at")),
        "updated_at": _to_epoch(data.get("updated_at")),
        "provider_response": _json_load(data.get("provider_response"), None),
    }


def save_job(job: Dict[str, Any]) -> None:
    with _LOCK:
        with _connection() as conn:
            if db_backend() == "postgres":
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO lpr_jobs (
                        job_id, status, prompt, inn, company_name, platforms, metadata,
                        webhook_url, result_url, candidates, error, created_at, updated_at,
                        provider_response
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                        %s, %s, %s::jsonb, %s,
                        to_timestamp(%s), to_timestamp(%s), %s::jsonb
                    )
                    ON CONFLICT (job_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        prompt = EXCLUDED.prompt,
                        inn = EXCLUDED.inn,
                        company_name = EXCLUDED.company_name,
                        platforms = EXCLUDED.platforms,
                        metadata = EXCLUDED.metadata,
                        webhook_url = EXCLUDED.webhook_url,
                        result_url = EXCLUDED.result_url,
                        candidates = EXCLUDED.candidates,
                        error = EXCLUDED.error,
                        updated_at = EXCLUDED.updated_at,
                        provider_response = EXCLUDED.provider_response
                    """,
                    (
                        job["job_id"],
                        job["status"],
                        job["prompt"],
                        job.get("inn") or "",
                        job.get("company_name") or "",
                        _json_dump(job.get("platforms") or []),
                        _json_dump(job.get("metadata") or {}),
                        job.get("webhook_url") or "",
                        job.get("result_url"),
                        _json_dump(job.get("candidates") or []),
                        job.get("error"),
                        float(job.get("created_at") or time.time()),
                        float(job.get("updated_at") or time.time()),
                        _json_dump(job.get("provider_response"))
                        if job.get("provider_response") is not None
                        else None,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO lpr_jobs (
                        job_id, status, prompt, inn, company_name, platforms, metadata,
                        webhook_url, result_url, candidates, error, created_at, updated_at,
                        provider_response
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        status=excluded.status,
                        prompt=excluded.prompt,
                        inn=excluded.inn,
                        company_name=excluded.company_name,
                        platforms=excluded.platforms,
                        metadata=excluded.metadata,
                        webhook_url=excluded.webhook_url,
                        result_url=excluded.result_url,
                        candidates=excluded.candidates,
                        error=excluded.error,
                        updated_at=excluded.updated_at,
                        provider_response=excluded.provider_response
                    """,
                    (
                        job["job_id"],
                        job["status"],
                        job["prompt"],
                        job.get("inn") or "",
                        job.get("company_name") or "",
                        _json_dump(job.get("platforms") or []),
                        _json_dump(job.get("metadata") or {}),
                        job.get("webhook_url") or "",
                        job.get("result_url"),
                        _json_dump(job.get("candidates") or []),
                        job.get("error"),
                        float(job.get("created_at") or time.time()),
                        float(job.get("updated_at") or time.time()),
                        _json_dump(job.get("provider_response"))
                        if job.get("provider_response") is not None
                        else None,
                    ),
                )


def load_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _connection() as conn:
        if db_backend() == "postgres":
            import psycopg2.extras

            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM lpr_jobs WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM lpr_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return _row_to_job(row) if row else None


def delete_job(job_id: str) -> None:
    with _LOCK:
        with _connection() as conn:
            if db_backend() == "postgres":
                cur = conn.cursor()
                cur.execute("DELETE FROM lpr_jobs WHERE job_id = %s", (job_id,))
            else:
                conn.execute("DELETE FROM lpr_jobs WHERE job_id = ?", (job_id,))


def purge_expired(cutoff_ts: float) -> int:
    with _LOCK:
        with _connection() as conn:
            if db_backend() == "postgres":
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM lpr_jobs WHERE created_at < to_timestamp(%s)",
                    (cutoff_ts,),
                )
                return cur.rowcount
            cur = conn.execute(
                "DELETE FROM lpr_jobs WHERE created_at < ?", (cutoff_ts,)
            )
            return cur.rowcount


init_db()
