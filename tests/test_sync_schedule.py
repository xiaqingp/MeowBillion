import os
import tempfile
import unittest

import database
import server


class SyncScheduleTests(unittest.TestCase):
    def setUp(self):
        self.original_db = database.DB_FILE
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        database.DB_FILE = os.path.join(self.tmpdir.name, "finance.db")
        database.init_db()
        with database.get_db() as conn:
            conn.execute(
                "INSERT INTO users (id, email, password_hash, display_name, role, active, created_at) VALUES (?, ?, ?, ?, ?, 1, datetime('now'))",
                ("admin", "admin@example.com", "x", "Admin", "admin"),
            )
            conn.execute(
                "INSERT INTO users (id, email, password_hash, display_name, role, active, created_at) VALUES (?, ?, ?, ?, ?, 1, datetime('now'))",
                ("user", "user@example.com", "x", "User", "user"),
            )
            conn.commit()
        server.app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = server.app.test_client()

    def tearDown(self):
        database.DB_FILE = self.original_db
        self.tmpdir.cleanup()

    def login_as(self, user_id):
        with self.client.session_transaction() as session:
            session["user_id"] = user_id

    def test_admin_can_save_global_daily_sync_time(self):
        self.login_as("admin")

        initial = self.client.get("/api/sync_schedule")
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.get_json()["daily_sync_time"], "16:00")
        self.assertTrue(initial.get_json()["can_edit"])

        saved = self.client.post("/api/sync_schedule", json={"daily_sync_time": "18:30"})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["daily_sync_time"], "18:30")

        with database.get_db() as conn:
            value = conn.execute("SELECT value FROM app_config WHERE key = 'daily_sync_time'").fetchone()[0]
        self.assertEqual(value, "18:30")

    def test_non_admin_can_view_but_cannot_change_global_daily_sync_time(self):
        self.login_as("user")

        viewed = self.client.get("/api/sync_schedule")
        self.assertEqual(viewed.status_code, 200)
        self.assertEqual(viewed.get_json()["daily_sync_time"], "16:00")
        self.assertFalse(viewed.get_json()["can_edit"])

        denied = self.client.post("/api/sync_schedule", json={"daily_sync_time": "09:00"})
        self.assertEqual(denied.status_code, 403)

    def test_rejects_invalid_daily_sync_time(self):
        self.login_as("admin")

        response = self.client.post("/api/sync_schedule", json={"daily_sync_time": "25:00"})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
