"""
Webhook-интеграция с внешним LPR-сервисом (TenChat / LinkedIn).

Паттерн без документации:
  1. Мы создаём job и отдаём callback URL + промпт.
  2. Провайдер выполняет задачу и вызывает наш webhook с result_url или с данными inline.
  3. Мы скачиваем result_url (если есть) и нормализуем в candidates[] для Identity Layer.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import requests

WEBHOOK_BASE_URL = (os.environ.get("WEBHOOK_BASE_URL") or os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
LPR_AGENT_SUBMIT_URL = os.environ.get("LPR_AGENT_SUBMIT_URL", "").strip()
LPR_AGENT_API_KEY = os.environ.get("LPR_AGENT_API_KEY", "").strip()
JOB_TTL = int(os.environ.get("LPR_JOB_TTL", "86400"))

_jobs: Dict[str, Dict[str, Any]] = {}


def _now() -> float:
    return time.time()


def _purge_expired() -> None:
    cutoff = _now() - JOB_TTL
    stale = [jid for jid, job in _jobs.items() if job.get("created_at", 0) < cutoff]
    for jid in stale:
        _jobs.pop(jid, None)


def build_callback_url(job_id: str) -> str:
    if not WEBHOOK_BASE_URL:
        raise ValueError(
            "WEBHOOK_BASE_URL не задан — укажите публичный URL сервиса, "
            "например https://your-app.onrender.com"
        )
    return f"{WEBHOOK_BASE_URL}/api/webhooks/lpr/inbound?job_id={job_id}"


def verify_inbound_secret(provided: Optional[str]) -> bool:
    if not WEBHOOK_SECRET:
        return True
    return hmac.compare_digest(provided or "", WEBHOOK_SECRET)


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
    plats = platforms or ["tenchat", "linkedin"]

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
        "instructions_for_provider": {
            "callback_url": callback_url,
            "expected_callback_body_examples": [
                {"result_url": "https://provider.example/results/abc.json"},
                {"url": "https://provider.example/results/abc.json"},
                {"contacts": [{"name": "Иван Иванов", "role": "CFO", "profile_url": "https://tenchat.ru/..."}]},
            ],
            "optional_header": "X-Webhook-Secret: <WEBHOOK_SECRET>" if WEBHOOK_SECRET else None,
        },
        "auto_submit": submit_info,
    }


def submit_task_to_provider(job: Dict[str, Any] | None = None, job_id: str = "") -> Dict[str, Any]:
    """Опционально: POST задачи на URL провайдера, если LPR_AGENT_SUBMIT_URL задан."""
    if job is None:
        job = get_job(job_id)
    if not LPR_AGENT_SUBMIT_URL:
        return {"skipped": True, "reason": "LPR_AGENT_SUBMIT_URL не задан"}

    payload = {
        "prompt": job["prompt"],
        "task": job["prompt"],
        "webhook_url": job["webhook_url"],
        "callback_url": job["webhook_url"],
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
        return job["provider_response"]
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        job["updated_at"] = _now()
        return {"error": str(exc)}


def get_job(job_id: str) -> Dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise KeyError(f"Job {job_id} not found")
    return job


def get_job_public(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "inn": job.get("inn"),
        "company_name": job.get("company_name"),
        "webhook_url": job.get("webhook_url"),
        "result_url": job.get("result_url"),
        "candidates_count": len(job.get("candidates") or []),
        "candidates": job.get("candidates") or [],
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


def handle_inbound_webhook(job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Принимает callback от провайдера.
    Поддерживает:
      - result_url / url / results_url → скачиваем JSON
      - contacts / results / people / data → inline
    """
    job = get_job(job_id)
    job["status"] = "running"
    job["updated_at"] = _now()

    result_url = _extract_result_url(payload)
    if result_url:
        job["result_url"] = result_url
        try:
            fetched = fetch_result_url(result_url)
            payload = {**payload, **fetched} if isinstance(fetched, dict) else {"data": fetched}

        except Exception as exc:
            job["status"] = "failed"
            job["error"] = f"Не удалось скачать result_url: {exc}"
            job["updated_at"] = _now()
            return get_job_public(job_id)

    candidates = normalize_contacts(payload, provider="lpr_agent")
    if not candidates:
        status = (payload.get("status") or "").lower()
        if status in ("failed", "error"):
            job["status"] = "failed"
            job["error"] = payload.get("error") or payload.get("message") or "Provider reported failure"
        else:
            job["status"] = "failed"
            job["error"] = "Пустой результат — ожидали result_url или contacts/results"
    else:
        job["status"] = "completed"
        job["candidates"] = candidates
        job["error"] = None

    job["updated_at"] = _now()
    job["raw_payload_keys"] = list(payload.keys())[:20]
    return get_job_public(job_id)


def fetch_result_url(url: str) -> Any:
    headers = {}
    if LPR_AGENT_API_KEY:
        headers["Authorization"] = f"Bearer {LPR_AGENT_API_KEY}"
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _extract_result_url(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("result_url", "results_url", "url", "link", "download_url", "file_url"):
        val = payload.get(key)
        if isinstance(val, str) and val.startswith("http"):
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

        out.append({
            "name": name or "—",
            "role": role or "Контакт",
            "source": f"{provider} · {platform or 'webhook'}",
            "source_type": source_type,
            "confidence_base": min(max(conf, 0), 100),
            "profile_url": profile_url,
            "profile_resolved": bool(profile_url),
            "profile_platform": platform or ("tenchat" if "tenchat" in profile_url else "linkedin"),
            "stakeholder_hint": hint,
            "email": person.get("email"),
            "phone": person.get("phone"),
            "telegram": person.get("telegram"),
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
        f"Найди в TenChat и LinkedIn людей, связанных с компанией: "
        f"финансовый/коммерческий директор (ЛПР), IT/1С lead (ЛВР), HR (ЛДПР). "
        f"Продукт продавца: {product}. "
        f"Верни JSON со списком contacts: name, role, platform, profile_url, email, phone, confidence."
    )


_POWER_TYPE = {
    "ceo": "Собственник / CEO",
    "lpr": "ЛПР (Бизнес-заказчик)",
    "lvr": "ЛВР (Технический эксперт)",
    "hr": "ЛДПР / Инициатор",
}


def candidates_to_lpr_entries(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Преобразует webhook-кандидатов в формат lpr_matrix для UI."""
    out: List[Dict[str, Any]] = []
    for c in candidates:
        hint = c.get("stakeholder_hint") or "lpr"
        platform = c.get("profile_platform") or "tenchat"
        platform_label = {"tenchat": "TenChat", "linkedin": "LinkedIn"}.get(platform, platform)
        resolved = bool(c.get("profile_resolved") and c.get("profile_url"))
        conf = int(c.get("confidence_base") or c.get("profile_confidence") or 0)
        email = c.get("email") or "—"
        phone = c.get("phone") or "—"
        out.append({
            "power_type": _POWER_TYPE.get(hint, _POWER_TYPE["lpr"]),
            "role": c.get("role") or "Контакт",
            "name": c.get("name") or "—",
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
                "phone_type": "LPR Agent",
                "email": email,
                "email_status": "webhook" if email != "—" else "unknown",
                "email_badge": "Webhook" if email != "—" else "—",
                "is_verified": email != "—",
                "telegram": c.get("telegram") or "—",
                "search_link_tenchat": c.get("profile_url") if platform == "tenchat" else "",
                "search_link_linkedin": c.get("profile_url") if platform == "linkedin" else "",
                "profile_badge": f"Direct • {platform_label}" if resolved else "LPR Agent",
                "profile_resolved": resolved,
            },
        })
    return out


def is_configured() -> bool:
    return bool(WEBHOOK_BASE_URL)
