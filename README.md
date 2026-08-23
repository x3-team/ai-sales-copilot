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

- `DADATA_API_KEY` — директор и поиск по названию
- `HH_USER_AGENT` / `HH_ACCESS_TOKEN` — скан вакансий и опционально резюме
- ЕИС getDocsIP — отдельный токен, когда подключим живой пакет закупок
