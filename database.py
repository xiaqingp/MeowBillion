import os
import sqlite3
import json
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
]

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
            'prediction_reason': "TEXT DEFAULT ''"
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
