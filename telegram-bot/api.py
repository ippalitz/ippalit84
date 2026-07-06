import math
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import requests

from config import LOGIN, MARKUP_PERCENT, PASSWORD, URL_PRICES


def send_xml(xml: str) -> str | None:
    try:
        response = requests.post(URL_PRICES, data={"xml": xml}, timeout=60)
        response.encoding = "utf-8"
        return response.text
    except Exception as exc:
        print("Ошибка запроса ADEO:", exc, flush=True)
        return None


def parse_xml(xml_text: str | None):
    if not xml_text:
        return None
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:
        print("Ошибка XML ADEO:", exc, flush=True)
        return None


def get_brands(code: str) -> str | None:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<message>
    <param>
        <action>price</action>
        <login>{escape(LOGIN)}</login>
        <password>{escape(PASSWORD)}</password>
        <code>{escape(code)}</code>
    </param>
</message>
"""
    return send_xml(xml)


def get_prices(code: str, brand: str) -> str | None:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<message>
    <param>
        <action>price</action>
        <login>{escape(LOGIN)}</login>
        <password>{escape(PASSWORD)}</password>
        <code>{escape(code)}</code>
        <brand>{escape(brand)}</brand>
        <crosses>allow</crosses>
    </param>
</message>
"""
    return send_xml(xml)


def to_int(value, default: int = 0) -> int:
    try:
        return int(float(str(value).strip().replace(",", ".")))
    except (TypeError, ValueError):
        return default


def to_float(value, default: float = 0.0) -> float:
    try:
        return float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default


def sell_price(price: float) -> int:
    return int(math.ceil(price * (1 + MARKUP_PERCENT / 100) / 10) * 10)


def text(detail, tag: str, default: str = "") -> str:
    return detail.findtext(tag, default).strip()


def parse_brands(xml_text: str | None) -> list[str]:
    root = parse_xml(xml_text)
    if root is None:
        return []

    brands = []
    for detail in root.findall(".//detail"):
        producer = text(detail, "producer")
        if producer:
            brands.append(producer)

    return list(dict.fromkeys(brands))


def parse_offers(xml_text: str | None, requested_code: str = "") -> list[dict]:
    root = parse_xml(xml_text)
    if root is None:
        return []

    offers = []
    for detail in root.findall(".//detail"):
        price = to_float(text(detail, "price", "0"))
        if price <= 0:
            continue

        offer = {
            "requested_code": requested_code,
            "producer": text(detail, "producer"),
            "code": text(detail, "code", requested_code),
            "caption": text(detail, "caption"),
            "price": price,
            "sell_price": sell_price(price),
            "currency": text(detail, "currency", "руб"),
            "rest": to_int(text(detail, "rest", "0")),
            "delivery": text(detail, "deliveryDisplay") or text(detail, "delivery"),
            "deliverydays": to_int(text(detail, "deliverydays", "0")),
            "region": text(detail, "RegionName"),
            "stock": text(detail, "stock"),
            "refuse": to_int(text(detail, "PercentRefuse", "0")),
            "return": text(detail, "good_return") or text(detail, "supplier_comment"),
            "b_id": text(detail, "b_id"),
        }
        offers.append(offer)

    return offers


def search_article(code: str, part_name: str | None = None) -> list[dict]:
    from filters import best_score, filter_offers_by_part

    brands = parse_brands(get_brands(code))
    all_offers = []

    for brand in brands:
        xml = get_prices(code, brand)
        all_offers.extend(parse_offers(xml, requested_code=code))

    all_offers = filter_offers_by_part(all_offers, part_name)
    return sorted(all_offers, key=best_score)
