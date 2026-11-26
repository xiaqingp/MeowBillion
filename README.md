# MeowBillion

MeowBillion is a local-first personal finance workspace for Plaid-linked accounts, transaction review, spending analysis, travel/rental views, and portfolio allocation tracking.

## Setup

1. Create and activate a Python environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set app-level values such as `APP_SECRET_KEY`.
4. Start the app:

Double-click `start-server.bat` to start the app. It listens on `0.0.0.0:8090`,
so it is available locally at `http://127.0.0.1:8090` and through the machine's
Tailscale IP at `http://<tailscale-ip>:8090`. Double-click `stop-server.bat` to stop it.
On first launch, create the admin account in the setup screen. That first account claims any existing local data; later signups start with empty personal data.
Each user adds their own Plaid API credentials in Plaid Settings before linking banks.

## Local Data

The SQLite database (`finance.db`), Plaid credentials (`.env`), WAL/SHM files, and local archives are intentionally ignored by Git. Do not commit personal financial data or secrets.

For a new user, the app initializes an empty local database with default categories, including `Travel` and `Rentals`.

## Server operations

See [startup, backup, and recovery instructions](ops/README.md) for the systemd units and backup script used by the Linux server.
