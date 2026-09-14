# Website Agent Guide

## Purpose and stack

This repository publishes Raula Gaikovina Kula's academic and research website at
`https://raux.github.io/`. It is a Hugo site using the `NewBee` theme, configured in
`hugo.toml`, and deployed from `master` to GitHub Pages.

## Important website areas

| Area | Main files | Notes |
| --- | --- | --- |
| Site identity and navigation | `hugo.toml` | Base URL, title, menus, author profile, English/Japanese languages, and site-wide settings. |
| Home and shared structure | `layouts/index.html`, `layouts/_default/baseof.html`, `layouts/partials/` | The home page and reusable header, footer, menu, search, metadata, and widget templates. |
| Posts and profile | `content/posts/`, `content/about/` | Markdown content; Japanese translations use the `.ja.md` suffix. |
| Research deck | `content/papers.md`, `layouts/_default/deck.html`, `bib/`, `data/papers.yaml` | The `/papers/` page is generated from bibliography and curation data. Read `scripts/README.md` before changing this pipeline. |
| Student ticker | `layouts/shortcodes/students.html`, `data/students.yaml`, `static/students/` | The `{{< students >}}` shortcode on `/posts/students/`. Hand-maintained, no generator. A person with no photo gets a monogram. |
| Deadline board | `content/deadlines.md`, `layouts/_default/deadlines.html`, `bib/conferences.yaml`, `data/deadlines.yaml` | The `/deadlines/` page displays generated conference and call-for-paper dates. |
| Styling and client behaviour | `static/css/`, `static/js/`, `static/images/` | Site-specific CSS, browser JavaScript, and static assets. |
| Translations | `content/**/*.ja.md`, `i18n/ja.toml`, `i18n/en.toml`, `i18n/zh.toml` | English is published at `/`; Japanese is published at `/ja/`. Keep route counterparts aligned when relevant. |
| Change history | `CHANGELOG.md` | Dated entries, newest first. Add to **Unreleased** as you go; it is written for a reader, not generated from commits. |
| Automation and deployment | `.github/workflows/` | PR builds and GitHub Pages deployment; paper-deck regeneration has its own workflow. |

## Data pipelines

### Research-paper deck (`/papers/`)

Inputs owned by editors:

- `bib/*.bib` — bibliographic exports
- `bib/deck-overrides.yaml` — paper themes, loglines, featured/spotlight choices, and visibility
- `bib/venues.yaml` — venue plates, publisher colours, and logos
- `bib/people.yaml` — author and current-institution metadata

Generated outputs — **do not edit by hand**:

- `data/papers.yaml`
- `data/venues.yaml`
- `data/institutions.yaml`

Regenerate locally after input changes:

```bash
pip install pyyaml
python scripts/bib2papers.py
python scripts/bib2papers.py --check
```

The `Rebuild paper deck` workflow in `.github/workflows/papers.yml` regenerates these
files on relevant pushes to `master`. `scripts/feature.py` controls the featured paper
and Spotlight row.

### Deadline board (`/deadlines/`)

- Editable source: `bib/conferences.yaml`
- Generated output: `data/deadlines.yaml` — **do not edit by hand**
- Generator: `scripts/deadlines.py`

Useful checks and rebuilds:

```bash
python scripts/deadlines.py list
python scripts/deadlines.py build
python scripts/deadlines.py build --check
```

`researchr` records are refreshed from their source; `manual` records are maintained in
`bib/conferences.yaml` and are not overwritten by refreshes.

## Content and template guidance

- Add ordinary pages and posts under `content/`; preserve Markdown front matter and create a
  `.ja.md` counterpart when a Japanese version is needed.
- Templates in `layouts/` override the theme. Prefer editing the smallest applicable layout or
  partial rather than copying theme-wide behaviour.
- Keep visual changes in `static/css/_custom.css` when possible; use other stylesheet files only
  for the component they already own.
- Place new public images and browser assets in `static/`; Hugo copies them to the site root.

## Validation and deployment

Before a PR, run the applicable checks:

```bash
hugo --minify --gc
python scripts/bib2papers.py --check       # when paper-deck inputs change
python scripts/deadlines.py build --check  # when deadline inputs change
```

GitHub Actions builds pull requests targeting `master`. Pushes to `master` trigger
`.github/workflows/deploy.yml`, which builds Hugo and deploys `public/` to `gh-pages`.

## Safety notes

- Do not hand-edit generated `data/*.yaml` pipeline outputs. The one exception is
  `data/students.yaml`, which has no generator and is maintained by hand; its header says so.
- Do not commit `public/` build output unless the task explicitly requires it.
- Treat `bib/deck-overrides.yaml`, `bib/venues.yaml`, `bib/people.yaml`, and
  `bib/conferences.yaml` as curated source data; preserve existing entries and comments.
- Confirm before committing, pushing, deploying, or running network-backed deadline refreshes.
