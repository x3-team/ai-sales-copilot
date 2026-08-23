"""Merged procurement scan: Gosplan + Tenderland."""
import unittest
from unittest.mock import patch

import procurement_scan


class ProcurementScanMergeTest(unittest.TestCase):
    def test_merge_prefers_first_source(self):
        gp = {
            "scan_status": "ok",
            "scan_message": "Gosplan ok",
            "items": [{"inn": "7604031290", "name": "A", "title": "t1"}],
            "raw_count": 1,
        }
        tl = {
            "scan_status": "tenderland_missing",
            "scan_message": "no key",
            "items": [],
            "raw_count": 0,
        }
        with patch("gosplan.scan_for_offer", return_value=gp), patch(
            "tenderland.scan_for_offer", return_value=tl
        ):
            result = procurement_scan.scan_for_offer("мебель", limit=5)
        self.assertEqual(result["scan_status"], "ok")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["sources"]["gosplan"], "ok")

    def test_deduplicate_by_inn(self):
        gp = {
            "scan_status": "ok",
            "scan_message": "gp",
            "items": [{"inn": "7604031290", "name": "A", "title": "t1"}],
            "raw_count": 1,
        }
        tl = {
            "scan_status": "ok",
            "scan_message": "tl",
            "items": [
                {"inn": "7604031290", "name": "A dup", "title": "t2"},
                {"inn": "3903009923", "name": "B", "title": "t3"},
            ],
            "raw_count": 2,
        }
        with patch("gosplan.scan_for_offer", return_value=gp), patch(
            "tenderland.scan_for_offer", return_value=tl
        ):
            result = procurement_scan.scan_for_offer("мебель", limit=5)
        inns = [x["inn"] for x in result["items"]]
        self.assertEqual(inns, ["7604031290", "3903009923"])

    def test_both_missing(self):
        gp = {"scan_status": "gosplan_empty", "scan_message": "empty", "items": [], "raw_count": 0}
        tl = {"scan_status": "tenderland_missing", "scan_message": "missing", "items": [], "raw_count": 0}
        with patch("gosplan.scan_for_offer", return_value=gp), patch(
            "tenderland.scan_for_offer", return_value=tl
        ):
            result = procurement_scan.scan_for_offer("мебель", limit=5)
        self.assertIn(result["scan_status"], ("procurement_empty", "procurement_missing", "gosplan_empty"))


if __name__ == "__main__":
    unittest.main()
