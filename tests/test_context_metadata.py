import os
import tempfile
import unittest

import database
from server import app


class ContextMetadataApiTests(unittest.TestCase):
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
            conn.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = "u1"

    def tearDown(self):
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def test_trip_crud_and_soft_archive(self):
        created = self.client.post("/api/trips", json={"name": "Japan", "year": 2026}).get_json()
        self.assertEqual(created["name"], "Japan")
        self.assertEqual(created["year"], 2026)

        duplicate = self.client.post("/api/trips", json={"name": " japan ", "year": "2026"})
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("2026 japan", duplicate.get_json()["error"])

        trip_id = created["id"]
        updated = self.client.patch(
            f"/api/trips/{trip_id}",
            json={"name": "Japan Family", "year": 2026, "status": "active"},
        ).get_json()
        self.assertEqual(updated["name"], "Japan Family")

        with database.get_db() as conn:
            conn.execute(
                """
                INSERT INTO transactions
                (transaction_id, date, type, merchant, amount, direction, account_name, trip_id, user_id)
                VALUES ('tx1', '2026-05-01', 'Travel', 'Airline', 100, 'outflow', 'a1', ?, 'u1')
                """,
                (trip_id,),
            )
            conn.commit()

        deleted = self.client.delete(f"/api/trips/{trip_id}").get_json()
        self.assertEqual(deleted["status"], "archived")
        trips = self.client.get("/api/trips").get_json()
        self.assertEqual(trips[0]["status"], "archived")

    def test_rental_property_crud_and_soft_archive(self):
        created = self.client.post(
            "/api/rental_properties",
            json={"name": "Fremont Condo", "city": "Fremont", "state": "CA"},
        ).get_json()
        self.assertEqual(created["name"], "Fremont Condo")
        self.assertEqual(created["active"], 1)

        property_id = created["id"]
        updated = self.client.patch(
            f"/api/rental_properties/{property_id}",
            json={"name": "Fremont Condo", "city": "Fremont", "state": "CA", "active": 1},
        ).get_json()
        self.assertEqual(updated["city"], "Fremont")

        with database.get_db() as conn:
            conn.execute(
                """
                INSERT INTO transactions
                (transaction_id, date, type, merchant, amount, direction, account_name, rental_property_id, user_id)
                VALUES ('tx1', '2026-06-01', 'Rentals', 'Bank', 2000, 'outflow', 'a1', ?, 'u1')
                """,
                (property_id,),
            )
            conn.commit()

        deleted = self.client.delete(f"/api/rental_properties/{property_id}").get_json()
        self.assertEqual(deleted["status"], "archived")
        props = self.client.get("/api/rental_properties").get_json()
        self.assertEqual(props[0]["active"], 0)


if __name__ == "__main__":
    unittest.main()
