import os
import tempfile
import unittest

import database
from server import app


class ReportsV2Tests(unittest.TestCase):
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
                (transaction_id, date, type, merchant, amount, direction, account_name, subtype, note,
                 reviewed, pending, ipay, trip_id, rental_property_id, user_id)
                VALUES
                ('travel_1', '2026-05-01', 'Travel', 'Airline', 100, 'outflow', 'a1', 'Flight', 'old note A', 1, 0, -100, 'trip_1', NULL, 'u1'),
                ('travel_2', '2026-05-02', 'Travel', 'Hotel', 200, 'outflow', 'a1', 'Hotel', 'old note B', 1, 0, -200, 'trip_1', NULL, 'u1'),
                ('travel_refund', '2026-05-03', 'Travel', 'Refund', 50, 'inflow', 'a1', 'Hotel', 'refund note', 1, 0, 50, 'trip_1', NULL, 'u1'),
                ('travel_reimbursement', '2026-05-04', 'Travel', 'Work hotel', 125, 'outflow', 'a1', 'Hotel', 'reimbursable', 1, 0, -125, 'trip_1', NULL, 'u1'),
                ('travel_unassigned', '2026-06-01', 'Travel', 'Taxi', 50, 'outflow', 'a1', 'Transport', '', 1, 0, -50, NULL, NULL, 'u1'),
                ('rental_1', '2026-06-01', 'Rentals', 'Bank', 2400, 'outflow', 'a1', 'Mortgage', 'old property A', 1, 0, -2400, NULL, 'rprop_1', 'u1'),
                ('rental_2', '2026-06-02', 'Rentals', 'Tenant', 3000, 'inflow', 'a1', 'Rent', 'old property B', 1, 0, 3000, NULL, 'rprop_1', 'u1'),
                ('rental_unassigned', '2026-06-03', 'Rentals', 'Repair', 150, 'outflow', 'a1', 'Maintenance', '', 1, 0, -150, NULL, NULL, 'u1')
                """
            )
            conn.execute("UPDATE transactions SET is_reimbursement = 1 WHERE transaction_id = 'travel_reimbursement'")
            conn.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = "u1"

    def tearDown(self):
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def test_travel_analysis_groups_by_trip_id_not_note(self):
        data = self.client.get("/api/travel_analysis").get_json()
        trips = [trip for year in data["years"] for trip in year["trips"]]
        japan = next(trip for trip in trips if trip["trip_id"] == "trip_1")
        unassigned = next(trip for trip in trips if trip["trip"] == "Unassigned Travel 2026")
        self.assertEqual(japan["trip"], "Japan")
        self.assertEqual(japan["count"], 3)
        self.assertAlmostEqual(japan["total"], 250)
        reimbursement = next(tx for tx in japan["transactions"] if tx["transaction_id"] == "travel_reimbursement")
        self.assertEqual(reimbursement["is_reimbursement"], 1)
        self.assertEqual(len(japan["transactions"]), 4)
        refund = next(tx for tx in japan["transactions"] if tx["transaction_id"] == "travel_refund")
        self.assertAlmostEqual(refund["amount"], -50)
        self.assertEqual(unassigned["count"], 1)

    def test_rental_analysis_groups_by_property_id_not_note(self):
        data = self.client.get("/api/rental_analysis").get_json()
        prop = next(row for row in data["properties"] if row["property_id"] == "rprop_1")
        unassigned = next(row for row in data["properties"] if row["property"] == "Unassigned Rental Property")
        self.assertEqual(prop["property"], "Fremont Condo")
        self.assertEqual(prop["count"], 2)
        self.assertAlmostEqual(prop["income"], 3000)
        self.assertAlmostEqual(prop["expense"], 2400)
        self.assertEqual(unassigned["count"], 1)


if __name__ == "__main__":
    unittest.main()
