"""Verify live company seed into memory store."""
import os
import tempfile
import unittest


class SeedLiveCompaniesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("DATABASE_URL", None)
        os.environ["COPILOT_MEMORY_DB_PATH"] = os.path.join(self.tmp.name, "seed.db")
        import importlib
        import memory_store
        import company_status

        importlib.reload(company_status)
        importlib.reload(memory_store)
        self.ms = memory_store
        self.cs = company_status

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("COPILOT_MEMORY_DB_PATH", None)

    def test_seed_all_five_in_work_not_reachable(self):
        from scripts.seed_live_companies import apply_live_seed

        summary = apply_live_seed(self.ms)
        self.assertEqual(summary["seeded"], 5)
        for c in summary["companies"]:
            self.assertNotEqual(c["card_status"], "reachable")
            self.assertEqual(c["queue"], "in_work")

        sila = self.ms.get_company("4217184336")
        people = self.ms.list_people("4217184336")
        self.assertEqual(sila["card_status"], "named")
        ceo = people[0]
        self.assertEqual(ceo["fio"], "Мальцев Максим Робертович")
        self.assertIsNone(ceo.get("profile_url"))
        self.assertEqual(ceo["meta"].get("registry_url"), "https://www.rusprofile.ru/id/11095765")
        phones = [x for x in ceo["contacts"] if x["type"] == "phone"]
        self.assertEqual(len(phones), 2)
        self.assertTrue(all("checko.ru" in (p.get("source_url") or "") for p in phones))

        rus = self.ms.list_people("9103100540")[0]
        self.assertIsNone(rus.get("profile_url"))
        emails = [x for x in rus["contacts"] if x["type"] == "email"]
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]["value"], "kanc@ooorus.net")
        self.assertIn("checko.ru", emails[0]["source_url"])

        im = self.ms.get_company("7801711200")
        self.assertEqual(im["card_status"], "named")
        self.assertIn("HH:", " ".join(im.get("triggers") or []))


if __name__ == "__main__":
    unittest.main()
