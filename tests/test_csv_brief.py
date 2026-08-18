from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "src/csv_brief.py"
    spec = importlib.util.spec_from_file_location("csv_brief", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class CSVBriefTests(unittest.TestCase):
    def test_synthetic_profile_has_expected_quality_flags(self):
        module = load_module()
        profile = module.profile_csv(ROOT / "assets/synthetic_sales.csv")
        self.assertEqual(profile["row_count"], 7)
        self.assertEqual(profile["column_count"], 6)
        self.assertEqual(profile["missing_cells"], 1)
        self.assertEqual(profile["exact_duplicate_rows"], 1)
        self.assertEqual(profile["baseline_status"], "review")

    def test_numeric_and_date_inference(self):
        module = load_module()
        profile = module.profile_csv(ROOT / "assets/synthetic_sales.csv")
        columns = {column["name"]: column for column in profile["columns"]}
        self.assertEqual(columns["revenue"]["type"], "number")
        self.assertEqual(columns["revenue"]["minimum"], "500")
        self.assertEqual(columns["revenue"]["maximum"], "2200")
        self.assertEqual(columns["order_date"]["type"], "date")
        self.assertEqual(columns["order_date"]["minimum"], "2026-07-01")
        self.assertEqual(columns["order_date"]["maximum"], "2026-07-06")

    def test_write_brief_creates_json_and_escaped_html(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            result = module.write_brief(
                ROOT / "assets/synthetic_sales.csv",
                Path(directory),
                "Quarterly <Draft>",
            )
            self.assertTrue(result["profile_path"].is_file())
            rendered = result["brief_path"].read_text(encoding="utf-8")
            self.assertIn("Quarterly &lt;Draft&gt;", rendered)
            self.assertNotIn("Quarterly <Draft>", rendered)

    def test_hide_top_values_suppresses_text_samples(self):
        module = load_module()
        profile = module.profile_csv(
            ROOT / "assets/synthetic_sales.csv",
            include_top_values=False,
        )
        self.assertTrue(all("top_values" not in column for column in profile["columns"]))

    def test_join_guard_flags_duplicate_declared_key(self):
        module = load_module()
        profile = module.profile_csv(
            ROOT / "assets/synthetic_sales.csv",
            key_columns=["order_id"],
        )
        guard = profile["join_guard"]
        self.assertFalse(guard["one_to_one_ready"])
        self.assertEqual(guard["duplicate_key_groups"], 1)
        self.assertEqual(guard["duplicate_key_excess_rows"], 1)
        self.assertEqual(guard["groups"][0]["key"], ["O-1001"])
        self.assertEqual(guard["groups"][0]["source_rows"], [2, 7])

    def test_join_guard_handles_composite_blank_and_hidden_keys(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dimension.csv"
            source.write_text(
                "account,region,label\n"
                "A1,North,First\n"
                "A1,North,Duplicate\n"
                "A2,,Missing region\n",
                encoding="utf-8",
            )
            profile = module.profile_csv(
                source,
                key_columns=["account", "region"],
                include_key_values=False,
            )
            guard = profile["join_guard"]
            self.assertEqual(guard["blank_key_rows"], [4])
            self.assertEqual(guard["duplicate_key_rows"], [2, 3])
            self.assertNotIn("key", guard["groups"][0])
            with self.assertRaisesRegex(ValueError, "Unknown join-key"):
                module.profile_csv(source, key_columns=["missing_column"])

    def test_rejects_ragged_rows_and_blank_headers(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            ragged = Path(directory) / "ragged.csv"
            ragged.write_text("id,value\n1,ok,extra\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "more fields"):
                module.profile_csv(ragged)

            blank_header = Path(directory) / "blank.csv"
            blank_header.write_text("id,\n1,ok\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not be blank"):
                module.profile_csv(blank_header)

    def test_drift_guard_detects_quality_and_key_regression(self):
        module = load_module()
        baseline = module.profile_csv(
            ROOT / "assets/synthetic_sales_baseline.csv",
            key_columns=["order_id"],
        )
        current = module.profile_csv(
            ROOT / "assets/synthetic_sales.csv",
            key_columns=["order_id"],
        )
        drift = module.compare_profiles(baseline, current)
        codes = {item["code"] for item in drift["drifts"]}
        self.assertEqual(drift["status"], "review")
        self.assertEqual(drift["row_count"]["delta"], 1)
        self.assertIn("row_count_changed", codes)
        self.assertIn("missing_rate_increased", codes)
        self.assertIn("distinct_changed", codes)
        self.assertIn("key_uniqueness_regression", codes)
        self.assertTrue(drift["key_comparison"]["uniqueness_regression"])

        unchanged = module.compare_profiles(baseline, baseline)
        self.assertEqual(unchanged["status"], "pass")
        self.assertFalse(unchanged["has_drift"])

    def test_drift_guard_detects_schema_and_type_changes(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            baseline_path = Path(directory) / "baseline.csv"
            current_path = Path(directory) / "current.csv"
            baseline_path.write_text(
                "id,amount,legacy\n1,10,A\n2,20,B\n",
                encoding="utf-8",
            )
            current_path.write_text(
                "id,amount,new_col\n1,unknown,X\n2,30,Y\n",
                encoding="utf-8",
            )
            baseline = module.profile_csv(baseline_path, key_columns=["id"])
            current = module.profile_csv(current_path, key_columns=["id"])
            drift = module.compare_profiles(baseline, current)
            self.assertEqual(drift["schema"]["added_columns"], ["new_col"])
            self.assertEqual(drift["schema"]["removed_columns"], ["legacy"])
            self.assertEqual(
                drift["schema"]["type_changes"],
                [{"column": "amount", "baseline": "number", "current": "text"}],
            )
            self.assertEqual(drift["status"], "review")

    def test_write_brief_with_baseline_creates_drift_outputs(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            result = module.write_brief(
                ROOT / "assets/synthetic_sales.csv",
                Path(directory),
                "Drift Review",
                key_columns=["order_id"],
                baseline_path=ROOT / "assets/synthetic_sales_baseline.csv",
            )
            self.assertTrue(result["drift_path"].is_file())
            persisted = json.loads(result["drift_path"].read_text(encoding="utf-8"))
            self.assertEqual(persisted["status"], "review")
            rendered = result["brief_path"].read_text(encoding="utf-8")
            self.assertIn("Schema / Quality Drift Guard", rendered)
            self.assertIn("key_uniqueness_regression", rendered)

    def test_cli_fails_closed_on_review_level_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "src/csv_brief.py"),
                    str(ROOT / "assets/synthetic_sales.csv"),
                    "--baseline",
                    str(ROOT / "assets/synthetic_sales_baseline.csv"),
                    "--output-dir",
                    directory,
                    "--key",
                    "order_id",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(process.returncode, 2)
            summary = json.loads(process.stdout)
            self.assertEqual(summary["drift_status"], "review")
            self.assertTrue((Path(directory) / "drift.json").is_file())

    def test_cli_fails_closed_when_baseline_is_malformed(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "bad-baseline.csv"
            output = Path(directory) / "output"
            baseline.write_text("id,value\n1,ok,extra\n", encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "src/csv_brief.py"),
                    str(ROOT / "assets/synthetic_sales.csv"),
                    "--baseline",
                    str(baseline),
                    "--output-dir",
                    str(output),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse((output / "drift.json").exists())


if __name__ == "__main__":
    unittest.main()
