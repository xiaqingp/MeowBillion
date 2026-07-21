import json
import os
import tempfile
import unittest

import database


class CategoryPredictionMigrationTests(unittest.TestCase):
    def test_startup_backfill_is_user_scoped_and_respects_each_users_categories(self):
        original_db_file = database.DB_FILE
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
                database.DB_FILE = os.path.join(tmpdir, "finance.db")
                database.init_db()
                with database.get_db() as conn:
                    for user_id in ("u1", "u2"):
                        conn.execute(
                            """
                            INSERT INTO users
                                (id, email, password_hash, display_name, role, active, created_at)
                            VALUES (?, ?, 'x', ?, 'user', 1, datetime('now'))
                            """,
                            (user_id, f"{user_id}@example.com", user_id),
                        )
                    conn.execute(
                        "INSERT INTO app_config (key, value) VALUES (?, ?)",
                        ("u1:categories_config", json.dumps({"categories": ["Other", "Travel"], "rules": {}})),
                    )
                    conn.execute(
                        "INSERT INTO app_config (key, value) VALUES (?, ?)",
                        ("u2:categories_config", json.dumps({"categories": ["Other", "Rentals"], "rules": {}})),
                    )
                    for user_id, category in (("u1", "Travel"), ("u2", "Rentals")):
                        for idx in range(3):
                            conn.execute(
                                """
                                INSERT INTO transactions
                                    (transaction_id, date, type, subtype, merchant, amount, direction,
                                     account_name, reviewed, pending, imported_from_legacy, user_id)
                                VALUES (?, '2026-07-01', ?, '', 'Shared Merchant', 10, 'outflow',
                                        ?, 1, 0, 0, ?)
                                """,
                                (f"{user_id}_reviewed_{idx}", category, f"{user_id}_account", user_id),
                            )
                        conn.execute(
                            """
                            INSERT INTO transactions
                                (transaction_id, date, type, merchant, amount, direction, account_name,
                                 reviewed, pending, imported_from_legacy, user_id)
                            VALUES (?, '2026-07-02', '', 'Shared Merchant', 10, 'outflow',
                                    ?, 0, 0, 0, ?)
                            """,
                            (f"{user_id}_target", f"{user_id}_account", user_id),
                        )
                    conn.execute(
                        """
                        INSERT INTO transactions
                            (transaction_id, date, type, merchant, amount, direction, account_name,
                             reviewed, pending, imported_from_legacy, user_id)
                        VALUES
                            ('u1_transfer_candidate', '2026-07-03', 'Other', 'Move', 99, 'outflow',
                             'u1_account', 0, 0, 0, 'u1'),
                            ('u2_transfer_candidate', '2026-07-03', 'Other', 'Move', 99, 'inflow',
                             'u2_account', 0, 0, 0, 'u2')
                        """
                    )
                    conn.commit()

                database.init_db()

                with database.get_db() as conn:
                    rows = conn.execute(
                        "SELECT transaction_id, type FROM transactions WHERE transaction_id LIKE '%_target' ORDER BY transaction_id"
                    ).fetchall()
                self.assertEqual(
                    [(row["transaction_id"], row["type"]) for row in rows],
                    [("u1_target", "Travel"), ("u2_target", "Rentals")],
                )
                with database.get_db() as conn:
                    transfer_types = conn.execute(
                        """
                        SELECT transaction_id, type
                        FROM transactions
                        WHERE transaction_id LIKE '%_transfer_candidate'
                        ORDER BY transaction_id
                        """
                    ).fetchall()
                self.assertEqual(
                    [(row["transaction_id"], row["type"]) for row in transfer_types],
                    [("u1_transfer_candidate", "Other"), ("u2_transfer_candidate", "Other")],
                )
        finally:
            database.DB_FILE = original_db_file


if __name__ == "__main__":
    unittest.main()
