# PRD

## Status

- Project: MeowBillion
- Owner: surreal
- Approval: Approved as current baseline
- Last updated: 2026-07-14

## Summary

MeowBillion is a local-first personal finance workspace for household finance tracking. It supports multi-user login, user-scoped Plaid credentials and linked accounts, transaction review, spending analysis, travel/rental reporting, portfolio allocation, and local data ownership through SQLite.

The target user is a technically comfortable household or family that wants more control than consumer budgeting apps provide, especially around transaction cleanup, custom categories, travel spend, rentals, and investment allocation.

## Problem

Personal finance data is fragmented across banks, brokerages, spreadsheets, and manual records. Existing apps often hide raw data, limit custom reporting, and make correction workflows cumbersome. The product needs to keep synced data usable while allowing manual review, structured context assignment, and local ownership of sensitive financial data.

## Goals

- Provide a reliable local dashboard for net worth, allocation, accounts, transactions, spending, travel, and rentals.
- Keep each user's financial data isolated behind login.
- Let every user configure their own Plaid API credentials and linked institutions.
- Make transaction review efficient and consistent with user-defined categories and subcategories.
- Support structured Travel Trip and Rental Property assignment instead of relying on notes as grouping keys.
- Preserve historical reporting while allowing manual correction.
- Keep sensitive data and secrets out of Git.

## Non-Goals

- Public SaaS hosting.
- Shared family workspaces or cross-user data sharing.
- Global rule engines beyond current category prediction and rental property match rules.
- Long-history Plaid backfill beyond current sync scope.
- Committing personal finance databases, secrets, or local archives.

## Users and Use Cases

| User | Use case | Success outcome |
| --- | --- | --- |
| Primary user | Link personal banks and brokerages | Accounts, balances, transactions, and holdings sync into the local DB |
| Family member | Sign up with own Plaid credentials | Their data is isolated from other users |
| Reviewer | Categorize transactions | Reviewed transactions are locked until de-reviewed |
| Traveler | Track trip-level spending | Travel transactions are grouped by Trip and refunds reduce net spend |
| Rental owner | Track rental properties | Rental transactions are grouped by Property with monthly/yearly summaries |
| Investor | Review portfolio allocation | Accounts show allocation across Cash, Stock, Bond, Real Estate, and related buckets |

## Requirements

### Functional Requirements

- Users can sign in, sign up, and maintain isolated user-scoped data.
- Each user can store and manage Plaid credentials in-app.
- Users can link, repair, reconnect, sync, and clean cached Plaid institutions.
- Transactions can be filtered by search, date/month, account, amount, category, subcategory, status, and Trip/Property assignment, with a one-click reset to the default all-transactions view.
- Transaction filter selections survive a browser refresh within the current tab and remain isolated by user.
- Pending transactions are visible but not reviewable.
- Reviewed transactions are locked until de-reviewed, including Trip/Property assignment.
- Plaid investment income imports into Transactions for `interest`, `interest receivable`, `dividend`, `qualified dividend`, and `non-qualified dividend` only; other investment activity remains excluded.
- Imported investment income maps to `Income / Interest` or `Income / Dividend`, remains unreviewed, and preserves the original Plaid subtype for future analysis.
- Spending shows monthly and yearly Income totals broken down by subcategory, excluding pending transactions.
- Every non-zero Spending category or Income subcategory cell opens Transactions with the matching period and classification filters.
- Travel transactions can link to `trips.id` through `transactions.trip_id`.
- Rental transactions can link to `rental_properties.id` through `transactions.rental_property_id`.
- Trip Manager, Rental Property Manager, and Rental Rule Manager support inline table editing.
- Rental property match rules can predict Rentals category, subtype, and property for unreviewed transactions only.
- Travel reports group by Trip ID and show net spending; inflow/refund transactions reduce spend.
- Rental reports group by Rental Property ID and show property-level transactions, income, expense, monthly, and yearly summaries.
- Overview shows net worth trend, allocation trend, portfolio allocation, and account allocation.
- Net Worth Trend hover stays compact with date and Net Worth only; clicking/tapping a point opens its top three positive and negative account-level contributors plus any unattributed residual.

### UX Requirements

- Primary pages: Overview, Spending, Transactions, Travel, Rentals, Categories, Plaid.
- Transaction filters should be compact and fit on one row where reasonable.
- Review controls must clearly distinguish pending, reviewed, unreviewed, manual, transfer, legacy matched, and legacy imported states.
- Manager pages should favor editable tables over separate add/list forms.
- iPad/Tailscale usage must be practical through `HOST=0.0.0.0` on port `8090`.
- Web and mobile use the same Tiffany `#0ABAB5` logo background with a white cat outline.
- Web and mobile use a balanced Tiffany theme: Tiffany identifies brand and interaction states, while financial categories and status semantics retain distinct coordinated colors.
- Net Worth stays compact on both clients: web hover and the mobile selected-point summary show only the date and value; full driver details appear only after an explicit point click/tap and dismiss outside the detail surface.

### Data Requirements

- Primary storage is SQLite `finance.db`.
- Personal DB files, WAL/SHM files, `.env`, backups, and local archives are ignored by Git.
- User-scoped tables include Plaid tokens, accounts, transactions, balances, allocation data, manual assets, trips, rental properties, and rental rules.
- Categories and subcategories are stored in DB, not JSON fallback.
- Historical legacy data may exist for the primary user, but new users start without legacy assumptions.

### Operational Requirements

- Local development starts with `python server.py` or `start-server.bat`.
- The app defaults to port `8090`.
- Server should listen on `0.0.0.0` when remote access through Tailscale is desired.
- Every code change should be committed and pushed to GitHub.
- Tests should run before delivery when code behavior changes.

## Market and References

No external market scan was run during this baseline creation. Current baseline is derived from the existing repository and user-approved product direction. Deeper research is optional if the product moves toward broader distribution.

| Reference | Type | Relevant finding | Link |
| --- | --- | --- | --- |
| README.md | Project doc | Product scope includes Plaid accounts, transaction review, spending, travel/rental views, and portfolio allocation | Local repo |

## Decisions

| Decision | Rationale | Date |
| --- | --- | --- |
| Local-first SQLite app | Keeps personal finance data under local control | 2026-07-09 |
| Multi-user isolation without sharing | Family members need separate accounts and data, not shared views | 2026-07-09 |
| User-owned Plaid credentials | New users should not use the primary user's Plaid API credentials | 2026-07-09 |
| Structured Trips/Rentals metadata | Notes are free text and should not be the source of truth for grouping | 2026-07-09 |
| Reviewed transaction lock | Reviewed data should not change unless explicitly de-reviewed | 2026-07-09 |
| Travel refunds net against spend | Inflow/refund travel transactions reduce trip spend | 2026-07-09 |
| Import investment income only | Interest and dividend cash income belongs in reviewable Transactions; buys, sells, transfers, fees, and reinvestments do not belong in ordinary cash-flow review | 2026-07-13 |
| Tiffany logo across web and mobile | Keeps the in-app mark and browser favicon visually consistent with the mobile brand | 2026-07-13 |
| Balanced Tiffany web theme | Extends the brand beyond the logo without reducing chart readability or semantic color meaning | 2026-07-13 |
| Net Worth drivers live in the chart tooltip | Explains a selected snapshot without adding another permanent Overview panel | 2026-07-14 |
| Mobile reuses the balanced Tiffany theme and Net Worth driver API | Keeps Overview behavior and financial color meaning consistent across clients | 2026-07-14 |

## Open Questions

- Whether future family features should allow optional sharing or remain strictly isolated.
- Whether backups should be implemented through Google Drive, another cloud provider, or local encrypted archives.
- Whether the product should remain local-only or eventually support hosted deployment.

## Acceptance Criteria

- A user can start the app locally, sign in, and access their isolated workspace.
- A new user can add their own Plaid credentials and link accounts.
- Transactions can be synced, filtered, reviewed, de-reviewed, categorized, and assigned to Trips/Properties.
- Reviewed transactions cannot be edited until de-reviewed.
- Travel and Rental pages report using structured IDs, not note parsing.
- Travel refunds reduce trip spend and category totals.
- Portfolio and allocation reports continue to load from existing account/allocation data.
- Local sensitive data remains untracked by Git.
