# Research deck pipeline

The deck at [`/papers/`](https://raux.github.io/papers/) is generated. Three files feed it:

| File | Owner | Contents |
|---|---|---|
| `bib/*.bib` | your reference manager | title, year, venue, DOI/URL |
| `bib/deck-overrides.yaml` | you, by hand | themes, loglines, featured paper, hidden entries |
| `bib/venues.yaml` | you, by hand | card art: abbreviation, publisher, brand colour per venue |
| `bib/people.yaml` | you, by hand | where each author is now, and their institution |
| `data/papers.yaml` | **generated — do not edit** | what the site reads |
| `data/venues.yaml` | **generated — do not edit** | the plate for each venue in use |
| `data/institutions.yaml` | **generated — do not edit** | the institutions in use |

## Adding papers

Drop a new export into `bib/` (replacing `publications.bib`, or alongside it — every
`.bib` in the folder is read), commit, push. The **Rebuild paper deck** action regenerates
`data/papers.yaml`, commits it, and asks the site workflows to redeploy.

Locally:

```bash
pip install pyyaml
python scripts/bib2papers.py          # regenerate
python scripts/bib2papers.py --check  # exit 1 if stale; this is what PRs run
```

## Writing the curation

BibTeX has no field for "which theme is this" or "why should anyone read it", so those
live in `bib/deck-overrides.yaml`, keyed by citation key *or* title (case and
punctuation are ignored, so a key that changes between exports still matches by title):

```yaml
featured: "The Life and Death of Software Ecosystems"

entries:
  DBLP:journals/tse/KulaGB23:
    themes: [soc, eco]     # eco sec prof soc review — max 3, the first tints the poster
    logline: "What happens to a package ecosystem when the world's politics arrive in it."
    venue: "IEEE TSE"      # optional, overrides the abbreviation derived from the .bib
    kind: journal          # optional: journal | conf | preprint
    hide: false            # optional: keep an entry out of the deck
```

Nothing in this file is ever overwritten. A paper with no logline still appears, falling
back to `Venue, year` — and the run warns about it, so gaps stay visible instead of
quietly shipping.

## Card art

Each card shows its venue's plate: the abbreviation set large, the full name beneath, and the
publisher's mark over a wash of their brand colour — with a faint node-link texture seeded from
the paper's own title, so no two cards in a row look identical.

Venues are described in `bib/venues.yaml`:

```yaml
publishers:
  ieee: { name: "IEEE", color: "#00629B", logo: "ieee-cs.webp" }   # logo lives in static/venues/
  elsevier: { name: "Elsevier", color: "#D8642B" }                 # no logo file -> wordmark in type

venues:
  "MSR":
    abbr: MSR                              # what fills the card, set at 38px
    full: Mining Software Repositories
    publisher: ieee
```

A publisher with a `logo` renders that image; one without renders its name as a wordmark. To
upgrade a wordmark to a real mark, drop the file into `static/venues/` and add `logo:` — mind
each publisher's brand guidelines. A venue missing from the registry gets a plain slate plate
and a warning naming it.

## Choosing what the deck puts forward

`scripts/feature.py` picks the billboard paper and the Spotlight row, writing `featured:` and
`spotlight:` into `bib/deck-overrides.yaml` and leaving the rest of that file alone. Run
`scripts/bib2papers.py` afterwards to rebuild.

```bash
python scripts/feature.py                    # a fresh random pick
python scripts/feature.py --count 10         # longer Spotlight row (0 to skip it)
python scripts/feature.py --seed 2026-09-09  # reproducible — CI can pass the date
python scripts/feature.py --pin "Open Source at a Crossroads"   # choose the hero yourself
python scripts/feature.py --dry-run          # print the pick, write nothing
```

It **rotates on its own**: the *Rebuild paper deck* workflow runs every Monday, reshuffles with
`--seed $(date -u +%F)`, commits the result and asks the site to redeploy. Only the schedule and
an explicit "Run workflow" (with *rotate* ticked) reshuffle — a content push never moves the
billboard out from under whatever you just wrote. To make it daily, change the cron in
`.github/workflows/papers.yml` from `0 0 * * 1` to `0 0 * * *`.

Because the seed is the date, a re-run on the same day reproduces exactly the same pick and
commits nothing.

The draw is weighted rather than uniform: recent work and papers where you are first author come
up more often, and a paper whose logline is still the `Venue, year.` fallback is heavily
discounted, since it makes a poor billboard. Heroes used recently are recorded in
`bib/feature-history.yaml` and skipped, so the billboard does not repeat.

## Authors and institutions

Author names and their order come from the `.bib`, so keeping the export current keeps the
bylines current. A card shows the **first author** in bold, a `+N` for the rest, and a small
accent dot when you are a co-author but not first; when you *are* first author your name is in
the accent colour. The detail sheet lists everyone, tags the first author, and shows every
distinct institution on the paper.

BibTeX has no affiliation field, so `bib/people.yaml` carries that:

```yaml
institutions:
  osaka: { name: "The University of Osaka", short: "Osaka", color: "#0F3B7C" }

people:
  "Raula Gaikovina Kula":
    institution: osaka
    self: true          # marks you — shown in the accent colour throughout
  "Some Coauthor": { institution: "" }    # no chip, and the run warns
```

These are **current** affiliations, reused across all of a person's papers — so a 2019 paper
shows where its authors are today, not where the work was done. People move, so this file needs
an occasional pass; every author still missing an institution is counted in the run summary.

To use a real university mark instead of a wordmark chip, add `logo: "osaka.svg"` to the
institution and drop the file in `static/institutions/` — mind each university's brand
guidelines, they are stricter than most publishers'.

## What the generator does on its own

- **Venue abbreviation** — `IEEE Transactions on Software Engineering` → `IEEE TSE`, via
  the `VENUE_MAP` table at the top of `bib2papers.py`. Add your own venues there.
- **Kind** — `@inproceedings` → conference, `@article` → journal, anything with
  `archivePrefix = {arXiv}` or a `CoRR` journal → preprint.
- **Link** — `url`, else `doi` as a doi.org link, else the arXiv abstract page, else a
  DBLP title search.
- **Themes** — keyword rules over title, venue and keywords (`THEME_RULES` in the script).
  A guess, and meant to be overridden.
- **Preprint merging** — when an arXiv entry and its published version share a title, only
  the published one is kept, inheriting the preprint's logline if it has none of its own.
- **Authors** — parsed from the `.bib` `author` field, accepting both `First Last` and
  `Last, First`, in printed order. A curated `authors:` list in the overrides wins if a parse
  goes wrong.
- **Sorting** — newest first, then alphabetical.

## Warnings worth acting on

```
warn:   no logline yet: Detecting Vulnerable Dependencies with LLMs
warn:   override matches nothing: nonexistentkeycheck
```

The first means a new paper is on the site with a placeholder line. The second means an
override lost its paper — usually a title edited in the `.bib`, or an entry you removed.
Both appear in the Actions run summary.


---

# Deadline board

A second, independent pipeline behind [`/deadlines/`](https://raux.github.io/deadlines/).

| File | Owner | Contents |
|---|---|---|
| `bib/conferences.yaml` | you, plus the fetcher | which conferences to track, and every date read from them |
| `data/deadlines.yaml` | **generated — do not edit** | what the page reads |

Conference deadlines are not typed out by hand: `scripts/deadlines.py` reads each conference's own
dates page on `conf.researchr.org`, so the board stays honest to its source. Journal special issues
and anything else researchr does not carry are entered with `new`, below.

```bash
python scripts/deadlines.py add msr-2027                 # add a conference
python scripts/deadlines.py add https://conf.researchr.org/home/icse-2027
python scripts/deadlines.py refresh                      # re-read every one
python scripts/deadlines.py refresh saner-2027           # or just one
python scripts/deadlines.py list                         # what is tracked, and how much is still ahead
python scripts/deadlines.py remove icsme-2026            # stop tracking one entirely

python scripts/deadlines.py tracks icse-2027             # what tracks it carries, and how many dates each
python scripts/deadlines.py hide icse-2027 "Shadow PC"   # drop a track from the board
python scripts/deadlines.py hide icse-2027 --matching MSR
python scripts/deadlines.py show icse-2027 "Shadow PC"   # put it back
python scripts/deadlines.py keep icse-2027 --matching "Research Track,NIER"   # hide everything else
python scripts/deadlines.py build                        # write data/deadlines.yaml
python scripts/deadlines.py build --check                # exit 1 if stale

python scripts/deadlines.py new                          # hand-enter anything researchr does not carry
```

`keep` is `hide` inverted: it keeps the tracks you name and hides every other one, which is how the
board went from 376 dates to the research and NIER tracks alone.

`add` and `refresh` need network and space their requests out; `build` is offline. Only `build`
is needed in CI if the fetched data is committed.

## What it works out on its own

- **Dates.** A row reading `Wed 7 - Sun 18 Oct 2026` resolves to its **end**, since that is the date
  the deadline actually lands on; the original text is kept as `raw`.
- **Kind.** `submission`, `notification`, `camera`, `event` or `other`, from the label. This is what
  makes the board usable — the page opens showing submissions only, because a conference page lists
  four or five times as many notification and camera-ready dates.
- **Venue plate.** `msr-2027` finds the `MSR` plate already defined in `bib/venues.yaml`, so the
  board and the research deck use one visual vocabulary. `VENUE_ALIASES` in the script covers the
  cases where the slug and the plate differ, such as ESEIW → ESEM.

`name` and `venue` in `bib/conferences.yaml` are yours to edit; everything under `deadlines:` is
replaced on the next refresh.

## Journals, special issues, and anything else off researchr

Not every deadline has a researchr page — journal special issues and smaller calls usually live on a
publisher's own page. `new` enters one by hand. Run it bare and it asks:

```
$ python scripts/deadlines.py new
Name (e.g. 'TOSEM Special Issue on Agentic SE'): TOSEM Special Issue on Agentic Software Engineering
Short id [tosem-special-issue-on-agentic-software-engineering]:
Call-for-papers URL: https://dl.acm.org/journal/tosem/calls-for-papers
Venue key from bib/venues.yaml (blank for none): ACM TOSEM
Track name [Submission]: Special Issue
Timezone as published (e.g. 'AoE (UTC-12h)'): AoE (UTC-12h)
  date 1 (YYYY-MM-DD, blank to finish): 2027-02-15
  label [Paper submission]:
  date 2 (YYYY-MM-DD, blank to finish): 2027-05-30
  label [Paper submission]: First-round notification
  date 3 (YYYY-MM-DD, blank to finish):
added tosem-special-issue-on-agentic-software-engineering — 2 dates, kept out of every refresh
```

or drive it entirely from flags, which is what to do when scripting or when the shell is not
interactive:

```bash
python scripts/deadlines.py new \
  --name "TOSEM Special Issue on Agentic Software Engineering" \
  --url https://dl.acm.org/journal/tosem/calls-for-papers \
  --venue "ACM TOSEM" --track "Special Issue" --tz "AoE (UTC-12h)" \
  --date 2027-02-15 --label "Paper submission" \
  --date 2027-05-30 --label "First-round notification"
```

Each conference in `bib/conferences.yaml` now carries a `source:`, and it decides who owns the dates:

| `source` | Where the dates come from | What `refresh` does |
|---|---|---|
| `researchr` | the conference's dates page | re-reads it, replacing `deadlines:` wholesale |
| `manual` | you, via `new` or by editing the file | **nothing — it is skipped by name** |

So a hand-entered row is safe to edit in place: nothing overwrites it. `refresh` says so rather than
silently passing over it, and naming a manual entry explicitly is an error, not a no-op. Everything
downstream treats the two the same — `list`, `remove`, `hide`/`show`/`keep`, `build`, the venue
plate, the countdown, the `.ics` download. `list` prints `by hand` where a fetched entry shows its
last fetch date.

To retire one, `remove` it like any other; to correct a date, edit `bib/conferences.yaml` and
`build`.

## Things to know

- A conference whose dates have all passed is named in the `build` output, so it can be refreshed to
  its next edition or removed.
- researchr aggregates co-located events, so ICSE 2027 carries its workshops: 62 tracks, including
  full MSR and CHASE ones that also appear under those conferences on their own. `tracks` shows what
  a conference is really carrying and `hide` prunes it. **Hiding is a filter, not a deletion** — the
  rows stay in `bib/conferences.yaml` under a `hidden:` block, survive `refresh`, and `show` brings
  them back with no re-fetch. Removing the duplicated ICSE tracks takes it from 238 dates to 168.
- Dates are shown exactly as published, with the conference's stated timezone beside the row.
  **Always check the conference site before relying on one.**
