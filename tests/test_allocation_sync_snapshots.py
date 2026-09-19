import os
import tempfile
import unittest
from unittest.mock import patch

import database
import routes_plaid
from server import app


class FakeHoldingsResponse:
    def to_dict(self):
        return {
            "holdings": [
                {
                    "account_id": "investment",
                    "security_id": "stock_security",
                    "institution_value": 150,
                }
            ],
            "securities": [
                {
                    "security_id": "stock_security",
                    "type": "equity",
                    "name": "Example Stock",
                }
            ],
        }


class FakePlaidClient:
    def __init__(self):
        self.holdings_calls = 0

    def investments_holdings_get(self, request):
        self.holdings_calls += 1
        return FakeHoldingsResponse()


class AllocationSyncSnapshotTests(unittest.TestCase):
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
                "INSERT INTO users (id, email, password_hash, display_name, role, created_at) "
                "VALUES ('u1', 'u1@example.com', 'x', 'User One', 'admin', datetime('now'))"
            )
            conn.executemany(
                """
                INSERT INTO accounts
                    (account_id, name, type, subtype, balance_current, item_id, institution_name, user_id)
                VALUES (?, ?, ?, ?, ?, 'item1', 'Test Bank', 'u1')
                """,
                [
                    ("checking", "Checking", "depository", "checking", 100),
                    ("investment", "Brokerage", "investment", "brokerage", 200),
                ],
            )
            conn.commit()

        with self.client.session_transaction() as session:
            session["user_id"] = "u1"

    def tearDown(self):
        routes_plaid.ALLOCATION_CACHE.update({"time": 0.0, "payload": None, "user_id": None})
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def test_sync_fetches_holdings_once_and_persists_account_allocations(self):
        accounts = [
            {
                "account_id": "checking",
                "name": "Checking",
                "type": "depository",
                "subtype": "checking",
                "balances": {"current": 100},
            },
            {
                "account_id": "investment",
                "name": "Brokerage",
                "type": "investment",
                "subtype": "brokerage",
                "balances": {"current": 200},
            },
        ]
        client = FakePlaidClient()

        with database.get_db() as conn:
            result = routes_plaid.sync_item_allocation_snapshots(
                client, conn.cursor(), "u1", "token", "item1", accounts, "2026-07-16"
            )
            conn.commit()
            rows = conn.execute(
                """
                SELECT account_id, cash_pct, stock_pct, source
                FROM account_allocation_snapshots
                WHERE user_id = 'u1' AND date = '2026-07-16'
                ORDER BY account_id
                """
            ).fetchall()

        self.assertEqual(client.holdings_calls, 1)
        self.assertEqual(result["holdings_count"], 1)
        self.assertEqual(
            [(row["account_id"], row["cash_pct"], row["stock_pct"], row["source"]) for row in rows],
            [
                ("checking", 100.0, 0.0, "cash_default"),
                ("investment", 25.0, 75.0, "holdings"),
            ],
        )

    def test_overview_allocation_reads_snapshot_without_calling_plaid(self):
        with database.get_db() as conn:
            conn.execute(
                """
                INSERT INTO account_allocation_snapshots
                    (user_id, account_id, date, value, cash_pct, stock_pct, bond_pct,
                     real_estate_pct, source, holdings_count)
                VALUES ('u1', 'investment', '2026-07-16', 200, 25, 75, 0, 0, 'holdings', 1)
                """
            )
            conn.commit()

        with patch("routes_plaid.get_plaid_client", side_effect=AssertionError("Overview must not call Plaid")):
            response = self.client.get("/api/allocation_accounts")
            history_response = self.client.get("/api/allocation_history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(history_response.status_code, 200)
        investment = next(row for row in response.get_json()["accounts"] if row["account_id"] == "investment")
        self.assertEqual(investment["source"], "holdings")
        self.assertAlmostEqual(investment["categories"]["Cash"], 50)
        self.assertAlmostEqual(investment["categories"]["Stock"], 150)

    def test_allocation_history_carries_forward_accounts_missing_from_partial_sync_day(self):
        with database.get_db() as conn:
            conn.executemany(
                """
                INSERT INTO account_balances_history
                    (account_id, date, balance_current, balance_available, user_id)
                VALUES (?, ?, ?, ?, 'u1')
                """,
                [
                    ("checking", "2026-07-15", 100, 100),
                    ("investment", "2026-07-15", 200, 200),
                    ("checking", "2026-07-16", 110, 110),
                ],
            )
            conn.commit()

        history = self.client.get("/api/allocation_history").get_json()["history"]
        latest = next(row for row in history if row["date"] == "2026-07-16")

        self.assertAlmostEqual(latest["Net Worth"], 310)

        current = self.client.get("/api/allocation_accounts").get_json()
        self.assertAlmostEqual(history[-1]["Net Worth"], current["net_worth"])

    def test_inactive_account_is_excluded_from_current_net_worth(self):
        with database.get_db() as conn:
            conn.execute("UPDATE accounts SET active = 0 WHERE account_id = 'checking'")
            conn.commit()

        current = self.client.get("/api/allocation_accounts").get_json()
        accounts = self.client.get("/api/accounts").get_json()

        self.assertNotIn("checking", {row["account_id"] for row in current["accounts"]})
        self.assertAlmostEqual(current["net_worth"], 200)
        self.assertEqual(next(row for row in accounts if row["account_id"] == "checking")["active"], 0)

    def test_daily_snapshot_is_frozen_and_inactive_balance_stops_at_last_observation(self):
        with database.get_db() as conn:
            conn.execute("UPDATE accounts SET active = 0 WHERE account_id = 'checking'")
            conn.executemany(
                """
                INSERT INTO account_balances_history
                    (account_id, date, balance_current, balance_available, user_id)
                VALUES (?, ?, ?, ?, 'u1')
                """,
                [
                    ("checking", "2026-07-15", 100, 100),
                    ("investment", "2026-07-15", 200, 200),
                    ("investment", "2026-07-16", 210, 210),
                ],
            )
            conn.execute(
                """
                INSERT INTO allocation_history_snapshots
                    (date, cash, stock, bond, real_estate, liabilities, source, user_id)
                VALUES ('2026-07-16', 999, 0, 0, 0, 0, 'daily_sync', 'u1')
                """
            )
            conn.execute(
                """
                INSERT INTO account_value_estimates
                    (account_id, date, value, cash_pct, stock_pct, bond_pct, real_estate_pct, user_id)
                VALUES ('checking', '2026-07-16', 50, 100, 0, 0, 0, 'u1')
                """
            )
            conn.execute(
                """
                INSERT INTO manual_assets
                    (asset_id, name, value, real_estate_pct, active, user_id)
                VALUES ('home', 'Home', 50, 100, 1, 'u1')
                """
            )
            conn.execute(
                "INSERT INTO manual_asset_values (asset_id, date, value, user_id) VALUES ('home', '2026-07-16', 50, 'u1')"
            )
            conn.commit()

        history = self.client.get("/api/allocation_history").get_json()["history"]
        july_15 = next(row for row in history if row["date"] == "2026-07-15")
        july_16 = next(row for row in history if row["date"] == "2026-07-16")

        self.assertAlmostEqual(july_15["Net Worth"], 350)
        self.assertAlmostEqual(july_16["Net Worth"], 999)
        self.assertAlmostEqual(july_16["Cash"], 999)
        self.assertAlmostEqual(july_16["Real Estate"], 0)

    def test_current_allocation_snapshot_is_persisted_per_user_and_date(self):
        routes_plaid.persist_current_allocation_history_snapshot("u1", "2026-07-17")

        with database.get_db() as conn:
            row = conn.execute(
                """
                SELECT cash, stock, liabilities, net_worth, source
                FROM allocation_history_snapshots
                WHERE user_id = 'u1' AND date = '2026-07-17'
                """
            ).fetchone()

        self.assertEqual(row["source"], "daily_sync")
        self.assertAlmostEqual(row["cash"], 100)
        self.assertAlmostEqual(row["stock"], 0)
        self.assertAlmostEqual(row["liabilities"], 0)
        self.assertAlmostEqual(row["net_worth"], 300)

    def test_background_snapshot_includes_user_overrides_and_manual_assets(self):
        with database.get_db() as conn:
            conn.execute(
                """
                INSERT INTO allocation_overrides
                    (account_id, cash_pct, stock_pct, bond_pct, real_estate_pct,
                     unclassified_pct, user_id)
                VALUES ('investment', 0, 50, 50, 0, 0, 'u1')
                """
            )
            conn.execute(
                """
                INSERT INTO manual_assets
                    (asset_id, name, asset_type, value, cash_pct, stock_pct,
                     bond_pct, real_estate_pct, active, user_id)
                VALUES ('home', 'Home', 'real_estate', 500, 0, 0, 0, 100, 1, 'u1')
                """
            )
            conn.commit()

        # Background sync has no request/session context, so the explicit user ID
        # must be propagated to both override and manual-asset loaders.
        routes_plaid.persist_current_allocation_history_snapshot("u1", "2026-07-17")

        with database.get_db() as conn:
            row = conn.execute(
                """
                SELECT cash, stock, bond, real_estate, net_worth
                FROM allocation_history_snapshots
                WHERE user_id = 'u1' AND date = '2026-07-17'
                """
            ).fetchone()

        self.assertAlmostEqual(row["cash"], 100)
        self.assertAlmostEqual(row["stock"], 100)
        self.assertAlmostEqual(row["bond"], 100)
        self.assertAlmostEqual(row["real_estate"], 500)
        self.assertAlmostEqual(row["net_worth"], 800)

    def test_failed_holdings_refresh_keeps_last_successful_snapshot(self):
        with database.get_db() as conn:
            conn.execute(
                """
                INSERT INTO account_allocation_snapshots
                    (user_id, account_id, date, value, cash_pct, stock_pct, bond_pct,
                     real_estate_pct, source, holdings_count)
                VALUES ('u1', 'investment', '2026-07-15', 180, 10, 90, 0, 0, 'holdings', 2)
                """
            )
            routes_plaid.persist_item_allocation_snapshots(
                conn.cursor(),
                "u1",
                [
                    {
                        "account_id": "investment",
                        "name": "Brokerage",
                        "type": "investment",
                        "subtype": "brokerage",
                        "balances": {"current": 200},
                    }
                ],
                {},
                "2026-07-16",
            )
            conn.commit()

        response = self.client.get("/api/allocation_accounts")

        investment = next(row for row in response.get_json()["accounts"] if row["account_id"] == "investment")
        self.assertAlmostEqual(investment["categories"]["Cash"], 20)
        self.assertAlmostEqual(investment["categories"]["Stock"], 180)
        self.assertEqual(investment["holdings_count"], 2)

    def test_clearing_manual_override_refreshes_auto_snapshot(self):
        with database.get_db() as conn:
            conn.execute(
                """
                INSERT INTO plaid_tokens (access_token, item_id, institution_name, user_id)
                VALUES ('token', 'item1', 'Test Bank', 'u1')
                """
            )
            conn.execute(
                """
                INSERT INTO allocation_overrides
                    (account_id, cash_pct, stock_pct, bond_pct, real_estate_pct, user_id)
                VALUES ('investment', 0, 0, 100, 0, 'u1')
                """
            )
            conn.commit()

        with patch("routes_plaid.get_plaid_client", return_value=FakePlaidClient()):
            response = self.client.post(
                "/api/allocation_overrides",
                json={"account_id": "investment", "percentages": {}, "clear": True},
            )

        self.assertEqual(response.status_code, 200)
        routes_plaid.ALLOCATION_CACHE.update({"time": 0.0, "payload": None, "user_id": None})
        investment = next(
            row
            for row in self.client.get("/api/allocation_accounts").get_json()["accounts"]
            if row["account_id"] == "investment"
        )
        self.assertEqual(investment["source"], "holdings")
        self.assertAlmostEqual(investment["categories"]["Cash"], 50)
        self.assertAlmostEqual(investment["categories"]["Stock"], 150)


if __name__ == "__main__":
    unittest.main()
