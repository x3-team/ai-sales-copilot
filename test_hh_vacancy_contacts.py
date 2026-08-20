"""Tests: HH vacancy is trigger-only — not a reachable contact source."""
import os
import tempfile
import unittest

import company_status as cs
from identity_layer import HHVacancyParser


HIDDEN_CONTACT_HTML = """
<html><body>
  <div data-qa="vacancy-contacts">
    <p>Контактная информация скрыта работодателем</p>
  </div>
  <script type="application/ld+json">
  {"@type":"JobPosting","title":"Программист 1С","description":"Связаться: hr@example.com +7 999 111-22-33"}
  </script>
</body></html>
"""

OPEN_CONTACT_HTML = """
<html><body>
  <div data-qa="vacancy-contacts">
    <span data-qa="vacancy-contacts-name">Иванова Анна Сергеевна</span>
    <a data-qa="vacancy-contacts-email" href="mailto:anna.ivanova@client.ru">anna.ivanova@client.ru</a>
    <span data-qa="vacancy-contacts-phone">+7 (495) 123-45-67</span>
  </div>
</body></html>
"""


class HHVacancyContactsTest(unittest.TestCase):
    def test_hidden_contact_fields_empty(self):
        parsed = HHVacancyParser.parse_open_contacts(HIDDEN_CONTACT_HTML)
        self.assertEqual(parsed.get("contacts_hidden"), "true")
        self.assertEqual(parsed.get("contact_name"), "")
        self.assertEqual(parsed.get("contact_email"), "")
        self.assertEqual(parsed.get("contact_phone"), "")

    def test_open_contact_fields_from_dom(self):
        parsed = HHVacancyParser.parse_open_contacts(OPEN_CONTACT_HTML)
        self.assertNotEqual(parsed.get("contacts_hidden"), "true")
        self.assertEqual(parsed.get("contact_name"), "Иванова Анна Сергеевна")

    def test_no_regex_guess_from_description_when_hidden(self):
        parsed = HHVacancyParser.parse_open_contacts(HIDDEN_CONTACT_HTML)
        self.assertEqual(parsed.get("contact_email"), "")
        self.assertEqual(parsed.get("contact_phone"), "")

    def test_one_c_search_keywords_expanded(self):
        keywords = HHVacancyParser.one_c_search_keywords("1С")
        blob = " ".join(keywords).lower()
        for term in ("консультант 1с", "аналитик 1с", "внедренец 1с"):
            self.assertIn(term, blob)

    def test_vacancy_email_not_reachable(self):
        vacancy_url = "https://hh.ru/vacancy/12345678"
        self.assertFalse(
            cs.is_personal_reachable_contact("email", "anna.ivanova@client.ru", vacancy_url)
        )
        people = [{
            "fio": "",
            "profile_url": None,
            "meta": {},
            "contacts": [
                {"type": "email", "value": "anna.ivanova@client.ru", "source_url": vacancy_url},
            ],
        }]
        status = cs.compute_card_status(
            people=people,
            vacancies=[{"title": "Консультант 1С"}],
        )
        self.assertNotEqual(status, cs.STATUS_REACHABLE)
        self.assertEqual(status, cs.STATUS_SIGNAL)

    def test_vacancy_phone_not_reachable(self):
        vacancy_url = "https://hh.ru/vacancy/12345678"
        self.assertFalse(
            cs.is_personal_reachable_contact("phone", "+7 495 123-45-67", vacancy_url)
        )

    def test_tenchat_email_reachable(self):
        status = cs.compute_card_status(
            lprs=[{
                "name": "Иванов",
                "contacts": {"email": "ivan.petrov@company.ru"},
            }],
        )
        self.assertEqual(status, cs.STATUS_REACHABLE)

    def test_ceo_dadata_named_not_vacancy_contact(self):
        status = cs.compute_card_status(
            vacancies=[{"title": "Аналитик 1С"}],
            ceo_name="Аристов Алексей",
        )
        self.assertEqual(status, cs.STATUS_NAMED)

    def test_checko_phone_still_not_reachable(self):
        people = [{
            "fio": "Мальцев",
            "contacts": [
                {
                    "type": "phone",
                    "value": "+7 800 301-10-32",
                    "source_url": "https://checko.ru/company/example",
                },
            ],
        }]
        status = cs.compute_card_status(people=people, ceo_name="Мальцев")
        self.assertEqual(status, cs.STATUS_NAMED)


class HHVacancyMemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("DATABASE_URL", None)
        os.environ["COPILOT_MEMORY_DB_PATH"] = os.path.join(self.tmp.name, "hh.db")
        import importlib
        import memory_store

        importlib.reload(memory_store)
        self.ms = memory_store

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("COPILOT_MEMORY_DB_PATH", None)

    def test_upsert_from_hh_vacancy_hidden_contact_trigger_only(self):
        inn = self.ms.upsert_from_hh_vacancy(
            "7801711200",
            "АО «ИМ»",
            {
                "title": "Программист 1С",
                "url": "https://hh.ru/vacancy/135527588",
                "contacts_hidden": True,
            },
        )
        self.assertEqual(inn, "7801711200")
        self.assertEqual(len(self.ms.list_people("7801711200")), 0)
        row = self.ms.get_company("7801711200")
        self.assertIn("HH:", " ".join(row.get("triggers") or []))
        self.assertEqual(row.get("card_status"), cs.STATUS_SIGNAL)

    def test_upsert_from_hh_vacancy_open_contact_not_stored(self):
        """Even open vacancy contacts are not persisted — trigger + INN only."""
        inn = self.ms.upsert_from_hh_vacancy(
            "9999999999",
            "ООО Тест HH",
            {
                "title": "Консультант 1С",
                "url": "https://hh.ru/vacancy/99999999",
                "contact_name": "Петрова Мария",
                "contact_email": "maria.petrova@test.ru",
                "contact_phone": "+7 916 000-00-01",
            },
        )
        self.assertEqual(inn, "9999999999")
        self.assertEqual(len(self.ms.list_people("9999999999")), 0)
        row = self.ms.get_company("9999999999")
        self.assertEqual(row.get("card_status"), cs.STATUS_SIGNAL)


class LiveQueueInactiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("DATABASE_URL", None)
        os.environ["COPILOT_MEMORY_DB_PATH"] = os.path.join(self.tmp.name, "queue.db")
        import importlib
        import memory_store

        importlib.reload(memory_store)
        self.ms = memory_store

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("COPILOT_MEMORY_DB_PATH", None)

    def test_inactive_ip_excluded_from_queue(self):
        from scripts.seed_live_companies import apply_live_seed

        apply_live_seed(self.ms)
        all_in_work = self.ms.list_companies(queue=cs.QUEUE_IN_WORK)
        inns = {c["inn"] for c in all_in_work}
        self.assertNotIn("771579995573", inns)
        self.assertEqual(len(all_in_work), 4)


if __name__ == "__main__":
    unittest.main()
