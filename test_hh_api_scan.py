"""Tests: HH vacancy scan via public API + DaData INN (no HTML)."""
import os
import unittest
from unittest.mock import MagicMock, patch

from hh_auth import HHAuthClient


SAMPLE_VACANCY = {
    "id": "12345678",
    "name": "Программист 1С",
    "alternate_url": "https://hh.ru/vacancy/12345678",
    "archived": False,
    "employer": {"id": "999", "name": 'ООО "Тест Компания"'},
    "snippet": {
        "requirement": "Опыт 1С:ERP, ЗУП",
        "responsibility": "Разработка и доработка конфигураций",
    },
    "salary": {"from": 150000, "to": 200000, "currency": "RUR"},
}


class HHApiScanTest(unittest.TestCase):
    def test_probe_unreachable_on_403(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        with patch("hh_auth.requests.get", return_value=mock_resp):
            probe = HHAuthClient.probe_vacancies_api()
        self.assertFalse(probe["available"])
        self.assertEqual(probe["http_status"], 403)
        self.assertIn("403", probe["message"])

    def test_scan_hh_unreachable_when_probe_fails(self):
        with patch.object(
            HHAuthClient,
            "probe_vacancies_api",
            return_value={
                "available": False,
                "http_status": 403,
                "message": "HH API недоступен с этого сервера (HTTP 403).",
            },
        ):
            result = HHAuthClient.scan_one_c_vacancy_triggers(limit=3)
        self.assertEqual(result["scan_status"], "hh_unreachable")
        self.assertEqual(result["items"], [])
        self.assertIn("403", result["scan_message"])

    def test_scan_dadata_missing(self):
        with patch.object(
            HHAuthClient,
            "probe_vacancies_api",
            return_value={"available": True, "http_status": 200, "message": "OK"},
        ), patch("dadata_company.is_configured", return_value=False):
            result = HHAuthClient.scan_one_c_vacancy_triggers(limit=3)
        self.assertEqual(result["scan_status"], "dadata_missing")
        self.assertEqual(result["items"], [])

    def test_scan_ok_with_inn_match(self):
        with patch.object(
            HHAuthClient,
            "probe_vacancies_api",
            return_value={"available": True, "http_status": 200, "message": "OK"},
        ), patch("dadata_company.is_configured", return_value=True), patch.object(
            HHAuthClient,
            "search_vacancies_api",
            return_value=([SAMPLE_VACANCY], None),
        ), patch(
            "dadata_company.resolve_party_inn",
            return_value={
                "inn": "7701234567",
                "matched_name": 'ООО "Тест Компания"',
                "active": True,
                "reason": "matched",
            },
        ):
            result = HHAuthClient.scan_one_c_vacancy_triggers(limit=3)
        self.assertEqual(result["scan_status"], "ok")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["inn"], "7701234567")
        self.assertTrue(result["items"][0]["trigger_only"])

    def test_scan_no_inn_matches(self):
        with patch.object(
            HHAuthClient,
            "probe_vacancies_api",
            return_value={"available": True, "http_status": 200, "message": "OK"},
        ), patch("dadata_company.is_configured", return_value=True), patch.object(
            HHAuthClient,
            "search_vacancies_api",
            return_value=([SAMPLE_VACANCY], None),
        ), patch(
            "dadata_company.resolve_party_inn",
            return_value={"inn": "", "matched_name": "", "active": False, "reason": "no_match"},
        ):
            result = HHAuthClient.scan_one_c_vacancy_triggers(limit=3)
        self.assertEqual(result["scan_status"], "no_inn_matches")
        self.assertEqual(result["items"], [])
        self.assertGreater(result["raw_vacancy_count"], 0)

    def test_scan_skips_inactive_inn(self):
        with patch.object(
            HHAuthClient,
            "probe_vacancies_api",
            return_value={"available": True, "http_status": 200, "message": "OK"},
        ), patch("dadata_company.is_configured", return_value=True), patch.object(
            HHAuthClient,
            "search_vacancies_api",
            return_value=([SAMPLE_VACANCY], None),
        ), patch(
            "dadata_company.resolve_party_inn",
            return_value={
                "inn": "771579995573",
                "matched_name": "ИП Елисеев",
                "active": True,
                "reason": "matched",
            },
        ):
            result = HHAuthClient.scan_one_c_vacancy_triggers(limit=3)
        self.assertEqual(result["scan_status"], "no_inn_matches")
        self.assertEqual(result["items"], [])


if __name__ == "__main__":
    unittest.main()
