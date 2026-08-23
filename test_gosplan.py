"""Gosplan EIS REST client tests."""
import os
import unittest
from unittest.mock import patch

import gosplan


FZ44_SAMPLE = {
    "customers": ["7604031290"],
    "object_info": "Шкафы металлические",
    "purchase_number": "0171100002226000023",
    "max_price": 180000.0,
    "responsible": "7604031290",
}

FZ223_SAMPLE = {
    "customer": "3903009923",
    "object_info": "Поставка 1С",
    "purchase_number": "32616034890",
    "max_price": 480000.0,
}


class GosplanNormalizeTest(unittest.TestCase):
    def test_fz44_item(self):
        item = gosplan.normalize_item(FZ44_SAMPLE, law="fz44", org_cache={})
        self.assertEqual(item["inn"], "7604031290")
        self.assertIn("zakupki.gov.ru", item["url"])
        self.assertIn("ea20", item["url"])
        self.assertEqual(item["price_text"], "180000.0")

    def test_fz223_item(self):
        item = gosplan.normalize_item(FZ223_SAMPLE, law="fz223", org_cache={})
        self.assertEqual(item["inn"], "3903009923")
        self.assertIn("notice223", item["url"])

    def test_skip_without_inn(self):
        self.assertIsNone(gosplan.normalize_item({"object_info": "x"}, law="fz44"))


class GosplanSearchQueryTest(unittest.TestCase):
    def test_short_1c_expanded(self):
        self.assertEqual(gosplan._search_query("1С"), "1С предприятие")

    def test_min_three_chars(self):
        self.assertEqual(gosplan._search_query("металлическая мебель"), "металлическая мебель")


class GosplanScanTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("GOSPLAN_API_KEY", None)
        os.environ.pop("GOSPLAN_API_BASE", None)

    def test_scan_ok_mock(self):
        raw44 = dict(FZ44_SAMPLE)
        raw44["_law"] = "fz44"
        with patch.object(gosplan, "search_purchases", return_value=([raw44], None)):
            result = gosplan.scan_for_offer("металлическая мебель", limit=3)
        self.assertEqual(result["scan_status"], "ok")
        self.assertEqual(result["items"][0]["inn"], "7604031290")

    def test_unreachable(self):
        with patch.object(gosplan, "search_purchases", return_value=([], "http_429")):
            result = gosplan.scan_for_offer("поставка", limit=3)
        self.assertEqual(result["scan_status"], "gosplan_unreachable")

    def test_no_inn_matches(self):
        with patch.object(
            gosplan,
            "search_purchases",
            return_value=([{"object_info": "x", "_law": "fz44"}], None),
        ):
            result = gosplan.scan_for_offer("поставка", limit=3)
        self.assertEqual(result["scan_status"], "no_inn_matches")

    def test_session_test_mode_without_key(self):
        os.environ.pop("GOSPLAN_API_KEY", None)
        os.environ["GOSPLAN_API_BASE"] = gosplan.TEST_BASE
        st = gosplan.session_status()
        self.assertTrue(st["available"])
        self.assertEqual(st["mode"], "test")
        self.assertEqual(st["base_url"], gosplan.TEST_BASE)

    def test_scan_rate_limit_message(self):
        with patch.object(gosplan, "search_purchases", return_value=([], "http_429")):
            result = gosplan.scan_for_offer("поставка", limit=3)
        self.assertEqual(result["scan_status"], "gosplan_unreachable")
        self.assertIn("429", result["scan_message"])

    def test_probe_rate_limited(self):
        os.environ.pop("GOSPLAN_API_KEY", None)
        os.environ["GOSPLAN_API_BASE"] = gosplan.TEST_BASE
        with patch.object(gosplan, "_get_json", return_value=(None, "http_429")):
            probe = gosplan.probe_api()
        self.assertTrue(probe["available"])
        self.assertTrue(probe.get("rate_limited"))
        self.assertEqual(probe["base_url"], gosplan.TEST_BASE)


if __name__ == "__main__":
    unittest.main()
