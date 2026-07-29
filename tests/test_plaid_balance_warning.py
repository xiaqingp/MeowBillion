import os
import tempfile
import unittest
from pathlib import Path

import database
from routes_plaid import record_balance_sync_result

ROOT = Path(__file__).resolve().parents[1]


class PlaidBalanceWarningTests(unittest.TestCase):
    def setUp(self):
        self.original_db_file = database.DB_FILE
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        database.DB_FILE = os.path.join(self.tmpdir.name, "finance.db")
        database.init_db()
        with database.get_db() as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, password_hash, display_name, role, created_at)
                VALUES ('u1', 'u1@example.com', 'x', 'User One', 'admin', datetime('now'))
                """
            )
            conn.execute(
                """
                INSERT INTO plaid_tokens (access_token, item_id, institution_name, user_id)
                VALUES ('token', 'item1', 'Robinhood', 'u1')
                """
            )
            conn.commit()

    def tearDown(self):
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def test_balance_failure_is_persisted_and_next_success_clears_it(self):
        with database.get_db() as conn:
            record_balance_sync_result(
                conn.cursor(), "u1", "token", False, "2026-07-28 16:00:00", "temporary timeout"
            )
            failed = conn.execute(
                """
                SELECT balance_sync_status, balance_last_synced, balance_error_message
                FROM plaid_tokens
                WHERE access_token = 'token'
                """
            ).fetchone()

            self.assertEqual(failed["balance_sync_status"], "failed")
            self.assertIsNone(failed["balance_last_synced"])
            self.assertEqual(failed["balance_error_message"], "temporary timeout")

            record_balance_sync_result(
                conn.cursor(), "u1", "token", True, "2026-07-28 17:00:00"
            )
            recovered = conn.execute(
                """
                SELECT balance_sync_status, balance_last_synced, balance_error_message
                FROM plaid_tokens
                WHERE access_token = 'token'
                """
            ).fetchone()

        self.assertEqual(recovered["balance_sync_status"], "synced")
        self.assertEqual(recovered["balance_last_synced"], "2026-07-28 17:00:00")
        self.assertIsNone(recovered["balance_error_message"])

    def test_balance_failure_ui_recommends_sync_instead_of_repair(self):
        app_js = (ROOT / "app.js").read_text(encoding="utf-8")
        plaid_service_js = (ROOT / "modules" / "plaid-service.js").read_text(encoding="utf-8")

        self.assertIn('label: "Balance stale"', app_js)
        self.assertIn('primaryLabel: "Sync now"', app_js)
        self.assertIn('"Suggested action: Sync now"', app_js)
        self.assertIn("warningCount", plaid_service_js)
        self.assertIn("institution warning", plaid_service_js)

    def test_dashboard_does_not_default_missing_net_worth_to_zero(self):
        app_js = (ROOT / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("Number(allocationPayload?.net_worth || 0)", app_js)
        self.assertIn('cashBalEl.textContent = "—"', app_js)


if __name__ == "__main__":
    unittest.main()
