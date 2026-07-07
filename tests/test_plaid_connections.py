import sqlite3
import unittest

from routes_plaid import item_has_investment_accounts


class PlaidConnectionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            """
            CREATE TABLE accounts (
                user_id TEXT,
                item_id TEXT,
                account_id TEXT,
                type TEXT,
                subtype TEXT
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
            "INSERT INTO accounts VALUES (?, ?, ?, ?, ?)",
            ("user-1", "item-1", "acc-1", "depository", "brokerage"),
        )

        self.assertTrue(item_has_investment_accounts(self.conn.cursor(), "user-1", "item-1"))
        self.assertFalse(item_has_investment_accounts(self.conn.cursor(), "user-2", "item-1"))


if __name__ == "__main__":
    unittest.main()
