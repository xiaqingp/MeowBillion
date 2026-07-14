# Tiffany Balanced Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved balanced Tiffany brand treatment and coordinated allocation palette across the existing MeowBillion web UI without changing layout, data, APIs, or workflows.

**Architecture:** Keep the implementation inside the existing frontend: CSS variables own brand/surface tokens and one small `CHART_COLORS` constant in `app.js` owns Overview chart colors. A static unittest locks the approved tokens and prevents the old Indigo/purple brand treatment from returning.

**Tech Stack:** Vanilla CSS, vanilla JavaScript, Chart.js, Python `unittest` static regression tests.

## Global Constraints

- Tiffany primary is exactly `#0ABAB5`; hover/deep is `#078F8B`; ink is `#066F6C`; wash is `#E8F9F8`.
- Allocation colors are exactly Cash `#238F9D`, Stock `#4A9B78`, Bond `#C89A43`, and Real Estate `#8875A8`.
- Semantic success, danger, warning, pending, and informational colors remain independent.
- No new dependency, theme framework, dark mode, or user-selectable theme.
- Do not change responsive breakpoints, page layout, financial values, APIs, or backend behavior.
- Bump the displayed version from `v0.1.22` to `v0.1.23` with a minute-precision update timestamp.

---

### Task 1: Lock the Approved Theme Contract

**Files:**
- Create: `tests/test_tiffany_theme.py`
- Test: `tests/test_tiffany_theme.py`

**Interfaces:**
- Consumes: Existing static files `styles.css`, `app.js`, and `index.html`.
- Produces: A regression contract for exact CSS tokens, chart colors, removal of the old brand gradient, and the new displayed version.

- [ ] **Step 1: Write the failing static regression test**

```python
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
        self.assertIn("v0.1.23", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m unittest tests.test_tiffany_theme -v`

Expected: FAIL because the CSS still uses Indigo, `CHART_COLORS` does not exist, and the page still displays `v0.1.22`.

- [ ] **Step 3: Commit the failing contract with the implementation in Task 2**

The failing test is intentionally kept uncommitted until the minimal implementation makes the repository green.

### Task 2: Apply the Minimal Theme Implementation

**Files:**
- Modify: `styles.css:1-350`
- Modify: `app.js:1-80,1188-1215,1428-1478`
- Modify: `modules/transaction-renderer.js:250-325`
- Modify: `index.html:92`
- Test: `tests/test_tiffany_theme.py`

**Interfaces:**
- Consumes: The exact token contract from Task 1.
- Produces: CSS custom properties and `CHART_COLORS = Object.freeze(...)` used by both Overview chart renderers.

- [ ] **Step 1: Replace brand and surface CSS tokens**

Set the existing root variables to the approved cool-neutral surfaces and Tiffany brand values. Add `--color-primary-hover` and `--color-primary-ink`; use the wash color directly for `--color-primary-glow`.

- [ ] **Step 2: Remove the two brand gradients**

Render `.brand h2` as solid `var(--text-primary)`. Render `.sync-btn` with solid `var(--color-primary)`, use `var(--color-primary-hover)` on hover, and update its shadow to Tiffany RGB values.

- [ ] **Step 3: Add restrained navigation and keyboard focus treatment**

Add `box-shadow: inset 3px 0 0 var(--color-primary)` to `.nav-btn.active`. Add a global `:focus-visible` outline using the Tiffany primary so keyboard focus is not removed.

- [ ] **Step 4: Define and use the shared chart palette**

Add this constant near the top of `app.js`:

```javascript
const CHART_COLORS = Object.freeze({
    brand: "#078F8B",
    brandFill: "rgba(10, 186, 181, 0.08)",
    allocation: Object.freeze({
        Cash: "#238F9D",
        Stock: "#4A9B78",
        Bond: "#C89A43",
        "Real Estate": "#8875A8"
    }),
    chartText: "#697A82",
    chartGrid: "rgba(105, 122, 130, 0.12)"
});
```

Use `CHART_COLORS.brand` and `brandFill` for Net Worth. Use `CHART_COLORS.allocation[category]` for Allocation Trend and Portfolio Allocation. Use `chartText` and `chartGrid` for the affected Overview chart legends, axes, and grid lines.

- [ ] **Step 5: Update primary-color fallbacks and displayed version**

Change only primary-brand fallbacks in `modules/transaction-renderer.js` from blue to Tiffany. Keep reviewed, pending, transfer, warning, danger, and legacy-import provenance colors unchanged. Update `index.html` to `v0.1.23` and the current minute-precision timestamp.

- [ ] **Step 6: Run the focused test and verify GREEN**

Run: `python -m unittest tests.test_tiffany_theme tests.test_brand_logo -v`

Expected: All theme and logo tests pass.

- [ ] **Step 7: Run JavaScript syntax validation**

Run: `node --check app.js` and `node --check modules/transaction-renderer.js`.

Expected: Both commands exit `0` with no output.

### Task 3: Verify, Record, and Deliver

**Files:**
- Modify: `coho_meowbillion/Milestones.md`
- Modify: `coho_meowbillion/TechDesign.md` only if implementation differs from the approved design

**Interfaces:**
- Consumes: The completed theme implementation and its verification evidence.
- Produces: Coho delivery record, a clean main branch, and a pushed GitHub commit.

- [ ] **Step 1: Run the complete automated suite**

Run: `python -m unittest discover -s tests`

Expected: All tests pass.

- [ ] **Step 2: Run static hygiene checks**

Run: `git diff --check` and search changed production files for the removed Indigo/purple brand gradients.

Expected: No whitespace errors and no removed gradient strings.

- [ ] **Step 3: Verify desktop and iPad presentation**

Open the running local app, sign in using the existing local session, and inspect Overview plus representative Spending, Transactions, Categories, and Plaid states at desktop and iPad widths. Confirm no overlap, clipped controls, unreadable legend text, or semantic-color regressions.

- [ ] **Step 4: Record delivery evidence**

Mark `M4/T5` Done in `coho_meowbillion/Milestones.md`, record focused/full test results and visual viewport coverage, and add a dated change-log entry.

- [ ] **Step 5: Commit and push**

```powershell
git add styles.css app.js modules/transaction-renderer.js index.html tests/test_tiffany_theme.py coho_meowbillion/Milestones.md
git commit -m "Apply balanced Tiffany web theme"
git push origin main
```

Expected: Push advances `origin/main`, and `git status --short` is empty.
