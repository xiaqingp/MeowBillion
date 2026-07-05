import sqlite3
import unittest

from classifier import infer_transaction_classification_from_history, normalize_merchant_key


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE transactions (
            transaction_id TEXT PRIMARY KEY,
            merchant TEXT,
            type TEXT,
            subtype TEXT,
            direction TEXT,
            reviewed INTEGER
        )
        """
    )
    return conn


class MerchantHistoryClassificationTests(unittest.TestCase):
    def test_uses_stable_reviewed_merchant_history(self):
        conn = make_conn()
        for idx in range(3):
            conn.execute(
                "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?)",
                (f"tx_{idx}", "Trader Joe's", "Groceries", "Food", "outflow", 1)
            )

        learned = infer_transaction_classification_from_history(conn.cursor(), "TRADER JOES", "outflow")

        self.assertEqual(learned["type"], "Groceries")
        self.assertEqual(learned["subtype"], "Food")
        self.assertEqual(learned["match_count"], 3)

    def test_requires_enough_examples(self):
        conn = make_conn()
        for idx in range(2):
            conn.execute(
                "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?)",
                (f"tx_{idx}", "Costco", "Groceries", "", "outflow", 1)
            )

        self.assertIsNone(infer_transaction_classification_from_history(conn.cursor(), "Costco", "outflow"))

    def test_rejects_conflicting_history(self):
        conn = make_conn()
        rows = [
            ("tx_1", "Amazon", "Shopping", "", "outflow", 1),
            ("tx_2", "Amazon", "Shopping", "", "outflow", 1),
            ("tx_3", "Amazon", "Subscription", "", "outflow", 1),
        ]
        conn.executemany("INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?)", rows)

        self.assertIsNone(infer_transaction_classification_from_history(conn.cursor(), "Amazon", "outflow"))

    def test_normalizes_punctuation_and_spacing(self):
        self.assertEqual(normalize_merchant_key(" Trader-Joe's  #123 "), "trader joes 123")


if __name__ == "__main__":
    unittest.main()
