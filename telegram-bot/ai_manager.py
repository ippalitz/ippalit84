import base64
from typing import Any

import requests

from config import (
    ODIROUTER_API_KEY,
    ODIROUTER_BASE_URL,
    ODIROUTER_MAX_TOKENS,
    ODIROUTER_MODEL,
    ODIROUTER_TIMEOUT,
)

SYSTEM_PROMPT = """Ты — ИИ-менеджер магазина «Иппалит Запчасти» в Telegram.
Отвечай клиенту по-русски, коротко, вежливо и по делу.

Твоя задача:
1. Понять, какая запчасть нужна.
2. Запросить VIN автомобиля (17 символов) или фото VIN, если применимость зависит от автомобиля.
3. Если клиент прислал VIN или номер/OEM с фото, явно повторить распознанное значение и попросить подтвердить его.
4. Для двигателя, КПП, ТНВД и других дорогих агрегатов дополнительно запросить маркировку агрегата.
5. Когда клиент подтвердил OEM/артикул, попросить отправить его отдельным сообщением — бот автоматически проверит ADEO.
6. Если данных недостаточно, задать только один самый важный уточняющий вопрос.

Строгие правила:
- Не выдумывай цену, наличие, срок, применимость или результат поиска.
- Не говори, что уже проверил ADEO, Bamper, Motorland или другой источник, если результат не передан тебе системой.
- Не показывай клиенту названия поставщиков, закупочные цены и ссылки поставщиков.
- Не обещай заказ или оплату от имени магазина.
- При сомнении передавай вопрос живому менеджеру.
- Пиши обычным текстом без Markdown и HTML.
"""


def is_enabled() -> bool:
    return bool(ODIROUTER_API_KEY and ODIROUTER_MODEL)


def _image_data_url(image_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def ask_ai(
    text: str,
    history: list[dict[str, Any]] | None = None,
    image_bytes: bytes | None = None,
    image_mime_type: str = "image/jpeg",
) -> str | None:
    if not is_enabled():
        return None

    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-6:])

    if image_bytes:
        user_content: Any = [
            {"type": "text", "text": text or "Определи VIN или маркировку детали на фотографии."},
            {
                "type": "image_url",
                "image_url": {"url": _image_data_url(image_bytes, image_mime_type)},
            },
        ]
    else:
        user_content = text

    messages.append({"role": "user", "content": user_content})

    try:
        response = requests.post(
            f"{ODIROUTER_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {ODIROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": ODIROUTER_MODEL,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": ODIROUTER_MAX_TOKENS,
            },
            timeout=ODIROUTER_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        answer = payload["choices"][0]["message"]["content"]
        if isinstance(answer, str) and answer.strip():
            return answer.strip()
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        print(f"OdiRouter request failed: {exc}", flush=True)

    return None
