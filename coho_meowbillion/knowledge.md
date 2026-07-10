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
