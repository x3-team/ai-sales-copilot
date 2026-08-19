"""
TenChat authenticated session для MVP (бесплатно, без официального API).

TenChat хранит OAuth-токены в cookies TCAF (access) и TCRF (refresh), но API
ожидает заголовок Authorization: Bearer <access>. Cookies часто HttpOnly —
в DevTools → Application их может не быть, тогда берите Bearer из Network.

Env (любой из вариантов):
  TENCHAT_ACCESS_TOKEN + TENCHAT_REFRESH_TOKEN
  TENCHAT_COOKIE=TCAF=...; TCRF=...
  TENCHAT_BEARER=...  (только access, для read-only поиска)
"""
import os
import re
import urllib.parse
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup


class TenChatAuthClient:
    BASE_URL = "https://tenchat.ru"
    API_PREFIX = "/gostinder/api/web/auth"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://tenchat.ru",
        "Referer": "https://tenchat.ru/connect",
    }

    _session: Optional[requests.Session] = None

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls._get_access_token())

    @classmethod
    def _get_access_token(cls) -> str:
        bearer = os.environ.get("TENCHAT_BEARER", "").strip()
        if bearer:
            return bearer.removeprefix("Bearer ").strip()
        token = os.environ.get("TENCHAT_ACCESS_TOKEN", "").strip() or cls._parse_cookie_value("TCAF")
        return token.removeprefix("Bearer ").strip()

    @classmethod
    def _get_refresh_token(cls) -> str:
        return os.environ.get("TENCHAT_REFRESH_TOKEN", "").strip() or cls._parse_cookie_value("TCRF")

    @classmethod
    def _parse_cookie_value(cls, name: str) -> str:
        raw = os.environ.get("TENCHAT_COOKIE", "").strip()
        if not raw:
            return ""
        for part in raw.split(";"):
            part = part.strip()
            if part.startswith(f"{name}="):
                return part.split("=", 1)[1].strip()
        return ""

    @classmethod
    def _auth_headers(cls, extra: Optional[Dict] = None) -> Dict:
        headers = {**cls.HEADERS, **(extra or {})}
        access = cls._get_access_token()
        if access:
            headers["Authorization"] = f"Bearer {access}"
        return headers

    @classmethod
    def _get_session(cls) -> requests.Session:
        if cls._session is None:
            cls._session = requests.Session()
            cls._session.headers.update(cls.HEADERS)
        access = cls._get_access_token()
        refresh = cls._get_refresh_token()
        if access:
            cls._session.cookies.set("TCAF", access, domain="tenchat.ru")
            cls._session.headers["Authorization"] = f"Bearer {access}"
        if refresh:
            cls._session.cookies.set("TCRF", refresh, domain="tenchat.ru")
        return cls._session

    @classmethod
    def session_status(cls) -> Dict:
        """Проверка: cookies заданы и сессия живая."""
        if not cls.is_configured():
            return {
                "configured": False,
                "authenticated": False,
                "message": (
                    "Задайте TENCHAT_BEARER или TENCHAT_ACCESS_TOKEN "
                    "(DevTools → Network → любой запрос к tenchat.ru → Authorization: Bearer ...)"
                ),
            }
        try:
            resp = cls._get_session().get(
                f"{cls.BASE_URL}{cls.API_PREFIX}/account/work-status",
                headers=cls._auth_headers({"Accept": "application/json"}),
                timeout=8,
            )
            if resp.status_code == 200:
                return {
                    "configured": True,
                    "authenticated": True,
                    "message": "Сессия TenChat активна",
                    "work_status": resp.json() if resp.text else {},
                }
            if resp.status_code == 401:
                return {
                    "configured": True,
                    "authenticated": False,
                    "message": (
                        "Токен недействителен. DevTools → Network → Fetch/XHR → "
                        "work-status или username → скопируйте Authorization: Bearer ..."
                    ),
                }
            return {
                "configured": True,
                "authenticated": False,
                "message": f"TenChat API вернул HTTP {resp.status_code}",
            }
        except Exception as exc:
            return {
                "configured": True,
                "authenticated": False,
                "message": f"Ошибка проверки сессии: {exc}",
            }

    @classmethod
    def search_people(cls, query: str, limit: int = 15) -> List[Dict]:
        """
        Поиск людей через авторизованную сессию.
        1) POST search/elastic (если доступен)
        2) Fallback: парсинг /connect?query=
        """
        if not cls.is_configured():
            return []

        results = cls._search_via_api(query, limit)
        if results:
            return results
        return cls._search_via_connect_page(query, limit)

    @classmethod
    def _search_via_api(cls, query: str, limit: int) -> List[Dict]:
        session = cls._get_session()
        endpoints = [
            (f"{cls.API_PREFIX}/account/v2/search/elastic", {"phrase": query, "page": 0, "size": limit}),
            (f"{cls.API_PREFIX}/account/search/elastic", {"phrase": query, "page": 0, "size": limit}),
            (f"{cls.API_PREFIX}/account/search/elastic", {"searchText": query, "pageNumber": 0, "pageSize": limit}),
            (f"{cls.API_PREFIX}/account/search", {"query": query}),
            (f"{cls.API_PREFIX}/account/search/default", {}),
        ]
        headers = cls._auth_headers({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        for path, body in endpoints:
            try:
                resp = session.post(f"{cls.BASE_URL}{path}", json=body, headers=headers, timeout=10)
                if resp.status_code != 200 or not resp.text:
                    continue
                data = resp.json()
                parsed = cls._parse_api_results(data)
                if parsed:
                    return parsed[:limit]
            except Exception:
                continue
        return []

    @classmethod
    def _parse_api_results(cls, data) -> List[Dict]:
        items = []
        if isinstance(data, dict):
            for key in ("content", "items", "accounts", "users", "data", "results"):
                if isinstance(data.get(key), list):
                    items = data[key]
                    break
            if not items and isinstance(data.get("payload"), dict):
                for key in ("content", "items", "accounts"):
                    if isinstance(data["payload"].get(key), list):
                        items = data["payload"][key]
                        break
        elif isinstance(data, list):
            items = data

        results = []
        for item in items:
            if not isinstance(item, dict):
                continue
            username = item.get("username") or item.get("userName") or item.get("login") or ""
            name = item.get("fullName") or item.get("name") or item.get("fio") or ""
            role = item.get("positionName") or item.get("position") or item.get("positionTitle") or ""
            company = item.get("companyName") or item.get("company") or ""
            if isinstance(role, dict):
                role = role.get("name") or role.get("positionName") or ""
            if not username and not name:
                continue
            profile_url = f"{cls.BASE_URL}/{username}" if username else ""
            results.append({
                "name": name or username,
                "role": role,
                "company": company,
                "username": username,
                "profile_url": profile_url,
                "source": "TenChat API (auth)",
                "source_type": "tenchat_auth_api",
            })
        return results

    @classmethod
    def _search_via_connect_page(cls, query: str, limit: int) -> List[Dict]:
        session = cls._get_session()
        try:
            resp = session.get(
                f"{cls.BASE_URL}/connect?query={urllib.parse.quote(query)}",
                headers={**cls.HEADERS, "Accept": "text/html"},
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            return cls._parse_connect_html(resp.text, limit)
        except Exception:
            return []

    @classmethod
    def _parse_connect_html(cls, html: str, limit: int) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        skip = {
            "/feed", "/connect", "/vacancy", "/partners", "/plus", "/business",
            "/resume", "/company", "/docs", "/contacts", "/wallet", "/media", "/auth",
        }
        results = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not re.match(r"^/[a-zA-Z0-9_-]{2,40}$", href) or href in skip:
                continue
            slug = href[1:]
            if slug in seen:
                continue
            text = a.get_text(strip=True)
            if not text or len(text) < 3 or text.isdigit():
                continue
            if "профиль компании" in text.lower():
                continue
            seen.add(slug)
            results.append({
                "name": text,
                "role": "",
                "company": "",
                "username": slug,
                "profile_url": f"{cls.BASE_URL}/{slug}",
                "source": "TenChat Connect (auth)",
                "source_type": "tenchat_auth_connect",
            })
            if len(results) >= limit:
                break
        return results

    @classmethod
    def discover_candidates_for_company(
        cls,
        company_name: str,
        role_hint: str = "директор",
        limit: int = 10,
    ) -> List[Dict]:
        """Несколько auth-поисков под компанию + роль."""
        if not cls.is_configured():
            return []
        queries = [
            f"{company_name} {role_hint}",
            company_name,
            f"{company_name} 1с",
            role_hint,
        ]
        seen = set()
        out = []
        for q in queries:
            for person in cls.search_people(q, limit=limit):
                key = person.get("profile_url") or person.get("username")
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "name": person.get("name") or "—",
                    "role": person.get("role") or role_hint,
                    "source": person.get("source", "TenChat Auth"),
                    "source_type": person.get("source_type", "tenchat_auth"),
                    "confidence_base": 65,
                    "profile_url": person.get("profile_url"),
                    "profile_resolved": True,
                    "profile_platform": "TenChat",
                    "company_hint": person.get("company", ""),
                })
            if len(out) >= limit:
                break
        return out[:limit]
