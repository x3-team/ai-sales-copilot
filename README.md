# Sales Copilot

Локальный диспетчер спроса: оффер → компании с наймом или закупкой → ИНН → с кого начать → черновик письма. Письмо отправляете сами.

Render не используется.

## Запуск

```bash
python3 -m pip install -r requirements.txt
cp env.example .env   # заполните ключи, файл не коммитится
./scripts/run_local.sh
```

Кабинет: http://127.0.0.1:8000/app  
Карточка: `GET /api/copilot/company-card?inn=7706729736`

Память: SQLite в `data/` (каталог в `.gitignore`). `DEMO_MODE=0`.

## Ключи (локальный `.env`)

- `DADATA_API_KEY` — директор и поиск по названию; при открытии карточки закупки подтягивает CEO из ЕГРЮЛ
- `HH_USER_AGENT` / `HH_ACCESS_TOKEN` — скан вакансий и опционально резюме
- `TENDERLAND_API_KEY` — закупки (тест 3 дня на tenderland.ru, нужен API-ключ)
- `GOSPLAN_API_BASE=https://v2test.gosplan.info` — **по умолчанию в env.example**, test API ЕИС без ключа (лимиты, возможен 429)
- `GOSPLAN_API_KEY` — опционально для prod (`v2.gosplan.info`, trial 7 дней)
- ЕИС SOAP не подключаем в первом слое: Gosplan REST дешевле по интеграции
- Карточка закупки даёт go / no-go / review по офферу и НМЦК — это не прогноз победы
- Оффер продавца сохраняется в SQLite (`data/`) и переживает перезапуск
