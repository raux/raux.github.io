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
    python scripts/deadlines.py new                       add anything by hand (journals, CFPs)
    python scripts/deadlines.py add msr-2027              add a conference from researchr
    python scripts/deadlines.py add https://conf.researchr.org/home/icse-2027
    python scripts/deadlines.py refresh                   re-read every one
    python scripts/deadlines.py refresh msr-2027          re-read just one
    python scripts/deadlines.py list                      what is tracked
    python scripts/deadlines.py remove msr-2027           stop tracking one
    python scripts/deadlines.py tracks icse-2027          what tracks it carries
    python scripts/deadlines.py hide icse-2027 "Shadow PC"        drop a track
    python scripts/deadlines.py hide icse-2027 --matching Workshop
    python scripts/deadlines.py show icse-2027 "Shadow PC"        put it back
    python scripts/deadlines.py keep icse-2027 "Research Track"   hide everything else
    python scripts/deadlines.py build                     write data/deadlines.yaml
    python scripts/deadlines.py build --check             exit 1 if stale (CI)

Two kinds of entry live side by side. A `researchr` entry is fetched and is
replaced wholesale on the next `refresh`. A `manual` entry — a journal special
issue, a CFP with no researchr page, anything you typed — is never fetched and
never overwritten; `refresh` skips it by design.

Hiding is a filter, not a deletion: the rows stay in bib/conferences.yaml and
survive `refresh`, so `show` brings them back without re-fetching. That matters
because researchr aggregates co-located events — ICSE carries its workshops, so
most of its 238 rows are not ICSE deadlines at all.

`add` and `refresh` need network; everything else does not. Fetches are spaced
out and send a descriptive User-Agent.
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
# Order matters: the first pattern to match wins, so the more specific
# kinds go first.  "Camera-ready Submission Deadline" is a camera-ready
# date, not a submission, and reads as one only if camera is tested first.
KINDS = [
    ("camera",       r"camera|final version|final copy|proceedings|front matter"),
    # Programme-committee dates.  Conferences publish these on the same page
    # as author deadlines, and "Final Reviews Due" reads as a submission if
    # you only look for "due".  They are nothing an author has to act on.
    ("other",        r"review(s)? due|assigned for review|bidding|pc meeting|"
                     r"review(ing)? period"),
    ("submission",   r"abstract"),
    ("submission",   r"submission|submit|paper deadline|deadline for|due|proposals"),
    ("notification", r"notification|notify|decision|acceptance|reject|response"),
    ("event",        r"conference|workshop day|sessions|dates|symposium"),
]


def slugify(s):
    return re.sub(r"[^a-z0-9-]", "", s.lower().replace(" ", "-"))


def trim_slug(s, limit=48):
    """Long names make unusable ids, but cutting mid-word gives
    ...-software-engineer for ...-software-engineering.  Cut at a hyphen."""
    if len(s) <= limit:
        return s
    cut = s[:limit + 1].rsplit("-", 1)[0]
    return (cut or s[:limit]).rstrip("-")


def strip_tags(s):
    """Tags become a space, not nothing — researchr hangs "new" badges off labels,
    and stripping them bare gives "Abstract deadlinenew"."""
    t = html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    # Invisible formatting characters survive a copy-paste into a CFP and then
    # sit at the head of a label, where they are impossible to see and break
    # sorting and matching.  Word joiner, zero-widths, BOM, soft hyphen.
    t = re.sub(r"[\u200b-\u200d\u2060\ufeff\u00ad\u180e]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+(new|NEW|updated|UPDATED)$", "", t).strip()
    return t.rstrip(":").strip()


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


def write_source(data, hidden=None):
    L = ["# Conferences whose deadlines the board tracks.",
         "#",
         "# Add one with:  python scripts/deadlines.py add <slug-or-url>",
         "# Re-read all:   python scripts/deadlines.py refresh",
         "#",
         "# Everything under `deadlines:` is fetched from the conference's own",
         "# dates page — edit `venue:` or `name:` freely, but expect the rest to be",
         "# replaced on the next refresh.",
         "",
         ""]
    hidden = {k: sorted(v) for k, v in (hidden or {}).items() if v}
    if hidden:
        L += ["# Tracks kept off the board. The rows below are untouched, so `show`",
              "# restores them without re-fetching.",
              "hidden:"]
        for slug in sorted(hidden):
            L.append("  %s:" % slug)
            for t in hidden[slug]:
                L.append("    - " + q(t))
        L.append("")
    L.append("conferences:")
    for slug in sorted(data, key=lambda s: (data[s].get("name") or s).lower()):
        c = data[slug]
        L += ["  %s:" % slug,
              "    source: " + (c.get("source") or "researchr"),
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
        "source": "researchr",
        "name": conference_title(slug, page),
        "url": HOME_URL % slug,
        "venue": guess_venue(slug, venues),
        "fetched": dt.date.today().isoformat(),
        "deadlines": uniq,
    }


def emit(data, today, hidden=None):
    hidden = hidden or {}
    rows = []
    for slug, c in data.items():
        drop = set(hidden.get(slug) or [])
        for d in c.get("deadlines") or []:
            if d["track"] in drop:
                continue
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
              "    source: " + (c.get("source") or "researchr"),
              "    name: " + q(c.get("name") or slug),
              "    url: " + q(c.get("url") or ""),
              "    venue: " + q(c.get("venue") or "")]
    L += ["", "dates:"]
    for iso, slug, c, d in rows:
        L += ["  - date: " + q(iso),
              "    conf: " + slug,
              "    track: " + q(d["track"]),
              "    label: " + q(d["label"]),
              # classified here, not at fetch time, so improving the rules
              # re-sorts the whole board without re-fetching anything
              "    kind: " + classify(d["label"]),
              "    tz: " + q(d.get("tz") or ""),
              "    url: " + q(d.get("url") or c.get("url") or "")]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command",
                    choices=["add", "refresh", "list", "remove", "build",
                             "tracks", "hide", "show", "keep", "new"])
    ap.add_argument("target", nargs="*",
                    help="conference slug or researchr URL; for hide/show, the track names")
    ap.add_argument("--matching", metavar="TEXT",
                    help="hide/show/keep: tracks whose name contains this (case-insensitive); "
                         "comma-separate for several")
    ap.add_argument("--check", action="store_true", help="build only: exit 1 if stale")
    ap.add_argument("--quiet", action="store_true")
    # `new` may be driven by flags instead of prompts, for scripting
    ap.add_argument("--name", help="new: what to call it, e.g. 'TOSEM Special Issue on X'")
    ap.add_argument("--slug", help="new: short id; derived from --name when omitted")
    ap.add_argument("--venue", help="new: a key from bib/venues.yaml, e.g. 'ACM TOSEM'")
    ap.add_argument("--url", help="new: the call-for-papers page")
    ap.add_argument("--date", action="append", metavar="YYYY-MM-DD",
                    help="new: a deadline; repeatable, paired with --label")
    ap.add_argument("--label", action="append",
                    help="new: what that date is, e.g. 'Paper submission'")
    ap.add_argument("--track", help="new: track name for every date (default: Submission)")
    ap.add_argument("--tz", help="new: timezone as published, e.g. 'AoE (UTC-12h)'")
    a = ap.parse_args()

    try:
        import yaml  # noqa: F401
    except ImportError:
        sys.exit("error: PyYAML is required.  pip install pyyaml")

    def log(m):
        if not a.quiet:
            print(m)

    raw = load(SRC, {"conferences": {}})
    data = raw.get("conferences") or {}
    hidden = {k: list(v or []) for k, v in (raw.get("hidden") or {}).items()}
    venues = (load(VENUES, {}).get("venues") or {})
    today = dt.date.today()

    if a.command == "list":
        if not data:
            print("nothing tracked yet — try: python scripts/deadlines.py add msr-2027")
            return 0
        w = max(len(s) for s in data)
        n = min(34, max(len(c.get("name") or "") for c in data.values()))
        for slug in sorted(data):
            c = data[slug]
            future = [d for d in c.get("deadlines") or [] if d["date"] >= today.isoformat()]
            off = set(hidden.get(slug) or [])
            note = "  (%d track%s hidden)" % (len(off), "" if len(off) == 1 else "s") if off else ""
            src = "by hand" if c.get("source") == "manual" else (c.get("fetched") or "never")
            print("%-*s  %-*s %3d dates, %3d still ahead   %s%s"
                  % (w, slug, n, (c.get("name") or "")[:n], len(c.get("deadlines") or []),
                     len(future), src, note))
        return 0

    def track_counts(slug):
        c = data.get(slug)
        if c is None:
            sys.exit("error: not tracked: %s  (try: deadlines.py list)" % slug)
        counts = {}
        for d in c.get("deadlines") or []:
            counts[d["track"]] = counts.get(d["track"], 0) + 1
        return counts

    if a.command == "tracks":
        if not a.target:
            sys.exit("error: which conference?  e.g. deadlines.py tracks icse-2027")
        for t in a.target:
            slug = slugify(t.rstrip("/").split("/")[-1])
            counts = track_counts(slug)
            off = set(hidden.get(slug) or [])
            print("%s — %d tracks, %d hidden" % (slug, len(counts), len(off & set(counts))))
            for name in sorted(counts, key=lambda n: (-counts[n], n.lower())):
                print("  %-5s %3d  %s" % ("hidden" if name in off else "", counts[name], name))
        return 0

    if a.command == "new":
        interactive = not (a.name and a.date)

        def ask(prompt, default=""):
            try:
                v = input(prompt + (" [%s]" % default if default else "") + ": ").strip()
            except EOFError:
                v = ""
            return v or default

        if interactive:
            print("Adding an entry by hand — for a journal special issue, a CFP with no")
            print("researchr page, or anything else. Leave a date blank to finish.")
            print("This entry will never be fetched or overwritten by `refresh`.\n")
            if a.venue is None and venues:
                print("venue keys available: " + ", ".join(sorted(venues)[:12]) + " …\n")

        name = a.name or ask("Name (e.g. 'TOSEM Special Issue on Agentic SE')")
        if not name:
            sys.exit("error: a name is required")
        slug = trim_slug(slugify(a.slug or name)) or "entry"
        if slug in data and (data[slug].get("source") != "manual"):
            sys.exit("error: %s already exists and is fetched from researchr" % slug)
        venue = a.venue if a.venue is not None else (ask("Venue plate key (optional)") if interactive else "")
        if venue and venue not in venues:
            near = [k for k in venues if venue.lower() in k.lower()]
            print("  note: %r is not in bib/venues.yaml%s — the row will use a plain plate"
                  % (venue, ("; did you mean %s?" % ", ".join(near[:3])) if near else ""))
        url = a.url if a.url is not None else (ask("Call-for-papers URL (optional)") if interactive else "")
        track = a.track or (ask("Track", "Submission") if interactive else "Submission")
        tz = a.tz if a.tz is not None else (ask("Timezone as published (optional)") if interactive else "")

        rows = []
        if a.date:
            labels = a.label or []
            for i, dstr in enumerate(a.date):
                rows.append((dstr, labels[i] if i < len(labels) else "Submission"))
        else:
            while True:
                dstr = ask("\nDeadline date (YYYY-MM-DD, blank to finish)")
                if not dstr:
                    break
                label = ask("  What is it", "Paper submission")
                rows.append((dstr, label))

        if not rows:
            sys.exit("error: no dates given")

        deadlines = []
        for dstr, label in rows:
            try:
                iso = dt.date.fromisoformat(dstr.strip()).isoformat()
            except ValueError:
                sys.exit("error: %r is not a date in YYYY-MM-DD form" % dstr)
            deadlines.append({
                "date": iso, "track": track, "label": label,
                "kind": classify(label), "raw": iso, "tz": tz, "url": url,
            })
        deadlines.sort(key=lambda d: (d["date"], d["label"]))

        data[slug] = {
            "source": "manual", "name": name, "url": url, "venue": venue,
            "fetched": "", "deadlines": deadlines,
        }
        write_source(data, hidden)
        print("\nadded %s — %d date%s, kept out of every refresh"
              % (slug, len(deadlines), "" if len(deadlines) == 1 else "s"))
        for d in deadlines:
            print("  %s  %-28s %s" % (d["date"], d["label"][:28], d["kind"]))
        print("\nnow run: python scripts/deadlines.py build")
        return 0

    if a.command == "keep":
        if len(a.target) < 1:
            sys.exit('error: deadlines.py keep <conference> "Research Track" [more...]')
        slug = slugify(a.target[0].rstrip("/").split("/")[-1])
        counts = track_counts(slug)
        wanted = set()
        for n in a.target[1:]:
            exact = n if n in counts else next(
                (k for k in counts if k.lower() == n.lower()), None)
            if exact is None:
                print("  no such track in %s: %s" % (slug, n))
            else:
                wanted.add(exact)
        for frag in (a.matching or "").split(","):
            frag = frag.strip()
            if frag:
                wanted |= {k for k in counts if frag.lower() in k.lower()}
        if not wanted:
            sys.exit("error: nothing matched, so everything would be hidden — refusing")
        hidden[slug] = sorted(set(counts) - wanted)
        write_source(data, hidden)
        for k in sorted(wanted, key=lambda n: (-counts[n], n.lower())):
            print("  kept   %3d  %s" % (counts[k], k))
        kept_n = sum(counts[k] for k in wanted)
        print("%s: %d of %d dates now on the board (%d of %d tracks hidden)"
              % (slug, kept_n, sum(counts.values()),
                 len(hidden[slug]), len(counts)))
        print("now run: python scripts/deadlines.py build")
        return 0

    if a.command in ("hide", "show"):
        if not a.target:
            sys.exit("error: which conference?  e.g. deadlines.py hide icse-2027 \"Shadow PC\"")
        slug = slugify(a.target[0].rstrip("/").split("/")[-1])
        counts = track_counts(slug)
        names = list(a.target[1:])
        for frag in (a.matching or "").split(","):
            frag = frag.strip()
            if frag:
                names += [n for n in counts if frag.lower() in n.lower()]
        if not names:
            sys.exit("error: name a track, or use --matching TEXT")
        cur = set(hidden.get(slug) or [])
        touched = 0
        for n in names:
            exact = n if n in counts else next(
                (k for k in counts if k.lower() == n.lower()), None)
            if exact is None:
                print("  no such track in %s: %s" % (slug, n))
                continue
            if a.command == "hide" and exact not in cur:
                cur.add(exact); touched += 1
                print("  hidden   %3d  %s" % (counts[exact], exact))
            elif a.command == "show" and exact in cur:
                cur.discard(exact); touched += 1
                print("  restored %3d  %s" % (counts[exact], exact))
        hidden[slug] = sorted(cur)
        write_source(data, hidden)
        kept = sum(v for k, v in counts.items() if k not in cur)
        print("%s: %d of %d dates now on the board (%d track%s hidden)"
              % (slug, kept, sum(counts.values()), len(cur), "" if len(cur) == 1 else "s"))
        if touched:
            print("now run: python scripts/deadlines.py build")
        return 0

    if a.command == "remove":
        if not a.target:
            sys.exit("error: which conference?")
        for t in a.target:
            slug = slugify(t.rstrip("/").split("/")[-1])
            if data.pop(slug, None) is None:
                print("not tracked: " + slug)
            else:
                hidden.pop(slug, None)
                print("removed " + slug)
        write_source(data, hidden)
        return 0

    if a.command in ("add", "refresh"):
        if a.command == "add":
            if not a.target:
                sys.exit("error: give a conference slug or researchr URL")
            slugs = [slugify(t.rstrip("/").split("/")[-1]) for t in a.target]
        else:
            asked = [slugify(t.rstrip("/").split("/")[-1]) for t in a.target]
            slugs = asked or sorted(data)
            manual = [s for s in slugs if (data.get(s) or {}).get("source") == "manual"]
            if manual:
                for m in manual:
                    log("  %-16s skipped — a hand-entered entry is never re-fetched" % m)
                slugs = [s for s in slugs if s not in manual]
            if not slugs:
                sys.exit("error: nothing to fetch" if asked else "error: nothing tracked yet")
        log("reading %d conference page%s" % (len(slugs), "" if len(slugs) == 1 else "s"))
        for i, slug in enumerate(slugs):
            if i:
                time.sleep(PAUSE)
            try:
                data[slug] = pull(slug, venues, log)
            except Exception as e:
                print("  %-16s FAILED: %s" % (slug, str(e)[:70]), file=sys.stderr)
        write_source(data, hidden)
        log("\nwrote bib/conferences.yaml — now run: python scripts/deadlines.py build")
        return 0

    # build
    if not data:
        sys.exit("error: nothing tracked — add a conference first")
    text = emit(data, today, hidden)

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
    iso = today.isoformat()

    def kept(slug, c):
        drop = set(hidden.get(slug) or [])
        return [d for d in (c.get("deadlines") or []) if d["track"] not in drop]

    on_board = {s: kept(s, c) for s, c in data.items()}
    total = sum(len(v) for v in on_board.values())
    ahead = sum(1 for v in on_board.values() for d in v if d["date"] >= iso)
    suppressed = sum(len(c.get("deadlines") or []) for c in data.values()) - total
    print("%s data/deadlines.yaml — %d dates across %d conferences, %d still ahead%s"
          % ("wrote" if changed else "unchanged", total, len(data), ahead,
             "  (%d hidden)" % suppressed if suppressed else ""))
    stale = [s for s, v in on_board.items() if not any(d["date"] >= iso for d in v)]
    if stale:
        print("note: every date has passed for %s — refresh or remove" % ", ".join(sorted(stale)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
