import os
import sqlite3
import json
import uuid
from classifier import infer_transaction_classification_from_history, predict_custom_type

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')

USER_SCOPED_TABLES = [
    'plaid_tokens',
    'accounts',
    'transactions',
    'account_balances_history',
    'allocation_overrides',
    'manual_assets',
    'manual_asset_values',
    'allocation_history_snapshots',
    'account_value_estimates',
    'trips',
    'rental_properties',
    'rental_property_match_rules',
]

DEFAULT_ANALYSIS_RULES_CONFIG = {
    "travel": {
        "category": "Travel",
        "trip_source": "note",
        "category_source": "subtype",
        "year_prefix": True,
        "fallback_year": "Note",
    },
    "rentals": {
        "category": "Rentals",
        "property_source": "note",
        "category_source": "subtype",
        "fallback_property": "Unassigned",
        "fallback_category": "Unclassified",
    },
}


def _load_analysis_rules_for_user(conn, user_id):
    keys = [f"{user_id}:analysis_rules"] if user_id else []
    keys.append("analysis_rules")
    for key in keys:
        row = conn.execute("SELECT value FROM app_config WHERE key = ?", (key,)).fetchone()
        if row:
            try:
                data = json.loads(row["value"])
                if isinstance(data, dict):
                    merged = json.loads(json.dumps(DEFAULT_ANALYSIS_RULES_CONFIG))
                    for section, defaults in DEFAULT_ANALYSIS_RULES_CONFIG.items():
                        incoming = data.get(section) if isinstance(data.get(section), dict) else {}
                        for name, default in defaults.items():
                            merged[section][name] = incoming.get(name, default)
                    return merged
            except Exception:
                pass
    return json.loads(json.dumps(DEFAULT_ANALYSIS_RULES_CONFIG))


def _transaction_field(row, field_name, fallback=""):
    if field_name not in {"note", "subtype", "merchant"}:
        return fallback
    return row[field_name] or fallback


def _parse_trip_name(value, tx_date=None, year_prefix=True, fallback_year="Note"):
    text = (value or "").strip()
    tx_year = (tx_date or "")[:4]
    fallback = tx_year if tx_year.isdigit() else (fallback_year or "Note")
    if not text:
        return fallback, f"Unassigned Travel {fallback}"
    year = text[:4]
    if year_prefix and year.isdigit():
        trip = text[4:].strip(" -_|:/") or text
        return year, trip[:64]
    return fallback, text[:64]


def get_or_create_trip(conn, user_id, name, year, destination=None):
    clean_name = (name or "").strip() or f"Unassigned Travel {year or 'Unknown'}"
    clean_year = int(year) if str(year or "").isdigit() else None
    row = conn.execute(
        """
        SELECT id FROM trips
        WHERE user_id = ?
          AND COALESCE(year, -1) = COALESCE(?, -1)
          AND lower(name) = lower(?)
        LIMIT 1
        """,
        (user_id, clean_year, clean_name),
    ).fetchone()
    if row:
        return row["id"]
    trip_id = f"trip_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO trips (id, user_id, name, year, destination)
        VALUES (?, ?, ?, ?, ?)
        """,
        (trip_id, user_id, clean_name, clean_year, destination),
    )
    return trip_id


def get_or_create_rental_property(conn, user_id, name):
    clean_name = (name or "").strip() or "Unassigned Rental Property"
    row = conn.execute(
        """
        SELECT id FROM rental_properties
        WHERE user_id = ? AND lower(name) = lower(?)
        LIMIT 1
        """,
        (user_id, clean_name),
    ).fetchone()
    if row:
        return row["id"]
    property_id = f"rprop_{uuid.uuid4().hex}"
    conn.execute(
        """
        INSERT INTO rental_properties (id, user_id, name)
        VALUES (?, ?, ?)
        """,
        (property_id, user_id, clean_name),
    )
    return property_id


def migrate_travel_contexts(conn):
    users = [
        row["user_id"]
        for row in conn.execute(
            """
            SELECT DISTINCT user_id FROM transactions
            WHERE user_id IS NOT NULL AND user_id != ''
            """
        ).fetchall()
    ]
    for user_id in users:
        rules = _load_analysis_rules_for_user(conn, user_id)
        travel_rules = rules.get("travel") or {}
        category = str(travel_rules.get("category") or "Travel").strip().lower()
        rows = conn.execute(
            """
            SELECT transaction_id, date, merchant, note, subtype
            FROM transactions
            WHERE user_id = ?
              AND lower(COALESCE(type, '')) = ?
              AND (trip_id IS NULL OR trip_id = '')
            """,
            (user_id, category),
        ).fetchall()
        for row in rows:
            source = _transaction_field(row, travel_rules.get("trip_source"), "")
            year, name = _parse_trip_name(
                source,
                row["date"],
                bool(travel_rules.get("year_prefix", True)),
                travel_rules.get("fallback_year") or "Note",
            )
            trip_id = get_or_create_trip(conn, user_id, name, year)
            conn.execute(
                "UPDATE transactions SET trip_id = ? WHERE transaction_id = ? AND user_id = ?",
                (trip_id, row["transaction_id"], user_id),
            )


def migrate_rental_contexts(conn):
    users = [
        row["user_id"]
        for row in conn.execute(
            """
            SELECT DISTINCT user_id FROM transactions
            WHERE user_id IS NOT NULL AND user_id != ''
            """
        ).fetchall()
    ]
    for user_id in users:
        rules = _load_analysis_rules_for_user(conn, user_id)
        rental_rules = rules.get("rentals") or {}
        category = str(rental_rules.get("category") or "Rentals").strip().lower()
        fallback = rental_rules.get("fallback_property") or "Unassigned Rental Property"
        rows = conn.execute(
            """
            SELECT transaction_id, merchant, note, subtype
            FROM transactions
            WHERE user_id = ?
              AND lower(COALESCE(type, '')) = ?
              AND (rental_property_id IS NULL OR rental_property_id = '')
            """,
            (user_id, category),
        ).fetchall()
        for row in rows:
            name = (_transaction_field(row, rental_rules.get("property_source"), fallback) or fallback).strip()
            if name.lower() == "unassigned":
                name = "Unassigned Rental Property"
            property_id = get_or_create_rental_property(conn, user_id, name)
            conn.execute(
                """
                UPDATE transactions
                SET rental_property_id = ?
                WHERE transaction_id = ? AND user_id = ?
                """,
                (property_id, row["transaction_id"], user_id),
            )

def get_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError:
        pass  # ignore if in read-only or constrained env
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            role TEXT DEFAULT 'user',
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS user_plaid_credentials (
            user_id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            secret TEXT NOT NULL,
            environment TEXT NOT NULL DEFAULT 'development',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create plaid_tokens table
        conn.execute('''
        CREATE TABLE IF NOT EXISTS plaid_tokens (
            access_token TEXT PRIMARY KEY,
            item_id TEXT,
            institution_name TEXT,
            last_cursor TEXT,
            status TEXT DEFAULT 'active',
            error_message TEXT
        )
        ''')
        
        # Migrate plaid_tokens to add missing columns if table already existed
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(plaid_tokens)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'item_id' not in columns:
            cursor.execute("ALTER TABLE plaid_tokens ADD COLUMN item_id TEXT")
        if 'institution_name' not in columns:
            cursor.execute("ALTER TABLE plaid_tokens ADD COLUMN institution_name TEXT")
        if 'status' not in columns:
            cursor.execute("ALTER TABLE plaid_tokens ADD COLUMN status TEXT DEFAULT 'active'")
        if 'error_message' not in columns:
            cursor.execute("ALTER TABLE plaid_tokens ADD COLUMN error_message TEXT")
        if 'created_at' not in columns:
            cursor.execute("ALTER TABLE plaid_tokens ADD COLUMN created_at TEXT")
            # Set default created_at to yesterday for existing tokens
            cursor.execute("UPDATE plaid_tokens SET created_at = datetime('now', '-1 day')")
        if 'holdings_sync_status' not in columns:
            cursor.execute("ALTER TABLE plaid_tokens ADD COLUMN holdings_sync_status TEXT DEFAULT 'no_holdings'")
        if 'holdings_last_synced' not in columns:
            cursor.execute("ALTER TABLE plaid_tokens ADD COLUMN holdings_last_synced TEXT")
        # Create accounts table
        conn.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            account_id TEXT PRIMARY KEY,
            name TEXT,
            official_name TEXT,
            type TEXT,
            subtype TEXT,
            balance_current REAL,
            balance_available REAL,
            item_id TEXT,
            institution_name TEXT
        )
        ''')
        # Create base transactions table
        conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            date TEXT,
            type TEXT,
            merchant TEXT,
            amount REAL,
            direction TEXT,
            account_name TEXT
        )
        ''')
        # Create account_balances_history table
        conn.execute('''
        CREATE TABLE IF NOT EXISTS account_balances_history (
            account_id TEXT,
            date TEXT,
            balance_current REAL,
            balance_available REAL,
            PRIMARY KEY (account_id, date)
        )
        ''')
        # Create sync_metadata table
        conn.execute('''
        CREATE TABLE IF NOT EXISTS sync_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.execute(
            "INSERT OR IGNORE INTO app_config (key, value, updated_at) VALUES ('daily_sync_time', '16:00', CURRENT_TIMESTAMP)"
        )
        conn.execute('''
        CREATE TABLE IF NOT EXISTS allocation_overrides (
            account_id TEXT PRIMARY KEY,
            cash_pct REAL DEFAULT 0,
            stock_pct REAL DEFAULT 0,
            bond_pct REAL DEFAULT 0,
            real_estate_pct REAL DEFAULT 0,
            unclassified_pct REAL DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS manual_assets (
            asset_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            asset_type TEXT DEFAULT 'manual',
            value REAL DEFAULT 0,
            cash_pct REAL DEFAULT 0,
            stock_pct REAL DEFAULT 0,
            bond_pct REAL DEFAULT 0,
            real_estate_pct REAL DEFAULT 0,
            active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS manual_asset_values (
            asset_id TEXT NOT NULL,
            date TEXT NOT NULL,
            value REAL DEFAULT 0,
            PRIMARY KEY (asset_id, date),
            FOREIGN KEY (asset_id) REFERENCES manual_assets(asset_id)
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS allocation_history_snapshots (
            date TEXT PRIMARY KEY,
            cash REAL DEFAULT 0,
            stock REAL DEFAULT 0,
            bond REAL DEFAULT 0,
            real_estate REAL DEFAULT 0,
            liabilities REAL DEFAULT 0,
            source TEXT DEFAULT 'imported'
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS account_value_estimates (
            account_id TEXT NOT NULL,
            date TEXT NOT NULL,
            value REAL DEFAULT 0,
            cash_pct REAL DEFAULT 0,
            stock_pct REAL DEFAULT 100,
            bond_pct REAL DEFAULT 0,
            real_estate_pct REAL DEFAULT 0,
            source TEXT DEFAULT 'estimated',
            PRIMARY KEY (account_id, date)
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            year INTEGER,
            destination TEXT,
            budget REAL,
            currency TEXT DEFAULT 'USD',
            travelers TEXT,
            notes TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS rental_properties (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            state TEXT,
            active INTEGER DEFAULT 1,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS rental_property_match_rules (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            rental_property_id TEXT NOT NULL,
            name TEXT,
            merchant_contains TEXT,
            account_name_contains TEXT,
            direction TEXT,
            amount_min REAL,
            amount_max REAL,
            default_subtype TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()

        cursor = conn.cursor()
        for table in USER_SCOPED_TABLES:
            cursor.execute(f"PRAGMA table_info({table})")
            scoped_columns = [row[1] for row in cursor.fetchall()]
            if 'user_id' not in scoped_columns:
                print(f"Adding {table} column: user_id (TEXT)")
                conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")

        # Dynamic Schema Upgrades: Auto-migration check: add new columns if they do not exist
        cursor.execute("PRAGMA table_info(transactions)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        new_columns = {
            'authorized_date': 'TEXT',
            'pending': 'INTEGER',
            'categories': 'TEXT',
            'location': 'TEXT',
            'payment_channel': 'TEXT',
            'is_b': "TEXT DEFAULT 'n'",
            'ratio': 'REAL DEFAULT 1.0',
            'ipay': 'REAL',
            'bpay': 'REAL',
            'mown': 'REAL DEFAULT 0.0',
            'note': "TEXT DEFAULT ''",
            'subtype': "TEXT DEFAULT ''",
            'reviewed': 'INTEGER DEFAULT 0',
            'imported_from_legacy': 'INTEGER DEFAULT 0',
            'legacy_matched': 'INTEGER DEFAULT 0',
            'prediction_source': "TEXT DEFAULT ''",
            'prediction_confidence': 'REAL DEFAULT 0',
            'prediction_reason': "TEXT DEFAULT ''",
            'trip_id': 'TEXT',
            'rental_property_id': 'TEXT'
        }
        
        for col_name, col_type in new_columns.items():
            if col_name not in existing_columns:
                print(f"Adding database column: {col_name} ({col_type})")
                conn.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}")
        
        # Dynamic Schema Upgrades for accounts table
        cursor.execute("PRAGMA table_info(accounts)")
        existing_acc_columns = [row[1] for row in cursor.fetchall()]
        new_acc_columns = {
            'balance_current': 'REAL',
            'balance_available': 'REAL',
            'item_id': 'TEXT',
            'institution_name': 'TEXT'
        }
        for col_name, col_type in new_acc_columns.items():
            if col_name not in existing_acc_columns:
                print(f"Adding accounts column: {col_name} ({col_type})")
                conn.execute(f"ALTER TABLE accounts ADD COLUMN {col_name} {col_type}")
        
        # Backfill default values and force reviewed = 0 for ALL existing records if NULL
        conn.execute("UPDATE transactions SET is_b = 'n' WHERE is_b IS NULL")
        conn.execute("UPDATE transactions SET ratio = 1.0 WHERE ratio IS NULL")
        conn.execute("UPDATE transactions SET mown = 0.0 WHERE mown IS NULL")
        conn.execute("UPDATE transactions SET note = '' WHERE note IS NULL")
        conn.execute("UPDATE transactions SET subtype = '' WHERE subtype IS NULL")
        conn.execute("UPDATE transactions SET reviewed = 0 WHERE reviewed IS NULL")
        
        # Backfill ipay / bpay calculations
        conn.execute("""
            UPDATE transactions 
            SET ipay = CASE WHEN direction = 'inflow' THEN amount ELSE -amount END 
            WHERE ipay IS NULL
        """)
        conn.execute("UPDATE transactions SET bpay = 0.0 WHERE bpay IS NULL")
        
        # Retroactively predict and update category Types for unreviewed, non-legacy records only (if type is missing or empty)
        cursor.execute("SELECT transaction_id, categories, merchant, direction FROM transactions WHERE reviewed = 0 AND imported_from_legacy = 0 AND (type IS NULL OR type = '')")
        existing_txs = cursor.fetchall()
        for r in existing_txs:
            tx_id, cats_json, merchant, direction = r
            plaid_primary = 'OTHER'
            plaid_detailed = 'OTHER'
            try:
                cats = json.loads(cats_json or '[]')
                if len(cats) > 0:
                    plaid_primary = cats[0]
                if len(cats) > 1:
                    plaid_detailed = cats[1]
            except Exception as ex:
                pass
            learned = infer_transaction_classification_from_history(cursor, merchant, direction)
            if learned:
                conn.execute(
                    "UPDATE transactions SET type = ?, subtype = ? WHERE transaction_id = ?",
                    (learned["type"], learned["subtype"], tx_id)
                )
            else:
                predicted = predict_custom_type(plaid_primary, plaid_detailed, merchant, direction == 'inflow')
                conn.execute("UPDATE transactions SET type = ? WHERE transaction_id = ?", (predicted, tx_id))
            
        # 5. Automatically detect and apply 'Internal Transfer' type for all unreviewed transactions (excluding legacy/manual ones)
        cursor.execute("SELECT transaction_id, date, amount, direction, account_name FROM transactions WHERE reviewed = 0 AND imported_from_legacy = 0 AND account_name != 'Legacy'")
        all_unreviewed = cursor.fetchall()
        for r in all_unreviewed:
            tx_id, date, amount, direction, account_name = r
            detect_and_apply_transfer_type(cursor, tx_id, date, amount, direction, account_name)

        # Create indexes after schema upgrades so a brand-new empty database has every indexed column.
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date DESC, transaction_id DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_reviewed ON transactions(reviewed)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_direction ON transactions(direction)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, date DESC, transaction_id DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_plaid_tokens_user ON plaid_tokens(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_balances_history_date ON account_balances_history(date DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_balances_history_user_date ON account_balances_history(user_id, date DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trips_user_year ON trips(user_id, year, name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rental_properties_user_active ON rental_properties(user_id, active, name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rental_rules_property ON rental_property_match_rules(user_id, rental_property_id, enabled)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_trip ON transactions(user_id, trip_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_rental_property ON transactions(user_id, rental_property_id)")

        migrate_travel_contexts(conn)
        migrate_rental_contexts(conn)

        env_client_id = os.getenv('PLAID_CLIENT_ID', '').strip()
        env_secret = os.getenv('PLAID_SECRET', '').strip()
        env_environment = os.getenv('PLAID_ENV', 'development').strip() or 'development'
        if env_client_id and env_secret:
            cursor.execute(
                """
                SELECT id FROM users
                WHERE id NOT IN (SELECT user_id FROM user_plaid_credentials)
                  AND (
                    role = 'admin'
                    OR id IN (SELECT DISTINCT user_id FROM plaid_tokens WHERE user_id IS NOT NULL AND user_id != '')
                  )
                """
            )
            for row in cursor.fetchall():
                conn.execute(
                    """
                    INSERT OR IGNORE INTO user_plaid_credentials
                    (user_id, client_id, secret, environment, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (row['id'], env_client_id, env_secret, env_environment)
                )

        conn.commit()

def detect_and_apply_transfer_type(cursor, tx_id, date, amount, direction, account_name, user_id=None):
    """
    Search for a counterpart transaction (same amount, opposite direction, diff account, within 3 days).
    If found, set both transactions to 'Internal Transfer' type. Excludes legacy/manual records.
    """
    if not date or amount is None or not direction or not account_name or account_name == 'Legacy':
        return False
        
    user_clause = "AND user_id = ?" if user_id else ""
    params = [tx_id, amount, direction, account_name, date]
    if user_id:
        params.append(user_id)
    cursor.execute(
        """
        SELECT transaction_id, reviewed FROM transactions
        WHERE transaction_id != ?
          AND amount = ?
          AND direction != ?
          AND account_name != ?
          AND account_name != 'Legacy'
          AND imported_from_legacy = 0
          AND abs(julianday(date) - julianday(?)) <= 3
          {user_clause}
        """.format(user_clause=user_clause),
        tuple(params)
    )
    counterparts = cursor.fetchall()
    if counterparts:
        # Update current transaction type
        if user_id:
            cursor.execute("UPDATE transactions SET type = 'Internal Transfer' WHERE transaction_id = ? AND user_id = ?", (tx_id, user_id))
        else:
            cursor.execute("UPDATE transactions SET type = 'Internal Transfer' WHERE transaction_id = ?", (tx_id,))
        # Update counterparts if they are not reviewed
        for cp in counterparts:
            cp_id, cp_reviewed = cp
            if cp_reviewed == 0:
                if user_id:
                    cursor.execute("UPDATE transactions SET type = 'Internal Transfer' WHERE transaction_id = ? AND user_id = ?", (cp_id, user_id))
                else:
                    cursor.execute("UPDATE transactions SET type = 'Internal Transfer' WHERE transaction_id = ?", (cp_id,))
        return True
    return False
