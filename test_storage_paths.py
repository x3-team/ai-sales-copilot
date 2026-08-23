"""Local SQLite path prefers ./data, not /tmp."""
import os
import tempfile
import unittest

import storage_paths


class StoragePathsTest(unittest.TestCase):
    def test_defaults_to_project_data_dir(self):
        os.environ.pop("COPILOT_MEMORY_DB_PATH", None)
        path = storage_paths.resolve_sqlite_path("COPILOT_MEMORY_DB_PATH", "copilot_memory.db")
        self.assertTrue(path.endswith(os.path.join("data", "copilot_memory.db")))
        self.assertNotIn("/tmp/", path)

    def test_explicit_env_wins(self):
        tmp = tempfile.mkdtemp()
        target = os.path.join(tmp, "custom.db")
        os.environ["COPILOT_MEMORY_DB_PATH"] = target
        try:
            path = storage_paths.resolve_sqlite_path("COPILOT_MEMORY_DB_PATH", "copilot_memory.db")
            self.assertEqual(path, target)
        finally:
            os.environ.pop("COPILOT_MEMORY_DB_PATH", None)


if __name__ == "__main__":
    unittest.main()
