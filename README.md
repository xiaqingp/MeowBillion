# MeowBillion

MeowBillion is a local-first personal finance workspace for Plaid-linked accounts, transaction review, spending analysis, travel/rental views, and portfolio allocation tracking.

## Setup

1. Create and activate a Python environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and add your Plaid credentials.
4. Start the app:

```powershell
python server.py
```

The app listens on `http://127.0.0.1:8090` by default, or the next available port.
On first launch, create the admin account in the setup screen. That first account claims any existing local data; later signups start with empty personal data.

## Local Data

The SQLite database (`finance.db`), Plaid credentials (`.env`), WAL/SHM files, and local archives are intentionally ignored by Git. Do not commit personal financial data or secrets.

For a new user, the app initializes an empty local database with default categories, including `Travel` and `Rentals`.
