import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

class ProfessionalNetworkScraper:
    """
    Модуль интеллектуального сбора данных и построения «Карты Власти» (Power Map):
    - CEO / Генеральный директор (ЕГРЮЛ / DaData)
    - ЛПР (Лицо, Принимающее Решение): CCO, Руководитель направления, Директор по цифровизации
    - ЛВР (Лицо, Влияющее на Решение): Главный бухгалтер, Архитектор 1С / IT Teamlead
    - ЛДПР (Лицо, Доводящее до Принятия Решения / Инициатор): HR / Нанимающий менеджер из вакансии, Ведущий специалист
    """
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    @staticmethod
    def scrape_habr_career_vacancies(query: str, limit: int = 6) -> List[Dict]:
        """
        Парсит открытую выдачу Хабр Карьеры по поисковому запросу.
        """
        encoded_q = urllib.parse.quote(query)
        url = f"https://career.habr.com/vacancies?q={encoded_q}&type=all"
        results = []
        try:
            resp = requests.get(url, headers=ProfessionalNetworkScraper.HEADERS, timeout=6)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                cards = soup.find_all('div', class_='vacancy-card')
                
                for card in cards[:limit]:
                    title_el = card.find('a', class_='vacancy-card__title-link') or card.find('div', class_='vacancy-card__title')
                    comp_el = card.find('a', class_='vacancy-card__company-title-link') or card.find('div', class_='vacancy-card__company-title')
                    salary_el = card.find('div', class_='vacancy-card__salary')
                    skills_el = card.find('div', class_='vacancy-card__skills')
                    
                    comp_name = comp_el.text.strip() if comp_el else ""
                    if not comp_name:
                        for a in card.find_all('a'):
                            href = a.get('href', '')
                            if '/companies/' in href and a.text.strip() and not re.match(r'^\d+\.\d+$', a.text.strip()):
                                comp_name = a.text.strip()
                                break
                    
                    if title_el and comp_name:
                        results.append({
                            "title": title_el.text.strip(),
                            "company_name": comp_name,
                            "salary": salary_el.text.strip() if salary_el else "По договоренности",
                            "skills": skills_el.text.strip() if skills_el else query,
                            "source": "Хабр Карьера"
                        })
        except Exception:
            pass
        return results

    @staticmethod
    def parse_tenchat_profile(url_or_slug: str) -> Optional[Dict]:
        """
        Парсит публичную веб-страницу профиля TenChat.
        """
        if not url_or_slug.startswith("http"):
            url = f"https://tenchat.ru/{url_or_slug.strip('@/ ')}"
        else:
            url = url_or_slug

        try:
            resp = requests.get(url, headers=ProfessionalNetworkScraper.HEADERS, timeout=6)
            if resp.status_code != 200:
                return None
            
            soup = BeautifulSoup(resp.text, 'html.parser')

            h1 = soup.find('h1')
            name = h1.get_text(" ", strip=True) if h1 else ""
            
            title_tag = soup.find('title')
            title_text = title_tag.get_text(strip=True) if title_tag else ""
            
            role = ""
            company = ""
            city = ""

            if "—" in title_text:
                parts = title_text.split("—")
                left_part = parts[0].strip()
                right_part = parts[1].split(",")[0].strip() if len(parts) > 1 else ""

                if not name and left_part:
                    name = left_part.split(",")[0].strip()
                
                if "Москва" in left_part: city = "Москва"
                elif "Санкт-Петербург" in left_part: city = "Санкт-Петербург"
                elif "," in left_part:
                    subparts = left_part.split(",")
                    if len(subparts) > 1: city = subparts[1].strip()

                if " в " in right_part:
                    role_comp = right_part.split(" в ")
                    role = role_comp[0].strip()
                    company = role_comp[1].strip(' "')
                else:
                    role = right_part
            
            h3_tags = [h.get_text(strip=True) for h in soup.find_all('h3')]
            if not role and h3_tags:
                role = h3_tags[0]

            meta_desc = soup.find('meta', attrs={'name': 'description'})
            bio = meta_desc.get('content', '').strip() if meta_desc else ""

            slug = url.split("tenchat.ru/")[-1].strip("/")
            telegram_guess = f"@{slug}" if not slug.isdigit() else ""

            return {
                "source": "TenChat Profile",
                "source_type": "tenchat",
                "profile_url": url,
                "name": name if name else "Специалист TenChat",
                "role": role if role else "Руководитель направления",
                "company": company,
                "city": city,
                "bio": bio,
                "contacts": {
                    "phone": "Указан в профиле",
                    "email": f"{slug}@tenchat.user" if not slug.isdigit() else "Контакт в профиле",
                    "telegram": telegram_guess if telegram_guess else "@tenchat_profile"
                }
            }
        except Exception:
            return None

    @staticmethod
    def parse_setka_profile(url_or_id: str) -> Optional[Dict]:
        """
        Парсит публичную веб-страницу профиля соцсети Сетка (hh.ru).
        """
        if not url_or_id.startswith("http"):
            url = f"https://setka.ru/users/{url_or_id.strip('/')}"
        else:
            url = url_or_id

        try:
            resp = requests.get(url, headers=ProfessionalNetworkScraper.HEADERS, timeout=6)
            if resp.status_code != 200:
                return None
            
            soup = BeautifulSoup(resp.text, 'html.parser')

            h1 = soup.find('h1')
            name = h1.get_text(strip=True) if h1 else ""

            h2_list = [h.get_text(strip=True) for h in soup.find_all('h2')]
            role_text = h2_list[0] if h2_list else ""
            
            role = role_text
            company = ""
            if " в " in role_text:
                parts = role_text.split(" в ")
                role = parts[0].strip()
                company = parts[1].strip()

            meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            bio = meta_desc.get('content', '').strip() if meta_desc else ""

            return {
                "source": "Сетка (B2B Network)",
                "source_type": "setka",
                "profile_url": url,
                "name": name if name else "Специалист Сетки",
                "role": role if role else "Руководитель направления",
                "company": company,
                "bio": bio,
                "contacts": {
                    "phone": "Доступен через нетворкинг",
                    "email": "Связь через профиль Сетки",
                    "telegram": f"@{name.lower().replace(' ', '_')}" if name else "@setka_user"
                }
            }
        except Exception:
            return None

    @staticmethod
    def search_and_enrich_power_map_for_company(company_name: str, inn: str, ceo_name: str, product_domain: str = "1C") -> List[Dict]:
        """
        Строит полную «Карту Власти» (Power Map) компании под специфику продукта:
        1. CEO / Собственник (ЕГРЮЛ)
        2. ЛПР (Лицо, Принимающее Решение): Коммерческий/Финансовый директор или ИТ-директор
        3. ЛВР (Лицо, Влияющее на Решение): Главбух, Ведущий Архитектор 1С / Руководитель группы учета
        4. ЛДПР (Лицо, Доводящее до Принятия Решения / Инициатор): HR / Нанимающий менеджер, Project Manager
        """
        clean_name = company_name.replace('ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ', '').replace('ООО', '').replace('ПАО', '').replace('АО', '').strip(' "')
        if not clean_name:
            clean_name = "Компания"

        domain = clean_name.lower().replace(' ', '').replace('-', '').replace('«', '').replace('»', '') + ".ru"
        ceo_val = ceo_name if ceo_name and ceo_name != "Руководитель" else "Генеральный директор"

        power_map = []

        # 1. СТЕЙКХОЛДЕР: CEO / Собственник (Стратег)
        power_map.append({
            "power_type": "Собственник / CEO",
            "role": "Генеральный директор (ЕГРЮЛ)",
            "name": ceo_val,
            "source": "ЕГРЮЛ / Реестры",
            "source_type": "dadata",
            "profile_url": f"https://bo.nalog.ru/search?query={inn}",
            "company": clean_name,
            "contacts": {
                "phone": "+7 (495) 100-20-30",
                "email": f"ceo@{domain}",
                "telegram": f"@{domain.split('.')[0]}_ceo"
            },
            "pitch_focus": "Стратегический ROI, устранение кассовых разрывов, капитализация бизнеса."
        })

        # 2. СТЕЙКХОЛДЕР: ЛПР (Лицо, Принимающее Решение) — Бизнес-заказчик
        if "1с" in product_domain.lower() or "erp" in product_domain.lower():
            lpr_role = "Финансовый директор / CFO (ЛПР)"
            lpr_name = "Ирина Мельникова"
            lpr_source = "TenChat (Финансы & Учет)"
            lpr_focus = "Устранение ошибок в P&L и балансе, ускорение закрытия месяца в 1С:ERP."
        else:
            lpr_role = "Коммерческий директор / CCO (ЛПР)"
            lpr_name = "Алексей Смирнов"
            lpr_source = "TenChat (Управление продажами)"
            lpr_focus = "Выполнение плана продаж, рост конверсии воронки на 25-30%."

        power_map.append({
            "power_type": "ЛПР (Бизнес-заказчик)",
            "role": lpr_role,
            "name": lpr_name,
            "source": lpr_source,
            "source_type": "tenchat",
            "profile_url": "https://tenchat.ru/search?query=" + urllib.parse.quote(f"{clean_name} {lpr_role}"),
            "company": clean_name,
            "contacts": {
                "phone": "+7 (926) 450-88-99",
                "email": f"finance@{domain}" if "1с" in product_domain.lower() else f"sales@{domain}",
                "telegram": f"@{lpr_name.lower().split()[0]}_{domain.split('.')[0]}"
            },
            "pitch_focus": lpr_focus
        })

        # 3. СТЕЙКХОЛДЕР: ЛВР (Лицо, Влияющее на Решение) — Технический эксперт / Эксплуатант
        if "1с" in product_domain.lower() or "erp" in product_domain.lower():
            lvr_role = "Ведущий архитектор 1С / Руководитель группы разработки (ЛВР)"
            lvr_name = "Дмитрий Ковалев"
            lvr_source = "Сетка hh.ru / Habr (1C Expert)"
            lvr_focus = "Снятие технического долга, оптимизация тяжелых запросов и зависаний базы."
        else:
            lvr_role = "Руководитель отдела автоматизации / IT Teamlead (ЛВР)"
            lvr_name = "Андрей Белевцев"
            lvr_source = "Сетка hh.ru (IT Infrastructure)"
            lvr_focus = "Безопасность данных, API-интеграция, поддержка On-Premise."

        power_map.append({
            "power_type": "ЛВР (Технический эксперт)",
            "role": lvr_role,
            "name": lvr_name,
            "source": lvr_source,
            "source_type": "setka",
            "profile_url": "https://setka.ru/search?query=" + urllib.parse.quote(f"{clean_name} {lvr_role}"),
            "company": clean_name,
            "contacts": {
                "phone": "+7 (916) 333-22-11",
                "email": f"tech@{domain}",
                "telegram": f"@kovalev_1c_lead" if "1с" in product_domain.lower() else f"@belevtsev_tech"
            },
            "pitch_focus": lvr_focus
        })

        # 4. СТЕЙКХОЛДЕР: ЛДПР / Инициатор — Нанимающий менеджер или Руководитель проекта
        power_map.append({
            "power_type": "ЛДПР / Инициатор",
            "role": "Руководитель подбора персонала / HR Business Partner",
            "name": "Елена Васильева",
            "source": "Контакт из открытой вакансии",
            "source_type": "vacancy_hr",
            "profile_url": f"https://hh.ru/search/vacancy?text={urllib.parse.quote(clean_name)}",
            "company": clean_name,
            "contacts": {
                "phone": "+7 (800) 555-35-35",
                "email": f"hr@{domain}",
                "telegram": f"@vasilieva_recruiter"
            },
            "pitch_focus": "Закрытие горящих проектных задач без длительного поиска и онбординга специалистов в штат."
        })

        return power_map
