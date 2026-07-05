import os
import tempfile
import unittest

import database
from routes_config import load_analysis_rules_config_from_db, load_categories_config_from_db


class ZeroStartTests(unittest.TestCase):
    def test_empty_database_initializes_default_config(self):
        original_db_file = database.DB_FILE
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
                database.DB_FILE = os.path.join(tmpdir, "finance.db")
                database.init_db()

                categories_config = load_categories_config_from_db()
                analysis_rules = load_analysis_rules_config_from_db()

                self.assertIn("Travel", categories_config["categories"])
                self.assertIn("Rentals", categories_config["categories"])
                self.assertEqual(analysis_rules["travel"]["category"], "Travel")
                self.assertEqual(analysis_rules["rentals"]["category"], "Rentals")
                self.assertTrue(os.path.exists(database.DB_FILE))
        finally:
            database.DB_FILE = original_db_file


if __name__ == "__main__":
    unittest.main()
