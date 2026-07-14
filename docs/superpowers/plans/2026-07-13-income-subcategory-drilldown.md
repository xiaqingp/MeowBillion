# Income Subcategory Drill-down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every non-zero Income by Subcategory cell open the matching Transactions, with a visible and persistent Subcategory filter.

**Architecture:** Reuse the existing `subtype` query parameter and Spending drill-down event delegation. Add user-scoped subtype options to the existing filter-options response and wire one native select through the current filter state, reset, persistence, and fetch paths.

**Tech Stack:** Flask, SQLite, vanilla JavaScript, Python unittest.

## Global Constraints

- Do not add a database column or endpoint.
- Pending transactions remain excluded from Spending drill-downs.
- Blank subtype values display as `Uncategorized` and use an internal filter sentinel.
- Every code change is tested, versioned, committed, and pushed.

---

### Task 1: Add Income Subcategory Drill-down

**Files:**
- Modify: `routes_transactions.py`
- Modify: `modules/api.js`
- Modify: `modules/state.js`
- Modify: `app.js`
- Modify: `index.html`
- Modify: `styles.css`
- Test: `tests/test_spending_income_drilldown.py`

**Interfaces:**
- Consumes: `GET /api/transaction_filter_options`, `GET /api/transactions?subtype=...`, `drillDownToTransactions(period, category)`.
- Produces: `subcategories` filter options and `drillDownToTransactions(period, category, subcategory)`.

- [x] Write backend and static UI tests for subtype options, blank-subtype filtering, query forwarding, filter state/reset, and Income cell attributes.
- [x] Run the focused tests and confirm they fail because the desktop filter and drill-down wiring are absent.
- [x] Add the minimum backend option query and frontend select/state/drill-down wiring.
- [x] Run focused and full tests, JS/Python syntax checks, and `git diff --check`.
- [x] Bump the app version, update Coho docs, and restart port 8090.
