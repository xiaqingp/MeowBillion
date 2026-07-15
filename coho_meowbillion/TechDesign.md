# Tech Design

## Status

- Project: MeowBillion
- Approval: Approved as current baseline
- Last updated: 2026-07-14
- Based on PRD version/date: PRD.md 2026-07-14

## Overview

MeowBillion is a Flask + SQLite + vanilla JavaScript application. The backend owns auth, DB initialization/migrations, Plaid sync, transaction APIs, metadata APIs, reporting APIs, and allocation APIs. The frontend is a single-page app in `index.html`, `app.js`, and `modules/*`.

The design favors local-first storage, user-scoped rows, explicit review workflows, and small targeted APIs over broad abstractions.

## Architecture

- `server.py`: Flask app entrypoint and blueprint registration.
- `auth.py`: login, signup, setup, sessions, and current user resolution.
- `database.py`: SQLite connection, schema creation, dynamic migrations, default config, context metadata migration.
- `routes_plaid.py`: Plaid credentials, link/repair/reconnect, account and transaction sync, holdings/allocation sync.
- `routes_transactions.py`: transaction list/filter/review APIs, spending analysis, travel/rental reports, manual transactions, merge helpers.
- `routes_metadata.py`: Trip, Rental Property, and Rental Rule CRUD and rule application.
- `routes_config.py`: category/subcategory and config APIs.
- `classifier.py`: transaction category prediction from history and configured categories.
- `app.js`: SPA orchestration, page rendering, filter wiring, dashboard/report rendering.
- `modules/api.js`: frontend API client.
- `modules/state.js`: frontend state.
- `modules/transaction-renderer.js`: transaction table rendering and row actions.

### Web Theme Contract

- `styles.css` owns the brand and surface tokens. Tiffany `#0ABAB5` is the primary interaction color, with darker and pale variants for hover, text, focus, and selected states.
- `app.js` owns one shared chart color map. Net Worth uses deep Tiffany; Allocation uses Cash `#238F9D`, Stock `#4A9B78`, Bond `#C89A43`, and Real Estate `#8875A8`.
- The React Native client mirrors those brand and chart colors in its existing component styles. Income/Expense and status colors remain semantic.
- Status colors remain semantic: success/income, danger/expense, warning/pending, and informational states are not collapsed into the brand color.
- Theme changes do not alter layout, data, APIs, or responsive breakpoints.

### Net Worth Driver Contract

- Net Worth Trend renders before driver data; the latest date is prefetched asynchronously and other dates load on demand into a frontend date cache.
- Account contributions compare the latest known values on or before the selected and previous Net Worth snapshot dates.
- Asset deltas contribute directly; liability deltas contribute with reversed sign; manual assets participate through account value estimates.
- The API returns top three positive and negative contributors, the sum across all explained items, and an explicit unattributed residual for aggregate Legacy history.
- Hover keeps the native Chart.js date/Net Worth tooltip. Desktop click and touch tap open the pinned HTML driver details; driver failures do not prevent chart rendering.
- Mobile keeps its compact selected-point date/value summary. Tapping a point loads the same user-scoped endpoint and opens a native bottom sheet; results are cached by date for the current Home snapshot.

## Data Model

Key tables:

- `users`: login identity and role.
- `plaid_credentials`: user-scoped Plaid API credentials.
- `plaid_tokens`: user-scoped Plaid item/access tokens.
- `accounts`: synced account metadata.
- `transactions`: synced/manual transactions, review fields, prediction fields, `trip_id`, `rental_property_id`.
- `trips`: Travel metadata.
- `rental_properties`: Rental Property metadata.
- `rental_property_match_rules`: property-scoped prediction rules.
- `app_config`: categories, analysis rules, and app/user config.
- `account_balances_history`, `allocation_history_snapshots`, `allocation_overrides`, `manual_assets`, `manual_asset_values`, `account_value_estimates`: portfolio/allocation state and history.

Important contracts:

- `transactions.trip_id` links Travel transactions to `trips.id`.
- `transactions.rental_property_id` links Rentals transactions to `rental_properties.id`.
- If transaction type is not Travel/Rentals, both assignment fields should be empty.
- Reviewed transactions are stable and should not be mutated by sync predictions, rental rules, or assignment changes.

## Interfaces and Contracts

Core APIs:

- `GET /api/transactions`: paginated transaction list with filters.
- `POST /api/update_transaction`: review transaction and write category, split, note, subtype, Trip/Property assignment.
- `POST /api/update_transaction_assignment`: assignment-only update for unreviewed transactions.
- `POST /api/unconfirm_transaction`: de-review transaction.
- `GET /api/transaction_filter_options`: account, status, Trip, and Property filter options.
- Transaction filter state is stored in user-scoped browser `sessionStorage`, restored before the initial transaction fetch, and then applied to controls after dynamic options load.
- `GET/POST/PATCH/DELETE /api/trips`
- `GET/POST/PATCH/DELETE /api/rental_properties`
- `GET/POST/PATCH/DELETE /api/rental_property_match_rules`
- `POST /api/rental_property_match_rules/apply`
- `GET /api/travel_analysis`
- `GET /api/rental_analysis`
- `GET /api/monthly_analysis`: monthly/yearly cash flow, category spending, and aligned monthly/yearly Income subcategory matrices; pending transactions are excluded.
- Spending report cells drill into the existing Transaction view by setting date/category/subcategory filters client-side; blank subcategories use the internal `__uncategorized__` filter value, and no duplicate reporting API is used.
- `GET /api/account_balance_history`: user-scoped single-account balance history for expanded Account Allocation rows.
- `GET /api/net_worth_drivers?date=YYYY-MM-DD`: on-demand, user-scoped account/manual-asset contributions between a selected Net Worth snapshot and its actual preceding snapshot.
- `GET/POST /api/sync_schedule`: global daily sync time. All users may read it; only an active admin may update it.

Operational commands:

```powershell
python server.py
python -m unittest discover -s tests
python -m py_compile database.py routes_metadata.py routes_transactions.py routes_plaid.py server.py
```

## Dependencies

| Dependency | Purpose | Risk or constraint |
| --- | --- | --- |
| Flask | Web app and APIs | Session/auth behavior must remain local-safe |
| SQLite | Local persistence | Single-writer constraints; WAL and reasonable timeouts are used |
| Plaid API | Account, transaction, holdings sync | Institution support varies; user credentials required |
| Chart.js | Dashboard and analysis charts | Frontend-only rendering |
| Lucide icons | UI icons | Loaded in browser |
| Python unittest | Regression tests | Tests create temp DBs |

## Error Handling

- API routes return JSON errors with appropriate HTTP status where practical.
- Pending transactions cannot be reviewed until posted.
- Reviewed transactions cannot have assignment changed through assignment-only endpoint.
- Invalid Trip/Property IDs return not found.
- Plaid errors are surfaced in Plaid Settings and connection health.
- Sync should preserve reviewed user fields and only update raw Plaid fields/predictions where allowed.
- Investment Items also call Plaid Investments Transactions. The first successful import starts at January 1 of the current year; later imports use a rolling 90-day window recorded in `sync_metadata`.
- Only the approved investment-income subtype whitelist is written to `transactions`; Plaid investment transaction IDs provide idempotency, and reviewed rows retain user review fields.

## Security and Privacy

- Users authenticate before accessing app data.
- Rows are scoped by `user_id`.
- New users provide their own Plaid credentials.
- Local secrets and DB files are ignored by Git.
- Remote access is intended through private network tooling such as Tailscale, not public exposure.
- Production-style internet hosting would require a separate security review.

## Performance and Scalability

- Target workload is local household finance data.
- Transaction list is paginated.
- Filter options are cached on frontend load.
- Overview and transaction loading have been optimized enough for local use, but large DB growth should be monitored.
- SQLite concurrent writes are limited; avoid long transactions and uncontrolled parallel writes.

## Testing Strategy

- Unit/integration tests in `tests/` use temporary SQLite DBs.
- Business logic and regression fixes should add tests.
- Current suite covers auth/allocation/classifier/pending duplicate/Plaid sync/transactions/context metadata/reports/rental rules.
- UI-only polish can be verified by static loading and targeted manual checks.
- Backend route changes should run `python -m unittest discover -s tests`.

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Personal financial data leakage | High | Keep DB/secrets ignored; do not paste large raw DB contents into model context |
| Plaid institution limitations | Medium | Support manual correction and fallback allocation |
| SQLite write contention | Medium | Keep writes short; consider locks/queues only if measured need appears |
| Report sign errors | Medium | Add regression tests for refunds/inflows and net calculations |
| Multi-user leakage | High | Always include `user_id` in queries and joins |

## Decisions

| Decision | Rationale | Date |
| --- | --- | --- |
| Flask + SQLite retained | Existing app works locally and does not need a framework migration | 2026-07-09 |
| Inline metadata manager tables | Fits the transaction-table editing pattern and reduces separate form/list friction | 2026-07-09 |
| Assignment-only endpoint rejects reviewed transactions | Enforces review lock server-side, not just in UI | 2026-07-09 |
| Travel report uses signed net spend | Refunds should reduce travel spend | 2026-07-09 |
| Account balance history expands inside Account Allocation | Keeps account-level history contextual and avoids another large Overview chart | 2026-07-09 |
| Daily sync time is global and admin-controlled | One scheduler syncs all active users; polling the DB avoids restart after a time change | 2026-07-10 |
| Investment income uses the existing transaction model | Avoids a second review/reporting system while keeping non-income investment activity out of spending data | 2026-07-13 |
| Tiffany is a balanced interaction theme | Keeps the product recognizable while preserving distinct financial series and operational status colors | 2026-07-13 |

## Open Questions

- Whether to add encrypted scheduled backup support.
- Whether to introduce a DB write queue if concurrent sync/review writes increase.
- Whether future deployment should remain private-network only.
