"""Demand card from memory — works without DaData."""
import os
import tempfile
import unittest


class CompanyCardTest(unittest.TestCase):
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

    def test_habr_card_without_dadata(self):
        from scripts.seed_habr_buyers import apply_habr_buyers_seed
        from company_card import build_company_card

        apply_habr_buyers_seed(self.ms)
        card = build_company_card("7706729736", {"product_name": "1С", "value_proposition": "Закрываем ЗУП без найма"})
        self.assertIsNotNone(card)
        self.assertEqual(card["demand_pack"], "hiring")
        self.assertIn("habr.com", card["primary_trigger"]["url"])
        self.assertIn("ТВЭЛ", card.get("note") or "")
        self.assertTrue(card["send_yourself"])
        self.assertFalse(card["dadata_available"])
        self.assertIn("1С", card["pitch"])

    def test_tender_card_pack(self):
        from scripts.seed_tender_buyers import apply_tender_buyers_seed
        from company_card import build_company_card

        apply_tender_buyers_seed(self.ms)
        card = build_company_card("7604031290", {"product_name": "металлическая мебель"})
        self.assertEqual(card["demand_pack"], "procurement")
        self.assertIn("zakupki.gov.ru", card["primary_trigger"]["url"])
        self.assertEqual(card["starting_person"], None)
        self.assertIn("Закупка", " ".join(card["triggers"]))


class TenderSeedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("DATABASE_URL", None)
        os.environ["COPILOT_MEMORY_DB_PATH"] = os.path.join(self.tmp.name, "tender.db")
        import importlib
        import memory_store

        importlib.reload(memory_store)
        self.ms = memory_store

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("COPILOT_MEMORY_DB_PATH", None)

    def test_five_tender_buyers_in_work(self):
        from scripts.seed_tender_buyers import apply_tender_buyers_seed, tender_buyer_records
        import company_status as cs
        from live_companies import TENDER_SEED_INNS

        self.assertEqual(len(tender_buyer_records()), 5)
        summary = apply_tender_buyers_seed(self.ms)
        self.assertEqual(summary["seeded"], 5)
        inns = {c["inn"] for c in self.ms.list_companies(queue=cs.QUEUE_IN_WORK)}
        for inn in TENDER_SEED_INNS:
            self.assertIn(inn, inns)
        for rec in summary["companies"]:
            self.assertEqual(rec["card_status"], cs.STATUS_SIGNAL)
            self.assertEqual(rec["people_count"], 0)


if __name__ == "__main__":
    unittest.main()
