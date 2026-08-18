#!/usr/bin/env python3
"""Run the CSV Brief CLI against its bundled synthetic fixture."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="csv-brief-demo-") as directory:
        process = subprocess.run(
            [
                sys.executable,
                "src/csv_brief.py",
                "assets/synthetic_sales.csv",
                "--baseline",
                "assets/synthetic_sales_baseline.csv",
                "--output-dir",
                directory,
                "--title",
                "Synthetic Sales Data Brief",
                "--key",
                "order_id",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        try:
            profile = json.loads((Path(directory) / "profile.json").read_text(encoding="utf-8"))
            drift = json.loads((Path(directory) / "drift.json").read_text(encoding="utf-8"))
            html_exists = (Path(directory) / "brief.html").is_file()
            drift_codes = {item["code"] for item in drift["drifts"]}
            passed = (
                process.returncode == 2
                and html_exists
                and profile["row_count"] == 7
                and profile["column_count"] == 6
                and profile["missing_cells"] == 1
                and profile["exact_duplicate_rows"] == 1
                and not profile["join_guard"]["one_to_one_ready"]
                and profile["join_guard"]["duplicate_key_groups"] == 1
                and drift["status"] == "review"
                and drift["key_comparison"]["uniqueness_regression"]
                and "missing_rate_increased" in drift_codes
            )
            detail = (
                f'{profile["row_count"]} rows, {profile["column_count"]} columns, '
                f'{profile["missing_cells"]} missing cell, '
                f'{profile["exact_duplicate_rows"]} exact duplicate row; '
                f'JoinGuard found {profile["join_guard"]["duplicate_key_groups"]} duplicate key group; '
                "Drift Guard caught missing-rate and key regressions"
            )
        except (OSError, KeyError, json.JSONDecodeError) as error:
            passed, detail = False, str(error)

    print(f'[{"PASS" if passed else "FAIL"}] CSV Brief demo: {detail}')
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
