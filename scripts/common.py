from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

USER_AGENT = (
    "Mozilla/5.0 (compatible; HongjiangQianAcademicPageBot/1.0; "
    "+https://hongjiang-qian.github.io/)"
)

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

MONTH_PATTERN = (
    r"January|Jan(?:uary)?|February|Feb(?:ruary)?|March|Mar(?:ch)?|"
    r"April|Apr(?:il)?|May|June|Jun(?:e)?|July|Jul(?:y)?|"
    r"August|Aug(?:ust)?|September|Sept?(?:ember)?|October|Oct(?:ober)?|"
    r"November|Nov(?:ember)?|December|Dec(?:ember)?"
)


def clean_text(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = value.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", value).strip()


def month_number(name: str) -> int:
    return MONTHS[name.lower().rstrip(".")]


def fetch(url: str, timeout: int = 35) -> str:
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
    )
    response.raise_for_status()
    return response.text


def absolute_url(base: str, href: str | None) -> str:
    return urljoin(base, href or "")


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def today_iso() -> str:
    return date.today().isoformat()


def active_through(end_date: str | None) -> bool:
    if not end_date:
        return True
    try:
        return date.fromisoformat(end_date) >= date.today()
    except ValueError:
        return True


def event_date_display(start: str, end: str | None) -> str:
    s = date.fromisoformat(start)
    e = date.fromisoformat(end or start)
    if s == e:
        return f"{s.strftime('%b.')} {s.day}, {s.year}"
    if s.year == e.year and s.month == e.month:
        return f"{s.strftime('%b.')} {s.day}-{e.day}, {s.year}"
    if s.year == e.year:
        return f"{s.strftime('%b.')} {s.day}-{e.strftime('%b.')} {e.day}, {s.year}"
    return (
        f"{s.strftime('%b.')} {s.day}, {s.year}-"
        f"{e.strftime('%b.')} {e.day}, {e.year}"
    )


def normalize_title(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()
