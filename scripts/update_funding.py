from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from common import DATA_DIR, absolute_url, clean_text, fetch, load_json, save_json, today_iso
from config import (
    NSF_CAREER_URL,
    NSF_MATHSCI_URL,
    SIMONS_TARGETED_MPS_URL,
    SIMONS_TRAVEL_LANDING,
)

DATA_FILE = DATA_DIR / "funding.json"

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)


def plain_text(html: str) -> str:
    return clean_text(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))


def parse_month_date(month: str, day: str, year: str) -> date:
    return datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date()


def simons_travel() -> dict:
    landing_html = fetch(SIMONS_TRAVEL_LANDING)
    soup = BeautifulSoup(landing_html, "html.parser")

    link = None
    for a in soup.find_all("a", href=True):
        label = clean_text(a.get_text(" ", strip=True))
        if "Travel Support for Mathematicians" in label and "Request for Applications" in label:
            link = absolute_url(SIMONS_TRAVEL_LANDING, a["href"])
            break
    if not link:
        # The landing page itself often contains the current deadline.
        link = SIMONS_TRAVEL_LANDING

    detail_html = fetch(link)
    text = plain_text(detail_html)

    match = re.search(
        rf"Application Submission Deadline\s*[-:]?\s*"
        rf"({MONTHS})\s+(\d{{1,2}}),\s+(20\d{{2}}),?\s*"
        rf"(12\s*p\.?m\.?|noon)\s*(ET|Eastern Time|Eastern time)",
        text, re.I,
    )
    if not match:
        match = re.search(
            rf"deadline.*?({MONTHS})\s+(\d{{1,2}}),\s+(20\d{{2}}).*?"
            rf"(12\s*p\.?m\.?|noon).*?(ET|Eastern Time|Eastern time)",
            text, re.I,
        )
    if not match:
        raise RuntimeError("Could not verify the current Simons Travel deadline.")

    month, day, year = match.group(1), match.group(2), match.group(3)
    deadline = parse_month_date(month, day, year)
    return {
        "id": "simons-travel",
        "title": f"Travel Support for Mathematicians - {deadline.year}",
        "sponsor": "Simons Foundation",
        "kind": "Research and travel support",
        "url": link,
        "deadline_type": "date",
        "deadline_date": deadline.isoformat(),
        "deadline_display": f"{deadline.strftime('%B')} {deadline.day}, {deadline.year}, 12:00 p.m. ET",
        "status": "Open" if deadline >= date.today() else "Closed",
        "last_verified": today_iso(),
    }


def nsf_career() -> dict:
    html = fetch(NSF_CAREER_URL)
    text = plain_text(html)

    # Prefer text adjacent to "Deadline date".
    match = re.search(
        rf"({MONTHS})\s+(\d{{1,2}})\s*,?\s*(20\d{{2}})\s*-\s*Deadline date",
        text, re.I,
    )
    if not match:
        # Current NSF pages also expose "Upcoming due dates".
        block = re.search(r"Upcoming due dates(.{0,1200})", text, re.I)
        target = block.group(1) if block else text
        match = re.search(
            rf"({MONTHS})\s+(\d{{1,2}})\s*,?\s*(20\d{{2}})",
            target, re.I,
        )
    if not match:
        raise RuntimeError("Could not verify NSF CAREER deadline.")

    deadline = parse_month_date(*match.groups())
    return {
        "id": "nsf-career",
        "title": "Faculty Early Career Development Program (CAREER)",
        "sponsor": "U.S. National Science Foundation",
        "kind": "Early-career research and education",
        "url": NSF_CAREER_URL,
        "deadline_type": "date",
        "deadline_date": deadline.isoformat(),
        "deadline_display": (
            f"{deadline.strftime('%B')} {deadline.day}, {deadline.year}, "
            "5:00 p.m. submitting organization's local time"
        ),
        "status": "Open" if deadline >= date.today() else "Closed",
        "last_verified": today_iso(),
    }


def nsf_mathsci() -> dict:
    html = fetch(NSF_MATHSCI_URL)
    text = plain_text(html).lower()
    if "accepted anytime" not in text:
        raise RuntimeError("NSF MathSci page no longer says proposals are accepted anytime.")
    return {
        "id": "nsf-mathsci",
        "title": "MPS Mathematical Sciences Research Programs (MPS MathSci)",
        "sponsor": "U.S. National Science Foundation",
        "kind": "Mathematical sciences research",
        "url": NSF_MATHSCI_URL,
        "deadline_type": "anytime",
        "deadline_date": None,
        "deadline_display": "Proposals accepted anytime",
        "status": "Open",
        "last_verified": today_iso(),
    }


def simons_targeted() -> dict:
    html = fetch(SIMONS_TARGETED_MPS_URL)
    text = plain_text(html).lower()
    if "rolling" not in text or "letter" not in text:
        raise RuntimeError("Could not verify rolling LOI status.")
    return {
        "id": "simons-targeted-mps",
        "title": "Targeted Grants in MPS",
        "sponsor": "Simons Foundation",
        "kind": "Theoretical mathematics and physical sciences",
        "url": SIMONS_TARGETED_MPS_URL,
        "deadline_type": "rolling",
        "deadline_date": None,
        "deadline_display": "Rolling letter of intent; may be submitted at any time",
        "status": "Open",
        "last_verified": today_iso(),
    }


def main():
    previous = load_json(DATA_FILE, [])
    old = {item.get("id"): item for item in previous if item.get("id")}

    updaters = [
        ("simons-travel", simons_travel),
        ("nsf-career", nsf_career),
        ("nsf-mathsci", nsf_mathsci),
        ("simons-targeted-mps", simons_targeted),
    ]

    output = []
    for item_id, updater in updaters:
        try:
            item = updater()
            output.append(item)
            print(f"{item['title']}: {item['deadline_display']}")
        except Exception as exc:
            print(f"WARNING: {item_id} failed: {exc}")
            if item_id in old:
                output.append(old[item_id])
                print("  Preserved the last verified record.")
            else:
                output.append({
                    "id": item_id,
                    "title": item_id,
                    "sponsor": "",
                    "kind": "",
                    "url": "",
                    "deadline_type": "tba",
                    "deadline_date": None,
                    "deadline_display": "TBA - official deadline could not be verified",
                    "status": "Unverified",
                    "last_verified": None,
                })

    save_json(DATA_FILE, output)
    print(f"Saved {len(output)} external funding opportunities.")


if __name__ == "__main__":
    main()
