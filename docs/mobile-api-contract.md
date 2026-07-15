# MeowBillion Mobile API Contract

The Android app uses the existing Flask API as its system of record. It sends `Authorization: Bearer <access_token>` after mobile login; existing browser session authentication remains supported.

## Authentication

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| POST | `/api/auth/mobile/login` | `email`, `password`, `device_name` | `access_token`, `expires_at`, `user` |
| POST | `/api/auth/mobile/logout` | Bearer token | `status` |
| GET | `/api/auth/mobile/sessions` | Bearer token | safe device metadata only |

Mobile access tokens are random values. SQLite stores only their SHA-256 hashes. A revoked or expired token receives `401 Authentication required` on protected endpoints.

## M2 Home

| Endpoint | Request | Home usage |
| --- | --- | --- |
| `GET /api/accounts` | Bearer token | account cards and net-worth fallback calculation |
| `GET /api/monthly_analysis` | Bearer token | latest monthly income and expense |
| `GET /api/transactions?reviewed_filter=unreviewed&page=1&limit=1` | Bearer token | authoritative `total_count` for the Home pending-transactions entry |
| `GET /api/credentials_status` | Bearer token | last successful sync display |
| `GET /api/allocation_accounts` | Bearer token | canonical net-worth formula, portfolio allocation, and read-only account allocation summary |
| `GET /api/allocation_history` | Bearer token | net-worth and asset-allocation trend charts |
| `GET /api/net_worth_drivers?date=YYYY-MM-DD` | Bearer token | on-demand account drivers after tapping a Net Worth point |

`/api/transactions` returns the desktop-compatible PascalCase fields, including `TransactionID`, `Merchant`, `Amount`, and `Direction`.

The Home Net Worth chart stays compact. Tapping a point opens the full Top 3 Up/Down account explanation in a native bottom sheet; closing it returns to the chart without reloading Home.

## M3 Transactions

The Transactions tab reuses `/api/transactions`, `/api/transaction_filter_options`, `/api/categories`, `/api/update_transaction`, `/api/unconfirm_transaction`, `/api/create_manual_transaction`, `/api/delete_transaction`, `/api/merge_candidates`, and `/api/merge_transactions`.

Pending transactions remain read-only. Backend errors are shown to the user; `401` also clears the secure mobile session.

## Local Development

- Android emulator default: `http://10.0.2.2:8090`.
- The app lets each installation override and persist its backend URL on the login screen or in **More** > **Connection settings**.
- A physical Android device must use the computer's reachable private-network HTTPS URL.
- Changing the configured URL clears the local mobile session before the new URL is used.
- The Flask server must not be directly exposed to the public internet.
