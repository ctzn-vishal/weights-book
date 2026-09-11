# Weights, Design, and Estimands

*A Field Guide for Applied Researchers* — Vishal Singh

An online booklet on three decisions hidden inside "should I use the survey
weights?": the population quantity being targeted, the way observations enter the
estimator, and the sampling or assignment design that governs uncertainty. Every
chapter is built on real public survey data (ACS, CPS, ATUS, NHIS, NHANES, BRFSS).

**Status: first draft.** Pages carry a draft banner and are excluded from search
indexing until the verification pass is complete.

Served at **https://vishalsingh.org/weights** (see *Deployment*).

## How the book is built

```
Box (analysis, never public)                 this repo (public)                     Vercel
  ipums/parquet, analysis/  (microdata)        app/<chapter>/article.mdx   prose
  ipums/book/chapters/<chapter>/build.py  ─►   app/<chapter>/data/*.json   numbers ─► vishalsingh.org/weights
       writes artifacts/*.json                 analysis/<chapter>/*.py     code
                     book/export.py  ──────────┘
```

- Analysis runs where the data live. Each chapter's `build.py` reads the microdata,
  computes design-based estimates (Taylor linearization or replicate weights), and
  writes small JSON artifacts: **facts** (every number the prose states), **figures**,
  and **ledgers** (the Analysis Ledger for each headline result).
- `book/export.py` is the only bridge. It copies artifacts and code into this repo
  and refuses to copy microdata or anything resembling a credential.
- Prose never types a number. `<Fact id="ch1.atus_work_weighted" />` renders the value
  from the artifact, with its interval, weight, variance method, and source on hover.
  The build fails if a referenced fact, figure, ledger, or citation does not exist.
- Microdata are never redistributed. The repo holds only published-style aggregates
  and the code that produced them.

## Local development

```bash
npm install
npm run dev
```

Then open http://localhost:3000/weights (the app lives under the `/weights` base path).

`npm run build` regenerates the artifact registry, verifies every reference in the
chapters, builds the site, and checks that no equation failed to render.

Chapter authors can check a draft without a full build:

```bash
node scripts/check-mdx.mjs path/to/article.mdx --data path/to/artifacts
```

## Repository layout

| Path | Contents |
|---|---|
| `app/<chapter>/` | `article.mdx`, `page.tsx`, and `data/` (manifest, facts, ledger, figures) |
| `components/book/`, `components/charts/` | book chrome, MDX components, server-rendered SVG charts |
| `components/widgets/` | interactive widgets (sampler, weight builder, hidden weights, …) |
| `lib/` | TOC, artifact registry and types, formatters, the synthetic population |
| `analysis/<chapter>/` | the analysis code that produced each chapter's artifacts |
| `docs/CONTRACT.md` | the authoring contract: artifact schema, MDX rules, editorial rules |
| `data/references.json` | the verified bibliography |

## Deployment

Deploy as a standalone Vercel project (framework preset: Next.js; default install and
build commands). Because of `basePath: '/weights'`, the site is served at
`https://<project>.vercel.app/weights`, and the bare root redirects there.

To serve it at `vishalsingh.org/weights`, add a rewrite to the `beforeFiles` array in
the `d3m-book` project's `next.config.ts` (it must be `beforeFiles`, because
`app/[slug]` there would otherwise match `/weights`):

```ts
{ source: '/weights', destination: 'https://<project>.vercel.app/weights' },
{ source: '/weights/:path*', destination: 'https://<project>.vercel.app/weights/:path*' },
```

## Data and citation

Data: IPUMS USA, IPUMS CPS, IPUMS Time Use, IPUMS Health Surveys (NHIS), CDC/NCHS
NHANES, and CDC BRFSS. Full citations and pinned
releases are in Appendix C of the book. Use of IPUMS data is subject to the IPUMS
terms of use; this repository contains derived aggregates only.
