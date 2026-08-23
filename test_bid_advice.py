"""Go / no-go from offer + tender facts. Not a win forecast."""
import os
import tempfile
import unittest

from bid_advice import VERDICT_GO, VERDICT_NO, VERDICT_REVIEW, advise_bid, parse_money


class ParseMoneyTest(unittest.TestCase):
    def test_spaces_and_nbsp(self):
        self.assertEqual(parse_money("НМЦК 1 250 000 ₽"), 1250000.0)
        self.assertEqual(parse_money("цена 87\xa0500,50"), 87500.5)

    def test_empty(self):
        self.assertIsNone(parse_money(""))
        self.assertIsNone(parse_money("без суммы"))


class AdviseBidTest(unittest.TestCase):
    def test_go_when_offer_matches_and_price_in_band(self):
        advice = advise_bid(
            {
                "product_name": "1С внедрение",
                "product_description": "лицензии 1С:Предприятие",
                "min_deal_amount": 100_000,
                "max_deal_amount": 5_000_000,
            },
            title="Поставка лицензий 1С:Предприятие 8.3 КОРП",
            note="НМЦК 480 000",
        )
        self.assertEqual(advice["verdict"], VERDICT_GO)
        self.assertIn("1с", advice["matched_terms"])
        self.assertEqual(advice["price"], 480000.0)
        self.assertTrue(any("не прогноз" in r.lower() for r in advice["reasons"]))

    def test_no_go_when_subject_mismatch(self):
        advice = advise_bid(
            {"product_name": "1С внедрение", "product_description": "ЗУП ERP"},
            title="Шкафы металлические для архива",
            note="44-ФЗ мебель",
        )
        self.assertEqual(advice["verdict"], VERDICT_NO)
        self.assertEqual(advice["matched_terms"], [])

    def test_no_go_when_below_min_nmck(self):
        advice = advise_bid(
            {
                "product_name": "металлическая мебель",
                "min_deal_amount": 2_000_000,
            },
            title="Шкафы металлические",
            note="НМЦК 180 000",
        )
        self.assertEqual(advice["verdict"], VERDICT_NO)
        self.assertTrue(any("ниже" in r for r in advice["reasons"]))

    def test_review_when_above_max_or_weak_match(self):
        weak = advise_bid(
            {"product_name": "металлическая мебель"},
            title="Шкафы металлические",
            note="",
        )
        self.assertEqual(weak["verdict"], VERDICT_REVIEW)
        self.assertIn("металлическая", weak["matched_terms"])

        high = advise_bid(
            {
                "product_name": "1С внедрение лицензии",
                "max_deal_amount": 200_000,
            },
            title="Лицензия 1С:Предприятие",
            note="НМЦК 900 000",
        )
        self.assertEqual(high["verdict"], VERDICT_REVIEW)
        self.assertTrue(any("выше" in r for r in high["reasons"]))

    def test_review_without_tender_text(self):
        advice = advise_bid({"product_name": "1С"}, title="", note="")
        self.assertEqual(advice["verdict"], VERDICT_REVIEW)


class CompanyCardBidAdviceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("DADATA_API_KEY", None)
        os.environ["COPILOT_MEMORY_DB_PATH"] = os.path.join(self.tmp.name, "card.db")
        import importlib
        import memory_store

        importlib.reload(memory_store)
        self.ms = memory_store

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("COPILOT_MEMORY_DB_PATH", None)

    def test_court_tender_has_bid_advice(self):
        from scripts.seed_tender_buyers import apply_tender_buyers_seed
        from company_card import build_company_card

        apply_tender_buyers_seed(self.ms)
        card = build_company_card(
            "7604031290",
            {"product_name": "металлическая мебель", "product_description": "шкафы"},
        )
        self.assertEqual(card["demand_pack"], "procurement")
        self.assertIsNotNone(card["bid_advice"])
        self.assertEqual(card["bid_advice"]["verdict"], VERDICT_GO)
        self.assertIn("шкафы", card["bid_advice"]["matched_terms"])

    def test_hiring_card_has_no_bid_advice(self):
        from scripts.seed_habr_buyers import apply_habr_buyers_seed
        from company_card import build_company_card

        apply_habr_buyers_seed(self.ms)
        card = build_company_card("7706729736", {"product_name": "1С"})
        self.assertEqual(card["demand_pack"], "hiring")
        self.assertIsNone(card["bid_advice"])


if __name__ == "__main__":
    unittest.main()
