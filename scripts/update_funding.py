from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from common import DATA_DIR, clean_text, fetch, load_json, save_json, today_iso
from config import FUNDING_PROGRAMS

DATA_FILE = DATA_DIR / "funding.json"
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"

def soup_text(raw_html: str) -> str:
    return clean_text(BeautifulSoup(raw_html, "html.parser").get_text(" ", strip=True))

def parse_simons_travel(raw_html: str, program: dict) -> dict:
    text = soup_text(raw_html)
    m = re.search(
        rf"({MONTHS})\s+(\d{{1,2}}),\s+(20\d{{2}}).*?(?:12\s*p\.?m\.?|noon).*?(?:ET|Eastern Time|Eastern time)",
        text, re.I,
    )
    if not m:
        raise ValueError("Could not verify the Simons Travel deadline.")
    month, day, year = m.groups()
    dt = datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date()
    return {
        **program,
        "deadline_type": "date",
        "deadline_date": dt.isoformat(),
        "deadline_display": f"{dt.strftime('%B')} {dt.day}, {dt.year}, 12:00 p.m. ET",
        "status": "Open" if dt >= date.today() else "Closed",
        "last_verified": today_iso(),
    }

def parse_nsf_career(raw_html: str, program: dict) -> dict:
    text = soup_text(raw_html)
    m = re.search(rf"({MONTHS})\s+(\d{{1,2}})\s+(20\d{{2}})\s*-\s*Deadline date", text, re.I)
    if not m:
        raise ValueError("Could not verify the NSF CAREER deadline.")
    month, day, year = m.groups()
    dt = datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date()
    return {
        **program,
        "deadline_type": "date",
        "deadline_date": dt.isoformat(),
        "deadline_display": f"{dt.strftime('%B')} {dt.day}, {dt.year}, 5:00 p.m. submitting organization's local time",
        "status": "Open" if dt >= date.today() else "Closed",
        "last_verified": today_iso(),
    }

def parse_nsf_anytime(raw_html: str, program: dict) -> dict:
    text = soup_text(raw_html).lower()
    if "accepted anytime" not in text and "proposals accepted anytime" not in text:
        raise ValueError("Could not verify the NSF accepted-anytime status.")
    return {
        **program,
        "deadline_type": "anytime",
        "deadline_date": None,
        "deadline_display": "Proposals accepted anytime",
        "status": "Open",
        "last_verified": today_iso(),
    }

def parse_simons_rolling(raw_html: str, program: dict) -> dict:
    text = soup_text(raw_html).lower()
    if "rolling" not in text or "letter" not in text:
        raise ValueError("Could not verify the rolling LOI status.")
    return {
        **program,
        "deadline_type": "rolling",
        "deadline_date": None,
        "deadline_display": "Rolling letter of intent (LOI); may be submitted at any time",
        "status": "Open",
        "last_verified": today_iso(),
    }

PARSERS = {
    "simons_travel": parse_simons_travel,
    "nsf_career": parse_nsf_career,
    "nsf_anytime": parse_nsf_anytime,
    "simons_rolling": parse_simons_rolling,
}

def main() -> None:
    old = load_json(DATA_FILE, [])
    old_by_id = {x.get("id"): x for x in old if x.get("id")}
    updated = []
    for program in FUNDING_PROGRAMS:
        try:
            item = PARSERS[program["parser"]](fetch(program["url"]), program)
            updated.append(item)
            print(f"{program['title']}: {item['deadline_display']}")
        except Exception as exc:
            print(f"WARNING: {program['title']} update failed: {exc}")
            if program["id"] in old_by_id:
                updated.append(old_by_id[program["id"]])
                print("  Preserved last valid record.")
            else:
                updated.append({
                    **program,
                    "deadline_type": "tba",
                    "deadline_date": None,
                    "deadline_display": "TBA — official deadline could not be verified",
                    "status": "Unverified",
                    "last_verified": None,
                })
    save_json(DATA_FILE, updated)
    print(f"Saved {len(updated)} funding opportunities.")

if __name__ == "__main__":
    main()
