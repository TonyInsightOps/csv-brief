# CSV Brief

![CSV Brief — from raw CSV to reviewable insight](docs/csv-brief-hero.png)

[![Tests](https://github.com/TonyInsightOps/csv-brief/actions/workflows/test.yml/badge.svg)](https://github.com/TonyInsightOps/csv-brief/actions/workflows/test.yml)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB)
![No dependencies](https://img.shields.io/badge/dependencies-none-16A34A)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Local-only and stdlib-only:** CSV Brief makes no network requests, emits no
> telemetry, requires no credentials, and uses only the Python standard library.
> Python 3.9 or newer is required.

CSV Brief turns a CSV file into two reviewable local artifacts:

- a self-contained HTML data brief for a client or reviewer;
- a JSON profile for reproducible QA and downstream work.

It is a small portfolio product for CSV cleaning, BI, and public-data research
jobs. It reports structure, missing cells, exact duplicate rows, inferred basic
column types, numeric/date ranges, and optional top text values.

## Hard boundaries

CSV Brief does **not** parse XLSX workbooks or PDFs, fetch webpages, run OCR,
perform fuzzy matching, infer missing values, detect fraud, prove source truth,
or replace analyst review. Type inference is a deterministic convenience, not a
business definition. Review the generated report before sharing it.

## One-command demo

Open a terminal in the directory containing this README and run:

```bash
python3 scripts/run_demo.py
```

The demo uses only `assets/synthetic_sales.csv`, writes into a temporary local
directory, and prints a clear `[PASS]` or `[FAIL]` result.

## Run on a CSV

```bash
python3 src/csv_brief.py assets/synthetic_sales.csv \
  --output-dir my-brief \
  --title "Synthetic Sales Data Brief"
```

Outputs:

- `my-brief/brief.html`
- `my-brief/profile.json`

For a safer report that does not include the most common text values:

```bash
python3 src/csv_brief.py assets/synthetic_sales.csv \
  --output-dir my-brief-private \
  --hide-top-values
```

## Current test scope

```bash
python3 -m unittest discover -s tests -v
```

The five tests cover the bundled synthetic profile, numeric/date inference,
HTML and JSON generation, suppression of top text values, rejection of ragged
rows, and rejection of blank headers. They do not cover real customer files,
XLSX, OCR, large-file performance, locale-specific number/date formats, fuzzy
duplicates, or the correctness of business conclusions.

## Privacy and safe use

The tool does not upload data, but its HTML report may contain column names and
top text values from the input. Use `--hide-top-values`, inspect outputs, and
never publish customer, personal, confidential, or proprietary data without
authorization. The bundled fixture is invented and safe for demonstrations.

## Commercial use

The MIT license permits commercial use. The open prototype can support paid
work such as custom profiling rules, private workbook conversion, dashboard
design, data cleanup, and analyst-reviewed public-data briefs.

## Client-ready service

### CSV Data Quality Mini Audit — US$99 fixed

- up to 5,000 CSV rows;
- one agreed deterministic duplicate key;
- cleaned CSV plus an exception register;
- reproducible JSON profile and a reviewable HTML brief;
- concise QA and reconciliation notes;
- delivery through an active, funded marketplace contract.

Larger files, fuzzy entity matching, XLSX workbooks, dashboards, and custom
business rules are scoped separately before work begins.

**[Hire me on Upwork](https://www.upwork.com/freelancers/~0126ecd9d346d44de2)**

For privacy, never post client files or personal data in GitHub issues.
