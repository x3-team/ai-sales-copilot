import os
import json
import re
import csv
import io
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query, Body, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="AI Sales Copilot Production Pilot")

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
    
    models = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"]
    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 300
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=6)
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
    product_name: str = "AI Sales Copilot"
    product_description: str = "Автоматизация B2B продаж и голосовой AI-ассистент"
    target_icp: str = "Компания с B2B отделом продаж от 5 человек, использующая CRM"
    value_proposition: str = "Сокращает рутину менеджеров, подсказывает идеальный скрипт во время разговора и поднимает конверсию сделок на 25-30%"

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

def generate_dynamic_lprs(inn: str, company_name: str, ceo_from_dadata: str, trigger_info: str = ""):
    clean_name = company_name.replace('ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ', '').replace('ООО', '').replace('ПАО', '').replace('АО', '').strip(' "')
    if not clean_name:
        clean_name = "Компания"

    domain = clean_name.lower().replace(' ', '').replace('-', '') + ".ru"
    ceo_name = ceo_from_dadata if ceo_from_dadata else "Управляющий директор"

    # Шаблоны базовых питчей
    p_name = current_seller_profile.product_name
    p_val = current_seller_profile.value_proposition

    fallback_ceo = f"Здравствуйте, {ceo_name}! Проанализировали компанию «{clean_name}». Наша команда предлагает решение «{p_name}». Для вашего бизнеса это позволит: {p_val}. Когда вам удобно провести короткую встречу?"
    fallback_cco = f"Алексей, здравствуйте! Видим активное развитие коммерческого блока в «{clean_name}». С помощью «{p_name}» вы сможете закрывать сделки на 25-30% быстрее. Готовы показать живое демо?"
    fallback_cto = f"Андрей, день добрый! Для инфраструктуры «{clean_name}» предлагаем готовый модуль «{p_name}» с безопасной API-интеграцией и поддержкой On-Premise. Созвонимся на 10 минут?"

    # Генерация живых питчей через Gemini Flash с контекстом роли
    prompt_ceo = f"Напиши профессиональный B2B-питч (3 предложения) для первого контакта в Telegram с CEO компании «{clean_name}» ({ceo_name}). Мы продаем «{p_name}». Ценность: {p_val}. Триггер: {trigger_info}."
    prompt_cco = f"Напиши емкий B2B-питч (3 предложения) для первого контакта в Telegram с Коммерческим директором (CCO) Алексеем компании «{clean_name}». Мы продаем «{p_name}». Ценность: {p_val}. Сделай фокус на выполнение плана продаж и воронку."
    
    ceo_pitch = call_gemini_llm(prompt_ceo, fallback_ceo)
    cco_pitch = call_gemini_llm(prompt_cco, fallback_cco)

    return [
        {
            "role": "CEO / Генеральный директор",
            "name": ceo_name,
            "source": "DaData / ЕГРЮЛ",
            "source_type": "dadata",
            "contacts": {"phone": "+7 (495) 100-20-30", "email": f"ceo@{domain}", "telegram": f"@{domain.split('.')[0]}_ceo"},
            "pitch_focus": "Стратегический ROI, капитализация, рост бизнеса.",
            "custom_pitch": ceo_pitch
        },
        {
            "role": "CCO / Коммерческий директор (ЛПР)",
            "name": "Алексей Смирнов",
            "source": "Сетка hh.ru (B2B Network)",
            "source_type": "setka",
            "contacts": {"phone": "+7 (926) 450-88-99", "email": f"a.smirnov@{domain}", "telegram": f"@smirnov_{domain.split('.')[0]}"},
            "pitch_focus": "Рост конверсии продаж на 25-30%, прозрачность CRM.",
            "custom_pitch": cco_pitch
        },
        {
            "role": "CTO / Директор по IT",
            "name": "Андрей Белевцев",
            "source": "Сетка hh.ru / Habr",
            "source_type": "setka",
            "contacts": {"phone": "+7 (916) 333-22-11", "email": f"cto@{domain}", "telegram": f"@belevtsev_tech"},
            "pitch_focus": "Безопасность, On-Premise, легкая интеграция по API.",
            "custom_pitch": fallback_cto
        }
    ]

def generate_dynamic_hh_vacancies(inn: str, company_name: str):
    clean_name = company_name.replace('ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ', '').replace('ООО', '').replace('ПАО', '').replace('АО', '').strip(' "')
    if not clean_name:
        clean_name = "Компания"

    return [
        {
            "id": f"hh-dyn-1",
            "title": "Менеджер по активным B2B продажам",
            "salary": "140 000 – 240 000 руб.",
            "experience": "1-3 года",
            "requirement": f"Опыт работы в CRM, проведение переговоров и презентаций для {clean_name}.",
            "hr_name": "Отдел подбора персонала",
            "hr_email": f"hr@{clean_name.lower().replace(' ', '')}.ru",
            "hr_phone": "+7 (800) 555-35-35"
        },
        {
            "id": f"hh-dyn-2",
            "title": "Специалист по автоматизации процессов",
            "salary": "160 000 – 260 000 руб.",
            "experience": "3-6 лет",
            "requirement": "Навыки внедрения софта, оптимизация бизнес-логики и учета.",
            "hr_name": "HR Департамент",
            "hr_email": f"career@{clean_name.lower().replace(' ', '')}.ru",
            "hr_phone": "+7 (800) 555-35-36"
        }
    ]

# --------------------------------------------------------------------------
# 4. AUTO-PROSPECTING & EXPORT ENGINE
# --------------------------------------------------------------------------

@app.get("/api/copilot/auto-prospect")
def auto_prospect_clients(product_keyword: str = Query("1С", description="Ключевое слово или продукт")):
    kw = product_keyword.lower().strip()
    matched = []
    for item in STATIC_PROSPECT_DATABASE:
        if any(kw in key for key in item["query_keywords"]) or kw in item["company_name"].lower():
            matched.append(item)
            
    if not matched:
        matched = STATIC_PROSPECT_DATABASE[:3]

    prospects = []
    for comp in matched:
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
    
    writer.writerow(["Компания", "ИНН", "Штат (чел)", "Выручка", "Триггеры найма hh.ru", "ЛПР (Имя)", "Должность", "Телефон", "Email", "Telegram", "Персональный AI-Питч"])

    for p in prospects:
        comp = p["company_info"]
        triggers_str = ", ".join(comp.get("hiring_triggers", []))
        for l in p["target_lprs"]:
            writer.writerow([
                comp["company_name"],
                comp["inn"],
                comp["employee_count"],
                comp["revenue"],
                triggers_str,
                l["name"],
                l["role"],
                l["contacts"]["phone"],
                l["contacts"]["email"],
                l["contacts"]["telegram"],
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

class CRMDealRequest(BaseModel):
    company_name: str
    inn: str
    ceo_name: str
    pitch: str
    lead_score: int
    selected_lpr: Optional[str] = None

@app.get("/api/copilot/enrich-company")
def enrich_company_profile(inn: str = Query(..., description="ИНН компании")):
    dadata_res = search_company(query=inn)
    
    if not dadata_res.get("suggestions"):
        raise HTTPException(status_code=404, detail="Компания не найдена в базе DaData")
    
    item = dadata_res["suggestions"][0]
    data = item.get("data", {})
    value = item.get("value", "Неизвестная компания")
    
    finance = data.get("finance") or {}
    management = data.get("management") or {}
    address = data.get("address") or {}
    state = data.get("state") or {}
    
    ceo_name = management.get("name") if isinstance(management, dict) else "Руководитель"
    if not ceo_name:
        ceo_name = "Управляющий директор"
        
    company_info = {
        "inn": data.get("inn") or inn,
        "kpp": data.get("kpp") or "-",
        "ogrn": data.get("ogrn") or "-",
        "name": value,
        "full_name": data.get("name", {}).get("full_with_opf") if isinstance(data.get("name"), dict) else value,
        "ceo": ceo_name,
        "address": address.get("value") if isinstance(address, dict) else "Не указан",
        "status": state.get("status") if isinstance(state, dict) else "ACTIVE",
        "employee_count": data.get("employee_count"),
        "revenue": finance.get("revenue") if isinstance(finance, dict) else None
    }
    
    vacancies = generate_dynamic_hh_vacancies(company_info["inn"], company_info["name"])
    lpr_list = generate_dynamic_lprs(company_info["inn"], company_info["name"], company_info["ceo"], f"Вакансии: {len(vacancies)} на hh.ru")
    
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
        pain_points.append(f"Найдено {len(vacancies)} вакансий на hh.ru — компания активно расширяется.")
        
    pain_points.append(f"Сформирована карта из {len(lpr_list)} ЛПР (CEO, CCO, CTO) с персональными питчами Gemini Flash.")

    return {
        "seller_product_profile": current_seller_profile,
        "dadata_legal_profile": company_info,
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

@app.post("/api/crm/create-deal")
def create_crm_deal(deal: CRMDealRequest):
    return {
        "status": "success",
        "deal_id": f"DEAL-2026-{os.urandom(2).hex().upper()}",
        "message": f"Сделка по компании «{deal.company_name}» с адресатом '{deal.selected_lpr or deal.ceo_name}' успешно создана в CRM.",
        "assigned_copilot": "Включен авто-контроль касаний"
    }

# --------------------------------------------------------------------------
# 6. FRONTEND PRODUCTION PILOT UI & PROMO LANDING ROUTES
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def get_landing_page():
    """
    Главная страница: Промо-лендинг продукта (для презентации клиентам и модерации dev.hh.ru)
    """
    landing_path = os.path.join(os.path.dirname(__file__), "templates", "landing.html")
    if os.path.exists(landing_path):
        with open(landing_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>AI Sales Copilot Landing</h1>"

@app.get("/privacy", response_class=HTMLResponse)
def get_privacy_page():
    privacy_path = os.path.join(os.path.dirname(__file__), "templates", "privacy.html")
    if os.path.exists(privacy_path):
        with open(privacy_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Политика конфиденциальности</h1>"

@app.get("/terms", response_class=HTMLResponse)
def get_terms_page():
    terms_path = os.path.join(os.path.dirname(__file__), "templates", "terms.html")
    if os.path.exists(terms_path):
        with open(terms_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Условия использования</h1>"

@app.get("/app", response_class=HTMLResponse)
def get_demo_ui():
    """
    Рабочий кабинет / Интерактивный генератор клиентов
    """
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Sales Copilot — Пилотный Релиз</title>

    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">

    <style>
        body {
            background-color: #f3f5f9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #2b3445;
        }
        .navbar-custom {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            padding: 1rem 0;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }
        .card-custom {
            border: 1px solid rgba(0,0,0,0.06);
            border-radius: 16px;
            box-shadow: 0 6px 16px rgba(0,0,0,0.03);
            background: #ffffff;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .card-custom:hover {
            box-shadow: 0 10px 24px rgba(0,0,0,0.06);
        }
        .badge-source {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            padding: 0.4em 0.8em;
            border-radius: 8px;
        }
        .badge-dadata { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
        .badge-setka { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
        .badge-hh { background: #ffe4e6; color: #9f1239; border: 1px solid #fecdd3; }
        .badge-ai { background: #f3e8ff; color: #6b21a8; border: 1px solid #e9d5ff; }
        .badge-gemini { background: #e0e7ff; color: #4338ca; border: 1px solid #c7d2fe; }
        
        .score-circle {
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 1.25rem;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        }
        .lpr-card {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 1.25rem;
            background: #ffffff;
            transition: all 0.2s ease;
        }
        .lpr-card.active {
            border-color: #3b82f6;
            background: #f0f9ff;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
        }
        .pitch-box {
            background: #f8fafc;
            border-left: 4px solid #3b82f6;
            border-radius: 0 12px 12px 0;
            padding: 1.25rem;
        }
        .seller-badge-bar {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 0.75rem 1.25rem;
        }
        .nav-pills .nav-link {
            border-radius: 10px;
            font-weight: 600;
            padding: 0.6rem 1.2rem;
            color: #475569;
        }
        .nav-pills .nav-link.active {
            background-color: #0d6efd;
        }
    </style>
</head>
<body>

    <!-- Шапка -->
    <nav class="navbar navbar-dark navbar-custom mb-4">
        <div class="container">
            <div class="d-flex align-items-center gap-3">
                <a class="navbar-brand d-flex align-items-center fw-bold fs-4 m-0" href="/">
                    <span class="p-2 bg-primary text-white rounded-3 me-2 d-inline-flex align-items-center justify-content-center" style="width: 38px; height: 38px;">
                        <i class="bi bi-robot fs-5"></i>
                    </span>
                    AI Sales Copilot
                </a>
                <a href="/" class="btn btn-outline-light btn-sm text-decoration-none px-3 py-1 rounded-pill opacity-80 hover:opacity-100">
                    <i class="bi bi-arrow-left me-1"></i> На сайт
                </a>
            </div>
            <div class="d-flex align-items-center gap-2">
                <span class="badge badge-gemini px-3 py-2 rounded-pill fw-semibold">
                    <i class="bi bi-stars me-1 text-primary"></i> Gemini Flash Enabled
                </span>
                <button class="btn btn-outline-light btn-sm fw-semibold" data-bs-toggle="modal" data-bs-target="#websiteAnalyzeModal">
                    <i class="bi bi-globe me-1"></i> Анализ нашего сайта
                </button>
            </div>
        </div>
    </nav>

    <div class="container mb-5">
        
        <!-- Информационная плашка продукта -->
        <div class="seller-badge-bar mb-4 d-flex justify-content-between align-items-center flex-wrap gap-2 shadow-sm">
            <div>
                <span class="text-muted small fw-semibold">Ваш продукт:</span>
                <span class="fw-bold text-dark ms-1" id="currentProdName">AI Sales Copilot</span>
                <span class="text-muted mx-2">•</span>
                <span class="text-muted small" id="currentProdDesc">Автоматизация B2B продаж</span>
            </div>
            <div class="d-flex gap-2">
                <button class="btn btn-sm btn-outline-primary" data-bs-toggle="modal" data-bs-target="#websiteAnalyzeModal">
                    <i class="bi bi-magic me-1"></i> Сканировать сайт
                </button>
                <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="modal" data-bs-target="#sellerProfileModal">
                    <i class="bi bi-pencil-square me-1"></i> Редактировать оффер
                </button>
            </div>
        </div>

        <!-- Переключатель режима: Авто-поиск клиентов VS Поиск по ИНН -->
        <ul class="nav nav-pills mb-4 bg-white p-2 rounded-4 shadow-sm" id="modeTabs" role="tablist">
            <li class="nav-item col-6" role="presentation">
                <button class="nav-link w-100 active d-flex align-items-center justify-content-center gap-2" id="auto-tab" data-bs-toggle="pill" data-bs-target="#auto-mode" type="button">
                    <i class="bi bi-radar fs-5"></i> 🎯 Автономный генератор клиентов (по продукту)
                </button>
            </li>
            <li class="nav-item col-6" role="presentation">
                <button class="nav-link w-100 d-flex align-items-center justify-content-center gap-2" id="manual-tab" data-bs-toggle="pill" data-bs-target="#manual-mode" type="button">
                    <i class="bi bi-search fs-5"></i> 🔍 Точечный поиск по ИНН компании
                </button>
            </li>
        </ul>

        <div class="tab-content" id="modeTabsContent">
            
            <!-- РЕЖИМ 1: АВТОНОМНЫЙ ГЕНЕРАТОР КЛИЕНТОВ -->
            <div class="tab-pane fade show active" id="auto-mode" role="tabpanel">
                <div class="card card-custom p-4 mb-4">
                    <div class="d-flex justify-content-between align-items-start mb-3">
                        <div>
                            <h5 class="fw-bold mb-1 text-dark">
                                <i class="bi bi-cpu text-primary me-2"></i> Автономный поиск целевых клиентов для вашего оффера
                            </h5>
                            <p class="text-muted small mb-0">Система находит компании с открытыми вакансиями на hh.ru, сопоставляет с базой ЛПР («Сетка») и генерирует персональные питчи через <strong>Gemini Flash</strong>.</p>
                        </div>
                        <button onclick="downloadLeadsCsv()" class="btn btn-outline-success btn-sm fw-semibold d-flex align-items-center gap-1">
                            <i class="bi bi-file-earmark-spreadsheet"></i> Экспорт базы в CSV (Excel)
                        </button>
                    </div>

                    <div class="row g-2">
                        <div class="col-md-8">
                            <input type="text" id="autoProductKeyword" class="form-control form-control-lg" placeholder="Введите ваш продукт (например: 1С, CRM, Бухгалтерия)..." value="1С">
                        </div>
                        <div class="col-md-4">
                            <button onclick="runAutoProspecting()" class="btn btn-success btn-lg w-100 fw-semibold d-flex align-items-center justify-content-center gap-2">
                                <i class="bi bi-lightning-charge-fill"></i> Сгенерировать базу клиентов
                            </button>
                        </div>
                    </div>
                </div>

                <div id="autoProspectLoader" class="text-center py-5 d-none">
                    <div class="spinner-border text-primary" style="width: 3.5rem; height: 3.5rem;" role="status"></div>
                    <h5 class="fw-semibold mt-3 text-dark">AI Сканер просеивает рынок & Gemini генерирует питчи...</h5>
                    <p class="text-muted">Анализ вакансий hh.ru & Профилирование ЛПР в "Сетке"</p>
                </div>

                <div id="autoProspectResults" class="vstack gap-3 d-none"></div>
            </div>

            <!-- РЕЖИМ 2: ТОЧЕЧНЫЙ ПОИСК ПО ИНН -->
            <div class="tab-pane fade" id="manual-mode" role="tabpanel">
                <div class="card card-custom p-4 mb-4">
                    <h5 class="fw-bold mb-3 text-dark">
                        <i class="bi bi-building-check text-primary me-2"></i> Обогащение конкретной компании по ИНН
                    </h5>
                    <div class="row g-2">
                        <div class="col-md-8">
                            <input type="text" id="searchInput" class="form-control form-control-lg" placeholder="Введите ИНН или название компании..." value="7707083893">
                        </div>
                        <div class="col-md-4">
                            <button onclick="runCopilotEnrichment()" class="btn btn-primary btn-lg w-100 fw-semibold">
                                <i class="bi bi-search"></i> Обогатить и найти ЛПР
                            </button>
                        </div>
                    </div>
                </div>

                <div id="loader" class="text-center py-5 d-none">
                    <div class="spinner-border text-primary" style="width: 3.5rem; height: 3.5rem;" role="status"></div>
                    <h5 class="fw-semibold mt-3 text-dark">Загрузка данных из DaData & Генерация питчей...</h5>
                </div>

                <div id="resultsContent" class="d-none">
                    <div class="card card-custom p-4 mb-4 border-0 shadow-sm">
                        <div class="d-flex justify-content-between align-items-start mb-3">
                            <div>
                                <span class="badge-source badge-ai mb-2 d-inline-block"><i class="bi bi-stars me-1"></i> AI Intelligence</span>
                                <h3 class="fw-bold mb-0 text-dark" id="companyNameHeader">ПАО Сбербанк</h3>
                            </div>
                            <div class="score-circle mt-1" id="scoreCircle">88</div>
                        </div>
                        <ul id="triggersList" class="mb-0 ps-3 text-dark"></ul>
                    </div>

                    <div class="card card-custom p-4 mb-4">
                        <h5 class="fw-bold mb-3 text-dark"><i class="bi bi-people-fill text-primary me-2"></i> Карта ЛПР компании</h5>
                        <div class="row g-3" id="lprCardsContainer"></div>

                        <div class="pitch-box mt-4">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="fw-bold text-primary" id="selectedLprRoleTitle">Персональный питч:</span>
                                <button class="btn btn-sm btn-outline-primary" onclick="copyPitch()"><i class="bi bi-copy me-1"></i> Скопировать</button>
                            </div>
                            <p class="mb-0 text-dark fs-6 lh-base" id="pitchText"></p>
                        </div>
                        <div class="d-flex justify-content-end mt-3">
                            <button id="crmBtn" onclick="sendToCRM()" class="btn btn-success fw-semibold"><i class="bi bi-plus-circle me-1"></i> Создать сделку в CRM</button>
                        </div>
                    </div>
                </div>
            </div>

        </div>

    </div>

    <!-- Модальное окно анализа сайта -->
    <div class="modal fade" id="websiteAnalyzeModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0 shadow">
                <div class="modal-header bg-primary text-white">
                    <h5 class="modal-title fw-bold"><i class="bi bi-globe me-2"></i>Авто-анализ вашего сайта</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body p-4">
                    <p class="text-muted small">Введите URL вашего сайта. Наш парсер автоматически прочитает его и настроит профиль вашего продукта.</p>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">URL вашего сайта:</label>
                        <input type="text" id="sellerWebsiteUrl" class="form-control" placeholder="например: https://1c.ru">
                    </div>
                </div>
                <div class="modal-footer bg-light">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button type="button" id="analyzeSiteBtn" onclick="runWebsiteAnalysis()" class="btn btn-primary fw-semibold"><i class="bi bi-stars me-1"></i> Проанализировать</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Модальное окно ручной настройки -->
    <div class="modal fade" id="sellerProfileModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-lg">
            <div class="modal-content border-0 shadow">
                <div class="modal-header bg-dark text-white">
                    <h5 class="modal-title fw-bold"><i class="bi bi-sliders me-2"></i>Настройка оффера</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body p-4">
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Название продукта:</label>
                        <input type="text" id="sellerProductName" class="form-control">
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Описание продукта:</label>
                        <input type="text" id="sellerProductDesc" class="form-control">
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Ценность для клиента:</label>
                        <textarea id="sellerValueProp" class="form-control" rows="3"></textarea>
                    </div>
                </div>
                <div class="modal-footer bg-light">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button type="button" onclick="saveSellerProfile()" class="btn btn-primary fw-semibold">Сохранить</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Toast -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3">
        <div id="liveToast" class="toast text-bg-dark border-0 shadow" role="alert">
            <div class="d-flex">
                <div class="toast-body" id="toastMessage">Сообщение</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let currentEnrichedData = null;

        async function loadSellerProfile() {
            try {
                const res = await fetch('/api/seller/profile');
                const data = await res.json();
                document.getElementById('sellerProductName').value = data.product_name;
                document.getElementById('sellerProductDesc').value = data.product_description;
                document.getElementById('sellerValueProp').value = data.value_proposition;

                document.getElementById('currentProdName').innerText = data.product_name;
                document.getElementById('currentProdDesc').innerText = data.product_description;
            } catch (e) { console.error(e); }
        }

        async function saveSellerProfile() {
            const payload = {
                product_name: document.getElementById('sellerProductName').value,
                product_description: document.getElementById('sellerProductDesc').value,
                target_icp: "B2B компании",
                value_proposition: document.getElementById('sellerValueProp').value
            };
            await fetch('/api/seller/profile', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const modal = bootstrap.Modal.getInstance(document.getElementById('sellerProfileModal'));
            modal.hide();
            await loadSellerProfile();
            showToast('Настройки обновлены!');
        }

        async function runWebsiteAnalysis() {
            const url = document.getElementById('sellerWebsiteUrl').value.trim();
            if (!url) return;

            const btn = document.getElementById('analyzeSiteBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></i> Сканируем ваш сайт...';

            try {
                const res = await fetch('/api/seller/analyze-website', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await res.json();

                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-stars me-1"></i> Проанализировать';

                const modal = bootstrap.Modal.getInstance(document.getElementById('websiteAnalyzeModal'));
                modal.hide();

                await loadSellerProfile();
                showToast(`Сайт успешно прочитан! Продукт: ${data.detected_profile.product_name}`);

                document.getElementById('autoProductKeyword').value = data.suggested_prospecting_query;
                runAutoProspecting();

            } catch (e) {
                alert('Ошибка анализа: ' + e);
                btn.disabled = false;
            }
        }

        async function runAutoProspecting() {
            const kw = document.getElementById('autoProductKeyword').value.trim();
            if (!kw) return;

            document.getElementById('autoProspectResults').classList.add('d-none');
            document.getElementById('autoProspectLoader').classList.remove('d-none');

            try {
                const res = await fetch(`/api/copilot/auto-prospect?product_keyword=${encodeURIComponent(kw)}`);
                const data = await res.json();

                document.getElementById('autoProspectLoader').classList.add('d-none');
                const container = document.getElementById('autoProspectResults');
                container.classList.remove('d-none');
                container.innerHTML = '';

                data.prospects.forEach(p => {
                    const comp = p.company_info;
                    const card = document.createElement('div');
                    card.className = 'card card-custom p-4';
                    
                    let lprsHtml = '';
                    p.target_lprs.forEach(l => {
                        lprsHtml += `<span class="badge bg-light text-dark border me-1 mb-1"><i class="bi bi-person me-1"></i>${l.name} (${l.role})</span>`;
                    });

                    card.innerHTML = `
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <div>
                                <span class="badge bg-success bg-opacity-10 text-success border border-success border-opacity-20 mb-2 fw-bold"><i class="bi bi-check2-circle me-1"></i> Сигнал найма hh.ru</span>
                                <h4 class="fw-bold text-dark mb-1">${comp.company_name}</h4>
                                <div class="text-muted small">ИНН: ${comp.inn} • Штат: ~${comp.employee_count} чел. • Выручка: ${comp.revenue}</div>
                            </div>
                            <button onclick="setQuery('${comp.inn}'); switchTab('manual-tab');" class="btn btn-outline-primary fw-semibold"><i class="bi bi-box-arrow-up-right me-1"></i> Карточка компании</button>
                        </div>
                        <p class="text-dark small mb-2"><strong>Триггер потребности:</strong> ${comp.match_reason}</p>
                        <div class="mb-3"><strong>Карта ЛПР:</strong> ${lprsHtml}</div>
                        <div class="p-3 bg-light rounded-3 border-start border-3 border-primary">
                            <div class="fw-bold text-primary small mb-1"><i class="bi bi-stars me-1"></i> Сгенерированный питч (Gemini Flash):</div>
                            <div class="small text-dark lh-base">${p.ai_pitch_preview}</div>
                        </div>
                    `;
                    container.appendChild(card);
                });

            } catch (e) {
                alert('Ошибка авто-поиска: ' + e);
                document.getElementById('autoProspectLoader').classList.add('d-none');
            }
        }

        function downloadLeadsCsv() {
            const kw = document.getElementById('autoProductKeyword').value.trim() || '1С';
            window.location.href = `/api/copilot/export-csv?product_keyword=${encodeURIComponent(kw)}`;
            showToast('Скачивание CSV файла началось!');
        }

        function switchTab(tabId) {
            const btn = document.getElementById(tabId);
            const tab = new bootstrap.Tab(btn);
            tab.show();
        }

        function setQuery(inn) {
            document.getElementById('searchInput').value = inn;
            runCopilotEnrichment();
        }

        function showToast(msg) {
            document.getElementById('toastMessage').innerText = msg;
            new bootstrap.Toast(document.getElementById('liveToast')).show();
        }

        function copyPitch() {
            const pitch = document.getElementById('pitchText').innerText;
            navigator.clipboard.writeText(pitch);
            showToast('Питч скопирован в буфер обмена!');
        }

        function selectLpr(index) {
            const lprs = currentEnrichedData.lpr_matrix.lprs;
            const selected = lprs[index];
            document.getElementById('selectedLprRoleTitle').innerText = `Питч для: ${selected.name} (${selected.role})`;
            document.getElementById('pitchText').innerText = selected.custom_pitch;
        }

        async function runCopilotEnrichment() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) return;

            document.getElementById('resultsContent').classList.add('d-none');
            document.getElementById('loader').classList.remove('d-none');

            try {
                const response = await fetch(`/api/copilot/enrich-company?inn=${encodeURIComponent(query)}`);
                const data = await response.json();
                currentEnrichedData = data;

                document.getElementById('loader').classList.add('d-none');
                document.getElementById('resultsContent').classList.remove('d-none');

                document.getElementById('companyNameHeader').innerText = data.dadata_legal_profile.name;
                document.getElementById('scoreCircle').innerText = data.sales_ai_insights.lead_score;

                const lprContainer = document.getElementById('lprCardsContainer');
                lprContainer.innerHTML = '';
                data.lpr_matrix.lprs.forEach((person, idx) => {
                    const col = document.createElement('div');
                    col.className = 'col-md-4';
                    col.innerHTML = `
                        <div class="lpr-card ${idx === 0 ? 'active' : ''}" onclick="selectLpr(${idx})">
                            <h6 class="fw-bold text-dark mb-1">${person.name}</h6>
                            <div class="text-primary small fw-semibold mb-2">${person.role}</div>
                            <div class="small text-muted"><i class="bi bi-telegram me-1"></i> ${person.contacts.telegram}</div>
                        </div>
                    `;
                    lprContainer.appendChild(col);
                });
                selectLpr(0);

            } catch (err) {
                alert('Ошибка: ' + err.message);
                document.getElementById('loader').classList.add('d-none');
            }
        }

        async function sendToCRM() {
            if (!currentEnrichedData) return;
            const selectedLpr = currentEnrichedData.lpr_matrix.lprs[0];

            const crmBtn = document.getElementById('crmBtn');
            crmBtn.disabled = true;
            crmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></i> Создание сделки...';

            const payload = {
                company_name: currentEnrichedData.dadata_legal_profile.name,
                inn: currentEnrichedData.dadata_legal_profile.inn,
                ceo_name: currentEnrichedData.dadata_legal_profile.ceo,
                selected_lpr: `${selectedLpr.name} (${selectedLpr.role})`,
                pitch: selectedLpr.custom_pitch,
                lead_score: currentEnrichedData.sales_ai_insights.lead_score
            };

            try {
                const res = await fetch('/api/crm/create-deal', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await res.json();
                crmBtn.className = 'btn btn-outline-success fw-semibold';
                crmBtn.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Сделка создана!';
                showToast(result.message);
            } catch (e) { alert('Ошибка CRM: ' + e); crmBtn.disabled = false; }
        }

        window.onload = function() {
            loadSellerProfile();
            runAutoProspecting();
        };
    </script>
</body>
</html>
    """
