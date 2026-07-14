# Lessons

## 2026-07-09 - Coho baseline

- Issue: Project work had accumulated many implementation decisions without a single local baseline.
- Cause: Work proceeded task-by-task before Coho was activated.
- Fix: Created Coho documentation structure for product, technical design, milestones, lessons, and reusable knowledge.
- Prevention: Before project-related changes under Coho, read the relevant Coho docs and update them when behavior, data model, scope, or test commitments change.
- Affected docs: PRD.md, TechDesign.md, Milestones.md, knowledge.md

## 2026-07-09 - Travel refund sign handling

- Issue: Travel report showed booking and refund transactions as positive spend.
- Cause: The report used `abs(ipay)`, which erased inflow/refund sign.
- Fix: Travel report now converts signed payment into net spend, so refunds reduce trip/category totals.
- Prevention: Add regression tests for sign-sensitive reporting whenever amount logic changes.
- Affected docs: PRD.md, TechDesign.md, Milestones.md

## 2026-07-09 - Reviewed assignment lock

- Issue: Trip/Property assignment could be changed on reviewed transactions.
- Cause: Assignment UI and endpoint did not fully apply the reviewed-lock rule.
- Fix: Disable assignment controls for reviewed transactions and reject assignment-only updates server-side.
- Prevention: Any new editable transaction field must explicitly decide how reviewed lock applies.
- Affected docs: PRD.md, TechDesign.md, Milestones.md

## 2026-07-13 - Transaction review scroll position

- Issue: Reviewing a transaction refreshed the Transactions page at the top.
- Cause: Scroll preservation captured `.main-content`, which is non-scrolling, while `.viewport` owns vertical scrolling.
- Fix: Capture and restore the `.viewport` scroll position during data refresh.
- Prevention: Scroll-state helpers must target the element whose CSS owns `overflow-y: auto`.
- Affected docs: Milestones.md, Lessons.md

## 2026-07-13 - Lucide logo color after icon replacement

- Issue: Web logo backgrounds were Tiffany, but the cat outlines rendered black.
- Cause: CSS targeted the source `<i>` elements, while `lucide.createIcons()` replaces them with `<svg>` elements that no longer matched the white color rule.
- Fix: Apply the logo size and color rules to both the source `<i>` and rendered `<svg>` elements.
- Prevention: Tests for Lucide styling must cover the rendered SVG selector, not only the pre-render HTML element.
- Affected docs: Lessons.md, Milestones.md
