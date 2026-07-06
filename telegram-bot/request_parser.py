import re
from dataclasses import dataclass

from filters import detect_part_key

VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.IGNORECASE)
OEM_RE = re.compile(
    r"\b(?:[A-ZА-Я]{0,4}\d[A-ZА-Я0-9]{4,16}|\d{4,12}[- ]?\d{2,8}[- ]?\d{0,6})\b",
    re.IGNORECASE,
)


@dataclass
class ClientRequest:
    text: str
    vin: str | None
    oems: list[str]
    part_key: str | None
    part_text: str | None


def normalize_code(value: str) -> str:
    return re.sub(r"[\s_]+", "", value.upper())


def extract_vin(text: str) -> str | None:
    match = VIN_RE.search(text or "")
    return match.group(0).upper() if match else None


def extract_oems(text: str) -> list[str]:
    vin = extract_vin(text)
    result = []

    for match in OEM_RE.findall(text or ""):
        code = normalize_code(match)
        if vin and code == vin:
            continue
        if len(code) < 5:
            continue
        if not any(ch.isdigit() for ch in code):
            continue
        result.append(code)

    return list(dict.fromkeys(result))


def parse_client_request(text: str) -> ClientRequest:
    part_key = detect_part_key(text)
    return ClientRequest(
        text=text or "",
        vin=extract_vin(text or ""),
        oems=extract_oems(text or ""),
        part_key=part_key,
        part_text=text if part_key else None,
    )
