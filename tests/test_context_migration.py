import os
import tempfile
import unittest

import database


class ContextMigrationTests(unittest.TestCase):
    def setUp(self):
        self.original_db_file = database.DB_FILE
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        database.DB_FILE = os.path.join(self.tmpdir.name, "finance.db")

    def tearDown(self):
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def test_init_db_adds_context_schema(self):
        database.init_db()
        with database.get_db() as conn:
            tx_columns = {row["name"] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()}
            self.assertIn("trip_id", tx_columns)
            self.assertIn("rental_property_id", tx_columns)

            tables = {
                row["name"]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
            }
            self.assertIn("trips", tables)
            self.assertIn("rental_properties", tables)
            self.assertIn("rental_property_match_rules", tables)

    def test_migrates_existing_travel_and_rentals_idempotently(self):
        database.init_db()
        with database.get_db() as conn:
            conn.execute(
                """
                INSERT INTO transactions
                (transaction_id, date, type, merchant, amount, direction, account_name, note, subtype, reviewed, user_id)
                VALUES
                ('travel_1', '2026-05-01', 'Travel', 'Airline', 300, 'outflow', 'a1', '2026 Japan', 'Flight', 1, 'u1'),
                ('travel_2', '2026-05-02', 'Travel', 'Hotel', 500, 'outflow', 'a1', '2026 Japan', 'Hotel', 1, 'u1'),
                ('rental_1', '2026-06-01', 'Rentals', 'Bank', 2400, 'outflow', 'a1', 'Fremont Condo', 'Mortgage', 1, 'u1')
                """
            )
            conn.commit()

        database.init_db()
        database.init_db()

        with database.get_db() as conn:
            trips = conn.execute("SELECT id, name, year FROM trips WHERE user_id = 'u1'").fetchall()
            props = conn.execute("SELECT id, name FROM rental_properties WHERE user_id = 'u1'").fetchall()
            self.assertEqual(len(trips), 1)
            self.assertEqual((trips[0]["name"], trips[0]["year"]), ("Japan", 2026))
            self.assertEqual(len(props), 1)
            self.assertEqual(props[0]["name"], "Fremont Condo")

            rows = conn.execute(
                "SELECT transaction_id, note, subtype, reviewed, trip_id, rental_property_id FROM transactions ORDER BY transaction_id"
            ).fetchall()
            by_id = {row["transaction_id"]: row for row in rows}
            self.assertEqual(by_id["travel_1"]["trip_id"], trips[0]["id"])
            self.assertEqual(by_id["travel_2"]["trip_id"], trips[0]["id"])
            self.assertEqual(by_id["rental_1"]["rental_property_id"], props[0]["id"])
            self.assertEqual(by_id["travel_1"]["note"], "2026 Japan")
            self.assertEqual(by_id["rental_1"]["subtype"], "Mortgage")
            self.assertEqual(by_id["travel_1"]["reviewed"], 1)


if __name__ == "__main__":
    unittest.main()
