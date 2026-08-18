import os
import json
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
# 1. REAL DADATA INTEGRATION
# --------------------------------------------------------------------------

@app.get("/api/dadata/company")
def search_company(query: str = Query(..., description="ИНН, ОГРН или название компании")):
    """
    Реальный поиск компании в DaData по ИНН/названию.
    """
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
        # Попробуем общий поиск по названию если findById не дал совпадений
        url_suggest = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"
        response = requests.post(url_suggest, json=payload, headers=headers, timeout=10)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Ошибка при запросе к DaData")
    
    return response.json()

# --------------------------------------------------------------------------
# 2. HH.RU DYNAMIC MOCK ENGINE (Умная имитация вакансий под любую компанию)
# --------------------------------------------------------------------------

STATIC_MOCK_VACANCIES = {
    "7707083893": [ # Сбербанк
        {
            "id": "hh-101",
            "title": "Senior Python Developer (AI & Machine Learning)",
            "salary": "280 000 – 380 000 руб.",
            "experience": "3-6 лет",
            "requirement": "Опыт работы с Python 3.12, FastAPI, LangChain, LlamaIndex, PostgreSQL, Vector DB.",
            "responsibility": "Разработка LLM-агентов для автоматизации процессов B2B коммерции.",
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
            "responsibility": "Выполнение KPI по выручке, расширение клиентской базы в секторе Enterprise.",
            "hr_name": "Максим Громов",
            "hr_email": "m.gromov@sberbank.ru",
            "hr_phone": "+7 (495) 777-55-34"
        }
    ],
    "7702070139": [ # Яндекс
        {
            "id": "hh-201",
            "title": "B2B Sales Manager (Яндекс 360 & AI Solutions)",
            "salary": "180 000 – 320 000 руб.",
            "experience": "1-3 года",
            "requirement": "Понимание устройства SaaS и облачных платформ, опыт проведения пресейлов.",
            "responsibility": "Прямые продажи облачных сервисов для бизнеса, работа в CRM.",
            "hr_name": "Алина Орлова",
            "hr_email": "a-orlova@yandex-team.ru",
            "hr_phone": "+7 (495) 739-70-00"
        }
    ],
    "7710353606": [ # Т-Банк
        {
            "id": "hh-301",
            "title": "Head of Sales / Руководитель отдела продаж",
            "salary": "300 000 – 500 000 руб.",
            "experience": "Более 6 лет",
            "requirement": "Опыт управления отделом продаж от 20 человек, построение воронок в CRM.",
            "responsibility": "Масштабирование B2B направления, автоматизация обработки входящих лидов.",
            "hr_name": "Ольга Белова",
            "hr_email": "o.belova@tbank.ru",
            "hr_phone": "+7 (812) 888-00-11"
        }
    ]
}

def generate_dynamic_hh_vacancies(inn: str, company_name: str):
    """
    Генерирует динамический набор вакансий для любой компании, если её нет в статической базе.
    """
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
            "responsibility": f"Прямое привлечение клиентов для {clean_name}, проведение презентаций и заключение договоров.",
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
            "responsibility": "Поиск новых точек роста компании, автоматизация коммуникаций с клиентами.",
            "hr_name": "HR Департамент",
            "hr_email": f"career@{clean_name.lower().replace(' ', '')}.ru",
            "hr_phone": "+7 (800) 555-35-36"
        }
    ]

# --------------------------------------------------------------------------
# 3. AI SALES COPILOT ENRICHMENT API
# --------------------------------------------------------------------------

class CRMDealRequest(BaseModel):
    company_name: str
    inn: str
    ceo_name: str
    pitch: str
    lead_score: int

@app.get("/api/copilot/enrich-company")
def enrich_company_profile(inn: str = Query(..., description="ИНН компании")):
    """
    Агрегирует реальные данные DaData и имитацию hh.ru, формирует AI-рекомендации.
    """
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
        ceo_name = "Уважаемый руководитель"
        
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
    
    # AI Scoring & Pitch Generation Engine
    score = 70
    pain_points = []
    
    if company_info.get("employee_count"):
        emp = company_info["employee_count"]
        if emp > 500:
            score += 15
            pain_points.append(f"Крупный штат ({emp} сотрудников) — высокая нагрузка на отдел продаж и коммуникации.")
        elif emp > 50:
            score += 10
            pain_points.append(f"Средний бизнес ({emp} сотрудников) — этап активного масштабирования процессов.")
            
    if len(vacancies) > 0:
        score += 15
        pain_points.append(f"Открыто {len(vacancies)} ключевых вакансий на hh.ru — компания инвестирует в расширение команды.")
        
    pitch = (
        f"Здравствуйте, {company_info['ceo']}! Мы проанализировали текущую активность компании «{company_info['name']}». "
        f"Видим, что вы нанимаете специалистов в отдел продаж и развитие бизнеса. "
        f"Наш AI Sales Copilot интегрируется в вашу CRM и помогает автоматизировать рутину менеджеров, "
        f"подсказывая скрипты прямо во время звонка и повышая конверсию сделок на 25-30%."
    )
    
    return {
        "dadata_legal_profile": company_info,
        "hh_recruitment_profile": {
            "open_vacancies_count": len(vacancies),
            "vacancies": vacancies
        },
        "sales_ai_insights": {
            "lead_score": min(score, 98),
            "recommended_pitch": pitch,
            "insights": pain_points,
            "next_steps": [
                "1. Отправить персональное КП на email HR/Руководителю",
                "2. Запланировать вводную демо-презентацию AI Copilot",
                "3. Назначить встреча со ЛПР (Лицом, Принимающим Решения)"
            ]
        }
    }

@app.post("/api/crm/create-deal")
def create_crm_deal(deal: CRMDealRequest):
    """
    Имитация создания сделки в CRM (amoCRM / Битрикс24)
    """
    return {
        "status": "success",
        "deal_id": f"DEAL-2026-{os.urandom(2).hex().upper()}",
        "message": f"Сделка по компании «{deal.company_name}» успешно создана в CRM со статусом 'Первичный контакт'.",
        "assigned_copilot": "Включен авто-контроль касаний"
    }

# --------------------------------------------------------------------------
# 4. FRONTEND INTERACTIVE PROTOTYPE (Bootstrap 5 + Modern UI)
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def get_demo_ui():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Sales Copilot — Рабочий Прототип</title>

    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">

    <style>
        :root {
            --bs-primary-rgb: 13, 110, 253;
            --card-radius: 16px;
        }
        body {
            background-color: #f3f5f9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #2b3445;
        }
        .navbar-custom {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 1rem 0;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        .card-custom {
            border: 1px solid rgba(0,0,0,0.06);
            border-radius: var(--card-radius);
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
        .pitch-box {
            background: #f8fafc;
            border-left: 4px solid #3b82f6;
            border-radius: 0 12px 12px 0;
            padding: 1.25rem;
        }
        .vacancy-card {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 1rem;
            background: #ffffff;
            margin-bottom: 0.75rem;
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
                <span class="badge bg-success bg-opacity-20 text-success px-3 py-2 rounded-pill border border-success border-opacity-20">
                    <i class="bi bi-broadcast me-1"></i> Live Prototype
                </span>
            </div>
        </div>
    </nav>

    <div class="container mb-5">
        
        <!-- Панель поиска -->
        <div class="card card-custom p-4 mb-4">
            <h5 class="fw-bold mb-3 text-dark">
                <i class="bi bi-search text-primary me-2"></i> Обогащение профиля клиента для менеджера по продажам
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
                        <i class="bi bi-stars"></i> Запустить AI Ассистент
                    </button>
                </div>
            </div>
            
            <div class="d-flex align-items-center gap-2 mt-3 text-muted small">
                <span class="fw-semibold">Быстрые примеры:</span>
                <button class="btn btn-sm btn-outline-secondary rounded-pill py-0 px-2" onclick="setQuery('7707083893')">Сбербанк</button>
                <button class="btn btn-sm btn-outline-secondary rounded-pill py-0 px-2" onclick="setQuery('7702070139')">Яндекс</button>
                <button class="btn btn-sm btn-outline-secondary rounded-pill py-0 px-2" onclick="setQuery('7710353606')">Т-Банк</button>
                <button class="btn btn-sm btn-outline-secondary rounded-pill py-0 px-2" onclick="setQuery('7709257050')">1С</button>
            </div>
        </div>

        <!-- Прелоадер -->
        <div id="loader" class="text-center py-5 d-none">
            <div class="spinner-border text-primary" style="width: 3.5rem; height: 3.5rem;" role="status"></div>
            <h5 class="fw-semibold mt-3 text-dark">AI Копилот собирает данные...</h5>
            <p class="text-muted">Запрос юридических реквизитов DaData & Анализ вакансий hh.ru</p>
        </div>

        <!-- Область результатов -->
        <div id="resultsContent" class="d-none">
            
            <!-- AI Copilot Card -->
            <div class="card card-custom p-4 mb-4 border-0 shadow-sm" style="background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);">
                <div class="d-flex justify-content-between align-items-start mb-3">
                    <div>
                        <span class="badge-source badge-ai mb-2 d-inline-block">
                            <i class="bi bi-cpu-fill me-1"></i> AI Sales Intelligence
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

                <!-- Рекомендуемый скрипт -->
                <div class="pitch-box mb-3">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="fw-bold text-primary"><i class="bi bi-chat-left-text-fill me-2"></i>Сгенерированный Pitch для первого звонка:</span>
                        <button class="btn btn-sm btn-outline-primary" onclick="copyPitch()"><i class="bi bi-copy me-1"></i> Скопировать</button>
                    </div>
                    <p class="mb-0 text-dark fs-6 lh-base" id="pitchText"></p>
                </div>

                <div class="row g-3">
                    <div class="col-md-7">
                        <h6 class="fw-bold text-secondary mb-2"><i class="bi bi-lightning-charge-fill text-warning me-1"></i>Выявленные боли и триггеры:</h6>
                        <ul id="triggersList" class="mb-0 ps-3 text-dark"></ul>
                    </div>
                    <div class="col-md-5">
                        <h6 class="fw-bold text-secondary mb-2"><i class="bi bi-check2-circle text-success me-1"></i>Рекомендуемые шаги (Next Steps):</h6>
                        <ul id="nextStepsList" class="list-unstyled mb-0 small text-muted"></ul>
                    </div>
                </div>

                <hr class="my-3 text-muted opacity-25">

                <div class="d-flex justify-content-between align-items-center">
                    <span class="text-muted small"><i class="bi bi-shield-check me-1"></i> Данные верифицированы AI Копилотом</span>
                    <button id="crmBtn" onclick="sendToCRM()" class="btn btn-success fw-semibold">
                        <i class="bi bi-plus-circle me-1"></i> Создать сделку в CRM
                    </button>
                </div>
            </div>

            <!-- Две колонки с источниками -->
            <div class="row g-4">
                
                <!-- DaData Column -->
                <div class="col-lg-6">
                    <div class="card card-custom h-100 p-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold mb-0 text-dark">
                                <i class="bi bi-building-check text-primary me-2"></i>Юридические данные
                            </h5>
                            <span class="badge-source badge-dadata">
                                <i class="bi bi-check-circle-fill me-1"></i> DaData (Live)
                            </span>
                        </div>
                        
                        <div class="table-responsive">
                            <table class="table table-borderless table-sm mb-0">
                                <tbody>
                                    <tr>
                                        <td class="text-muted fw-semibold" style="width: 40%;">ИНН / КПП:</td>
                                        <td class="fw-semibold text-dark" id="legalInnKpp">-</td>
                                    </tr>
                                    <tr>
                                        <td class="text-muted fw-semibold">ОГРН:</td>
                                        <td class="text-dark" id="legalOgrn">-</td>
                                    </tr>
                                    <tr>
                                        <td class="text-muted fw-semibold">Генеральный директор:</td>
                                        <td class="fw-bold text-primary" id="legalCeo">-</td>
                                    </tr>
                                    <tr>
                                        <td class="text-muted fw-semibold">Юридический адрес:</td>
                                        <td class="text-dark small" id="legalAddress">-</td>
                                    </tr>
                                    <tr>
                                        <td class="text-muted fw-semibold">Штат сотрудников:</td>
                                        <td class="text-dark" id="legalEmployees">-</td>
                                    </tr>
                                    <tr>
                                        <td class="text-muted fw-semibold">Статус:</td>
                                        <td><span class="badge bg-success bg-opacity-10 text-success fw-bold" id="legalStatus">ДЕЙСТВУЮЩЕЕ</span></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- hh.ru Column -->
                <div class="col-lg-6">
                    <div class="card card-custom h-100 p-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold mb-0 text-dark">
                                <i class="bi bi-person-search text-danger me-2"></i>Найм & Вакансии
                            </h5>
                            <span class="badge-source badge-hh">
                                <i class="bi bi-cpu-fill me-1"></i> hh.ru (Mock Engine)
                            </span>
                        </div>

                        <div class="d-flex align-items-center justify-content-between mb-3 p-2 bg-light rounded-3">
                            <span class="text-muted small fw-semibold">Активных вакансий на поиске:</span>
                            <span class="badge bg-danger rounded-pill px-3 py-1 fs-6" id="vacanciesCount">0</span>
                        </div>

                        <div id="vacanciesContainer" class="vstack gap-2"></div>
                    </div>
                </div>

            </div>

        </div>

    </div>

    <!-- Уведомления Toast -->
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

        function setQuery(inn) {
            document.getElementById('searchInput').value = inn;
            runCopilotEnrichment();
        }

        function showToast(msg) {
            document.getElementById('toastMessage').innerText = msg;
            const toastEl = document.getElementById('liveToast');
            const toast = new bootstrap.Toast(toastEl);
            toast.show();
        }

        function copyPitch() {
            const pitch = document.getElementById('pitchText').innerText;
            navigator.clipboard.writeText(pitch);
            showToast('Скрипт обращения скопирован в буфер обмена!');
        }

        async function runCopilotEnrichment() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) return;

            document.getElementById('resultsContent').classList.add('d-none');
            document.getElementById('loader').classList.remove('d-none');

            try {
                const response = await fetch(`/api/copilot/enrich-company?inn=${encodeURIComponent(query)}`);
                if (!response.ok) {
                    throw new Error('Компания не найдена или ошибка API');
                }

                const data = await response.json();
                currentEnrichedData = data;

                document.getElementById('loader').classList.add('d-none');
                document.getElementById('resultsContent').classList.remove('d-none');

                const legal = data.dadata_legal_profile;
                const hh = data.hh_recruitment_profile;
                const ai = data.sales_ai_insights;

                // Header & Score
                document.getElementById('companyNameHeader').innerText = legal.name;
                document.getElementById('scoreCircle').innerText = ai.lead_score;
                document.getElementById('pitchText').innerText = ai.recommended_pitch;

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

                // DaData Fill
                document.getElementById('legalInnKpp').innerText = `${legal.inn} / ${legal.kpp}`;
                document.getElementById('legalOgrn').innerText = legal.ogrn;
                document.getElementById('legalCeo').innerText = legal.ceo;
                document.getElementById('legalAddress').innerText = legal.address;
                document.getElementById('legalEmployees').innerText = legal.employee_count ? `${legal.employee_count} чел.` : 'Данные отсутствуют';

                // hh.ru Fill
                document.getElementById('vacanciesCount').innerText = hh.open_vacancies_count;
                const vacContainer = document.getElementById('vacanciesContainer');
                vacContainer.innerHTML = '';

                hh.vacancies.forEach(v => {
                    const el = document.createElement('div');
                    el.className = 'vacancy-card';
                    el.innerHTML = `
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="fw-bold text-dark">${v.title}</div>
                            <span class="badge bg-primary bg-opacity-10 text-primary">${v.salary}</span>
                        </div>
                        <p class="small text-muted mb-2 mt-1">${v.requirement}</p>
                        <div class="d-flex justify-content-between align-items-center pt-2 border-top border-light small text-muted">
                            <span><i class="bi bi-person me-1"></i> ${v.hr_name}</span>
                            <a href="mailto:${v.hr_email}" class="text-decoration-none"><i class="bi bi-envelope me-1"></i> Написать HR</a>
                        </div>
                    `;
                    vacContainer.appendChild(el);
                });

                // Reset CRM button
                const crmBtn = document.getElementById('crmBtn');
                crmBtn.disabled = false;
                crmBtn.className = 'btn btn-success fw-semibold';
                crmBtn.innerHTML = '<i class="bi bi-plus-circle me-1"></i> Создать сделку в CRM';

            } catch (err) {
                alert('Ошибка: ' + err.message);
                document.getElementById('loader').classList.add('d-none');
            }
        }

        async function sendToCRM() {
            if (!currentEnrichedData) return;

            const crmBtn = document.getElementById('crmBtn');
            crmBtn.disabled = true;
            crmBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></i> Сохранение в CRM...';

            const payload = {
                company_name: currentEnrichedData.dadata_legal_profile.name,
                inn: currentEnrichedData.dadata_legal_profile.inn,
                ceo_name: currentEnrichedData.dadata_legal_profile.ceo,
                pitch: currentEnrichedData.sales_ai_insights.recommended_pitch,
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
                crmBtn.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Сделка создана в CRM!';
                showToast(`${result.message} (ID: ${result.deal_id})`);
            } catch (e) {
                alert('Ошибка создания сделки: ' + e);
                crmBtn.disabled = false;
            }
        }

        window.onload = runCopilotEnrichment;
    </script>
</body>
</html>
    """
