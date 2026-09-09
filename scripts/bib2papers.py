#!/usr/bin/env python3
"""
bib2papers.py — build data/papers.yaml (the research deck catalogue) from BibTeX.

    bib/*.bib                  facts: title, year, venue, doi/url          (machine-owned)
    bib/deck-overrides.yaml    themes, loglines, featured, hidden entries  (human-owned)
    bib/venues.yaml            card art: abbreviation, publisher, brand hue (human-owned)
    bib/people.yaml            where each author is now, and their institution (human-owned)
                 |
                 v
    data/papers.yaml           generated; do not hand-edit
    data/venues.yaml           generated; the plate for each venue in use
    data/institutions.yaml     generated; the institutions in use

The sources live in bib/ rather than data/ on purpose: Hugo parses everything in
data/ as site data and aborts the build on a file it cannot unmarshal, which a
.bib is.

Usage
    python scripts/bib2papers.py             regenerate data/papers.yaml
    python scripts/bib2papers.py --check     exit 1 if papers.yaml is stale (CI guard)
    python scripts/bib2papers.py --quiet     only warnings and errors

Only dependency is PyYAML, and only for reading the overrides file.
"""

import argparse
import glob
import os
import re
import sys
import unicodedata
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "bib")            # inputs
DATA = os.path.join(ROOT, "data")          # Hugo's data dir — generated output only
OUT = os.path.join(DATA, "papers.yaml")
OVERRIDES = os.path.join(SRC, "deck-overrides.yaml")
VENUES_IN = os.path.join(SRC, "venues.yaml")
VENUES_OUT = os.path.join(DATA, "venues.yaml")
PEOPLE_IN = os.path.join(SRC, "people.yaml")
INST_OUT = os.path.join(DATA, "institutions.yaml")

VALID_THEMES = ("eco", "sec", "prof", "soc", "review")
VALID_KINDS = ("journal", "conf", "preprint")

# ── venue prettifying ────────────────────────────────────────────────────────
# First regex to match wins. Add your own; order matters.
VENUE_MAP = [
    (r"transactions on software engineering",            "IEEE TSE"),
    (r"transactions on software engineering and methodology", "ACM TOSEM"),
    (r"empirical software engineering",                  "Empirical Software Engineering"),
    (r"ieee software",                                   "IEEE Software"),
    (r"journal of systems and software",                 "Journal of Systems and Software"),
    (r"information and software technology",             "Information and Software Technology"),
    (r"science of computer programming",                 "Science of Computer Programming"),
    (r"applied soft computing",                          "Applied Soft Computing"),
    (r"ieice transactions",                              "IEICE Transactions"),
    (r"journal of information processing",               "Journal of Information Processing"),
    (r"automated software engineering|(\b|/)ase(\b|/)",  "ASE"),
    (r"mining software repositories|(\b|/)msr(\b|/)",    "MSR"),
    (r"foundations of software engineering|esec/fse|(\b|/)fse(\b|/)", "ESEC/FSE"),
    (r"international conference on software engineering", "ICSE"),
    (r"software maintenance and evolution|icsme",        "ICSME"),
    (r"software analysis, evolution and reengineering|saner", "SANER"),
    (r"program comprehension|icpc",                      "ICPC"),
    (r"predictive models|promise",                       "PROMISE"),
    (r"corr|arxiv",                                      "arXiv"),
]

# ── theme inference ──────────────────────────────────────────────────────────
# Applied to "title + venue + keywords" when an entry has no theme override.
THEME_RULES = [
    ("sec",    r"vulnerab|security|cve\b|log4|exploit|unsafe|malicious|attack|patch.*secur"),
    ("eco",    r"ecosystem|npm\b|pypi|maven|cargo|packagist|registry|depend|librar|package|"
               r"docker|semver|version|supply chain|third-party|reuse"),
    ("review", r"code review|reviewer|patch|pull request|build system|technical debt|"
               r"openstack|gerrit|continuous integration|merge"),
    ("prof",   r"readme|snippet|proficien|stack overflow|documentation|comment|"
               r"generative ai|llm|language model|copilot|api recommend|mashup|education|learn"),
    ("soc",    r"newcomer|contribut|communit|societ|protest|inclusion|diversit|emoji|"
               r"discussion|forum|onboarding|motivat|governance|sanction|developer experience"),
]


# ── BibTeX parsing (no third-party parser; handles the shapes exports emit) ──
def parse_bib(text):
    """Return a list of {'key','type','fields'} from BibTeX source."""
    entries = []
    i, n = 0, len(text)
    while True:
        at = text.find("@", i)
        if at < 0:
            break
        m = re.match(r"@(\w+)\s*[{(]", text[at:])
        if not m:
            i = at + 1
            continue
        etype = m.group(1).lower()
        body_start = at + m.end()
        # walk to the matching close brace, respecting nesting and quotes
        depth, j, in_quote = 1, body_start, False
        while j < n and depth:
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if c == '"' and depth == 1:
                in_quote = not in_quote
            elif not in_quote:
                if c in "{(":
                    depth += 1
                elif c in "})":
                    depth -= 1
            j += 1
        body = text[body_start:j - 1]
        i = j
        if etype in ("comment", "preamble", "string"):
            continue
        # citation key is everything up to the first comma
        head, _, rest = body.partition(",")
        entries.append({"key": head.strip(), "type": etype, "fields": parse_fields(rest)})
    return entries


def parse_fields(src):
    """Split 'a = {x}, b = "y", c = 3' into a dict, brace-aware."""
    fields, i, n = {}, 0, len(src)
    while i < n:
        m = re.compile(r"\s*([A-Za-z][\w-]*)\s*=\s*").match(src, i)
        if not m:
            break
        name = m.group(1).lower()
        i = m.end()
        if i < n and src[i] == "{":
            depth, start = 1, i + 1
            i += 1
            while i < n and depth:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == "{":
                    depth += 1
                elif src[i] == "}":
                    depth -= 1
                i += 1
            raw = src[start:i - 1]
        elif i < n and src[i] == '"':
            start = i + 1
            i += 1
            while i < n and src[i] != '"':
                i += 2 if src[i] == "\\" else 1
            raw = src[start:i]
            i += 1
        else:
            start = i
            while i < n and src[i] != ",":
                i += 1
            raw = src[start:i]
        fields[name] = clean(raw)
        while i < n and src[i] in ", \t\r\n":
            i += 1
    return fields


LATEX = {
    r"\&": "&", r"\_": "_", r"\%": "%", r"\#": "#", r"\$": "$",
    r"\{": "{", r"\}": "}", r"\textquotesingle": "'", r"\ldots": "…",
    "---": "—", "--": "–", "``": "\u201c", "''": "\u201d",
}
ACCENT = re.compile(r"\\([`'^\"~=.])\{?(\w)\}?")


def clean(raw):
    s = raw.strip()
    s = ACCENT.sub(lambda m: unicodedata.normalize(
        "NFC", m.group(2) + {"`": "\u0300", "'": "\u0301", "^": "\u0302",
                             '"': "\u0308", "~": "\u0303", "=": "\u0304",
                             ".": "\u0307"}[m.group(1)]), s)
    for a, b in LATEX.items():
        s = s.replace(a, b)
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def norm(s):
    """Match key: lowercase alphanumerics only, so punctuation drift is harmless."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# ── field derivation ─────────────────────────────────────────────────────────
def authors_of(e):
    """BibTeX joins authors with ' and '. Accepts 'First Last' and 'Last, First'."""
    raw = e["fields"].get("author", "")
    if not raw:
        return []
    out = []
    for part in re.split(r"\s+and\s+", raw):
        n = part.strip().strip(",")
        if not n or n.lower() in ("others", "et al", "et al."):
            continue
        if "," in n:                       # "Kula, Raula Gaikovina"
            last, _, first = n.partition(",")
            n = (first.strip() + " " + last.strip()).strip()
        out.append(re.sub(r"\s+", " ", n))
    return out


def venue_of(e):
    f = e["fields"]
    raw = f.get("journal") or f.get("booktitle") or f.get("publisher") or f.get("school") or ""
    if f.get("archiveprefix", "").lower() == "arxiv" or "corr" in raw.lower():
        raw = "arXiv"
    low = raw.lower()
    for pattern, pretty in VENUE_MAP:
        if re.search(pattern, low):
            if pretty == "arXiv" and e["type"] in ("incollection", "inbook"):
                return "arXiv — book chapter"
            return pretty
    return raw or "Unpublished"


def kind_of(e, venue):
    if venue.startswith("arXiv") or e["fields"].get("archiveprefix", "").lower() == "arxiv":
        return "preprint"
    if e["type"] in ("inproceedings", "conference", "proceedings"):
        return "conf"
    if e["type"] in ("article", "incollection", "inbook", "book", "phdthesis", "mastersthesis"):
        return "journal"
    return "preprint"


def url_of(e, title):
    f = e["fields"]
    if f.get("url"):
        return f["url"]
    if f.get("doi"):
        return "https://doi.org/" + f["doi"].replace("https://doi.org/", "")
    ep = f.get("eprint", "")
    if ep and f.get("archiveprefix", "").lower() == "arxiv":
        return "https://arxiv.org/abs/" + ep
    from urllib.parse import quote
    return "https://dblp.org/search?q=" + quote(title)


def themes_of(title, venue, keywords):
    hay = " ".join([title, venue, keywords]).lower()
    hits = [t for t, pat in THEME_RULES if re.search(pat, hay)]
    return hits[:3] or ["eco"]


# ── YAML emitting (we own the shape, so no dumper needed) ────────────────────
def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def emit_institutions(papers, people, log):
    """Resolve each author to an institution; emit only those actually in use."""
    insts = (people.get("institutions") or {})
    who = (people.get("people") or {})
    seen, missing = {}, []
    for p in papers:
        keys = []
        for name in p["authors"]:
            rec = who.get(name)
            if rec is None:
                if name not in missing:
                    missing.append(name)
                continue
            k = (rec or {}).get("institution") or ""
            if k and k not in keys:
                keys.append(k)
            if k and k not in seen:
                if k in insts:
                    seen[k] = insts[k]
                else:
                    log("  institution %r is not in bib/people.yaml" % k, warn=True)
        p["insts"] = keys
        p["self"] = [n for n in p["authors"] if (who.get(n) or {}).get("self")]
    if missing:
        log("  %d author(s) not in bib/people.yaml, so they add no institution: %s"
            % (len(missing), ", ".join(missing[:6]) + (" …" if len(missing) > 6 else "")),
            warn=True)
    blank = [n for n, r in who.items() if not (r or {}).get("institution")]
    if blank:
        log("  %d author(s) in bib/people.yaml still have no institution" % len(blank),
            warn=True)

    L = ["# GENERATED FILE — do not edit by hand.",
         "# Edit bib/people.yaml instead, then run scripts/bib2papers.py", ""]
    for k in sorted(seen):
        v = seen[k] or {}
        L += ["%s:" % q(k),
              "  name: " + q(v.get("name") or k),
              "  short: " + q(v.get("short") or k),
              "  color: " + q(v.get("color") or "#5C6580"),
              "  logo: " + q(v.get("logo") or "")]
    return "\n".join(L) + "\n"


def emit_venues(papers, reg, log):
    """One plate per venue actually in use, with its publisher resolved."""
    pubs = (reg.get("publishers") or {})
    known = (reg.get("venues") or {})
    fallback = pubs.get("none", {"name": "", "color": "#5C6580"})
    L = [
        "# GENERATED FILE — do not edit by hand.",
        "# Edit bib/venues.yaml instead, then run scripts/bib2papers.py",
        "",
    ]
    for venue in sorted({p["venue"] for p in papers}):
        v = known.get(venue)
        if not v:
            log("  venue not in bib/venues.yaml, using a plain plate: " + venue, warn=True)
            v = {"abbr": venue, "full": "", "publisher": "none"}
        pub = pubs.get(v.get("publisher", "none"), fallback)
        L += [
            "%s:" % q(venue),
            "  abbr: " + q(v.get("abbr") or venue),
            "  full: " + q(v.get("full") or ""),
            "  pub: " + q(pub.get("name") or ""),
            "  color: " + q(pub.get("color") or fallback["color"]),
            "  logo: " + q(pub.get("logo") or ""),
        ]
    return "\n".join(L) + "\n"


def emit(papers, featured, sources):
    L = [
        "# GENERATED FILE — do not edit by hand.",
        "# Regenerate with:  python scripts/bib2papers.py",
        "#",
        "#   facts     <- " + ", ".join("bib/" + x for x in sources),
        "#   curation  <- bib/deck-overrides.yaml  (themes, loglines, featured)",
        "#",
        "# Last generated %s · %d papers" % (date.today().isoformat(), len(papers)),
        "",
        "featured: " + q(featured),
        "",
        "papers:",
    ]
    for p in papers:
        L += [
            "  - title: " + q(p["title"]),
            "    year: %d" % p["year"],
            "    venue: " + q(p["venue"]),
            "    kind: " + p["kind"],
            "    themes: [" + ", ".join(p["themes"]) + "]",
            "    logline: " + q(p["logline"]),
            "    url: " + q(p["url"]),
        ]
        if p.get("authors"):
            L.append("    authors: [" + ", ".join(q(a) for a in p["authors"]) + "]")
        if p.get("insts"):
            L.append("    insts: [" + ", ".join(p["insts"]) + "]")
        if p.get("self"):
            L.append("    self: [" + ", ".join(q(a) for a in p["self"]) + "]")
    return "\n".join(L) + "\n"


# ── main ─────────────────────────────────────────────────────────────────────
def build(log):
    try:
        import yaml
    except ImportError:
        sys.exit("error: PyYAML is required.  pip install pyyaml")

    bibs = sorted(glob.glob(os.path.join(SRC, "*.bib")))
    stray = sorted(glob.glob(os.path.join(DATA, "*.bib")))
    if stray:
        log("  .bib files in data/ break the Hugo build — move these to bib/: "
            + ", ".join(os.path.basename(x) for x in stray), warn=True)
        bibs += stray
    if not bibs:
        sys.exit("error: no .bib file found in bib/.  Drop your export in as bib/publications.bib")

    entries = []
    for path in bibs:
        with open(path, encoding="utf-8") as fh:
            found = parse_bib(fh.read())
        log("read %-28s %3d entries" % (os.path.basename(path), len(found)))
        entries += found

    ov = {}
    if os.path.exists(OVERRIDES):
        with open(OVERRIDES, encoding="utf-8") as fh:
            ov = yaml.safe_load(fh) or {}
    people = {}
    if os.path.exists(PEOPLE_IN):
        with open(PEOPLE_IN, encoding="utf-8") as fh:
            people = yaml.safe_load(fh) or {}
    else:
        log("  bib/people.yaml missing — no authors will show an institution", warn=True)
    reg = {}
    if os.path.exists(VENUES_IN):
        with open(VENUES_IN, encoding="utf-8") as fh:
            reg = yaml.safe_load(fh) or {}
    else:
        log("  bib/venues.yaml missing — every card gets a plain plate", warn=True)
    by_key = {norm(k): v or {} for k, v in (ov.get("entries") or {}).items()}
    used = set()

    papers, seen = [], {}
    for e in entries:
        f = e["fields"]
        title = f.get("title", "").strip()
        if not title:
            continue
        ym = re.search(r"\d{4}", f.get("year", ""))
        if not ym:
            log("  skip (no year): " + title[:60], warn=True)
            continue
        year = int(ym.group())

        venue = venue_of(e)
        kind = kind_of(e, venue)
        rec = {
            "title": title, "year": year, "venue": venue, "kind": kind,
            "authors": authors_of(e),
            "themes": themes_of(title, venue, f.get("keywords", "")),
            "logline": "", "url": url_of(e, title),
        }

        # curation wins over everything inferred
        o = by_key.get(norm(e["key"])) or by_key.get(norm(title)) or {}
        if o:
            used.add(norm(e["key"]) if norm(e["key"]) in by_key else norm(title))
            if o.get("hide"):
                continue
            for field in ("venue", "logline", "url", "kind"):
                if o.get(field):
                    rec[field] = o[field]
            if o.get("authors"):
                rec["authors"] = list(o["authors"])
            if o.get("themes"):
                rec["themes"] = [t for t in o["themes"] if t in VALID_THEMES] or rec["themes"]
            if o.get("year"):
                rec["year"] = int(o["year"])

        if rec["kind"] not in VALID_KINDS:
            log("  bad kind %r on %s — using 'preprint'" % (rec["kind"], title[:40]), warn=True)
            rec["kind"] = "preprint"

        # a published version supersedes its own preprint
        nt = norm(title)
        if nt in seen:
            prev = seen[nt]
            keep, drop = (rec, prev) if (prev["kind"] == "preprint" and rec["kind"] != "preprint") else (prev, rec)
            if not keep["logline"] and drop["logline"]:
                keep["logline"] = drop["logline"]
            if not keep["authors"] and drop["authors"]:
                keep["authors"] = drop["authors"]
            papers[papers.index(prev)] = keep
            seen[nt] = keep
            log("  merged preprint + published: " + title[:56])
            continue
        seen[nt] = rec
        papers.append(rec)

    for p in papers:
        if not p["logline"]:
            p["logline"] = "%s, %s." % (p["venue"], p["year"])
            log("  no logline yet: " + p["title"][:60], warn=True)

    for k in set(by_key) - used:
        log("  override matches nothing: " + k[:60], warn=True)

    papers.sort(key=lambda p: (-p["year"], p["title"].lower()))

    featured = ov.get("featured") or ""
    match = [p for p in papers if norm(p["title"]) == norm(featured)]
    if not match:
        for e in entries:
            if norm(e["key"]) == norm(featured):
                match = [p for p in papers if norm(p["title"]) == norm(e["fields"].get("title", ""))]
                break
    if match:
        featured = match[0]["title"]
    else:
        if featured:
            log("  featured %r not found — using the newest paper" % featured, warn=True)
        featured = papers[0]["title"] if papers else ""

    inst_text = emit_institutions(papers, people, log)   # sets p["insts"] as a side effect
    for p in papers:
        if not p["authors"]:
            log("  no authors in the .bib for: " + p["title"][:56], warn=True)
    return (emit(papers, featured, [os.path.basename(b) for b in bibs]),
            emit_venues(papers, reg, log), inst_text, papers)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if papers.yaml is stale")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    warnings = []

    def log(msg, warn=False):
        if warn:
            warnings.append(msg)
            print("warn: " + msg, file=sys.stderr)
        elif not a.quiet:
            print(msg)

    text, venues_text, inst_text, papers = build(log)

    def strip_stamp(s):
        return "\n".join(l for l in s.splitlines() if not l.startswith("# Last generated"))

    def read(path):
        return open(path, encoding="utf-8").read() if os.path.exists(path) else ""

    changed = (strip_stamp(read(OUT)) != strip_stamp(text)
               or strip_stamp(read(VENUES_OUT)) != strip_stamp(venues_text)
               or strip_stamp(read(INST_OUT)) != strip_stamp(inst_text))

    if a.check:
        print("catalogue is %s" % ("STALE — run scripts/bib2papers.py" if changed else "up to date"))
        return 1 if changed else 0

    if changed:
        with open(OUT, "w", encoding="utf-8") as fh:
            fh.write(text)
        with open(VENUES_OUT, "w", encoding="utf-8") as fh:
            fh.write(venues_text)
        with open(INST_OUT, "w", encoding="utf-8") as fh:
            fh.write(inst_text)
        print("wrote data/papers.yaml + venues.yaml + institutions.yaml — %d papers, %d warning(s)"
              % (len(papers), len(warnings)))
    else:
        print("catalogue already up to date — %d papers" % len(papers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
