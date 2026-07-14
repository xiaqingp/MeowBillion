from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TransactionFilterPersistenceUiTests(unittest.TestCase):
    def test_filters_restore_before_initial_transaction_fetch(self):
        app_js = (ROOT / "app.js").read_text(encoding="utf-8")
        init_app = app_js.split("async function initApp()", 1)[1].split("function showApp", 1)[0]

        self.assertIn("restoreTransactionFilters(auth.user);", init_app)
        self.assertLess(
            init_app.index("restoreTransactionFilters(auth.user);"),
            init_app.index("fetchTransactions(state.currentPage"),
        )

    def test_filters_are_user_scoped_saved_and_applied_to_controls(self):
        app_js = (ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('sessionStorage.getItem(transactionFilterStorageKey)', app_js)
        self.assertIn('sessionStorage.setItem(transactionFilterStorageKey', app_js)
        self.assertIn('`meowbillion:transaction-filters:${userKey}`', app_js)
        self.assertIn("persistTransactionFilters();", app_js)
        self.assertIn("applyTransactionFiltersToControls();", app_js)
        self.assertIn('document.getElementById("tx-month-filter")', app_js)
        self.assertIn('setMultiselectValues("filter-category-container"', app_js)
        self.assertIn('setMultiselectValues("filter-reviewed-container"', app_js)


if __name__ == "__main__":
    unittest.main()
