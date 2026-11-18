from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common import DATA_DIR, active_through, clean_text, fetch, load_json, save_json, today_iso
from config import (
    AMS_MAJOR_EVENT_URLS,
    APT_EVENTS_URL,
    BERNOULLI_MEETINGS_URL,
    CURATED_SEED_EVENTS,
    IEEE_CSS_FINANCIAL_URL,
    MAJOR_TITLE_PATTERNS,
    SCHOOL_TITLE_PATTERNS,
    SIAM_MAJOR_EVENT_URLS,
)

DATA_FILE = DATA_DIR / "conferences.json"

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


def month_number(name: str) -> int:
    return MONTHS[name.lower().rstrip(".")]


def matches_any(title: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, title, re.I) for pattern in patterns)


def normalize_title(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date_range(text: str):
    """Parse common public-event date formats anywhere in a string."""
    text = clean_text(text)

    # January 12-15, 2027
    m = re.search(
        rf"({MONTH_PATTERN})\s+(\d{{1,2}})\s*-\s*(\d{{1,2}})\s*,?\s*(20\d{{2}})",
        text, re.I,
    )
    if m:
        mon, d1, d2, year = m.groups()
        mm = month_number(mon)
        return (
            date(int(year), mm, int(d1)).isoformat(),
            date(int(year), mm, int(d2)).isoformat(),
            m.start(), m.end(),
        )

    # 12-15 January 2027
    m = re.search(
        rf"(\d{{1,2}})\s*-\s*(\d{{1,2}})\s+({MONTH_PATTERN})\s*,?\s*(20\d{{2}})",
        text, re.I,
    )
    if m:
        d1, d2, mon, year = m.groups()
        mm = month_number(mon)
        return (
            date(int(year), mm, int(d1)).isoformat(),
            date(int(year), mm, int(d2)).isoformat(),
            m.start(), m.end(),
        )

    # 12 January - 6 February 2027
    m = re.search(
        rf"(\d{{1,2}})\s+({MONTH_PATTERN})\s*-\s*(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})",
        text, re.I,
    )
    if m:
        d1, mon1, d2, mon2, year = m.groups()
        yy = int(year)
        return (
            date(yy, month_number(mon1), int(d1)).isoformat(),
            date(yy, month_number(mon2), int(d2)).isoformat(),
            m.start(), m.end(),
        )

    # January 12, 2027
    m = re.search(
        rf"({MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(20\d{{2}})",
        text, re.I,
    )
    if m:
        mon, day, year = m.groups()
        dd = date(int(year), month_number(mon), int(day)).isoformat()
        return dd, dd, m.start(), m.end()

    # 12 January 2027
    m = re.search(
        rf"(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})",
        text, re.I,
    )
    if m:
        day, mon, year = m.groups()
        dd = date(int(year), month_number(mon), int(day)).isoformat()
        return dd, dd, m.start(), m.end()

    return None


def apt_lines(html: str):
    """Preserve APT <br>-separated event lines."""
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        label = clean_text(a.get_text(" ", strip=True))
        if "website" in label.lower():
            absolute = urljoin(APT_EVENTS_URL, a["href"])
            a.replace_with(f" [[URL:{absolute}]] ")

    raw = soup.get_text("\n", strip=True)
    lines = []
    for raw_line in raw.splitlines():
        line = clean_text(raw_line)
        if line and re.search(r"\b20\d{2}\b", line):
            lines.append(line)
    return lines


def parse_apt():
    html = fetch(APT_EVENTS_URL)
    events = []

    for line in apt_lines(html):
        parsed = parse_date_range(line)
        if not parsed:
            continue

        start, end, begin, finish = parsed
        if not active_through(end):
            continue

        # Most APT lines have date first, then title (Website), location.
        remainder = line[finish:].strip(" ,.-")
        url = APT_EVENTS_URL

        marker = re.search(r"\[\[URL:(.*?)\]\]", remainder)
        if marker:
            url = marker.group(1).strip()
            before = remainder[:marker.start()].strip()
            after = remainder[marker.end():].strip()
            title = re.sub(r"\(\s*$", "", before).strip(" ,.")
            location = re.sub(r"^\s*\)\s*,?\s*", "", after).strip(" ,.")
        else:
            no_link = re.search(r"\(\s*Website\s+to\s+come\s*\)", remainder, re.I)
            if no_link:
                title = remainder[:no_link.start()].strip(" ,.")
                location = remainder[no_link.end():].strip(" ,.")
            else:
                # Do not guess comma splits if there is no website marker.
                title = remainder.strip(" ,.")
                location = ""

        event_type = None
        organization = "Community"

        if matches_any(title, SCHOOL_TITLE_PATTERNS):
            event_type = "school"
            organization = "School"
        elif matches_any(title, MAJOR_TITLE_PATTERNS):
            event_type = "conference"
            if "INFORMS" in title.upper():
                organization = "INFORMS APS"
            elif "SPA" in title.upper() or "STOCHASTIC PROCESSES" in title.upper():
                organization = "Bernoulli / Applied Probability"
            elif "IMS" in title.upper():
                organization = "IMS"
            elif "BERNOULLI" in title.upper():
                organization = "Bernoulli Society"

        if not event_type:
            continue

        events.append({
            "title": title,
            "start_date": start,
            "end_date": end,
            "location": location,
            "organization": organization,
            "url": url,
            "event_type": event_type,
            "source": "Applied Probability Trust",
            "last_verified": today_iso(),
            "manual": False,
        })

    return events


def parse_siam_event(url: str):
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    if not title_tag:
        raise RuntimeError("No SIAM h1 found.")
    title = clean_text(title_tag.get_text(" ", strip=True))

    text = clean_text(soup.get_text(" ", strip=True))
    # Example: Event Details February 22–26 , 2027 Pittsburgh, Pennsylvania, U.S.
    m = re.search(
        rf"Event Details.*?({MONTH_PATTERN})\s+(\d{{1,2}})\s*-\s*(\d{{1,2}})\s*,?\s*(20\d{{2}})\s+"
        rf"(.+?)(?:\s+(?:DEADLINES|Announcement|Ask a SIAM|About|Get Involved))",
        text, re.I,
    )
    if not m:
        raise RuntimeError("Could not parse SIAM date/location.")

    mon, d1, d2, year, location = m.groups()
    mm = month_number(mon)
    start = date(int(year), mm, int(d1)).isoformat()
    end = date(int(year), mm, int(d2)).isoformat()

    # The first location phrase is enough; strip venue if it was captured.
    location = re.split(
        r"\s+(?:DEADLINES|Announcement|About|Get Involved|Apply Now|Submit Now)",
        location,
        maxsplit=1,
        flags=re.I,
    )[0].strip(" ,.")

    # If a hotel/venue was concatenated, keep the city/country portion only.
    venue_words = ["Convention Center", "Hilton", "Hyatt", "Hotel", "University"]
    for word in venue_words:
        pos = location.find(word)
        if pos > 0:
            location = location[:pos].strip(" ,.")
            break

    if not active_through(end):
        return None

    organization = "SIAM"
    if "International Congress for Industrial and Applied Mathematics" in title:
        organization = "ICIAM / SIAM"

    return {
        "title": title,
        "start_date": start,
        "end_date": end,
        "location": location,
        "organization": organization,
        "url": url,
        "event_type": "conference",
        "source": "SIAM",
        "last_verified": today_iso(),
        "manual": False,
    }


def parse_ieee_css():
    events = []
    seen = set()

    for suffix in ["", "?page=1"]:
        url = IEEE_CSS_FINANCIAL_URL + suffix
        html = fetch(url)
        soup = BeautifulSoup(html, "html.parser")

        # Extract text blocks around headings; the page exposes title/date/location together.
        for heading in soup.find_all(["h2", "h3", "h4"]):
            title = clean_text(heading.get_text(" ", strip=True))
            if not re.search(
                r"Conference on Decision and Control|American Control Conference|"
                r"Conference on Control Technology and Applications",
                title,
                re.I,
            ):
                continue

            block_text = clean_text(heading.parent.get_text(" ", strip=True))
            parsed = parse_date_range(block_text)
            if not parsed:
                continue
            start, end, _, _ = parsed
            if not active_through(end):
                continue

            # Location usually follows the title/date in the same card.
            location = ""
            strings = [
                clean_text(s)
                for s in heading.parent.stripped_strings
                if clean_text(s)
            ]
            for candidate in strings:
                if candidate == title or re.search(r"\b20\d{2}\b", candidate):
                    continue
                if len(candidate) < 90 and "," in candidate:
                    location = candidate
                    break

            link = heading.find("a", href=True) or heading.parent.find("a", href=True)
            event_url = urljoin(url, link["href"]) if link else url

            key = (title, start)
            if key in seen:
                continue
            seen.add(key)

            events.append({
                "title": title,
                "start_date": start,
                "end_date": end,
                "location": location,
                "organization": "IEEE Control Systems Society",
                "url": event_url,
                "event_type": "conference",
                "source": "IEEE CSS",
                "last_verified": today_iso(),
                "manual": False,
            })

    return events


def parse_bernoulli():
    html = fetch(BERNOULLI_MEETINGS_URL)
    soup = BeautifulSoup(html, "html.parser")
    events = []

    for element in soup.find_all(["li", "p", "article", "div"]):
        text = clean_text(element.get_text(" ", strip=True))
        if not text or not matches_any(text, MAJOR_TITLE_PATTERNS):
            continue
        parsed = parse_date_range(text)
        if not parsed:
            continue
        start, end, begin, _ = parsed
        if not active_through(end):
            continue

        # Keep only Bernoulli/SPA/EMS/world-level meetings from this page.
        if not re.search(
            r"Stochastic Processes and their Applications|Bernoulli[- ]IMS|"
            r"World Congress in Probability and Statistics|European Meeting of Statisticians",
            text,
            re.I,
        ):
            continue

        prefix = text[:begin].strip(" ,.-")
        title = prefix if prefix else text
        title = re.sub(r"^\W+", "", title)

        link = element.find("a", href=True)
        event_url = urljoin(BERNOULLI_MEETINGS_URL, link["href"]) if link else BERNOULLI_MEETINGS_URL

        events.append({
            "title": title,
            "start_date": start,
            "end_date": end,
            "location": "",
            "organization": "Bernoulli Society",
            "url": event_url,
            "event_type": "conference",
            "source": "Bernoulli Society",
            "last_verified": today_iso(),
            "manual": False,
        })

    return events


def seeded_events():
    events = []
    for item in CURATED_SEED_EVENTS:
        item = dict(item)
        item["last_verified"] = today_iso()
        if active_through(item.get("end_date")):
            events.append(item)
    return events


def same_event(a: dict, b: dict) -> bool:
    if a.get("start_date") != b.get("start_date"):
        return False
    x = normalize_title(a.get("title", ""))
    y = normalize_title(b.get("title", ""))
    return x == y or SequenceMatcher(None, x, y).ratio() >= 0.82


def deduplicate(events: list[dict]) -> list[dict]:
    output = []
    for event in sorted(
        events,
        key=lambda x: (x.get("start_date", "9999-12-31"), x.get("title", "")),
    ):
        idx = next((i for i, old in enumerate(output) if same_event(old, event)), None)
        if idx is None:
            output.append(event)
            continue

        old = output[idx]
        # Prefer richer official source metadata.
        if event.get("location") and not old.get("location"):
            old["location"] = event["location"]
        if event.get("organization") and old.get("organization") in {"Community", "School"}:
            old["organization"] = event["organization"]
        if event.get("url") and event.get("source") in {"SIAM", "IEEE CSS", "Bernoulli Society"}:
            old["url"] = event["url"]
            old["source"] = event["source"]
        old["last_verified"] = max(
            old.get("last_verified", ""),
            event.get("last_verified", ""),
        )

    return output


def main():
    previous = load_json(DATA_FILE, [])
    manual = [
        item
        for item in previous
        if item.get("manual") and active_through(item.get("end_date"))
    ]

    collected = []
    failures = []

    # APT: schools + only whitelisted community-wide conferences.
    try:
        collected.extend(parse_apt())
    except Exception as exc:
        failures.append(f"APT: {exc}")

    # SIAM: direct official event pages.
    for url in SIAM_MAJOR_EVENT_URLS:
        try:
            event = parse_siam_event(url)
            if event:
                collected.append(event)
        except Exception as exc:
            failures.append(f"SIAM {url}: {exc}")

    # IEEE CSS flagship/sponsored conferences.
    try:
        collected.extend(parse_ieee_css())
    except Exception as exc:
        failures.append(f"IEEE CSS: {exc}")

    # Bernoulli/SPA/world meetings.
    try:
        collected.extend(parse_bernoulli())
    except Exception as exc:
        failures.append(f"Bernoulli: {exc}")

    collected.extend(seeded_events())

    # If a source temporarily fails, keep previous non-expired automatic records
    # from that source so the page never goes blank.
    failed_names = set()
    for failure in failures:
        if failure.startswith("APT"):
            failed_names.add("Applied Probability Trust")
        elif failure.startswith("SIAM"):
            failed_names.add("SIAM")
        elif failure.startswith("IEEE"):
            failed_names.add("IEEE CSS")
        elif failure.startswith("Bernoulli"):
            failed_names.add("Bernoulli Society")

    preserved = [
        item
        for item in previous
        if not item.get("manual")
        and item.get("source") in failed_names
        and active_through(item.get("end_date"))
    ]

    final = deduplicate(manual + collected + preserved)
    final = [item for item in final if active_through(item.get("end_date"))]
    final.sort(
        key=lambda x: (
            x.get("event_type") != "conference",
            x.get("start_date", "9999-12-31"),
            x.get("title", ""),
        )
    )
    save_json(DATA_FILE, final)

    print(f"Saved {len(final)} curated conferences/schools.")
    for failure in failures:
        print("WARNING:", failure)


if __name__ == "__main__":
    main()
