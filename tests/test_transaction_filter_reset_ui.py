from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TransactionFilterResetUiTests(unittest.TestCase):
    def test_reset_control_and_handler_cover_all_filter_types(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        app_js = (ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="tx-reset-filters-btn"', html)
        self.assertIn('function resetTransactionFilters()', app_js)
        self.assertIn('setMultiselectValues("filter-category-container"', app_js)
        self.assertIn('setMultiselectValues("filter-reviewed-container"', app_js)
        self.assertIn('triggerFilterUpdate();', app_js)

    def test_setup_filters_declares_reset_button_before_binding_it(self):
        app_js = (ROOT / "app.js").read_text(encoding="utf-8")
        setup_filters = app_js.split("function setupFilters()", 1)[1].split("function resetTransactionFilters()", 1)[0]

        declaration = 'const resetFiltersBtn = document.getElementById("tx-reset-filters-btn");'
        binding = 'if (resetFiltersBtn) resetFiltersBtn.onclick = resetTransactionFilters;'
        self.assertIn(declaration, setup_filters)
        self.assertLess(setup_filters.index(declaration), setup_filters.index(binding))


if __name__ == "__main__":
    unittest.main()
