from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class BrandLogoTests(unittest.TestCase):
    def test_web_logo_matches_mobile_tiffany_mark(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        favicon = (ROOT / "favicon.svg").read_text(encoding="utf-8")

        logo_rule = css.split(".logo-icon {", 1)[1].split("}", 1)[0]
        avatar_rule = css.split(".avatar {", 1)[1].split("}", 1)[0]
        self.assertIn("background: #0ABAB5;", logo_rule)
        self.assertIn("background: #0ABAB5;", avatar_rule)
        self.assertIn('fill="#0ABAB5"', favicon)
        self.assertIn('stroke="#fff"', favicon)
        self.assertNotIn("linearGradient", favicon)


if __name__ == "__main__":
    unittest.main()
