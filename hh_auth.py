"""
HH.ru Employer API (optional BYOS) — поиск резюме сотрудников по опыту работы.

Официальный API: https://dev.hh.ru/admin
Требуется: аккаунт работодателя + платный доступ к базе резюме.

Env:
  HH_ACCESS_TOKEN  — OAuth Bearer token
  HH_USER_AGENT    — AI-Sales-Copilot/1.0 (you@email.com)  [обязателен для HH API]
"""
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests


class HHAuthClient:
    BASE_URL = "https://api.hh.ru"
    DEFAULT_USER_AGENT = "AI-Sales-Copilot/1.0 (copilot@local.dev)"

    ROLE_SEARCHES: Tuple[Tuple[str, str], ...] = (
        ("lpr", "финансовый директор"),
        ("lpr", "коммерческий директор"),
        ("lpr", "директор по продажам"),
        ("lvr", "1с"),
        ("lvr", "архитектор 1с"),
        ("lvr", "руководитель it"),
        ("hr", "hr"),
        ("hr", "рекрутер"),
    )

    @classmethod
    def is_configured(cls) -> bool:
        return bool(os.environ.get("HH_ACCESS_TOKEN", "").strip())

    @classmethod
    def _headers(cls) -> Dict[str, str]:
        token = os.environ.get("HH_ACCESS_TOKEN", "").strip().removeprefix("Bearer ").strip()
        ua = os.environ.get("HH_USER_AGENT", "").strip() or cls.DEFAULT_USER_AGENT
        return {
            "Authorization": f"Bearer {token}",
            "User-Agent": ua,
            "Accept": "application/json",
        }

    @classmethod
    def session_status(cls) -> Dict:
        if not cls.is_configured():
            return {
                "configured": False,
                "authenticated": False,
                "resume_access": False,
                "message": (
                    "Задайте HH_ACCESS_TOKEN в .env "
                    "(https://dev.hh.ru/admin → приложение → OAuth token)"
                ),
            }
        try:
            resp = requests.get(f"{cls.BASE_URL}/me", headers=cls._headers(), timeout=10)
            if resp.status_code == 401:
                return {
                    "configured": True,
                    "authenticated": False,
                    "resume_access": False,
                    "message": "HH токен недействителен — перевыпустите на dev.hh.ru",
                }
            if resp.status_code != 200:
                return {
                    "configured": True,
                    "authenticated": False,
                    "resume_access": False,
                    "message": f"HH /me вернул HTTP {resp.status_code}",
                }

            data = resp.json()
            employer = data.get("employer") if isinstance(data.get("employer"), dict) else None
            is_employer = bool(data.get("is_employer")) or bool(employer)

            resume_access = False
            probe_detail = ""
            if is_employer:
                probe = requests.get(
                    f"{cls.BASE_URL}/resumes",
                    headers=cls._headers(),
                    params={"text": "директор", "per_page": 1, "page": 0},
                    timeout=10,
                )
                resume_access = probe.status_code == 200
                if probe.status_code == 403:
                    probe_detail = "403 — нужна платная база резюме у работодателя"
                elif probe.status_code != 200:
                    probe_detail = f"probe HTTP {probe.status_code}"

            if resume_access:
                message = "HH Employer API: поиск резюме доступен"
            elif is_employer:
                message = f"Токен работодателя OK, но поиск резюме недоступен. {probe_detail}".strip()
            else:
                message = "Токен валиден, но это не аккаунт работодателя (нужен employer OAuth)"

            return {
                "configured": True,
                "authenticated": True,
                "resume_access": resume_access,
                "is_employer": is_employer,
                "employer_name": (employer or {}).get("name"),
                "message": message,
            }
        except Exception as exc:
            return {
                "configured": True,
                "authenticated": False,
                "resume_access": False,
                "message": f"Ошибка проверки HH: {exc}",
            }

    @classmethod
    def _vacancy_api_headers(cls) -> Dict[str, str]:
        """Public HH API headers — User-Agent required; Bearer optional."""
        ua = os.environ.get("HH_USER_AGENT", "").strip() or cls.DEFAULT_USER_AGENT
        headers = {"User-Agent": ua, "Accept": "application/json"}
        token = os.environ.get("HH_ACCESS_TOKEN", "").strip().removeprefix("Bearer ").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @classmethod
    def probe_vacancies_api(cls) -> Dict[str, Any]:
        """Check if api.hh.ru/vacancies is reachable from this host."""
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/vacancies",
                headers=cls._vacancy_api_headers(),
                params={"text": "1с", "per_page": 1, "page": 0},
                timeout=12,
            )
            if resp.status_code == 200:
                found = int(resp.json().get("found") or 0)
                return {
                    "available": True,
                    "http_status": 200,
                    "found_sample": found,
                    "message": "HH Vacancies API доступен",
                }
            if resp.status_code in (403, 429):
                return {
                    "available": False,
                    "http_status": resp.status_code,
                    "message": (
                        f"HH API недоступен с этого сервера (HTTP {resp.status_code}). "
                        "Скан вакансий с Render может быть заблокирован."
                    ),
                }
            return {
                "available": False,
                "http_status": resp.status_code,
                "message": f"HH Vacancies API вернул HTTP {resp.status_code}",
            }
        except requests.RequestException as exc:
            return {
                "available": False,
                "http_status": 0,
                "message": f"HH API: ошибка сети ({exc.__class__.__name__})",
            }

    @classmethod
    def search_vacancies_api(
        cls,
        text: str,
        *,
        per_page: int = 20,
        page: int = 0,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """GET /vacancies — JSON only, no HTML."""
        try:
            resp = requests.get(
                f"{cls.BASE_URL}/vacancies",
                headers=cls._vacancy_api_headers(),
                params={
                    "text": text,
                    "per_page": per_page,
                    "page": page,
                    "order_by": "publication_time",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                return [], f"http_{resp.status_code}"
            return list(resp.json().get("items") or []), None
        except requests.RequestException as exc:
            return [], exc.__class__.__name__

    @classmethod
    def scan_one_c_vacancy_triggers(
        cls,
        *,
        limit: int = 5,
        product_keyword: str = "1С",
    ) -> Dict[str, Any]:
        """
        Find 1C vacancy triggers via HH API + confirm INN via DaData.
        Vacancy contacts are ignored — trigger + company only.
        """
        from dadata_company import is_configured as dadata_ok, resolve_party_inn
        from identity_layer import HHVacancyParser
        from live_companies import is_active_company

        probe = cls.probe_vacancies_api()
        if not probe.get("available"):
            return {
                "scan_status": "hh_unreachable",
                "scan_message": probe.get("message") or "HH API недоступен",
                "items": [],
                "raw_vacancy_count": 0,
                "http_status": probe.get("http_status"),
            }

        if not dadata_ok():
            return {
                "scan_status": "dadata_missing",
                "scan_message": "DaData не настроен — нельзя подтвердить ИНН компаний из HH",
                "items": [],
                "raw_vacancy_count": 0,
            }

        keywords = HHVacancyParser.one_c_search_keywords(product_keyword)
        raw_vacancy_count = 0
        api_errors: List[str] = []
        seen_employers: set = set()
        out: List[Dict[str, Any]] = []

        for kw in keywords:
            if len(out) >= limit:
                break
            items, err = cls.search_vacancies_api(kw, per_page=30)
            if err:
                api_errors.append(f"{kw}:{err}")
                continue
            raw_vacancy_count += len(items)
            for item in items:
                if item.get("archived"):
                    continue
                title = (item.get("name") or "").strip()
                snippet = item.get("snippet") or {}
                blob = f"{title} {snippet.get('requirement', '')} {snippet.get('responsibility', '')}".lower()
                if not HHVacancyParser.matches_one_c_focus(blob):
                    continue
                employer = item.get("employer") or {}
                employer_name = (employer.get("name") or "").strip()
                employer_id = str(employer.get("id") or "")
                dedupe_key = employer_id or employer_name.lower()
                if not employer_name or dedupe_key in seen_employers:
                    continue

                resolved = resolve_party_inn(employer_name)
                inn = (resolved.get("inn") or "").strip()
                if not inn:
                    continue
                if not is_active_company(inn):
                    continue
                state = resolved.get("reason")
                if state == "no_match" or not resolved.get("active"):
                    continue

                seen_employers.add(dedupe_key)
                vid = str(item.get("id") or "")
                vacancy_url = item.get("alternate_url") or (
                    f"https://hh.ru/vacancy/{vid}" if vid else ""
                )
                salary = item.get("salary") or {}
                sal_text = ""
                if salary:
                    frm = salary.get("from")
                    to = salary.get("to")
                    cur = salary.get("currency") or "RUR"
                    if frm and to:
                        sal_text = f"{frm}–{to} {cur}"
                    elif frm:
                        sal_text = f"от {frm} {cur}"
                    elif to:
                        sal_text = f"до {to} {cur}"

                out.append({
                    "employer": employer_name,
                    "employer_matched": resolved.get("matched_name") or employer_name,
                    "inn": inn,
                    "title": title,
                    "salary": sal_text,
                    "url": vacancy_url,
                    "vacancy_id": vid,
                    "demand_reason": f"HH API: «{title}»",
                    "trigger_only": True,
                })
                if len(out) >= limit:
                    break

        if raw_vacancy_count == 0 and api_errors and not out:
            return {
                "scan_status": "hh_unreachable",
                "scan_message": (
                    "HH API не вернул вакансии "
                    f"({', '.join(api_errors[:3])})"
                ),
                "items": [],
                "raw_vacancy_count": 0,
                "api_errors": api_errors[:5],
            }

        if raw_vacancy_count == 0:
            return {
                "scan_status": "hh_empty",
                "scan_message": "HH API доступен, но вакансий 1С по запросу не найдено",
                "items": [],
                "raw_vacancy_count": 0,
            }

        if not out:
            return {
                "scan_status": "no_inn_matches",
                "scan_message": (
                    f"HH вернул {raw_vacancy_count} вакансий, "
                    "но ни одной компании с подтверждённым активным ИНН"
                ),
                "items": [],
                "raw_vacancy_count": raw_vacancy_count,
            }

        return {
            "scan_status": "ok",
            "scan_message": f"Найдено {len(out)} компаний с ИНН (триггер HH)",
            "items": out,
            "raw_vacancy_count": raw_vacancy_count,
        }

    @classmethod
    def search_resumes(
        cls,
        company_name: str,
        role_hint: str = "",
        per_page: int = 8,
    ) -> List[Dict]:
        if not cls.is_configured():
            return []

        params: List[Tuple[str, str]] = [
            ("text", company_name),
            ("text.logic", "all"),
            ("text.field", "experience_company"),
            ("text.period", "all_time"),
            ("per_page", str(per_page)),
            ("page", "0"),
        ]
        if role_hint:
            params.extend([
                ("text", role_hint),
                ("text.logic", "all"),
                ("text.field", "experience_position"),
                ("text.period", "all_time"),
            ])

        try:
            resp = requests.get(
                f"{cls.BASE_URL}/resumes",
                headers=cls._headers(),
                params=params,
                timeout=12,
            )
            if resp.status_code != 200:
                return []
            return resp.json().get("items") or []
        except Exception:
            return []

    @classmethod
    def _clean_company(cls, company_name: str) -> str:
        return company_name.replace("ООО", "").replace("ПАО", "").replace("АО", "").strip(' "')

    @classmethod
    def _company_in_experience(cls, item: Dict, company_name: str, inn: str = "") -> Optional[Dict]:
        clean = cls._clean_company(company_name).lower()
        tokens = [t for t in re.split(r'[\s"«»\-]+', clean) if len(t) > 2]
        for exp in item.get("experience") or []:
            comp = (exp.get("company") or "").lower()
            if not comp:
                continue
            if inn and inn in comp:
                return exp
            if clean and len(clean) >= 4 and clean[:4] in comp:
                return exp
            if any(t in comp for t in tokens):
                return exp
        return None

    @classmethod
    def _full_name(cls, item: Dict) -> str:
        parts = [
            item.get("last_name") or "",
            item.get("first_name") or "",
            item.get("middle_name") or "",
        ]
        name = " ".join(p for p in parts if p).strip()
        return name

    @classmethod
    def _item_to_candidate(
        cls,
        item: Dict,
        company_name: str,
        inn: str,
        slot_hint: str,
        role_hint: str,
    ) -> Optional[Dict]:
        exp = cls._company_in_experience(item, company_name, inn)
        if not exp:
            return None

        name = cls._full_name(item)
        position = exp.get("position") or item.get("title") or role_hint
        resume_id = item.get("id") or ""
        profile_url = item.get("alternate_url") or f"https://hh.ru/resume/{resume_id}"
        setka = item.get("setka_access_type") or item.get("setka_status")

        conf = 72 if name else 52
        if item.get("can_view_full_info"):
            conf += 5

        return {
            "name": name or "—",
            "role": position[:100],
            "source": f"HH.ru API: резюме (опыт в «{exp.get('company', company_name)[:40]}»)",
            "source_type": "hh_resume_api",
            "confidence_base": conf,
            "profile_url": profile_url,
            "profile_resolved": True,
            "profile_platform": "HH.ru",
            "company_verified": True,
            "stakeholder_hint": slot_hint,
            "resume_id": resume_id,
            "setka_access_type": setka,
            "hh_experience": exp,
        }

    @classmethod
    def discover_candidates_for_company(
        cls,
        company_name: str,
        inn: str = "",
        product_domain: str = "",
        limit: int = 12,
    ) -> List[Dict]:
        """Auth-поиск резюме с фильтром по опыту работы в целевой компании."""
        if not cls.is_configured():
            return []

        status = cls.session_status()
        if not status.get("resume_access"):
            return []

        seen_ids: set = set()
        out: List[Dict] = []

        searches = list(cls.ROLE_SEARCHES)
        if product_domain and "1с" in product_domain.lower():
            searches = [("lvr", "1с")] + list(searches)

        for slot_hint, role_hint in searches:
            for item in cls.search_resumes(company_name, role_hint, per_page=6):
                rid = item.get("id")
                if not rid or rid in seen_ids:
                    continue
                cand = cls._item_to_candidate(item, company_name, inn, slot_hint, role_hint)
                if not cand:
                    continue
                seen_ids.add(rid)
                out.append(cand)
                if len(out) >= limit:
                    return out

        clean = cls._clean_company(company_name)
        if clean and len(out) < limit:
            for item in cls.search_resumes(clean, "директор", per_page=6):
                rid = item.get("id")
                if not rid or rid in seen_ids:
                    continue
                cand = cls._item_to_candidate(item, company_name, inn, "lpr", "директор")
                if not cand:
                    continue
                seen_ids.add(rid)
                out.append(cand)
                if len(out) >= limit:
                    break

        return out
