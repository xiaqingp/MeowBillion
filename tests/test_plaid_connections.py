import sqlite3
import unittest

from routes_plaid import item_has_investment_accounts


class PlaidConnectionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE accounts (
                user_id TEXT,
                item_id TEXT,
                account_id TEXT,
                type TEXT,
                subtype TEXT,
                name TEXT,
                official_name TEXT,
                institution_name TEXT
            )
            """
        )

    def tearDown(self):
        self.conn.close()

    def test_synced_holdings_mark_item_as_investment(self):
        self.assertTrue(
            item_has_investment_accounts(
                self.conn.cursor(),
                "user-1",
                "item-1",
                holdings_sync_status="synced",
            )
        )

    def test_detects_investment_account_by_type_or_subtype(self):
        self.conn.execute(
            "INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("user-1", "item-1", "acc-1", "depository", "brokerage", "Brokerage", "Brokerage", "Bank"),
        )

        self.assertTrue(item_has_investment_accounts(self.conn.cursor(), "user-1", "item-1"))
        self.assertFalse(item_has_investment_accounts(self.conn.cursor(), "user-2", "item-1"))

    def test_detects_cash_management_as_investment_like_for_repair(self):
        self.conn.execute(
            "INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("user-1", "item-1", "acc-1", "depository", "cash management", "CMA-Edge", "CMA-Edge", "Merrill"),
        )

        self.assertTrue(item_has_investment_accounts(self.conn.cursor(), "user-1", "item-1"))

    def test_checking_only_does_not_request_investments_for_repair(self):
        self.conn.execute(
            "INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("user-1", "item-1", "acc-1", "depository", "checking", "Checking", "Checking", "Bank"),
        )

        self.assertFalse(item_has_investment_accounts(self.conn.cursor(), "user-1", "item-1"))


if __name__ == "__main__":
    unittest.main()
