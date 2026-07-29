# Knowledge

## 2026-07-09 - Project location

- Fact: Main project repo is `C:\Users\surreal\MyProjects\MeowBillion`.
- Scope: Local development and Git operations.
- Source: Current repo inspection.
- Usage: Use this directory for project work unless the user explicitly redirects.

## 2026-07-09 - Startup

- Fact: The app runs on Flask through `python server.py`, defaulting to port `8090`.
- Scope: Local app startup.
- Source: README.md and current runtime checks.
- Usage: Use `HOST=0.0.0.0` and `PORT=8090` when Tailscale/iPad access is needed.

## 2026-07-09 - Git workflow

- Fact: Every code change should be committed and pushed to GitHub.
- Scope: Repository changes.
- Source: User instruction.
- Usage: After edits and verification, commit and `git push`.

## 2026-07-09 - Sensitive data handling

- Fact: `finance.db`, WAL/SHM files, `.env`, local backups, and archives are not for Git.
- Scope: Privacy and repository hygiene.
- Source: README.md and project history.
- Usage: Do not commit DB/secrets; avoid dumping large DB contents into model context.

## 2026-07-09 - Current server

- Fact: Server has been run on `0.0.0.0:8090` for local and Tailscale access.
- Scope: Runtime operation.
- Source: Runtime checks.
- Usage: If the app is inaccessible from another device, confirm the server is listening on `0.0.0.0`, not only `127.0.0.1`.

## 2026-07-09 - Test commands

- Fact: Useful verification commands are `python -m unittest discover -s tests` and `python -m py_compile database.py routes_metadata.py routes_transactions.py routes_plaid.py server.py`.
- Scope: Backend and regression checks.
- Source: Project test runs.
- Usage: Run before delivery when backend/data/report behavior changes.

## 2026-07-09 - Account balance history

- Fact: Account-level balance history is exposed through `GET /api/account_balance_history?account_id=...&range=1M|3M|1Y|5Y|ALL`.
- Scope: Overview Account Allocation expanded rows.
- Source: M4/T4 implementation.
- Usage: Use `account_balances_history` for Plaid accounts and `account_value_estimates` for manual assets; always filter by `user_id`.

## 2026-07-10 - Daily sync schedule

- Fact: The global daily auto-sync time is stored in `app_config.daily_sync_time`, defaulting to `16:00` local server time.
- Scope: All active users; only an active administrator may update it through `/api/sync_schedule`.
- Source: M5/T4 implementation.
- Usage: The scheduler reads the database every 30 seconds, so a saved setting applies without restarting the Flask server.

## 2026-07-13 - Plaid investment income sync

- Fact: Investment transaction import accepts only `interest`, `interest receivable`, `dividend`, `qualified dividend`, and `non-qualified dividend`.
- Scope: Investment-like Plaid Items and the existing Transaction review flow.
- Source: User-approved mapping and `routes_plaid.py`.
- Usage: Map to `Income / Interest` or `Income / Dividend`; first import starts January 1 of the current year, later imports look back 90 days, and reviewed rows remain protected.

## 2026-07-14 - Net Worth driver attribution

- Fact: `GET /api/net_worth_drivers?date=YYYY-MM-DD` explains a Net Worth snapshot against its actual preceding snapshot with Top 3 Up/Down account contributions and an explicit unattributed residual.
- Scope: User-scoped Overview Net Worth Trend tooltip.
- Source: M4/T6 implementation and tests.
- Usage: Load per date on demand; assets use direct deltas, liabilities reverse the sign, manual history participates, and aggregate Legacy gaps remain unattributed.

## 2026-07-14 - Mobile Overview parity

- Fact: Mobile v1.0.1 uses the balanced Tiffany palette and opens Net Worth account drivers only after a chart-point tap.
- Scope: React Native Home screen and shared dashboard chart components.
- Source: M4/T7 implementation and mobile tests.
- Usage: Keep the chart summary compact and reuse `GET /api/net_worth_drivers?date=YYYY-MM-DD` for full details.

## 2026-07-16 - Allocation snapshot ownership

- Fact: Scheduled and manual Plaid sync write daily user-scoped rows to `account_allocation_snapshots`; Overview allocation endpoints only read the database.
- Scope: Account Allocation, Portfolio Allocation, and Allocation Trend on Overview.
- Source: M4/T8 implementation and allocation snapshot tests.
- Usage: Fetch holdings during sync, preserve the latest successful investment snapshot on holdings failure, and never add Plaid side effects back to Overview reads.

## 2026-07-20 - Merchant-history classification

- Fact: The most frequent reviewed Category/Subcategory pair wins when the winning pair has at least three posted examples for the same normalized merchant and direction; first-place ties use the first stored pair.
- Scope: Plaid sync prediction, review-time propagation, and startup backfill.
- Source: M2/T4 implementation and regression tests.
- Usage: Always scope history and Category/Subcategory config by `user_id`; preserve deterministic stored order when resolving a first-place tie.

## 2026-07-28 - Net Worth history as-of balances

- Fact: `GET /api/allocation_history` carries each account's latest known balance forward to later Plaid history dates until a newer balance is stored.
- Scope: Overview Net Worth Trend and Allocation Trend.
- Source: M4/T9 implementation and allocation history regression test.
- Usage: Treat per-institution daily sync as partial input; never interpret missing same-day account rows as a zero balance.
