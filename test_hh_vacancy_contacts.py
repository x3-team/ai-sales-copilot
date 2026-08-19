"""Tests for HH vacancy open-contact parsing and reachable status from vacancy contacts."""
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

GENERIC_CONTACT_HTML = """
<html><body>
  <div data-qa="vacancy-contacts">
    <span data-qa="vacancy-contacts-name">Отдел подбора</span>
    <a data-qa="vacancy-contacts-email" href="mailto:hr@company.ru">hr@company.ru</a>
    <span data-qa="vacancy-contacts-phone">+7 (495) 000-00-00</span>
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
        self.assertEqual(parsed.get("contact_email"), "anna.ivanova@client.ru")
        self.assertEqual(parsed.get("contact_phone"), "+7 (495) 123-45-67")

    def test_no_regex_guess_from_description_when_hidden(self):
        """Description mentions email/phone but hidden flag — must stay empty."""
        parsed = HHVacancyParser.parse_open_contacts(HIDDEN_CONTACT_HTML)
        self.assertEqual(parsed.get("contact_email"), "")
        self.assertEqual(parsed.get("contact_phone"), "")

    def test_one_c_search_keywords_expanded(self):
        keywords = HHVacancyParser.one_c_search_keywords("1С")
        blob = " ".join(keywords).lower()
        for term in ("консультант 1с", "аналитик 1с", "внедренец 1с", "администратор 1с", "автоматизация 1с"):
            self.assertIn(term, blob)

    def test_reachable_from_personal_vacancy_email(self):
        vacancy_url = "https://hh.ru/vacancy/12345678"
        people = [{
            "fio": "Иванова Анна Сергеевна",
            "profile_url": None,
            "meta": {},
            "contacts": [
                {
                    "type": "email",
                    "value": "anna.ivanova@client.ru",
                    "source_url": vacancy_url,
                },
            ],
        }]
        status = cs.compute_card_status(people=people)
        self.assertEqual(status, cs.STATUS_REACHABLE)

    def test_generic_vacancy_email_not_reachable(self):
        vacancy_url = "https://hh.ru/vacancy/12345678"
        people = [{
            "fio": "",
            "profile_url": None,
            "meta": {},
            "contacts": [
                {"type": "email", "value": "hr@company.ru", "source_url": vacancy_url},
                {"type": "email", "value": "info@company.ru", "source_url": vacancy_url},
                {"type": "email", "value": "vacancy@company.ru", "source_url": vacancy_url},
            ],
        }]
        status = cs.compute_card_status(
            people=people,
            vacancies=[{"title": "Консультант 1С"}],
        )
        self.assertNotEqual(status, cs.STATUS_REACHABLE)

    def test_vacancy_name_yields_named_not_reachable_without_contact(self):
        people = [{
            "fio": "Иванова Анна Сергеевна",
            "profile_url": None,
            "meta": {"source_type": "hh_vacancy"},
            "contacts": [],
        }]
        status = cs.compute_card_status(
            people=people,
            vacancies=[{"title": "Аналитик 1С"}],
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

    def test_upsert_from_hh_vacancy_empty_slots(self):
        pid = self.ms.upsert_from_hh_vacancy(
            "7801711200",
            "АО «ИМ»",
            {
                "id": "hh-135527588",
                "title": "Программист 1С",
                "url": "https://hh.ru/vacancy/135527588",
                "hr_name": "",
                "hr_email": "",
                "hr_phone": "",
                "contacts_hidden": True,
            },
        )
        self.assertIsNone(pid)
        people = self.ms.list_people("7801711200")
        self.assertEqual(len(people), 0)

    def test_upsert_from_hh_vacancy_with_open_contact(self):
        url = "https://hh.ru/vacancy/99999999"
        pid = self.ms.upsert_from_hh_vacancy(
            "9999999999",
            "ООО Тест HH",
            {
                "title": "Консультант 1С",
                "url": url,
                "contact_name": "Петрова Мария",
                "contact_email": "maria.petrova@test.ru",
                "contact_phone": "+7 916 000-00-01",
            },
        )
        self.assertIsNotNone(pid)
        people = self.ms.list_people("9999999999")
        self.assertEqual(len(people), 1)
        contacts = people[0]["contacts"]
        emails = [c for c in contacts if c["type"] == "email"]
        self.assertEqual(emails[0]["value"], "maria.petrova@test.ru")
        self.assertEqual(emails[0]["source_url"], url)
        row = self.ms.get_company("9999999999")
        self.assertEqual(row.get("card_status"), cs.STATUS_REACHABLE)


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
