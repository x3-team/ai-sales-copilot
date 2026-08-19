"""SQLite persistence for LPR webhook jobs (survives process restart; use Render disk for full restarts)."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

_DEFAULT_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.environ.get("LPR_JOBS_DB_PATH") or os.path.join(_DEFAULT_DIR, "lpr_jobs.db")

_LOCK = threading.Lock()


def _ensure_dir() -> None:
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)


def _connect() -> sqlite3.Connection:
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lpr_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    inn TEXT,
                    company_name TEXT,
                    platforms TEXT,
                    metadata TEXT,
                    webhook_url TEXT,
                    result_url TEXT,
                    candidates TEXT,
                    error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    provider_response TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lpr_jobs_created_at ON lpr_jobs(created_at)"
            )
            conn.commit()
        finally:
            conn.close()


def _row_to_job(row: sqlite3.Row) -> Dict[str, Any]:
    def _json_load(val: Optional[str], default: Any) -> Any:
        if val is None or val == "":
            return default
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return default

    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "prompt": row["prompt"],
        "inn": row["inn"] or "",
        "company_name": row["company_name"] or "",
        "platforms": _json_load(row["platforms"], []),
        "metadata": _json_load(row["metadata"], {}),
        "webhook_url": row["webhook_url"] or "",
        "result_url": row["result_url"],
        "candidates": _json_load(row["candidates"], []),
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "provider_response": _json_load(row["provider_response"], None),
    }


def save_job(job: Dict[str, Any]) -> None:
    init_db()
    with _LOCK:
        conn = _connect()
        try:
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
                    json.dumps(job.get("platforms") or [], ensure_ascii=False),
                    json.dumps(job.get("metadata") or {}, ensure_ascii=False),
                    job.get("webhook_url") or "",
                    job.get("result_url"),
                    json.dumps(job.get("candidates") or [], ensure_ascii=False),
                    job.get("error"),
                    float(job.get("created_at") or time.time()),
                    float(job.get("updated_at") or time.time()),
                    json.dumps(job.get("provider_response"), ensure_ascii=False)
                    if job.get("provider_response") is not None
                    else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def load_job(job_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM lpr_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return _row_to_job(row) if row else None
        finally:
            conn.close()


def delete_job(job_id: str) -> None:
    init_db()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute("DELETE FROM lpr_jobs WHERE job_id = ?", (job_id,))
            conn.commit()
        finally:
            conn.close()


def purge_expired(cutoff_ts: float) -> int:
    init_db()
    with _LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM lpr_jobs WHERE created_at < ?", (cutoff_ts,)
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


def db_path() -> str:
    return DB_PATH


init_db()
