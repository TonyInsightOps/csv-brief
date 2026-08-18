from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
