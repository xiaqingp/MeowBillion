from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SpendingDrilldownUiTests(unittest.TestCase):
    def test_spending_tables_render_drilldown_controls(self):
        app_js = (ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-drilldown-period', app_js)
        self.assertIn('data-drilldown-category', app_js)
        self.assertIn('drillDownToTransactions', app_js)
        self.assertIn('drilldownCell(row.income || 0, row.month, "Income")', app_js)
        self.assertIn('drilldownCell(row.income || 0, row.year, "Income")', app_js)
        self.assertIn('drilldownCell(amount, row.month, category)', app_js)
        self.assertIn('drilldownCell(amount, row.year, category)', app_js)
        self.assertIn('filter(value => value !== "pending")', app_js)


if __name__ == "__main__":
    unittest.main()
