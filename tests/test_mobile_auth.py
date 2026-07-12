import hashlib
import os
import tempfile
import unittest

import database
from auth import create_user
from server import app


class MobileAuthTests(unittest.TestCase):
    def setUp(self):
        self.original_db = database.DB_FILE
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        database.DB_FILE = os.path.join(self.tmpdir.name, "finance.db")
        database.init_db()
        app.config.update(TESTING=True, SECRET_KEY="test-mobile-auth")
        self.client = app.test_client()
        with database.get_db() as conn:
            self.owner_id = create_user(conn, "owner@example.com", "password123", "Owner", "admin")
            self.member_id = create_user(conn, "member@example.com", "password123", "Member", "user")
            conn.execute(
                """
                INSERT INTO transactions
                (transaction_id, user_id, date, merchant, amount, direction, account_name, type, subtype)
                VALUES ('owner-tx', ?, '2026-07-10', 'Owner Store', 10, 'outflow', 'Checking', 'Groceries', 'Restaurant')
                """,
                (self.owner_id,),
            )
            conn.execute(
                """
                INSERT INTO transactions
                (transaction_id, user_id, date, merchant, amount, direction, account_name)
                VALUES ('member-tx', ?, '2026-07-10', 'Member Store', 20, 'outflow', 'Checking')
                """,
                (self.member_id,),
            )
            conn.commit()

    def tearDown(self):
        database.DB_FILE = self.original_db
        self.tmpdir.cleanup()

    def mobile_login(self, email="owner@example.com"):
        response = self.client.post(
            "/api/auth/mobile/login",
            json={"email": email, "password": "password123", "device_name": "Pixel Test"},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["access_token"]

    def bearer_headers(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_mobile_login_issues_hashed_token_and_authorizes_only_its_user(self):
        token = self.mobile_login()

        with database.get_db() as conn:
            row = conn.execute(
                "SELECT token_hash, user_id, device_name FROM mobile_session_tokens"
            ).fetchone()

        self.assertEqual(row["user_id"], self.owner_id)
        self.assertEqual(row["device_name"], "Pixel Test")
        self.assertNotEqual(row["token_hash"], token)

        response = self.client.get("/api/transactions", headers=self.bearer_headers(token))
        self.assertEqual(response.status_code, 200)
        ids = [tx["TransactionID"] for tx in response.get_json()["transactions"]]
        self.assertEqual(ids, ["owner-tx"])

    def test_mobile_logout_revokes_token(self):
        token = self.mobile_login()

        response = self.client.post("/api/auth/mobile/logout", headers=self.bearer_headers(token))
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/api/transactions", headers=self.bearer_headers(token))
        self.assertEqual(response.status_code, 401)

    def test_mobile_category_options_and_subcategory_filter(self):
        token = self.mobile_login()
        headers = self.bearer_headers(token)

        options = self.client.get("/api/category_options", headers=headers)
        self.assertEqual(options.status_code, 200)
        self.assertIn("categories", options.get_json())
        self.assertIn("subcategories", options.get_json())

        response = self.client.get(
            "/api/transactions?reviewed_filter=all&subtype=Restaurant",
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [transaction["TransactionID"] for transaction in response.get_json()["transactions"]],
            ["owner-tx"],
        )

    def test_expired_mobile_token_is_rejected(self):
        token = self.mobile_login()
        with database.get_db() as conn:
            conn.execute(
                "UPDATE mobile_session_tokens SET expires_at = '2000-01-01T00:00:00+00:00'"
            )
            conn.commit()

        response = self.client.get("/api/transactions", headers=self.bearer_headers(token))
        self.assertEqual(response.status_code, 401)

    def test_mobile_session_list_does_not_expose_tokens_or_other_users(self):
        owner_token = self.mobile_login()
        self.mobile_login("member@example.com")

        response = self.client.get("/api/auth/mobile/sessions", headers=self.bearer_headers(owner_token))
        self.assertEqual(response.status_code, 200)
        sessions = response.get_json()["sessions"]

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["device_name"], "Pixel Test")
        self.assertNotIn("token_hash", sessions[0])

    def test_revoke_other_mobile_sessions_keeps_current_token_active(self):
        current_token = self.mobile_login()
        other_token = self.mobile_login()

        response = self.client.post(
            "/api/auth/mobile/sessions/revoke_others",
            headers=self.bearer_headers(current_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["revoked_count"], 1)
        self.assertEqual(self.client.get("/api/transactions", headers=self.bearer_headers(current_token)).status_code, 200)
        self.assertEqual(self.client.get("/api/transactions", headers=self.bearer_headers(other_token)).status_code, 401)

    def test_revoke_specific_mobile_session_requires_same_user(self):
        owner_token = self.mobile_login()
        target_token = self.mobile_login()
        with database.get_db() as conn:
            target_id = conn.execute(
                "SELECT id FROM mobile_session_tokens WHERE token_hash = ?",
                (hashlib.sha256(target_token.encode("utf-8")).hexdigest(),),
            ).fetchone()["id"]

        response = self.client.delete(f"/api/auth/mobile/sessions/{target_id}", headers=self.bearer_headers(owner_token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/transactions", headers=self.bearer_headers(target_token)).status_code, 401)


if __name__ == "__main__":
    unittest.main()
