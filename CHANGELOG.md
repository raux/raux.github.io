# Changelog

Notable changes to [raux.github.io](https://raux.github.io/). Newest first.

The site deploys continuously from `master`, so there are no version numbers — entries
are dated by the day the work landed. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Two parts of the site are **generated** and have their own pipelines, documented in
[`scripts/README.md`](scripts/README.md): the research deck at `/papers/` and the deadline
board at `/deadlines/`. Changes to them are usually changes to a generator or to curated
input, not to a page.

## [Unreleased]

Branch `feature/papers-2025-2026`. 20 commits.

### Added

- **Deadline board at `/deadlines/`.** Submission dates for the venues this group
  publishes in, read from each conference's own dates page on `conf.researchr.org` rather
  than typed out by hand. Each row carries a live countdown, the venue plate, the kind of
  date, its timezone as published, a Google Calendar link, an `.ics` download and a link
  to the track. Rows group by month; the accent sharpens inside 30 days, then again inside
  7. Currently 8 conferences — APSEC 2026, CHASE, FSE, ICPC, ICSE, ICSME, MSR and SANER
  2027 — 60 dates on the board, 17 in the opening view. English and Japanese.
- **`scripts/deadlines.py`**, the board's generator: `add`, `refresh`, `list`, `remove`,
  `tracks`, `hide`, `show`, `keep`, `new` and `build`. Fetches are paced 1.5s apart.
- **Hand-entered deadlines.** `deadlines.py new` adds anything with no researchr page —
  a journal special issue, a smaller call — by prompt or entirely from flags. Every
  conference now carries a `source:`: `researchr` entries are re-read and replaced
  wholesale, `manual` ones are skipped by name and never overwritten.
- **Track-level curation.** `hide` and `show` prune a conference to the tracks worth
  watching, and `keep` inverts it. Hiding is a filter, not a deletion: hidden rows stay in
  `bib/conferences.yaml`, survive a refresh, and come back with no re-fetch. This is what
  makes the board readable — researchr serves ICSE's 62 co-located tracks under ICSE, so
  383 fetched dates across 96 tracks become 60 across 12. One hand-entered row alongside them: the
  *Information and Software Technology* special issue on *Evaluation of Qualitative Aspects of
  Intelligent Software Assistants*, due 13 December 2026.
- **A held billboard.** `feature.py --pin` now *keeps* a paper on the billboard instead of
  merely setting it; `--unpin` releases it. The Spotlight row still rotates underneath.
- **Daily rotation in CI**, for both pages: the paper deck reshuffles at 09:00 JST and the
  deadline board re-fetches at 09:20, each committing only when something actually moved.
- **`AGENT.MD`**, a map of the repository: where things live, what is generated, and which
  checks to run before a PR.
- **`bib/conferences.yaml` is safe to edit by hand.** It opens with a copy-paste template,
  and `build` validates what it reads — naming the conference, the row and the field —
  rather than failing with a traceback.

### Changed

- **The catalogue is complete: 43 papers → 127, spanning 2019-2024 → 2009-2026**, every one
  with its author list. 44 venue plates, 15 institutions.
- **Bylines and affiliations.** Cards show the first author in bold with a `+N` for the
  rest, and the accent colour when Kula is first author. The detail sheet lists everyone,
  tags the first author, and shows every distinct institution on the paper. Affiliations
  are **current**, not as-published, and live in `bib/people.yaml`.
- **Filtering is include/exclude** rather than two sets of radio buttons. Chips are
  tri-state — click to include, again to exclude, a third time to clear. Several includes
  in one facet are an OR; facets combine with AND. A new **Theme** facet joins Type and
  Years.
- **The billboard is currently held on** *BonsAIDE: An Extended Vision for Human-AI
  Interaction in IDEs* (ACM TOSEM 2026), with its DOI as the link.
- **`AVOID_LAST` 8 → 30.** The no-repeat window counts rotations, not days, so the old
  value meant eight days once rotation went daily.
- **An unknown `venue:` key is now taken literally** as the plate's label, so a hand-entered row can
  carry a short tag without inventing a registry entry. Falling back to the first word of the name
  only works when the name starts with the venue (`MSR 2027`), not when it is a title.
- **`kind:` is no longer stored in `bib/conferences.yaml`.** It is derived from the label
  at build time, so improving the rules re-sorts the whole board with no re-fetch, and the
  editable file carries only what the conference actually published.

### Fixed

- **Venue abbreviations matched first, not most-specific**, so `ACM TOSEM` rendered as
  `IEEE TSE`. The same trap caught `ESEM`/`EMSE`, `ASEW`/`ASE` and `IWESEP`.
- **Name variants split one person in two.** "Brittany Anne Reid" and "Brittany Reid" would
  have produced two bylines and two institution chips; `bib/people.yaml` gained `aliases:`.
- **Date-seeded rotation was not reproducible**, then its fix unblocked the current hero for
  every draw — the billboard could repeat the next day. The history now records
  `last_seed:` and the trailing entry is ignored only when the run repeats that seed.
  Verified over 34 consecutive daily rotations.
- **`write_key` quoted every scalar**, so `pinned: "false"` was a truthy string and would
  have held the billboard forever.
- **Camera-ready dates read as submissions.** `submission` was tested before `camera`, so
  "Camera-ready Submission Deadline" and 12 similar labels sat in the opening view.
- **Programme-committee dates were offered as author deadlines.** APSEC publishes its
  review cycle on the same page, and "Final Reviews Due" matched the `due` pattern.
- **Date ranges took their first day.** `Wed 7 - Sun 18 Oct 2026` is the 18th; the
  published text is kept as `raw` so a parsed date can be checked against its source.
- **researchr's "new" badges concatenated into labels** — stripping tags bare gave
  "Abstract deadlinenew". One label also began with an invisible word joiner (U+2060) and
  ended with a stray colon.
- **The detail sheet mislabelled every non-arXiv link** as "Find on DBLP", including real
  DOIs, and the deck footer credited files in `data/` that live in `bib/`.
- **The `build` summary counted the raw pull, not the board**, reporting 446 where the file
  held 376.
- **A colon in a venue name** ("Journal of Software: Evolution and Process") broke
  `venues.yaml` until quoted, and **"New Releases" still meant 2024**.

### Data quality

Google Scholar is an index, not a source of record. **12 of its 60 pre-2019 rows were
dropped rather than imported**: two proceedings front-matter records whose author field is
every author in the volume, one mojibake title, one row dated 1992 which is impossible for
its authors, and eight duplicates. It also **corrected two venues** that had been inferred
from conference profiles.

Author lists come from a third-party index rather than the papers themselves, and **20 of
168 affiliations are verified**; the other 148 are counted in every run's warnings, so cards
degrade quietly rather than breaking.

`robots.txt` was respected throughout: DBLP's search API and `.bib` export and Scholar's
`/citations` paths are disallowed to automated fetchers, so neither was fetched
programmatically.

## 2026-09-09 — Research deck

Reconstructed from git history; this predates the changelog.

### Added

- **Research deck at `/papers/`** (#56), generated from BibTeX — a browsable, themed view
  of the publication record in place of a list.
- **Venue plates** as card art (#56), replacing abstract posters: the abbreviation set
  large, the full name beneath, and the publisher's mark over a wash of their brand colour,
  with a node-link texture seeded from the paper's own title.
- **Authors and institutions on every card** (#57), with the first author foremost.

[Unreleased]: https://github.com/raux/raux.github.io/compare/master...feature/papers-2025-2026
