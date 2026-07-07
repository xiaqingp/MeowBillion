import os
import tempfile
import unittest

import database
from routes_metadata import apply_rental_property_rules_to_transaction
from server import app


class RentalPropertyRulesTests(unittest.TestCase):
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
            conn.execute(
                """
                INSERT INTO accounts (account_id, name, institution_name, user_id)
                VALUES ('acct_1', 'Checking', 'Bank', 'u1')
                """
            )
            conn.execute(
                """
                INSERT INTO rental_properties (id, user_id, name)
                VALUES ('rprop_1', 'u1', 'Fremont Condo')
                """
            )
            conn.execute(
                """
                INSERT INTO rental_property_match_rules
                (id, user_id, rental_property_id, name, merchant_contains, account_name_contains,
                 direction, amount_min, amount_max, default_subtype, enabled)
                VALUES ('rule_1', 'u1', 'rprop_1', 'Mortgage rule', 'mortgage', '', 'outflow', 1000, 5000, 'Mortgage', 1)
                """
            )
            conn.execute(
                """
                INSERT INTO transactions
                (transaction_id, date, type, merchant, amount, direction, account_name, reviewed, imported_from_legacy, user_id)
                VALUES
                ('tx_unreviewed', '2026-06-01', 'Other', 'Mortgage Payment', 2400, 'outflow', 'acct_1', 0, 0, 'u1'),
                ('tx_reviewed', '2026-06-02', 'Other', 'Mortgage Payment', 2400, 'outflow', 'acct_1', 1, 0, 'u1')
                """
            )
            conn.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = "u1"

    def tearDown(self):
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def test_rule_predicts_rentals_property_for_unreviewed_transaction(self):
        with database.get_db() as conn:
            changed = apply_rental_property_rules_to_transaction(conn.cursor(), "u1", "tx_unreviewed")
            conn.commit()
            row = conn.execute(
                """
                SELECT type, subtype, rental_property_id, reviewed, prediction_source
                FROM transactions WHERE transaction_id = 'tx_unreviewed'
                """
            ).fetchone()
        self.assertTrue(changed)
        self.assertEqual(row["type"], "Rentals")
        self.assertEqual(row["subtype"], "Mortgage")
        self.assertEqual(row["rental_property_id"], "rprop_1")
        self.assertEqual(row["reviewed"], 0)
        self.assertEqual(row["prediction_source"], "rental_property_rule")

    def test_rule_does_not_modify_reviewed_transaction(self):
        with database.get_db() as conn:
            changed = apply_rental_property_rules_to_transaction(conn.cursor(), "u1", "tx_reviewed")
            conn.commit()
            row = conn.execute(
                "SELECT type, rental_property_id, reviewed FROM transactions WHERE transaction_id = 'tx_reviewed'"
            ).fetchone()
        self.assertFalse(changed)
        self.assertEqual(row["type"], "Other")
        self.assertIsNone(row["rental_property_id"])
        self.assertEqual(row["reviewed"], 1)

    def test_apply_endpoint_returns_updated_count(self):
        res = self.client.post(
            "/api/rental_property_match_rules/apply",
            json={"rental_property_id": "rprop_1"},
        ).get_json()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["updated_count"], 1)

    def test_rule_crud(self):
        created = self.client.post(
            "/api/rental_property_match_rules",
            json={
                "rental_property_id": "rprop_1",
                "name": "HOA",
                "merchant_contains": "hoa",
                "direction": "outflow",
                "default_subtype": "HOA",
            },
        ).get_json()
        self.assertEqual(created["default_subtype"], "HOA")
        updated = self.client.patch(
            f"/api/rental_property_match_rules/{created['id']}",
            json={"rental_property_id": "rprop_1", "name": "HOA dues", "enabled": 0},
        ).get_json()
        self.assertEqual(updated["name"], "HOA dues")
        self.assertEqual(updated["enabled"], 0)
        deleted = self.client.delete(f"/api/rental_property_match_rules/{created['id']}").get_json()
        self.assertEqual(deleted["status"], "deleted")


if __name__ == "__main__":
    unittest.main()
