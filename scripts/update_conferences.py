from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher

from bs4 import BeautifulSoup

from common import (
    DATA_DIR, MONTH_PATTERN, absolute_url, active_through, clean_text, fetch,
    load_json, month_number, normalize_title, save_json, today_iso,
)
from config import (
    CONFERENCE_EXCLUDE_KEYWORDS, CONFERENCE_KEYWORDS, CONFERENCE_SOURCES,
)

DATA_FILE = DATA_DIR / "conferences.json"


def relevant(title: str) -> bool:
    text = title.lower()
    if any(word in text for word in CONFERENCE_EXCLUDE_KEYWORDS):
        return False
    return any(word in text for word in CONFERENCE_KEYWORDS)


def classify(title: str) -> list[str]:
    text = title.lower()
    categories = []
    mapping = [
        ("Schools", ["school", "lectures"]),
        ("Stochastic Control", [
            "stochastic control", "optimal control", "mean-field control",
            "mean field control", "mean-field game", "mean field game",
        ]),
        ("SPDE", ["spde", "stochastic partial differential"]),
        ("Filtering", ["filtering"]),
        ("Large Deviations", ["large deviation", "moderate deviation", "rare event"]),
        ("Stochastic Analysis", ["stochastic analysis", "stochastic differential", "diffusion"]),
        ("Probability", ["probability", "probabilistic", "random", "stochastic", "markov"]),
    ]
    for category, terms in mapping:
        if any(term in text for term in terms):
            categories.append(category)
    return categories or ["Probability"]


def parse_leading_date(text: str):
    text = clean_text(text)

    # 23 - 27 November 2026, Event title...
    match = re.match(
        rf"^(\d{{1,2}})\s*-\s*(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\s*,\s*(.+)$",
        text, re.I,
    )
    if match:
        d1, d2, mon, year, rest = match.groups()
        m = month_number(mon)
        return (
            date(int(year), m, int(d1)).isoformat(),
            date(int(year), m, int(d2)).isoformat(),
            rest,
        )

    # 28 June - 2 July 2027, Event title...
    match = re.match(
        rf"^(\d{{1,2}})\s+({MONTH_PATTERN})\s*-\s*(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\s*,\s*(.+)$",
        text, re.I,
    )
    if match:
        d1, mon1, d2, mon2, year, rest = match.groups()
        year = int(year)
        return (
            date(year, month_number(mon1), int(d1)).isoformat(),
            date(year, month_number(mon2), int(d2)).isoformat(),
            rest,
        )

    # 27 May 2027, Event title...
    match = re.match(
        rf"^(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\s*,\s*(.+)$",
        text, re.I,
    )
    if match:
        day, mon, year, rest = match.groups()
        d = date(int(year), month_number(mon), int(day)).isoformat()
        return d, d, rest

    return None


def split_apt_title_location(rest: str):
    rest = clean_text(rest)
    marker = re.search(r"\(\s*W\s*e\s*b\s*s\s*i\s*t\s*e[^)]*\)", rest, re.I)
    if marker:
        return (
            rest[:marker.start()].strip(" ,."),
            rest[marker.end():].strip(" ,."),
        )
    return rest.strip(" ,."), ""


def best_link(element, source_url: str) -> str:
    links = element.find_all("a", href=True)
    for link in links:
        label = clean_text(link.get_text(" ", strip=True)).lower()
        if "website" in label:
            return absolute_url(source_url, link["href"])
    for link in links:
        return absolute_url(source_url, link["href"])
    return source_url


def parse_apt(html: str, source: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    for element in soup.find_all(["li", "p"]):
        text = clean_text(element.get_text(" ", strip=True))
        if not text or text in seen:
            continue
        seen.add(text)
        parsed = parse_leading_date(text)
        if not parsed:
            continue
        start, end, rest = parsed
        title, location = split_apt_title_location(rest)
        if not relevant(title) or not active_through(end):
            continue
        events.append({
            "title": title,
            "start_date": start,
            "end_date": end,
            "location": location,
            "url": best_link(element, source["url"]),
            "categories": classify(title),
            "source": source["name"],
            "source_url": source["url"],
            "last_verified": today_iso(),
            "manual": False,
        })
    return events


def parse_date_anywhere(text: str):
    # July 5-9, 2027
    match = re.search(
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})\s*-\s*(\d{{1,2}})\s*,?\s*(20\d{{2}})",
        text, re.I,
    )
    if match:
        mon, d1, d2, year = match.groups()
        m = month_number(mon)
        return (
            date(int(year), m, int(d1)).isoformat(),
            date(int(year), m, int(d2)).isoformat(),
            match.start(), match.end(),
        )

    # 5-9 July 2027
    match = re.search(
        rf"(\d{{1,2}})\s*-\s*(\d{{1,2}})\s+({MONTH_PATTERN})\s*,?\s*(20\d{{2}})",
        text, re.I,
    )
    if match:
        d1, d2, mon, year = match.groups()
        m = month_number(mon)
        return (
            date(int(year), m, int(d1)).isoformat(),
            date(int(year), m, int(d2)).isoformat(),
            match.start(), match.end(),
        )
    return None


def parse_bernoulli(html: str, source: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    events = []

    for element in soup.find_all(["li", "p"]):
        text = clean_text(element.get_text(" ", strip=True))
        parsed = parse_date_anywhere(text)
        if not parsed:
            continue
        start, end, begin, finish = parsed
        prefix = text[:begin].strip(" ,.")
        title = prefix
        location = ""
        if " in " in prefix:
            title, location = prefix.rsplit(" in ", 1)
            title = title.strip(" ,.")
            location = location.strip(" ,.")
        if not relevant(title) or not active_through(end):
            continue
        events.append({
            "title": title,
            "start_date": start,
            "end_date": end,
            "location": location,
            "url": best_link(element, source["url"]),
            "categories": classify(title),
            "source": source["name"],
            "source_url": source["url"],
            "last_verified": today_iso(),
            "manual": False,
        })
    return events


PARSERS = {"apt": parse_apt, "bernoulli": parse_bernoulli}


def duplicate(a: dict, b: dict) -> bool:
    if a.get("start_date") != b.get("start_date"):
        return False
    x = normalize_title(a.get("title", ""))
    y = normalize_title(b.get("title", ""))
    return x == y or SequenceMatcher(None, x, y).ratio() >= 0.84


def deduplicate(events: list[dict]) -> list[dict]:
    output = []
    for event in sorted(events, key=lambda x: (x.get("start_date", ""), x.get("title", ""))):
        found = None
        for i, old in enumerate(output):
            if duplicate(old, event):
                found = i
                break
        if found is None:
            output.append(event)
        else:
            old = output[found]
            old["categories"] = sorted(set(old.get("categories", []) + event.get("categories", [])))
            if event.get("url") and event.get("url") != event.get("source_url"):
                old["url"] = event["url"]
    return output


def main():
    old = load_json(DATA_FILE, [])
    manual = [x for x in old if x.get("manual") and active_through(x.get("end_date"))]
    refreshed = []
    failed = set()

    for source in CONFERENCE_SOURCES:
        try:
            html = fetch(source["url"])
            items = PARSERS[source["parser"]](html, source)
            if not items:
                raise RuntimeError("No events parsed.")
            refreshed.extend(items)
            print(f"{source['name']}: {len(items)} events")
        except Exception as exc:
            print(f"WARNING: {source['name']} failed: {exc}")
            failed.add(source["name"])

    preserved = [
        x for x in old
        if x.get("source") in failed
        and not x.get("manual")
        and active_through(x.get("end_date"))
    ]

    final = deduplicate(manual + refreshed + preserved)
    final = [x for x in final if active_through(x.get("end_date"))]
    final.sort(key=lambda x: (x.get("start_date", "9999-12-31"), x.get("title", "")))
    save_json(DATA_FILE, final)
    print(f"Saved {len(final)} upcoming conferences.")


if __name__ == "__main__":
    main()
