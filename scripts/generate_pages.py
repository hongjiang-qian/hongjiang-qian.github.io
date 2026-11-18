from __future__ import annotations

import html
import re
from collections import defaultdict
from datetime import date

from common import DATA_DIR, ROOT, date_display, load_json
from config import (
    CONFERENCE_HTML, CONFERENCE_JEMDOC, CONFERENCE_PAGE_INTRO, CONFERENCE_PAGE_TITLE,
    FUNDING_HTML, FUNDING_JEMDOC, FUNDING_PAGE_INTRO, FUNDING_PAGE_TITLE,
)

CONF_START = "# AUTO-GENERATED-CONFERENCES-START"
CONF_END = "# AUTO-GENERATED-CONFERENCES-END"
FUND_START = "# AUTO-GENERATED-FUNDING-START"
FUND_END = "# AUTO-GENERATED-FUNDING-END"
MENU_PATH = ROOT / "MENU"

def escape_jemdoc(text: str) -> str:
    return text.replace("[", r"\[").replace("]", r"\]")

def ensure_menu_entries() -> None:
    if MENU_PATH.exists():
        lines = MENU_PATH.read_text(encoding="utf-8").splitlines()
    else:
        lines = [
            "Menu", "Home [index.html]", "Biography [bio.html]", "Research [research.html]",
            "Publications [pub.html]", "Teaching [teach.html]", "Prof Activities [act.html]",
            "Misc", "Links [link.html]",
        ]
    targets = set()
    for line in lines:
        m = re.search(r"\[([^\]]+)\]", line)
        if m:
            targets.add(m.group(1))
    additions = []
    if CONFERENCE_HTML not in targets:
        additions.append(f"Conferences [{CONFERENCE_HTML}]")
    if FUNDING_HTML not in targets:
        additions.append(f"Funding [{FUNDING_HTML}]")
    if additions:
        try:
            idx = lines.index("Misc")
        except ValueError:
            idx = len(lines)
        lines[idx:idx] = additions
        MENU_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

def patch_or_create_jemdoc(path, title: str, intro: str, start: str, end: str, block: str) -> None:
    if path.exists():
        original = path.read_text(encoding="utf-8")
    else:
        original = f"# jemdoc: menu{{MENU}}{{{path.with_suffix('.html').name}}}\n\n= {title}\n\n{intro}\n"
    replacement = f"{start}\n{block.rstrip()}\n{end}"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    result = pattern.sub(replacement, original) if pattern.search(original) else original.rstrip() + "\n\n" + replacement + "\n"
    path.write_text(result, encoding="utf-8")

def current_conferences():
    items = load_json(DATA_DIR / "conferences.json", [])
    today = date.today()
    out = []
    for item in items:
        try:
            end = date.fromisoformat(item.get("end_date") or item["start_date"])
        except Exception:
            continue
        if end >= today:
            out.append(item)
    return sorted(out, key=lambda x: (x["start_date"], x.get("title", "")))

def current_funding():
    items = load_json(DATA_DIR / "funding.json", [])
    today = date.today()
    out = []
    for item in items:
        if item.get("deadline_type") == "date" and item.get("deadline_date"):
            try:
                if date.fromisoformat(item["deadline_date"]) < today:
                    continue
            except ValueError:
                pass
        out.append(item)
    def key(item):
        if item.get("deadline_type") == "date" and item.get("deadline_date"):
            return (0, item["deadline_date"], item.get("title", ""))
        if item.get("deadline_type") == "rolling":
            return (1, "9999-01-01", item.get("title", ""))
        if item.get("deadline_type") == "anytime":
            return (2, "9999-01-02", item.get("title", ""))
        return (3, "9999-12-31", item.get("title", ""))
    return sorted(out, key=key)

def conference_jemdoc_block(items) -> str:
    if not items:
        return "No upcoming events are currently listed."
    grouped = defaultdict(lambda: defaultdict(list))
    for item in items:
        d = date.fromisoformat(item["start_date"])
        grouped[d.year][d.month].append(item)
    month_names = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    lines = []
    for year in sorted(grouped):
        lines += [f"== {year}", ""]
        for month in sorted(grouped[year]):
            lines += [f"=== {month_names[month]}", ""]
            for item in grouped[year][month]:
                title = escape_jemdoc(item.get("title", "Untitled event"))
                url = item.get("url") or item.get("source_url") or "#"
                location = escape_jemdoc(item.get("location", ""))
                dates = date_display(item["start_date"], item.get("end_date"))
                lines.append(f"- *{dates}* \\")
                lines.append(f"  [{url} {title}]")
                if location:
                    lines[-1] += r" \\" 
                    lines.append(f"  {location}")
                lines.append("")
    return "\n".join(lines)

def funding_jemdoc_block(items) -> str:
    if not items:
        return "No currently open opportunities are listed."
    lines = ["== Open and Upcoming", ""]
    for item in items:
        title = escape_jemdoc(item.get("title", "Funding opportunity"))
        sponsor = escape_jemdoc(item.get("sponsor", ""))
        kind = escape_jemdoc(item.get("kind", ""))
        deadline = escape_jemdoc(item.get("deadline_display", "TBA"))
        url = item.get("url", "#")
        verified = item.get("last_verified")
        lines.append(f"- [{url} {title}] \\")
        if sponsor or kind:
            lines.append(f"  {' · '.join(x for x in [sponsor, kind] if x)} \\")
        lines.append(f"  *Deadline:* {deadline}")
        if verified:
            lines[-1] += r" \\" 
            lines.append(f"  /Last verified: {verified}/")
        lines.append("")
    return "\n".join(lines)

def parse_menu():
    if not MENU_PATH.exists():
        return []
    out = []
    for raw in MENU_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"(.+?)\s*\[([^\]]+)\]\s*$", line)
        out.append(("item", m.group(1).strip(), m.group(2).strip()) if m else ("category", line, None))
    return out

def menu_html(current: str) -> str:
    chunks = []
    for kind, label, target in parse_menu():
        if kind == "category":
            chunks.append(f'<div class="menu-category">{html.escape(label)}</div>')
        else:
            css = ' class="current"' if target == current else ""
            chunks.append(f'<div class="menu-item"><a href="{html.escape(target)}"{css}>{html.escape(label)}</a></div>')
    return "\n".join(chunks)

def page_shell(title: str, current_html: str, body: str, verified_dates) -> str:
    dates = [x for x in verified_dates if x]
    last_verified = max(dates) if dates else date.today().isoformat()
    return '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
<meta name="generator" content="automatic academic opportunities updater" />
<meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
<link rel="stylesheet" href="jemdoc.css" type="text/css" />
<title>{title}</title>
</head>
<body>
<table summary="Table for page layout." id="tlayout">
<tr valign="top">
<td id="layout-menu">
{menu}
</td>
<td id="layout-content">
<div id="toptitle"><h1>{title}</h1></div>
{body}
<div id="footer"><div id="footer-text">
Information automatically updated from public source pages. Last verified {verified}.
</div></div>
</td>
</tr>
</table>
</body>
</html>
'''.format(title=html.escape(title), menu=menu_html(current_html), body=body, verified=html.escape(last_verified))

def conference_html_body(items) -> str:
    chunks = [f"<p>{html.escape(CONFERENCE_PAGE_INTRO)}</p>", "<p><i>This page is updated automatically.</i></p>"]
    grouped = defaultdict(lambda: defaultdict(list))
    for item in items:
        d = date.fromisoformat(item["start_date"])
        grouped[d.year][d.month].append(item)
    for year in sorted(grouped):
        chunks.append(f"<h2>{year}</h2>")
        for month in sorted(grouped[year]):
            chunks.append(f"<h3>{date(2000, month, 1).strftime('%B')}</h3>")
            chunks.append("<ul>")
            for item in grouped[year][month]:
                title = html.escape(item.get("title", "Untitled event"))
                url = html.escape(item.get("url") or item.get("source_url") or "#", quote=True)
                location = html.escape(item.get("location", ""))
                dates = html.escape(date_display(item["start_date"], item.get("end_date")))
                text = f'<li><p><b>{dates}</b><br /><a href="{url}" target="_blank">{title}</a>'
                if location:
                    text += f"<br />{location}"
                chunks.append(text + "</p></li>")
            chunks.append("</ul>")
    return "\n".join(chunks)

def funding_html_body(items) -> str:
    chunks = [
        f"<p>{html.escape(FUNDING_PAGE_INTRO)}</p>",
        "<p><i>Only external funding is listed. Deadlines are taken from official program pages.</i></p>",
        "<h2>Open and Upcoming</h2>", "<ul>",
    ]
    for item in items:
        title = html.escape(item.get("title", "Funding opportunity"))
        url = html.escape(item.get("url", "#"), quote=True)
        sponsor = html.escape(item.get("sponsor", ""))
        kind = html.escape(item.get("kind", ""))
        deadline = html.escape(item.get("deadline_display", "TBA"))
        verified = html.escape(item.get("last_verified") or "")
        text = f'<li><p><a href="{url}" target="_blank"><b>{title}</b></a><br />'
        meta = " &middot; ".join(x for x in [sponsor, kind] if x)
        if meta:
            text += meta + "<br />"
        text += f"<b>Deadline:</b> {deadline}"
        if verified:
            text += f"<br /><i>Last verified: {verified}</i>"
        chunks.append(text + "</p></li>")
    chunks.append("</ul>")
    return "\n".join(chunks)

def main() -> None:
    ensure_menu_entries()
    conferences, funding = current_conferences(), current_funding()
    patch_or_create_jemdoc(ROOT / CONFERENCE_JEMDOC, CONFERENCE_PAGE_TITLE, CONFERENCE_PAGE_INTRO, CONF_START, CONF_END, conference_jemdoc_block(conferences))
    patch_or_create_jemdoc(ROOT / FUNDING_JEMDOC, FUNDING_PAGE_TITLE, FUNDING_PAGE_INTRO, FUND_START, FUND_END, funding_jemdoc_block(funding))
    (ROOT / CONFERENCE_HTML).write_text(page_shell(CONFERENCE_PAGE_TITLE, CONFERENCE_HTML, conference_html_body(conferences), [x.get("last_verified") for x in conferences]), encoding="utf-8")
    (ROOT / FUNDING_HTML).write_text(page_shell(FUNDING_PAGE_TITLE, FUNDING_HTML, funding_html_body(funding), [x.get("last_verified") for x in funding]), encoding="utf-8")
    print("Generated conferences.jemdoc/conferences.html and funding.jemdoc/funding.html")

if __name__ == "__main__":
    main()
