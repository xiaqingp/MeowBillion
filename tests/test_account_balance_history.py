import os
import tempfile
import unittest

import database
from server import app


class AccountBalanceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.original_db_file = database.DB_FILE
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        database.DB_FILE = os.path.join(self.tmpdir.name, "finance.db")
        database.init_db()
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()
        with database.get_db() as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, password_hash, display_name, role, created_at)
                VALUES
                  ('u1', 'u1@example.com', 'x', 'User One', 'admin', datetime('now')),
                  ('u2', 'u2@example.com', 'x', 'User Two', 'user', datetime('now'))
                """
            )
            conn.execute(
                """
                INSERT INTO accounts (account_id, name, type, subtype, institution_name, balance_current, user_id)
                VALUES
                  ('acc_1', 'Checking', 'depository', 'checking', 'Bank A', 130, 'u1'),
                  ('acc_2', 'Other User', 'depository', 'checking', 'Bank B', 999, 'u2')
                """
            )
            conn.executemany(
                """
                INSERT INTO account_balances_history (account_id, date, balance_current, balance_available, user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    ('acc_1', '2026-05-31', 100, 100, 'u1'),
                    ('acc_1', '2026-06-15', 120, 120, 'u1'),
                    ('acc_1', '2026-07-15', 130, 130, 'u1'),
                    ('acc_2', '2026-07-15', 999, 999, 'u2'),
                ],
            )
            conn.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = "u1"

    def tearDown(self):
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def test_account_balance_history_filters_by_range(self):
        all_data = self.client.get("/api/account_balance_history?account_id=acc_1&range=ALL").get_json()
        self.assertEqual(all_data["account"]["account_id"], "acc_1")
        self.assertEqual([row["date"] for row in all_data["history"]], ["2026-05-31", "2026-06-15", "2026-07-15"])

        one_month = self.client.get("/api/account_balance_history?account_id=acc_1&range=1M").get_json()
        self.assertEqual([row["date"] for row in one_month["history"]], ["2026-06-15", "2026-07-15"])

    def test_account_balance_history_is_user_scoped(self):
        res = self.client.get("/api/account_balance_history?account_id=acc_2&range=ALL")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
