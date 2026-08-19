import os
import json
import re
import csv
import io
import time
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query, Body, Response, Header, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from scraper import ProfessionalNetworkScraper, ProfileDorkResolver, ContactEnrichmentEngine

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import demo_mode
import lpr_webhook
import memory_store
import company_status

app = FastAPI(title="Sales Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DADATA_API_KEY = os.environ.get("DADATA_API_KEY", "")
DADATA_SECRET_KEY = os.environ.get("DADATA_SECRET_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# --------------------------------------------------------------------------
# 0. GEMINI 3.5/3.6 FLASH LLM ENGINE (Умная генерация B2B-питчей)
# --------------------------------------------------------------------------

def call_gemini_llm(prompt: str, fallback_text: str) -> str:
    """
    Вызов Gemini Flash API для генерации естественных, пробивных питчей.
    При сбое или превышении таймаута безопасно возвращает подготовленный fallback.
    """
    if not GEMINI_API_KEY:
        return fallback_text
    
    models = ["gemini-2.0-flash", "gemini-1.5-flash"]
    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 280
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                if text:
                    return text
        except Exception:
            continue
            
    return fallback_text


# --------------------------------------------------------------------------
# 1. COMPANY PRODUCT PROFILE & WEBSITE ANALYZER
# --------------------------------------------------------------------------

class SellerProductProfile(BaseModel):
    product_name: str = "1С: внедрение и сопровождение"
    product_description: str = "Автоматизация учёта, доработка конфигураций 1С и проектная поддержка для B2B"
    target_icp: str = "Средний и крупный B2B-бизнес с отделом учёта и IT"
    value_proposition: str = "Сокращаем срок закрытия периода, снимаем техдолг 1С и закрываем проектные задачи под ключ без долгого найма"

class WebsiteAnalyzeRequest(BaseModel):
    url: str

current_seller_profile = SellerProductProfile()

@app.get("/api/seller/profile")
def get_seller_profile():
    return current_seller_profile

@app.post("/api/seller/profile")
def update_seller_profile(profile: SellerProductProfile):
    global current_seller_profile
    current_seller_profile = profile
    return {"status": "success", "profile": current_seller_profile}

@app.post("/api/seller/analyze-website")
def analyze_website(req: WebsiteAnalyzeRequest):
    """
    Анализирует сайт продавца (быстрый HTML/Meta Parser) и формирует понимание продукта.
    """
    url = req.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta_desc = ""
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if meta_desc_tag and meta_desc_tag.get('content'):
            meta_desc = meta_desc_tag['content'].strip()

        h1 = soup.find('h1')
        h1_text = h1.get_text(strip=True) if h1 else ""
        body_text = soup.get_text()
        
        site_content = (title + " " + meta_desc + " " + h1_text + " " + body_text[:1200]).lower()

        if "1с" in site_content or "1c" in site_content:
            p_name = "Внедрение и доработка 1С:ERP / 1С:УТ"
            p_desc = "Комплексная автоматизация учета, устранение сбоев и доработка конфигураций 1С под ключ."
            p_icp = "Торговые, производственные и логистические компании с штатом от 20 человек"
            p_val = "Устраняем зависания и ошибки склада в 1С, ускоряем документооборот на 40% без долгих поисков штатных программистов."
            search_query = "1С"
        elif "crm" in site_content or "битрикс" in site_content or "amo" in site_content:
            p_name = "Интеграция CRM (amoCRM / Битрикс24)"
            p_desc = "Настройка воронок, авто-контроль сделок и сквозная аналитика для отдела продаж."
            p_icp = "B2B компании со штатом менеджеров по продажам от 3 человек"
            p_val = "Исключаем потерю лидов менеджерами и увеличиваем конверсию в оплату на 25-35%."
            search_query = "CRM"
        elif "логистик" in site_content or "груз" in site_content or "доставк" in site_content:
            p_name = "Транспортная логистика и грузоперевозки B2B"
            p_desc = "Экспресс-доставка, сборные грузы и экспедирование по РФ и СНГ."
            p_icp = "Дистрибьюторы, ритейлеры и производства с регулярными отгрузками"
            p_val = "Сокращаем издержки на логистику до 20% и гарантируем соблюдение сроков доставки с финансовой ответственностью."
            search_query = "Логистика"
        else:
            p_name = title[:45] if title else "B2B Продукт компании"
            p_desc = meta_desc[:120] if meta_desc else (h1_text if h1_text else "Профессиональные решения для бизнеса")
            p_icp = "B2B компании среднего и крупного бизнеса"
            p_val = "Оптимизация ключевых операционных процессов и повышение прибыльности компании."
            search_query = title[:20] if title else "B2B Services"

        detected_profile = SellerProductProfile(
            product_name=p_name,
            product_description=p_desc,
            target_icp=p_icp,
            value_proposition=p_val
        )

        global current_seller_profile
        current_seller_profile = detected_profile

        return {
            "status": "success",
            "url": url,
            "detected_profile": detected_profile,
            "suggested_prospecting_query": search_query
        }

    except Exception as e:
        domain = url.split("//")[-1].split("/")[0]
        fallback_profile = SellerProductProfile(
            product_name=f"Решения для бизнеса ({domain})",
            product_description="Автоматизация и развитие B2B клиентов",
            target_icp="Средний и крупный коммерческий бизнес",
            value_proposition="Повышение эффективности процессов и рост конверсии B2B продаж"
        )
        current_seller_profile = fallback_profile
        return {
            "status": "warning",
            "message": f"Сайт обработан по домену: {e}",
            "detected_profile": fallback_profile,
            "suggested_prospecting_query": "1С"
        }

# --------------------------------------------------------------------------
# 2. REAL DADATA INTEGRATION
# --------------------------------------------------------------------------

@app.get("/api/dadata/company")
def search_company(query: str = Query(..., description="ИНН, ОГРН или название компании")):
    if not DADATA_API_KEY:
        raise HTTPException(status_code=500, detail="DADATA_API_KEY не установлен")
    
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {DADATA_API_KEY}"
    }
    payload = {"query": query}
    
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    if response.status_code != 200 or not response.json().get("suggestions"):
        url_suggest = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"
        response = requests.post(url_suggest, json=payload, headers=headers, timeout=10)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Ошибка при запросе к DaData")
    
    return response.json()

# --------------------------------------------------------------------------
# 3. LPR & PROSPECTING DYNAMIC ENGINE
# --------------------------------------------------------------------------

STATIC_PROSPECT_DATABASE = [
    {
        "inn": "7707083893",
        "company_name": "ПАО СБЕРБАНК",
        "employee_count": 280000,
        "revenue": "1.2 Трлн руб.",
        "hiring_triggers": ["Разработка AI / LLM", "Менеджеры по B2B продажам"],
        "match_reason": "Открыто 15+ вакансий в коммерческий и IT блоки. Активная цифровизация.",
        "query_keywords": ["ai", "crm", "1с", "продажи", "b2b"]
    },
    {
        "inn": "7702070139",
        "company_name": "ООО ЯНДЕКС",
        "employee_count": 20000,
        "revenue": "600 Млрд руб.",
        "hiring_triggers": ["B2B Sales Manager", "Разработчики облачных сервисов"],
        "match_reason": "Масштабирование направления Яндекс 360 для бизнеса.",
        "query_keywords": ["crm", "облака", "b2b", "продажи"]
    },
    {
        "inn": "7710353606",
        "company_name": "АО Т-БАНК",
        "employee_count": 35000,
        "revenue": "350 Млрд руб.",
        "hiring_triggers": ["Руководитель отдела продаж", "1C Программист"],
        "match_reason": "Ищут специалистов по 1С и руководителей коммерческих воронок.",
        "query_keywords": ["1с", "crm", "руководитель продаж", "b2b"]
    },
    {
        "inn": "7709257050",
        "company_name": "ООО 1С-СОФТ",
        "employee_count": 1500,
        "revenue": "85 Млрд руб.",
        "hiring_triggers": ["Консультант 1С:ERP", "Менеджер по работе с партнерами"],
        "match_reason": "Прямое совпадение с экосистемой корпоративного софта 1С.",
        "query_keywords": ["1с", "erp", "бухгалтерия", "учет"]
    },
    {
        "inn": "7709440038",
        "company_name": "ООО МЕГАПОЛИС ЛОГИСТИКА",
        "employee_count": 450,
        "revenue": "4.2 Млрд руб.",
        "hiring_triggers": ["Программист 1С:УТ", "Логист по B2B грузоперевозкам"],
        "match_reason": "Крупный дистрибьютор, переходящий на новую версию 1С и внедряющий CRM.",
        "query_keywords": ["1с", "логистика", "склад", "транспорт", "crm"]
    }
]

def generate_dynamic_lprs(
    inn: str,
    company_name: str,
    ceo_from_dadata: str,
    trigger_info: str = "",
    website_url: str = None,
    stored_lprs: Optional[List[dict]] = None,
):
    from live_companies import skip_social_discovery

    clean_name = company_name.replace('ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ', '').replace('ООО', '').replace('ПАО', '').replace('АО', '').strip(' "')
    if not clean_name:
        clean_name = "Компания"

    prefilled = memory_store.lprs_by_slot(stored_lprs or [])
    missing = memory_store.slots_needing_search(stored_lprs or [])
    if skip_social_discovery(inn):
        if stored_lprs:
            power_map = list(stored_lprs)
        else:
            only_slots = ("ceo",)
            power_map = ProfessionalNetworkScraper.search_and_enrich_power_map_for_company(
                clean_name, inn, ceo_from_dadata,
                product_domain=current_seller_profile.product_name,
                website_url=website_url,
                only_slots=only_slots,
                prefilled_by_slot=None,
            )
    elif stored_lprs and not missing:
        power_map = list(stored_lprs)
    else:
        only_slots = tuple(missing) if missing else None
        skip_prefilled = {k: v for k, v in prefilled.items() if k not in (missing or [])}
        power_map = ProfessionalNetworkScraper.search_and_enrich_power_map_for_company(
            clean_name, inn, ceo_from_dadata,
            product_domain=current_seller_profile.product_name,
            website_url=website_url,
            only_slots=only_slots,
            prefilled_by_slot=skip_prefilled if only_slots else None,
        )
        if stored_lprs:
            power_map = memory_store.merge_lpr_lists(stored_lprs, power_map)

    email_domain = ContactEnrichmentEngine.resolve_email_domain(website_url, clean_name)

    p_name = current_seller_profile.product_name
    p_val = current_seller_profile.value_proposition

    for idx, person in enumerate(power_map):
        role = person["role"]
        name = person["name"]
        power_type = person["power_type"]
        greet = name if name not in ("—", "Контакт не найден", "Руководитель") else "коллега"

        fallbacks = [
            f"Здравствуйте, {greet}! Обратил внимание на масштабирование «{clean_name}». "
            f"Предлагаем «{p_name}» ({p_val}). Готовы показать результат на 10-минутной встрече?",
            f"Здравствуйте, {greet}! Изучили задачи «{clean_name}». Предлагаем «{p_name}» ({p_val}). "
            f"Когда удобно провести 10-минутное демо?",
            f"Приветствую, {greet}! Вижу задачи по 1С в «{clean_name}». "
            f"Снимаем техдолг и поддерживаем 1С:ERP под ключ. Созвонимся на 10 минут?",
            f"Здравствуйте, {greet}! Видим потребность в специалистах 1С в «{clean_name}». "
            f"Закрываем проектные задачи под ключ без долгого найма. Обсудим детали?",
        ]
        prompts = [
            None,
            f"Напиши персональный B2B-питч (3 ёмких предложения) для первого контакта в Telegram с {greet} "
            f"({role}, тип влияния: {power_type}) компании «{clean_name}». Продукт: «{p_name}». "
            f"Ценность: {p_val}. Триггер: {trigger_info}.",
            f"Напиши B2B-питч (3 предложения) для IT / 1С-лида {greet} ({role}) компании «{clean_name}». "
            f"Продукт: «{p_name}». Фокус: техдолг и стабильность 1С.",
            f"Напиши B2B-питч (3 предложения) для HR {greet} ({role}) компании «{clean_name}». "
            f"Продукт: «{p_name}». Фокус: закрытие задач без долгого найма.",
        ]
        fb = fallbacks[min(idx, len(fallbacks) - 1)]
        pr = prompts[min(idx, len(prompts) - 1)]
        person["custom_pitch"] = call_gemini_llm(pr, fb) if pr else fb

    return power_map

def generate_dynamic_hh_vacancies(inn: str, company_name: str, product_keyword: str = ""):
    from identity_layer import HHVacancyParser
    kw = product_keyword or current_seller_profile.product_name or "1С"
    vacancies = HHVacancyParser.list_vacancies(company_name, kw, inn=inn, limit=8)
    if vacancies:
        return vacancies
    return []

# --------------------------------------------------------------------------
# 4. AUTO-PROSPECTING & EXPORT ENGINE
# --------------------------------------------------------------------------

@app.get("/api/copilot/auto-prospect")
def auto_prospect_clients(product_keyword: str = Query("1С", description="Ключевое слово или продукт")):
    kw = product_keyword.lower().strip()
    
    # 1. Живой сбор сигналов спроса через открытый скрейпер Хабр Карьеры
    live_vacancies = ProfessionalNetworkScraper.scrape_habr_career_vacancies(product_keyword, limit=5)
    
    matched = []
    
    # Если найдены живые вакансии — формируем профили компаний
    for vac in live_vacancies:
        c_name = vac["company_name"]
        if not c_name or any(m["company_name"] == c_name for m in matched):
            continue
            
        matched.append({
            "inn": "770" + str(abs(hash(c_name)))[:7],
            "company_name": c_name,
            "employee_count": 250,
            "revenue": "От 500 млн руб.",
            "hiring_triggers": [vac["title"], f"Стек: {vac['skills']}"],
            "match_reason": f"Открытая вакансия «{vac['title']}» ({vac['salary']}). Активный наем специалистов.",
            "query_keywords": [kw]
        })
    
    # 2. Дополняем эталонными проверенными компаниями
    for item in STATIC_PROSPECT_DATABASE:
        if (any(kw in key for key in item["query_keywords"]) or kw in item["company_name"].lower()) and not any(m["company_name"] == item["company_name"] for m in matched):
            matched.append(item)
            
    if not matched:
        matched = STATIC_PROSPECT_DATABASE[:4]

    prospects = []
    for comp in matched[:6]:
        lprs = generate_dynamic_lprs(comp["inn"], comp["company_name"], "Руководитель", comp["match_reason"])
        prospects.append({
            "company_info": comp,
            "target_lprs": lprs,
            "ai_pitch_preview": lprs[1]["custom_pitch"] if len(lprs) > 1 else lprs[0]["custom_pitch"]
        })

    return {
        "search_query": product_keyword,
        "active_seller_product": current_seller_profile.product_name,
        "found_count": len(prospects),
        "live_signals_source": "Identity Layer: DaData + HH + Habr + сайт + TenChat/Setka verify (BYOS optional)",
        "prospects": prospects
    }

@app.get("/api/copilot/export-csv")
def export_prospects_csv(product_keyword: str = Query("1С")):
    """
    Экспорт найденных целевых компаний и ЛПР в CSV файл для отдела продаж.
    """
    res = auto_prospect_clients(product_keyword)
    prospects = res.get("prospects", [])

    output = io.StringIO()
    # Запись UTF-8 BOM для корректного открытия в русском Excel
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    
    writer.writerow(["Компания", "ИНН", "Штат (чел)", "Выручка", "Триггеры потребности", "Стейкхолдер (Имя)", "Тип Влияния", "Должность", "Источник Identity", "Телефон / Отдел", "Корпоративный Email", "SMTP Статус", "Профиль (URL)", "Confidence", "Профиль найден", "Telegram", "Персональный AI-Питч"])

    for p in prospects:
        comp = p["company_info"]
        triggers_str = ", ".join(comp.get("hiring_triggers", []))
        for l in p["target_lprs"]:
            c = l["contacts"]
            profile_url = l.get("profile_url") or c.get("search_link_tenchat", "")
            profile_found = "Да" if l.get("profile_resolved") or c.get("profile_resolved") else "Нет"
            display_name = l["name"] if l["name"] not in ("—", "Контакт не найден") else l["role"]
            writer.writerow([
                comp["company_name"],
                comp["inn"],
                comp["employee_count"],
                comp["revenue"],
                triggers_str,
                display_name,
                l.get("power_type", "ЛПР"),
                l["role"],
                l.get("identity_source", l.get("source", "")),
                c.get("phone", ""),
                c.get("email", ""),
                c.get("email_status", "Не проверен"),
                profile_url,
                l.get("profile_confidence", 0),
                profile_found,
                c.get("telegram", ""),
                l["custom_pitch"]
            ])

    output.seek(0)
    import urllib.parse
    safe_filename = urllib.parse.quote(f"leads_{product_keyword}.csv")
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8')]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{safe_filename}"}
    )

# --------------------------------------------------------------------------
# 5. SINGLE COMPANY ENRICHMENT API
# --------------------------------------------------------------------------

def _extract_website_from_dadata(data: dict) -> str:
    sites = data.get("sites") or []
    if sites:
        first = sites[0]
        if isinstance(first, str) and first.startswith("http"):
            return first.rstrip("/")
        if isinstance(first, dict):
            url = first.get("value") or first.get("url") or ""
            if url.startswith("http"):
                return url.rstrip("/")
    return ""


@app.get("/api/copilot/sources-status")
def copilot_sources_status():
    """Статус интеграций: core (без cookies) + optional BYOS (TenChat, HH Employer)."""
    from tenchat_auth import TenChatAuthClient
    from hh_auth import HHAuthClient
    tenchat = TenChatAuthClient.session_status()
    hh = HHAuthClient.session_status()
    optional_full = tenchat.get("authenticated") or hh.get("resume_access")
    return {
        "mvp_mode": "full" if optional_full else "core_without_byos",
        "core": {
            "dadata": {
                "available": bool(DADATA_API_KEY),
                "label": "DaData / ЕГРЮЛ",
                "detail": "ИНН, CEO, адрес" if DADATA_API_KEY else "DADATA_API_KEY не задан",
            },
            "hh": {
                "available": True,
                "label": "HH.ru",
                "detail": "HTML-парсинг вакансий и ролей",
            },
            "habr": {
                "available": True,
                "label": "Хабр Карьера",
                "detail": "Сигналы IT-найма",
            },
            "website": {
                "available": True,
                "label": "Сайт компании",
                "detail": "/team, /about, /contacts",
            },
            "tenchat_public": {
                "available": True,
                "label": "TenChat (публичный)",
                "detail": "Slug probe + verify без cookies",
            },
            "setka_public": {
                "available": True,
                "label": "Сетка (публичный)",
                "detail": "Dork → пост → автор /users/{uuid} + verify",
            },
        },
        "optional": {
            "hh_employer": {
                "configured": hh.get("configured", False),
                "authenticated": hh.get("authenticated", False),
                "resume_access": hh.get("resume_access", False),
                "label": "HH Employer API",
                "message": hh.get("message", ""),
                "setup": (
                    "1. Зарегистрируйте приложение на https://dev.hh.ru/admin\n"
                    "2. OAuth token работодателя с доступом к базе резюме (платно)\n"
                    "3. .env: HH_ACCESS_TOKEN=... и HH_USER_AGENT=AI-Sales-Copilot/1.0 (email@domain.com)"
                ),
            },
            "tenchat_auth": {
                "configured": tenchat.get("configured", False),
                "authenticated": tenchat.get("authenticated", False),
                "label": "TenChat BYOS",
                "message": tenchat.get("message", ""),
                "setup": (
                    "Локально: создайте .env с TENCHAT_ACCESS_TOKEN=... "
                    "(DevTools → Network → Authorization: Bearer ...). "
                    "Обновляйте ~раз в 2 недели. MVP работает и без этого."
                ),
            },
            "lpr_webhook": {
                "configured": lpr_webhook.is_configured(),
                "hmac_configured": lpr_webhook.hmac_configured(),
                "store": lpr_webhook.store_info(),
                "submit_url_set": bool(os.environ.get("LPR_AGENT_SUBMIT_URL")),
                "label": "LPR Agent (webhook)",
                "message": (
                    "POST /api/copilot/lpr-jobs → webhook_url + HMAC auth для Soprano"
                    if lpr_webhook.is_configured() and lpr_webhook.hmac_configured()
                    else "Задайте WEBHOOK_BASE_URL (https) и WEBHOOK_HMAC_SECRET на Render"
                ),
            },
            "memory": {
                "configured": memory_store.is_configured(),
                "store": memory_store.store_info(),
                "label": "Persistent memory (Postgres/SQLite)",
                "message": (
                    "DATABASE_URL задан — компании/люди/контакты сохраняются между рестартами"
                    if memory_store.db_backend() == "postgres"
                    else "Локальный SQLite fallback — задайте DATABASE_URL на Render для Postgres"
                ),
            },
        },
    }


@app.get("/api/copilot/hh-status")
def hh_session_status():
    """Проверка HH Employer OAuth (без вывода токена)."""
    from hh_auth import HHAuthClient
    return HHAuthClient.session_status()


@app.get("/api/copilot/tenchat-status")
def tenchat_session_status():
    """Проверка авторизованной сессии TenChat (без вывода токенов)."""
    from tenchat_auth import TenChatAuthClient
    return TenChatAuthClient.session_status()


@app.get("/api/copilot/discover-identity")
def discover_identity(
    company: str = Query(..., description="Название компании"),
    inn: str = Query("", description="ИНН"),
    ceo_name: str = Query("", description="CEO из DaData"),
    product_domain: str = Query("1С", description="Продукт продавца"),
):
    """Clay-grade Identity Layer: поиск реальных кандидатов ЛПР из открытых источников."""
    from identity_layer import IdentityLayer
    candidates = IdentityLayer.discover_candidates(company, inn, ceo_name, product_domain)
    return {"company": company, "candidates_count": len(candidates), "candidates": candidates}


@app.get("/api/copilot/resolve-profile")
def resolve_lpr_profile(
    company: str = Query(..., description="Название компании"),
    name: str = Query("", description="ФИО или имя ЛПР"),
    role: str = Query("директор", description="Должность"),
    stakeholder_type: str = Query("lpr", description="ceo | lpr | lvr | hr"),
):
    """
    Backend Google Dorking: находит прямой URL профиля ЛПР на TenChat/LinkedIn/Сетке.
    """
    result = ProfileDorkResolver.resolve_profile(
        company=company,
        name=name,
        role=role,
        stakeholder_type=stakeholder_type,
    )
    return {
        "company": company,
        "name": name,
        "role": role,
        **result,
    }

class CRMDealRequest(BaseModel):
    company_name: str
    inn: str
    ceo_name: str
    pitch: str
    lead_score: int
    selected_lpr: Optional[str] = None


class LprJobCreateRequest(BaseModel):
    prompt: Optional[str] = None
    inn: str = ""
    company_name: str = ""
    platforms: Optional[List[str]] = None
    metadata: Optional[dict] = None
    auto_submit: bool = True


@app.on_event("startup")
def startup_memory_schema():
    try:
        memory_store.ensure_schema()
    except Exception:
        pass
    try:
        import lpr_job_store

        lpr_job_store.init_db()
    except Exception:
        pass


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "memory": memory_store.store_info(),
    }


@app.post("/api/copilot/lpr-jobs")
def create_lpr_job(body: LprJobCreateRequest):
    """
    Создаёт задачу для внешнего LPR-агента.
    Отдаёт webhook_url + prompt — их передаёте провайдеру.
    Провайдер вызывает callback с result_url или contacts inline.
    """
    if not lpr_webhook.is_configured():
        raise HTTPException(
            status_code=503,
            detail="WEBHOOK_BASE_URL не задан — укажите публичный HTTPS URL сервиса на Render",
        )
    if not lpr_webhook.hmac_configured():
        raise HTTPException(
            status_code=503,
            detail="WEBHOOK_HMAC_SECRET не задан — сгенерируйте секрет в Render env",
        )
    prompt = body.prompt or lpr_webhook.default_prompt(
        body.company_name or "Компания",
        body.inn or "—",
        current_seller_profile.product_name or "1С",
    )
    try:
        return lpr_webhook.create_job(
            prompt=prompt,
            inn=body.inn,
            company_name=body.company_name,
            platforms=body.platforms,
            metadata=body.metadata,
            auto_submit=body.auto_submit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/copilot/lpr-jobs/{job_id}")
def get_lpr_job(job_id: str):
    try:
        return lpr_webhook.get_job_public(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/webhooks/lpr/inbound/{job_id}")
async def lpr_inbound_webhook(
    job_id: str,
    request: Request,
    x_webhook_timestamp: Optional[str] = Header(None, alias="X-Webhook-Timestamp"),
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
):
    """Callback от Soprano: contacts только в JSON body, auth через HMAC."""
    forwarded = request.headers.get("x-forwarded-proto") or request.url.scheme
    if not lpr_webhook.verify_https_inbound(forwarded):
        raise HTTPException(status_code=403, detail="HTTPS required")

    try:
        lpr_webhook.validate_job_id(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    body = await request.body()
    ok, err = lpr_webhook.verify_inbound_hmac(x_webhook_timestamp, x_webhook_signature, body)
    if not ok:
        raise HTTPException(status_code=401, detail=err)

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")

    try:
        return lpr_webhook.handle_inbound_webhook(job_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/webhooks/lpr/inbound")
async def lpr_inbound_webhook_legacy():
    """Устаревший endpoint с job_id в query — отключён."""
    raise HTTPException(
        status_code=410,
        detail="Используйте POST /api/webhooks/lpr/inbound/{job_id} с HMAC-заголовками",
    )


@app.post("/api/copilot/lpr-jobs/{job_id}/apply-to-enrich")
def apply_lpr_job_to_enrich(job_id: str, inn: str = Query(..., description="ИНН компании в кэше enrich")):
    """Подмешивает готовых кандидатов из webhook-job в persistent memory по ИНН."""
    try:
        job = lpr_webhook.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail=f"Job status: {job.get('status')}")

    candidates = job.get("candidates") or []
    if not candidates:
        raise HTTPException(status_code=422, detail="Job completed but candidates empty")

    memory_store.upsert_from_inbound(inn, job.get("company_name") or "", candidates)

    cached = memory_store.get_enrich_payload(inn)
    if not cached:
        raise HTTPException(status_code=404, detail="Enrich memory miss — сначала запустите enrich по этому ИНН")

    extra = lpr_webhook.candidates_to_lpr_entries(candidates)
    merged = dict(cached)
    lprs = list((merged.get("lpr_matrix") or {}).get("lprs") or [])
    seen_urls = {p.get("profile_url") for p in lprs if p.get("profile_url")}
    for entry in extra:
        url = entry.get("profile_url")
        if url and url in seen_urls:
            continue
        lprs.append(entry)
        if url:
            seen_urls.add(url)

    merged["lpr_matrix"] = {"total_lprs": len(lprs), "lprs": lprs}
    merged["lpr_webhook_applied"] = {"job_id": job_id, "added": len(extra)}
    memory_store.save_enrich_payload(inn, merged)
    return merged


@app.get("/api/copilot/memory/companies/{inn}")
def memory_get_company(inn: str):
    """Чтение сохранённой компании и power map из persistent memory."""
    row = memory_store.get_company(inn)
    if not row:
        raise HTTPException(status_code=404, detail="Company not in memory")
    st = row.get("card_status") or company_status.STATUS_SIGNAL
    return {
        "company": row,
        "company_card": company_status.card_status_payload(
            st, triggers=row.get("triggers") or []
        ),
        "people": memory_store.list_people(inn),
        "power_map": memory_store.get_power_map(inn),
    }


@app.get("/api/copilot/company-queue")
def copilot_company_queue(
    queue: str = Query(
        "in_work",
        description="reachable — можно касаться; in_work — сигнал и есть имя",
    ),
    limit: int = Query(50, ge=1, le=200),
):
    q = (queue or "in_work").strip().lower()
    if q not in (company_status.QUEUE_REACHABLE, company_status.QUEUE_IN_WORK):
        raise HTTPException(
            status_code=400,
            detail="queue must be reachable or in_work",
        )
    items = memory_store.list_companies(queue=q, limit=limit)
    return {
        "queue": q,
        "queue_label": "Можно касаться" if q == company_status.QUEUE_REACHABLE else "В работе",
        "count": len(items),
        "companies": items,
    }


@app.get("/api/copilot/memory/people")
def memory_list_people(inn: str = Query(..., description="ИНН компании")):
    people = memory_store.list_people(inn)
    if not people:
        raise HTTPException(status_code=404, detail="No people in memory for this INN")
    return {"inn": inn, "count": len(people), "people": people}


@app.get("/api/copilot/memory/contacts")
def memory_list_contacts(person_id: int = Query(..., description="ID person из memory")):
    contacts = memory_store.list_contacts(person_id)
    return {"person_id": person_id, "count": len(contacts), "contacts": contacts}

@app.get("/api/copilot/demo-companies")
def copilot_demo_companies():
    """Рекомендованные компании для живого демо."""
    return {"demo_mode": demo_mode.is_demo_mode(), "companies": demo_mode.demo_company_chips()}


@app.get("/api/copilot/resolve-query")
def copilot_resolve_query(q: str = Query(..., description="ИНН, сайт или название")):
    try:
        inn = demo_mode.resolve_company_query(q, lambda query: search_company(query=query))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"query": q, "inn": inn}


@app.get("/api/copilot/enrich-company")
def enrich_company_profile(
    inn: str = Query("", description="ИНН компании (legacy)"),
    query: str = Query("", description="ИНН, сайт или название компании"),
    refresh: bool = Query(False, description="Пропустить кэш"),
):
    raw = (query or inn).strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Укажите ИНН, сайт или название компании")

    try:
        resolved_inn = demo_mode.resolve_company_query(
            raw, lambda q: search_company(query=q)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not refresh:
        cached = memory_store.get_enrich_payload(resolved_inn)
        if cached:
            cached = dict(cached)
            cached["cache_hit"] = True
            cached["memory_hit"] = True
            missing = memory_store.slots_needing_search(
                (cached.get("lpr_matrix") or {}).get("lprs") or []
            )
            cached["slots_needing_search"] = missing
            if not missing:
                return cached

    stored_lprs = None
    if not refresh:
        stored_row = memory_store.get_enrich_payload(resolved_inn)
        if stored_row:
            stored_lprs = (stored_row.get("lpr_matrix") or {}).get("lprs") or []

    dadata_res = search_company(query=resolved_inn)
    
    if not dadata_res.get("suggestions"):
        raise HTTPException(status_code=404, detail="Компания не найдена в базе DaData")
    
    item = dadata_res["suggestions"][0]
    data = item.get("data", {})
    value = item.get("value", "Неизвестная компания")
    
    finance = data.get("finance") or {}
    management = data.get("management") or {}
    address = data.get("address") or {}
    state = data.get("state") or {}
    website_url = _extract_website_from_dadata(data)
    
    ceo_name = management.get("name") if isinstance(management, dict) else "Руководитель"
    if not ceo_name:
        ceo_name = "Управляющий директор"
        
    company_info = {
        "inn": data.get("inn") or resolved_inn,
        "kpp": data.get("kpp") or "-",
        "ogrn": data.get("ogrn") or "-",
        "name": value,
        "full_name": data.get("name", {}).get("full_with_opf") if isinstance(data.get("name"), dict) else value,
        "ceo": ceo_name,
        "address": address.get("value") if isinstance(address, dict) else "Не указан",
        "status": state.get("status") if isinstance(state, dict) else "ACTIVE",
        "employee_count": data.get("employee_count"),
        "revenue": finance.get("revenue") if isinstance(finance, dict) else None,
        "website": website_url or None,
    }
    
    product_kw = current_seller_profile.product_name or "1С"
    vacancies = generate_dynamic_hh_vacancies(company_info["inn"], company_info["name"], product_kw)
    for vac in vacancies:
        try:
            memory_store.upsert_from_hh_vacancy(
                company_info["inn"],
                company_info["name"],
                vac,
            )
        except Exception:
            pass
    lpr_list = generate_dynamic_lprs(
        company_info["inn"],
        company_info["name"],
        company_info["ceo"],
        f"Вакансии: {len(vacancies)} на hh.ru",
        website_url=website_url or None,
        stored_lprs=stored_lprs,
    )
    
    score = 75
    pain_points = []
    
    if company_info.get("employee_count"):
        emp = company_info["employee_count"]
        if emp > 500:
            score += 15
            pain_points.append(f"Крупный штат ({emp} сотрудников) — высокая нагрузка на коммуникации.")
        elif emp > 50:
            score += 10
            pain_points.append(f"Средний бизнес ({emp} сотрудников) — этап активного масштабирования.")
            
    if len(vacancies) > 0:
        score += 10
        pain_points.append(f"Найдено {len(vacancies)} реальных вакансий на hh.ru — компания активно расширяется.")
        
    pain_points.append(f"Сформирована карта из {len(lpr_list)} стейкхолдеров (Identity Layer: DaData + HH + сайт + TenChat verify).")

    from tenchat_auth import TenChatAuthClient
    from hh_auth import HHAuthClient
    tc_ok = TenChatAuthClient.is_configured() and TenChatAuthClient.session_status().get("authenticated")
    hh_ok = HHAuthClient.is_configured() and HHAuthClient.session_status().get("resume_access")
    sources_note = (
        "TenChat BYOS + HH Employer API активны — расширенный поиск ЛПР."
        if tc_ok and hh_ok
        else "TenChat BYOS активен — расширенный поиск TenChat."
        if tc_ok
        else "HH Employer API активен — поиск резюме по опыту в компании."
        if hh_ok
        else "Core-режим: DaData, HH вакансии, сайт, TenChat/Setka public verify."
    )

    result = {
        "seller_product_profile": current_seller_profile,
        "dadata_legal_profile": company_info,
        "sources_status_note": sources_note,
        "demo_mode": False,
        "cache_hit": False,
        "memory_hit": False,
        "query_resolved": {"input": raw, "inn": resolved_inn},
        "lpr_matrix": {
            "total_lprs": len(lpr_list),
            "lprs": lpr_list
        },
        "hh_recruitment_profile": {
            "open_vacancies_count": len(vacancies),
            "vacancies": vacancies
        },
        "sales_ai_insights": {
            "lead_score": min(score, 98),
            "insights": pain_points,
            "next_steps": [
                f"1. Выбрать целевого ЛПР (Коммерческий директор / CCO)",
                f"2. Отправить персональный питч в Telegram или на Email",
                "3. Назначить 15-минутную онлайн-демонстрацию решения"
            ]
        }
    }

    if lpr_webhook.is_configured() and os.environ.get("LPR_WEBHOOK_AUTO", "0") == "1":
        try:
            job = lpr_webhook.create_job(
                prompt=lpr_webhook.default_prompt(company_info["name"], company_info["inn"], product_kw),
                inn=company_info["inn"],
                company_name=company_info["name"],
                metadata={"source": "enrich-company"},
                auto_submit=True,
            )
            result["lpr_job"] = {
                "job_id": job["job_id"],
                "status": job["status"],
                "webhook_url": job["webhook_url"],
                "poll_url": f"/api/copilot/lpr-jobs/{job['job_id']}",
            }
        except ValueError:
            pass

    try:
        result["company_card"] = company_status.compute_from_enrich_payload(result)
        memory_store.save_enrich_payload(resolved_inn, result)
        row = memory_store.get_company(resolved_inn)
        if row:
            result["company_card"] = company_status.card_status_payload(
                row.get("card_status") or result["company_card"]["status"],
                triggers=row.get("triggers") or result["company_card"].get("triggers"),
            )
    except Exception:
        result.setdefault(
            "company_card",
            company_status.compute_from_enrich_payload(result),
        )
    return result

@app.post("/api/crm/create-deal")
def create_crm_deal(deal: CRMDealRequest):
    return {
        "status": "success",
        "deal_id": f"DEAL-2026-{os.urandom(2).hex().upper()}",
        "message": f"Сделка по компании «{deal.company_name}» с адресатом '{deal.selected_lpr or deal.ceo_name}' успешно создана в CRM.",
        "assigned_copilot": "Включен авто-контроль касаний"
    }

# --------------------------------------------------------------------------
# 6. FRONTEND: LANDING, WORKSPACE, LEGAL PAGES
# --------------------------------------------------------------------------

BRAND_NAME = "Sales Copilot"
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

_INCLUDE_RE = re.compile(r"<!--\s*include:\s*([\w./-]+)\s*-->")


def render_template(relative_path: str, **context) -> str:
    """Читает шаблон, подставляет партиалы `<!-- include: x.html -->` и плейсхолдеры."""
    path = os.path.join(TEMPLATES_DIR, relative_path)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Страница не найдена")

    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    def _inject(match: "re.Match") -> str:
        partial = os.path.join(TEMPLATES_DIR, "partials", match.group(1))
        if not os.path.exists(partial):
            return ""
        with open(partial, "r", encoding="utf-8") as pf:
            return pf.read()

    html = _INCLUDE_RE.sub(_inject, html)
    html = html.replace("{{BRAND}}", BRAND_NAME)
    for key, value in context.items():
        html = html.replace("{{" + key + "}}", str(value))
    return html


LEGAL_PAGES = {
    "privacy":       ("Политика конфиденциальности", "19 августа 2026"),
    "terms":         ("Условия использования", "19 августа 2026"),
    "personal-data": ("Обработка персональных данных", "19 августа 2026"),
    "offer":         ("Публичная оферта", "19 августа 2026"),
    "cookies":       ("Файлы cookie", "19 августа 2026"),
    "security":      ("Безопасность", "19 августа 2026"),
    "sources":       ("Источники данных", "19 августа 2026"),
    "contacts":      ("Контакты", "19 августа 2026"),
}


def render_legal(slug: str) -> str:
    title, updated = LEGAL_PAGES[slug]
    content = render_template(os.path.join("legal", f"{slug}.html"))
    return render_template("legal_base.html", TITLE=title, UPDATED=updated, CONTENT=content)


@app.get("/", response_class=HTMLResponse)
def get_landing_page():
    """Промо-лендинг: карта власти компании и проверенные контакты ЛПР."""
    return render_template("landing.html")


@app.get("/app", response_class=HTMLResponse)
def get_workspace_ui():
    """Рабочий кабинет: пошаговый прогон агента по компании."""
    return render_template("app.html")


@app.get("/privacy", response_class=HTMLResponse)
def page_privacy():
    return render_legal("privacy")


@app.get("/terms", response_class=HTMLResponse)
def page_terms():
    return render_legal("terms")


@app.get("/personal-data", response_class=HTMLResponse)
def page_personal_data():
    return render_legal("personal-data")


@app.get("/offer", response_class=HTMLResponse)
def page_offer():
    return render_legal("offer")


@app.get("/cookies", response_class=HTMLResponse)
def page_cookies():
    return render_legal("cookies")


@app.get("/security", response_class=HTMLResponse)
def page_security():
    return render_legal("security")


@app.get("/sources", response_class=HTMLResponse)
def page_sources():
    return render_legal("sources")


@app.get("/contacts", response_class=HTMLResponse)
def page_contacts():
    return render_legal("contacts")

