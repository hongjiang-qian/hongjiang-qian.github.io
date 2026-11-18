from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from common import DATA_DIR, ROOT, event_date_display, load_json
from config import CONF_HTML, FUND_HTML, TEMPLATE_HTML


def visible_conferences():
    today = date.today()
    output = []
    for item in load_json(DATA_DIR / "conferences.json", []):
        try:
            end = date.fromisoformat(item.get("end_date") or item["start_date"])
        except Exception:
            continue
        if end >= today:
            output.append(item)
    return sorted(output, key=lambda x: (x["start_date"], x.get("title", "")))


def visible_funding():
    today = date.today()
    output = []
    for item in load_json(DATA_DIR / "funding.json", []):
        if item.get("deadline_type") == "date" and item.get("deadline_date"):
            try:
                if date.fromisoformat(item["deadline_date"]) < today:
                    continue
            except ValueError:
                pass
        output.append(item)

    def sort_key(item):
        if item.get("deadline_type") == "date" and item.get("deadline_date"):
            return (0, item["deadline_date"], item.get("title", ""))
        if item.get("deadline_type") == "rolling":
            return (1, "9999-01-01", item.get("title", ""))
        if item.get("deadline_type") == "anytime":
            return (2, "9999-01-02", item.get("title", ""))
        return (3, "9999-12-31", item.get("title", ""))

    return sorted(output, key=sort_key)


def fallback_template() -> BeautifulSoup:
    return BeautifulSoup(
        """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="jemdoc.css" type="text/css">
<title>Academic page</title>
</head>
<body>
<table id="tlayout" summary="Table for page layout.">
<tr valign="top">
<td id="layout-menu">
<div class="menu-category">Menu</div>
<div class="menu-item"><a href="index.html">Home</a></div>
<div class="menu-item"><a href="bio.html">Biography</a></div>
<div class="menu-item"><a href="pub.html">Publications</a></div>
<div class="menu-item"><a href="teach.html">Teaching</a></div>
<div class="menu-item"><a href="act.html">Activities</a></div>
<div class="menu-category">Misc</div>
</td>
<td id="layout-content"></td>
</tr>
</table>
</body>
</html>""",
        "html.parser",
    )


def load_template() -> BeautifulSoup:
    path = ROOT / TEMPLATE_HTML
    if path.exists():
        return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    return fallback_template()


def ensure_extra_menu_links(soup: BeautifulSoup):
    menu = soup.find(id="layout-menu")
    if menu is None:
        return

    existing = {a.get("href") for a in menu.find_all("a", href=True)}
    anchor_div = None

    for a in menu.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        href = (a.get("href") or "").lower()
        if text == "activities" or href in {"act.html", "activities.html"}:
            anchor_div = a.find_parent("div", class_="menu-item")
            break

    if anchor_div is None:
        misc = None
        for div in menu.find_all("div", class_="menu-category"):
            if div.get_text(" ", strip=True).lower() == "misc":
                misc = div
                break
        anchor_div = misc

    def make_item(label, href):
        div = soup.new_tag("div")
        div["class"] = "menu-item"
        a = soup.new_tag("a", href=href)
        a.string = label
        div.append(a)
        return div

    current_anchor = anchor_div
    if CONF_HTML not in existing:
        item = make_item("Conferences", CONF_HTML)
        if current_anchor:
            current_anchor.insert_after(item)
        else:
            menu.append(item)
        current_anchor = item

    if FUND_HTML not in existing:
        item = make_item("Funding", FUND_HTML)
        if current_anchor:
            current_anchor.insert_after(item)
        else:
            menu.append(item)


def mark_current(soup: BeautifulSoup, href: str):
    menu = soup.find(id="layout-menu")
    if not menu:
        return
    for a in menu.find_all("a"):
        classes = [c for c in a.get("class", []) if c != "current"]
        if classes:
            a["class"] = classes
        elif a.has_attr("class"):
            del a["class"]
        if a.get("href") == href:
            a["class"] = a.get("class", []) + ["current"]


def replace_content(soup: BeautifulSoup, title: str, body_html: str, current_href: str):
    ensure_extra_menu_links(soup)
    mark_current(soup, current_href)

    if soup.title:
        soup.title.string = title

    content = soup.find(id="layout-content")
    if content is None:
        raise RuntimeError("Template does not contain #layout-content.")

    content.clear()
    fragment = BeautifulSoup(
        f'<div id="toptitle"><h1>{title}</h1></div>{body_html}',
        "html.parser",
    )
    for child in list(fragment.contents):
        content.append(child)


def conference_body(items) -> str:
    pieces = [
        "<p>A selected list of upcoming conferences, workshops, and schools in "
        "probability, stochastic analysis, stochastic control, SPDEs, and related areas.</p>",
        "<p><i>This page is updated automatically.</i></p>",
    ]

    if not items:
        pieces.append("<p>No upcoming events are currently listed.</p>")
        return "\n".join(pieces)

    grouped = defaultdict(lambda: defaultdict(list))
    for item in items:
        d = date.fromisoformat(item["start_date"])
        grouped[d.year][d.month].append(item)

    for year in sorted(grouped):
        pieces.append(f"<h2>{year}</h2>")
        for month in sorted(grouped[year]):
            month_name = date(2000, month, 1).strftime("%B")
            pieces.append(f"<h3>{month_name}</h3>")
            pieces.append("<ul>")
            for item in grouped[year][month]:
                dates = event_date_display(item["start_date"], item.get("end_date"))
                url = item.get("url") or item.get("source_url") or "#"
                title = item.get("title", "Untitled event")
                location = item.get("location", "")
                pieces.append("<li><p>")
                pieces.append(f"<b>{dates}</b><br />")
                pieces.append(f'<a href="{url}" target="_blank">{title}</a>')
                if location:
                    pieces.append(f"<br />{location}")
                pieces.append("</p></li>")
            pieces.append("</ul>")

    verified = [x.get("last_verified") for x in items if x.get("last_verified")]
    if verified:
        pieces.append(
            f'<div id="footer"><div id="footer-text">'
            f'Conference sources last verified {max(verified)}.'
            f'</div></div>'
        )
    return "\n".join(pieces)


def funding_body(items) -> str:
    dated = [x for x in items if x.get("deadline_type") == "date"]
    flexible = [x for x in items if x.get("deadline_type") != "date"]

    pieces = [
        "<p>A selected list of external research and travel funding opportunities "
        "relevant to mathematics and the mathematical sciences.</p>",
        "<p><i>Only external funding is listed. Exact deadlines are taken from "
        "official program pages.</i></p>",
    ]

    if dated:
        pieces.append("<h2>Upcoming Deadlines</h2><ul>")
        for item in dated:
            pieces.append("<li><p>")
            pieces.append(
                f'<a href="{item.get("url", "#")}" target="_blank">'
                f'<b>{item.get("title", "Funding opportunity")}</b></a><br />'
            )
            meta = " &middot; ".join(
                x for x in [item.get("sponsor", ""), item.get("kind", "")] if x
            )
            if meta:
                pieces.append(meta + "<br />")
            pieces.append(f'<b>Deadline:</b> {item.get("deadline_display", "TBA")}')
            if item.get("last_verified"):
                pieces.append(f'<br /><i>Last verified: {item["last_verified"]}</i>')
            pieces.append("</p></li>")
        pieces.append("</ul>")

    if flexible:
        pieces.append("<h2>Rolling or No Fixed Deadline</h2><ul>")
        for item in flexible:
            pieces.append("<li><p>")
            pieces.append(
                f'<a href="{item.get("url", "#")}" target="_blank">'
                f'<b>{item.get("title", "Funding opportunity")}</b></a><br />'
            )
            meta = " &middot; ".join(
                x for x in [item.get("sponsor", ""), item.get("kind", "")] if x
            )
            if meta:
                pieces.append(meta + "<br />")
            pieces.append(f'<b>Deadline:</b> {item.get("deadline_display", "TBA")}')
            if item.get("last_verified"):
                pieces.append(f'<br /><i>Last verified: {item["last_verified"]}</i>')
            pieces.append("</p></li>")
        pieces.append("</ul>")

    if not items:
        pieces.append("<p>No currently open opportunities are listed.</p>")

    verified = [x.get("last_verified") for x in items if x.get("last_verified")]
    if verified:
        pieces.append(
            f'<div id="footer"><div id="footer-text">'
            f'Funding sources last verified {max(verified)}.'
            f'</div></div>'
        )
    return "\n".join(pieces)


def write_page(filename: str, title: str, body_html: str):
    soup = load_template()
    replace_content(soup, title, body_html, filename)
    (ROOT / filename).write_text(str(soup), encoding="utf-8")


def main():
    conferences = visible_conferences()
    funding = visible_funding()

    write_page(CONF_HTML, "Conferences and Schools", conference_body(conferences))
    write_page(FUND_HTML, "Funding Opportunities", funding_body(funding))

    print(f"Generated {CONF_HTML} ({len(conferences)} events)")
    print(f"Generated {FUND_HTML} ({len(funding)} opportunities)")


if __name__ == "__main__":
    main()
