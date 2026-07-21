# Milestones

## Status

- Project: MeowBillion
- Approval: Approved current baseline and forward milestone structure
- Last updated: 2026-07-20
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
| T4 | Use user-scoped most-frequent history while enforcing configured Categories/Subcategories | Done | Classifier, propagation, startup migration, Plaid sync, and full-suite regression tests | 88 tests passed 2026-07-20 |
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
| T5 | Apply approved balanced Tiffany web theme and coordinated allocation palette | Done | `tests/test_tiffany_theme.py`; JS syntax checks; full unittest suite; desktop/iPad visual checks | 72 tests passed 2026-07-13; 1440x900 and 1024x768 auth surfaces verified; authenticated Overview follows approved mock and static chart contract |
| T6 | Add on-demand Net Worth driver tooltip with Top 3 Up/Down account contributions | Done | Backend contribution/reconciliation tests; frontend tooltip contract test; JS syntax; full suite; real-data endpoint smoke check | 78 tests passed 2026-07-14; latest real snapshot reconciled at 100%; browser automation unavailable for final visual pass |
| T7 | Apply balanced Tiffany colors and on-demand Net Worth drivers to mobile Overview | Done | Mobile unit tests; TypeScript check; Expo Android export | 31 tests passed 2026-07-14; TypeScript and Android export passed |
| T8 | Persist allocation during sync and make Overview allocation database-only | Done | Allocation snapshot tests; full unittest suite; real sync and cold endpoint timing | 82 tests passed; 9 Items synced without warnings; cold allocation reads 4.8 ms and 7.5 ms on 2026-07-16 |

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
| 2026-07-13 | Approved balanced Tiffany web theme | User selected the balanced brand treatment and coordinated allocation palette in visual mockups | M4/T5 |
| 2026-07-13 | Applied balanced Tiffany web theme | Replaced Indigo brand styling, unified Overview chart colors, and bumped web version to v0.1.23 | M4/T5 |
| 2026-07-14 | Approved Net Worth driver tooltip | User selected an in-chart hover/tap explanation instead of a permanent Overview panel | M4/T6 |
| 2026-07-14 | Added Net Worth driver tooltip | Added user-scoped attribution, Top 3 Up/Down hover details, touch pinning, residual reconciliation, and on-demand caching in v0.1.24 | M4/T6 |
| 2026-07-14 | Stabilized Net Worth hover rendering | Deduplicated loading-completion redraws and skipped unchanged dataset highlight updates after a browser freeze report | M4/T6 |
| 2026-07-14 | Split Net Worth hover and details | Restored the compact date/Net Worth hover and moved full Top 3 attribution to explicit click/tap in v0.1.26 | M4/T6 |
| 2026-07-14 | Fixed Net Worth detail dismissal | Chart blank-space clicks and repeated clicks on the selected point now close the full detail panel in v0.1.27 | M4/T6 |
| 2026-07-14 | Applied Overview uplift to mobile | Unified the balanced Tiffany palette and added tap-only Net Worth driver details in mobile v1.0.1 | M4/T7 |
| 2026-07-16 | Moved holdings allocation work into sync | Persisted daily account allocation snapshots, retained last successful holdings on failure, and made Overview allocation DB-only in v0.1.28 | M4/T8 |
| 2026-07-20 | Corrected merchant-history prediction | Unique most-frequent reviewed classification now wins; all prediction/backfill paths enforce the owning user's configuration in v0.1.29 | M2/T4 |
| 2026-07-20 | Made tied merchant history deterministic | First-place ties now use the first stored reviewed combination instead of skipping prediction in v0.1.30 | M2/T4 |
