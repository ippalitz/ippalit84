PART_FILTERS = {
    "brake_pads": {
        "names": ["колодки", "тормозные колодки", "brake pads", "pads"],
        "good": ["колод", "pad", "brake", "торм"],
        "bad": ["датчик", "sensor", "фильтр", "масло", "ремкомплект"],
    },
    "oil_filter": {
        "names": ["масляный фильтр", "фильтр масла", "oil filter"],
        "good": ["фильтр", "filter", "масл", "oil"],
        "bad": ["воздуш", "салон", "топлив", "air", "cabin", "fuel"],
    },
    "air_filter": {
        "names": ["воздушный фильтр", "air filter"],
        "good": ["фильтр", "filter", "воздуш", "air"],
        "bad": ["масл", "салон", "топлив", "oil", "cabin", "fuel"],
    },
    "cabin_filter": {
        "names": ["салонный фильтр", "cabin filter"],
        "good": ["фильтр", "filter", "салон", "cabin"],
        "bad": ["масл", "воздуш", "топлив", "oil", "air", "fuel"],
    },
}


def detect_part_key(text: str) -> str | None:
    value = (text or "").lower()
    for key, rules in PART_FILTERS.items():
        if any(name in value for name in rules["names"]):
            return key
    return None


def best_score(offer: dict) -> tuple:
    rest = int(offer.get("rest") or 0)
    deliverydays = int(offer.get("deliverydays") or 99)
    refuse = int(offer.get("refuse") or 0)
    price = float(offer.get("sell_price") or offer.get("price") or 0)

    no_stock_penalty = 1000 if rest <= 0 else 0
    return (no_stock_penalty, deliverydays, refuse, price)


def filter_offers_by_part(offers: list[dict], part_name: str | None) -> list[dict]:
    part_key = detect_part_key(part_name or "")
    if not part_key:
        return offers

    rules = PART_FILTERS[part_key]
    result = []

    for offer in offers:
        name = (offer.get("caption") or "").lower()
        has_good_word = any(word in name for word in rules["good"])
        has_bad_word = any(word in name for word in rules["bad"])
        if has_good_word and not has_bad_word:
            result.append(offer)

    return result or offers
