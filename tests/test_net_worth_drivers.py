import os
import tempfile
import unittest

import database
import routes_plaid
from server import app


class NetWorthDriverTests(unittest.TestCase):
    def setUp(self):
        self.original_db_file = database.DB_FILE
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        database.DB_FILE = os.path.join(self.tmpdir.name, "finance.db")
        database.init_db()
        routes_plaid.ALLOCATION_CACHE.update({"time": 0.0, "payload": None, "user_id": None})
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
            conn.executemany(
                """
                INSERT INTO accounts
                    (account_id, name, type, subtype, institution_name, balance_current, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("asset_up", "Checking", "depository", "checking", "Bank A", 120, "u1"),
                    ("credit_down", "Credit Card", "credit", "credit card", "Bank B", 40, "u1"),
                    ("asset_down", "Brokerage", "investment", "brokerage", "Broker C", 180, "u1"),
                    ("other_user", "Private Account", "depository", "checking", "Other Bank", 1999, "u2"),
                ],
            )
            conn.executemany(
                """
                INSERT INTO account_balances_history
                    (account_id, date, balance_current, balance_available, user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    ("asset_up", "2026-07-13", 100, 100, "u1"),
                    ("asset_up", "2026-07-14", 120, 120, "u1"),
                    ("credit_down", "2026-07-13", 50, 50, "u1"),
                    ("credit_down", "2026-07-14", 40, 40, "u1"),
                    ("asset_down", "2026-07-13", 200, 200, "u1"),
                    ("asset_down", "2026-07-14", 180, 180, "u1"),
                    ("other_user", "2026-07-13", 999, 999, "u2"),
                    ("other_user", "2026-07-14", 1999, 1999, "u2"),
                ],
            )
            conn.execute(
                """
                INSERT INTO manual_assets
                    (asset_id, name, asset_type, value, real_estate_pct, active, user_id)
                VALUES ('manual_home', 'Home', 'real_estate', 315, 100, 1, 'u1')
                """
            )
            conn.executemany(
                """
                INSERT INTO manual_asset_values (asset_id, date, value, user_id)
                VALUES (?, ?, ?, ?)
                """,
                [
                    ("manual_home", "2026-07-13", 300, "u1"),
                    ("manual_home", "2026-07-14", 315, "u1"),
                ],
            )
            conn.executemany(
                """
                INSERT INTO allocation_history_snapshots
                    (date, cash, stock, bond, real_estate, liabilities, source, user_id)
                VALUES (?, ?, 0, 0, 0, 0, 'imported', 'u1')
                """,
                [
                    ("2026-06-01", 1000),
                    ("2026-06-30", 1100),
                ],
            )
            conn.commit()

        with self.client.session_transaction() as session:
            session["user_id"] = "u1"

    def tearDown(self):
        routes_plaid.ALLOCATION_CACHE.update({"time": 0.0, "payload": None, "user_id": None})
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def test_explains_assets_liabilities_manual_assets_and_down_moves(self):
        response = self.client.get("/api/net_worth_drivers?date=2026-07-14")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(payload["previous_date"], "2026-07-13")
        self.assertAlmostEqual(payload["net_worth"], 575)
        self.assertAlmostEqual(payload["previous_net_worth"], 550)
        self.assertAlmostEqual(payload["net_worth_change"], 25)
        self.assertAlmostEqual(payload["explained_change"], 25)
        self.assertAlmostEqual(payload["unattributed_change"], 0)
        self.assertAlmostEqual(payload["coverage_pct"], 100)

        self.assertEqual(
            [(row["account_id"], row["contribution"]) for row in payload["top_up"]],
            [("asset_up", 20), ("manual_home", 15), ("credit_down", 10)],
        )
        self.assertEqual(payload["top_down"][0]["account_id"], "asset_down")
        self.assertAlmostEqual(payload["top_down"][0]["contribution"], -20)
        self.assertNotIn("other_user", str(payload))

    def test_legacy_aggregate_change_is_unattributed(self):
        response = self.client.get("/api/net_worth_drivers?date=2026-06-30")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()

        self.assertEqual(payload["previous_date"], "2026-06-01")
        self.assertAlmostEqual(payload["net_worth_change"], 100)
        self.assertAlmostEqual(payload["explained_change"], 0)
        self.assertAlmostEqual(payload["unattributed_change"], 100)
        self.assertAlmostEqual(payload["coverage_pct"], 0)
        self.assertEqual(payload["top_up"], [])
        self.assertEqual(payload["top_down"], [])

    def test_validates_date_and_requires_a_previous_snapshot(self):
        self.assertEqual(self.client.get("/api/net_worth_drivers").status_code, 400)
        self.assertEqual(self.client.get("/api/net_worth_drivers?date=not-a-date").status_code, 400)
        self.assertEqual(self.client.get("/api/net_worth_drivers?date=2026-06-01").status_code, 404)
        self.assertEqual(self.client.get("/api/net_worth_drivers?date=2026-06-02").status_code, 404)


if __name__ == "__main__":
    unittest.main()
