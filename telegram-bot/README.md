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

## ИИ-менеджер через OdiRouter

ИИ включается только когда заданы обе переменные:

```env
ODIROUTER_API_KEY=ключ_из_личного_кабинета_odirouter
ODIROUTER_MODEL=точный_id_модели_из_каталога_odirouter
ODIROUTER_BASE_URL=https://api.odirouter.ai/v1
```

Что делает ИИ:

- отвечает на обычные вопросы клиента;
- принимает фотографии VIN и маркировки;
- повторяет распознанный VIN/OEM и просит подтверждение;
- просит отдельным сообщением отправить подтверждённый OEM, после чего существующий код проверяет ADEO;
- не показывает поставщиков и не выдумывает цены или наличие;
- при ошибке OdiRouter оставляет рабочими ADEO, заявку менеджеру и кнопку «Купить».

### Настройка на Render

1. Откройте сервис `ippalit-zapchasty-bot`.
2. В разделе Environment добавьте `ODIROUTER_API_KEY`.
3. Добавьте `ODIROUTER_MODEL` с точным ID выбранной модели.
4. Убедитесь, что `ODIROUTER_BASE_URL` равен `https://api.odirouter.ai/v1`.
5. Выполните Manual Deploy и проверьте текстовое сообщение и фотографию.
