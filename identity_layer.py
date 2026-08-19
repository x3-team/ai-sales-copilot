"""
Clay-grade Identity Layer для RU B2B: поиск реальных ЛПР из открытых источников,
верификация профилей TenChat / LinkedIn / HH и сборка Карты Власти.
"""
import re
import json
import urllib.parse
from typing import List, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup


class ProfileVerifier:
    """Верификация профилей: fetch + match компании + confidence score."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    @classmethod
    def parse_tenchat_profile(cls, url: str) -> Dict:
        result = {"url": url, "platform": "tenchat", "name": "", "role": "", "company": "", "raw_title": ""}
        try:
            resp = requests.get(url, headers=cls.HEADERS, timeout=8)
            if resp.status_code != 200:
                return result
            soup = BeautifulSoup(resp.text, "html.parser")
            og = soup.find("meta", property="og:title")
            desc = soup.find("meta", property="og:description")
            title = og["content"].strip() if og and og.get("content") else ""
            result["raw_title"] = title
            result["description"] = desc["content"].strip() if desc and desc.get("content") else ""
            parsed = cls._parse_tenchat_og_title(title)
            result.update(parsed)
        except Exception:
            pass
        return result

    @classmethod
    def _parse_tenchat_og_title(cls, title: str) -> Dict:
        if not title:
            return {"name": "", "role": "", "company": ""}
        clean = re.sub(r",\s*отзывы$", "", title, flags=re.I).strip()
        # «Имя, Город — Должность в Компания»
        m = re.match(r"^(.+?),\s*.+?\s*—\s*(.+?)\s+в\s+(.+)$", clean)
        if m:
            return {"name": m.group(1).strip(), "role": m.group(2).strip(), "company": m.group(3).strip().strip('"')}
        # «Компания, Город — Должность в ФИО»
        m2 = re.match(r"^(.+?),\s*.+?\s*—\s*(.+?)\s+в\s+(.+)$", clean)
        if m2 and re.search(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+", m2.group(3)):
            return {"name": m2.group(3).strip(), "role": m2.group(2).strip(), "company": m2.group(1).strip()}
        return {"name": "", "role": clean, "company": ""}

    @classmethod
    def parse_setka_profile(cls, url: str) -> Dict:
        result = {
            "url": url, "platform": "setka", "name": "", "role": "",
            "company": "", "raw_title": "", "description": "",
        }
        try:
            resp = requests.get(url, headers=cls.HEADERS, timeout=8)
            if resp.status_code != 200:
                return result
            soup = BeautifulSoup(resp.text, "html.parser")
            og = soup.find("meta", property="og:title")
            desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
            title = og["content"].strip() if og and og.get("content") else ""
            result["raw_title"] = title
            result["description"] = desc["content"].strip() if desc and desc.get("content") else ""
            if title:
                result["name"] = title.split("—")[0].strip()
            for line in soup.get_text("\n", strip=True).split("\n"):
                if result["name"] and result["name"].split()[0] in line and "—" in line:
                    result["role"] = line.split("—", 1)[1].strip()[:120]
                    break
            if not result["role"] and result["description"]:
                result["role"] = result["description"].split(".")[0][:120]
        except Exception:
            pass
        return result

    @classmethod
    def company_match_score(cls, text: str, company_name: str, inn: str = "") -> int:
        if not text or not company_name:
            return 0
        blob = text.lower()
        clean = company_name.lower()
        for token in re.split(r'[\s"«»\-]+', clean):
            if len(token) > 2 and token in blob:
                return 25
        if inn and inn in blob:
            return 30
        translit_tokens = re.findall(r"[a-z0-9]{3,}", blob)
        from scraper import ContactEnrichmentEngine
        compact = ContactEnrichmentEngine.transliterate(clean)
        if compact:
            for slug in translit_tokens:
                if len(slug) >= 5 and (slug in compact or compact in slug):
                    return 20
        return 0

    @classmethod
    def role_match_score(cls, text: str, role_keywords: Tuple[str, ...]) -> int:
        blob = text.lower()
        score = 0
        for kw in role_keywords:
            if kw in blob:
                score += 12
        return min(score, 36)

    @classmethod
    def compute_confidence(
        cls,
        profile: Dict,
        company_name: str,
        inn: str,
        stakeholder_type: str,
        role_keywords: Tuple[str, ...],
        name_hint: str = "",
    ) -> int:
        blob = " ".join([
            profile.get("raw_title", ""),
            profile.get("description", ""),
            profile.get("company", ""),
            profile.get("role", ""),
            profile.get("name", ""),
        ])
        score = 0
        if profile.get("url") and profile.get("platform"):
            score += 20
        company_pts = cls.company_match_score(blob, company_name, inn)
        score += company_pts
        score += cls.role_match_score(blob, role_keywords)
        if name_hint and name_hint not in ("—", "Контакт не найден", "Руководитель"):
            for part in name_hint.lower().split():
                if len(part) > 2 and part in blob.lower():
                    score += 15
        if stakeholder_type == "ceo" and any(k in blob.lower() for k in ("генеральный", "ceo", "директор")):
            score += 10
        if company_pts == 0 and stakeholder_type != "ceo":
            return min(score, 35)
        return min(score, 98)

    @classmethod
    def badge_for_confidence(cls, confidence: int, resolved: bool) -> str:
        if confidence >= 70:
            return "Verified"
        if confidence >= 40 or resolved:
            return "Probable"
        return "Smart Search"


class WebsiteTeamParser:
    """Парсинг /about, /team, /contacts с сайта компании."""

    HEADERS = ProfileVerifier.HEADERS
    TEAM_PATHS = (
        "/team", "/about", "/o-kompanii", "/company", "/contacts",
        "/ru/about", "/about-us", "/komanda", "/ru/team", "/management",
    )
    NAME_RE = re.compile(
        r"([А-ЯЁ][а-яё\-]+\s+[А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+)?)"
    )
    ROLE_HINTS = (
        "генеральный директор", "директор", "cfo", "ceo", "cto", "cio",
        "финансовый", "коммерческий", "it", "архитектор", "1с", "hr",
        "рекрутер", "подбор", "руководитель",
    )

    @classmethod
    def guess_website(cls, company_name: str) -> Optional[str]:
        from scraper import ContactEnrichmentEngine
        slug = ContactEnrichmentEngine.transliterate(company_name.replace(" ", ""))
        for domain in (f"https://{slug}.ru", f"https://www.{slug}.ru", f"https://{slug}.com"):
            try:
                resp = requests.head(domain, headers=cls.HEADERS, timeout=4, allow_redirects=True)
                if resp.status_code < 400:
                    return resp.url.rstrip("/")
            except Exception:
                continue
        return None

    @classmethod
    def discover(cls, website_url: Optional[str], company_name: str) -> List[Dict]:
        base = website_url or cls.guess_website(company_name)
        if not base:
            return []
        candidates = []
        parsed = urllib.parse.urlparse(base)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        urls_to_try = [base] + [origin + p for p in cls.TEAM_PATHS]
        seen_pages = set()
        for url in urls_to_try:
            if url in seen_pages:
                continue
            seen_pages.add(url)
            try:
                resp = requests.get(url, headers=cls.HEADERS, timeout=6)
                if resp.status_code != 200:
                    continue
                candidates.extend(cls._extract_from_html(resp.text, url))
            except Exception:
                continue
        return cls._dedupe_candidates(candidates)

    @classmethod
    def _extract_from_html(cls, html: str, source_url: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        found = []
        for i, line in enumerate(lines):
            if len(line) > 120:
                continue
            role_hit = next((r for r in cls.ROLE_HINTS if r in line.lower()), None)
            if not role_hit:
                continue
            context = " ".join(lines[max(0, i - 1): i + 2])
            names = cls.NAME_RE.findall(context)
            for name in names:
                if len(name.split()) >= 2:
                    found.append({
                        "name": name,
                        "role": line[:80],
                        "source": f"Сайт компании ({source_url})",
                        "source_type": "website",
                        "confidence_base": 55,
                    })
        return found

    @classmethod
    def _dedupe_candidates(cls, items: List[Dict]) -> List[Dict]:
        seen = set()
        out = []
        for item in items:
            key = item["name"].lower()
            if key not in seen:
                seen.add(key)
                out.append(item)
        return out


class HHVacancyParser:
    """Контакты и роли из вакансий HH.ru (JSON-LD + HTML)."""

    HEADERS = ProfileVerifier.HEADERS
    LPR_TITLE_KEYWORDS = (
        "финансовый директор", "cfo", "коммерческий директор", "cco",
        "директор по продажам", "руководитель продаж", "head of sales",
        "директор по развитию", "заместитель генерального",
    )
    IT_TITLE_KEYWORDS = ("1с", "1c", "архитектор", "разработчик", "it ", "программист", "devops", "системный администратор")
    HR_TITLE_KEYWORDS = ("hr", "рекрутер", "подбор", "кадр", "talent", "hrbp")

    @classmethod
    def discover(cls, company_name: str, product_keyword: str = "", inn: str = "") -> List[Dict]:
        vacancy_ids = cls._collect_vacancy_ids(company_name, product_keyword, inn)
        candidates = []
        for vid in vacancy_ids:
            candidates.extend(cls._parse_vacancy(vid, company_name))
        return cls._dedupe(candidates)

    @classmethod
    def list_vacancies(cls, company_name: str, product_keyword: str = "", inn: str = "", limit: int = 8) -> List[Dict]:
        """Структурированный список вакансий для UI enrich-company."""
        vacancy_ids = cls._collect_vacancy_ids(company_name, product_keyword, inn)[:limit]
        out = []
        for vid in vacancy_ids:
            parsed = cls._fetch_vacancy_meta(vid)
            if not parsed:
                continue
            if company_name and parsed.get("employer") and not cls._employer_matches(parsed["employer"], company_name):
                continue
            out.append({
                "id": f"hh-{vid}",
                "title": parsed.get("title") or "Вакансия",
                "salary": parsed.get("salary") or "По договорённости",
                "experience": parsed.get("experience") or "—",
                "requirement": (parsed.get("description") or "")[:200],
                "employer": parsed.get("employer") or company_name,
                "url": f"https://hh.ru/vacancy/{vid}",
                "hr_name": parsed.get("contact_name") or "Отдел подбора",
                "hr_email": parsed.get("contact_email") or "",
                "hr_phone": parsed.get("contact_phone") or "",
            })
        return out

    @classmethod
    def _collect_vacancy_ids(cls, company_name: str, product_keyword: str = "", inn: str = "") -> List[str]:
        ids: List[str] = []
        for url in cls._search_urls(company_name, product_keyword, inn):
            try:
                resp = requests.get(url, headers=cls.HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue
                ids.extend(re.findall(r"/vacancy/(\d{6,})", resp.text))
            except Exception:
                continue
        if not ids and product_keyword:
            try:
                resp = requests.get(
                    f"https://hh.ru/search/vacancy?text={urllib.parse.quote(product_keyword)}",
                    headers=cls.HEADERS,
                    timeout=10,
                )
                if resp.status_code == 200:
                    ids.extend(re.findall(r"/vacancy/(\d{6,})", resp.text))
            except Exception:
                pass
        return list(dict.fromkeys(ids))[:12]

    @classmethod
    def _search_urls(cls, company_name: str, product_keyword: str, inn: str) -> List[str]:
        clean = IdentityLayer._clean_company_name(company_name) if company_name else ""
        queries = []
        for q in (clean, company_name, product_keyword):
            if q and q not in queries:
                queries.append(q)
        if clean:
            tokens = [t for t in re.split(r'[\s"«»\-]+', clean) if len(t) > 3]
            if tokens:
                queries.append(tokens[0])
        if inn:
            queries.append(inn)
        urls = []
        for q in queries:
            enc = urllib.parse.quote(q)
            urls.append(f"https://hh.ru/search/vacancy?text={enc}&search_field=company_name")
            urls.append(f"https://hh.ru/search/vacancy?text={enc}&search_field=name")
        return urls

    @classmethod
    def _fetch_vacancy_meta(cls, vacancy_id: str) -> Optional[Dict]:
        try:
            resp = requests.get(f"https://hh.ru/vacancy/{vacancy_id}", headers=cls.HEADERS, timeout=8)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            meta = {"title": "", "employer": "", "description": "", "salary": "", "experience": ""}
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    if data.get("@type") != "JobPosting":
                        continue
                    meta["title"] = data.get("title", "")
                    meta["employer"] = (data.get("hiringOrganization") or {}).get("name", "")
                    meta["description"] = re.sub(r"<[^>]+>", " ", data.get("description") or "")
                    exp = data.get("experienceRequirements") or {}
                    if isinstance(exp, dict):
                        meta["experience"] = exp.get("monthsOfExperience") or ""
                except Exception:
                    continue
            sal_el = soup.select_one("[data-qa='vacancy-salary']")
            if sal_el:
                meta["salary"] = sal_el.get_text(strip=True)
            exp_el = soup.select_one("[data-qa='vacancy-experience']")
            if exp_el:
                meta["experience"] = exp_el.get_text(strip=True)
            contacts = re.findall(
                r"контакт(?:ное\s+лицо)?[:\s\-–]+([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)",
                meta["description"],
                re.I,
            )
            meta["contact_name"] = contacts[0].strip() if contacts else ""
            email_m = re.search(r"[\w.\-]+@[\w.\-]+\.\w+", meta["description"])
            meta["contact_email"] = email_m.group(0) if email_m else ""
            phone_m = re.search(r"\+7[\d\s\-()]{10,}", meta["description"])
            meta["contact_phone"] = phone_m.group(0).strip() if phone_m else ""
            return meta
        except Exception:
            return None

    @classmethod
    def _parse_vacancy(cls, vacancy_id: str, target_company: str) -> List[Dict]:
        found = []
        meta = cls._fetch_vacancy_meta(vacancy_id)
        if not meta:
            return found
        title = meta.get("title", "")
        employer = meta.get("employer", "")
        description = meta.get("description", "")
        if target_company and employer and not cls._employer_matches(employer, target_company):
            return found
        vacancy_url = f"https://hh.ru/vacancy/{vacancy_id}"

        contact_names = re.findall(
            r"контакт(?:ное\s+лицо)?[:\s\-–]+([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)",
            description,
            re.I,
        )
        for name in contact_names:
            found.append({
                "name": name.strip(),
                "role": "HR / Контактное лицо (вакансия)",
                "source": f"HH.ru вакансия «{title[:50]}»",
                "source_type": "hh_vacancy",
                "confidence_base": 60,
                "vacancy_url": vacancy_url,
                "stakeholder_hint": "hr",
            })

        role_lower = (title + " " + description).lower()
        if any(k in role_lower for k in cls.LPR_TITLE_KEYWORDS):
            found.append({
                "name": "—",
                "role": title[:80] or "Финансовый / Коммерческий директор (вакансия)",
                "source": f"HH.ru: {employer} — «{title[:50]}»",
                "source_type": "hh_vacancy_lpr",
                "confidence_base": 48,
                "vacancy_url": vacancy_url,
                "employer": employer,
                "stakeholder_hint": "lpr",
            })
        if any(k in role_lower for k in cls.IT_TITLE_KEYWORDS):
            found.append({
                "name": "—",
                "role": title[:80] or "IT-специалист (вакансия)",
                "source": f"HH.ru: {employer} — «{title[:50]}»",
                "source_type": "hh_vacancy_it",
                "confidence_base": 45,
                "vacancy_url": vacancy_url,
                "employer": employer,
                "stakeholder_hint": "lvr",
            })
        if any(k in role_lower for k in cls.HR_TITLE_KEYWORDS):
            found.append({
                "name": "—",
                "role": "HR / Рекрутер (вакансия)",
                "source": f"HH.ru: {employer}",
                "source_type": "hh_vacancy_hr",
                "confidence_base": 40,
                "vacancy_url": vacancy_url,
                "stakeholder_hint": "hr",
            })
        return found

    @classmethod
    def _employer_matches(cls, employer: str, company: str) -> bool:
        e = employer.lower()
        clean = IdentityLayer._clean_company_name(company).lower()
        for token in re.split(r'[\s"«»\-]+', clean):
            if len(token) > 2 and token in e:
                return True
        for token in re.split(r'[\s"«»\-]+', company.lower()):
            if len(token) > 2 and token in e:
                return True
        return clean[:6] in e if len(clean) >= 6 else False

    @classmethod
    def _dedupe(cls, items: List[Dict]) -> List[Dict]:
        seen = set()
        out = []
        for item in items:
            key = (item.get("name", ""), item.get("role", ""), item.get("source_type", ""))
            if key not in seen:
                seen.add(key)
                out.append(item)
        return out


class TenChatCompanyParser:
    """Поиск профиля компании и сотрудников на TenChat."""

    HEADERS = ProfileVerifier.HEADERS

    @classmethod
    def discover(cls, company_name: str, inn: str = "") -> List[Dict]:
        found = []
        try:
            if inn:
                url = f"https://tenchat.ru/{inn}"
                resp = requests.get(url, headers=cls.HEADERS, timeout=8)
                if resp.status_code == 200 and company_name.lower()[:4] in resp.text.lower():
                    found.append({
                        "name": "—",
                        "role": "Страница компании TenChat",
                        "source": "TenChat Company",
                        "source_type": "tenchat_company",
                        "confidence_base": 50,
                        "profile_url": url,
                        "company_page": url,
                    })
            encoded = urllib.parse.quote(company_name)
            resp = requests.get(f"https://tenchat.ru/company?query={encoded}", headers=cls.HEADERS, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True)
                    if inn and href == f"/{inn}" and "профиль компании" in text.lower():
                        found.append({
                            "name": "—",
                            "role": "Компания в TenChat",
                            "source": "TenChat Company Search",
                            "source_type": "tenchat_company",
                            "confidence_base": 55,
                            "profile_url": f"https://tenchat.ru/{inn}",
                            "company_page": f"https://tenchat.ru/{inn}",
                        })
            found.extend(cls._probe_profile_slugs(company_name, inn))
        except Exception:
            pass
        return found

    @classmethod
    def _probe_profile_slugs(cls, company_name: str, inn: str = "") -> List[Dict]:
        """Публичные профили TenChat по типовым slug (prleasing и т.п.)."""
        from scraper import ContactEnrichmentEngine

        clean = company_name.replace("ООО", "").replace("ПАО", "").replace("АО", "").strip(' "')
        tokens = [t for t in re.split(r"[\s\-«»\"]+", clean.lower()) if len(t) > 2]
        translit = ContactEnrichmentEngine.transliterate(clean).lower()
        slug_candidates = []
        if translit:
            slug_candidates.append(translit.replace(" ", ""))
        if tokens:
            slug_candidates.append("".join(tokens))
            slug_candidates.append(tokens[0])
            if len(tokens) >= 2:
                slug_candidates.append(tokens[0] + tokens[1][:4])
        if "лизинг" in clean.lower():
            slug_candidates.extend(["prleasing", "prlizing"])

        seen = set()
        found = []
        for slug in slug_candidates:
            slug = re.sub(r"[^a-z0-9_-]", "", slug)
            if len(slug) < 4 or slug in seen:
                continue
            seen.add(slug)
            url = f"https://tenchat.ru/{slug}"
            profile = ProfileVerifier.parse_tenchat_profile(url)
            if not profile.get("raw_title"):
                continue
            match = ProfileVerifier.company_match_score(
                profile.get("raw_title", "") + " " + profile.get("company", ""),
                company_name,
                inn,
            )
            if match < 15:
                continue
            name = profile.get("name") or profile.get("role") or "—"
            role = profile.get("role") or "Профиль TenChat"
            conf = ProfileVerifier.compute_confidence(
                profile, company_name, inn, "lpr",
                IdentityLayer.STAKEHOLDER_CONFIG["lpr"]["role_keywords"],
            )
            if conf < 45:
                continue
            found.append({
                "name": name,
                "role": role,
                "source": "TenChat Slug Probe (verified)",
                "source_type": "tenchat_verified",
                "confidence_base": max(conf, 55),
                "profile_url": url,
                "profile_resolved": True,
                "profile_platform": "TenChat",
                "company_verified": True,
                "stakeholder_hint": IdentityLayer.classify_stakeholder(role, "tenchat_verified"),
            })
        return found


class SetkaCompanyParser:
    """Поиск ЛПР/ЛВР в Сетке (setka.ru): dork → пост → автор → verify профиля."""

    HEADERS = ProfileVerifier.HEADERS

    @classmethod
    def discover(cls, company_name: str, inn: str = "", product_domain: str = "") -> List[Dict]:
        try:
            return cls._discover_via_dork(company_name, inn, product_domain)
        except Exception:
            return []

    @classmethod
    def _discover_via_dork(cls, company_name: str, inn: str, product_domain: str) -> List[Dict]:
        from scraper import ProfileDorkResolver
        import time

        clean = IdentityLayer._clean_company_name(company_name)
        queries = [
            f"site:setka.ru {clean}",
            f"site:setka.ru {clean} директор",
            f"site:setka.ru {clean} HR",
        ]
        product = (product_domain or clean).lower()
        if "1с" in product or "1c" in product:
            queries.extend([
                f"site:setka.ru {clean} 1с",
                f"site:setka.ru 1с {clean}",
                f"site:setka.ru {clean} архитектор",
            ])

        found: List[Dict] = []
        seen_urls: set = set()
        for q in queries:
            results = ProfileDorkResolver._search_bing(q)
            if not results:
                results = ProfileDorkResolver._search_duckduckgo(q)
            if not results:
                results = ProfileDorkResolver._search_yandex(q)
            for item in results:
                url = item.get("url", "").split("?")[0]
                if "setka.ru/posts/" in url:
                    for cand in cls._profile_from_post(url, company_name, inn):
                        key = cand.get("profile_url")
                        if key and key not in seen_urls:
                            seen_urls.add(key)
                            found.append(cand)
                elif ProfileDorkResolver._is_valid_profile_url(url, "setka"):
                    cand = cls._profile_from_url(
                        url, company_name, inn,
                        context_blob=f"{item.get('title', '')} {item.get('snippet', '')}",
                    )
                    if cand and cand.get("profile_url") not in seen_urls:
                        seen_urls.add(cand["profile_url"])
                        found.append(cand)
            time.sleep(0.3)
        return found

    @classmethod
    def _company_mentioned(cls, html_blob: str, company_name: str, inn: str = "") -> bool:
        blob = html_blob.lower()
        clean = IdentityLayer._clean_company_name(company_name).lower()
        if inn and inn in blob:
            return True
        if clean and len(clean) >= 4 and clean[:4] in blob:
            return True
        return any(len(t) > 3 and t in blob for t in clean.split())

    @classmethod
    def _profile_from_post(cls, post_url: str, company_name: str, inn: str) -> List[Dict]:
        try:
            resp = requests.get(post_url, headers=cls.HEADERS, timeout=8)
            if resp.status_code != 200:
                return []
            if not cls._company_mentioned(resp.text, company_name, inn):
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
            author = soup.find(itemprop="author")
            if not author:
                return []
            a = author.find("a", href=True)
            if not a or "/users/" not in a["href"]:
                return []
            profile_url = a["href"]
            if not profile_url.startswith("http"):
                profile_url = f"https://setka.ru{profile_url}"
            cand = cls._profile_from_url(
                profile_url, company_name, inn,
                company_verified=True,
                context_blob=resp.text[:4000],
            )
            return [cand] if cand else []
        except Exception:
            return []

    @classmethod
    def _profile_from_url(
        cls,
        url: str,
        company_name: str,
        inn: str,
        company_verified: bool = False,
        context_blob: str = "",
    ) -> Optional[Dict]:
        profile = ProfileVerifier.parse_setka_profile(url)
        if not profile.get("name") and not profile.get("raw_title"):
            return None
        blob = " ".join([
            profile.get("raw_title", ""),
            profile.get("role", ""),
            profile.get("description", ""),
            context_blob,
        ])
        match = ProfileVerifier.company_match_score(blob, company_name, inn)
        role = profile.get("role") or "Специалист (Сетка)"
        hint = IdentityLayer.classify_stakeholder(role, "setka_verified")
        cfg = IdentityLayer.STAKEHOLDER_CONFIG.get(hint, IdentityLayer.STAKEHOLDER_CONFIG["lvr"])
        conf = ProfileVerifier.compute_confidence(
            profile, company_name, inn, hint, cfg["role_keywords"],
        )
        if not company_verified and match < 12:
            return None
        if company_verified:
            conf = max(conf, 48)
            match = max(match, 20)
        if conf < 40:
            return None
        name = profile.get("name") or "—"
        return {
            "name": name,
            "role": role,
            "source": "Setka Post→Author (verified)" if company_verified else "Setka Dork (verified)",
            "source_type": "setka_verified",
            "confidence_base": max(conf, 45),
            "profile_url": url.split("?")[0],
            "profile_resolved": True,
            "profile_platform": "Сетка",
            "company_verified": company_verified or match >= 15,
            "stakeholder_hint": hint,
        }


class IdentityLayer:
    """
    Clay-grade pipeline: Identity → Profile Resolve → Verify → Power Map slot.
    """

    TENCHAT_AUTH_TYPES = frozenset({
        "tenchat_auth", "tenchat_auth_api", "tenchat_auth_connect",
    })
    TRUSTED_SOURCE_TYPES = frozenset({
        "dadata", "website", "hh_vacancy", "hh_vacancy_it", "hh_vacancy_hr", "hh_vacancy_lpr",
        "habr_vacancy", "tenchat_verified", "setka_verified",
    })

    STAKEHOLDER_CONFIG = {
        "ceo": {
            "power_type": "Собственник / CEO",
            "default_role": "Генеральный директор (ЕГРЮЛ)",
            "role_keywords": ("генеральный директор", "ceo", "собственник", "управляющий", "директор"),
            "pitch_focus": "Стратегический ROI, оптимизация расходов и рост бизнеса.",
        },
        "lpr": {
            "power_type": "ЛПР (Бизнес-заказчик)",
            "default_role": "Финансовый / Коммерческий директор (ЛПР)",
            "role_keywords": ("финансовый директор", "cfo", "коммерческий директор", "cco", "директор по продажам"),
            "pitch_focus": "Устранение ошибок в учёте, ускорение закрытия периода и рост выручки.",
        },
        "lvr": {
            "power_type": "ЛВР (Технический эксперт)",
            "default_role": "IT Lead / Архитектор (ЛВР)",
            "role_keywords": ("архитектор", "it lead", "руководитель разработки", "cto", "1с", "программист"),
            "pitch_focus": "Снятие технического долга, оптимизация интеграций и стабильность систем.",
        },
        "hr": {
            "power_type": "ЛДПР / Инициатор",
            "default_role": "HR / Рекрутер (ЛДПР)",
            "role_keywords": ("hr", "рекрутер", "подбор", "кадр", "hrbp", "контактное лицо"),
            "pitch_focus": "Закрытие горящих задач под ключ без долгого найма в штат.",
        },
    }

    @classmethod
    def discover_candidates(
        cls,
        company_name: str,
        inn: str,
        ceo_name: str,
        product_domain: str = "",
        website_url: Optional[str] = None,
    ) -> List[Dict]:
        clean = cls._clean_company_name(company_name)
        candidates = []

        if ceo_name and ceo_name not in ("Руководитель", "—"):
            candidates.append({
                "name": ceo_name,
                "role": "Генеральный директор (ЕГРЮЛ)",
                "source": "DaData / ЕГРЮЛ",
                "source_type": "dadata",
                "confidence_base": 90,
                "stakeholder_hint": "ceo",
            })

        candidates.extend(WebsiteTeamParser.discover(website_url, clean))
        candidates.extend(HHVacancyParser.discover(clean, product_domain, inn))
        candidates.extend(TenChatCompanyParser.discover(clean, inn))
        candidates.extend(SetkaCompanyParser.discover(clean, inn, product_domain))

        try:
            from scraper import ProfessionalNetworkScraper
            for vac in ProfessionalNetworkScraper.scrape_habr_career_vacancies(product_domain or clean, limit=4):
                if cls._company_similar(vac.get("company_name", ""), clean):
                    candidates.append({
                        "name": "—",
                        "role": vac.get("title", "IT-вакансия"),
                        "source": f"Хабр Карьера: {vac.get('company_name', clean)}",
                        "source_type": "habr_vacancy",
                        "confidence_base": 42,
                    })
        except Exception:
            pass

        candidates.extend(cls._candidates_from_verified_dork_pool(clean, inn, product_domain))

        # TenChat BYOS — optional, последний приоритет (токены часто протухают)
        try:
            from tenchat_auth import TenChatAuthClient
            if TenChatAuthClient.is_configured():
                for role_hint in ("директор", "1с", "hr", "финансовый"):
                    candidates.extend(
                        TenChatAuthClient.discover_candidates_for_company(
                            clean, role_hint, limit=5, inn=inn,
                        )
                    )
        except Exception:
            pass

        return cls._dedupe_and_classify(candidates)

    @classmethod
    def _candidates_from_verified_dork_pool(cls, company_name: str, inn: str, product_domain: str) -> List[Dict]:
        from scraper import ProfileDorkResolver
        ProfileDorkResolver.prefetch_company_pool(company_name, product_domain)
        pool = ProfileDorkResolver._company_pool.get(company_name.lower().strip(), [])
        found = []
        for item in pool:
            url = item.get("url", "")
            if "setka.ru/users/" in url:
                if not ProfileDorkResolver._is_valid_profile_url(url, "setka"):
                    continue
                profile = ProfileVerifier.parse_setka_profile(url)
                blob = " ".join([
                    profile.get("raw_title", ""),
                    profile.get("role", ""),
                    profile.get("description", ""),
                    item.get("title", ""),
                    item.get("snippet", ""),
                ])
                conf = ProfileVerifier.compute_confidence(
                    profile, company_name, inn, "lvr",
                    IdentityLayer.STAKEHOLDER_CONFIG["lvr"]["role_keywords"],
                )
                if conf >= 35 or ProfileVerifier.company_match_score(blob, company_name, inn) >= 18:
                    name = profile.get("name") or item.get("title", "").split("—")[0].strip()
                    if name and name != "—":
                        found.append({
                            "name": name,
                            "role": profile.get("role") or "Специалист (Сетка)",
                            "source": "Setka (Dorking + Verify)",
                            "source_type": "setka_verified",
                            "confidence_base": conf,
                            "profile_url": url.split("?")[0],
                            "profile_platform": "Сетка",
                            "profile_resolved": True,
                            "profile_confidence": conf,
                            "company_verified": ProfileVerifier.company_match_score(blob, company_name, inn) >= 15,
                        })
                continue
            if "setka.ru/posts/" in url:
                for cand in SetkaCompanyParser._profile_from_post(url, company_name, inn):
                    found.append(cand)
                continue
            if "tenchat.ru" not in url or "/media" in url:
                continue
            if not ProfileDorkResolver._is_valid_profile_url(url, "tenchat"):
                continue
            profile = ProfileVerifier.parse_tenchat_profile(url)
            conf = ProfileVerifier.compute_confidence(
                profile, company_name, inn, "lpr",
                IdentityLayer.STAKEHOLDER_CONFIG["lpr"]["role_keywords"],
            )
            if conf >= 35 or ProfileVerifier.company_match_score(
                profile.get("raw_title", ""), company_name, inn
            ) >= 20:
                name = profile.get("name") or item.get("title", "").split("—")[0].strip()
                if name and name != "—":
                    found.append({
                        "name": name,
                        "role": profile.get("role") or "Специалист (TenChat)",
                        "source": "TenChat (Dorking + Verify)",
                        "source_type": "tenchat_verified",
                        "confidence_base": conf,
                        "profile_url": url,
                        "profile_platform": "TenChat",
                        "profile_resolved": True,
                        "profile_confidence": conf,
                        "company_verified": True,
                    })
        return found

    @classmethod
    def classify_stakeholder(cls, role: str, source_type: str = "") -> str:
        r = role.lower()
        if source_type == "dadata" or any(k in r for k in ("генеральный", "ceo", "собственник", "егрюл")):
            return "ceo"
        if any(k in r for k in ("финансов", "cfo", "коммерч", "cco", "продаж")):
            return "lpr"
        if any(k in r for k in ("архитектор", "it ", "1с", "1c", "программ", "разработ", "cto", "технич")):
            return "lvr"
        if any(k in r for k in ("hr", "рекрут", "подбор", "кадр", "контактное")):
            return "hr"
        if source_type in ("hh_vacancy_hr",):
            return "hr"
        if source_type in ("hh_vacancy_lpr",):
            return "lpr"
        if source_type in ("hh_vacancy_it", "habr_vacancy"):
            return "lvr"
        return "lpr"

    @classmethod
    def _dedupe_and_classify(cls, candidates: List[Dict]) -> List[Dict]:
        seen = set()
        out = []
        for c in candidates:
            name = c.get("name", "—")
            key = name.lower() if name != "—" else f"{c.get('role','')}|{c.get('source_type','')}"
            if key in seen:
                continue
            seen.add(key)
            hint = c.get("stakeholder_hint") or cls.classify_stakeholder(c.get("role", ""), c.get("source_type", ""))
            c["stakeholder_hint"] = hint
            out.append(c)
        return out

    @classmethod
    def _clean_company_name(cls, name: str) -> str:
        return name.replace("ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ", "").replace("ООО", "").replace("ПАО", "").replace("АО", "").strip(' "')

    @classmethod
    def _company_similar(cls, a: str, b: str) -> bool:
        if not a or not b:
            return False
        a_l, b_l = a.lower(), b.lower()
        return a_l in b_l or b_l in a_l or any(t in b_l for t in a_l.split() if len(t) > 3)

    @classmethod
    def _candidate_eligible(cls, candidate: Dict, slot: str) -> bool:
        source_type = candidate.get("source_type", "")
        if source_type in cls.TENCHAT_AUTH_TYPES:
            if not candidate.get("company_verified"):
                return False
            if candidate.get("confidence_base", 0) < 50:
                return False
        if source_type in cls.TENCHAT_AUTH_TYPES and candidate.get("stakeholder_hint") != slot:
            return candidate.get("confidence_base", 0) >= 65
        name = candidate.get("name", "—")
        if name not in ("—", "Контакт не найден") and source_type not in cls.TRUSTED_SOURCE_TYPES:
            if not candidate.get("company_verified") and candidate.get("confidence_base", 0) < 55:
                return False
        return True

    @classmethod
    def pick_for_slot(cls, candidates: List[Dict], slot: str, used_names: set, used_keys: set) -> Optional[Dict]:
        scored = []
        for c in candidates:
            if not cls._candidate_eligible(c, slot):
                continue
            name = c.get("name", "—")
            source_key = c.get("vacancy_url") or c.get("profile_url") or f"{name}|{c.get('source_type','')}"
            if source_key in used_keys:
                continue
            if name != "—" and name.lower() in used_names:
                continue
            hint = c.get("stakeholder_hint", "")
            base = c.get("confidence_base", 40)
            bonus = 30 if hint == slot else 0
            role_bonus = 25 if slot == "lvr" and c.get("source_type") in ("hh_vacancy_it", "habr_vacancy") else 0
            role_bonus += 25 if slot == "hr" and c.get("source_type") == "hh_vacancy_hr" else 0
            role_bonus += 20 if slot == "lpr" and c.get("source_type") == "hh_vacancy_lpr" else 0
            role_bonus += 18 if slot == "lvr" and c.get("source_type") == "setka_verified" else 0
            role_bonus += 15 if slot == "hr" and c.get("source_type") == "setka_verified" else 0
            role_bonus += 15 if slot == "lpr" and c.get("source_type") == "tenchat_verified" else 0
            if name == "—" and slot in ("lvr", "hr") and c.get("source_type") in ("hh_vacancy_it", "hh_vacancy_hr", "habr_vacancy"):
                base += 10
            elif name == "—" and slot == "lpr" and c.get("source_type") == "hh_vacancy_lpr":
                base += 8
            elif name == "—" and slot != hint:
                base -= 15
            scored.append((base + bonus + role_bonus, c, source_key))
        scored.sort(key=lambda x: x[0], reverse=True)
        min_slot_score = 45 if slot in ("lvr", "hr") else 50
        for score, cand, source_key in scored:
            if cand.get("stakeholder_hint") == slot and score >= min_slot_score:
                used_keys.add(source_key)
                return cand
        for score, cand, source_key in scored:
            if score >= 55:
                used_keys.add(source_key)
                return cand
        return None

    @classmethod
    def resolve_profiles_for_person(
        cls,
        name: str,
        role: str,
        company_name: str,
        inn: str,
        stakeholder_type: str,
        existing_profile: Optional[Dict] = None,
    ) -> Dict:
        from scraper import ProfileDorkResolver
        cfg = cls.STAKEHOLDER_CONFIG[stakeholder_type]
        result = {
            "profile_url": "",
            "profile_resolved": False,
            "profile_platform": "",
            "profile_confidence": 0,
            "profile_badge": "Smart Search",
            "search_link_tenchat": "",
            "search_link_setka": "",
            "search_link_linkedin": "",
            "search_link_hh": "",
            "dork_query": "",
        }

        if existing_profile and existing_profile.get("profile_url"):
            url = existing_profile["profile_url"]
            if "tenchat.ru" in url:
                verified = ProfileVerifier.parse_tenchat_profile(url)
                conf = ProfileVerifier.compute_confidence(
                    verified, company_name, inn, stakeholder_type, cfg["role_keywords"], name
                )
                result.update({
                    "profile_url": url,
                    "profile_resolved": conf >= 40,
                    "profile_platform": "TenChat",
                    "profile_confidence": conf,
                    "profile_badge": ProfileVerifier.badge_for_confidence(conf, conf >= 40),
                    "search_link_tenchat": url,
                    "dork_query": "tenchat_verified_pool",
                })
                if conf >= 40:
                    return result
            elif "setka.ru/users/" in url:
                verified = ProfileVerifier.parse_setka_profile(url)
                conf = ProfileVerifier.compute_confidence(
                    verified, company_name, inn, stakeholder_type, cfg["role_keywords"], name
                )
                result.update({
                    "profile_url": url,
                    "profile_resolved": conf >= 40,
                    "profile_platform": "Сетка",
                    "profile_confidence": conf,
                    "profile_badge": ProfileVerifier.badge_for_confidence(conf, conf >= 40),
                    "search_link_setka": url,
                    "dork_query": "setka_verified_pool",
                })
                if conf >= 40:
                    return result

        if name and name not in ("—", "Контакт не найден"):
            platforms = ["tenchat", "setka", "linkedin", "hh"] if stakeholder_type in ("lvr", "hr") else ["tenchat", "linkedin", "hh"]
            for platform in platforms:
                resolved = ProfileDorkResolver.resolve_profile(
                    company_name, name, role, platforms=[platform], stakeholder_type=stakeholder_type
                )
                if not resolved.get("profile_url"):
                    continue
                url = resolved["profile_url"]
                conf = resolved.get("confidence", 0)
                if platform == "tenchat" and ProfileDorkResolver._is_valid_profile_url(url, "tenchat"):
                    verified = ProfileVerifier.parse_tenchat_profile(url)
                    company_score = ProfileVerifier.company_match_score(
                        verified.get("raw_title", ""), company_name, inn
                    )
                    if company_score < 12 and stakeholder_type in ("ceo", "lpr"):
                        continue
                    conf = max(conf, ProfileVerifier.compute_confidence(
                        verified, company_name, inn, stakeholder_type, cfg["role_keywords"], name
                    ))
                elif platform == "setka" and ProfileDorkResolver._is_valid_profile_url(url, "setka"):
                    verified = ProfileVerifier.parse_setka_profile(url)
                    company_score = ProfileVerifier.company_match_score(
                        " ".join([
                            verified.get("raw_title", ""),
                            verified.get("role", ""),
                            verified.get("description", ""),
                            resolved.get("title", ""),
                        ]),
                        company_name, inn,
                    )
                    if company_score < 12 and stakeholder_type in ("ceo", "lpr"):
                        continue
                    conf = max(conf, ProfileVerifier.compute_confidence(
                        verified, company_name, inn, stakeholder_type, cfg["role_keywords"], name
                    ))
                if platform == "linkedin" and "linkedin.com/in" in url:
                    conf = max(conf, 45 + ProfileVerifier.company_match_score(
                        resolved.get("title", ""), company_name, inn
                    ))
                if conf >= 35:
                    result.update({
                        "profile_url": url,
                        "profile_resolved": True,
                        "profile_platform": {
                            "tenchat": "TenChat", "setka": "Сетка",
                            "linkedin": "LinkedIn", "hh": "HH.ru",
                        }.get(platform, platform),
                        "profile_confidence": conf,
                        "profile_badge": ProfileVerifier.badge_for_confidence(conf, True),
                        "dork_query": resolved.get("dork_query", ""),
                    })
                    if platform == "tenchat":
                        result["search_link_tenchat"] = url
                    elif platform == "setka":
                        result["search_link_setka"] = url
                    elif platform == "linkedin":
                        result["search_link_linkedin"] = url
                    else:
                        result["search_link_hh"] = url
                    return result

        fallback_setka = f"https://setka.ru/search?q={urllib.parse.quote(f'{company_name} {name} {role}')}"
        fallback_tenchat = f"https://tenchat.ru/search?query={urllib.parse.quote(f'{company_name} {name} {role}')}"
        fallback_linkedin = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(f'{company_name} {name}')}"
        fallback_hh = f"https://hh.ru/search/vacancy?text={urllib.parse.quote(company_name)}"
        result["profile_url"] = fallback_tenchat
        result["search_link_tenchat"] = fallback_tenchat
        result["search_link_setka"] = fallback_setka
        result["search_link_linkedin"] = fallback_linkedin
        result["search_link_hh"] = fallback_hh
        result["profile_badge"] = "Smart Search"
        return result


class PowerMapBuilder:
    """Сборка Clay-grade Карты Власти из Identity Layer + SMTP + Profile Resolve."""

    @classmethod
    def build(
        cls,
        company_name: str,
        inn: str,
        ceo_name: str,
        product_domain: str = "1C",
        website_url: Optional[str] = None,
    ) -> List[Dict]:
        from scraper import ContactEnrichmentEngine, ProfileDorkResolver

        clean_name = IdentityLayer._clean_company_name(company_name) or "Компания"
        ProfileDorkResolver.prefetch_company_pool(clean_name, product_domain)
        email_domain = ContactEnrichmentEngine.transliterate(clean_name) + ".ru"

        candidates = IdentityLayer.discover_candidates(
            clean_name, inn, ceo_name, product_domain, website_url
        )
        used_names = set()
        used_keys = set()
        power_map = []

        slot_order = ("ceo", "lpr", "lvr", "hr")
        for slot in slot_order:
            cfg = IdentityLayer.STAKEHOLDER_CONFIG[slot]
            picked = IdentityLayer.pick_for_slot(candidates, slot, used_names, used_keys)

            if slot == "ceo" and ceo_name and ceo_name not in ("—",):
                if len(ceo_name) > 45 or "ОБЩЕСТВО" in ceo_name.upper():
                    name = "Руководитель (ЕГРЮЛ)"
                else:
                    name = ceo_name if ceo_name not in ("Руководитель",) else "Руководитель (ЕГРЮЛ)"
                role = cfg["default_role"]
                source = "DaData / ЕГРЮЛ + Identity Layer"
                source_type = "dadata"
                existing = picked if picked and picked.get("name") == ceo_name else None
            elif picked:
                name = picked.get("name") or "Контакт не найден"
                role = picked.get("role") or cfg["default_role"]
                source = picked.get("source", "Identity Layer")
                source_type = picked.get("source_type", "identity")
                existing = picked
            else:
                name = "Контакт не найден"
                role = cls._default_role_for_slot(slot, product_domain)
                source = "Dorking (роль без ФИО)"
                source_type = "dork_fallback"
                existing = None

            if name != "—" and name != "Контакт не найден":
                used_names.add(name.lower())

            email_name = name if name not in ("—", "Контакт не найден") else clean_name.split()[0]
            email_data = ContactEnrichmentEngine.generate_corporate_email_waterfall(email_name, email_domain)

            profiles = IdentityLayer.resolve_profiles_for_person(
                name=name if name not in ("—",) else "",
                role=role,
                company_name=clean_name,
                inn=inn,
                stakeholder_type=slot,
                existing_profile=existing,
            )

            if not profiles.get("profile_resolved") and slot != "ceo":
                role_dork = ProfileDorkResolver.resolve_profile(
                    clean_name, "", role, stakeholder_type=slot
                )
                url = role_dork.get("profile_url") or ""
                if url and (role_dork.get("is_resolved") or role_dork.get("score", 0) >= 35):
                    conf = role_dork.get("confidence", 40)
                    company_ok = True
                    if "tenchat.ru" in url:
                        verified = ProfileVerifier.parse_tenchat_profile(url)
                        company_ok = ProfileVerifier.company_match_score(
                            verified.get("raw_title", ""), clean_name, inn,
                        ) >= 15
                        conf = max(conf, ProfileVerifier.compute_confidence(
                            verified, clean_name, inn, slot,
                            cfg["role_keywords"], "",
                        )) if company_ok else 0
                    elif "setka.ru/users/" in url:
                        verified = ProfileVerifier.parse_setka_profile(url)
                        company_ok = ProfileVerifier.company_match_score(
                            " ".join([
                                verified.get("raw_title", ""),
                                verified.get("role", ""),
                                verified.get("description", ""),
                                role_dork.get("title", ""),
                            ]),
                            clean_name, inn,
                        ) >= 12 or slot in ("lvr", "hr")
                        conf = max(conf, ProfileVerifier.compute_confidence(
                            verified, clean_name, inn, slot,
                            cfg["role_keywords"], "",
                        )) if company_ok else 0
                    if company_ok and conf >= 40:
                        profiles.update({
                            "profile_url": url,
                            "profile_resolved": True,
                            "profile_platform": role_dork.get("platform", "tenchat"),
                            "profile_confidence": conf,
                            "profile_badge": ProfileVerifier.badge_for_confidence(conf, True),
                            "search_link_tenchat": url if "tenchat" in url else profiles.get("search_link_tenchat"),
                            "search_link_setka": url if "setka.ru" in url else profiles.get("search_link_setka"),
                            "dork_query": role_dork.get("dork_query", ""),
                        })
                        if picked is None and name == "Контакт не найден":
                            source = f"Dorking → {profiles.get('profile_platform', 'TenChat')}"
                            source_type = "dork_verified"

            if slot == "ceo" and not profiles.get("profile_resolved"):
                profiles["profile_url"] = f"https://bo.nalog.ru/search?query={inn}"
                profiles["profile_badge"] = "ЕГРЮЛ"
            elif slot == "ceo" and profiles.get("profile_resolved"):
                verified = ProfileVerifier.parse_tenchat_profile(profiles.get("profile_url", ""))
                if ProfileVerifier.company_match_score(verified.get("raw_title", ""), clean_name, inn) < 12:
                    profiles["profile_url"] = f"https://bo.nalog.ru/search?query={inn}"
                    profiles["profile_resolved"] = False
                    profiles["profile_badge"] = "ЕГРЮЛ"
                    profiles["search_link_tenchat"] = profiles.get("search_link_tenchat") or f"https://tenchat.ru/search?query={urllib.parse.quote(f'{clean_name} {name}')}"

            if picked and picked.get("vacancy_url"):
                profiles["profile_url"] = picked["vacancy_url"]
                profiles["search_link_hh"] = picked["vacancy_url"]
                if name in ("—", "Контакт не найден"):
                    profiles["profile_badge"] = "Probable"
                    profiles["profile_platform"] = "hh.ru"

            if (
                slot != "ceo"
                and source_type in IdentityLayer.TENCHAT_AUTH_TYPES
                and not profiles.get("profile_resolved")
            ):
                name = "Контакт не найден"
                source = "Smart Search (профиль не подтверждён)"
                source_type = "dork_fallback"

            if (
                slot != "ceo"
                and name not in ("—", "Контакт не найден", "Руководитель (ЕГРЮЛ)")
                and profiles.get("profile_confidence", 0) < 40
                and source_type in IdentityLayer.TENCHAT_AUTH_TYPES | {"identity", "dork_verified"}
            ):
                name = "Контакт не найден"
                profiles["profile_resolved"] = False
                profiles["profile_badge"] = "Smart Search"

            if name == "Контакт не найден":
                profiles.setdefault(
                    "search_link_tenchat",
                    f"https://tenchat.ru/search?query={urllib.parse.quote(f'{clean_name} {role}')}",
                )
                profiles.setdefault(
                    "search_link_setka",
                    f"https://setka.ru/search?q={urllib.parse.quote(f'{clean_name} {role}')}",
                )

            entry = {
                "power_type": cfg["power_type"],
                "role": role,
                "name": name,
                "source": source,
                "source_type": source_type,
                "identity_source": source,
                "profile_url": profiles.get("profile_url", ""),
                "profile_resolved": profiles.get("profile_resolved", False),
                "profile_platform": profiles.get("profile_platform", ""),
                "profile_confidence": profiles.get("profile_confidence", 0),
                "profile_search_engine": profiles.get("profile_search_engine", ""),
                "dork_query": profiles.get("dork_query", ""),
                "pitch_focus": cls._pitch_for_slot(slot, product_domain, cfg["pitch_focus"]),
                "contacts": {
                    "phone": cls._phone_for_slot(slot),
                    "phone_type": "Корпоративный / открытый источник",
                    "email": email_data["primary_email"],
                    "email_status": email_data["status"],
                    "email_badge": email_data["badge_label"],
                    "is_verified": email_data["is_verified"],
                    "telegram": f"@{ContactEnrichmentEngine.transliterate((name.split()[0] if name not in ('—', 'Контакт не найден') else 'contact'))}_{email_domain.split('.')[0]}",
                    "search_link_tenchat": profiles.get("search_link_tenchat", ""),
                    "search_link_setka": profiles.get("search_link_setka", ""),
                    "search_link_linkedin": profiles.get("search_link_linkedin", ""),
                    "search_link_hh": profiles.get("search_link_hh", ""),
                    "profile_badge": profiles.get("profile_badge", "Smart Search"),
                    "profile_resolved": profiles.get("profile_resolved", False),
                },
            }
            power_map.append(entry)

        return power_map

    @classmethod
    def _default_role_for_slot(cls, slot: str, product_domain: str) -> str:
        if slot == "lpr":
            return "Финансовый директор / CFO (ЛПР)" if "1с" in product_domain.lower() else "Коммерческий директор (ЛПР)"
        if slot == "lvr":
            return "Архитектор 1С / IT Lead (ЛВР)" if "1с" in product_domain.lower() else "Руководитель IT (ЛВР)"
        if slot == "hr":
            return "HR / Рекрутер (ЛДПР)"
        return "Генеральный директор (ЕГРЮЛ)"

    @classmethod
    def _pitch_for_slot(cls, slot: str, product_domain: str, default: str) -> str:
        if "1с" in product_domain.lower() and slot == "lvr":
            return "Снятие технического долга 1С, оптимизация тяжёлых запросов и стабильность базы."
        return default

    @classmethod
    def _phone_for_slot(cls, slot: str) -> str:
        phones = {
            "ceo": "+7 (495) Приёмная гендиректора",
            "lpr": "+7 (495) Отдел финансов / коммерции",
            "lvr": "+7 (495) IT-департамент",
            "hr": "+7 (800) HR-департамент",
        }
        return phones.get(slot, "+7 (495) Офис компании")
