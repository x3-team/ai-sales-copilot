"""Tests for LPR job SQLite persistence."""
import importlib
import os
import tempfile
import unittest


class LprJobStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test_lpr_jobs.db")
        os.environ["LPR_JOBS_DB_PATH"] = self.db_path
        os.environ["WEBHOOK_BASE_URL"] = "https://example.onrender.com"
        os.environ["WEBHOOK_HMAC_SECRET"] = "test-secret"
        os.environ["WEBHOOK_ALLOW_HTTP"] = "1"

        import lpr_job_store
        import lpr_webhook

        importlib.reload(lpr_job_store)
        importlib.reload(lpr_webhook)
        self.store = lpr_job_store
        self.webhook = lpr_webhook

    def tearDown(self):
        self.tmp.cleanup()

    def test_job_survives_module_reload(self):
        created = self.webhook.create_job(
            prompt="test prompt",
            inn="4217184336",
            company_name="ООО Тест",
            auto_submit=False,
        )
        job_id = created["job_id"]
        self.assertTrue(os.path.isfile(self.db_path))

        import lpr_job_store
        import lpr_webhook

        importlib.reload(lpr_job_store)
        importlib.reload(lpr_webhook)

        job = lpr_webhook.get_job_public(job_id)
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["inn"], "4217184336")
        self.assertEqual(job["company_name"], "ООО Тест")

    def test_inbound_persisted(self):
        created = self.webhook.create_job(
            prompt="test",
            inn="9709052492",
            company_name="ООО «МОЛОЧНЫЙ ДОМ»",
            auto_submit=False,
        )
        job_id = created["job_id"]
        self.webhook.handle_inbound_webhook(
            job_id,
            {
                "status": "completed",
                "contacts": [
                    {
                        "name": "Test Director",
                        "role": "Director",
                        "company": "OOO Test",
                        "source": "ЕГРЮЛ + TenChat страница компании",
                        "extra_links": ["https://tenchat.ru/1197746487641"],
                        "stakeholder_hint": "ceo",
                        "confidence": 70,
                    }
                ],
            },
        )

        import lpr_job_store
        import lpr_webhook

        importlib.reload(lpr_job_store)
        importlib.reload(lpr_webhook)

        job = lpr_webhook.get_job_public(job_id)
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["candidates_count"], 1)
        self.assertEqual(job["candidates"][0]["name"], "Test Director")


if __name__ == "__main__":
    unittest.main()
