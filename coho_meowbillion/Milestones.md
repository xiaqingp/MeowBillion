# Milestones

## Status

- Project: MeowBillion
- Approval: Approved current baseline and forward milestone structure
- Last updated: 2026-07-13
- Approved scope: Maintain current local-first app, fix bugs, improve UX, preserve tests, push every code change.

## Milestone Summary

| Milestone | Goal | Status | Test summary |
| --- | --- | --- | --- |
| M1 - Baseline Stabilization | Preserve current behavior and document architecture/product state | In progress | Coho docs created; existing automated tests remain required |
| M2 - Transaction Review Quality | Make transaction filtering, review locks, prediction, and assignment reliable | In progress | Transaction assignment and report tests exist |
| M3 - Travel and Rentals V2 | Maintain structured Trip/Property reports and managers | In progress | Context metadata, migration, rules, and report tests exist |
| M4 - Portfolio and Overview Quality | Keep net worth/allocation reporting accurate and usable | In progress | Allocation tests plus manual chart verification |
| M5 - Operations and Backup | Improve local startup, private access, and backup safety | Not started | Manual startup/Tailscale checks; future backup tests TBD |

## Milestone Details

### M1 - Baseline Stabilization

- Goal: Establish project memory and preserve current product/engineering decisions.
- Scope: PRD, TechDesign, Milestones, Lessons, knowledge; document commands and operational constraints.
- Out of scope: New product behavior.
- Status: In progress.
- Acceptance criteria:
  - Coho docs exist in `coho_meowbillion/`.
  - Docs reflect current product state.
  - Git remains clean except intentionally ignored local data.

#### Tasks

| Task | Description | Status | Test plan | Test result |
| --- | --- | --- | --- | --- |
| T1 | Create Coho project directory and baseline docs | In progress | Review docs for consistency with README/current app | Pending user review |
| T2 | Record reusable project facts | In progress | Confirm commands and constraints are captured | Pending user review |
| T3 | Match web and mobile Tiffany logo colors | Done | `tests/test_brand_logo.py`; full unittest suite | 69 tests passed 2026-07-13, including rendered Lucide SVG selectors |

#### Delivery Notes

- Baseline docs should be updated when product behavior, data model, or test commitments change.

### M2 - Transaction Review Quality

- Goal: Make transaction review predictable and fast.
- Scope: Filters, status handling, reviewed lock, pending behavior, category/subcategory prediction, history-based prediction, assignment filter.
- Out of scope: Full global rules engine.
- Status: In progress.
- Acceptance criteria:
  - Reviewed transactions cannot be changed until de-reviewed.
  - Pending transactions cannot be reviewed.
  - Filters cover search, date/month, account, amount, category, status, and Trip/Property.
  - Prediction stays within user-configured categories.

#### Tasks

| Task | Description | Status | Test plan | Test result |
| --- | --- | --- | --- | --- |
| T1 | Enforce reviewed lock for Trip/Property assignment | Done | `tests/test_transaction_assignment.py` | Passed previously |
| T2 | Add Trip/Property transaction filter | Done | `tests/test_transaction_assignment.py` | Passed previously |
| T3 | Compact transaction filter UI | Done | Manual static load check | Passed previously |
| T4 | Continue improving prediction accuracy | Not started | Add classifier/regression tests per bug | Pending |
| T5 | Add Spending report transaction drill-down | Done | `tests/test_spending_drilldown_ui.py`; JS syntax check | Passed 2026-07-12 |
| T6 | Add one-click Transaction filter reset | Done | `tests/test_transaction_filter_reset_ui.py`; JS syntax check | Passed 2026-07-12 |
| T7 | Import approved Plaid interest/dividend investment transactions | Done | `tests/test_investment_income_sync.py`; full unittest suite | 61 tests passed 2026-07-13 |
| T8 | Preserve Transaction scroll position after review refresh | Done | `tests/test_transaction_review_scroll_ui.py`; JS syntax check | Passed 2026-07-13 |
| T9 | Preserve user-scoped Transaction filters across page refresh | Done | `tests/test_transaction_filter_persistence_ui.py`; JS syntax check | Passed 2026-07-13 |
| T10 | Add monthly/yearly Income subcategory tables to Spending | Done | `tests/test_spending_income_subcategories.py`; full unittest suite | 66 tests passed 2026-07-13 |
| T11 | Add Income subcategory drill-down and Transaction filter | Done | `tests/test_spending_income_drilldown.py`; full unittest suite | 68 tests passed 2026-07-13 |

#### Delivery Notes

- Reviewed lock is both frontend and backend enforced.

### M3 - Travel and Rentals V2

- Goal: Use structured metadata for Travel and Rentals instead of note grouping.
- Scope: Trips, Rental Properties, assignment columns, managers, rental rules, reports.
- Out of scope: Global rules engine and shared family data.
- Status: In progress.
- Acceptance criteria:
  - Travel groups by `trip_id`.
  - Rentals groups by `rental_property_id`.
  - Unassigned buckets remain visible.
  - Travel refunds reduce trip spend.
  - Managers are inline-editable tables.

#### Tasks

| Task | Description | Status | Test plan | Test result |
| --- | --- | --- | --- | --- |
| T1 | Add structured metadata schema and migration | Done | Context migration tests | Passed previously |
| T2 | Add transaction assignment UI/API | Done | Transaction assignment tests | Passed previously |
| T3 | Add rental property match rules | Done | Rental rule tests | Passed previously |
| T4 | Group reports by IDs | Done | Reports V2 tests | Passed previously |
| T5 | Net travel refunds correctly | Done | Reports V2 refund regression | Passed previously |
| T6 | Continue manager UX cleanup | Not started | Manual UI check plus API tests if behavior changes | Pending |

#### Delivery Notes

- Notes remain free text and are not the source of truth for grouping.

### M4 - Portfolio and Overview Quality

- Goal: Keep Overview accurate and readable as daily history grows.
- Scope: Net worth trend, allocation trend, portfolio allocation, account allocation, manual overrides, legacy/manual assets.
- Out of scope: Investment-provider replacement unless explicitly approved.
- Status: In progress.
- Acceptance criteria:
  - Net worth and linked assets reconcile.
  - Allocation history preserves daily snapshots.
  - Manual allocation changes do not corrupt historical data.
  - Charts handle time windows and dense daily points.

#### Tasks

| Task | Description | Status | Test plan | Test result |
| --- | --- | --- | --- | --- |
| T1 | Maintain separate net worth and allocation trend charts | Done | Manual chart check | Passed previously |
| T2 | Keep allocation defaults and manual overrides understandable | In progress | Allocation tests and DB spot checks | Ongoing |
| T3 | Investigate institution-specific holdings gaps | In progress | Plaid status and DB holdings inspection | Ongoing |
| T4 | Add expandable account balance history in Account Allocation | Done | `tests/test_account_balance_history.py`; full unittest suite; static load check | Passed 2026-07-09 |

#### Delivery Notes

- Fidelity and other institution behavior depends on Plaid holdings availability.

### M5 - Operations and Backup

- Goal: Make local operation and private remote access safe and repeatable.
- Scope: `start-server.bat`, Tailscale access, backup planning, Git hygiene.
- Out of scope: Public hosting without security review.
- Status: Not started.
- Acceptance criteria:
  - Server can start with `HOST=0.0.0.0` and `PORT=8090`.
  - App is reachable through Tailscale IP on port `8090`.
  - Personal data remains ignored by Git.
  - Backup design is explicit before implementation.

#### Tasks

| Task | Description | Status | Test plan | Test result |
| --- | --- | --- | --- | --- |
| T1 | Verify local start command and batch file | Done | HTTP 200 on port 8090 | Passed previously |
| T2 | Design backup strategy | Not started | Review restore workflow and encryption expectations | Pending |
| T3 | Implement backup if approved | Not started | Backup/restore test with sample DB | Pending |
| T4 | Add configurable global daily sync time | Done | `tests/test_sync_schedule.py`; full unittest suite; static load check | Passed 2026-07-10 |

#### Delivery Notes

- Tailscale fix was app server listening on `0.0.0.0`, not a Tailscale configuration change.

## Change Log

| Date | Change | Reason | Affected milestone/task |
| --- | --- | --- | --- |
| 2026-07-09 | Created baseline milestone structure | Coho start approved | M1/T1 |
| 2026-07-09 | Added expandable account balance history to Account Allocation | User requested account-level history in Overview | M4/T4 |
| 2026-07-10 | Added admin-controlled global daily sync time | User requested daily auto-sync at 16:00 with no-restart updates | M5/T4 |
| 2026-07-13 | Added Plaid investment income import mapping | User approved five interest/dividend subtypes for the existing Transaction review flow | M2/T7 |
| 2026-07-13 | Added monthly/yearly Income subcategory reporting | User requested Income subcategory tables on Spending | M2/T10 |
| 2026-07-13 | Added Income subcategory drill-down | User requested each Income table cell to open matching Transactions | M2/T11 |
| 2026-07-13 | Unified web and mobile logo colors | User approved Tiffany background and white cat outline across web surfaces | M1/T3 |
