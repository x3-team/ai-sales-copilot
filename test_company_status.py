"""Tests for company card status calculation."""
import unittest

import company_status as cs


def _lpr(name="", email=None, phone=None, telegram=None, profile_url="", profile_resolved=False):
    return {
        "name": name,
        "profile_url": profile_url,
        "profile_resolved": profile_resolved,
        "contacts": {
            "email": email,
            "phone": phone,
            "telegram": telegram,
        },
    }


class CompanyStatusTest(unittest.TestCase):
    def test_generic_office_email_not_reachable(self):
        self.assertTrue(cs.is_generic_office_email("kanc@ooorus.net"))
        self.assertTrue(cs.is_generic_office_email("info@company.ru"))
        self.assertFalse(cs.is_generic_office_email("ivan.petrov@company.ru"))

    def test_company_tenchat_page_not_personal_profile(self):
        self.assertFalse(cs.is_personal_profile_url("https://tenchat.ru/1197746487641"))
        self.assertTrue(cs.is_personal_profile_url("https://tenchat.ru/u/ivan-petrov"))

    def test_status_never_downgrades(self):
        self.assertEqual(cs.merge_status("named", "signal"), "named")
        self.assertEqual(cs.merge_status("reachable", "named"), "reachable")
        self.assertEqual(cs.merge_status("signal", "named"), "named")

    def test_signal_vacancy_no_person(self):
        status = cs.compute_card_status(
            lprs=[_lpr()],
            vacancies=[{"title": "Программист 1С"}],
        )
        self.assertEqual(status, cs.STATUS_SIGNAL)

    def test_named_ceo_egrul(self):
        status = cs.compute_card_status(
            lprs=[_lpr(name="Хажаев", profile_url="https://tenchat.ru/9709052492", profile_resolved=True)],
            vacancies=[{"title": "1С"}],
            ceo_name="Хажаев",
        )
        self.assertEqual(status, cs.STATUS_NAMED)

    def test_reachable_personal_email(self):
        status = cs.compute_card_status(
            lprs=[_lpr(name="Иванов", email="ivan.petrov@company.ru")],
        )
        self.assertEqual(status, cs.STATUS_REACHABLE)

    def test_live_super_sila_named_not_reachable(self):
        status = cs.compute_card_status(
            lprs=[
                _lpr(
                    name="Мальцев",
                    profile_url="https://tenchat.ru/1197746487641",
                    profile_resolved=True,
                )
            ],
            vacancies=[{"title": "1С"}],
            ceo_name="Мальцев",
        )
        self.assertEqual(status, cs.STATUS_NAMED)

    def test_live_ip_eliseev_signal(self):
        status = cs.compute_card_status(
            lprs=[_lpr()],
            vacancies=[{"title": "1С"}],
        )
        self.assertEqual(status, cs.STATUS_SIGNAL)

    def test_live_ao_im_named(self):
        status = cs.compute_card_status(
            lprs=[
                _lpr(
                    name="Аристов",
                    profile_url="https://tenchat.ru/7801711200",
                    profile_resolved=True,
                )
            ],
            vacancies=[{"title": "1С"}],
            ceo_name="Аристов",
        )
        self.assertEqual(status, cs.STATUS_NAMED)

    def test_live_molochny_dom_named(self):
        status = cs.compute_card_status(
            lprs=[
                _lpr(
                    name="Хажаев",
                    profile_url="https://tenchat.ru/b/id9709052492",
                    profile_resolved=True,
                )
            ],
            vacancies=[{"title": "1С"}],
            ceo_name="Хажаев",
        )
        self.assertEqual(status, cs.STATUS_NAMED)

    def test_live_rus_kanc_signal_not_reachable(self):
        status = cs.compute_card_status(
            lprs=[_lpr(email="kanc@ooorus.net")],
            vacancies=[{"title": "1С"}],
        )
        self.assertNotEqual(status, cs.STATUS_REACHABLE)
        self.assertIn(status, (cs.STATUS_SIGNAL, cs.STATUS_NAMED))

    def test_queue_filters(self):
        self.assertEqual(cs.queue_for_status(cs.STATUS_REACHABLE), cs.QUEUE_REACHABLE)
        self.assertEqual(cs.queue_for_status(cs.STATUS_NAMED), cs.QUEUE_IN_WORK)
        self.assertEqual(cs.queue_for_status(cs.STATUS_SIGNAL), cs.QUEUE_IN_WORK)


if __name__ == "__main__":
    unittest.main()
