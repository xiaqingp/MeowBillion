from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class NetWorthDriverTooltipUiTests(unittest.TestCase):
    def test_chart_uses_external_on_demand_driver_tooltip(self):
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        api = (ROOT / "modules" / "api.js").read_text(encoding="utf-8")

        self.assertIn("fetchNetWorthDriversApi", api)
        self.assertIn("external: externalNetWorthTooltip", js)
        self.assertIn("enabled: false", js)
        self.assertIn("netWorthDriverCache = new Map()", js)
        self.assertIn("fetchNetWorthDriverCached(latestDate)", js)
        self.assertIn("Top moves up", js)
        self.assertIn("Top moves down", js)
        self.assertIn("Unattributed", js)

    def test_touch_pinning_and_cache_invalidation_are_wired(self):
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        plaid_service = (ROOT / "modules" / "plaid-service.js").read_text(encoding="utf-8")

        self.assertIn('(pointer: coarse)', js)
        self.assertIn("netWorthDriverTooltipPinned = true", js)
        self.assertIn('document.addEventListener("pointerdown"', js)
        self.assertIn("clearNetWorthDriverCache();", js)
        self.assertIn("refreshOverview: true", plaid_service)

    def test_tooltip_has_responsive_non_overlapping_layout(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")

        self.assertIn(".net-worth-driver-tooltip", css)
        self.assertIn("width: min(420px, calc(100vw - 24px));", css)
        self.assertIn("grid-template-columns: 12px minmax(0, 1fr) auto;", css)
        self.assertIn("font-variant-numeric: tabular-nums;", css)


if __name__ == "__main__":
    unittest.main()
