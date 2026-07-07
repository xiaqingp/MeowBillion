import os
import tempfile
import unittest

import database
from server import app


class TransactionAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.original_db_file = database.DB_FILE
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        database.DB_FILE = os.path.join(self.tmpdir.name, "finance.db")
        database.init_db()
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()
        with database.get_db() as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, password_hash, display_name, role, created_at)
                VALUES ('u1', 'u1@example.com', 'x', 'User One', 'admin', datetime('now'))
                """
            )
            conn.execute("INSERT INTO trips (id, user_id, name, year) VALUES ('trip_1', 'u1', 'Japan', 2026)")
            conn.execute("INSERT INTO rental_properties (id, user_id, name) VALUES ('rprop_1', 'u1', 'Fremont Condo')")
            conn.execute(
                """
                INSERT INTO transactions
                (transaction_id, date, type, merchant, amount, direction, account_name, subtype, reviewed, pending, user_id)
                VALUES
                ('travel_tx', '2026-05-01', 'Travel', 'Airline', 100, 'outflow', 'a1', 'Flight', 0, 0, 'u1'),
                ('rental_tx', '2026-06-01', 'Rentals', 'Bank', 2000, 'outflow', 'a1', 'Mortgage', 0, 0, 'u1'),
                ('other_tx', '2026-07-01', 'Other', 'Store', 50, 'outflow', 'a1', '', 0, 0, 'u1')
                """
            )
            conn.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = "u1"

    def tearDown(self):
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def test_transactions_return_assignment_fields(self):
        self.client.post(
            "/api/update_transaction_assignment",
            json={"transaction_id": "travel_tx", "trip_id": "trip_1"},
        )
        data = self.client.get("/api/transactions?reviewed_filter=all").get_json()
        tx = next(row for row in data["transactions"] if row["TransactionID"] == "travel_tx")
        self.assertEqual(tx["TripID"], "trip_1")
        self.assertEqual(tx["TripName"], "Japan")
        self.assertEqual(tx["TripYear"], 2026)
        self.assertEqual(tx["RentalPropertyID"], "")

    def test_update_assignment_does_not_change_reviewed(self):
        res = self.client.post(
            "/api/update_transaction_assignment",
            json={"transaction_id": "rental_tx", "rental_property_id": "rprop_1"},
        ).get_json()
        self.assertEqual(res["status"], "success")
        with database.get_db() as conn:
            row = conn.execute(
                "SELECT reviewed, trip_id, rental_property_id FROM transactions WHERE transaction_id = 'rental_tx'"
            ).fetchone()
        self.assertEqual(row["reviewed"], 0)
        self.assertIsNone(row["trip_id"])
        self.assertEqual(row["rental_property_id"], "rprop_1")

    def test_review_clears_irrelevant_assignment_fields(self):
        res = self.client.post(
            "/api/update_transaction",
            json={
                "transaction_id": "travel_tx",
                "type": "Travel",
                "subtype": "Flight",
                "is_b": "n",
                "ratio": 1,
                "mown": 0,
                "note": "",
                "trip_id": "trip_1",
                "rental_property_id": "rprop_1",
            },
        ).get_json()
        self.assertEqual(res["status"], "success")
        with database.get_db() as conn:
            row = conn.execute(
                "SELECT reviewed, trip_id, rental_property_id FROM transactions WHERE transaction_id = 'travel_tx'"
            ).fetchone()
        self.assertEqual(row["reviewed"], 1)
        self.assertEqual(row["trip_id"], "trip_1")
        self.assertIsNone(row["rental_property_id"])


if __name__ == "__main__":
    unittest.main()
