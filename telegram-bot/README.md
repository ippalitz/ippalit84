# Telegram-бот продаж автозапчастей

Бот продает автозапчасти через Telegram и использует уже существующую интеграцию Adeo XML API.

## Что умеет

- Проверяет наличие по номеру детали/OEM через Adeo API.
- Показывает клиенту название, бренд, цену, наличие, срок и склад/поставщика.
- Добавляет кнопку `Купить` под каждым предложением.
- Сохраняет покупки в `data/purchases.csv`.
- Собирает заявку, если клиент не знает номер детали/OEM.
- Сохраняет такие заявки в `data/leads.csv`.
- Уведомляет менеджера в Telegram.
- Опционально пишет заявки и покупки в Google Sheets.

## Бесплатная архитектура

Для бесплатного Render используется Web Service + Telegram webhook. Telegram отправляет сообщения на HTTPS-адрес сервиса, поэтому не нужен платный Background Worker.

Важно: free-план Render может засыпать после простоя. Telegram webhook разбудит сервис, но первый ответ после сна может идти с задержкой.

## Переменные окружения

Обязательные:

```env
TELEGRAM_TOKEN=токен_бота
MANAGER_CHAT_ID=telegram_id_менеджера
ADEO_LOGIN=логин_adeo
ADEO_PASSWORD=пароль_adeo
ADEO_URL_PRICES=https://xml.adeo.pro/pricedetails2.php
WEBHOOK_URL=https://your-render-service.onrender.com
WEBHOOK_SECRET=любая_секретная_строка
```

Опциональные:

```env
MARKUP_PERCENT=30
MAX_OFFERS_PER_QUERY=5
GOOGLE_SHEETS_ENABLED=0
GOOGLE_SHEET_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
```

## Локальный запуск для теста

```bash
pip install -r requirements.txt
python bot.py
```

## Бесплатный деплой на Render

1. Создайте `New` -> `Web Service`.
2. Выберите репозиторий `ippalitz/ippalit84`.
3. Root Directory: `telegram-bot`.
4. Runtime: Docker.
5. Plan: Free.
6. Добавьте переменные окружения из `.env.example`.
7. Создайте сервис.
8. После создания скопируйте URL сервиса Render.
9. Добавьте/обновите `WEBHOOK_URL` этим URL.
10. Перезапустите сервис.
11. В логах должно быть `Telegram webhook configured`.

## Проверка

1. Напишите боту `/start`.
2. Отправьте номер детали, например `2108-3501800`.
3. Проверьте, что появились предложения Adeo и кнопки `Купить`.
4. Нажмите `Купить` и проверьте уведомление менеджеру.
5. Нажмите `Не знаю номер детали` и пройдите анкету.
