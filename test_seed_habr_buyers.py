"""Verify Habr Career buyer seed into memory store."""
import os
import tempfile
import unittest

import company_status as cs
from live_companies import HABR_BUYER_SEED_INNS, INTEGRATOR_INNS, is_integrator


class SeedHabrBuyersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("DATABASE_URL", None)
        os.environ["COPILOT_MEMORY_DB_PATH"] = os.path.join(self.tmp.name, "habr.db")
        import importlib
        import memory_store

        importlib.reload(memory_store)
        self.ms = memory_store

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("COPILOT_MEMORY_DB_PATH", None)

    def test_integrator_blocklist_includes_jetlin(self):
        self.assertTrue(is_integrator("5835090155"))
        self.assertIn("5835090155", INTEGRATOR_INNS)
        self.assertIn("7811090505", INTEGRATOR_INNS)

    def test_seed_twelve_habr_buyers_signal_in_work(self):
        from scripts.seed_habr_buyers import apply_habr_buyers_seed, habr_buyer_records

        self.assertEqual(len(habr_buyer_records()), 12)
        summary = apply_habr_buyers_seed(self.ms)
        self.assertEqual(summary["seeded"], 12)
        self.assertEqual(summary["skipped"], [])

        in_work = self.ms.list_companies(queue=cs.QUEUE_IN_WORK)
        seeded_inns = {c["inn"] for c in in_work}
        for inn in HABR_BUYER_SEED_INNS:
            self.assertIn(inn, seeded_inns, msg=f"missing {inn} in in_work queue")

        for c in summary["companies"]:
            self.assertEqual(c["card_status"], cs.STATUS_SIGNAL)
            self.assertEqual(c["queue"], cs.QUEUE_IN_WORK)
            self.assertEqual(c["people_count"], 0)
            triggers = " ".join(c.get("triggers") or [])
            self.assertIn("Habr:", triggers)
            self.assertIn("career.habr.com/vacancies/", triggers)

    def test_no_contacts_or_profile_url(self):
        from scripts.seed_habr_buyers import apply_habr_buyers_seed

        apply_habr_buyers_seed(self.ms)
        for inn in HABR_BUYER_SEED_INNS:
            people = self.ms.list_people(inn)
            self.assertEqual(people, [], msg=f"unexpected people for {inn}")
            row = self.ms.get_company(inn)
            self.assertNotEqual(row.get("card_status"), cs.STATUS_REACHABLE)

    def test_greenatom_and_yabloko_notes(self):
        from scripts.seed_habr_buyers import apply_habr_buyers_seed

        apply_habr_buyers_seed(self.ms)
        green = self.ms.get_company("7706729736")
        yabloko = self.ms.get_company("6670381056")
        self.assertIn("ТВЭЛ-СТРОЙ", (green.get("enrich_payload") or {}).get("seed_note", ""))
        self.assertIn("розничный", (yabloko.get("enrich_payload") or {}).get("seed_note", ""))

    def test_idempotent_reseed(self):
        from scripts.seed_habr_buyers import apply_habr_buyers_seed

        apply_habr_buyers_seed(self.ms)
        first = self.ms.list_companies(queue=cs.QUEUE_IN_WORK)
        apply_habr_buyers_seed(self.ms)
        second = self.ms.list_companies(queue=cs.QUEUE_IN_WORK)
        self.assertGreaterEqual(len(second), len(first))


if __name__ == "__main__":
    unittest.main()
