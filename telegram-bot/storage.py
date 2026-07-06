import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config import (
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEET_ID,
    GOOGLE_SHEETS_ENABLED,
    LEADS_CSV_PATH,
    PURCHASES_CSV_PATH,
)

LEAD_FIELDS = [
    "created_at",
    "status",
    "telegram_id",
    "telegram_username",
    "phone",
    "vin",
    "car",
    "part",
    "city",
    "comment",
]

PURCHASE_FIELDS = [
    "created_at",
    "status",
    "telegram_id",
    "telegram_username",
    "phone",
    "requested_code",
    "producer",
    "code",
    "caption",
    "sell_price",
    "currency",
    "rest",
    "delivery",
    "stock",
    "region",
]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def append_csv(path: Path, fields: list[str], row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in fields})


def append_google_sheet(sheet_name: str, fields: list[str], row: dict[str, Any]) -> None:
    if not GOOGLE_SHEETS_ENABLED or not GOOGLE_SHEET_ID or not GOOGLE_SERVICE_ACCOUNT_JSON:
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("Google Sheets is enabled, but gspread/google-auth is not installed.", flush=True)
        return

    try:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(fields))
            worksheet.append_row(fields)

        values = worksheet.get_all_values()
        if not values:
            worksheet.append_row(fields)
        worksheet.append_row([row.get(field, "") for field in fields])
    except Exception as exc:
        print(f"Google Sheets write failed: {exc}", flush=True)


def save_lead(row: dict[str, Any]) -> dict[str, Any]:
    data = {"created_at": now_iso(), "status": "needs_oem", **row}
    append_csv(LEADS_CSV_PATH, LEAD_FIELDS, data)
    append_google_sheet("leads", LEAD_FIELDS, data)
    return data


def save_purchase(row: dict[str, Any]) -> dict[str, Any]:
    data = {"created_at": now_iso(), "status": "new_purchase", **row}
    append_csv(PURCHASES_CSV_PATH, PURCHASE_FIELDS, data)
    append_google_sheet("purchases", PURCHASE_FIELDS, data)
    return data
