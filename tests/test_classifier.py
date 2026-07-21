import sqlite3
import unittest

from classifier import constrain_category_to_config, infer_transaction_classification_from_history, normalize_merchant_key, predict_transaction_classification


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
            reviewed INTEGER,
            pending INTEGER DEFAULT 0,
            user_id TEXT DEFAULT 'u1'
        )
        """
    )
    return conn


class MerchantHistoryClassificationTests(unittest.TestCase):
    def test_uses_stable_reviewed_merchant_history(self):
        conn = make_conn()
        for idx in range(3):
            conn.execute(
                "INSERT INTO transactions (transaction_id, merchant, type, subtype, direction, reviewed) VALUES (?, ?, ?, ?, ?, ?)",
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
                "INSERT INTO transactions (transaction_id, merchant, type, subtype, direction, reviewed) VALUES (?, ?, ?, ?, ?, ?)",
                (f"tx_{idx}", "Costco", "Groceries", "", "outflow", 1)
            )

        self.assertIsNone(infer_transaction_classification_from_history(conn.cursor(), "Costco", "outflow"))

    def test_uses_most_frequent_history_combination(self):
        conn = make_conn()
        rows = [
            ("tx_1", "Amazon", "Shopping", "", "outflow", 1),
            ("tx_2", "Amazon", "Shopping", "", "outflow", 1),
            ("tx_3", "Amazon", "Shopping", "", "outflow", 1),
            ("tx_4", "Amazon", "Subscription", "", "outflow", 1),
            ("tx_5", "Amazon", "Subscription", "", "outflow", 1),
        ]
        conn.executemany("INSERT INTO transactions (transaction_id, merchant, type, subtype, direction, reviewed) VALUES (?, ?, ?, ?, ?, ?)", rows)

        learned = infer_transaction_classification_from_history(conn.cursor(), "Amazon", "outflow")

        self.assertEqual((learned["type"], learned["subtype"]), ("Shopping", ""))
        self.assertEqual(learned["match_count"], 3)
        self.assertEqual(learned["total_count"], 5)

    def test_tied_history_uses_first_seen_combination(self):
        conn = make_conn()
        rows = [
            (f"shopping_{idx}", "Amazon", "Shopping", "", "outflow", 1)
            for idx in range(3)
        ] + [
            (f"subscription_{idx}", "Amazon", "Subscription", "", "outflow", 1)
            for idx in range(3)
        ]
        conn.executemany("INSERT INTO transactions (transaction_id, merchant, type, subtype, direction, reviewed) VALUES (?, ?, ?, ?, ?, ?)", rows)

        learned = infer_transaction_classification_from_history(conn.cursor(), "Amazon", "outflow")

        self.assertEqual((learned["type"], learned["subtype"]), ("Shopping", ""))
        self.assertEqual(learned["match_count"], 3)

    def test_normalizes_punctuation_and_spacing(self):
        self.assertEqual(normalize_merchant_key(" Trader-Joe's  #123 "), "trader joes 123")

    def test_constrains_prediction_to_user_categories(self):
        self.assertEqual(constrain_category_to_config("Groceries", ["Other", "Rentals", "Travel"]), "Other")
        self.assertEqual(constrain_category_to_config("travel", ["Other", "Rentals", "Travel"]), "Travel")

    def test_prediction_falls_back_to_plaid_category(self):
        conn = make_conn()
        prediction = predict_transaction_classification(
            conn.cursor(), "TRAVEL", "TRAVEL_FLIGHTS", "Any Airline", "outflow", ["Other", "Travel"]
        )

        self.assertEqual(prediction["type"], "Travel")
        self.assertEqual(prediction["source"], "plaid_category")

    def test_prediction_falls_back_to_other(self):
        conn = make_conn()
        prediction = predict_transaction_classification(
            conn.cursor(), "GENERAL_SERVICES", "GENERAL_SERVICES_OTHER", "Mystery", "outflow", ["Other", "Travel"]
        )

        self.assertEqual(prediction["type"], "Other")
        self.assertEqual(prediction["source"], "fallback")

    def test_history_prediction_is_constrained_to_user_categories(self):
        conn = make_conn()
        for idx in range(3):
            conn.execute(
                "INSERT INTO transactions (transaction_id, merchant, type, subtype, direction, reviewed) VALUES (?, ?, ?, ?, ?, ?)",
                (f"tx_{idx}", "Old Store", "Deleted Category", "Old Subtype", "outflow", 1),
            )

        prediction = predict_transaction_classification(
            conn.cursor(),
            "OTHER",
            "OTHER",
            "Old Store",
            "outflow",
            ["Other", "Travel"],
            {"Travel": ["Flight"]},
        )

        self.assertEqual(prediction["type"], "Other")
        self.assertEqual(prediction["subtype"], "")

    def test_history_subcategory_is_constrained_to_user_rules(self):
        conn = make_conn()
        for idx in range(3):
            conn.execute(
                "INSERT INTO transactions (transaction_id, merchant, type, subtype, direction, reviewed) VALUES (?, ?, ?, ?, ?, ?)",
                (f"tx_{idx}", "Airline", "Travel", "Deleted Subtype", "outflow", 1),
            )

        prediction = predict_transaction_classification(
            conn.cursor(),
            "TRAVEL",
            "TRAVEL_FLIGHTS",
            "Airline",
            "outflow",
            ["Other", "Travel"],
            {"Travel": ["Flight"]},
        )

        self.assertEqual((prediction["type"], prediction["subtype"]), ("Travel", ""))

    def test_hardcoded_merchant_rules_removed(self):
        conn = make_conn()
        prediction = predict_transaction_classification(
            conn.cursor(), "GENERAL_SERVICES", "GENERAL_SERVICES_OTHER", "Amazon", "outflow", ["Other", "Shopping"]
        )

        self.assertEqual(prediction["type"], "Other")
        self.assertNotEqual(prediction["source"], "merchant_keyword")


if __name__ == "__main__":
    unittest.main()
