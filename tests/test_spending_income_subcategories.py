import os
import tempfile
import unittest
from pathlib import Path

import database
from server import app


class SpendingIncomeSubcategoryTests(unittest.TestCase):
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
            conn.executemany(
                """
                INSERT INTO transactions
                (transaction_id, date, type, subtype, merchant, amount, direction, pending, ipay, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'u1')
                """,
                [
                    ("salary_jan", "2026-01-15", "Income", "Salaries", "Employer", 1000, "inflow", 0, 1000),
                    ("interest_jan", "2026-01-31", "Income", "Interest", "Bank", 10, "inflow", 0, 10),
                    ("blank_jan", "2026-01-20", "Income", "", "Other income", 5, "inflow", 0, 5),
                    ("salary_feb", "2026-02-15", "Income", "Salaries", "Employer", 2000, "inflow", 0, 2000),
                    ("pending_dividend", "2026-02-20", "Income", "Dividend", "Broker", 99, "inflow", 1, 99),
                    ("expense", "2026-02-21", "Shopping", "Other", "Store", 50, "outflow", 0, -50),
                ],
            )
            conn.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = "u1"

    def tearDown(self):
        database.DB_FILE = self.original_db_file
        self.tmpdir.cleanup()

    def test_monthly_and_yearly_income_subcategory_matrices_exclude_pending(self):
        data = self.client.get("/api/monthly_analysis").get_json()

        self.assertEqual(data["income_subcategory_order"], ["Interest", "Salaries", "Uncategorized"])
        january = next(row for row in data["income_subcategory_matrix"] if row["month"] == "2026-01")
        february = next(row for row in data["income_subcategory_matrix"] if row["month"] == "2026-02")
        yearly = next(row for row in data["yearly_income_subcategory_matrix"] if row["year"] == "2026")

        self.assertEqual(january["subcategories"], {"Interest": 10.0, "Salaries": 1000.0, "Uncategorized": 5.0})
        self.assertEqual(february["subcategories"], {"Interest": 0.0, "Salaries": 2000.0, "Uncategorized": 0.0})
        self.assertEqual(yearly["subcategories"], {"Interest": 10.0, "Salaries": 3000.0, "Uncategorized": 5.0})
        self.assertNotIn("Dividend", data["income_subcategory_order"])

    def test_spending_page_has_monthly_and_yearly_income_subcategory_tables(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "index.html").read_text(encoding="utf-8")
        app_js = (root / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="monthly-income-subcategory-thead"', html)
        self.assertIn('id="yearly-income-subcategory-thead"', html)
        self.assertIn('data.income_subcategory_matrix', app_js)
        self.assertIn('data.yearly_income_subcategory_matrix', app_js)


if __name__ == "__main__":
    unittest.main()
