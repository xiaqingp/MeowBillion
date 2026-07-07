import unittest
import sqlite3

from routes_plaid import apply_plaid_transaction_updates, summarize_sync_results


class PlaidSyncSummaryTests(unittest.TestCase):
    def test_success_when_all_items_succeed(self):
        self.assertEqual(summarize_sync_results([{"item_id": "a"}], []), "success")

    def test_partial_success_when_some_items_fail(self):
        self.assertEqual(summarize_sync_results([{"item_id": "a"}], [{"item_id": "b"}]), "partial_success")

    def test_failed_when_all_items_fail(self):
        self.assertEqual(summarize_sync_results([], [{"item_id": "b"}]), "failed")

    def test_success_when_no_items(self):
        self.assertEqual(summarize_sync_results([], []), "success")

    def test_modified_transaction_updates_raw_fields_and_preserves_review_context(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE transactions (
                transaction_id TEXT PRIMARY KEY,
                date TEXT,
                authorized_date TEXT,
                type TEXT,
                merchant TEXT,
                amount REAL,
                direction TEXT,
                pending INTEGER,
                categories TEXT,
                location TEXT,
                payment_channel TEXT,
                account_name TEXT,
                is_b TEXT,
                ratio REAL,
                ipay REAL,
                bpay REAL,
                mown REAL,
                note TEXT,
                subtype TEXT,
                trip_id TEXT,
                rental_property_id TEXT,
                reviewed INTEGER,
                prediction_source TEXT,
                prediction_confidence REAL,
                prediction_reason TEXT,
                imported_from_legacy INTEGER DEFAULT 0,
                legacy_matched INTEGER DEFAULT 0,
                user_id TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO transactions
            (transaction_id, date, authorized_date, type, merchant, amount, direction, pending,
             categories, location, payment_channel, account_name, is_b, ratio, ipay, bpay, mown,
             note, subtype, trip_id, rental_property_id, reviewed, user_id)
            VALUES
            ('tx1', '2026-07-01', '2026-07-01', 'Travel', 'Old Merchant', 10, 'outflow', 0,
             '[]', '{}', 'other', 'old_account', 'n', 1, -10, 0, 0, 'Keep note',
             'Flight', 'trip_1', NULL, 1, 'u1')
            """
        )

        updates = {
            "added": [],
            "removed": [],
            "modified": [{
                "transaction_id": "tx1",
                "date": "2026-07-02",
                "authorized_date": "2026-07-01",
                "merchant_name": "New Merchant",
                "amount": 12.34,
                "pending": False,
                "account_id": "new_account",
                "payment_channel": "online",
                "location": {},
                "personal_finance_category": {"primary": "GENERAL_MERCHANDISE", "detailed": "GENERAL_MERCHANDISE_OTHER"}
            }]
        }
        count = apply_plaid_transaction_updates(conn.cursor(), "u1", updates, ["Travel", "Other"])
        row = conn.execute("SELECT * FROM transactions WHERE transaction_id = 'tx1'").fetchone()

        self.assertEqual(count, 0)
        self.assertEqual(row["date"], "2026-07-02")
        self.assertEqual(row["merchant"], "New Merchant")
        self.assertEqual(row["amount"], 12.34)
        self.assertEqual(row["account_name"], "new_account")
        self.assertEqual(row["type"], "Travel")
        self.assertEqual(row["subtype"], "Flight")
        self.assertEqual(row["note"], "Keep note")
        self.assertEqual(row["trip_id"], "trip_1")
        self.assertEqual(row["reviewed"], 1)


if __name__ == "__main__":
    unittest.main()
