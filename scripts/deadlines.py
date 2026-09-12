#!/usr/bin/env python3
"""
deadlines.py — keep a conference deadline board without maintaining it by hand.

Point it at a conference on conf.researchr.org and it reads that conference's
own dates page, so the board stays honest to the source instead of drifting
into a hand-typed list.

    bib/conferences.yaml    what you track, and everything fetched  (yours)
                 |
                 v
    data/deadlines.yaml     generated; what the site reads

Usage
    python scripts/deadlines.py add msr-2027              add a conference
    python scripts/deadlines.py add https://conf.researchr.org/home/icse-2027
    python scripts/deadlines.py refresh                   re-read every one
    python scripts/deadlines.py refresh msr-2027          re-read just one
    python scripts/deadlines.py list                      what is tracked
    python scripts/deadlines.py remove msr-2027
    python scripts/deadlines.py build                     write data/deadlines.yaml
    python scripts/deadlines.py build --check             exit 1 if stale (CI)

`add` and `refresh` need network; `build` does not. Fetches are spaced out and
send a descriptive User-Agent.
"""

import argparse
import datetime as dt
import html
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "bib", "conferences.yaml")
OUT = os.path.join(ROOT, "data", "deadlines.yaml")
VENUES = os.path.join(ROOT, "bib", "venues.yaml")

UA = "raux.github.io deadline board (+https://raux.github.io/deadlines/)"
DATES_URL = "https://conf.researchr.org/dates/%s"
HOME_URL = "https://conf.researchr.org/home/%s"
PAUSE = 1.5  # seconds between fetches

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

# What sort of date a row is. First match wins, so order matters.
KINDS = [
    ("submission",   r"abstract"),
    ("submission",   r"submission|submit|paper deadline|deadline for|due|proposals"),
    ("notification", r"notification|notify|decision|acceptance|reject|response"),
    ("camera",       r"camera|final version|final copy|proceedings|front matter"),
    ("event",        r"conference|workshop day|sessions|dates|symposium"),
]


def slugify(s):
    return re.sub(r"[^a-z0-9-]", "", s.lower().replace(" ", "-"))


def strip_tags(s):
    """Tags become a space, not nothing — researchr hangs "new" badges off labels,
    and stripping them bare gives "Abstract deadlinenew"."""
    t = html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"\s+(new|NEW|updated|UPDATED)$", "", t).strip()


def parse_dates_page(text):
    """Rows are <tr href=TRACK_URL><td>when</td><td>track</td><td>what</td></tr>."""
    rows = []
    for tr in re.findall(r"<tr\b[^>]*>.*?</tr>", text, re.S):
        if "<th" in tr:
            continue
        href = re.search(r'href="([^"]+)"', tr)
        tds = re.findall(r"<td\b[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 3:
            continue
        tzm = re.search(r'title="Timezone:\s*([^"]+)"', tds[0])
        when, track, what = (strip_tags(tds[0]), strip_tags(tds[1]), strip_tags(tds[2]))
        if not when or not what:
            continue
        rows.append({
            "raw": when,
            "track": track or "General",
            "label": what,
            "tz": html.unescape(tzm.group(1)).strip() if tzm else "",
            "url": href.group(1) if href else "",
        })
    return rows


def operative_date(raw):
    """The date a row actually lands on. Ranges resolve to their end."""
    hits = re.findall(r"\b(\d{1,2})\s+([A-Z][a-z]{2})\s+(\d{4})", raw)
    if not hits:
        return None
    d, mon, y = hits[-1]
    if mon not in MONTHS:
        return None
    try:
        return dt.date(int(y), MONTHS[mon], int(d)).isoformat()
    except ValueError:
        return None


def classify(label):
    low = label.lower()
    for kind, pat in KINDS:
        if re.search(pat, low):
            return kind
    return "other"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def conference_title(slug, page):
    m = re.search(r"<title>(.*?)</title>", page, re.S)
    if m:
        t = strip_tags(m.group(1))
        t = re.sub(r"^\s*(Important\s+)?Dates\s*[-|]\s*", "", t)
        t = re.sub(r"\s*[-|]\s*(Important Dates|Dates)\b.*$", "", t)
        t = re.sub(r"\s*[-|].*$", "", t).strip()   # drop a trailing subtitle
        if t:
            return t
    return slug.upper()


# Conference slugs whose plate lives under a different name in bib/venues.yaml.
VENUE_ALIASES = {
    "ESEIW": "ESEM",       # the week; the conference inside it is ESEM
    "FSE": "ESEC/FSE",
    "ESEC": "ESEC/FSE",
    "APSECW": "APSECW",
}


def guess_venue(slug, venues):
    """Match msr-2027 -> the MSR plate already defined in bib/venues.yaml."""
    stem = re.sub(r"[-_]?\d{4}$", "", slug).upper()
    stem = VENUE_ALIASES.get(stem, stem)
    for key in venues:
        if key.upper() == stem:
            return key
    for key, v in venues.items():
        if str(v.get("abbr", "")).upper() == stem:
            return key
    return ""


# ── yaml helpers ────────────────────────────────────────────────────────────
def load(path, default=None):
    import yaml
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or (default if default is not None else {})


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_source(data):
    L = ["# Conferences whose deadlines the board tracks.",
         "#",
         "# Add one with:  python scripts/deadlines.py add <slug-or-url>",
         "# Re-read all:   python scripts/deadlines.py refresh",
         "#",
         "# Everything under `deadlines:` is fetched from the conference's own",
         "# dates page — edit `venue:` or `name:` freely, but expect the rest to be",
         "# replaced on the next refresh.",
         "",
         "conferences:"]
    for slug in sorted(data, key=lambda s: (data[s].get("name") or s).lower()):
        c = data[slug]
        L += ["  %s:" % slug,
              "    name: " + q(c.get("name") or slug),
              "    url: " + q(c.get("url") or ""),
              "    venue: " + q(c.get("venue") or ""),
              "    fetched: " + q(c.get("fetched") or ""),
              "    deadlines:"]
        for d in c.get("deadlines") or []:
            L += ["      - date: " + q(d["date"]),
                  "        track: " + q(d["track"]),
                  "        label: " + q(d["label"]),
                  "        kind: " + d["kind"],
                  "        raw: " + q(d["raw"]),
                  "        tz: " + q(d.get("tz") or ""),
                  "        url: " + q(d.get("url") or "")]
        L.append("")
    with open(SRC, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L).rstrip("\n") + "\n")


def pull(slug, venues, log):
    page = fetch(DATES_URL % slug)
    rows = parse_dates_page(page)
    out, dropped = [], 0
    for r in rows:
        iso = operative_date(r["raw"])
        if not iso:
            dropped += 1
            continue
        r["date"] = iso
        r["kind"] = classify(r["label"])
        out.append(r)
    out.sort(key=lambda r: (r["date"], r["track"], r["label"]))
    # a conference page can list the same row under several tracks
    seen, uniq = set(), []
    for r in out:
        k = (r["date"], r["track"], r["label"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    log("  %-16s %3d dates%s" % (slug, len(uniq),
        "  (%d rows had no parseable date)" % dropped if dropped else ""))
    return {
        "name": conference_title(slug, page),
        "url": HOME_URL % slug,
        "venue": guess_venue(slug, venues),
        "fetched": dt.date.today().isoformat(),
        "deadlines": uniq,
    }


def emit(data, today):
    rows = []
    for slug, c in data.items():
        for d in c.get("deadlines") or []:
            rows.append((d["date"], slug, c, d))
    rows.sort(key=lambda r: (r[0], r[1]))
    L = ["# GENERATED FILE — do not edit by hand.",
         "# Regenerate with:  python scripts/deadlines.py build",
         "#",
         "# Last generated %s · %d dates across %d conferences"
         % (today.isoformat(), len(rows), len(data)),
         "",
         "conferences:"]
    for slug in sorted(data):
        c = data[slug]
        L += ["  %s:" % slug,
              "    name: " + q(c.get("name") or slug),
              "    url: " + q(c.get("url") or ""),
              "    venue: " + q(c.get("venue") or "")]
    L += ["", "dates:"]
    for iso, slug, c, d in rows:
        L += ["  - date: " + q(iso),
              "    conf: " + slug,
              "    track: " + q(d["track"]),
              "    label: " + q(d["label"]),
              "    kind: " + d["kind"],
              "    tz: " + q(d.get("tz") or ""),
              "    url: " + q(d.get("url") or c.get("url") or "")]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["add", "refresh", "list", "remove", "build"])
    ap.add_argument("target", nargs="*", help="conference slug or researchr URL")
    ap.add_argument("--check", action="store_true", help="build only: exit 1 if stale")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    try:
        import yaml  # noqa: F401
    except ImportError:
        sys.exit("error: PyYAML is required.  pip install pyyaml")

    def log(m):
        if not a.quiet:
            print(m)

    data = (load(SRC, {"conferences": {}}).get("conferences") or {})
    venues = (load(VENUES, {}).get("venues") or {})
    today = dt.date.today()

    if a.command == "list":
        if not data:
            print("nothing tracked yet — try: python scripts/deadlines.py add msr-2027")
            return 0
        for slug in sorted(data):
            c = data[slug]
            future = [d for d in c.get("deadlines") or [] if d["date"] >= today.isoformat()]
            print("%-18s %-34s %3d dates, %2d still ahead   fetched %s"
                  % (slug, (c.get("name") or "")[:34], len(c.get("deadlines") or []),
                     len(future), c.get("fetched") or "never"))
        return 0

    if a.command == "remove":
        if not a.target:
            sys.exit("error: which conference?")
        for t in a.target:
            slug = slugify(t.rstrip("/").split("/")[-1])
            if data.pop(slug, None) is None:
                print("not tracked: " + slug)
            else:
                print("removed " + slug)
        write_source(data)
        return 0

    if a.command in ("add", "refresh"):
        if a.command == "add":
            if not a.target:
                sys.exit("error: give a conference slug or researchr URL")
            slugs = [slugify(t.rstrip("/").split("/")[-1]) for t in a.target]
        else:
            slugs = [slugify(t.rstrip("/").split("/")[-1]) for t in a.target] or sorted(data)
            if not slugs:
                sys.exit("error: nothing tracked yet")
        log("reading %d conference page%s" % (len(slugs), "" if len(slugs) == 1 else "s"))
        for i, slug in enumerate(slugs):
            if i:
                time.sleep(PAUSE)
            try:
                data[slug] = pull(slug, venues, log)
            except Exception as e:
                print("  %-16s FAILED: %s" % (slug, str(e)[:70]), file=sys.stderr)
        write_source(data)
        log("\nwrote bib/conferences.yaml — now run: python scripts/deadlines.py build")
        return 0

    # build
    if not data:
        sys.exit("error: nothing tracked — add a conference first")
    text = emit(data, today)

    def strip_stamp(s):
        return "\n".join(l for l in s.splitlines() if not l.startswith("# Last generated"))

    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    changed = strip_stamp(old) != strip_stamp(text)
    if a.check:
        print("deadlines.yaml is %s" % ("STALE — run scripts/deadlines.py build"
                                        if changed else "up to date"))
        return 1 if changed else 0
    if changed:
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write(text)
    total = sum(len(c.get("deadlines") or []) for c in data.values())
    ahead = sum(1 for c in data.values() for d in (c.get("deadlines") or [])
                if d["date"] >= today.isoformat())
    print("%s data/deadlines.yaml — %d dates across %d conferences, %d still ahead"
          % ("wrote" if changed else "unchanged", total, len(data), ahead))
    stale = [s for s, c in data.items()
             if not any(d["date"] >= today.isoformat() for d in (c.get("deadlines") or []))]
    if stale:
        print("note: every date has passed for %s — refresh or remove" % ", ".join(sorted(stale)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
