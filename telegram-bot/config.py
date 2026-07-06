import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

LOGIN = os.getenv("ADEO_LOGIN", "")
PASSWORD = os.getenv("ADEO_PASSWORD", "")
URL_PRICES = os.getenv("ADEO_URL_PRICES", "https://xml.adeo.pro/pricedetails2.php")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
MANAGER_CHAT_ID = os.getenv("MANAGER_CHAT_ID", "")

MARKUP_PERCENT = int(os.getenv("MARKUP_PERCENT", "30"))
MAX_OFFERS_PER_QUERY = int(os.getenv("MAX_OFFERS_PER_QUERY", "5"))

DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
MANAGER_CHAT_ID_FILE = Path(os.getenv("MANAGER_CHAT_ID_FILE", str(DATA_DIR / "manager_chat_id.txt")))
LEADS_CSV_PATH = Path(os.getenv("LEADS_CSV_PATH", str(DATA_DIR / "leads.csv")))
PURCHASES_CSV_PATH = Path(os.getenv("PURCHASES_CSV_PATH", str(DATA_DIR / "purchases.csv")))

GOOGLE_SHEETS_ENABLED = os.getenv("GOOGLE_SHEETS_ENABLED", "0").lower() in {"1", "true", "yes"}
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "telegram-webhook")
PORT = int(os.getenv("PORT", "10000"))
