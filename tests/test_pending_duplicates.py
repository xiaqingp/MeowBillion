import sqlite3
import unittest

from routes_plaid import find_pending_duplicate, merchant_names_match


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE transactions (
            transaction_id TEXT PRIMARY KEY,
            date TEXT,
            authorized_date TEXT,
            merchant TEXT,
            amount REAL,
            direction TEXT,
            account_name TEXT,
            pending INTEGER,
            type TEXT,
            subtype TEXT,
            is_b TEXT,
            ratio REAL,
            ipay REAL,
            bpay REAL,
            mown REAL,
            note TEXT,
            reviewed INTEGER,
            trip_id TEXT,
            rental_property_id TEXT,
            imported_from_legacy INTEGER,
            legacy_matched INTEGER
        )
        """
    )
    return conn


class PendingDuplicateTests(unittest.TestCase):
    def test_matches_posted_transaction_to_pending_by_normalized_merchant(self):
        conn = make_conn()
        conn.execute(
            """
            INSERT INTO transactions VALUES (
                'pending_1', '2026-07-01', '2026-07-01', 'T T Supermarket',
                82.91, 'outflow', 'account_1', 1, 'Groceries', '',
                'n', 1.0, -82.91, 0.0, 0.0, '', 1, NULL, NULL, 0, 0
            )
            """
        )

        duplicate = find_pending_duplicate(
            conn.cursor(),
            "posted_1",
            "T&t Supermarket",
            82.91,
            "outflow",
            "account_1",
            "2026-07-02",
            "2026-07-01"
        )

        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate["transaction_id"], "pending_1")

    def test_allows_posted_merchant_suffix(self):
        self.assertTrue(merchant_names_match("CBP I-94 PAY.GOV IN", "CBP I-94 PAY.GOV"))


if __name__ == "__main__":
    unittest.main()
