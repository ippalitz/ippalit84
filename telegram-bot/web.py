from flask import Flask, abort, request
from telebot import types

from bot import bot
from config import PORT, TELEGRAM_TOKEN, WEBHOOK_SECRET, WEBHOOK_URL

app = Flask(__name__)


@app.get("/")
def healthcheck():
    return "OK", 200


@app.post(f"/telegram/{WEBHOOK_SECRET}")
def telegram_webhook():
    if request.headers.get("content-type") != "application/json":
        abort(403)

    update = types.Update.de_json(request.get_data(as_text=True))
    bot.process_new_updates([update])
    return "OK", 200


def configure_webhook() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN is empty. Add it to environment variables.")
    if not WEBHOOK_URL:
        print("WEBHOOK_URL is empty. Server will run, but Telegram webhook is not configured.", flush=True)
        return

    webhook_endpoint = f"{WEBHOOK_URL}/telegram/{WEBHOOK_SECRET}"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_endpoint)
    print(f"Telegram webhook configured: {webhook_endpoint}", flush=True)


if __name__ == "__main__":
    configure_webhook()
    app.run(host="0.0.0.0", port=PORT)
