from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class IncomeSubcategoryDrilldownTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        import database
        self.original_db_file = database.DB_FILE
        database.DB_FILE = str(Path(self.temp_dir.name) / "income-drilldown.db")
        database.init_db()
        with database.get_db() as conn:
            conn.execute(
                "INSERT INTO users (id, email, password_hash, display_name, role, active, created_at) VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)",
                ("income-user", "income@example.com", "x", "Income User", "admin"),
            )
            conn.executemany(
                """
                INSERT INTO transactions
                    (transaction_id, user_id, date, type, subtype, merchant, amount, direction, pending, ipay)
                VALUES (?, 'income-user', '2026-07-01', 'Income', ?, ?, 10, 'inflow', 0, 10)
                """,
                [
                    ("interest", "Interest", "Interest Earned"),
                    ("blank", "", "Unlabeled Income"),
                ],
            )

        from server import app
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = "income-user"

    def tearDown(self):
        import database
        database.DB_FILE = self.original_db_file
        self.temp_dir.cleanup()

    def test_filter_options_and_uncategorized_query(self):
        options = self.client.get("/api/transaction_filter_options").get_json()
        self.assertEqual(
            options["subcategories"],
            [
                {"value": "Interest", "label": "Interest", "count": 1},
                {"value": "__uncategorized__", "label": "Uncategorized", "count": 1},
            ],
        )

        result = self.client.get(
            "/api/transactions?reviewed_filter=all&category=Income&subtype=__uncategorized__"
        ).get_json()
        self.assertEqual([row["TransactionID"] for row in result["transactions"]], ["blank"])

    def test_desktop_filter_and_income_cells_are_wired_for_subcategory(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        app_js = (ROOT / "app.js").read_text(encoding="utf-8")
        api_js = (ROOT / "modules" / "api.js").read_text(encoding="utf-8")
        state_js = (ROOT / "modules" / "state.js").read_text(encoding="utf-8")

        self.assertIn('id="tx-subcategory-filter"', html)
        self.assertIn('subtype: filters.subcategory || "all"', api_js)
        self.assertIn('subcategory: "all"', state_js)
        self.assertIn('data-drilldown-subcategory', app_js)
        self.assertIn('drillDownToTransactions(cell.dataset.drilldownPeriod || "", cell.dataset.drilldownCategory || "", cell.dataset.drilldownSubcategory || "")', app_js)
        self.assertIn('drilldownCell(amount, row[periodKey], "Income", name)', app_js)
        self.assertIn('["tx-subcategory-filter", "subcategory"]', app_js)
        self.assertIn('["tx-account-filter", "tx-assignment-filter", "tx-subcategory-filter"]', app_js)


if __name__ == "__main__":
    unittest.main()
