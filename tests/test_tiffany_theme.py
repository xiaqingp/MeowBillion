from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TiffanyThemeTests(unittest.TestCase):
    def test_balanced_tiffany_tokens_and_brand_treatment(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn("--color-primary: #0ABAB5;", css)
        self.assertIn("--color-primary-hover: #078F8B;", css)
        self.assertIn("--color-primary-ink: #066F6C;", css)
        self.assertIn("--color-primary-glow: #E8F9F8;", css)
        self.assertIn("box-shadow: inset 3px 0 0 var(--color-primary);", css)
        self.assertNotIn("linear-gradient(to right, #6366f1, #a855f7)", css)
        self.assertNotIn("linear-gradient(135deg, var(--color-primary), #4f46e5)", css)

    def test_overview_charts_use_approved_palette(self):
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        for color in ("#078F8B", "#238F9D", "#4A9B78", "#C89A43", "#8875A8"):
            self.assertIn(color, js)
        self.assertGreaterEqual(js.count("CHART_COLORS.allocation"), 2)

    def test_displayed_version_is_bumped(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("v0.1.28", html)


if __name__ == "__main__":
    unittest.main()
