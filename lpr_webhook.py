"""
Webhook-интеграция с внешним LPR-сервисом (Soprano / Grok Bot).

Безопасность inbound:
  - только HTTPS (Render edge + проверка X-Forwarded-Proto)
  - job_id = UUID v4 в path (не в query)
  - HMAC-SHA256 подпись тела: X-Webhook-Timestamp + X-Webhook-Signature
  - replay window ±5 мин
  - PII не логируется в plaintext
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import requests

import lpr_job_store

try:
    import memory_store
except ImportError:
    memory_store = None  # type: ignore

logger = logging.getLogger(__name__)

WEBHOOK_BASE_URL = (os.environ.get("WEBHOOK_BASE_URL") or os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
WEBHOOK_HMAC_SECRET = (os.environ.get("WEBHOOK_HMAC_SECRET") or os.environ.get("WEBHOOK_SECRET") or "").strip()
LPR_AGENT_SUBMIT_URL = os.environ.get("LPR_AGENT_SUBMIT_URL", "").strip()
LPR_AGENT_API_KEY = os.environ.get("LPR_AGENT_API_KEY", "").strip()
JOB_TTL = int(os.environ.get("LPR_JOB_TTL", "86400"))
REPLAY_TOLERANCE = int(os.environ.get("WEBHOOK_REPLAY_TOLERANCE", "300"))
WEBHOOK_REQUIRE_HTTPS = os.environ.get("WEBHOOK_REQUIRE_HTTPS", "1") == "1"
WEBHOOK_ALLOW_HTTP = os.environ.get("WEBHOOK_ALLOW_HTTP", "0") == "1"

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)

_jobs: Dict[str, Dict[str, Any]] = {}  # legacy cache; authoritative store is SQLite


def _persist_job(job: Dict[str, Any]) -> None:
    _jobs[job["job_id"]] = job
    lpr_job_store.save_job(job)


def _now() -> float:
    return time.time()


def _purge_expired() -> None:
    cutoff = _now() - JOB_TTL
    lpr_job_store.purge_expired(cutoff)
    stale = [jid for jid, job in _jobs.items() if job.get("created_at", 0) < cutoff]
    for jid in stale:
        _jobs.pop(jid, None)


def _assert_https_base_url(url: str) -> None:
    if url.startswith("https://"):
        return
    if WEBHOOK_ALLOW_HTTP and url.startswith("http://127.0.0.1"):
        return
    if WEBHOOK_ALLOW_HTTP and url.startswith("http://localhost"):
        return
    raise ValueError("WEBHOOK_BASE_URL должен быть https:// (Render public URL)")


def build_callback_url(job_id: str) -> str:
    if not WEBHOOK_BASE_URL:
        raise ValueError(
            "WEBHOOK_BASE_URL не задан — укажите публичный HTTPS URL сервиса на Render"
        )
    _assert_https_base_url(WEBHOOK_BASE_URL)
    return f"{WEBHOOK_BASE_URL}/api/webhooks/lpr/inbound/{job_id}"


def validate_job_id(job_id: str) -> None:
    if not _UUID_RE.match(job_id or ""):
        raise ValueError("Invalid job_id")


def verify_https_inbound(forwarded_proto: Optional[str]) -> bool:
    if not WEBHOOK_REQUIRE_HTTPS:
        return True
    if WEBHOOK_ALLOW_HTTP:
        return True
    return (forwarded_proto or "").lower() == "https"


def compute_inbound_signature(timestamp: str, body: bytes) -> str:
    signed_payload = f"{timestamp}.".encode("utf-8") + body
    return hmac.new(
        WEBHOOK_HMAC_SECRET.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()


def verify_inbound_hmac(
    timestamp: Optional[str],
    signature: Optional[str],
    body: bytes,
) -> Tuple[bool, str]:
    if not WEBHOOK_HMAC_SECRET:
        return False, "WEBHOOK_HMAC_SECRET не настроен на сервере"
    if not timestamp or not signature:
        return False, "Требуются заголовки X-Webhook-Timestamp и X-Webhook-Signature"
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False, "Некорректный X-Webhook-Timestamp"
    if abs(_now() - ts) > REPLAY_TOLERANCE:
        return False, "Timestamp вне окна replay (±5 мин)"
    expected = compute_inbound_signature(timestamp, body)
    if not hmac.compare_digest(expected, signature.strip()):
        return False, "Неверная подпись X-Webhook-Signature"
    return True, ""


def _redact_pii_value(value: Any) -> Any:
    if not value or not isinstance(value, str):
        return value
    if "@" in value:
        local, _, domain = value.partition("@")
        return f"{local[:1]}***@{domain}" if domain else "***"
    if value.startswith("http"):
        return value.split("/")[-1][:4] + "***" if len(value) > 8 else "***"
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 7:
        return f"***{digits[-2:]}"
    return "***"


def _redact_contact(contact: Dict[str, Any]) -> Dict[str, Any]:
    redacted = dict(contact)
    for key in ("email", "phone", "telegram"):
        if redacted.get(key):
            redacted[key] = _redact_pii_value(redacted[key])
    return redacted


def _log_inbound(job_id: str, status: str, candidates_count: int = 0) -> None:
    logger.info(
        "lpr_webhook inbound job_id=%s status=%s candidates=%s",
        job_id,
        status,
        candidates_count,
    )


def create_job(
    *,
    prompt: str,
    inn: str = "",
    company_name: str = "",
    platforms: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    auto_submit: bool = True,
) -> Dict[str, Any]:
    """Создаёт job и возвращает webhook URL для передачи провайдеру."""
    _purge_expired()
    job_id = str(uuid.uuid4())
    callback_url = build_callback_url(job_id)
    plats = platforms or ["tenchat"]

    job = {
        "job_id": job_id,
        "status": "pending",
        "prompt": prompt,
        "inn": inn,
        "company_name": company_name,
        "platforms": plats,
        "metadata": metadata or {},
        "webhook_url": callback_url,
        "result_url": None,
        "candidates": [],
        "error": None,
        "created_at": _now(),
        "updated_at": _now(),
        "provider_response": None,
    }
    _jobs[job_id] = job
    _persist_job(job)

    submit_info = None
    if auto_submit and LPR_AGENT_SUBMIT_URL:
        submit_info = submit_task_to_provider(job)

    return {
        "job_id": job_id,
        "status": job["status"],
        "webhook_url": callback_url,
        "prompt": prompt,
        "inn": inn,
        "company_name": company_name,
        "platforms": plats,
        "instructions_for_provider": _provider_instructions(job_id, callback_url),
        "auto_submit": submit_info,
    }


def _provider_instructions(job_id: str, callback_url: str) -> Dict[str, Any]:
    return {
        "provider": "soprano",
        "callback_url": callback_url,
        "callback_method": "POST",
        "callback_path_note": "job_id только в path, контакты только в JSON body",
        "auth": {
            "type": "hmac-sha256",
            "headers": {
                "X-Webhook-Timestamp": "unix seconds (UTC)",
                "X-Webhook-Signature": "hex hmac-sha256(timestamp + '.' + raw_body)",
            },
            "replay_window_seconds": REPLAY_TOLERANCE,
            "signature_example_pseudo": "HMAC_SHA256(secret, f'{timestamp}.{raw_json_body}')",
        },
        "callback_body_contract": {
            "status": "completed",
            "contacts": [
                {
                    "name": "ФИО",
                    "role": "Должность",
                    "company": "ООО «…»",
                    "profile_url": "https://tenchat.ru/…",
                    "telegram": "https://t.me/…",
                    "email": "… или null",
                    "phone": "… или null",
                    "source": "TenChat · …",
                    "confidence": 95,
                    "stakeholder_hint": "ceo",
                    "extra_links": ["https://…"],
                }
            ],
        },
        "rules": [
            "HTTPS only",
            "Не выдумывать email/phone",
            "Пустые поля — null или omit",
            "Можно вернуть result_url (HTTPS) вместо inline contacts",
        ],
    }


def submit_task_to_provider(job: Dict[str, Any] | None = None, job_id: str = "") -> Dict[str, Any]:
    if job is None:
        job = get_job(job_id)
    if not LPR_AGENT_SUBMIT_URL:
        return {"skipped": True, "reason": "LPR_AGENT_SUBMIT_URL не задан"}

    payload = {
        "prompt": job["prompt"],
        "task": job["prompt"],
        "webhook_url": job["webhook_url"],
        "callback_url": job["webhook_url"],
        "job_id": job["job_id"],
        "inn": job.get("inn"),
        "company": job.get("company_name"),
        "company_name": job.get("company_name"),
        "platforms": job.get("platforms"),
        "metadata": {"job_id": job["job_id"], **(job.get("metadata") or {})},
    }
    headers = {"Content-Type": "application/json"}
    if LPR_AGENT_API_KEY:
        headers["Authorization"] = f"Bearer {LPR_AGENT_API_KEY}"

    try:
        resp = requests.post(LPR_AGENT_SUBMIT_URL, json=payload, headers=headers, timeout=45)
        job["status"] = "running" if resp.status_code < 400 else "failed"
        job["provider_response"] = {"status_code": resp.status_code, "body": _safe_json(resp)}
        job["updated_at"] = _now()
        if resp.status_code >= 400:
            job["error"] = f"Provider submit HTTP {resp.status_code}"
        _persist_job(job)
        return job["provider_response"]
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        job["updated_at"] = _now()
        _persist_job(job)
        return {"error": str(exc)}


def get_job(job_id: str) -> Dict[str, Any]:
    validate_job_id(job_id)
    job = lpr_job_store.load_job(job_id) or _jobs.get(job_id)
    if not job:
        raise KeyError(f"Job {job_id} not found")
    _jobs[job_id] = job
    return job


def _is_honest_empty_inbound(payload: Dict[str, Any]) -> bool:
    """Provider finished successfully but found no people — not a transport error."""
    status = (payload.get("status") or "").lower().strip()
    if status in ("failed", "error"):
        return False
    if status in ("completed", "success", "ok", "done", "empty", "not_found", "no_results"):
        return True
    for key in ("contacts", "results", "people", "persons", "items", "profiles"):
        val = payload.get(key)
        if isinstance(val, list) and len(val) == 0:
            return True
    data = payload.get("data")
    if isinstance(data, dict):
        return _is_honest_empty_inbound(data)
    # Explicit success-ish payload without error and without result_url requirement
    if not payload.get("error") and status != "failed":
        return True
    return False


def _resolve_inbound_status(
    payload: Dict[str, Any], candidates: List[Dict[str, Any]]
) -> Tuple[str, Optional[str]]:
    if candidates:
        return "completed", None
    status = (payload.get("status") or "").lower().strip()
    if status in ("failed", "error"):
        return "failed", payload.get("error") or payload.get("message") or "Provider reported failure"
    if _is_honest_empty_inbound(payload):
        return "completed", None
    return "failed", "Пустой результат — ожидали result_url или contacts/results"


def get_job_public(job_id: str, *, include_pii: bool = True) -> Dict[str, Any]:
    job = get_job(job_id)
    candidates = job.get("candidates") or []
    if not include_pii:
        candidates = [_redact_contact(c) for c in candidates]
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "inn": job.get("inn"),
        "company_name": job.get("company_name"),
        "webhook_url": job.get("webhook_url"),
        "result_url": job.get("result_url"),
        "candidates_count": len(job.get("candidates") or []),
        "candidates": candidates,
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


def handle_inbound_webhook(job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    job = get_job(job_id)
    job["status"] = "running"
    job["updated_at"] = _now()

    result_url = _extract_result_url(payload)
    if result_url:
        if not result_url.startswith("https://"):
            job["status"] = "failed"
            job["error"] = "result_url должен быть HTTPS"
            job["updated_at"] = _now()
            _log_inbound(job_id, "failed")
            _persist_job(job)
            return get_job_public(job_id)
        job["result_url"] = result_url
        try:
            fetched = fetch_result_url(result_url)
            payload = {**payload, **fetched} if isinstance(fetched, dict) else {"data": fetched}
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = f"Не удалось скачать result_url: {exc}"
            job["updated_at"] = _now()
            _log_inbound(job_id, "failed")
            _persist_job(job)
            return get_job_public(job_id)

    candidates = normalize_contacts(payload, provider="soprano")
    status, err = _resolve_inbound_status(payload, candidates)
    job["status"] = status
    job["error"] = err
    if candidates:
        job["candidates"] = candidates
    elif status == "completed":
        job["candidates"] = []
        job["error"] = None

    job["updated_at"] = _now()
    _log_inbound(job_id, job["status"], len(candidates))
    if candidates:
        logger.debug(
            "lpr_webhook candidates_redacted=%s",
            json.dumps([_redact_contact(c) for c in candidates], ensure_ascii=False),
        )
        if memory_store is not None:
            try:
                inn = (job.get("inn") or "").strip()
                company_name = job.get("company_name") or ""
                if not inn and candidates:
                    inn = (candidates[0].get("company_inn") or "").strip()
                if inn:
                    memory_store.upsert_from_inbound(inn, company_name, candidates)
            except Exception:
                logger.exception("memory_store upsert failed job_id=%s", job_id)
    _persist_job(job)
    return get_job_public(job_id)


def fetch_result_url(url: str) -> Any:
    if not url.startswith("https://"):
        raise ValueError("result_url must use HTTPS")
    headers = {}
    if LPR_AGENT_API_KEY:
        headers["Authorization"] = f"Bearer {LPR_AGENT_API_KEY}"
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _extract_result_url(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("result_url", "results_url", "url", "link", "download_url", "file_url"):
        val = payload.get(key)
        if isinstance(val, str) and val.startswith("https://"):
            return val
    data = payload.get("data")
    if isinstance(data, dict):
        return _extract_result_url(data)
    return None


def _extract_people_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("contacts", "results", "people", "persons", "items", "data", "profiles"):
        val = payload.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
        if isinstance(val, dict):
            nested = _extract_people_list(val)
            if nested:
                return nested
    return []


def normalize_contacts(payload: Dict[str, Any], provider: str = "lpr_agent") -> List[Dict[str, Any]]:
    people = _extract_people_list(payload)
    out: List[Dict[str, Any]] = []
    for person in people:
        name = (person.get("name") or person.get("full_name") or person.get("fio") or "").strip()
        role = (person.get("role") or person.get("title") or person.get("position") or person.get("job_title") or "").strip()
        profile_url = (
            person.get("profile_url") or person.get("url") or person.get("linkedin") or person.get("tenchat") or ""
        ).strip()
        platform = (person.get("platform") or person.get("source_platform") or "").lower()
        if not platform:
            if "tenchat" in profile_url:
                platform = "tenchat"
            elif "linkedin" in profile_url:
                platform = "linkedin"

        conf = person.get("confidence") or person.get("score") or 72
        try:
            conf = int(conf)
        except (TypeError, ValueError):
            conf = 72

        hint = person.get("stakeholder_hint") or _guess_stakeholder_hint(role)
        source_type = "tenchat_verified" if platform == "tenchat" else "identity"
        if "linkedin" in platform or "linkedin" in profile_url:
            source_type = "identity"

        company = (person.get("company") or person.get("company_name") or "").strip()
        source_label = (person.get("source") or "").strip()
        if not source_label:
            source_label = f"{provider} · {platform or 'webhook'}"
        if company and company not in source_label:
            source_label = f"{source_label} · {company}"

        email = person.get("email")
        phone = person.get("phone")
        telegram = person.get("telegram")
        if isinstance(email, str) and not email.strip():
            email = None
        if isinstance(phone, str) and not phone.strip():
            phone = None
        if isinstance(telegram, str) and not telegram.strip():
            telegram = None

        extra_links = person.get("extra_links") or person.get("links")
        if not isinstance(extra_links, list):
            extra_links = []

        out.append({
            "name": name or "—",
            "role": role or "Контакт",
            "company": company or None,
            "source": source_label,
            "source_type": source_type,
            "confidence_base": min(max(conf, 0), 100),
            "profile_url": profile_url,
            "profile_resolved": bool(profile_url),
            "profile_platform": platform or ("tenchat" if "tenchat" in profile_url else "linkedin"),
            "stakeholder_hint": hint,
            "email": email,
            "phone": phone,
            "telegram": telegram,
            "extra_links": extra_links,
        })
    return out


def _guess_stakeholder_hint(role: str) -> str:
    r = (role or "").lower()
    if any(k in r for k in ("ceo", "генеральн", "директор", "собствен")):
        return "ceo"
    if any(k in r for k in ("hr", "рекрут", "кадр", "подбор")):
        return "hr"
    if any(k in r for k in ("it", "1с", "1c", "архитект", "cto", "разработ")):
        return "lvr"
    return "lpr"


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return (resp.text or "")[:500]


def default_prompt(company_name: str, inn: str, product: str = "1С") -> str:
    return (
        f"Компания: {company_name}, ИНН {inn}. "
        f"Найди в TenChat людей, связанных с компанией (ЛПР, IT/1С, HR, CEO). "
        f"Продукт продавца: {product}. "
        f"Только факты из профилей и открытых источников — без выдуманных контактов. "
        f"Верни JSON: contacts[] с полями name, role, company, profile_url, telegram, email, phone, source, confidence."
    )


_POWER_TYPE = {
    "ceo": "Собственник / CEO",
    "lpr": "ЛПР (Бизнес-заказчик)",
    "lvr": "ЛВР (Технический эксперт)",
    "hr": "ЛДПР / Инициатор",
}


def candidates_to_lpr_entries(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in candidates:
        hint = c.get("stakeholder_hint") or "lpr"
        platform = c.get("profile_platform") or "tenchat"
        platform_label = {"tenchat": "TenChat", "linkedin": "LinkedIn"}.get(platform, platform)
        resolved = bool(c.get("profile_resolved") and c.get("profile_url"))
        conf = int(c.get("confidence_base") or c.get("profile_confidence") or 0)
        email = c.get("email")
        phone = c.get("phone")
        telegram = c.get("telegram")
        out.append({
            "power_type": _POWER_TYPE.get(hint, _POWER_TYPE["lpr"]),
            "role": (f"{c.get('role') or 'Контакт'}" + (f" · {c['company']}" if c.get("company") else "")),
            "name": c.get("name") or "",
            "source": c.get("source") or "LPR Agent · webhook",
            "source_type": c.get("source_type") or "identity",
            "identity_source": c.get("source") or "LPR Agent · webhook",
            "profile_url": c.get("profile_url") or "",
            "profile_resolved": resolved,
            "profile_platform": platform_label,
            "profile_confidence": conf,
            "profile_search_engine": "lpr_webhook",
            "dork_query": "",
            "pitch_focus": "",
            "contacts": {
                "phone": phone,
                "phone_type": "LPR Agent" if phone else None,
                "email": email,
                "email_status": "webhook" if email else None,
                "email_badge": "Webhook" if email else None,
                "is_verified": bool(email),
                "telegram": telegram,
                "search_link_tenchat": c.get("profile_url") if platform == "tenchat" else "",
                "search_link_linkedin": c.get("profile_url") if platform == "linkedin" else "",
                "profile_badge": f"Direct • {platform_label}" if resolved else "LPR Agent",
                "profile_resolved": resolved,
            },
        })
    return out


def is_configured() -> bool:
    if not WEBHOOK_BASE_URL:
        return False
    try:
        _assert_https_base_url(WEBHOOK_BASE_URL)
    except ValueError:
        return False
    return True


def hmac_configured() -> bool:
    return bool(WEBHOOK_HMAC_SECRET)


def store_info() -> Dict[str, Any]:
    return lpr_job_store.store_info()
