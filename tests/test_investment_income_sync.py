import datetime
import json
import sqlite3
import unittest

from routes_plaid import (
    apply_plaid_investment_income_updates,
    fetch_plaid_investment_transactions,
    get_investment_income_start_date,
)


class InvestmentIncomeSyncTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
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
            );
            CREATE TABLE sync_metadata (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    def tearDown(self):
        self.conn.close()

    def test_maps_only_approved_income_subtypes(self):
        rows = [
            self._tx("interest", "i1", -12.5),
            self._tx("interest receivable", "i2", -3),
            self._tx("dividend", "d1", -8),
            self._tx("qualified dividend", "d2", -9),
            self._tx("non-qualified dividend", "d3", -10),
            self._tx("dividend reinvestment", "skip1", 8),
            self._tx("buy", "skip2", 100),
        ]

        count = apply_plaid_investment_income_updates(
            self.conn.cursor(), "u1", rows
        )
        saved = self.conn.execute(
            "SELECT transaction_id, type, subtype, direction, ipay, reviewed, categories "
            "FROM transactions ORDER BY transaction_id"
        ).fetchall()

        self.assertEqual(count, 5)
        self.assertEqual([row["transaction_id"] for row in saved], ["d1", "d2", "d3", "i1", "i2"])
        self.assertEqual(
            [(row["type"], row["subtype"]) for row in saved],
            [
                ("Income", "Dividend"),
                ("Income", "Dividend"),
                ("Income", "Dividend"),
                ("Income", "Interest"),
                ("Income", "Interest"),
            ],
        )
        self.assertTrue(all(row["direction"] == "inflow" for row in saved))
        self.assertTrue(all(row["ipay"] > 0 for row in saved))
        self.assertTrue(all(row["reviewed"] == 0 for row in saved))
        self.assertIn("qualified dividend", saved[1]["categories"])
        config = json.loads(
            self.conn.execute(
                "SELECT value FROM app_config WHERE key = 'u1:categories_config'"
            ).fetchone()[0]
        )
        self.assertIn("Income", config["categories"])
        self.assertEqual(config["rules"]["Income"], ["Dividend", "Interest"])

    def test_upsert_is_idempotent_and_preserves_reviewed_fields(self):
        tx = self._tx("dividend", "d1", -8)
        cursor = self.conn.cursor()
        self.assertEqual(apply_plaid_investment_income_updates(cursor, "u1", [tx]), 1)
        self.conn.execute(
            "UPDATE transactions SET reviewed = 1, type = 'Other', subtype = 'Keep', note = 'Mine' "
            "WHERE transaction_id = 'd1'"
        )
        changed = dict(tx, amount=-10, name="Updated dividend")

        self.assertEqual(apply_plaid_investment_income_updates(cursor, "u1", [changed]), 0)
        row = self.conn.execute(
            "SELECT merchant, amount, type, subtype, note, reviewed FROM transactions WHERE transaction_id = 'd1'"
        ).fetchone()

        self.assertEqual(row["merchant"], "Updated dividend")
        self.assertEqual(row["amount"], 10)
        self.assertEqual((row["type"], row["subtype"], row["note"], row["reviewed"]), ("Other", "Keep", "Mine", 1))

    def test_first_window_starts_january_first_then_uses_90_days(self):
        today = datetime.date(2026, 7, 13)
        cursor = self.conn.cursor()

        self.assertEqual(
            get_investment_income_start_date(cursor, "u1", "item1", today),
            datetime.date(2026, 1, 1),
        )
        self.conn.execute(
            "INSERT INTO sync_metadata (key, value) VALUES (?, ?)",
            ("u1:item1:investment_income_last_sync_date", "2026-07-12"),
        )
        self.assertEqual(
            get_investment_income_start_date(cursor, "u1", "item1", today),
            datetime.date(2026, 4, 14),
        )

    def test_fetches_all_investment_transaction_pages(self):
        class Response:
            def __init__(self, rows, total):
                self.rows = rows
                self.total = total

            def to_dict(self):
                return {
                    "investment_transactions": self.rows,
                    "total_investment_transactions": self.total,
                }

        class Client:
            def __init__(self):
                self.calls = 0

            def investments_transactions_get(self, request):
                self.calls += 1
                if self.calls == 1:
                    return Response([{"investment_transaction_id": "a"}, {"investment_transaction_id": "b"}], 3)
                return Response([{"investment_transaction_id": "c"}], 3)

        client = Client()
        rows = fetch_plaid_investment_transactions(
            client,
            "token",
            datetime.date(2026, 1, 1),
            datetime.date(2026, 7, 13),
        )

        self.assertEqual(client.calls, 2)
        self.assertEqual([row["investment_transaction_id"] for row in rows], ["a", "b", "c"])

    @staticmethod
    def _tx(subtype, tx_id, amount):
        return {
            "investment_transaction_id": tx_id,
            "account_id": "acct1",
            "date": "2026-06-30",
            "name": subtype.title(),
            "amount": amount,
            "type": "cash",
            "subtype": subtype,
            "iso_currency_code": "USD",
        }


if __name__ == "__main__":
    unittest.main()
