from __future__ import annotations

import re
from difflib import SequenceMatcher

from bs4 import BeautifulSoup

from common import (
    DATA_DIR, MONTH_PATTERN, absolute_url, clean_text, fetch, iso_date,
    is_future_or_current, load_json, month_number, normalize_title,
    save_json, today_iso,
)
from config import CONFERENCE_EXCLUDE_KEYWORDS, CONFERENCE_KEYWORDS, CONFERENCE_SOURCES

DATA_FILE = DATA_DIR / "conferences.json"

def relevant(title: str) -> bool:
    t = title.lower()
    if any(k in t for k in CONFERENCE_EXCLUDE_KEYWORDS):
        return False
    return any(k in t for k in CONFERENCE_KEYWORDS)

def classify(title: str) -> list[str]:
    t = title.lower()
    categories = []
    rules = [
        ("Schools", ["school", "lectures"]),
        ("Stochastic Control", ["stochastic control", "optimal control", "mean-field control", "mean field control", "mean-field game", "mean field game"]),
        ("SPDE", ["spde", "stochastic partial differential"]),
        ("Filtering", ["filtering", "nonlinear filter"]),
        ("Large Deviations", ["large deviation", "moderate deviation", "rare event"]),
        ("Stochastic Analysis", ["stochastic analysis", "stochastic differential", "diffusion"]),
        ("Probability", ["probability", "probabilistic", "random", "stochastic", "markov", "monte carlo", "interacting"]),
    ]
    for category, words in rules:
        if any(w in t for w in words):
            categories.append(category)
    return categories or ["Probability"]

def parse_start_date_prefix(text: str):
    text = clean_text(text)
    m = re.match(rf"^(\d{{1,2}})\s*-\s*(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\s*,\s*(.+)$", text, re.I)
    if m:
        d1, d2, mon, year, rest = m.groups()
        mm = month_number(mon)
        return iso_date(int(year), mm, int(d1)), iso_date(int(year), mm, int(d2)), rest
    m = re.match(rf"^(\d{{1,2}})\s+({MONTH_PATTERN})\s*-\s*(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\s*,\s*(.+)$", text, re.I)
    if m:
        d1, mon1, d2, mon2, year, rest = m.groups()
        yy = int(year)
        return iso_date(yy, month_number(mon1), int(d1)), iso_date(yy, month_number(mon2), int(d2)), rest
    m = re.match(rf"^(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\s*,\s*(.+)$", text, re.I)
    if m:
        d1, mon, year, rest = m.groups()
        dd = iso_date(int(year), month_number(mon), int(d1))
        return dd, dd, rest
    return None

def title_location_from_apt(rest: str):
    rest = clean_text(rest)
    marker = re.search(r"\(\s*W\s*e\s*b\s*s\s*i\s*t\s*e[^)]*\)", rest, re.I)
    if marker:
        return rest[:marker.start()].strip(" ,."), rest[marker.end():].strip(" ,.")
    return rest.strip(" ,."), ""

def candidate_url(element, source_url: str) -> str:
    for a in element.find_all("a", href=True):
        label = clean_text(a.get_text(" ", strip=True)).lower()
        if "website" in label or "conference" in label or "workshop" in label:
            return absolute_url(source_url, a.get("href"))
    for a in element.find_all("a", href=True):
        href = a.get("href", "")
        if href and not href.startswith("#"):
            return absolute_url(source_url, href)
    return source_url

def parse_apt(raw_html: str, source: dict) -> list[dict]:
    soup = BeautifulSoup(raw_html, "html.parser")
    events, seen = [], set()
    for element in soup.find_all(["li", "p"]):
        text = clean_text(element.get_text(" ", strip=True))
        if not text or text in seen:
            continue
        seen.add(text)
        parsed = parse_start_date_prefix(text)
        if not parsed:
            continue
        start, end, rest = parsed
        title, location = title_location_from_apt(rest)
        if not relevant(title) or not is_future_or_current(end):
            continue
        events.append({
            "title": title, "start_date": start, "end_date": end, "location": location,
            "url": candidate_url(element, source["url"]), "categories": classify(title),
            "source": source["name"], "source_url": source["url"],
            "last_verified": today_iso(), "manual": False,
        })
    if not events:
        for line in soup.get_text("\n").splitlines():
            text = clean_text(line)
            parsed = parse_start_date_prefix(text) if text else None
            if not parsed:
                continue
            start, end, rest = parsed
            title, location = title_location_from_apt(rest)
            if relevant(title) and is_future_or_current(end):
                events.append({
                    "title": title, "start_date": start, "end_date": end, "location": location,
                    "url": source["url"], "categories": classify(title), "source": source["name"],
                    "source_url": source["url"], "last_verified": today_iso(), "manual": False,
                })
    return events

def parse_date_anywhere(text: str):
    m = re.search(rf"({MONTH_PATTERN})\s+(\d{{1,2}})\s*-\s*(\d{{1,2}})\s*,?\s*(20\d{{2}})", text, re.I)
    if m:
        mon, d1, d2, year = m.groups()
        mm = month_number(mon)
        return iso_date(int(year), mm, int(d1)), iso_date(int(year), mm, int(d2)), m.start()
    m = re.search(rf"(\d{{1,2}})\s*-\s*(\d{{1,2}})\s+({MONTH_PATTERN})\s*,?\s*(20\d{{2}})", text, re.I)
    if m:
        d1, d2, mon, year = m.groups()
        mm = month_number(mon)
        return iso_date(int(year), mm, int(d1)), iso_date(int(year), mm, int(d2)), m.start()
    return None

def parse_bernoulli(raw_html: str, source: dict) -> list[dict]:
    soup = BeautifulSoup(raw_html, "html.parser")
    events = []
    for element in soup.find_all("li"):
        text = clean_text(element.get_text(" ", strip=True))
        parsed = parse_date_anywhere(text)
        if not parsed:
            continue
        start, end, pos = parsed
        prefix = text[:pos].strip(" ,.")
        title, location = prefix, ""
        if " in " in prefix:
            title, location = prefix.rsplit(" in ", 1)
            title, location = title.strip(" ,."), location.strip(" ,.")
        if not relevant(title) or not is_future_or_current(end):
            continue
        events.append({
            "title": title, "start_date": start, "end_date": end, "location": location,
            "url": candidate_url(element, source["url"]), "categories": classify(title),
            "source": source["name"], "source_url": source["url"],
            "last_verified": today_iso(), "manual": False,
        })
    return events

PARSERS = {"apt": parse_apt, "bernoulli": parse_bernoulli}

def same_event(a: dict, b: dict) -> bool:
    if a.get("start_date") != b.get("start_date"):
        return False
    ta, tb = normalize_title(a.get("title", "")), normalize_title(b.get("title", ""))
    return ta == tb or SequenceMatcher(None, ta, tb).ratio() >= 0.84

def deduplicate(events: list[dict]) -> list[dict]:
    result = []
    for event in sorted(events, key=lambda x: (x.get("start_date", ""), x.get("title", ""))):
        idx = next((i for i, old in enumerate(result) if same_event(old, event)), None)
        if idx is None:
            result.append(event)
        else:
            old = result[idx]
            if event.get("url") and event.get("url") != event.get("source_url"):
                old["url"] = event["url"]
            old["categories"] = sorted(set(old.get("categories", []) + event.get("categories", [])))
            old["last_verified"] = max(old.get("last_verified", ""), event.get("last_verified", ""))
    return result

def main() -> None:
    old = load_json(DATA_FILE, [])
    manual = [x for x in old if x.get("manual") and is_future_or_current(x.get("end_date"))]
    refreshed, failed_sources = [], set()
    for source in CONFERENCE_SOURCES:
        try:
            events = PARSERS[source["parser"]](fetch(source["url"]), source)
            if not events:
                raise RuntimeError("No events parsed; preserving previous data for this source.")
            refreshed.extend(events)
            print(f"{source['name']}: {len(events)} events")
        except Exception as exc:
            print(f"WARNING: {source['name']} update failed: {exc}")
            failed_sources.add(source["name"])
    preserved = [
        x for x in old if x.get("source") in failed_sources and not x.get("manual")
        and is_future_or_current(x.get("end_date"))
    ]
    combined = deduplicate(manual + refreshed + preserved)
    combined = [x for x in combined if is_future_or_current(x.get("end_date"))]
    combined.sort(key=lambda x: (x.get("start_date", "9999-12-31"), x.get("title", "")))
    save_json(DATA_FILE, combined)
    print(f"Saved {len(combined)} upcoming conferences.")

if __name__ == "__main__":
    main()
