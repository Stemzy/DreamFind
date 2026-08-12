#!/usr/bin/env python3
"""
Weekly auto-refresh for Paper Tiger (San Antonio) shows.

Fetches https://papertigersatx.com/calendar/, parses every event from the
calendar DOM, and rewrites the block between the PT_AUTO_START / PT_AUTO_END
markers in index.html. Run by .github/workflows/refresh.yml, or locally:

    pip install beautifulsoup4
    python3 scripts/refresh_paper_tiger.py

SAFETY: it refuses to write unless it parses a healthy number of events, so a
site layout change can never wipe the existing listings — it just logs and exits.
Only Paper Tiger is auto-scraped (plain calendar). Other venues are curated
"venue spot" cards that link out to their own live calendars.
"""
import re, sys, os, urllib.request

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependency: pip install beautifulsoup4"); sys.exit(1)

URL = "https://papertigersatx.com/calendar/"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(HERE, "index.html")
MIN_EVENTS = 20  # refuse to overwrite with fewer than this (guards against parse breakage)

MONTH_ABBR = {"january":"JAN","february":"FEB","march":"MAR","april":"APR","may":"MAY",
              "june":"JUN","july":"JUL","august":"AUG","september":"SEP","october":"OCT",
              "november":"NOV","december":"DEC"}
WIKI = {"soulfly":"Soulfly","unsane":"Unsane","built to spill":"Built_to_Spill",
        "emarosa":"Emarosa","menzingers":"The_Menzingers","suicide machines":"The_Suicide_Machines",
        "sweeping promises":"Sweeping_Promises"}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DreamscapeFinder refresh bot)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:28]
def sp(t): return t.replace("PM", " PM").replace("AM", " AM")
def esc(s): return s.replace("\\", "\\\\").replace("'", "\\'")


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    events, seen = [], set()
    for td in soup.find_all("td"):
        cell = td.get_text(" ", strip=True)
        dm = re.match(r"(\d{1,2})\b", cell)
        if not dm:
            continue
        day = int(dm.group(1))
        # month: nearest preceding text like "August 2026"
        mon = None
        prev = td.find_previous(string=re.compile(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}", re.I))
        if prev:
            mm = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)", prev, re.I)
            if mm:
                mon = MONTH_ABBR[mm.group(1).lower()]
        if not mon:
            continue
        for a in td.find_all("a", href=True):
            if not re.search(r"seetickets|eventim", a["href"]):
                continue
            name = a.get_text(strip=True)
            if not name or name.lower() == "buy tickets":
                continue
            key = (mon, day, name)
            if key in seen:
                continue
            seen.add(key)
            show = re.search(r"Show:\s*(\d+:\d+[AP]M)", cell)
            doors = re.search(r"Doors:\s*(\d+:\d+[AP]M)", cell)
            img = a.find("img") or a.find_previous("img")
            src = img["src"] if (img and img.has_attr("src") and "papertigerlogo" not in img["src"]) else None
            events.append(dict(mon=mon, day=day, name=name, link=a["href"], img=src,
                               show=show.group(1) if show else "",
                               doors=doors.group(1) if doors else ""))
    return events


def to_entry(e):
    name = e["name"]
    wk = next((v for k, v in WIKI.items() if k in name.lower()), None)
    date = f"{e['mon']} {e['day']}" + (f" · {sp(e['show'])}" if e["show"] else "")
    hrs = " · ".join(x for x in [("Doors " + sp(e["doors"])) if e["doors"] else "",
                                 ("Show " + sp(e["show"])) if e["show"] else ""] if x) or "See tickets"
    desc = "Live at Paper Tiger on the St. Mary's strip — SA's beloved DIY venue."
    iid = "pt-" + f"{e['mon'].lower()}{e['day']}-" + slug(name)
    f = [f"id: '{iid}'", "cat: 'show'", f"name: '{esc(name)}'", "city: 'San Antonio'",
         "state: 'TX'", f"date: '{date}'"]
    if wk: f.append(f"wiki: '{wk}'")
    if e["link"]: f.append(f"link: '{e['link']}'")
    if e["img"]: f.append(f"img: '{e['img']}'")
    f += ["ph: '♫'", f"desc: '{esc(desc)}'",
          'address: "2410 N St Mary\'s St, San Antonio, TX 78212"',
          f"hours: '{hrs}'", "price: '$$'", "era: 'Live @ Paper Tiger'",
          "tags: ['Paper Tiger', 'St. Marys Strip', 'Live Music']"]
    return "  {\n    " + ",\n    ".join(f) + "\n  },"


def main():
    events = parse(fetch(URL))
    print(f"Parsed {len(events)} Paper Tiger events.")
    if len(events) < MIN_EVENTS:
        print(f"Fewer than {MIN_EVENTS} events — layout may have changed. Not writing (data left intact).")
        sys.exit(0)
    block = "\n".join(to_entry(e) for e in events)
    src = open(INDEX, encoding="utf-8").read()
    new = re.sub(r"(/\* PT_AUTO_START.*?\*/\n).*?(\n\s*/\* PT_AUTO_END \*/)",
                 lambda m: m.group(1) + block + m.group(2), src, count=1, flags=re.S)
    if new == src:
        print("No change (markers missing or content identical)."); return
    open(INDEX, "w", encoding="utf-8").write(new)
    print(f"index.html updated with {len(events)} Paper Tiger shows.")


if __name__ == "__main__":
    main()
