#!/usr/bin/env python3
"""
feature.py — choose which papers the deck puts forward.

Writes two keys into bib/deck-overrides.yaml and touches nothing else:

    featured:   the one paper on the billboard
    spotlight:  a short list rendered as a "Spotlight" row

Then run scripts/bib2papers.py to rebuild the catalogue.

Usage
    python scripts/feature.py                  a fresh random pick
    python scripts/feature.py --count 10       a longer spotlight row
    python scripts/feature.py --seed 2026-09-09   reproducible (CI uses the date)
    python scripts/feature.py --pin "Open Source at a Crossroads"   choose the hero yourself
    python scripts/feature.py --dry-run        print the pick, write nothing

The choice is weighted, not uniform: recent work and papers where Kula is first
author come up more often, and anything used as the hero in the last few runs is
skipped so the billboard does not repeat. That history lives in
bib/feature-history.yaml.
"""

import argparse
import os
import random
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "bib")
OVERRIDES = os.path.join(SRC, "deck-overrides.yaml")
PEOPLE = os.path.join(SRC, "people.yaml")
HISTORY = os.path.join(SRC, "feature-history.yaml")
PAPERS = os.path.join(ROOT, "data", "papers.yaml")

AVOID_LAST = 8          # don't reuse a hero seen this recently
RECENCY_HALF_LIFE = 4   # years; a paper this old is half as likely as a new one
SELF_BOOST = 2.0        # weight multiplier when the owner is first author
NO_LOGLINE_PENALTY = 0.2


def load_yaml(path, default=None):
    import yaml
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or (default if default is not None else {})


def weight(paper, newest, owner):
    """Recent work and first-authored work surface more often."""
    age = max(0, newest - int(paper.get("year", newest)))
    w = 0.5 ** (age / float(RECENCY_HALF_LIFE))
    authors = paper.get("authors") or []
    if owner and authors and authors[0] == owner:
        w *= SELF_BOOST
    # a paper whose logline is still the "Venue, year." fallback makes a poor billboard
    log = (paper.get("logline") or "").strip()
    if not log or re.fullmatch(r".+,\s*\d{4}\.", log):
        w *= NO_LOGLINE_PENALTY
    return w


def pick(papers, k, rng, newest, owner, blocked):
    """Weighted sample without replacement."""
    pool = [p for p in papers if p["title"] not in blocked] or list(papers)
    chosen = []
    weights = {p["title"]: weight(p, newest, owner) for p in pool}
    for _ in range(min(k, len(pool))):
        total = sum(weights[p["title"]] for p in pool)
        if total <= 0:
            chosen.append(rng.choice(pool))
        else:
            r, acc = rng.random() * total, 0.0
            for p in pool:
                acc += weights[p["title"]]
                if acc >= r:
                    chosen.append(p)
                    break
            else:
                chosen.append(pool[-1])
        pool = [p for p in pool if p["title"] != chosen[-1]["title"]]
        if not pool:
            break
    return chosen


def write_key(text, key, value):
    """Replace a top-level scalar or list key, preserving the rest of the file."""
    if isinstance(value, list):
        block = key + ":\n" + "".join('  - "%s"\n' % v.replace('"', '\\"') for v in value)
    else:
        block = '%s: "%s"\n' % (key, str(value).replace('"', '\\"'))
    pattern = re.compile(r"^%s:.*?(?=^\S|\Z)" % re.escape(key), re.S | re.M)
    if pattern.search(text):
        return pattern.sub(block, text, count=1)
    return block + "\n" + text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=8, help="papers in the spotlight row (0 to skip)")
    ap.add_argument("--seed", help="any string; the same seed always picks the same papers")
    ap.add_argument("--pin", help="force this title onto the billboard")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    papers = (load_yaml(PAPERS).get("papers") or [])
    if not papers:
        sys.exit("error: no data/papers.yaml — run scripts/bib2papers.py first")

    people = load_yaml(PEOPLE)
    owner = next((n for n, r in (people.get("people") or {}).items()
                  if (r or {}).get("self")), None)
    newest = max(int(p["year"]) for p in papers)
    rng = random.Random(a.seed if a.seed else None)

    hist = load_yaml(HISTORY, {"recent": []})
    recent = list(hist.get("recent") or [])

    if a.pin:
        want = re.sub(r"[^a-z0-9]", "", a.pin.lower())
        match = [p for p in papers if re.sub(r"[^a-z0-9]", "", p["title"].lower()) == want]
        if not match:
            match = [p for p in papers if want in re.sub(r"[^a-z0-9]", "", p["title"].lower())]
        if not match:
            sys.exit("error: no paper matches %r" % a.pin)
        hero = match[0]
    else:
        hero = pick(papers, 1, rng, newest, owner, set(recent[-AVOID_LAST:]))[0]

    spot = pick(papers, a.count, rng, newest, owner, {hero["title"]}) if a.count > 0 else []

    print("billboard  %s (%s %s)" % (hero["title"][:64], hero["venue"], hero["year"]))
    for p in spot:
        print("  spotlight  %-58s %s" % (p["title"][:58], p["year"]))
    if a.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    text = open(OVERRIDES, encoding="utf-8").read()
    text = write_key(text, "featured", hero["title"])
    if a.count > 0:
        text = write_key(text, "spotlight", [p["title"] for p in spot])
    open(OVERRIDES, "w", encoding="utf-8").write(text)

    recent.append(hero["title"])
    with open(HISTORY, "w", encoding="utf-8") as fh:
        fh.write("# Heroes already used, so the billboard does not repeat itself.\n")
        fh.write("# scripts/feature.py appends here; trim it freely.\n\nrecent:\n")
        for t in recent[-40:]:
            fh.write('  - "%s"\n' % t.replace('"', '\\"'))

    print("\nwrote bib/deck-overrides.yaml — now run scripts/bib2papers.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
