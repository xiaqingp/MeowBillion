import os
import tempfile
import unittest
from flask import Flask

import database
from auth import auth_bp


class AuthSetupTests(unittest.TestCase):
    def test_setup_claims_existing_data(self):
        original_db = database.DB_FILE
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
                database.DB_FILE = os.path.join(tmpdir, "finance.db")
                database.init_db()
                with database.get_db() as conn:
                    conn.execute(
                        "INSERT INTO transactions (transaction_id, date, merchant, amount, direction, account_name) VALUES ('tx1', '2026-01-01', 'Store', 1, 'outflow', 'Legacy')"
                    )
                    conn.commit()

                app = Flask(__name__)
                app.secret_key = "test"
                app.register_blueprint(auth_bp)
                client = app.test_client()
                res = client.post("/api/auth/setup", json={
                    "display_name": "Owner",
                    "email": "owner@example.com",
                    "password": "password123"
                })
                self.assertEqual(res.status_code, 200)

                with database.get_db() as conn:
                    user = conn.execute("SELECT id, role FROM users WHERE email = 'owner@example.com'").fetchone()
                    tx = conn.execute("SELECT user_id FROM transactions WHERE transaction_id = 'tx1'").fetchone()
                self.assertEqual(user["role"], "admin")
                self.assertEqual(tx["user_id"], user["id"])
        finally:
            database.DB_FILE = original_db


if __name__ == "__main__":
    unittest.main()
