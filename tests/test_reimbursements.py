import os
import tempfile
import unittest
from pathlib import Path

import database
from server import app


class ReimbursementTests(unittest.TestCase):
    def setUp(self):
        self.original_db_file = database.DB_FILE
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        database.DB_FILE = os.path.join(self.tmpdir.name, "finance.db")
        database.init_db()
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()
        with database.get_db() as conn:
            conn.executemany(
                """
                INSERT INTO users (id, email, password_hash, display_name, role, created_at)
                VALUES (?, ?, 'x', ?, 'admin', datetime('now'))
                """,
                [("u1", "u1@example.com", "User One"), ("u2", "u2@example.com", "User Two")],
            )
            conn.executemany(
                """
                INSERT INTO transactions
                (transaction_id, date, type, merchant, amount, direction, pending, user_id)
                VALUES (?, '2026-08-01', ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("expense", "Shopping", "Store", 100, "outflow", 0, "u1"),
                    ("income", "Income", "Employer", 40, "inflow", 0, "u1"),
                    ("pending", "Shopping", "Pending store", 10, "outflow", 1, "u1"),
                    ("other_user", "Shopping", "Other user", 999, "outflow", 0, "u2"),
                ],
            )
            conn.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = "u1"

    def tearDown(self):
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def mark(self, transaction_id, value=True):
        return self.client.post(
            "/api/update_transaction",
            json={
                "transaction_id": transaction_id,
                "type": "Income" if transaction_id == "income" else "Shopping",
                "subtype": "",
                "is_b": "n",
                "ratio": 1,
                "mown": 0,
                "note": "",
                "is_reimbursement": value,
            },
        )

    def test_checked_outflow_minus_checked_inflow_drives_summary(self):
        self.assertEqual(self.mark("expense").get_json()["status"], "success")
        self.assertEqual(self.mark("income").get_json()["status"], "success")

        summary = self.client.get("/api/reimbursement_summary").get_json()
        self.assertEqual(summary["to_be_reimbursed"], 60.0)

        rows = self.client.get("/api/transactions?reviewed_filter=all").get_json()["transactions"]
        flags = {row["TransactionID"]: row["IsReimbursement"] for row in rows}
        self.assertEqual(flags["expense"], 1)
        self.assertEqual(flags["income"], 1)

    def test_unchecking_preserves_binary_classification_and_recalculates(self):
        self.mark("expense")
        self.mark("income")
        self.assertEqual(self.mark("income", False).status_code, 409)

        self.client.post("/api/unconfirm_transaction", json={"transaction_id": "income"})
        response = self.mark("income", False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/reimbursement_summary").get_json()["to_be_reimbursed"], 100.0)

    def test_pending_and_other_users_cannot_be_changed(self):
        self.assertEqual(self.mark("pending").status_code, 409)
        self.assertEqual(self.mark("other_user").status_code, 404)

    def test_manual_transaction_can_start_checked(self):
        response = self.client.post(
            "/api/create_manual_transaction",
            json={
                "date": "2026-08-02",
                "merchant": "Manual reimbursement",
                "amount": 25,
                "direction": "inflow",
                "type": "Income",
                "is_reimbursement": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/reimbursement_summary").get_json()["to_be_reimbursed"], -25.0)

    def test_personal_analysis_excludes_reimbursements_but_keeps_cash_flow_rows(self):
        self.assertEqual(self.mark("expense").status_code, 200)
        self.assertEqual(self.mark("income").status_code, 200)
        with database.get_db() as conn:
            conn.executemany(
                """
                INSERT INTO transactions
                (transaction_id, date, type, merchant, amount, direction, pending, reviewed, ipay, subtype, user_id)
                VALUES (?, '2026-08-02', ?, ?, ?, ?, 0, 1, ?, ?, 'u1')
                """,
                [
                    ("regular_expense", "Shopping", "Regular store", 30, "outflow", -30, "Retail"),
                    ("regular_income", "Income", "Salary", 20, "inflow", 20, "Salary"),
                ],
            )
            conn.commit()

        analysis = self.client.get("/api/monthly_analysis").get_json()
        august = next(row for row in analysis["months"] if row["month"] == "2026-08")
        self.assertEqual(august["income"], 20.0)
        self.assertEqual(august["expense"], 30.0)
        self.assertEqual(analysis["category_totals"], {"Shopping": 30.0})
        self.assertEqual(analysis["income_subcategory_order"], ["Salary"])
        rows = self.client.get("/api/transactions?reviewed_filter=all").get_json()["transactions"]
        self.assertEqual({row["TransactionID"] for row in rows}, {"expense", "income", "pending", "regular_expense", "regular_income"})

    def test_web_table_uses_narrow_final_checkbox_column_and_dashboard_card(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "index.html").read_text(encoding="utf-8")
        renderer = (root / "modules" / "transaction-renderer.js").read_text(encoding="utf-8")
        self.assertIn('<col style="width: 56px;">', html)
        self.assertIn('title="To be reimbursed">Reimb.</th>', html)
        self.assertIn('id="dash-reimbursement"', html)
        self.assertIn('class="card-label">To Be Reimbursed</span>', html)
        self.assertIn('id="reimbursement-input-${t.TransactionID}"', renderer)
        self.assertIn("${disabledAttr}", renderer)
        self.assertNotIn("toggleTransactionReimbursement", renderer)


if __name__ == "__main__":
    unittest.main()
