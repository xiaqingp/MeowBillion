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

## 2026-07-14 - Net Worth tooltip redraw burst

- Issue: The browser tab could freeze while moving across a Net Worth point whose driver request was still loading.
- Cause: Repeated hover renders attached multiple completion callbacks to the same request, and every callback requested a chart redraw when the response arrived.
- Fix: Allow one pending completion redraw per date and skip dataset highlight updates when the highlighted dataset has not changed.
- Prevention: Async chart tooltips must deduplicate both network requests and response-driven redraw callbacks.
- Affected docs: Lessons.md, Milestones.md

## 2026-07-14 - Net Worth hover detail density

- Issue: Showing all account drivers on hover obscured most of the Net Worth curve.
- Cause: Quick inspection and full explanation were combined in one moving overlay.
- Fix: Restore the compact date/Net Worth hover and require click/tap for the complete driver panel.
- Prevention: Keep hover content glanceable; put multi-row analysis behind an explicit action.
- Affected docs: PRD.md, TechDesign.md, Milestones.md, Lessons.md

## 2026-07-14 - Net Worth detail dismissal

- Issue: Clicking blank space inside the Net Worth chart did not close the pinned detail panel.
- Cause: The document dismiss handler excluded the entire chart canvas, while the chart click handler ignored clicks without a data point.
- Fix: Handle blank chart clicks explicitly and toggle the panel off when the selected point is clicked again.
- Prevention: Pinned chart overlays need tested close paths for outside-page clicks, chart blank-space clicks, and repeated point clicks.
- Affected docs: Lessons.md, Milestones.md

## 2026-07-16 - Overview allocation latency

- Issue: A cold Overview allocation load took about four seconds.
- Cause: The read endpoint called Plaid Holdings serially for linked investment Items instead of reading sync results from local storage.
- Fix: Persist daily account allocation snapshots during scheduled/manual sync and make Overview allocation endpoints database-only.
- Prevention: Dashboard read endpoints must be side-effect free; external refresh work belongs to explicit or scheduled sync paths.
- Affected docs: PRD.md, TechDesign.md, Milestones.md, knowledge.md

## 2026-07-20 - Category prediction consistency

- Issue: One conflicting historical review disabled merchant learning, while some fallback paths could use another user's history or restore removed Categories.
- Cause: History required every reviewed pair to match, scheduled sync did not load config by explicit user ID, and startup backfill omitted user/config constraints.
- Fix: Select the most-frequent pair with at least three winning examples, use the first stored pair on a tie, and enforce the owning user's Category/Subcategory config in every prediction path.
- Prevention: Every classifier entry point must receive explicit user-scoped configuration, and startup migrations must carry `user_id` through reads and writes.
- Affected docs: PRD.md, TechDesign.md, Milestones.md, knowledge.md

## 2026-07-28 - Partial-sync Net Worth drop

- Issue: The Overview headline showed about $6.54M while the latest Net Worth Trend point showed about $4.85M.
- Cause: The history endpoint summed only accounts with a balance row on that exact date; Robinhood had not written July 28 rows, so its July 27 balance was omitted.
- Fix: Build each Plaid history date from every account's latest known balance as of that date.
- Prevention: Daily portfolio history must use as-of account values because institution syncs can succeed independently.
- Affected docs: PRD.md, TechDesign.md, Milestones.md, Lessons.md, knowledge.md

## 2026-07-28 - Hidden balance-sync warning and duplicate current totals

- Issue: A retryable Robinhood balance failure was invisible, while the Overview headline and latest chart point were calculated through separate paths.
- Cause: Balance warnings existed only in the immediate sync response, and the browser recomputed headline liabilities separately from the history endpoint.
- Fix: Persist balance status/error per Item and expose one backend current-net-worth summary to both surfaces.
- Prevention: Operational warnings must survive the request that created them, and the same displayed financial metric must have one canonical producer.
- Affected docs: PRD.md, TechDesign.md, Milestones.md, Lessons.md, knowledge.md
