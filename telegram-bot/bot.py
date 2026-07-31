import html
from typing import Any

import telebot
from telebot import types

from ai_manager import ask_ai, is_enabled as ai_is_enabled
from api import search_article
from config import MANAGER_CHAT_ID, MANAGER_CHAT_ID_FILE, MAX_OFFERS_PER_QUERY, TELEGRAM_TOKEN
from request_parser import extract_oems
from storage import save_lead, save_purchase

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

USER_STATES: dict[int, dict[str, Any]] = {}
OFFERS_CACHE: dict[str, dict[str, Any]] = {}
AI_CONVERSATIONS: dict[int, list[dict[str, str]]] = {}
AI_CONSENT: set[int] = set()

LEAD_STEPS = [
    ("vin", "Укажите VIN автомобиля."),
    ("car", "Укажите марку, модель и год."),
    ("part", "Какая деталь нужна?"),
    ("city", "В какой город нужна доставка?"),
    ("phone", "Оставьте телефон для связи."),
]


def safe(value: Any) -> str:
    return html.escape(str(value or "").strip())


def user_info(message) -> dict[str, str]:
    user = message.from_user
    return {
        "telegram_id": str(user.id if user else message.chat.id),
        "telegram_username": f"@{user.username}" if user and user.username else "",
    }


def main_keyboard() -> types.ReplyKeyboardMarkup:
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Проверить по номеру/OEM")
    keyboard.row("Не знаю номер детали")
    keyboard.row("Подключить ИИ-менеджера")
    return keyboard


def lead_keyboard() -> types.ReplyKeyboardMarkup:
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Отменить заявку")
    return keyboard


def start_text() -> str:
    return (
        "Здравствуйте! Я помогу проверить наличие автозапчастей.\n\n"
        "Если вы знаете номер детали/OEM, отправьте его сюда, и я проверю актуальное наличие в Adeo.\n\n"
        "Если номер неизвестен, нажмите «Не знаю номер детали» — я соберу данные для менеджера.\n\n"
        "ИИ-менеджер может анализировать текст и фотографии только после вашего отдельного согласия."
    )


@bot.message_handler(commands=["start", "help"])
def start(message):
    USER_STATES.pop(message.chat.id, None)
    AI_CONVERSATIONS.pop(message.chat.id, None)
    remember_manager_chat(message.chat.id)
    bot.send_message(message.chat.id, start_text(), reply_markup=main_keyboard())


@bot.message_handler(func=lambda message: (message.text or "").strip() == "Проверить по номеру/OEM")
def ask_for_oem(message):
    USER_STATES.pop(message.chat.id, None)
    bot.send_message(
        message.chat.id,
        "Отправьте номер детали/OEM одним сообщением. Например: 2108-3501800",
        reply_markup=main_keyboard(),
    )


@bot.message_handler(func=lambda message: (message.text or "").strip() == "Не знаю номер детали")
def begin_lead(message):
    USER_STATES[message.chat.id] = {"mode": "lead", "step": 0, "data": user_info(message)}
    bot.send_message(message.chat.id, LEAD_STEPS[0][1], reply_markup=lead_keyboard())


@bot.message_handler(func=lambda message: (message.text or "").strip() == "Отменить заявку")
def cancel_lead(message):
    USER_STATES.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "Заявку отменил. Можете отправить номер детали/OEM.", reply_markup=main_keyboard())


def format_offer(offer: dict[str, Any], index: int) -> str:
    title = " ".join(filter(None, [offer.get("producer"), offer.get("code")]))
    delivery = offer.get("delivery") or offer.get("deliverydays") or "уточняется"
    return (
        f"<b>{index}. {safe(title)}</b>\n"
        f"{safe(offer.get('caption'))}\n"
        f"Бренд: {safe(offer.get('producer'))}\n"
        f"Цена: <b>{safe(offer.get('sell_price'))} {safe(offer.get('currency', 'руб'))}</b>\n"
        f"Наличие: {safe(offer.get('rest'))}\n"
        f"Срок: {safe(delivery)}"
    )


def offer_callback_id(chat_id: int, code: str, index: int) -> str:
    return f"{chat_id}:{code}:{index}"


def send_offers(message, code: str) -> None:
    bot.send_message(message.chat.id, f"Проверяю наличие по номеру {safe(code)} в Adeo...")
    offers = search_article(code)

    if not offers:
        bot.send_message(
            message.chat.id,
            f"По номеру {safe(code)} сейчас не нашел предложений. Менеджер может проверить вручную.",
            reply_markup=main_keyboard(),
        )
        notify_manager(
            "Клиент проверял номер, предложений нет:\n"
            f"Номер: {safe(code)}\n"
            f"Telegram ID: {message.chat.id}\n"
            f"Username: {safe(user_info(message).get('telegram_username'))}"
        )
        return

    limited = offers[:MAX_OFFERS_PER_QUERY]
    for index, offer in enumerate(limited, start=1):
        callback_id = offer_callback_id(message.chat.id, code, index)
        OFFERS_CACHE[callback_id] = {**offer, **user_info(message)}
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Купить", callback_data=f"buy:{callback_id}"))
        bot.send_message(message.chat.id, format_offer(offer, index), reply_markup=keyboard)


def remember_manager_chat(chat_id: int) -> None:
    if MANAGER_CHAT_ID or MANAGER_CHAT_ID_FILE.exists():
        return
    MANAGER_CHAT_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANAGER_CHAT_ID_FILE.write_text(str(chat_id), encoding="utf-8")
    print(f"Saved manager chat id: {chat_id}", flush=True)


def get_manager_chat_id() -> str:
    if MANAGER_CHAT_ID:
        return MANAGER_CHAT_ID
    if MANAGER_CHAT_ID_FILE.exists():
        return MANAGER_CHAT_ID_FILE.read_text(encoding="utf-8").strip()
    return ""


def notify_manager(text: str) -> None:
    manager_chat_id = get_manager_chat_id()
    if not manager_chat_id:
        print(f"MANAGER_CHAT_ID is empty. Notification:\n{text}", flush=True)
        return
    try:
        bot.send_message(manager_chat_id, text)
    except Exception as exc:
        print(f"Manager notification failed: {exc}", flush=True)


def finish_lead(message, data: dict[str, Any]) -> None:
    saved = save_lead(data)
    notify_manager(
        "Новая заявка: нужно подобрать номер детали/OEM\n\n"
        f"VIN: {safe(saved.get('vin'))}\n"
        f"Авто: {safe(saved.get('car'))}\n"
        f"Деталь: {safe(saved.get('part'))}\n"
        f"Город: {safe(saved.get('city'))}\n"
        f"Телефон: {safe(saved.get('phone'))}\n"
        f"Telegram: {safe(saved.get('telegram_username'))}\n"
        f"Telegram ID: {safe(saved.get('telegram_id'))}"
    )
    bot.send_message(
        message.chat.id,
        "Заявка принята. Менеджер подберет номер детали/OEM и свяжется с вами.\n\n"
        "Когда получите номер, отправьте его сюда — я проверю наличие и цены в Adeo.",
        reply_markup=main_keyboard(),
    )


def handle_lead_step(message, state: dict[str, Any]) -> None:
    step = int(state["step"])
    key, _ = LEAD_STEPS[step]
    state["data"][key] = (message.text or "").strip()
    step += 1

    if step >= len(LEAD_STEPS):
        USER_STATES.pop(message.chat.id, None)
        finish_lead(message, state["data"])
        return

    state["step"] = step
    bot.send_message(message.chat.id, LEAD_STEPS[step][1], reply_markup=lead_keyboard())


@bot.callback_query_handler(func=lambda call: (call.data or "").startswith("buy:"))
def buy_offer(call):
    callback_id = (call.data or "").split(":", 1)[1]
    offer = OFFERS_CACHE.get(callback_id)
    if not offer:
        bot.answer_callback_query(call.id, "Предложение устарело. Отправьте номер детали еще раз.")
        return

    saved = save_purchase(offer)
    notify_manager(
        "Новая покупка из Telegram\n\n"
        f"Номер запроса: {safe(saved.get('requested_code'))}\n"
        f"Позиция: {safe(saved.get('producer'))} {safe(saved.get('code'))}\n"
        f"Название: {safe(saved.get('caption'))}\n"
        f"Цена клиенту: {safe(saved.get('sell_price'))} {safe(saved.get('currency'))}\n"
        f"Наличие: {safe(saved.get('rest'))}\n"
        f"Срок: {safe(saved.get('delivery'))}\n"
        f"Склад: {safe(saved.get('stock'))}\n"
        f"Telegram: {safe(saved.get('telegram_username'))}\n"
        f"Telegram ID: {safe(saved.get('telegram_id'))}"
    )
    bot.answer_callback_query(call.id, "Заявка принята")
    bot.send_message(
        call.message.chat.id,
        "Заявка на покупку принята. Менеджер свяжется с вами для подтверждения и доставки.",
        reply_markup=main_keyboard(),
    )


def ai_consent_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Согласен, включить ИИ", callback_data="ai_consent:yes"),
        types.InlineKeyboardButton("Без ИИ", callback_data="ai_consent:no"),
    )
    return keyboard


def request_ai_consent(chat_id: int) -> None:
    bot.send_message(
        chat_id,
        "Для ответа ИИ текст сообщения, VIN и отправленные фотографии будут передаваться "
        "во внешний сервис OdiRouter. Не отправляйте паспортные данные, банковские данные "
        "и другую информацию, не относящуюся к подбору запчасти.\n\n"
        "Вы согласны включить ИИ-менеджера?",
        reply_markup=ai_consent_keyboard(),
    )


@bot.message_handler(
    func=lambda message: (message.text or "").strip() == "Подключить ИИ-менеджера"
)
def enable_ai_prompt(message):
    if not ai_is_enabled():
        bot.send_message(
            message.chat.id,
            "ИИ-менеджер пока не настроен. Оставьте заявку, и вам ответит менеджер.",
            reply_markup=main_keyboard(),
        )
        return
    request_ai_consent(message.chat.id)


@bot.callback_query_handler(func=lambda call: (call.data or "").startswith("ai_consent:"))
def handle_ai_consent(call):
    choice = (call.data or "").split(":", 1)[1]
    if choice == "yes":
        AI_CONSENT.add(call.message.chat.id)
        bot.answer_callback_query(call.id, "ИИ-менеджер включён")
        bot.send_message(
            call.message.chat.id,
            "ИИ-менеджер включён. Опишите нужную деталь или пришлите фото VIN/маркировки.",
            reply_markup=main_keyboard(),
        )
        return

    AI_CONSENT.discard(call.message.chat.id)
    AI_CONVERSATIONS.pop(call.message.chat.id, None)
    bot.answer_callback_query(call.id, "Работаем без ИИ")
    bot.send_message(
        call.message.chat.id,
        "Хорошо, данные во внешний ИИ не передаются. Используйте проверку по OEM "
        "или оставьте заявку менеджеру.",
        reply_markup=main_keyboard(),
    )


def reply_with_ai(message, text: str, image_bytes: bytes | None = None) -> bool:
    if not ai_is_enabled() or message.chat.id not in AI_CONSENT:
        return False

    history = AI_CONVERSATIONS.get(message.chat.id, [])
    answer = ask_ai(text=text, history=history, image_bytes=image_bytes)
    if not answer:
        return False

    clean_text = (text or "[фотография]").strip()
    history.extend(
        [
            {"role": "user", "content": clean_text},
            {"role": "assistant", "content": answer},
        ]
    )
    AI_CONVERSATIONS[message.chat.id] = history[-6:]
    bot.send_message(message.chat.id, safe(answer), reply_markup=main_keyboard())
    return True


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    if message.chat.id not in AI_CONSENT:
        request_ai_consent(message.chat.id)
        return

    try:
        photo = message.photo[-1]
        file_info = bot.get_file(photo.file_id)
        image_bytes = bot.download_file(file_info.file_path)
    except Exception as exc:
        print(f"Telegram photo download failed: {exc}", flush=True)
        bot.send_message(
            message.chat.id,
            "Не удалось прочитать фотографию. Пришлите VIN или номер детали текстом.",
            reply_markup=main_keyboard(),
        )
        return

    prompt = (message.caption or "").strip() or (
        "Распознай VIN или маркировку детали на фотографии. "
        "Повтори распознанное значение и попроси клиента подтвердить его."
    )
    if reply_with_ai(message, prompt, image_bytes=image_bytes):
        return

    bot.send_message(
        message.chat.id,
        "ИИ для фотографий временно недоступен. Пришлите VIN или номер детали текстом.",
        reply_markup=main_keyboard(),
    )


@bot.message_handler(func=lambda message: True)
def handle(message):
    text = (message.text or "").strip()
    if not text:
        bot.send_message(message.chat.id, "Отправьте номер детали/OEM текстом или оформите заявку.", reply_markup=main_keyboard())
        return

    state = USER_STATES.get(message.chat.id)
    if state and state.get("mode") == "lead":
        handle_lead_step(message, state)
        return

    codes = extract_oems(text)
    if codes:
        for code in codes[:3]:
            send_offers(message, code)
        return

    if message.chat.id in AI_CONSENT and reply_with_ai(message, text):
        return

    if ai_is_enabled() and message.chat.id not in AI_CONSENT:
        request_ai_consent(message.chat.id)
        return

    bot.send_message(
        message.chat.id,
        "Не увидел номер детали/OEM. Если номера нет, нажмите «Не знаю номер детали», и я передам заявку менеджеру.",
        reply_markup=main_keyboard(),
    )


if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is empty. Add it to server environment variables.")
    print("BOT STARTED", flush=True)
    bot.remove_webhook()
    bot.infinity_polling(timeout=60, long_polling_timeout=30, skip_pending=False)
