import os
import json
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AI Sales Copilot Demo API")

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
    if response.status_code != 200:
        # Попробуем общий поиск по названию если findById не дал совпадений
        url_suggest = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"
        response = requests.post(url_suggest, json=payload, headers=headers, timeout=10)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Ошибка при запросе к DaData")
    
    return response.json()


@app.get("/api/dadata/address")
def clean_address(address: str = Query(..., description="Адрес для проверки")):
    """
    Реальная стандартизация и проверка адреса через DaData Suggestions.
    """
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {DADATA_API_KEY}"
    }
    payload = {"query": address}
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Ошибка DaData Address API")
    return response.json()

# --------------------------------------------------------------------------
# 2. HH.RU MOCK INTEGRATION (Имитация API hh.ru)
# --------------------------------------------------------------------------

MOCK_VACANCIES = [
    {
        "id": "1001",
        "name": "Senior Python Developer / Lead Backend",
        "salary": {"from": 280000, "to": 350000, "currency": "RUR", "gross": False},
        "employer": {
            "id": "7707083893",
            "name": "ПАО Сбербанк",
            "alternate_url": "https://hh.ru/employer/3529",
            "trusted": True
        },
        "area": {"name": "Москва"},
        "published_at": "2026-08-17T10:30:00+0300",
        "snippet": {
            "requirement": "Опыт разработки на Python от 4-х лет, FastAPI/Django, PostgreSQL, Kafka, Kubernetes.",
            "responsibility": "Проектирование архитектуры микросервисов, оптимизация высоконагруженных систем."
        },
        "contacts": {
            "name": "Анна Петрова",
            "email": "hr-tech@sberbank.ru",
            "phones": [{"country": "7", "city": "495", "number": "1234567"}]
        },
        "experience": {"name": "От 3 до 6 лет"},
        "employment": {"name": "Полная занятость"},
        "schedule": {"name": "Удаленная работа"}
    },
    {
        "id": "1002",
        "name": "Менеджер по продажам B2B (AI & IT-решения)",
        "salary": {"from": 150000, "to": 300000, "currency": "RUR", "gross": True},
        "employer": {
            "id": "7702070139",
            "name": "Яндекс",
            "alternate_url": "https://hh.ru/employer/1740",
            "trusted": True
        },
        "area": {"name": "Москва"},
        "published_at": "2026-08-18T09:15:00+0300",
        "snippet": {
            "requirement": "Опыт B2B продаж сложных IT продуктов от 2 лет, понимание облачных сервисов и LLM/AI технологий.",
            "responsibility": "Активные продажи корпоративным клиентам, проведение пресейлов, выстраивание долгосрочных отношений."
        },
        "contacts": {
            "name": "Михаил Сергеев",
            "email": "b2b-recruitment@yandex-team.ru",
            "phones": [{"country": "7", "city": "495", "number": "7397000"}]
        },
        "experience": {"name": "От 1 года до 3 лет"},
        "employment": {"name": "Полная занятость"},
        "schedule": {"name": "Гибридный график"}
    },
    {
        "id": "1003",
        "name": "Руководитель отдела продаж (Sales Director)",
        "salary": {"from": 300000, "to": 500000, "currency": "RUR", "gross": False},
        "employer": {
            "id": "7710353606",
            "name": "Т-Банк (Тинькофф)",
            "alternate_url": "https://hh.ru/employer/78638",
            "trusted": True
        },
        "area": {"name": "Санкт-Петербург"},
        "published_at": "2026-08-16T14:20:00+0300",
        "snippet": {
            "requirement": "Успешный опыт управления отделом продаж от 15 человек в IT/Fintech сфере. Владение методологиями SPIN sales и MEDDPICC.",
            "responsibility": "Выполнение плана продаж, внедрение AI-инструментов автоматизации звонков и сделок."
        },
        "contacts": {
            "name": "Елена Соколова",
            "email": "e.sokolova@tbank.ru",
            "phones": [{"country": "7", "city": "812", "number": "9876543"}]
        },
        "experience": {"name": "Более 6 лет"},
        "employment": {"name": "Полная занятость"},
        "schedule": {"name": "Полный день"}
    }
]

@app.get("/api/hh/vacancies")
def search_hh_vacancies(text: str = Query("", description="Текст поиска вакансий")):
    """
    Имитация API hh.ru GET /vacancies
    """
    filtered = MOCK_VACANCIES
    if text:
        text_lower = text.lower()
        filtered = [
            v for v in MOCK_VACANCIES
            if text_lower in v["name"].lower()
            or text_lower in v["employer"]["name"].lower()
            or text_lower in v["snippet"]["requirement"].lower()
        ]
    
    return {
        "items": filtered,
        "found": len(filtered),
        "pages": 1,
        "per_page": 20,
        "page": 0,
        "mock_info": {
            "status": "simulated",
            "note": "Имитация API hh.ru (готов к переключению на реальный OAuth token)"
        }
    }

# --------------------------------------------------------------------------
# 3. AI SALES COPILOT ENRICHMENT API
# --------------------------------------------------------------------------

@app.get("/api/copilot/enrich-company")
def enrich_company_profile(inn: str = Query(..., description="ИНН компании")):
    """
    Агрегирует данные DaData (юридический профиль, адрес, ФИО директора)
    и данные hh.ru (открытые вакансии, контакты HR, потребности в кадрах).
    """
    # 1. Запрос в DaData по ИНН
    dadata_res = search_company(query=inn)
    company_info = {}
    if dadata_res.get("suggestions"):
        data = dadata_res["suggestions"][0]["data"]
        value = dadata_res["suggestions"][0]["value"]
        finance = data.get("finance") or {}
        company_info = {
            "inn": data.get("inn"),
            "kpp": data.get("kpp"),
            "ogrn": data.get("ogrn"),
            "name": value,
            "full_name": data.get("name", {}).get("full_with_opf") if isinstance(data.get("name"), dict) else None,
            "ceo": data.get("management", {}).get("name") if isinstance(data.get("management"), dict) else None,
            "address": data.get("address", {}).get("value") if isinstance(data.get("address"), dict) else None,
            "status": data.get("state", {}).get("status") if isinstance(data.get("state"), dict) else None,
            "employee_count": data.get("employee_count"),
            "revenue": finance.get("revenue") if isinstance(finance, dict) else None
        }
    
    # 2. Запрос в мок hh.ru по названию компании или ИНН
    comp_name = company_info.get("name", "")
    hh_res = search_hh_vacancies(text=comp_name)
    vacancies = hh_res.get("items", [])
    
    # 3. Формирование скоринга и AI-аналитики для отдела продаж
    pain_points = []
    if len(vacancies) > 0:
        pain_points.append(f"Активно нанимают сотрудников ({len(vacancies)} вакансий на hh.ru). Есть бюджет на развитие.")
    if any("AI" in v["snippet"]["requirement"] or "IT" in v["snippet"]["requirement"] for v in vacancies):
        pain_points.append("Внедряют IT & AI инновации в процессы продаж и разработки.")
    if company_info.get("employee_count") and company_info["employee_count"] > 100:
        pain_points.append("Крупный штат — высокая потребность в автоматизации коммуникаций.")
    
    return {
        "dadata_legal_profile": company_info,
        "hh_recruitment_profile": {
            "open_vacancies_count": len(vacancies),
            "vacancies": vacancies
        },
        "sales_ai_insights": {
            "lead_score": 88 if len(vacancies) > 0 else 60,
            "recommended_pitch": f"Здравствуйте, {company_info.get('ceo', 'коллега')}! Видим, что {company_info.get('name')} активно расширяет штат и ищет специалистов. Наш AI Sales Copilot поможет повысить конверсию отдела продаж и ускорить обработку лидов.",
            "insights": pain_points
        }
    }

# --------------------------------------------------------------------------
# 4. FRONTEND DEMO INTERFACE
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def get_demo_ui():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Sales Copilot — Интерактивное Демо</title>

    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">

    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
    <style>
        body { background-color: #f4f6f9; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }
        .hero-banner { background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%); color: white; padding: 2.5rem 0; margin-bottom: 2rem; border-radius: 0 0 1rem 1rem; }
        .card-custom { border: none; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); transition: all 0.2s; }
        .card-custom:hover { box-shadow: 0 6px 18px rgba(0,0,0,0.08); }
        .badge-status { font-size: 0.8rem; padding: 0.4em 0.8em; border-radius: 20px; }
        .source-tag { font-size: 0.75rem; text-transform: uppercase; font-weight: bold; letter-spacing: 0.5px; }
        .tag-dadata { background-color: #e7f1ff; color: #0d6efd; border: 1px solid #b6d4fe; }
        .tag-hh { background-color: #ffe6e6; color: #d63384; border: 1px solid #f5c2c7; }
        .tag-ai { background-color: #e0cffc; color: #6610f2; border: 1px solid #c5b3f9; }
        pre { background-color: #212529; color: #f8f9fa; padding: 1rem; border-radius: 8px; font-size: 0.85rem; }
    </style>
</head>
<body>

    <div class="hero-banner shadow-sm">
        <div class="container">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h1 class="fw-bold mb-1"><i class="bi bi-robot me-2"></i>AI Sales Copilot</h1>
                    <p class="lead mb-0 opacity-90">Единый профиль клиента: Реальные данные DaData + Имитация hh.ru</p>
                </div>
                <span class="badge bg-light text-primary px-3 py-2 rounded-pill fw-semibold">
                    <i class="bi bi-check-circle-fill text-success me-1"></i> Демо-режим
                </span>
            </div>
        </div>
    </div>

    <div class="container mb-5">
        <!-- Поисковая панель -->
        <div class="card card-custom p-4 mb-4">
            <h5 class="fw-bold mb-3"><i class="bi bi-search me-2 text-primary"></i>Быстрый обогащенный поиск контрагента</h5>
            <div class="row g-2">
                <div class="col-md-8">
                    <input type="text" id="searchInput" class="form-control form-control-lg" placeholder="Введите ИНН или название компании (например: 7707083893 или Сбербанк)..." value="7707083893">
                </div>
                <div class="col-md-4">
                    <button onclick="searchClient()" class="btn btn-primary btn-lg w-100 fw-semibold">
                        <i class="bi bi-magic me-1"></i> Обогатить профиль AI
                    </button>
                </div>
            </div>
            <div class="mt-2 text-muted small">
                <i class="bi bi-info-circle me-1"></i> Быстрые примеры ИНН: 
                <a href="#" onclick="setQuery('7707083893')" class="text-decoration-none ms-1">7707083893 (Сбер)</a>, 
                <a href="#" onclick="setQuery('7702070139')" class="text-decoration-none ms-1">7702070139 (Яндекс)</a>, 
                <a href="#" onclick="setQuery('7710353606')" class="text-decoration-none ms-1">7710353606 (Т-Банк)</a>
            </div>
        </div>

        <!-- Результаты исследования -->
        <div id="loading" class="text-center py-5 d-none">
            <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;"></div>
            <p class="mt-3 text-muted fw-semibold">Загрузка юридических данных из DaData и актуальных вакансий из hh.ru...</p>
        </div>

        <div id="resultsArea" class="d-none">
            <div class="row g-4">
                <!-- Карта AI подсказок для продаж -->
                <div class="col-12">
                    <div class="card card-custom p-4 border-start border-4 border-primary bg-white">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <span class="source-tag tag-ai px-2 py-1 rounded">
                                <i class="bi bi-stars me-1"></i> AI Sales Insight
                            </span>
                            <div class="text-end">
                                <small class="text-muted">Lead Score:</small>
                                <span id="leadScore" class="badge bg-success ms-1 fs-6">88 / 100</span>
                            </div>
                        </div>
                        <h4 class="fw-bold text-dark" id="compTitle">Название компании</h4>
                        <div class="alert alert-light border mt-3 mb-3">
                            <h6 class="fw-bold text-primary mb-2"><i class="bi bi-chat-quote-fill me-2"></i>Рекомендуемый скрипт обращения (Pitch):</h6>
                            <p id="recommendedPitch" class="mb-0 fst-italic text-dark fs-6"></p>
                        </div>
                        <h6 class="fw-bold mb-2 text-secondary">Ключевые триггеры для продажи:</h6>
                        <ul id="insightsList" class="mb-0 ps-3 text-dark"></ul>
                    </div>
                </div>

                <!-- Блок DaData -->
                <div class="col-md-6">
                    <div class="card card-custom h-100 p-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold mb-0 text-dark">
                                <i class="bi bi-building me-2 text-primary"></i>Юридический профиль
                            </h5>
                            <span class="source-tag tag-dadata px-2 py-1 rounded">
                                <i class="bi bi-patch-check-fill me-1"></i> DaData (Live)
                            </span>
                        </div>
                        <hr class="text-muted opacity-25">
                        <div class="mb-2"><strong>ИНН / КПП:</strong> <span id="dadataInn" class="text-muted"></span></div>
                        <div class="mb-2"><strong>ОГРН:</strong> <span id="dadataOgrn" class="text-muted"></span></div>
                        <div class="mb-2"><strong>Руководитель (CEO):</strong> <span id="dadataCeo" class="text-muted fw-semibold"></span></div>
                        <div class="mb-2"><strong>Юридический адрес:</strong> <span id="dadataAddress" class="text-muted"></span></div>
                        <div class="mb-2"><strong>Статус:</strong> <span id="dadataStatus" class="badge bg-success bg-opacity-10 text-success">ДЕЙСТВУЮЩЕЕ</span></div>
                        <div class="mb-2"><strong>Численность сотрудников:</strong> <span id="dadataCount" class="text-muted"></span></div>
                    </div>
                </div>

                <!-- Блок hh.ru -->
                <div class="col-md-6">
                    <div class="card card-custom h-100 p-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold mb-0 text-dark">
                                <i class="bi bi-briefcase me-2 text-danger"></i>Найм & Потребности
                            </h5>
                            <span class="source-tag tag-hh px-2 py-1 rounded">
                                <i class="bi bi-cpu me-1"></i> hh.ru (Mock Service)
                            </span>
                        </div>
                        <hr class="text-muted opacity-25">
                        <div class="mb-3">
                            <strong>Активных вакансий:</strong> 
                            <span id="hhVacanciesCount" class="badge bg-danger rounded-pill ms-1">0</span>
                        </div>
                        <div id="vacanciesList" class="vstack gap-2"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function setQuery(inn) {
            document.getElementById('searchInput').value = inn;
            searchClient();
        }

        async function searchClient() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) return;

            document.getElementById('resultsArea').classList.add('d-none');
            document.getElementById('loading').classList.remove('d-none');

            try {
                const response = await fetch(`/api/copilot/enrich-company?inn=${encodeURIComponent(query)}`);
                const data = await response.json();

                document.getElementById('loading').classList.add('d-none');
                document.getElementById('resultsArea').classList.remove('d-none');

                // Fill AI Insights
                const legal = data.dadata_legal_profile;
                const hh = data.hh_recruitment_profile;
                const ai = data.sales_ai_insights;

                document.getElementById('compTitle').innerText = legal.name || 'Компания не найдена';
                document.getElementById('leadScore').innerText = `${ai.lead_score} / 100`;
                document.getElementById('recommendedPitch').innerText = ai.recommended_pitch;

                const insightsList = document.getElementById('insightsList');
                insightsList.innerHTML = '';
                ai.insights.forEach(item => {
                    const li = document.createElement('li');
                    li.className = 'mb-1';
                    li.innerText = item;
                    insightsList.appendChild(li);
                });

                // Fill DaData
                document.getElementById('dadataInn').innerText = `${legal.inn || '-'} / ${legal.kpp || '-'}`;
                document.getElementById('dadataOgrn').innerText = legal.ogrn || '-';
                document.getElementById('dadataCeo').innerText = legal.ceo || 'Не указан';
                document.getElementById('dadataAddress').innerText = legal.address || '-';
                document.getElementById('dadataCount').innerText = legal.employee_count ? `${legal.employee_count} человек` : 'Не указано';

                // Fill hh.ru
                document.getElementById('hhVacanciesCount').innerText = hh.open_vacancies_count;
                const vacList = document.getElementById('vacanciesList');
                vacList.innerHTML = '';

                if (hh.vacancies.length === 0) {
                    vacList.innerHTML = '<div class="text-muted italic">Открытых вакансий в имитации hh.ru не найдено</div>';
                } else {
                    hh.vacancies.forEach(v => {
                        const salary = v.salary ? `${v.salary.from || ''} - ${v.salary.to || ''} ${v.salary.currency}` : 'З/П не указана';
                        const item = document.createElement('div');
                        item.className = 'p-2 border rounded bg-light';
                        item.innerHTML = `
                            <div class="fw-semibold text-dark">${v.name}</div>
                            <div class="small text-success fw-bold">${salary}</div>
                            <div class="small text-muted mt-1"><i class="bi bi-person-badge me-1"></i> Контакт: ${v.contacts.name} (${v.contacts.email})</div>
                        `;
                        vacList.appendChild(item);
                    });
                }

            } catch (err) {
                alert('Ошибка получения данных: ' + err);
                document.getElementById('loading').classList.add('d-none');
            }
        }

        // Автоматический запуск при загрузке
        window.onload = searchClient;
    </script>
</body>
</html>
    """
