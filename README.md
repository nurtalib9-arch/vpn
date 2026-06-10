# VPN SaaS Bot

Telegram VPN-бот с полной SaaS-инфраструктурой.

## Стек

- **Bot**: aiogram 3, Redis FSM
- **API/Admin**: FastAPI + Uvicorn
- **DB**: PostgreSQL 15 + SQLAlchemy async + Alembic
- **VPN**: Marzban (VLESS/Reality)
- **Платежи**: YooKassa, CryptoBot, CloudPayments
- **Scheduler**: APScheduler

## Быстрый старт

```bash
# 1. Скопировать конфиг
cp .env.example .env
# Заполнить BOT_TOKEN, MARZBAN_*, платёжные ключи

# 2. Поднять инфраструктуру
docker-compose up -d postgres redis

# 3. Применить миграции
docker-compose run --rm bot alembic upgrade head

# 4. Запустить всё
docker-compose up -d
```

## Структура

```
app/
├── main.py              # Telegram bot entrypoint
├── scheduler.py         # APScheduler entrypoint
├── webhooks.py          # Payment webhook handlers
├── core/                # Config, DB, Redis
├── models/              # SQLAlchemy ORM
├── services/            # Business logic
├── bot/
│   ├── handlers/        # Telegram message handlers
│   ├── keyboards/       # Reply/inline keyboards
│   └── middlewares/     # Ban, logging
├── admin/               # FastAPI admin panel
├── payments/            # YooKassa, CryptoBot, CloudPayments
└── utils/               # QR, helpers, validators
```

## Сервисы (Docker)

| Сервис | Порт | Описание |
|---|---|---|
| bot | — | Telegram bot (polling или webhook) |
| admin | 8000 | Admin panel (HTTP Basic Auth) |
| scheduler | — | APScheduler jobs |
| postgres | 5432 (local) | PostgreSQL |
| redis | 6379 (local) | Redis |

## Admin Panel

Доступ: `http://localhost:8000` (или ваш домен)  
Логин/пароль: из `.env` переменных `ADMIN_USERNAME` / `ADMIN_PASSWORD`

Разделы:
- **Дашборд** — ключевые метрики
- **Пользователи** — поиск, бан/разбан
- **Подписки** — статусы, фильтрация
- **Платежи** — история транзакций
- **Серверы** — добавление, вкл/выкл
- **Тарифы** — управление планами

## Webhook setup (production)

```bash
# В .env установить:
WEBHOOK_URL=https://your-domain.com/webhook/telegram

# Nginx пример:
# location /webhook/ { proxy_pass http://127.0.0.1:8001; }
```

## Переменные окружения

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота от @BotFather |
| `ADMIN_IDS` | Telegram ID администраторов (через запятую) |
| `MARZBAN_URL` | URL Marzban панели |
| `MARZBAN_USERNAME` | Логин в Marzban |
| `MARZBAN_PASSWORD` | Пароль в Marzban |
| `YOOKASSA_SHOP_ID` | ID магазина YooKassa |
| `YOOKASSA_SECRET_KEY` | Секретный ключ YooKassa |
| `CRYPTOBOT_TOKEN` | Токен CryptoBot API |
| `ADMIN_USERNAME` | Логин для веб-панели |
| `ADMIN_PASSWORD` | Пароль для веб-панели |
