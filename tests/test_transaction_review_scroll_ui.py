from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TransactionReviewScrollUiTests(unittest.TestCase):
    def test_review_refresh_preserves_the_actual_viewport_scroll_container(self):
        app_js = (ROOT / "app.js").read_text(encoding="utf-8")
        renderer_js = (ROOT / "modules" / "transaction-renderer.js").read_text(encoding="utf-8")

        self.assertIn('document.querySelector(".viewport")', app_js)
        self.assertNotIn('document.querySelector(".main-content") || document.scrollingElement', app_js)
        self.assertIn('await loadData({ preserveScroll: true });', renderer_js)


if __name__ == "__main__":
    unittest.main()
