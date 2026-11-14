# Sample CSV audit: stop a bad export before the next report

This is an example of a **reviewable result**, using invented data, not a claim
about a real client's numbers. Nothing was uploaded or corrected automatically.

| Check | [Reference export](../assets/synthetic_sales_baseline.csv) | [Incoming export](../assets/synthetic_sales.csv) |
|---|---:|---:|
| Rows (excluding the header) | 6 | 7 |
| Columns | 6 | 6 |
| Missing revenue values | 0 | 1 |
| Exact duplicate rows (after input normalization) | 0 | 1 |
| Duplicate groups in the declared `order_id` key | 0 | 1 |
| Ready to use as the unique side of a join? | Yes, structurally | No |

## Findings you can act on

- **Duplicate key:** order `O-1001` appears at source CSV lines **2 and 7**,
  counting the header as line 1. Check whether the second row was imported twice
  before removing it: the audit does not decide which row belongs.
- **Missing value:** order `O-1003`, source CSV line **4**, has a blank revenue
  field. The new export's revenue missing rate is **1/7 (14.3%)**, up from 0%.
  Verify the source value rather than guess.
- Structural key checks can stop an unsafe join; they cannot prove that the
  chosen key or join represents the right business relationship.

## What is delivered

The tool writes a local HTML brief, JSON profile and JSON drift register, then
returns **exit code 2** for this fixture to mark it for review. The two
review-level changes are the missing rate and loss of key uniqueness. Row
count and changes in distinct values are informational. The original data is
not changed by the audit.

To reproduce from the repository root:

```bash
python3 scripts/run_demo.py
```

The demo should print `[PASS]`: this means it correctly detected the *intentional
regressions*, not that the incoming CSV passed the join gate.

For a similar audit, start with a de-identified export, the columns expected to
be unique and an optional baseline. Agree which exceptions require review
before any cleanup or implementation. No XLSX, PDF/OCR, fuzzy matching or
inferred values are included in this demo.
