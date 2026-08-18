import os
import json
import requests
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="AI Sales Copilot Interactive Prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DADATA_API_KEY = os.environ.get("DADATA_API_KEY", "")
DADATA_SECRET_KEY = os.environ.get("DADATA_SECRET_KEY", "")

# --------------------------------------------------------------------------
# 0. COMPANY PRODUCT PROFILE (Настройка продукта продавца)
# --------------------------------------------------------------------------

class SellerProductProfile(BaseModel):
    product_name: str = "AI Sales Copilot"
    product_description: str = "Автоматизация продаж и B2B AI-ассистент"
    target_icp: str = "Компания с B2B отделом продаж от 5 человек, использующая CRM"
    value_proposition: str = "Сокращает рутину менеджеров, подсказывает идеальный скрипт во время разговора и поднимает конверсию сделок на 25-30%"

current_seller_profile = SellerProductProfile()

@app.get("/api/seller/profile")
def get_seller_profile():
    return current_seller_profile

@app.post("/api/seller/profile")
def update_seller_profile(profile: SellerProductProfile):
    global current_seller_profile
    current_seller_profile = profile
    return {"status": "success", "profile": current_seller_profile}

# --------------------------------------------------------------------------
# 1. REAL DADATA INTEGRATION
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
# 2. LPR & SETKA / HH.RU DYNAMIC FINDER ENGINE
# --------------------------------------------------------------------------

STATIC_MOCK_LPRS = {
    "7707083893": [ # Сбербанк
        {
            "role": "CEO / Президент",
            "name": "Греф Герман Оскарович",
            "source": "DaData / ЕГРЮЛ",
            "source_type": "dadata",
            "contacts": {"phone": "+7 (495) 957-58-60", "email": "gref-office@sberbank.ru", "telegram": "@sber_ceo_office"},
            "pitch_focus": "Стратегический ROI, технологическое лидерство, масштабирование экосистемы.",
            "custom_pitch": "Герман Оскарович, как лидеру технологической трансформации Сбера, предлагаем внедрить AI Sales Copilot для повышения эффективности B2B-коммерции."
        },
        {
            "role": "CCO / Руководитель Корпоративного Блока",
            "name": "Анатолий Попов",
            "source": "Сетка hh.ru / B2B Network",
            "source_type": "setka",
            "contacts": {"phone": "+7 (495) 777-55-34", "email": "a.popov@sberbank.ru", "telegram": "@apopov_sber_b2b"},
            "pitch_focus": "Рост конверсии B2B-продаж, снижение рутины менеджеров, прозрачность CRM.",
            "custom_pitch": "Анатолий, мы видим активный наем B2B менеджеров в Сбер. AI Sales Copilot подсказывает идеальные ответы прямо во время звонка и поднимает продажи корпоративным клиентам на 25%."
        },
        {
            "role": "CTO / Директор по ИИ и Технологиям",
            "name": "Андрей Белевцев",
            "source": "Сетка hh.ru / Habr",
            "source_type": "setka",
            "contacts": {"phone": "+7 (495) 777-55-33", "email": "a.belevtsev@sberbank-tech.ru", "telegram": "@belevtsev_ai"},
            "pitch_focus": "LLM-архитектура, безопасность данных, легкость API интеграции.",
            "custom_pitch": "Андрей, наше решение построена на локальных и облачных LLM с поддержкой On-Premise развертывания и готовыми API коннекторами."
        }
    ],
    "7702070139": [ # Яндекс
        {
            "role": "CEO / Генеральный директор",
            "name": "Бородин Артем Александрович",
            "source": "DaData / ЕГРЮЛ",
            "source_type": "dadata",
            "contacts": {"phone": "+7 (495) 739-70-00", "email": "ceo@yandex-team.ru", "telegram": "@yandex_ceo"},
            "pitch_focus": "Капитализация, рост доли рынка B2B сервисов.",
            "custom_pitch": "Артем Александрович, предлагаем решения для ускорения B2B продаж экосистемы Яндекс."
        },
        {
            "role": "CCO / Директор по B2B продажам",
            "name": "Михаил Сергеев",
            "source": "Сетка hh.ru",
            "source_type": "setka",
            "contacts": {"phone": "+7 (495) 739-70-01", "email": "m-sergeev@yandex-team.ru", "telegram": "@mikhail_yandex_b2b"},
            "pitch_focus": "Автоматизация пресейлов Яндекс 360, контроль качества звонков.",
            "custom_pitch": "Михаил, ваш отдел продаж Яндекс 360 активно растет. AI Copilot поможет новым менеджерам быстрее выходить на плановые показатели."
        }
    ]
}

STATIC_MOCK_VACANCIES = {
    "7707083893": [
        {
            "id": "hh-101",
            "title": "Senior Python Developer (AI & Machine Learning)",
            "salary": "280 000 – 380 000 руб.",
            "experience": "3-6 лет",
            "requirement": "Опыт работы с Python 3.12, FastAPI, LangChain, PostgreSQL, Vector DB.",
            "hr_name": "Екатерина Воронова",
            "hr_email": "e.voronova@sberbank-tech.ru",
            "hr_phone": "+7 (495) 777-55-33"
        },
        {
            "id": "hh-102",
            "title": "Руководитель группы продаж корпоративным клиентам",
            "salary": "200 000 – 400 000 руб.",
            "experience": "Более 6 лет",
            "requirement": "Опыт B2B продаж крупному бизнесу, навык переговоров с C-level (LPR).",
            "hr_name": "Максим Громов",
            "hr_email": "m.gromov@sberbank.ru",
            "hr_phone": "+7 (495) 777-55-34"
        }
    ]
}

def generate_dynamic_lprs(inn: str, company_name: str, ceo_from_dadata: str):
    if inn in STATIC_MOCK_LPRS:
        return STATIC_MOCK_LPRS[inn]
    
    clean_name = company_name.replace('ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ', '').replace('ООО', '').replace('ПАО', '').replace('АО', '').strip(' "')
    if not clean_name:
        clean_name = "Компания"

    domain = clean_name.lower().replace(' ', '').replace('-', '') + ".ru"

    return [
        {
            "role": "CEO / Генеральный директор",
            "name": ceo_from_dadata if ceo_from_dadata else "Управляющий директор",
            "source": "DaData / ЕГРЮЛ",
            "source_type": "dadata",
            "contacts": {"phone": "+7 (495) 100-20-30", "email": f"ceo@{domain}", "telegram": f"@{domain.split('.')[0]}_ceo"},
            "pitch_focus": "Стратегический рост бизнеса, снижение издержек, повышение прибыльности.",
            "custom_pitch": f"Уважаемый {ceo_from_dadata}, предлагаем внедрить {current_seller_profile.product_name} для автоматизации бизнес-процессов компании «{clean_name}»."
        },
        {
            "role": "CCO / Коммерческий директор (ЛПР)",
            "name": "Алексей Смирнов",
            "source": "Сетка hh.ru (Профессиональный профиль)",
            "source_type": "setka",
            "contacts": {"phone": "+7 (926) 450-88-99", "email": f"a.smirnov@{domain}", "telegram": f"@smirnov_{domain.split('.')[0]}"},
            "pitch_focus": "Выполнение плана продаж, рост конверсии лидов, контроль менеджеров.",
            "custom_pitch": f"Алексей, с помощью {current_seller_profile.product_name} ваш отдел продаж сможет закрывать сделки на 25-30% быстрее за счет AI-подсказок в реальном времени."
        },
        {
            "role": "HRD / Директор по персоналу",
            "name": "Елена Васильева",
            "source": "Сетка hh.ru / Кадры",
            "source_type": "setka",
            "contacts": {"phone": "+7 (916) 333-22-11", "email": f"hrd@{domain}", "telegram": f"@vasilieva_hr"},
            "pitch_focus": "Быстрый онбординг новичков, сокращение периода обучения менеджеров.",
            "custom_pitch": f"Елена, наше решение ускоряет адаптацию новых сотрудников в отделе продаж в 2 раза."
        }
    ]

def generate_dynamic_hh_vacancies(inn: str, company_name: str):
    if inn in STATIC_MOCK_VACANCIES:
        return STATIC_MOCK_VACANCIES[inn]
    
    clean_name = company_name.replace('ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ', '').replace('ООО', '').replace('ПАО', '').replace('АО', '').strip(' "')
    if not clean_name:
        clean_name = "Компания"

    return [
        {
            "id": f"hh-dyn-1",
            "title": "Менеджер по активным продажам B2B",
            "salary": "120 000 – 220 000 руб.",
            "experience": "1-3 года",
            "requirement": f"Опыт B2B продаж, ведение сделок в CRM, грамотная речь.",
            "hr_name": "Отдел кадров",
            "hr_email": f"hr@{clean_name.lower().replace(' ', '')}.ru",
            "hr_phone": "+7 (800) 555-35-35"
        },
        {
            "id": f"hh-dyn-2",
            "title": "Ведущий специалист по развитию бизнеса",
            "salary": "150 000 – 250 000 руб.",
            "experience": "3-6 лет",
            "requirement": "Навыки стратегического планирования, выстраивание партнерской сети.",
            "hr_name": "HR Департамент",
            "hr_email": f"career@{clean_name.lower().replace(' ', '')}.ru",
            "hr_phone": "+7 (800) 555-35-36"
        }
    ]

# --------------------------------------------------------------------------
# 3. AI SALES COPILOT ENRICHMENT API (С МАТРИЦЕЙ ЛПР)
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
    lpr_list = generate_dynamic_lprs(company_info["inn"], company_info["name"], company_info["ceo"])
    
    # AI Scoring & Pain Points
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
        
    pain_points.append(f"Сформирована карта из {len(lpr_list)} ЛПР (CEO, CCO, CTO) с персональными контактами и питчами.")

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
# 4. FRONTEND INTERACTIVE PROTOTYPE (С МАТРИЦЕЙ ЛПР И "СЕТКОЙ" HH.RU)
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def get_demo_ui():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Sales Copilot — Поиск ЛПР и Обогащение</title>

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
    </style>
</head>
<body>

    <!-- Шапка -->
    <nav class="navbar navbar-dark navbar-custom mb-4">
        <div class="container">
            <a class="navbar-brand d-flex align-items-center fw-bold fs-4" href="#">
                <span class="p-2 bg-primary text-white rounded-3 me-2 d-inline-flex align-items-center justify-content-center" style="width: 38px; height: 38px;">
                    <i class="bi bi-robot fs-5"></i>
                </span>
                AI Sales Copilot
            </a>
            <div class="d-flex align-items-center gap-2">
                <button class="btn btn-outline-light btn-sm fw-semibold" data-bs-toggle="modal" data-bs-target="#sellerProfileModal">
                    <i class="bi bi-gear-fill me-1"></i> Настроить мой оффер
                </button>
                <span class="badge bg-success bg-opacity-20 text-success px-3 py-2 rounded-pill border border-success border-opacity-20">
                    <i class="bi bi-broadcast me-1"></i> Live LPR Finder
                </span>
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
            <button class="btn btn-sm btn-link text-decoration-none p-0 text-primary fw-semibold" data-bs-toggle="modal" data-bs-target="#sellerProfileModal">
                <i class="bi bi-pencil-square me-1"></i> Изменить оффер
            </button>
        </div>

        <!-- Панель поиска -->
        <div class="card card-custom p-4 mb-4">
            <h5 class="fw-bold mb-3 text-dark">
                <i class="bi bi-person-lines-fill text-primary me-2"></i> Поиск ЛПР и Обогащение компании
            </h5>
            <div class="row g-2">
                <div class="col-md-8">
                    <div class="input-group input-group-lg">
                        <span class="input-group-text bg-white text-muted border-end-0"><i class="bi bi-building"></i></span>
                        <input type="text" id="searchInput" class="form-control border-start-0 ps-0" placeholder="Введите ИНН или название компании..." value="7707083893">
                    </div>
                </div>
                <div class="col-md-4">
                    <button onclick="runCopilotEnrichment()" class="btn btn-primary btn-lg w-100 fw-semibold d-flex align-items-center justify-content-center gap-2">
                        <i class="bi bi-search-heart"></i> Найти ЛПР и Обогатить
                    </button>
                </div>
            </div>
            
            <div class="d-flex align-items-center gap-2 mt-3 text-muted small">
                <span class="fw-semibold">Примеры:</span>
                <button class="btn btn-sm btn-outline-secondary rounded-pill py-0 px-2" onclick="setQuery('7707083893')">Сбербанк</button>
                <button class="btn btn-sm btn-outline-secondary rounded-pill py-0 px-2" onclick="setQuery('7702070139')">Яндекс</button>
                <button class="btn btn-sm btn-outline-secondary rounded-pill py-0 px-2" onclick="setQuery('7710353606')">Т-Банк</button>
            </div>
        </div>

        <!-- Прелоадер -->
        <div id="loader" class="text-center py-5 d-none">
            <div class="spinner-border text-primary" style="width: 3.5rem; height: 3.5rem;" role="status"></div>
            <h5 class="fw-semibold mt-3 text-dark">AI Копилот ищет ЛПР и формирует питчи...</h5>
            <p class="text-muted">Запрос реквизитов DaData & Сканирование "Сетки" hh.ru</p>
        </div>

        <!-- Область результатов -->
        <div id="resultsContent" class="d-none">
            
            <!-- AI Copilot Card Header -->
            <div class="card card-custom p-4 mb-4 border-0 shadow-sm">
                <div class="d-flex justify-content-between align-items-start mb-3">
                    <div>
                        <span class="badge-source badge-ai mb-2 d-inline-block">
                            <i class="bi bi-stars me-1"></i> AI Sales Intelligence
                        </span>
                        <h3 class="fw-bold mb-0 text-dark" id="companyNameHeader">ПАО Сбербанк</h3>
                    </div>
                    <div class="text-end d-flex align-items-center gap-3">
                        <div>
                            <div class="text-muted small fw-semibold">Lead Score</div>
                            <div class="score-circle mt-1" id="scoreCircle">88</div>
                        </div>
                    </div>
                </div>

                <div class="row g-3 mb-3">
                    <div class="col-md-7">
                        <h6 class="fw-bold text-secondary mb-2"><i class="bi bi-lightning-charge-fill text-warning me-1"></i>Аналитика и триггеры:</h6>
                        <ul id="triggersList" class="mb-0 ps-3 text-dark"></ul>
                    </div>
                    <div class="col-md-5">
                        <h6 class="fw-bold text-secondary mb-2"><i class="bi bi-check2-circle text-success me-1"></i>Рекомендуемые шаги:</h6>
                        <ul id="nextStepsList" class="list-unstyled mb-0 small text-muted"></ul>
                    </div>
                </div>
            </div>

            <!-- РАЗДЕЛ: МАТРИЦА ЛПР (ЛИЦА, ПРИНИМАЮЩИЕ РЕШЕНИЯ) -->
            <div class="card card-custom p-4 mb-4">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h5 class="fw-bold mb-0 text-dark">
                        <i class="bi bi-people-fill text-primary me-2"></i> Карта ЛПР компании (Найденные контакты)
                    </h5>
                    <span class="badge bg-primary bg-opacity-10 text-primary fw-bold" id="lprCountBadge">3 ЛПР найдено</span>
                </div>
                <p class="text-muted small mb-4">Выберите нужного руководителя — AI Copilot сразу сформирует персональный питч с учетом его роли и задач.</p>

                <div class="row g-3" id="lprCardsContainer"></div>

                <!-- Выбранный Pitch -->
                <div class="pitch-box mt-4">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="fw-bold text-primary" id="selectedLprRoleTitle">
                            <i class="bi bi-chat-left-quote-fill me-2"></i> Персональный питч для выбранного ЛПР:
                        </span>
                        <button class="btn btn-sm btn-outline-primary" onclick="copyPitch()"><i class="bi bi-copy me-1"></i> Скопировать питч</button>
                    </div>
                    <p class="mb-0 text-dark fs-6 lh-base" id="pitchText"></p>
                </div>

                <div class="d-flex justify-content-end mt-3">
                    <button id="crmBtn" onclick="sendToCRM()" class="btn btn-success fw-semibold">
                        <i class="bi bi-plus-circle me-1"></i> Создать сделку в CRM для этого ЛПР
                    </button>
                </div>
            </div>

            <!-- Колонки источника: DaData & hh.ru -->
            <div class="row g-4">
                <div class="col-lg-6">
                    <div class="card card-custom h-100 p-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold mb-0 text-dark"><i class="bi bi-building-check text-primary me-2"></i>Юридический профиль</h5>
                            <span class="badge-source badge-dadata"><i class="bi bi-check-circle-fill me-1"></i> DaData (Live)</span>
                        </div>
                        <table class="table table-borderless table-sm mb-0">
                            <tbody>
                                <tr><td class="text-muted fw-semibold">ИНН / КПП:</td><td class="fw-semibold text-dark" id="legalInnKpp">-</td></tr>
                                <tr><td class="text-muted fw-semibold">ОГРН:</td><td class="text-dark" id="legalOgrn">-</td></tr>
                                <tr><td class="text-muted fw-semibold">Генеральный директор:</td><td class="fw-bold text-primary" id="legalCeo">-</td></tr>
                                <tr><td class="text-muted fw-semibold">Адрес:</td><td class="text-dark small" id="legalAddress">-</td></tr>
                                <tr><td class="text-muted fw-semibold">Штат:</td><td class="text-dark" id="legalEmployees">-</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="col-lg-6">
                    <div class="card card-custom h-100 p-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold mb-0 text-dark"><i class="bi bi-briefcase text-danger me-2"></i>Найм & Вакансии</h5>
                            <span class="badge-source badge-hh"><i class="bi bi-cpu-fill me-1"></i> hh.ru API</span>
                        </div>
                        <div id="vacanciesContainer" class="vstack gap-2"></div>
                    </div>
                </div>
            </div>

        </div>

    </div>

    <!-- Модальное окно настройки -->
    <div class="modal fade" id="sellerProfileModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered modal-lg">
            <div class="modal-content border-0 shadow">
                <div class="modal-header bg-dark text-white">
                    <h5 class="modal-title fw-bold"><i class="bi bi-sliders me-2"></i>Настройка вашего продукта</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body p-4">
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Название продукта / решения:</label>
                        <input type="text" id="sellerProductName" class="form-control">
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Описание продукта:</label>
                        <input type="text" id="sellerProductDesc" class="form-control">
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-semibold">Ценность для клиента (Value Proposition):</label>
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
        <div id="liveToast" class="toast text-bg-dark border-0 shadow" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body" id="toastMessage">Сообщение скопировано</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let currentEnrichedData = null;
        let selectedLprIndex = 0;

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
            showToast('Настройки продукта обновлены!');
            if (document.getElementById('searchInput').value) runCopilotEnrichment();
        }

        function setQuery(inn) {
            document.getElementById('searchInput').value = inn;
            runCopilotEnrichment();
        }

        function showToast(msg) {
            document.getElementById('toastMessage').innerText = msg;
            const toastEl = document.getElementById('liveToast');
            new bootstrap.Toast(toastEl).show();
        }

        function copyPitch() {
            const pitch = document.getElementById('pitchText').innerText;
            navigator.clipboard.writeText(pitch);
            showToast('Питч скопирован в буфер обмена!');
        }

        function selectLpr(index) {
            selectedLprIndex = index;
            const lprs = currentEnrichedData.lpr_matrix.lprs;
            const selected = lprs[index];

            document.querySelectorAll('.lpr-card').forEach((card, idx) => {
                if (idx === index) card.classList.add('active');
                else card.classList.remove('active');
            });

            document.getElementById('selectedLprRoleTitle').innerHTML = `<i class="bi bi-chat-left-quote-fill me-2"></i> Питч для ЛПР: ${selected.name} (${selected.role}):`;
            document.getElementById('pitchText').innerText = selected.custom_pitch;
        }

        async function runCopilotEnrichment() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) return;

            document.getElementById('resultsContent').classList.add('d-none');
            document.getElementById('loader').classList.remove('d-none');

            try {
                const response = await fetch(`/api/copilot/enrich-company?inn=${encodeURIComponent(query)}`);
                if (!response.ok) throw new Error('Ошибка поиска компании');

                const data = await response.json();
                currentEnrichedData = data;

                document.getElementById('loader').classList.add('d-none');
                document.getElementById('resultsContent').classList.remove('d-none');

                const legal = data.dadata_legal_profile;
                const hh = data.hh_recruitment_profile;
                const ai = data.sales_ai_insights;
                const lpr = data.lpr_matrix;

                document.getElementById('companyNameHeader').innerText = legal.name;
                document.getElementById('scoreCircle').innerText = ai.lead_score;

                // Triggers
                const triggersList = document.getElementById('triggersList');
                triggersList.innerHTML = '';
                ai.insights.forEach(t => {
                    const li = document.createElement('li');
                    li.className = 'mb-1';
                    li.innerText = t;
                    triggersList.appendChild(li);
                });

                // Next steps
                const nextStepsList = document.getElementById('nextStepsList');
                nextStepsList.innerHTML = '';
                ai.next_steps.forEach(step => {
                    const li = document.createElement('li');
                    li.className = 'mb-1 fw-semibold text-dark';
                    li.innerText = step;
                    nextStepsList.appendChild(li);
                });

                // Render LPR Cards
                document.getElementById('lprCountBadge').innerText = `${lpr.total_lprs} ЛПР найдено`;
                const lprContainer = document.getElementById('lprCardsContainer');
                lprContainer.innerHTML = '';

                lpr.lprs.forEach((person, idx) => {
                    const badgeClass = person.source_type === 'setka' ? 'badge-setka' : 'badge-dadata';
                    const iconClass = person.source_type === 'setka' ? 'bi-share-fill' : 'bi-shield-check';
                    
                    const col = document.createElement('div');
                    col.className = 'col-md-4';
                    col.innerHTML = `
                        <div class="lpr-card ${idx === 0 ? 'active' : ''}" onclick="selectLpr(${idx})" style="cursor: pointer;">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <span class="badge-source ${badgeClass}"><i class="bi ${iconClass} me-1"></i> ${person.source}</span>
                            </div>
                            <h6 class="fw-bold text-dark mb-1">${person.name}</h6>
                            <div class="text-primary small fw-semibold mb-2">${person.role}</div>
                            
                            <div class="small text-muted mb-1"><i class="bi bi-telephone me-1"></i> ${person.contacts.phone}</div>
                            <div class="small text-muted mb-1"><i class="bi bi-envelope me-1"></i> ${person.contacts.email}</div>
                            <div class="small text-muted"><i class="bi bi-telegram me-1"></i> ${person.contacts.telegram}</div>
                        </div>
                    `;
                    lprContainer.appendChild(col);
                });

                // Set initial LPR pitch
                selectLpr(0);

                // DaData Fill
                document.getElementById('legalInnKpp').innerText = `${legal.inn} / ${legal.kpp}`;
                document.getElementById('legalOgrn').innerText = legal.ogrn;
                document.getElementById('legalCeo').innerText = legal.ceo;
                document.getElementById('legalAddress').innerText = legal.address;
                document.getElementById('legalEmployees').innerText = legal.employee_count ? `${legal.employee_count} чел.` : 'Не указано';

                // hh.ru Fill
                const vacContainer = document.getElementById('vacanciesContainer');
                vacContainer.innerHTML = '';
                hh.vacancies.forEach(v => {
                    const el = document.createElement('div');
                    el.className = 'p-2 border rounded bg-light small mb-2';
                    el.innerHTML = `<div class="fw-bold text-dark">${v.title}</div><div class="text-muted">${v.requirement}</div>`;
                    vacContainer.appendChild(el);
                });

            } catch (err) {
                alert('Ошибка: ' + err.message);
                document.getElementById('loader').classList.add('d-none');
            }
        }

        async function sendToCRM() {
            if (!currentEnrichedData) return;
            const selectedLpr = currentEnrichedData.lpr_matrix.lprs[selectedLprIndex];

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
            runCopilotEnrichment();
        };
    </script>
</body>
</html>
    """
