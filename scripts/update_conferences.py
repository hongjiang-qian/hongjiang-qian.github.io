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
    """Parse flagship Bernoulli/IMS meetings by their dedicated series sections.

    The Bernoulli meetings page contains a nested "Upcoming meetings" list, where
    an outer <li> may contain several child meetings. Parsing arbitrary <li> nodes
    can therefore merge RobStat, SPA, WSC, EMS, etc. into one title.

    Instead, this parser locates the dedicated series headings and reads only the
    first upcoming record under each series:
      - Bernoulli-IMS World Congress
      - Conference on Stochastic Processes and their Applications (SPA)
      - ISI World Statistics Congress
      - European Meeting of Statisticians (EMS)
    """
    html = fetch(BERNOULLI_MEETINGS_URL)
    soup = BeautifulSoup(html, "html.parser")
    events = []

    series_specs = [
        {
            "heading": "Bernoulli-IMS World Congress in Probability and Statistics",
            "title_suffix": "Bernoulli-IMS World Congress in Probability and Statistics",
            "organization": "Bernoulli Society / IMS",
        },
        {
            "heading": "Conference on Stochastic Processes and their Applications (SPA)",
            "title_suffix": "Conference on Stochastic Processes and their Applications (SPA)",
            "organization": "Bernoulli Society",
        },
        {
            "heading": "ISI World Statistics Congress",
            "title_suffix": "World Statistics Congress",
            "organization": "ISI",
        },
        {
            "heading": "European Meeting of Statisticians (EMS)",
            "title_suffix": "European Meeting of Statisticians (EMS)",
            "organization": "Bernoulli Society",
        },
    ]

    for spec in series_specs:
        heading_node = None

        # Find an element whose own visible text is the series heading.
        for candidate in soup.find_all(["h1", "h2", "h3", "h4", "p", "div"]):
            text = clean_text(candidate.get_text(" ", strip=True))
            if text == spec["heading"]:
                heading_node = candidate
                break

        # Fallback: exact string search, then use its parent element.
        if heading_node is None:
            string_node = soup.find(
                string=lambda s: isinstance(s, str)
                and clean_text(s) == spec["heading"]
            )
            if string_node is not None:
                heading_node = string_node.parent

        if heading_node is None:
            continue

        # The first <li> after the series heading is the next/current listed edition.
        item = heading_node.find_next("li")
        if item is None:
            continue

        text = clean_text(item.get_text(" ", strip=True))
        parsed = parse_date_range(text)
        if not parsed:
            continue

        start, end, _, _ = parsed
        if not active_through(end):
            continue

        # Edition number: "46th", "66th", "36th", "12th", ...
        edition_match = re.match(r"^\s*(\d+(?:st|nd|rd|th))\b", text, re.I)
        edition = edition_match.group(1) if edition_match else ""

        # Location is the text between "in" and the date.
        # Examples:
        #   "46th 2027 in Melbourne, Australia, July 5-9, ..."
        #   "66th World Statistics Congress in Lusaka, Zambia, July 11-15, ..."
        date_token = re.search(
            rf"(?:{MONTH_PATTERN})\s+\d{{1,2}}\s*-\s*\d{{1,2}}\s*,?\s*20\d{{2}}|"
            rf"\d{{1,2}}\s*-\s*\d{{1,2}}\s+(?:{MONTH_PATTERN})\s*,?\s*20\d{{2}}",
            text,
            re.I,
        )

        location = ""
        if date_token:
            before_date = text[:date_token.start()].strip(" ,.")
            in_match = re.search(r"\bin\s+(.+)$", before_date, re.I)
            if in_match:
                location = in_match.group(1).strip(" ,.")

        # Build a clean canonical title from the series name.
        if spec["heading"] == "ISI World Statistics Congress":
            title = (
                f"{edition} World Statistics Congress"
                if edition
                else "World Statistics Congress"
            )
        else:
            title = (
                f"{edition} {spec['title_suffix']}"
                if edition
                else spec["title_suffix"]
            )

        # Prefer the event website link inside this exact list item.
        event_url = BERNOULLI_MEETINGS_URL
        website_link = None

        for link in item.find_all("a", href=True):
            label = clean_text(link.get_text(" ", strip=True)).lower()
            if "website" in label or "conference" in label:
                website_link = link
                break

        if website_link is None:
            website_link = item.find("a", href=True)

        if website_link is not None:
            event_url = urljoin(
                BERNOULLI_MEETINGS_URL,
                website_link["href"],
            )

        events.append({
            "title": title,
            "start_date": start,
            "end_date": end,
            "location": location,
            "organization": spec["organization"],
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
