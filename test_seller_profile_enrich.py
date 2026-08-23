"""Seller profile persistence + DaData CEO on procurement cards."""
import os
import tempfile
import unittest
from unittest.mock import patch


class SellerProfilePersistenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("DATABASE_URL", None)
        os.environ["COPILOT_MEMORY_DB_PATH"] = os.path.join(self.tmp.name, "profile.db")
        import importlib
        import memory_store

        importlib.reload(memory_store)
        self.ms = memory_store

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("COPILOT_MEMORY_DB_PATH", None)

    def test_save_and_load_offer(self):
        payload = {
            "product_name": "металлическая мебель",
            "product_description": "шкафы для архивов",
            "target_icp": "госзаказчики",
            "value_proposition": "срок 14 дней",
            "min_deal_amount": 500000,
            "max_deal_amount": 5000000,
        }
        self.ms.save_seller_profile(payload)
        loaded = self.ms.get_seller_profile()
        self.assertEqual(loaded["product_name"], payload["product_name"])
        self.assertEqual(loaded["min_deal_amount"], 500000)


class CompanyEnrichTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("DATABASE_URL", None)
        os.environ["DADATA_API_KEY"] = "test-token"
        os.environ["COPILOT_MEMORY_DB_PATH"] = os.path.join(self.tmp.name, "enrich.db")
        import importlib
        import memory_store

        importlib.reload(memory_store)
        self.ms = memory_store

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("COPILOT_MEMORY_DB_PATH", None)
        os.environ.pop("DADATA_API_KEY", None)

    def test_ensure_ceo_from_dadata_on_tender(self):
        from scripts.seed_tender_buyers import apply_tender_buyers_seed
        from company_enrich import ensure_ceo_from_dadata
        from company_card import build_company_card

        apply_tender_buyers_seed(self.ms)
        party = {
            "inn": "7604031290",
            "name": 'Ярославский областной суд',
            "ceo": "Иванов Иван Иванович",
            "ceo_post": "Председатель",
            "active": True,
            "reason": "ok",
        }
        with patch("dadata_company.find_party_by_inn", return_value=party):
            person = ensure_ceo_from_dadata("7604031290")
        self.assertIsNotNone(person)
        self.assertEqual(person["name"], "Иванов Иван Иванович")
        people = self.ms.list_people("7604031290")
        self.assertEqual(people[0]["fio"], "Иванов Иван Иванович")

        card = build_company_card("7604031290", {"product_name": "металлическая мебель"})
        self.assertEqual(card["starting_person"]["name"], "Иванов Иван Иванович")
        self.assertEqual(card["starting_person"]["source"], "ЕГРЮЛ / DaData")

    def test_skip_when_ceo_already_present(self):
        from company_enrich import ensure_ceo_from_dadata

        self.ms.upsert_company("7707083893", name="Сбер")
        self.ms.upsert_person(
            company_inn="7707083893",
            stakeholder="ceo",
            fio="Греф Андрей",
            role="Президент",
            sources=["seed"],
        )
        with patch("dadata_company.find_party_by_inn") as mock_find:
            result = ensure_ceo_from_dadata("7707083893")
        mock_find.assert_not_called()
        self.assertIsNone(result)

    def test_honest_when_dadata_missing(self):
        from scripts.seed_tender_buyers import apply_tender_buyers_seed
        from company_enrich import ensure_ceo_from_dadata

        os.environ.pop("DADATA_API_KEY", None)
        apply_tender_buyers_seed(self.ms)
        with patch("dadata_company.find_party_by_inn") as mock_find:
            result = ensure_ceo_from_dadata("7604031290")
        mock_find.assert_not_called()
        self.assertIsNone(result)


class FindPartyByInnTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("DADATA_API_KEY", None)

    def test_bad_inn(self):
        from dadata_company import find_party_by_inn

        out = find_party_by_inn("123")
        self.assertEqual(out["reason"], "bad_inn")

    def test_missing_key(self):
        from dadata_company import find_party_by_inn

        os.environ.pop("DADATA_API_KEY", None)
        out = find_party_by_inn("7604031290")
        self.assertEqual(out["reason"], "dadata_missing")


if __name__ == "__main__":
    unittest.main()
