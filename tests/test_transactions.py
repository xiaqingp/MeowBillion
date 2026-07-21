import sqlite3
import unittest

from routes_transactions import apply_stable_history_to_unreviewed


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
            imported_from_legacy INTEGER DEFAULT 0,
            prediction_source TEXT DEFAULT '',
            prediction_confidence REAL DEFAULT 0,
            prediction_reason TEXT DEFAULT '',
            user_id TEXT
        )
        """
    )
    return conn


class StableHistoryAutoApplyTests(unittest.TestCase):
    def test_auto_apply_keeps_targets_unreviewed_and_skips_pending(self):
        conn = make_conn()
        rows = [
            ("r1", "Store A", "Travel", "Flight", "outflow", 1, 0, "u1"),
            ("r2", "Store A", "Travel", "Flight", "outflow", 1, 0, "u1"),
            ("r3", "Store A", "Travel", "Flight", "outflow", 1, 0, "u1"),
            ("u1", "Store A", "Other", "", "outflow", 0, 0, "u1"),
            ("p1", "Store A", "Other", "", "outflow", 0, 1, "u1"),
            ("d1", "Store A", "Other", "", "inflow", 0, 0, "u1"),
        ]
        conn.executemany(
            """
            INSERT INTO transactions
            (transaction_id, merchant, type, subtype, direction, reviewed, pending, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )

        count = apply_stable_history_to_unreviewed(
            conn.cursor(), "Store A", "outflow", "u1", ["Other", "Travel"]
        )

        self.assertEqual(count, 1)
        updated = conn.execute("SELECT type, subtype, reviewed FROM transactions WHERE transaction_id='u1'").fetchone()
        pending = conn.execute("SELECT type, reviewed FROM transactions WHERE transaction_id='p1'").fetchone()
        other_direction = conn.execute("SELECT type FROM transactions WHERE transaction_id='d1'").fetchone()
        self.assertEqual((updated["type"], updated["subtype"], updated["reviewed"]), ("Travel", "Flight", 0))
        self.assertEqual((pending["type"], pending["reviewed"]), ("Other", 0))
        self.assertEqual(other_direction["type"], "Other")

    def test_auto_apply_cannot_restore_deleted_category(self):
        conn = make_conn()
        for idx in range(3):
            conn.execute(
                """
                INSERT INTO transactions
                (transaction_id, merchant, type, subtype, direction, reviewed, pending, user_id)
                VALUES (?, 'Old Store', 'Deleted Category', 'Old Subtype', 'outflow', 1, 0, 'u1')
                """,
                (f"r{idx}",),
            )
        conn.execute(
            """
            INSERT INTO transactions
            (transaction_id, merchant, type, subtype, direction, reviewed, pending, user_id)
            VALUES ('target', 'Old Store', 'Other', '', 'outflow', 0, 0, 'u1')
            """
        )

        apply_stable_history_to_unreviewed(
            conn.cursor(), "Old Store", "outflow", "u1", ["Other", "Travel"]
        )

        target = conn.execute("SELECT type, subtype FROM transactions WHERE transaction_id='target'").fetchone()
        self.assertEqual((target["type"], target["subtype"]), ("Other", ""))


if __name__ == "__main__":
    unittest.main()
