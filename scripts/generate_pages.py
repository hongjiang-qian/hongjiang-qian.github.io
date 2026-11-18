from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo
from html import escape

from bs4 import BeautifulSoup

from common import DATA_DIR, ROOT, event_date_display, load_json
from config import CONF_HTML, FUND_HTML, TEMPLATE_HTML


PAGE_STYLE = r"""
.auto-page-note {
    color: #666666;
    font-style: italic;
    margin-bottom: 1.0em;
}

.auto-tabs {
    margin: 0.9em 0 1.2em 0;
    border-bottom: 1px solid #c8c8c8;
    padding-bottom: 0.45em;
}

.auto-tab {
    font-family: inherit;
    font-size: 95%;
    color: #555555;
    background: #eeeeee;
    border: 1px solid #c5c5c5;
    border-bottom-color: #b8b8b8;
    padding: 0.32em 0.9em;
    margin-right: 0.35em;
    cursor: pointer;
}

.auto-tab:hover {
    background: #e5e5e5;
}

.auto-tab.active {
    color: #224b8d;
    background: #e9eef5;
    border-color: #9fb0c6;
    font-weight: bold;
}

.auto-panel {
    display: none;
}

.auto-panel.active {
    display: block;
}

.auto-conf-list,
.auto-fund-list {
    list-style: none !important;
    margin-left: 0 !important;
    padding-left: 0 !important;
}

.auto-conf-item {
    display: grid;
    grid-template-columns: 145px minmax(0, 1fr);
    column-gap: 18px;
    align-items: start;
    margin: 0;
    padding: 0.45em 0 0.65em 0;
    border-bottom: 1px solid #eeeeee;
}

.auto-conf-item:last-child {
    border-bottom: none;
}

.auto-conf-date {
    color: #666666;
    white-space: nowrap;
}

.auto-conf-title {
    line-height: 1.25;
}

.auto-conf-meta {
    color: #777777;
    font-size: 95%;
    margin-top: 0.08em;
    line-height: 1.3;
}

.auto-fund-item {
    margin: 0 !important;
    padding: 0.62em 0 0.78em 0 !important;
    border-bottom: 1px solid #dddddd;
}

.auto-fund-item:last-child {
    border-bottom: none;
}

.auto-fund-title {
    font-weight: bold;
    line-height: 1.3;
}

.auto-fund-meta {
    color: #666666;
    font-size: 95%;
    margin-top: 0.12em;
}

.auto-fund-deadline {
    margin-top: 0.12em;
}

.auto-verified {
    color: #888888;
    font-size: 88%;
    font-style: italic;
    margin-top: 0.08em;
}

@media screen and (max-width: 700px) {
    .auto-conf-item {
        grid-template-columns: 1fr;
        row-gap: 0.05em;
    }

    .auto-tab {
        margin-bottom: 0.35em;
    }
}
"""

TAB_SCRIPT = r"""
(function () {
    var buttons = document.querySelectorAll('.auto-tab');
    var panels = document.querySelectorAll('.auto-panel');

    function showPanel(target) {
        buttons.forEach(function (button) {
            button.classList.toggle(
                'active',
                button.getAttribute('data-target') === target
            );
        });

        panels.forEach(function (panel) {
            panel.classList.toggle(
                'active',
                panel.id === target
            );
        });
    }

    buttons.forEach(function (button) {
        button.addEventListener('click', function () {
            showPanel(button.getAttribute('data-target'));
        });
    });
})();
"""


def eastern_update_timestamp():
    """Current America/Detroit time, including EST/EDT automatically."""
    now = datetime.now(ZoneInfo("America/Detroit"))
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")


def visible_events():
    today = date.today()
    output = []

    for item in load_json(DATA_DIR / "conferences.json", []):
        try:
            end = date.fromisoformat(item.get("end_date") or item["start_date"])
        except Exception:
            continue

        if end >= today:
            output.append(item)

    return sorted(
        output,
        key=lambda x: (x["start_date"], x.get("title", "")),
    )


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


def fallback_template():
    return BeautifulSoup(
        """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="jemdoc.css" type="text/css">
<title>Academic page</title>
</head>
<body>
<table id="tlayout">
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


def load_template():
    path = ROOT / TEMPLATE_HTML
    if path.exists():
        return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    return fallback_template()


def add_page_assets(soup, add_tabs=False):
    head = soup.find("head")
    if head:
        old_style = head.find("style", attrs={"id": "academic-auto-page-style"})
        if old_style:
            old_style.decompose()
        style = soup.new_tag("style")
        style["id"] = "academic-auto-page-style"
        style.string = PAGE_STYLE
        head.append(style)

    if add_tabs:
        body = soup.find("body")
        if body:
            old_script = body.find("script", attrs={"id": "academic-auto-tabs"})
            if old_script:
                old_script.decompose()
            script = soup.new_tag("script")
            script["id"] = "academic-auto-tabs"
            script.string = TAB_SCRIPT
            body.append(script)


def make_menu_item(soup, label, href):
    div = soup.new_tag("div")
    div["class"] = "menu-item"
    link = soup.new_tag("a", href=href)
    link.string = label
    div.append(link)
    return div


def ensure_misc_links(soup):
    """Conferences and Funding are the first two items under Misc."""
    menu = soup.find(id="layout-menu")
    if menu is None:
        return

    for a in list(menu.find_all("a", href=True)):
        if a.get("href") in {CONF_HTML, FUND_HTML}:
            parent = a.find_parent("div", class_="menu-item")
            if parent:
                parent.decompose()

    misc = None
    for div in menu.find_all("div", class_="menu-category"):
        if div.get_text(" ", strip=True).lower() == "misc":
            misc = div
            break

    if misc is None:
        misc = soup.new_tag("div")
        misc["class"] = "menu-category"
        misc.string = "Misc"
        menu.append(misc)

    fund_item = make_menu_item(soup, "Funding", FUND_HTML)
    conf_item = make_menu_item(soup, "Conferences", CONF_HTML)

    # Insert in reverse because insert_after always uses the same anchor.
    misc.insert_after(fund_item)
    misc.insert_after(conf_item)


def mark_current(soup, href):
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


def replace_content(soup, title, body_html, current_href, add_tabs=False):
    ensure_misc_links(soup)
    mark_current(soup, current_href)
    add_page_assets(soup, add_tabs=add_tabs)

    if soup.title:
        soup.title.string = title

    content = soup.find(id="layout-content")
    if content is None:
        raise RuntimeError("Template does not contain #layout-content.")

    content.clear()
    fragment = BeautifulSoup(
        f'<div id="toptitle"><h1>{escape(title)}</h1></div>{body_html}',
        "html.parser",
    )

    for child in list(fragment.contents):
        content.append(child)


def event_list_html(items, empty_message):
    if not items:
        return f"<p>{escape(empty_message)}</p>"

    grouped = defaultdict(lambda: defaultdict(list))
    for item in items:
        d = date.fromisoformat(item["start_date"])
        grouped[d.year][d.month].append(item)

    pieces = []

    for year in sorted(grouped):
        pieces.append(f"<h2>{year}</h2>")

        for month in sorted(grouped[year]):
            month_name = date(2000, month, 1).strftime("%B")
            pieces.append(f"<h3>{month_name}</h3>")
            pieces.append('<ul class="auto-conf-list">')

            for item in grouped[year][month]:
                dates = escape(
                    event_date_display(
                        item["start_date"],
                        item.get("end_date"),
                    )
                )
                title = escape(item.get("title", "Untitled event"))
                url = escape(
                    item.get("url") or "#",
                    quote=True,
                )
                organization = escape(item.get("organization", ""))
                location = escape(item.get("location", ""))

                meta_parts = [x for x in [organization, location] if x]
                meta = " &middot; ".join(meta_parts)

                pieces.append('<li class="auto-conf-item">')
                pieces.append(f'<div class="auto-conf-date">{dates}</div>')
                pieces.append('<div class="auto-conf-main">')
                pieces.append(
                    f'<div class="auto-conf-title">'
                    f'<a href="{url}" target="_blank">{title}</a>'
                    f'</div>'
                )
                if meta:
                    pieces.append(f'<div class="auto-conf-meta">{meta}</div>')
                pieces.append("</div>")
                pieces.append("</li>")

            pieces.append("</ul>")

    return "\n".join(pieces)


def conference_body(items):
    conferences = [
        item for item in items
        if item.get("event_type") == "conference"
    ]
    schools = [
        item for item in items
        if item.get("event_type") == "school"
    ]

    pieces = [
        "<p>A curated list of major meetings in mathematics, applied mathematics, "
        "probability, statistics, and control, together with selected schools.</p>",
        '<p class="auto-page-note">This page is updated automatically from official '
        "society and community sources.</p>",
        '<div class="auto-tabs">',
        '<button type="button" class="auto-tab active" '
        'data-target="auto-conferences">Conferences</button>',
        '<button type="button" class="auto-tab" '
        'data-target="auto-schools">Schools</button>',
        "</div>",
        '<div id="auto-conferences" class="auto-panel active">',
        event_list_html(
            conferences,
            "No upcoming major conferences are currently listed.",
        ),
        "</div>",
        '<div id="auto-schools" class="auto-panel">',
        event_list_html(
            schools,
            "No upcoming schools are currently listed.",
        ),
        "</div>",
    ]

    pieces.append(
        '<div id="footer"><div id="footer-text">'
        + eastern_update_timestamp()
        + '</div></div>'
    )

    return "\n".join(pieces)


def funding_entry(item):
    title = escape(item.get("title", "Funding opportunity"))
    url = escape(item.get("url", "#"), quote=True)
    sponsor = escape(item.get("sponsor", ""))
    kind = escape(item.get("kind", ""))
    deadline = escape(item.get("deadline_display", "TBA"))

    pieces = ['<li class="auto-fund-item">']
    pieces.append(
        f'<div class="auto-fund-title">'
        f'<a href="{url}" target="_blank">{title}</a></div>'
    )

    meta = " &middot; ".join(x for x in [sponsor, kind] if x)
    if meta:
        pieces.append(f'<div class="auto-fund-meta">{meta}</div>')

    pieces.append(
        f'<div class="auto-fund-deadline"><b>Deadline:</b> {deadline}</div>'
    )
    pieces.append("</li>")
    return "\n".join(pieces)


def funding_body(items):
    dated = [
        item for item in items
        if item.get("deadline_type") == "date"
    ]
    flexible = [
        item for item in items
        if item.get("deadline_type") != "date"
    ]

    pieces = [
        "<p>A selected list of external research and travel funding opportunities "
        "relevant to mathematics and the mathematical sciences.</p>",
        '<p class="auto-page-note">Only external funding is listed. '
        "Deadlines are verified from official program pages.</p>",
    ]

    if dated:
        pieces.append("<h2>Upcoming Deadlines</h2>")
        pieces.append('<ul class="auto-fund-list">')
        for item in dated:
            pieces.append(funding_entry(item))
        pieces.append("</ul>")

    if flexible:
        pieces.append("<h2>Rolling or No Fixed Deadline</h2>")
        pieces.append('<ul class="auto-fund-list">')
        for item in flexible:
            pieces.append(funding_entry(item))
        pieces.append("</ul>")

    pieces.append(
        '<div id="footer"><div id="footer-text">'
        + eastern_update_timestamp()
        + '</div></div>'
    )

    return "\n".join(pieces)


def write_page(filename, title, body_html, add_tabs=False):
    soup = load_template()
    replace_content(
        soup,
        title,
        body_html,
        filename,
        add_tabs=add_tabs,
    )
    (ROOT / filename).write_text(str(soup), encoding="utf-8")


def main():
    events = visible_events()
    funding = visible_funding()

    write_page(
        CONF_HTML,
        "Conferences and Schools",
        conference_body(events),
        add_tabs=True,
    )
    write_page(
        FUND_HTML,
        "Funding Opportunities",
        funding_body(funding),
        add_tabs=False,
    )

    print(
        f"Generated {CONF_HTML}: "
        f"{sum(x.get('event_type') == 'conference' for x in events)} conferences, "
        f"{sum(x.get('event_type') == 'school' for x in events)} schools."
    )
    print(f"Generated {FUND_HTML}: {len(funding)} opportunities.")


if __name__ == "__main__":
    main()
