"""Tenderland scan: honest statuses, skip items without customer INN."""
import os
import unittest
from unittest.mock import patch

import tenderland


class TenderlandNormalizeTest(unittest.TestCase):
    def test_skip_without_inn(self):
        self.assertIsNone(tenderland.normalize_item({"tender_name": "Поставка 1С"}))
        self.assertIsNone(tenderland.normalize_item({"tender_customerInn": "123"}))

    def test_keep_real_inn(self):
        item = tenderland.normalize_item({
            "tender_customerInn": "7604031290",
            "tender_customerName": "Ярославский областной суд",
            "tender_name": "Шкафы металлические",
            "tender_regNumber": "0171100002226000023",
            "tender_beginPrice": "180000",
        })
        self.assertEqual(item["inn"], "7604031290")
        self.assertIn("zakupki.gov.ru", item["url"])
        self.assertEqual(item["price_text"], "180000")


class TenderlandScanTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("TENDERLAND_API_KEY", None)

    def test_missing_key(self):
        os.environ.pop("TENDERLAND_API_KEY", None)
        result = tenderland.scan_for_offer("1С")
        self.assertEqual(result["scan_status"], "tenderland_missing")
        self.assertEqual(result["items"], [])

    def test_unreachable(self):
        os.environ["TENDERLAND_API_KEY"] = "test-key-not-real"
        with patch.object(tenderland, "search_tenders", return_value=([], "http_403")):
            result = tenderland.scan_for_offer("1С")
        self.assertEqual(result["scan_status"], "tenderland_unreachable")
        self.assertEqual(result["items"], [])

    def test_empty(self):
        os.environ["TENDERLAND_API_KEY"] = "test-key-not-real"
        with patch.object(tenderland, "search_tenders", return_value=([], None)):
            result = tenderland.scan_for_offer("1С")
        self.assertEqual(result["scan_status"], "tenderland_empty")

    def test_no_inn_matches(self):
        os.environ["TENDERLAND_API_KEY"] = "test-key-not-real"
        with patch.object(
            tenderland,
            "search_tenders",
            return_value=([{"tender_name": "Поставка без ИНН"}], None),
        ):
            result = tenderland.scan_for_offer("1С")
        self.assertEqual(result["scan_status"], "no_inn_matches")
        self.assertEqual(result["items"], [])
        self.assertEqual(result["raw_count"], 1)

    def test_ok_skips_bad_inn_and_duplicates(self):
        os.environ["TENDERLAND_API_KEY"] = "test-key-not-real"
        raw = [
            {"tender_customerInn": "xx", "tender_name": "без инн"},
            {
                "tender_customerInn": "3903009923",
                "tender_customerName": "ГП КО Водоканал",
                "tender_name": "1С КОРП",
                "tender_regNumber": "32616034890",
            },
            {
                "tender_customerInn": "3903009923",
                "tender_name": "дубль того же заказчика",
            },
        ]
        with patch.object(tenderland, "search_tenders", return_value=(raw, None)):
            result = tenderland.scan_for_offer("1С", limit=5)
        self.assertEqual(result["scan_status"], "ok")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["inn"], "3903009923")


if __name__ == "__main__":
    unittest.main()
