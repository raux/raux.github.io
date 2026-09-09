# Research deck pipeline

The deck at [`/papers/`](https://raux.github.io/papers/) is generated. Three files feed it:

| File | Owner | Contents |
|---|---|---|
| `bib/*.bib` | your reference manager | title, year, venue, DOI/URL |
| `bib/deck-overrides.yaml` | you, by hand | themes, loglines, featured paper, hidden entries |
| `bib/venues.yaml` | you, by hand | card art: abbreviation, publisher, brand colour per venue |
| `data/papers.yaml` | **generated — do not edit** | what the site reads |
| `data/venues.yaml` | **generated — do not edit** | the plate for each venue in use |

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
- **Sorting** — newest first, then alphabetical.

## Warnings worth acting on

```
warn:   no logline yet: Detecting Vulnerable Dependencies with LLMs
warn:   override matches nothing: nonexistentkeycheck
```

The first means a new paper is on the site with a placeholder line. The second means an
override lost its paper — usually a title edited in the `.bib`, or an entry you removed.
Both appear in the Actions run summary.
