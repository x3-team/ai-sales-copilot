import os
import tempfile
import unittest


class MemoryStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "mem.db")
        os.environ.pop("DATABASE_URL", None)
        os.environ["COPILOT_MEMORY_DB_PATH"] = self.db_path
        import importlib
        import memory_store

        importlib.reload(memory_store)
        self.ms = memory_store

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("COPILOT_MEMORY_DB_PATH", None)

    def test_upsert_and_read_company_people_contacts(self):
        self.ms.ensure_schema()
        self.ms.upsert_company("7707083893", name="ПАО СБЕРБАНК", website="https://sber.ru")
        pid = self.ms.upsert_person(
            company_inn="7707083893",
            stakeholder="ceo",
            fio="Иван Иванов",
            role="Генеральный директор",
            profile_url="https://tenchat.ru/u/test",
            platform="tenchat",
        )
        self.ms.upsert_contact(pid, "email", "ceo@example.com", source_url="https://tenchat.ru/u/test")
        self.ms.upsert_contact(pid, "phone", "", source_url=None)

        company = self.ms.get_company("7707083893")
        self.assertEqual(company["name"], "ПАО СБЕРБАНК")
        people = self.ms.list_people("7707083893")
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0]["fio"], "Иван Иванов")
        contacts = self.ms.list_contacts(pid)
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["type"], "email")

        pm = self.ms.get_power_map("7707083893")
        self.assertIsNotNone(pm["ceo"])
        self.assertIsNone(pm["lpr"])

    def test_inbound_upsert_and_enrich_reuse(self):
        self.ms.ensure_schema()
        candidate = {
            "name": "Пётр Петров",
            "role": "IT директор",
            "company": "ООО Тест",
            "profile_url": "https://tenchat.ru/u/petr",
            "profile_platform": "tenchat",
            "stakeholder_hint": "lvr",
            "email": "petr@test.ru",
            "phone": None,
            "telegram": None,
            "source": "TenChat",
            "confidence_base": 90,
            "profile_resolved": True,
            "source_type": "tenchat_verified",
        }
        self.ms.upsert_from_inbound("1234567890", "ООО Тест", [candidate])
        rebuilt = self.ms.rebuild_enrich_from_memory("1234567890")
        self.assertIsNotNone(rebuilt)
        lprs = rebuilt["lpr_matrix"]["lprs"]
        self.assertTrue(any(p.get("name") == "Пётр Петров" for p in lprs))
        entry = lprs[0]
        self.assertEqual(entry["contacts"]["email"], "petr@test.ru")
        self.assertIsNone(entry["contacts"]["phone"])

    def test_merge_prefers_stored_complete(self):
        stored = [{
            "name": "Stored CEO",
            "role": "CEO",
            "profile_url": "https://tenchat.ru/stored",
            "profile_resolved": True,
            "contacts": {"email": "stored@test.ru", "phone": None, "telegram": None},
        }]
        fresh = [{
            "name": "Fresh CEO",
            "role": "CEO",
            "profile_url": "",
            "profile_resolved": False,
            "contacts": {"email": None, "phone": None, "telegram": None},
        }]
        merged = self.ms.merge_lpr_lists(stored, fresh)
        self.assertEqual(merged[0]["name"], "Stored CEO")
        self.assertEqual(merged[0]["contacts"]["email"], "stored@test.ru")

    def test_slots_needing_search(self):
        complete = [{
            "name": "CEO Name",
            "profile_resolved": True,
            "profile_url": "https://tenchat.ru/x",
            "contacts": {},
        }]
        self.assertEqual(self.ms.slots_needing_search(complete), ["lpr", "lvr", "hr"])


    def test_status_persisted_and_not_downgraded(self):
        self.ms.ensure_schema()
        payload = {
            "dadata_legal_profile": {"inn": "4217184336", "name": "ООО «СУПЕР СИЛА»", "ceo": "Мальцев"},
            "lpr_matrix": {
                "lprs": [{
                    "name": "Мальцев",
                    "profile_url": "https://tenchat.ru/1197746487641",
                    "profile_resolved": True,
                    "contacts": {"email": None, "phone": None, "telegram": None},
                }]
            },
            "hh_recruitment_profile": {"vacancies": [{"title": "1С"}]},
            "sales_ai_insights": {"insights": []},
        }
        card = self.ms.sync_status_from_payload("4217184336", payload)
        self.assertEqual(card["status"], "named")
        self.ms.upsert_company("4217184336", card_status="signal")
        row = self.ms.get_company("4217184336")
        self.assertEqual(row["card_status"], "named")


if __name__ == "__main__":
    unittest.main()
