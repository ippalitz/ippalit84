# Бесплатный бот без задержек: Cloudflare Workers

Это рекомендуемый вариант для Telegram-бота: бесплатно, без постоянного сервера и без сна как у Render Free.

## Почему Cloudflare Workers

- Бесплатный план Cloudflare Workers дает 100 000 запросов в день.
- Worker стартует на каждый HTTPS-запрос Telegram и не требует long polling.
- Нет Render sleep после 15 минут простоя.
- Код вызывает тот же Adeo XML API: `https://xml.adeo.pro/pricedetails2.php`.
- Состояния диалога, заявки и покупки сохраняются в Cloudflare KV.

## Что нужно создать в Cloudflare

1. Аккаунт Cloudflare.
2. Workers & Pages -> Create Worker.
3. KV namespace, например `ippalit_zapchasty_bot`.
4. Привязать KV к Worker с binding name:

```text
BOT_KV
```

## Переменные Worker

В Cloudflare Worker -> Settings -> Variables добавьте:

```env
TELEGRAM_TOKEN=токен_бота
MANAGER_CHAT_ID=telegram_id_менеджера
ADEO_LOGIN=логин_adeo
ADEO_PASSWORD=пароль_adeo
ADEO_URL_PRICES=https://xml.adeo.pro/pricedetails2.php
MARKUP_PERCENT=30
MAX_OFFERS_PER_QUERY=5
MAX_BRANDS_PER_QUERY=8
WEBHOOK_SECRET=любая_секретная_строка
SETUP_SECRET=любая_другая_секретная_строка
WORKER_URL=https://ippalit-zapchasty-bot.<ваш-subdomain>.workers.dev
```

Опционально:

```env
STORAGE_WEBHOOK_URL=
```

`STORAGE_WEBHOOK_URL` можно использовать позже, если нужно дублировать заявки в Google Sheets через Apps Script.

## Установка webhook

После деплоя откройте в браузере:

```text
https://ippalit-zapchasty-bot.<ваш-subdomain>.workers.dev/setup?key=SETUP_SECRET
```

Если все хорошо, Telegram webhook будет установлен на:

```text
https://ippalit-zapchasty-bot.<ваш-subdomain>.workers.dev/telegram/WEBHOOK_SECRET
```

## Проверка

1. Откройте Telegram-бота.
2. Напишите `/start`.
3. Отправьте номер детали/OEM, например `2108-3501800`.
4. Проверьте предложения Adeo и кнопку `Купить`.
5. Нажмите `Не знаю номер детали` и пройдите анкету.

## Важно

Cloudflare KV хранит заявки и покупки как технические записи. Менеджерские уведомления приходят в Telegram сразу. Если нужен удобный табличный учет, следующим шагом можно подключить Google Sheets через `STORAGE_WEBHOOK_URL`.
