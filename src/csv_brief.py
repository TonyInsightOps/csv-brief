#!/usr/bin/env python3
"""Create a local HTML brief and JSON profile from a CSV file."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


def clean_header(value: str) -> str:
    return " ".join(value.strip().split())


def clean_value(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def parse_numbers(values: list[str]) -> list[Decimal] | None:
    try:
        return [Decimal(value) for value in values]
    except InvalidOperation:
        return None


def parse_dates(values: list[str]) -> list[date] | None:
    try:
        return [date.fromisoformat(value) for value in values]
    except ValueError:
        return None


def audit_join_key(
    rows: list[dict[str, str]],
    headers: list[str],
    key_columns: list[str],
    include_key_values: bool = True,
) -> dict:
    keys = [clean_header(column) for column in key_columns]
    if any(not column for column in keys):
        raise ValueError("Join-key column names must not be blank")
    if len(set(keys)) != len(keys):
        raise ValueError("Join-key columns must not be repeated")
    unknown = [column for column in keys if column not in headers]
    if unknown:
        raise ValueError(f"Unknown join-key columns: {', '.join(unknown)}")

    groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
    blank_rows: list[int] = []
    for source_row, row in enumerate(rows, start=2):
        key = tuple(row[column] for column in keys)
        if not all(key):
            blank_rows.append(source_row)
        else:
            groups[key].append(source_row)

    duplicate_groups = [
        (key, source_rows)
        for key, source_rows in sorted(groups.items())
        if len(source_rows) > 1
    ]
    group_details = []
    for key, source_rows in duplicate_groups:
        detail: dict[str, object] = {"source_rows": source_rows}
        if include_key_values:
            detail["key"] = list(key)
        group_details.append(detail)

    duplicate_key_rows = sorted(
        source_row
        for _, source_rows in duplicate_groups
        for source_row in source_rows
    )
    ready = not blank_rows and not duplicate_groups
    return {
        "key_columns": keys,
        "one_to_one_ready": ready,
        "status": "pass" if ready else "review",
        "blank_key_rows": blank_rows,
        "duplicate_key_groups": len(duplicate_groups),
        "duplicate_key_rows": duplicate_key_rows,
        "duplicate_key_excess_rows": sum(len(source_rows) - 1 for _, source_rows in duplicate_groups),
        "groups": group_details,
        "interpretation": (
            "No blank or duplicate keys were found in the declared columns."
            if ready
            else "Review blank or duplicate keys before using this file as the one-side of a join."
        ),
    }


def profile_csv(
    input_path: Path,
    include_top_values: bool = True,
    key_columns: list[str] | None = None,
    include_key_values: bool = True,
) -> dict:
    source_bytes = input_path.read_bytes()
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Input CSV must have a header row")
        headers = [clean_header(name) for name in reader.fieldnames]
        if any(not name for name in headers):
            raise ValueError("Header names must not be blank")
        if len(set(headers)) != len(headers):
            raise ValueError("Header names are duplicated after whitespace normalization")

        rows: list[dict[str, str]] = []
        for source_line, source_row in enumerate(reader, start=2):
            if None in source_row:
                raise ValueError(f"Row {source_line} has more fields than the header")
            rows.append({clean_header(key): clean_value(value) for key, value in source_row.items()})

    row_tuples = [tuple(row[column] for column in headers) for row in rows]
    row_counts = Counter(row_tuples)
    duplicate_rows = sum(count - 1 for count in row_counts.values() if count > 1)

    columns: list[dict[str, object]] = []
    missing_cells = 0
    for column in headers:
        all_values = [row[column] for row in rows]
        values = [value for value in all_values if value != ""]
        missing = len(all_values) - len(values)
        missing_cells += missing
        summary: dict[str, object] = {
            "name": column,
            "type": "empty",
            "non_missing": len(values),
            "missing": missing,
            "distinct": len(set(values)),
        }

        if values:
            numbers = parse_numbers(values)
            dates = parse_dates(values) if numbers is None else None
            if numbers is not None:
                mean = sum(numbers, Decimal("0")) / Decimal(len(numbers))
                summary.update(
                    {
                        "type": "number",
                        "minimum": decimal_text(min(numbers)),
                        "maximum": decimal_text(max(numbers)),
                        "mean": decimal_text(mean),
                    }
                )
            elif dates is not None:
                summary.update(
                    {
                        "type": "date",
                        "minimum": min(dates).isoformat(),
                        "maximum": max(dates).isoformat(),
                    }
                )
            else:
                summary["type"] = "text"
                if include_top_values:
                    summary["top_values"] = [
                        {"value": value, "count": count}
                        for value, count in Counter(values).most_common(5)
                    ]
        columns.append(summary)

    flags = []
    if missing_cells:
        flags.append(f"{missing_cells} missing cell(s) require review")
    if duplicate_rows:
        flags.append(f"{duplicate_rows} exact duplicate row(s) require review")

    profile = {
        "source_file": input_path.name,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "row_count": len(rows),
        "column_count": len(headers),
        "missing_cells": missing_cells,
        "exact_duplicate_rows": duplicate_rows,
        "baseline_status": "review" if flags else "pass",
        "quality_flags": flags,
        "columns": columns,
        "limits": [
            "Basic deterministic profiling only",
            "No fuzzy duplicate detection or inferred replacements",
            "Human review is required before sharing or acting on results",
        ],
    }
    if key_columns:
        profile["join_guard"] = audit_join_key(
            rows,
            headers,
            key_columns,
            include_key_values=include_key_values,
        )
    return profile


def render_html(profile: dict, title: str) -> str:
    def escaped(value: object) -> str:
        return html.escape(str(value))

    column_rows = []
    for column in profile["columns"]:
        range_text = ""
        if "minimum" in column:
            range_text = f'{escaped(column["minimum"])} to {escaped(column["maximum"])}'
        top_values = column.get("top_values", [])
        top_text = ", ".join(
            f'{escaped(item["value"])} ({escaped(item["count"])})' for item in top_values
        )
        column_rows.append(
            "<tr>"
            f'<td><strong>{escaped(column["name"])}</strong></td>'
            f'<td>{escaped(column["type"])}</td>'
            f'<td>{escaped(column["non_missing"])}</td>'
            f'<td>{escaped(column["missing"])}</td>'
            f'<td>{escaped(column["distinct"])}</td>'
            f"<td>{range_text}</td>"
            f"<td>{top_text}</td>"
            "</tr>"
        )

    flags = profile["quality_flags"] or ["No missing cells or exact duplicate rows detected."]
    flag_items = "".join(f"<li>{escaped(flag)}</li>" for flag in flags)
    status = escaped(str(profile["baseline_status"]).upper())
    join_guard = profile.get("join_guard")
    join_card = ""
    join_section = ""
    if join_guard:
        join_status = escaped(str(join_guard["status"]).upper())
        join_card = (
            '<div class="card"><div class="muted">JoinGuard</div>'
            f'<div class="value">{join_status}</div></div>'
        )
        group_items = []
        for index, group in enumerate(join_guard["groups"], start=1):
            key_text = " / ".join(group.get("key", [])) or f"hidden group {index}"
            rows_text = ", ".join(str(row) for row in group["source_rows"])
            group_items.append(
                f"<li><strong>{escaped(key_text)}</strong>: source rows {escaped(rows_text)}</li>"
            )
        groups_html = "".join(group_items) or "<li>No duplicate key groups detected.</li>"
        blank_text = ", ".join(str(row) for row in join_guard["blank_key_rows"]) or "None"
        join_section = f"""
  <section><h2>JoinGuard</h2>
    <p><strong>Declared key:</strong> {escaped(', '.join(join_guard["key_columns"]))}</p>
    <p><strong>One-to-one ready:</strong> {escaped(join_guard["one_to_one_ready"])}</p>
    <p><strong>Blank-key source rows:</strong> {escaped(blank_text)}</p>
    <p>{escaped(join_guard["interpretation"])}</p>
    <h3>Duplicate key evidence</h3><ul>{groups_html}</ul>
  </section>"""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped(title)}</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, system-ui, sans-serif; }}
    body {{ margin: 0; background: #f4f7fb; color: #172033; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 40px 24px 64px; }}
    h1 {{ margin-bottom: 6px; }} .muted {{ color: #667085; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 24px 0; }}
    .card, section {{ background: white; border: 1px solid #dfe5ee; border-radius: 12px; padding: 18px; }}
    .value {{ font-size: 1.7rem; font-weight: 700; margin-top: 6px; }}
    section {{ margin-top: 16px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    th, td {{ border-bottom: 1px solid #e7ebf1; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f8fafc; }} code {{ overflow-wrap: anywhere; }}
    footer {{ margin-top: 24px; color: #667085; font-size: 0.88rem; }}
  </style>
</head>
<body><main>
  <h1>{escaped(title)}</h1>
  <p class="muted">Local deterministic profile of <strong>{escaped(profile["source_file"])}</strong></p>
  <div class="cards">
    <div class="card"><div class="muted">Baseline status</div><div class="value">{status}</div></div>
    <div class="card"><div class="muted">Rows</div><div class="value">{escaped(profile["row_count"])}</div></div>
    <div class="card"><div class="muted">Columns</div><div class="value">{escaped(profile["column_count"])}</div></div>
    <div class="card"><div class="muted">Missing cells</div><div class="value">{escaped(profile["missing_cells"])}</div></div>
    <div class="card"><div class="muted">Exact duplicate rows</div><div class="value">{escaped(profile["exact_duplicate_rows"])}</div></div>
    {join_card}
  </div>
  <section><h2>Quality flags</h2><ul>{flag_items}</ul></section>
  {join_section}
  <section><h2>Column profile</h2><table>
    <thead><tr><th>Column</th><th>Type</th><th>Present</th><th>Missing</th><th>Distinct</th><th>Range</th><th>Top values</th></tr></thead>
    <tbody>{''.join(column_rows)}</tbody>
  </table></section>
  <section><h2>Traceability</h2><p>SHA-256: <code>{escaped(profile["source_sha256"])}</code></p></section>
  <footer>Baseline validation only. Human review is required before sharing or acting on this report.</footer>
</main></body></html>
"""


def write_brief(
    input_path: Path,
    output_dir: Path,
    title: str,
    include_top_values: bool = True,
    key_columns: list[str] | None = None,
    include_key_values: bool = True,
) -> dict:
    profile = profile_csv(
        input_path,
        include_top_values=include_top_values,
        key_columns=key_columns,
        include_key_values=include_key_values,
    )
    profile_path = output_dir / "profile.json"
    brief_path = output_dir / "brief.html"
    source_path = input_path.resolve()
    if any(path.resolve() == source_path for path in (profile_path, brief_path)):
        raise ValueError("Output directory would overwrite the source file")
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    brief_path.write_text(render_html(profile, title), encoding="utf-8")
    return {"profile": profile, "profile_path": profile_path, "brief_path": brief_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--title", default="CSV Data Brief")
    parser.add_argument("--hide-top-values", action="store_true")
    parser.add_argument(
        "--key",
        action="append",
        default=[],
        help="Declared join-key column; repeat for a composite key",
    )
    parser.add_argument("--hide-key-values", action="store_true")
    args = parser.parse_args()
    result = write_brief(
        args.input,
        args.output_dir,
        args.title,
        include_top_values=not args.hide_top_values,
        key_columns=args.key,
        include_key_values=not args.hide_key_values,
    )
    summary = {
        "brief": str(result["brief_path"]),
        "profile": str(result["profile_path"]),
        "rows": result["profile"]["row_count"],
        "columns": result["profile"]["column_count"],
        "baseline_status": result["profile"]["baseline_status"],
    }
    if "join_guard" in result["profile"]:
        summary["join_guard_status"] = result["profile"]["join_guard"]["status"]
        summary["one_to_one_ready"] = result["profile"]["join_guard"]["one_to_one_ready"]
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
