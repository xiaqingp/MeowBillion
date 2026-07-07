import os
import json
import time
import re
import threading
from flask import Blueprint, request, jsonify
import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.link_token_transactions import LinkTokenTransactions

from database import get_db, detect_and_apply_transfer_type
from auth import current_user_id
from classifier import constrain_category_to_config, infer_transaction_classification_from_history, normalize_merchant_key, predict_custom_type, predict_transaction_classification
from routes_config import load_categories_config_from_db
from routes_transactions import fetch_paginated_transactions

plaid_bp = Blueprint('plaid', __name__)

def get_institution_name(client, institution_id):
    if not client or not institution_id:
        return "Bank Link"
    try:
        from plaid.model.institutions_get_by_id_request import InstitutionsGetByIdRequest
        req = InstitutionsGetByIdRequest(
            institution_id=institution_id,
            country_codes=[CountryCode('US')]
        )
        res = client.institutions_get_by_id(req)
        return res.to_dict().get('institution', {}).get('name', 'Bank Link')
    except Exception as e:
        print(f"Error fetching institution name for {institution_id}: {e}")
        return "Bank Link"

LAST_BALANCES_FETCH_TIME = 0.0

ASSET_BUCKETS = ("Cash", "Stock", "Bond", "Real Estate")
ALLOCATION_CACHE = {"time": 0.0, "payload": None, "user_id": None}
ALLOCATION_CACHE_LOCK = threading.Lock()

def empty_asset_buckets():
    return {key: 0.0 for key in ASSET_BUCKETS}

def coerce_asset_bucket(bucket):
    return bucket if bucket in ASSET_BUCKETS else 'Cash'

def classify_security_bucket(security):
    sec_type = (security.get('type') or '').lower()
    name = (security.get('name') or '').lower()
    ticker = (security.get('ticker_symbol') or '').lower()

    if sec_type == 'fixed income' or 'bond' in name or 'treasury' in name or 't-bill' in name or 'fixed income' in name or re.search(r'\bcd\b', name):
        return 'Bond'
    if sec_type in ['cash', 'money market'] or ticker in ['spaxx', 'fdrxx', 'deposit'] or 'sweep' in name or 'cash' in name or 'deposit progrm' in name or 'deposit program' in name:
        return 'Cash'
    if sec_type in ['equity', 'cryptocurrency']:
        return 'Stock'
    if sec_type in ['etf', 'mutual fund']:
        if any(k in name for k in ['bond', 'treasury', 'fixed income', 't-bill', 'short-term', 'inflation', 'yield', 'corp', 'municipal']):
            return 'Bond'
        return 'Stock'
    return 'Stock'

def asset_bucket_total(buckets):
    return sum(float(v or 0.0) for v in buckets.values())

def holding_market_value(holding, security):
    value = float(holding.get('institution_value') or 0.0)
    sec_type = (security.get('type') or '').lower()
    if sec_type == 'fixed income':
        quantity = holding.get('quantity')
        price = holding.get('institution_price')
        if quantity is not None and price is not None:
            calculated = float(quantity or 0.0) * float(price or 0.0) / 100.0
            if calculated > value * 10:
                return calculated
    return value

def merchant_names_match(left, right):
    left_key = normalize_merchant_key(left)
    right_key = normalize_merchant_key(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    return left_key.startswith(right_key) or right_key.startswith(left_key)

def find_pending_duplicate(cursor, tx_id, merchant, amount, direction, account_id, date_str, auth_date_str, user_id=None):
    if not merchant or not account_id or not date_str:
        return None
    user_clause = "AND user_id = ?" if user_id else ""
    params = [tx_id, account_id, amount, direction, date_str, auth_date_str, auth_date_str]
    if user_id:
        params.insert(1, user_id)
    cursor.execute(
        """
        SELECT transaction_id, date, authorized_date, merchant, type, subtype, is_b, ratio, ipay, bpay, mown, note, reviewed,
               imported_from_legacy, legacy_matched
        FROM transactions
        WHERE transaction_id != ?
          {user_clause}
          AND pending = 1
          AND account_name = ?
          AND amount = ?
          AND direction = ?
          AND imported_from_legacy = 0
          AND ABS(julianday(date) - julianday(?)) <= 3
          AND (
              COALESCE(authorized_date, date) = COALESCE(?, authorized_date, date)
              OR ABS(julianday(COALESCE(authorized_date, date)) - julianday(COALESCE(?, date))) <= 3
          )
        ORDER BY reviewed DESC, date DESC
        """.format(user_clause=user_clause),
        tuple(params)
    )
    for row in cursor.fetchall():
        if merchant_names_match(merchant, row['merchant']):
            return row
    return None

def load_allocation_overrides():
    user_id = current_user_id()
    try:
        with get_db() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS allocation_overrides (
                    account_id TEXT PRIMARY KEY,
                    cash_pct REAL DEFAULT 0,
                    stock_pct REAL DEFAULT 0,
                    bond_pct REAL DEFAULT 0,
                    real_estate_pct REAL DEFAULT 0,
                    unclassified_pct REAL DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            rows = conn.execute(
                "SELECT account_id, cash_pct, stock_pct, bond_pct, real_estate_pct, unclassified_pct FROM allocation_overrides WHERE user_id = ?",
                (user_id,)
            ).fetchall()
            if rows:
                return {
                    r['account_id']: {
                        "Cash": r['cash_pct'],
                        "Stock": r['stock_pct'],
                        "Bond": r['bond_pct'],
                        "Real Estate": r['real_estate_pct']
                    }
                    for r in rows
                }
    except Exception:
        pass
    return {}

def save_allocation_overrides(data):
    user_id = current_user_id()
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS allocation_overrides (
                account_id TEXT PRIMARY KEY,
                cash_pct REAL DEFAULT 0,
                stock_pct REAL DEFAULT 0,
                bond_pct REAL DEFAULT 0,
                real_estate_pct REAL DEFAULT 0,
                unclassified_pct REAL DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute("DELETE FROM allocation_overrides WHERE user_id = ?", (user_id,))
        for account_id, percentages in (data or {}).items():
            pct = normalize_percentages(percentages)
            conn.execute(
                """
                INSERT OR REPLACE INTO allocation_overrides
                (account_id, cash_pct, stock_pct, bond_pct, real_estate_pct, unclassified_pct, updated_at, user_id)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
                """,
                (
                    account_id,
                    pct["Cash"],
                    pct["Stock"],
                    pct["Bond"],
                    pct["Real Estate"],
                    pct.get("Unclassified", 0.0),
                    user_id
                )
            )
        conn.commit()

def normalize_percentages(percentages):
    normalized = {}
    total = 0.0
    for key in ASSET_BUCKETS:
        try:
            val = float((percentages or {}).get(key, 0.0))
        except Exception:
            val = 0.0
        val = max(val, 0.0)
        normalized[key] = val
        total += val
    if total <= 0:
        normalized["Cash"] = 100.0
        total = 100.0
    if abs(total - 100.0) > 0.001:
        for key in normalized:
            normalized[key] = normalized[key] * 100.0 / total
    return normalized

def buckets_from_percentages(balance, percentages):
    pct = normalize_percentages(percentages)
    return {key: float(balance or 0.0) * pct[key] / 100.0 for key in pct}

def normalize_account_asset_buckets(account_summary):
    balance = float(account_summary.get('balance_current') or 0.0)
    raw_buckets = account_summary.get('categories') or {}
    buckets = empty_asset_buckets()
    for key, value in raw_buckets.items():
        target_key = coerce_asset_bucket(key)
        buckets[target_key] += float(value or 0.0)
    account_summary['categories'] = buckets
    total = asset_bucket_total(buckets)

    if total <= 0:
        if account_summary.get('type') == 'depository':
            buckets['Cash'] = balance
        elif account_summary.get('type') == 'investment':
            buckets['Cash'] = balance
        return

    if total > balance:
        overage = total - balance
        cash_reduction = min(float(buckets.get('Cash') or 0.0), overage)
        buckets['Cash'] = float(buckets.get('Cash') or 0.0) - cash_reduction
        overage -= cash_reduction

        if overage > 0:
            non_cash_total = sum(float(buckets.get(k) or 0.0) for k in ['Stock', 'Bond', 'Real Estate'])
            target_non_cash_total = max(balance - float(buckets.get('Cash') or 0.0), 0.0)
            if non_cash_total > 0:
                scale = target_non_cash_total / non_cash_total
                for key in ['Stock', 'Bond', 'Real Estate']:
                    buckets[key] = float(buckets.get(key) or 0.0) * scale
    elif total < balance:
        buckets['Cash'] = float(buckets.get('Cash') or 0.0) + (balance - total)

def load_user_plaid_credentials(user_id=None):
    user_id = user_id or current_user_id()
    if not user_id:
        return None
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT client_id, secret, environment, updated_at
            FROM user_plaid_credentials
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()
    return dict(row) if row else None


def get_plaid_client(user_id=None):
    creds = load_user_plaid_credentials(user_id)
    if not creds or not (creds.get('client_id') or '').strip() or not (creds.get('secret') or '').strip():
        return None

    plaid_env = (creds.get('environment') or 'development').strip()
    if plaid_env == 'sandbox':
        host = plaid.Environment.Sandbox
    elif plaid_env == 'development':
        host = plaid.Environment.Development
    else:
        host = plaid.Environment.Production

    configuration = plaid.Configuration(
        host=host,
        api_key={
            'clientId': creds['client_id'],
            'secret': creds['secret'],
        }
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


@plaid_bp.route('/api/plaid_credentials', methods=['GET', 'POST'])
def plaid_credentials_api():
    user_id = current_user_id()
    if request.method == 'GET':
        creds = load_user_plaid_credentials(user_id)
        return jsonify({
            "has_credentials": bool(creds),
            "client_id": creds.get('client_id') if creds else "",
            "environment": creds.get('environment') if creds else "development",
            "updated_at": creds.get('updated_at') if creds else None
        })

    data = request.get_json(silent=True) or {}
    client_id = (data.get('client_id') or '').strip()
    secret = (data.get('secret') or '').strip()
    environment = (data.get('environment') or 'development').strip()
    if environment not in ('sandbox', 'development', 'production'):
        return jsonify({"error": "Environment must be sandbox, development, or production"}), 400
    if not client_id:
        return jsonify({"error": "Missing Plaid client ID"}), 400

    existing = load_user_plaid_credentials(user_id)
    if not secret and existing:
        secret = existing.get('secret') or ''
    if not secret:
        return jsonify({"error": "Missing Plaid secret"}), 400

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO user_plaid_credentials (user_id, client_id, secret, environment, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                client_id = excluded.client_id,
                secret = excluded.secret,
                environment = excluded.environment,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, client_id, secret, environment)
        )
        conn.commit()
    return jsonify({"status": "success"})

@plaid_bp.route('/api/create_link_token', methods=['POST'])
def create_link_token():
    user_id = current_user_id()
    client = get_plaid_client()
    if not client:
        return jsonify({"error": "Please save your Plaid API credentials in Plaid Settings first."}), 400
    
    # Check if we are running in update mode for a specific item
    item_id = None
    access_token = None
    has_investment_accounts = False
    try:
        data = request.get_json(silent=True) or {}
        item_id = data.get('item_id')
        if item_id:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT access_token, holdings_sync_status FROM plaid_tokens WHERE item_id = ? AND user_id = ?", (item_id, user_id))
            row = cursor.fetchone()
            if row:
                access_token = row['access_token']
                has_investment_accounts = item_has_investment_accounts(cursor, user_id, item_id, row['holdings_sync_status'])
            conn.close()
            if not access_token:
                return jsonify({"error": "Connection not found for repair."}), 404
    except Exception as parse_err:
        print(f"Error checking update mode payload: {parse_err}")
        if item_id:
            return jsonify({"error": "Unable to prepare repair mode for this connection."}), 500
        
    try:
        req_args = {
            "client_name": "MeowBillion",
            "country_codes": [CountryCode('US')],
            "language": 'en',
            "user": LinkTokenCreateRequestUser(client_user_id=user_id),
            "transactions": LinkTokenTransactions(days_requested=90)
        }
        
        if access_token:
            req_args["access_token"] = access_token
            if has_investment_accounts:
                req_args["additional_consented_products"] = [Products('investments')]
        else:
            req_args["products"] = [Products('transactions')]
            
        req = LinkTokenCreateRequest(**req_args)
        response = client.link_token_create(req)
        return jsonify({"link_token": response['link_token']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def item_has_investment_accounts(cursor, user_id, item_id, holdings_sync_status=None):
    if holdings_sync_status == 'synced':
        return True
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM accounts
        WHERE user_id = ?
          AND item_id = ?
          AND (
            type = 'investment'
            OR lower(COALESCE(subtype, '')) IN ('brokerage', '401k', 'ira', 'roth', 'mutual fund')
          )
        """,
        (user_id, item_id)
    )
    return cursor.fetchone()[0] > 0

@plaid_bp.route('/api/exchange_public_token', methods=['POST'])
def exchange_public_token():
    user_id = current_user_id()
    client = get_plaid_client()
    if not client:
        return jsonify({"error": "Plaid client not configured for this user."}), 400
    
    data = request.get_json()
    public_token = data.get('public_token')
    if not public_token:
        return jsonify({"error": "Missing public_token"}), 400

    try:
        exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = client.item_public_token_exchange(exchange_request)
        
        access_token = exchange_response['access_token']
        item_id = exchange_response['item_id']
        
        # Get institution name from Item
        inst_name = "Bank Link"
        try:
            from plaid.model.item_get_request import ItemGetRequest
            item_req = ItemGetRequest(access_token=access_token)
            item_res = client.item_get(item_req).to_dict()
            inst_id = item_res.get('item', {}).get('institution_id')
            if inst_id:
                inst_name = get_institution_name(client, inst_id)
        except Exception as inst_err:
            print(f"Error fetching institution info on exchange: {inst_err}")
        
        # Save token to database
        with get_db() as conn:
            # Check if token exists first to preserve last_cursor if it was already linked
            cursor = conn.cursor()
            cursor.execute("SELECT last_cursor FROM plaid_tokens WHERE access_token = ? AND user_id = ?", (access_token, user_id))
            row = cursor.fetchone()
            last_cursor = row['last_cursor'] if row else ""
            
            from datetime import datetime
            created_at_str = datetime.now().isoformat()
            conn.execute(
                """
                INSERT OR REPLACE INTO plaid_tokens 
                (access_token, item_id, institution_name, last_cursor, status, created_at, holdings_sync_status, user_id) 
                VALUES (?, ?, ?, ?, 'active', ?, 'pending', ?)
                """,
                (access_token, item_id, inst_name, last_cursor, created_at_str, user_id)
            )
            conn.commit()
            
        return jsonify({"status": "success", "item_id": item_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@plaid_bp.route('/api/accounts', methods=['GET'])
def get_accounts():
    import time
    start = time.perf_counter()
    user_id = current_user_id()
    client = get_plaid_client()
    accounts_list = []
    
    # 1. Load accounts from local DB first
    has_plaid = False
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT access_token FROM plaid_tokens WHERE user_id = ?", (user_id,))
        has_plaid = len(cursor.fetchall()) > 0
        
        cursor.execute("SELECT account_id, name, official_name, type, subtype, balance_current, balance_available, item_id, institution_name FROM accounts WHERE user_id = ?", (user_id,))
        db_accounts = [dict(r) for r in cursor.fetchall()]
        conn.close()
    except Exception as db_err:
        has_plaid = False
        db_accounts = []

    # Check if we need to fetch live balances from Plaid API (manual refresh or first run only)
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    plaid_db_accounts = [acc for acc in db_accounts if acc['account_id'] != 'Legacy']
    
    needs_live_fetch = (
        client and has_plaid and (
            force_refresh or
            len(plaid_db_accounts) == 0
        )
    )

    if needs_live_fetch:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT access_token FROM plaid_tokens WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            conn.close()
            
            with get_db() as db_conn:
                for r in rows:
                    access_token = r['access_token']
                    try:
                        req = AccountsBalanceGetRequest(access_token=access_token)
                        res = client.accounts_balance_get(req)
                        accounts = res.to_dict().get('accounts', [])
                        item_id = res.to_dict().get('item', {}).get('item_id', 'unknown_item')
                        inst_id = res.to_dict().get('item', {}).get('institution_id')
                        inst_name = get_institution_name(client, inst_id)
                        
                        # Update metadata and status to active
                        db_conn.execute(
                            "UPDATE plaid_tokens SET item_id = ?, institution_name = ?, status = 'active', error_message = NULL WHERE access_token = ? AND user_id = ?",
                            (item_id, inst_name, access_token, user_id)
                        )
                        
                        for acc in accounts:
                            balances = acc.get('balances', {})
                            db_conn.execute(
                                """
                                INSERT OR REPLACE INTO accounts 
                                (account_id, name, official_name, type, subtype, balance_current, balance_available, item_id, institution_name, user_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    acc.get('account_id'),
                                    acc.get('name'),
                                    acc.get('official_name'),
                                    acc.get('type'),
                                    acc.get('subtype'),
                                    balances.get('current'),
                                    balances.get('available'),
                                    item_id,
                                    inst_name,
                                    user_id
                                )
                            )
                            # Also save to account_balances_history!
                            from datetime import date as dt_date
                            db_conn.execute(
                                """
                                INSERT OR REPLACE INTO account_balances_history
                                (account_id, date, balance_current, balance_available, user_id)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (acc.get('account_id'), dt_date.today().isoformat(), balances.get('current'), balances.get('available'), user_id)
                            )
                            
                            accounts_list.append({
                                "account_id": acc.get('account_id'),
                                "item_id": item_id,
                                "institution_name": inst_name,
                                "name": acc.get('name'),
                                "official_name": acc.get('official_name') or acc.get('name'),
                                "type": acc.get('type'),
                                "subtype": acc.get('subtype'),
                                "balance_available": balances.get('available'),
                                "balance_current": balances.get('current'),
                                "currency": balances.get('iso_currency_code', 'USD')
                            })
                    except Exception as token_err:
                        status = 'error'
                        err_msg = str(token_err)
                        try:
                            if hasattr(token_err, 'body'):
                                err_body = json.loads(token_err.body)
                                err_code = err_body.get('error_code')
                                if err_code == 'ADDITIONAL_CONSENT_REQUIRED':
                                    status = 'error_consent'
                                elif err_code == 'ITEM_LOGIN_REQUIRED':
                                    status = 'error_login'
                        except Exception:
                            pass
                            
                        try:
                            with get_db() as status_conn:
                                status_conn.execute(
                                    "UPDATE plaid_tokens SET status = ?, error_message = ? WHERE access_token = ? AND user_id = ?",
                                    (status, err_msg, access_token, user_id)
                                )
                                status_conn.commit()
                        except Exception as status_err:
                            print(f"Error updating token error status: {status_err}")
                db_conn.commit()
                import time as t_mod
                global LAST_BALANCES_FETCH_TIME
                LAST_BALANCES_FETCH_TIME = t_mod.time()
        except Exception as e:
            pass
    else:
        # Serve directly from the database!
        for acc in db_accounts:
            if acc['account_id'] != 'Legacy':
                accounts_list.append({
                    "account_id": acc['account_id'],
                    "item_id": acc['item_id'] or "cached_item",
                    "institution_name": acc['institution_name'] or "Bank Link",
                    "name": acc['name'],
                    "official_name": acc['official_name'] or acc['name'],
                    "type": acc['type'],
                    "subtype": acc['subtype'],
                    "balance_available": acc['balance_available'],
                    "balance_current": acc['balance_current'],
                    "currency": "USD"
                })

    # 2. Check if we have Legacy transactions in DB and inject the virtual card
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE account_name = 'Legacy' AND user_id = ?", (user_id,))
        has_legacy = cursor.fetchone()[0] > 0
        
        if has_legacy:
            cursor.execute("SELECT SUM(amount) FROM transactions WHERE account_name = 'Legacy' AND direction = 'inflow' AND user_id = ?", (user_id,))
            inflow_sum = cursor.fetchone()[0] or 0.0
            cursor.execute("SELECT SUM(amount) FROM transactions WHERE account_name = 'Legacy' AND direction = 'outflow' AND user_id = ?", (user_id,))
            outflow_sum = cursor.fetchone()[0] or 0.0
            legacy_balance = inflow_sum - outflow_sum
            
            accounts_list.append({
                "account_id": "Legacy",
                "item_id": "legacy_item",
                "name": "Legacy",
                "official_name": "Legacy Spreadsheet Data",
                "type": "depository",
                "subtype": "checking",
                "balance_available": legacy_balance,
                "balance_current": legacy_balance,
                "currency": "USD",
                "is_virtual": True
            })
        conn.close()
    except Exception as e:
        pass
        
    duration = (time.perf_counter() - start) * 1000
    print(f" * [/api/accounts] Fetch took {duration:.2f}ms")
    return jsonify(accounts_list)

def summarize_sync_results(succeeded_items, failed_items):
    if succeeded_items and failed_items:
        return "partial_success"
    if failed_items and not succeeded_items:
        return "failed"
    return "success"

def perform_sync(user_id=None):
    """
    Core sync function that can be run by either the Flask endpoint or scheduler.
    Returns: sync summary dict
    """
    user_id = user_id or current_user_id()
    if not user_id:
        raise Exception("Authentication required.")

    client = get_plaid_client(user_id)
    if not client:
        raise Exception("Plaid client not configured for this user.")

    conn = get_db()
    cursor = conn.cursor()
    from datetime import datetime as dt_datetime
    sync_time_str = dt_datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("INSERT OR REPLACE INTO sync_metadata (key, value) VALUES (?, ?)", (f"{user_id}:last_sync_attempt_at", sync_time_str))

    cursor.execute("SELECT access_token, last_cursor, item_id, institution_name FROM plaid_tokens WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    
    if not rows:
        conn.commit()
        conn.close()
        return {"status": "success", "new_transactions_count": 0, "succeeded_items": [], "failed_items": []}
        
    from datetime import date as dt_date
    today_str = dt_date.today().isoformat()
    new_tx_count = 0
    succeeded_items = []
    failed_items = []
    configured_categories = load_categories_config_from_db().get('categories', [])
    
    for r in rows:
        access_token = r['access_token']
        item_id = r['item_id'] or 'unknown_item'
        inst_name = r['institution_name'] or 'Bank Link'
        item_new_count = 0
        warnings = []
        
        # Fetch and update current balances for these linked accounts
        try:
            try:
                bal_req = AccountsBalanceGetRequest(access_token=access_token)
                bal_res = client.accounts_balance_get(bal_req)
                balance_data = bal_res.to_dict()
            except Exception as balance_err:
                balance_data = {"item": {"item_id": item_id}, "accounts": []}
                warnings.append({
                    "scope": "balance",
                    "message": f"Balance update failed, but transactions sync will continue: {balance_err}"
                })

            item_id = balance_data.get('item', {}).get('item_id', item_id)
            inst_id = balance_data.get('item', {}).get('institution_id')
            if inst_id:
                inst_name = get_institution_name(client, inst_id)
            
            # Update status and metadata to active
            cursor.execute(
                "UPDATE plaid_tokens SET item_id = ?, institution_name = ?, status = 'active', error_message = NULL WHERE access_token = ? AND user_id = ?",
                (item_id, inst_name, access_token, user_id)
            )
            
            for acc in balance_data.get('accounts', []):
                bal = acc.get('balances', {})
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO accounts 
                    (account_id, name, official_name, type, subtype, balance_current, balance_available, item_id, institution_name, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        acc.get('account_id'),
                        acc.get('name'),
                        acc.get('official_name'),
                        acc.get('type'),
                        acc.get('subtype'),
                        bal.get('current'),
                        bal.get('available'),
                        item_id,
                        inst_name,
                        user_id
                    )
                )
                
                # Also save to account_balances_history!
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO account_balances_history
                    (account_id, date, balance_current, balance_available, user_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (acc.get('account_id'), today_str, bal.get('current'), bal.get('available'), user_id)
                )
                
            last_cursor = r['last_cursor'] or ''
            cursor_val = last_cursor
            has_more = True
            
            while has_more:
                if cursor_val:
                    sync_req = TransactionsSyncRequest(access_token=access_token, cursor=cursor_val)
                else:
                    sync_req = TransactionsSyncRequest(access_token=access_token)
                
                sync_res = client.transactions_sync(sync_req)
                res_dict = sync_res.to_dict()
                
                added = res_dict.get('added', [])
                modified = res_dict.get('modified', [])
                removed = res_dict.get('removed', [])
                added_ids = {tx.get('transaction_id') for tx in added}

                for removed_tx in removed:
                    removed_id = removed_tx.get('transaction_id')
                    if not removed_id:
                        continue
                    cursor.execute(
                        "DELETE FROM transactions WHERE transaction_id = ? AND imported_from_legacy = 0 AND user_id = ?",
                        (removed_id, user_id)
                    )

                for tx in added + modified:
                    tx_id = tx.get('transaction_id')
                    amount = float(tx.get('amount', 0))
                    
                    pf_cat = tx.get('personal_finance_category') or {}
                    primary = pf_cat.get('primary') or 'OTHER'
                    detailed = pf_cat.get('detailed') or 'OTHER'
                    
                    primary_clean = primary.replace('_', ' ').title()
                    detailed_clean = detailed.replace(primary + '_', '').replace('_', ' ').title()
                    
                    categories_list = [primary_clean]
                    if detailed_clean and detailed_clean != primary_clean:
                        categories_list.append(detailed_clean)
                    
                    merchant = tx.get('merchant_name') or tx.get('name', 'Unknown')
                    
                    import datetime
                    date = tx.get('date')
                    tx_date = date
                    if isinstance(tx_date, str):
                        try:
                            tx_date = datetime.datetime.strptime(tx_date, "%Y-%m-%d").date()
                        except:
                            pass
                    elif isinstance(tx_date, datetime.datetime):
                        tx_date = tx_date.date()
                        
                    if isinstance(tx_date, datetime.date):
                        limit_date = datetime.date.today() - datetime.timedelta(days=90)
                        if tx_date < limit_date:
                            continue # Skip transactions older than 3 months
                            
                    date_str = date.isoformat() if hasattr(date, 'isoformat') else str(date)
                    
                    auth_date = tx.get('authorized_date')
                    auth_date_str = auth_date.isoformat() if hasattr(auth_date, 'isoformat') else str(auth_date) if auth_date else None
                    
                    pending = 1 if tx.get('pending') else 0
                    
                    categories_json = json.dumps(categories_list)
                    location_json = json.dumps(tx.get('location', {}))
                    payment_channel = tx.get('payment_channel', 'other')
                    
                    is_income = amount < 0
                    direction = "inflow" if is_income else "outflow"
                    prediction = predict_transaction_classification(
                        cursor, primary, detailed, merchant, direction, configured_categories, user_id=user_id
                    )
                    custom_type = prediction["type"]
                    custom_subtype = prediction.get("subtype", "")
                    
                    abs_amount = abs(amount)
                    ipay_val = abs_amount if is_income else -abs_amount
                    bpay_val = 0.0
                    pending_duplicate = None
                    if pending == 0:
                        pending_duplicate = find_pending_duplicate(
                            cursor,
                            tx_id,
                            merchant,
                            abs_amount,
                            direction,
                            tx.get('account_id'),
                            date_str,
                            auth_date_str,
                            user_id
                        )
                        if pending_duplicate and int(pending_duplicate['reviewed'] or 0) == 1:
                            custom_type = pending_duplicate['type'] or custom_type
                            custom_subtype = pending_duplicate['subtype'] or custom_subtype
                            prediction = {
                                "source": "pending_match",
                                "confidence": 0.9,
                                "reason": "Copied from matching reviewed pending transaction."
                            }
                            ipay_val = float(pending_duplicate['ipay'] or ipay_val)
                            bpay_val = float(pending_duplicate['bpay'] or bpay_val)
                    
                    cursor.execute(
                        "SELECT reviewed FROM transactions WHERE transaction_id = ? AND user_id = ?",
                        (tx_id, user_id)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        cursor.execute(
                            """
                            UPDATE transactions 
                            SET date = ?, authorized_date = ?, pending = ?, categories = ?, location = ?, payment_channel = ?, account_name = ?
                            WHERE transaction_id = ?
                              AND user_id = ?
                            """,
                            (
                                date_str,
                                auth_date_str,
                                pending,
                                categories_json,
                                location_json,
                                payment_channel,
                                tx.get('account_id'),
                                tx_id,
                                user_id
                            )
                        )
                    else:
                        reviewed_val = int(pending_duplicate['reviewed'] or 0) if pending_duplicate else 0
                        is_b_val = pending_duplicate['is_b'] if pending_duplicate else 'n'
                        ratio_val = float(pending_duplicate['ratio'] or 1.0) if pending_duplicate else 1.0
                        mown_val = float(pending_duplicate['mown'] or 0.0) if pending_duplicate else 0.0
                        note_val = pending_duplicate['note'] if pending_duplicate else ''
                        cursor.execute(
                            """
                            INSERT INTO transactions 
                            (transaction_id, date, authorized_date, type, merchant, amount, direction, pending, categories, location, payment_channel, account_name, is_b, ratio, ipay, bpay, mown, note, subtype, reviewed, prediction_source, prediction_confidence, prediction_reason, user_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                tx_id, 
                                date_str, 
                                auth_date_str, 
                                custom_type, 
                                merchant, 
                                abs_amount, 
                                direction,
                                pending,
                                categories_json,
                                location_json,
                                payment_channel,
                                tx.get('account_id'),
                                is_b_val,
                                ratio_val,
                                ipay_val,
                                bpay_val,
                                mown_val,
                                note_val,
                                custom_subtype,
                                reviewed_val,
                                prediction.get("source", ""),
                                prediction.get("confidence", 0.0),
                                prediction.get("reason", ""),
                                user_id
                            )
                        )
                        if pending_duplicate:
                            cursor.execute(
                                "DELETE FROM transactions WHERE transaction_id = ? AND user_id = ?",
                                (pending_duplicate['transaction_id'], user_id)
                            )
                        if reviewed_val == 0:
                            detect_and_apply_transfer_type(
                                cursor,
                                tx_id,
                                date_str,
                                abs_amount,
                                direction,
                                tx.get('account_id'),
                                user_id
                            )
                        if tx_id in added_ids:
                            new_tx_count += 1
                            item_new_count += 1
                
                has_more = res_dict.get('has_more', False)
                cursor_val = res_dict.get('next_cursor', '')
                
            cursor.execute(
                "UPDATE plaid_tokens SET last_cursor = ? WHERE access_token = ? AND user_id = ?",
                (cursor_val, access_token, user_id)
            )
            succeeded_items.append({
                "item_id": item_id,
                "institution_name": inst_name,
                "new_transactions_count": item_new_count,
                "warnings": warnings
            })
        except Exception as token_err:
            status = 'error'
            err_msg = str(token_err)
            err_code = ''
            try:
                if hasattr(token_err, 'body'):
                    err_body = json.loads(token_err.body)
                    err_code = err_body.get('error_code')
                    if err_code == 'ADDITIONAL_CONSENT_REQUIRED':
                        status = 'error_consent'
                    elif err_code == 'ITEM_LOGIN_REQUIRED':
                        status = 'error_login'
            except Exception:
                pass
                
            cursor.execute(
                "UPDATE plaid_tokens SET status = ?, error_message = ? WHERE access_token = ? AND user_id = ?",
                (status, err_msg, access_token, user_id)
            )
            failed_items.append({
                "item_id": item_id,
                "institution_name": inst_name,
                "error_code": err_code,
                "status": status,
                "message": err_msg
            })
            print(f"Error syncing token {access_token[:15]}...: {err_msg}")
        
    # Update last sync time
    cursor.execute("INSERT OR REPLACE INTO sync_metadata (key, value) VALUES (?, ?)", (f"{user_id}:last_sync_time", sync_time_str))
    if succeeded_items:
        cursor.execute("INSERT OR REPLACE INTO sync_metadata (key, value) VALUES (?, ?)", (f"{user_id}:last_success_at", sync_time_str))
    
    conn.commit()
    conn.close()
    status = summarize_sync_results(succeeded_items, failed_items)
    return {
        "status": status,
        "new_transactions_count": new_tx_count,
        "succeeded_items": succeeded_items,
        "failed_items": failed_items
    }

@plaid_bp.route('/api/sync_transactions', methods=['POST'])
def sync_transactions():
    try:
        sync_result = perform_sync()
        result = fetch_paginated_transactions(page=1, limit=100)
        return jsonify({
            **sync_result,
            "transactions": result['transactions'],
            "page": result['page'],
            "limit": result['limit'],
            "total_count": result['total_count'],
            "total_pages": result['total_pages']
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@plaid_bp.route('/api/balance_history', methods=['GET'])
def get_balance_history():
    try:
        user_id = current_user_id()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT h.date, h.account_id, h.balance_current, h.balance_available, a.name, a.institution_name, a.type
            FROM account_balances_history h
            LEFT JOIN accounts a ON h.account_id = a.account_id AND a.user_id = h.user_id
            WHERE h.user_id = ?
            ORDER BY h.date ASC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        history = [dict(r) for r in rows]
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@plaid_bp.route('/api/backfill_institutions', methods=['GET'])
def backfill_institutions():
    user_id = current_user_id()
    client = get_plaid_client()
    if not client:
        return jsonify({"error": "Plaid client not configured"}), 400
        
    try:
        from plaid.model.item_get_request import ItemGetRequest
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT access_token FROM plaid_tokens WHERE user_id = ?", (user_id,))
            tokens = [r[0] for r in cursor.fetchall()]
            
            updated_count = 0
            for token in tokens:
                try:
                    req = ItemGetRequest(access_token=token)
                    res = client.item_get(req)
                    item_id = res.to_dict().get('item', {}).get('item_id')
                    inst_id = res.to_dict().get('item', {}).get('institution_id')
                    if inst_id:
                        inst_name = get_institution_name(client, inst_id)
                        # Update all accounts with this item_id to have the correct institution_name
                        cursor.execute("UPDATE accounts SET institution_name = ? WHERE item_id = ? AND user_id = ?", (inst_name, item_id, user_id))
                        updated_count += 1
                except Exception as inner_e:
                    print(f"Error backfilling token: {inner_e}")
            conn.commit()
        return jsonify({"status": "success", "updated_count": updated_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@plaid_bp.route('/api/disconnect_item', methods=['POST'])
def disconnect_item():
    try:
        user_id = current_user_id()
        data = request.get_json(silent=True) or {}
        item_id = data.get('item_id')
        if not item_id:
            return jsonify({"error": "Missing item_id"}), 400
            
        with get_db() as conn:
            conn.execute("DELETE FROM plaid_tokens WHERE item_id = ? AND user_id = ?", (item_id, user_id))
            conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def cleanup_cached_item(conn, item_id, new_item_id=None):
    import re
    user_id = current_user_id()
    cursor = conn.cursor()

    cursor.execute("SELECT account_id, institution_name, name FROM accounts WHERE item_id = ? AND user_id = ?", (item_id, user_id))
    old_acc_rows = cursor.fetchall()
    old_acc_ids = [r[0] for r in old_acc_rows]
    inst_name = old_acc_rows[0][1] if old_acc_rows else None

    new_acc_rows = []
    if new_item_id:
        cursor.execute("SELECT account_id, name FROM accounts WHERE item_id = ? AND user_id = ?", (new_item_id, user_id))
        new_acc_rows = cursor.fetchall()
    elif inst_name:
        cursor.execute("SELECT account_id, name FROM accounts WHERE institution_name = ? AND item_id != ? AND user_id = ?", (inst_name, item_id, user_id))
        new_acc_rows = cursor.fetchall()
    new_acc_ids = [r[0] for r in new_acc_rows]

    account_mapping = {}
    if old_acc_rows and new_acc_rows:
        for old_id, _, old_name in old_acc_rows:
            best_match_new_id = None
            best_score = -1
            old_name_lower = (old_name or '').lower()
            old_words = set(re.findall(r'\w+', old_name_lower))
            for new_id, new_name in new_acc_rows:
                new_name_lower = (new_name or '').lower()
                new_words = set(re.findall(r'\w+', new_name_lower))
                score = len(old_words.intersection(new_words))
                if score > best_score:
                    best_score = score
                    best_match_new_id = new_id
            if best_match_new_id:
                account_mapping[old_id] = best_match_new_id

    for old_id, new_id in account_mapping.items():
        conn.execute(
            "UPDATE OR IGNORE account_balances_history SET account_id = ? WHERE account_id = ? AND user_id = ?",
            (new_id, old_id, user_id)
        )

    migrated_transactions = 0
    if old_acc_ids and new_acc_ids:
        placeholders = ",".join(["?"] * len(old_acc_ids))
        cursor.execute(
            f"SELECT date, amount, merchant, type, subtype, is_b, ratio, ipay, bpay, mown, note, reviewed, imported_from_legacy, legacy_matched "
            f"FROM transactions WHERE user_id = ? AND account_name IN ({placeholders}) AND (reviewed = 1 OR type != 'OTHER' OR note != '')",
            [user_id] + old_acc_ids
        )
        old_txs = [dict(r) for r in cursor.fetchall()]

        for tx in old_txs:
            new_placeholders = ",".join(["?"] * len(new_acc_ids))
            cursor.execute(
                f"SELECT transaction_id, merchant FROM transactions "
                f"WHERE user_id = ? AND account_name IN ({new_placeholders}) AND date = ? AND amount = ? AND reviewed = 0",
                [user_id] + new_acc_ids + [tx['date'], tx['amount']]
            )
            matches = cursor.fetchall()
            if not matches:
                continue

            best_match_id = None
            if len(matches) == 1:
                best_match_id = matches[0][0]
            else:
                best_score = -1
                old_merchant = (tx['merchant'] or '').lower()
                old_words = set(re.findall(r'\w+', old_merchant))
                for m_id, m_name in matches:
                    new_merchant = (m_name or '').lower()
                    new_words = set(re.findall(r'\w+', new_merchant))
                    score = len(old_words.intersection(new_words))
                    if score > best_score:
                        best_score = score
                        best_match_id = m_id

            if best_match_id:
                conn.execute(
                    """
                    UPDATE transactions
                    SET type = ?, subtype = ?, is_b = ?, ratio = ?, ipay = ?, bpay = ?, mown = ?, note = ?, reviewed = ?, imported_from_legacy = ?, legacy_matched = ?
                    WHERE transaction_id = ? AND user_id = ?
                    """,
                    (
                        tx['type'], tx['subtype'], tx['is_b'], tx['ratio'], tx['ipay'], tx['bpay'], tx['mown'], tx['note'],
                        tx['reviewed'], tx['imported_from_legacy'], tx['legacy_matched'], best_match_id, user_id
                    )
                )
                migrated_transactions += 1

    for acc_id in old_acc_ids:
        conn.execute("DELETE FROM transactions WHERE account_name = ? AND user_id = ?", (acc_id, user_id))
        conn.execute("DELETE FROM account_balances_history WHERE account_id = ? AND user_id = ?", (acc_id, user_id))

    conn.execute("DELETE FROM accounts WHERE item_id = ? AND user_id = ?", (item_id, user_id))

    return {
        "old_accounts_deleted": len(old_acc_ids),
        "new_accounts_found": len(new_acc_ids),
        "account_mappings": len(account_mapping),
        "migrated_transactions": migrated_transactions
    }

@plaid_bp.route('/api/delete_cached_accounts', methods=['POST'])
def delete_cached_accounts():
    try:
        user_id = current_user_id()
        data = request.get_json(silent=True) or {}
        item_id = data.get('item_id')
        if not item_id:
            return jsonify({"error": "Missing item_id"}), 400
            
        import re
        with get_db() as conn:
            cursor = conn.cursor()
            
            # 1. Find old accounts to be deleted
            cursor.execute("SELECT account_id, institution_name, name FROM accounts WHERE item_id = ? AND user_id = ?", (item_id, user_id))
            old_acc_rows = cursor.fetchall()
            old_acc_ids = [r[0] for r in old_acc_rows]
            inst_name = old_acc_rows[0][1] if old_acc_rows else None
            
            # 2. Find new accounts of the same institution
            new_acc_ids = []
            new_acc_rows = []
            if inst_name:
                cursor.execute("SELECT account_id, name FROM accounts WHERE institution_name = ? AND item_id != ? AND user_id = ?", (inst_name, item_id, user_id))
                new_acc_rows = cursor.fetchall()
                new_acc_ids = [r[0] for r in new_acc_rows]
                
            # 3. Establish account mapping for balance history migration
            account_mapping = {}
            if old_acc_rows and new_acc_rows:
                for old_id, _, old_name in old_acc_rows:
                    best_match_new_id = None
                    best_score = -1
                    old_name_lower = (old_name or '').lower()
                    for new_id, new_name in new_acc_rows:
                        new_name_lower = (new_name or '').lower()
                        # Word overlap score
                        old_words = set(re.findall(r'\w+', old_name_lower))
                        new_words = set(re.findall(r'\w+', new_name_lower))
                        score = len(old_words.intersection(new_words))
                        if score > best_score:
                            best_score = score
                            best_match_new_id = new_id
                    if best_match_new_id:
                        account_mapping[old_id] = best_match_new_id

            # 4. Migrate balance history
            for old_id, new_id in account_mapping.items():
                conn.execute(
                    "UPDATE OR IGNORE account_balances_history SET account_id = ? WHERE account_id = ? AND user_id = ?",
                    (new_id, old_id, user_id)
                )
                
            # 5. Auto-migrate reviewed/custom transactions using merchant similarity matching
            if old_acc_ids and new_acc_ids:
                # Find all custom or reviewed transactions from the old accounts
                placeholders = ",".join(["?"] * len(old_acc_ids))
                cursor.execute(
                    f"SELECT date, amount, merchant, type, subtype, is_b, ratio, ipay, bpay, mown, note, reviewed, imported_from_legacy, legacy_matched "
                    f"FROM transactions WHERE user_id = ? AND account_name IN ({placeholders}) AND (reviewed = 1 OR type != 'OTHER' OR note != '')",
                    [user_id] + old_acc_ids
                )
                old_txs = [dict(r) for r in cursor.fetchall()]
                
                for tx in old_txs:
                    new_placeholders = ",".join(["?"] * len(new_acc_ids))
                    cursor.execute(
                        f"SELECT transaction_id, merchant FROM transactions "
                        f"WHERE user_id = ? AND account_name IN ({new_placeholders}) AND date = ? AND amount = ? AND reviewed = 0",
                        [user_id] + new_acc_ids + [tx['date'], tx['amount']]
                    )
                    matches = cursor.fetchall()
                    if matches:
                        # Find the best merchant match based on keyword overlap
                        best_match_id = None
                        if len(matches) == 1:
                            best_match_id = matches[0][0]
                        else:
                            best_score = -1
                            old_merchant = (tx['merchant'] or '').lower()
                            old_words = set(re.findall(r'\w+', old_merchant))
                            for m_id, m_name in matches:
                                new_merchant = (m_name or '').lower()
                                new_words = set(re.findall(r'\w+', new_merchant))
                                score = len(old_words.intersection(new_words))
                                if score > best_score:
                                    best_score = score
                                    best_match_id = m_id
                                    
                        if best_match_id:
                            conn.execute(
                                """
                                UPDATE transactions
                                SET type = ?, subtype = ?, is_b = ?, ratio = ?, ipay = ?, bpay = ?, mown = ?, note = ?, reviewed = ?, imported_from_legacy = ?, legacy_matched = ?
                                WHERE transaction_id = ? AND user_id = ?
                                """,
                                (
                                    tx['type'], tx['subtype'], tx['is_b'], tx['ratio'], tx['ipay'], tx['bpay'], tx['mown'], tx['note'], 
                                    tx['reviewed'], tx['imported_from_legacy'], tx['legacy_matched'], best_match_id, user_id
                                )
                            )
            
            # 6. Perform the cleanup
            for acc_id in old_acc_ids:
                conn.execute("DELETE FROM transactions WHERE account_name = ? AND user_id = ?", (acc_id, user_id))
                conn.execute("DELETE FROM account_balances_history WHERE account_id = ? AND user_id = ?", (acc_id, user_id))
                
            conn.execute("DELETE FROM accounts WHERE item_id = ? AND user_id = ?", (item_id, user_id))
            conn.commit()
            
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@plaid_bp.route('/api/finalize_replacement', methods=['POST'])
def finalize_replacement():
    try:
        user_id = current_user_id()
        data = request.get_json(silent=True) or {}
        old_item_id = data.get('old_item_id')
        new_item_id = data.get('new_item_id')
        if not old_item_id or not new_item_id:
            return jsonify({"error": "Missing old_item_id or new_item_id"}), 400
        if old_item_id == new_item_id:
            return jsonify({"error": "old_item_id and new_item_id are the same; use update mode instead"}), 400

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE item_id = ? AND user_id = ?", (new_item_id, user_id))
            new_account_count = cursor.fetchone()[0]
            if new_account_count == 0:
                return jsonify({"error": "New linked item has no synced accounts yet"}), 409

            stats = cleanup_cached_item(conn, old_item_id, new_item_id)
            conn.execute("DELETE FROM plaid_tokens WHERE item_id = ? AND user_id = ?", (old_item_id, user_id))
            conn.commit()

        return jsonify({"status": "success", **stats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@plaid_bp.route('/api/connections', methods=['GET'])
def get_connections():
    try:
        user_id = current_user_id()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, institution_name, status, error_message, last_cursor, holdings_sync_status, holdings_last_synced FROM plaid_tokens WHERE user_id = ?", (user_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        cursor.execute(
            """
            SELECT
                a.item_id,
                COALESCE(MAX(a.institution_name), 'Bank Link') AS institution_name,
                'disconnected' AS status,
                NULL AS error_message,
                NULL AS last_cursor,
                NULL AS holdings_sync_status,
                NULL AS holdings_last_synced,
                1 AS is_cached_only,
                COUNT(DISTINCT a.account_id) AS cached_accounts_count,
                COUNT(t.transaction_id) AS cached_transactions_count,
                SUM(CASE WHEN t.reviewed = 1 THEN 1 ELSE 0 END) AS cached_reviewed_transactions_count,
                MIN(t.date) AS first_transaction_date,
                MAX(t.date) AS last_transaction_date,
                COUNT(DISTINCT CASE
                    WHEN a.type = 'investment'
                      OR lower(COALESCE(a.subtype, '')) IN ('brokerage', '401k', 'ira', 'roth', 'mutual fund')
                    THEN a.account_id
                END) AS cached_investment_accounts_count
            FROM accounts a
            LEFT JOIN transactions t
              ON t.user_id = a.user_id
             AND t.account_name = a.account_id
            WHERE a.user_id = ?
              AND a.item_id IS NOT NULL
              AND a.item_id NOT IN ('', 'Legacy', 'unknown')
              AND NOT EXISTS (
                  SELECT 1
                  FROM plaid_tokens p
                  WHERE p.user_id = a.user_id
                    AND p.item_id = a.item_id
              )
            GROUP BY a.item_id
            """,
            (user_id,)
        )
        cached_rows = [dict(r) for r in cursor.fetchall()]
        meta = {}
        for key in ("last_sync_attempt_at", "last_success_at", "last_sync_time"):
            cursor.execute("SELECT value FROM sync_metadata WHERE key = ?", (f"{user_id}:{key}",))
            row = cursor.fetchone()
            if row:
                meta[key] = row[0]
        
        for r in rows:
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE item_id = ? AND type = 'investment' AND user_id = ?", (r['item_id'], user_id))
            has_plaid_investment_account = cursor.fetchone()[0] > 0
            has_synced_holdings = (r.get('holdings_sync_status') == 'synced')
            has_inv = has_plaid_investment_account or has_synced_holdings
            r['has_investments'] = has_inv
            r['last_cursor_available'] = bool(r.get('last_cursor'))
            r['last_sync_attempt_at'] = meta.get('last_sync_attempt_at')
            r['last_success_at'] = meta.get('last_success_at') or meta.get('last_sync_time')
            error_code = ''
            raw_error = r.get('error_message') or ''
            try:
                if raw_error.strip().startswith('{'):
                    error_code = (json.loads(raw_error).get('error_code') or '')
            except Exception:
                pass
            for code in ('ITEM_LOGIN_REQUIRED', 'ADDITIONAL_CONSENT_REQUIRED'):
                if not error_code and code in raw_error:
                    error_code = code
            r['error_code'] = error_code
        
        for r in cached_rows:
            r['has_investments'] = (r.get('cached_investment_accounts_count') or 0) > 0
            r['last_cursor_available'] = False
            r['last_sync_attempt_at'] = None
            r['last_success_at'] = None
            r['error_code'] = ''
        rows.extend(cached_rows)
            
        conn.close()
        
        connections = [r for r in rows if r['item_id']]
        return jsonify(connections)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@plaid_bp.route('/api/portfolio_allocation_details', methods=['GET'])
def get_portfolio_allocation_details():
    user_id = current_user_id()
    client = get_plaid_client()
    item_filter = (request.args.get('item_id') or '').strip()
    institution_filter = (request.args.get('institution') or '').strip().lower()

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT access_token, item_id, institution_name, status, holdings_sync_status, holdings_last_synced FROM plaid_tokens WHERE user_id = ?", (user_id,))
        token_rows = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT account_id, name, official_name, type, subtype, balance_current, balance_available, institution_name, item_id FROM accounts WHERE user_id = ?", (user_id,))
        account_rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
    except Exception as db_err:
        return jsonify({"error": f"Database error: {db_err}"}), 500

    if item_filter:
        token_rows = [r for r in token_rows if r.get('item_id') == item_filter]
        account_rows = [r for r in account_rows if r.get('item_id') == item_filter]
    elif institution_filter:
        token_rows = [r for r in token_rows if institution_filter in (r.get('institution_name') or '').lower()]
        item_ids = {r.get('item_id') for r in token_rows}
        if item_ids:
            account_rows = [r for r in account_rows if r.get('item_id') in item_ids]
        else:
            account_rows = [r for r in account_rows if institution_filter in (r.get('institution_name') or '').lower()]

    token_by_item = {r.get('item_id'): r for r in token_rows if r.get('item_id')}
    account_by_id = {r['account_id']: r for r in account_rows}
    investment_item_ids = {r.get('item_id') for r in account_rows if r.get('type') == 'investment'}
    institutions = {}

    def ensure_institution(item_id, institution_name):
        key = item_id or f"institution:{institution_name or 'Unknown'}"
        if key not in institutions:
            token = token_by_item.get(item_id) or {}
            institutions[key] = {
                "item_id": item_id,
                "institution_name": institution_name or token.get('institution_name') or "Bank Link",
                "status": token.get('status') or "unknown",
                "holdings_sync_status": token.get('holdings_sync_status') or "unknown",
                "holdings_last_synced": token.get('holdings_last_synced'),
                "categories": empty_asset_buckets(),
                "accounts": [],
                "holdings": []
            }
        return institutions[key]

    for acc in account_rows:
        if acc.get('account_id') == 'Legacy':
            continue
        inst = ensure_institution(acc.get('item_id'), acc.get('institution_name'))
        balance = float(acc.get('balance_current') or 0.0)
        account_summary = {
            "account_id": acc.get('account_id'),
            "name": acc.get('name'),
            "official_name": acc.get('official_name'),
            "type": acc.get('type'),
            "subtype": acc.get('subtype'),
            "balance_current": balance,
            "categories": empty_asset_buckets()
        }
        inst["accounts"].append(account_summary)

    holdings_account_ids = set()
    if client:
        from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
        for token in token_rows:
            item_id = token.get('item_id')
            if token.get('status') == 'error_consent' or item_id not in investment_item_ids:
                continue
            try:
                req = InvestmentsHoldingsGetRequest(access_token=token.get('access_token'))
                res = client.investments_holdings_get(req).to_dict()
                holdings = res.get('holdings', [])
                securities = res.get('securities', [])
                sec_map = {s['security_id']: s for s in securities}
                item_institution = token.get('institution_name') or "Bank Link"
                item_has_holdings = False

                for h in holdings:
                    account_id = h.get('account_id')
                    acc = account_by_id.get(account_id)
                    if not acc:
                        continue

                    inst = ensure_institution(item_id, acc.get('institution_name') or item_institution)
                    security = sec_map.get(h.get('security_id'), {})
                    bucket = coerce_asset_bucket(classify_security_bucket(security))
                    value = holding_market_value(h, security)
                    holdings_account_ids.add(account_id)
                    item_has_holdings = True

                    inst["categories"][bucket] += value
                    for account_summary in inst["accounts"]:
                        if account_summary.get("account_id") == account_id:
                            account_summary["categories"][bucket] += value
                            break

                    inst["holdings"].append({
                        "account_id": account_id,
                        "account_name": acc.get('name'),
                        "security_name": security.get('name') or "Unknown Security",
                        "ticker_symbol": security.get('ticker_symbol'),
                        "security_type": security.get('type'),
                        "category": bucket,
                        "value": value,
                        "quantity": h.get('quantity')
                    })

                from datetime import datetime, timedelta
                holdings_sync_status = 'synced' if item_has_holdings else 'no_holdings'
                has_investment = any(a.get('item_id') == item_id and a.get('type') == 'investment' for a in account_rows)
                if not item_has_holdings and has_investment:
                    created_at = None
                    try:
                        with get_db() as status_conn:
                            status_cursor = status_conn.cursor()
                            status_cursor.execute("SELECT created_at FROM plaid_tokens WHERE item_id = ? AND user_id = ?", (item_id, user_id))
                            row = status_cursor.fetchone()
                            created_at = row[0] if row else None
                    except Exception:
                        pass
                    if created_at:
                        try:
                            if datetime.now() - datetime.fromisoformat(created_at) < timedelta(minutes=15):
                                holdings_sync_status = 'syncing'
                        except Exception:
                            pass

                try:
                    with get_db() as status_conn:
                        status_conn.execute(
                            """
                            UPDATE plaid_tokens
                            SET status = 'active', error_message = NULL, holdings_sync_status = ?, holdings_last_synced = ?
                            WHERE item_id = ? AND user_id = ?
                            """,
                            (holdings_sync_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item_id, user_id)
                        )
                        status_conn.commit()
                except Exception as status_err:
                    print(f"Error updating detailed holdings status: {status_err}")

                inst = institutions.get(item_id)
                if inst:
                    inst["status"] = "active"
                    inst["holdings_sync_status"] = holdings_sync_status
                    inst["holdings_last_synced"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            except Exception as holdings_err:
                print(f"Skipping detailed holdings for token {item_id}: {holdings_err}")
                status = 'active'
                holdings_sync_status = 'failed'
                try:
                    if hasattr(holdings_err, 'body'):
                        err_body = json.loads(holdings_err.body)
                        err_code = err_body.get('error_code')
                        if err_code == 'ADDITIONAL_CONSENT_REQUIRED':
                            status = 'error_consent'
                            holdings_sync_status = 'error_consent'
                        elif err_code == 'ITEM_LOGIN_REQUIRED':
                            status = 'error_login'
                            holdings_sync_status = 'error_login'
                    with get_db() as status_conn:
                        status_conn.execute(
                            "UPDATE plaid_tokens SET status = ?, error_message = ?, holdings_sync_status = ? WHERE item_id = ? AND user_id = ?",
                            (status, str(holdings_err), holdings_sync_status, item_id, user_id)
                        )
                        status_conn.commit()
                except Exception as status_err:
                    print(f"Error updating detailed holdings error status: {status_err}")

    for acc in account_rows:
        if acc.get('type') != 'investment' or acc.get('account_id') in holdings_account_ids:
            continue
        inst = ensure_institution(acc.get('item_id'), acc.get('institution_name'))
        balance = float(acc.get('balance_current') or 0.0)
        inst["categories"]["Cash"] += balance
        for account_summary in inst["accounts"]:
            if account_summary.get("account_id") == acc.get('account_id'):
                account_summary["categories"]["Cash"] += balance
                break

    result = []
    totals = empty_asset_buckets()
    for inst in institutions.values():
        inst["categories"] = empty_asset_buckets()
        for account_summary in inst["accounts"]:
            normalize_account_asset_buckets(account_summary)
            for key, val in (account_summary.get("categories") or {}).items():
                inst["categories"][key] += val
        inst["total"] = asset_bucket_total(inst["categories"])
        for account_summary in inst["accounts"]:
            account_summary["total"] = asset_bucket_total(account_summary["categories"])
        for key, val in inst["categories"].items():
            totals[key] += val
        inst["accounts"].sort(key=lambda a: (a.get("type") or "", a.get("name") or ""))
        inst["holdings"].sort(key=lambda h: (h.get("category") or "", -(h.get("value") or 0.0)))
        result.append(inst)

    result.sort(key=lambda r: (r.get("institution_name") or "", r.get("item_id") or ""))
    return jsonify({
        "categories": totals,
        "institutions": result
    })

def load_manual_asset_rows():
    user_id = current_user_id()
    rows = []
    with get_db() as conn:
        asset_rows = conn.execute(
            """
            SELECT asset_id, name, asset_type, value, cash_pct, stock_pct, bond_pct, real_estate_pct
            FROM manual_assets
            WHERE active = 1 AND user_id = ?
            ORDER BY name ASC
            """,
            (user_id,)
        ).fetchall()

    for asset in asset_rows:
        percentages = normalize_percentages({
            "Cash": asset["cash_pct"],
            "Stock": asset["stock_pct"],
            "Bond": asset["bond_pct"],
            "Real Estate": asset["real_estate_pct"]
        })
        value = float(asset["value"] or 0.0)
        categories = buckets_from_percentages(value, percentages)
        rows.append({
            "account_id": asset["asset_id"],
            "institution_name": "Manual Assets",
            "name": asset["name"],
            "official_name": asset["name"],
            "type": asset["asset_type"] or "manual",
            "subtype": "manual",
            "balance_current": value,
            "categories": {key: categories.get(key, 0.0) for key in ASSET_BUCKETS},
            "percentages": percentages,
            "source": "manual_asset",
            "holdings_count": 0
        })
    return rows

@plaid_bp.route('/api/manual_assets', methods=['GET', 'POST', 'DELETE'])
def manual_assets_api():
    try:
        user_id = current_user_id()
        if request.method == 'GET':
            with get_db() as conn:
                rows = conn.execute(
                    """
                    SELECT asset_id, name, asset_type, value, cash_pct, stock_pct, bond_pct, real_estate_pct, active, updated_at
                    FROM manual_assets
                    WHERE user_id = ?
                    ORDER BY active DESC, name ASC
                    """,
                    (user_id,)
                ).fetchall()
            return jsonify({"assets": [dict(row) for row in rows]})

        data = request.get_json(silent=True) or {}
        asset_id = (data.get("asset_id") or "").strip()
        if not asset_id:
            return jsonify({"error": "Missing asset_id"}), 400

        if request.method == 'DELETE':
            with get_db() as conn:
                conn.execute("DELETE FROM manual_assets WHERE asset_id = ? AND user_id = ?", (asset_id, user_id))
                conn.commit()
            ALLOCATION_CACHE["time"] = 0.0
            ALLOCATION_CACHE["payload"] = None
            return jsonify({"status": "success"})

        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Missing name"}), 400
        percentages = normalize_percentages(data.get("percentages") or {"Real Estate": 100})
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO manual_assets
                    (asset_id, name, asset_type, value, cash_pct, stock_pct, bond_pct, real_estate_pct, active, updated_at, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                    name = excluded.name,
                    asset_type = excluded.asset_type,
                    value = excluded.value,
                    cash_pct = excluded.cash_pct,
                    stock_pct = excluded.stock_pct,
                    bond_pct = excluded.bond_pct,
                    real_estate_pct = excluded.real_estate_pct,
                    active = excluded.active,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    asset_id,
                    name,
                    (data.get("asset_type") or "manual").strip() or "manual",
                    float(data.get("value") or 0.0),
                    percentages["Cash"],
                    percentages["Stock"],
                    percentages["Bond"],
                    percentages["Real Estate"],
                    1 if data.get("active", True) else 0,
                    user_id
                )
            )
            conn.commit()
        ALLOCATION_CACHE["time"] = 0.0
        ALLOCATION_CACHE["payload"] = None
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def load_allocation_history_snapshots():
    user_id = current_user_id()
    history = []
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT date, cash, stock, bond, real_estate, liabilities, source
            FROM allocation_history_snapshots
            WHERE user_id = ?
            ORDER BY date ASC
            """,
            (user_id,)
        ).fetchall()
    for row in rows:
        group = {
            "date": row["date"],
            "Net Worth": 0.0,
            "Cash": float(row["cash"] or 0.0),
            "Stock": float(row["stock"] or 0.0),
            "Bond": float(row["bond"] or 0.0),
            "Real Estate": float(row["real_estate"] or 0.0),
            "liabilities": float(row["liabilities"] or 0.0),
            "source": row["source"] or "snapshot"
        }
        group["Net Worth"] = group["Cash"] + group["Stock"] + group["Bond"] + group["Real Estate"] - group["liabilities"]
        history.append(group)
    return history

def load_manual_asset_values_by_date():
    user_id = current_user_id()
    by_date = {}
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT date, SUM(value) AS real_estate
            FROM manual_asset_values
            WHERE user_id = ?
            GROUP BY date
            ORDER BY date ASC
            """,
            (user_id,)
        ).fetchall()
    for row in rows:
        by_date[row["date"]] = {"Real Estate": float(row["real_estate"] or 0.0)}
    return by_date

def load_account_value_estimates():
    user_id = current_user_id()
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT e.account_id, e.date, e.value, e.cash_pct, e.stock_pct, e.bond_pct, e.real_estate_pct
            FROM account_value_estimates e
            INNER JOIN accounts a
              ON a.user_id = e.user_id
             AND a.account_id = e.account_id
            WHERE e.user_id = ?
            ORDER BY e.date ASC
            """,
            (user_id,)
        ).fetchall()
    return [dict(row) for row in rows]

def build_allocation_accounts_payload(use_cache=True):
    user_id = current_user_id()
    now = time.time()
    if use_cache and ALLOCATION_CACHE["user_id"] == user_id and ALLOCATION_CACHE["payload"] and now - ALLOCATION_CACHE["time"] < 45:
        return ALLOCATION_CACHE["payload"]
    if use_cache:
        with ALLOCATION_CACHE_LOCK:
            now = time.time()
            if ALLOCATION_CACHE["user_id"] == user_id and ALLOCATION_CACHE["payload"] and now - ALLOCATION_CACHE["time"] < 45:
                return ALLOCATION_CACHE["payload"]
            return build_allocation_accounts_payload(use_cache=False)

    client = get_plaid_client()
    overrides = load_allocation_overrides()

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT account_id, name, official_name, type, subtype, balance_current, balance_available, institution_name, item_id
            FROM accounts
            WHERE account_id != 'Legacy' AND user_id = ?
            """,
            (user_id,)
        )
        account_rows = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT access_token, item_id, institution_name, status FROM plaid_tokens WHERE user_id = ?", (user_id,))
        token_rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
    except Exception as db_err:
        raise RuntimeError(f"Database error: {db_err}") from db_err

    accounts_by_id = {a['account_id']: a for a in account_rows}
    investment_item_ids = {a.get('item_id') for a in account_rows if a.get('type') == 'investment'}
    account_buckets = {a['account_id']: empty_asset_buckets() for a in account_rows}
    holdings_count_by_account = {a['account_id']: 0 for a in account_rows}

    if client:
        from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
        for token in token_rows:
            if token.get('status') == 'error_consent' or token.get('item_id') not in investment_item_ids:
                continue
            try:
                res = client.investments_holdings_get(
                    InvestmentsHoldingsGetRequest(access_token=token.get('access_token'))
                ).to_dict()
                holdings = res.get('holdings') or []
                sec_map = {s['security_id']: s for s in (res.get('securities') or [])}
                item_has_holdings = False
                for h in holdings:
                    account_id = h.get('account_id')
                    if account_id not in accounts_by_id:
                        continue
                    security = sec_map.get(h.get('security_id'), {})
                    bucket = coerce_asset_bucket(classify_security_bucket(security))
                    value = holding_market_value(h, security)
                    account_buckets[account_id][bucket] += value
                    holdings_count_by_account[account_id] += 1
                    item_has_holdings = True
                
                from datetime import datetime, timedelta
                holdings_sync_status = 'synced' if item_has_holdings else 'no_holdings'
                has_inv = token.get('item_id') in investment_item_ids
                if not item_has_holdings and has_inv:
                    created_at = None
                    try:
                        with get_db() as status_conn:
                            status_cursor = status_conn.cursor()
                            status_cursor.execute("SELECT created_at FROM plaid_tokens WHERE item_id = ? AND user_id = ?", (token.get('item_id'), user_id))
                            row = status_cursor.fetchone()
                            created_at = row[0] if row else None
                    except Exception:
                        pass
                    if created_at:
                        try:
                            if datetime.now() - datetime.fromisoformat(created_at) < timedelta(minutes=15):
                                holdings_sync_status = 'syncing'
                        except Exception:
                            pass
                
                try:
                    with get_db() as status_conn:
                        status_conn.execute(
                            """
                            UPDATE plaid_tokens
                            SET status = 'active', error_message = NULL, holdings_sync_status = ?, holdings_last_synced = ?
                            WHERE item_id = ? AND user_id = ?
                            """,
                            (holdings_sync_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), token.get('item_id'), user_id)
                        )
                        status_conn.commit()
                except Exception as status_err:
                    print(f"Error updating active holdings status in build_payload: {status_err}")
            except Exception as holdings_err:
                print(f"Skipping allocation holdings for token {token.get('item_id')}: {holdings_err}")
                status = 'active'
                holdings_sync_status = 'failed'
                try:
                    if hasattr(holdings_err, 'body'):
                        err_body = json.loads(holdings_err.body)
                        err_code = err_body.get('error_code')
                        if err_code == 'ADDITIONAL_CONSENT_REQUIRED':
                            status = 'error_consent'
                            holdings_sync_status = 'error_consent'
                        elif err_code == 'ITEM_LOGIN_REQUIRED':
                            status = 'error_login'
                            holdings_sync_status = 'error_login'
                    with get_db() as status_conn:
                        status_conn.execute(
                            "UPDATE plaid_tokens SET status = ?, error_message = ?, holdings_sync_status = ? WHERE item_id = ? AND user_id = ?",
                            (status, str(holdings_err), holdings_sync_status, token.get('item_id'), user_id)
                        )
                        status_conn.commit()
                except Exception as status_err:
                    print(f"Error updating holdings error status in build_payload: {status_err}")

    rows = []
    totals = empty_asset_buckets()

    for acc in account_rows:
        acc_type = acc.get('type')
        if acc_type == 'credit':
            continue

        account_id = acc['account_id']
        balance = float(acc.get('balance_current') or 0.0)
        manual = overrides.get(account_id)
        source = "auto"

        if manual:
            categories = buckets_from_percentages(balance, manual)
            percentages = normalize_percentages(manual)
            source = "manual"
        else:
            categories = account_buckets.get(account_id) or empty_asset_buckets()
            has_holdings = holdings_count_by_account.get(account_id, 0) > 0
            if has_holdings:
                account_summary = {
                    "type": acc_type,
                    "balance_current": balance,
                    "categories": categories
                }
                normalize_account_asset_buckets(account_summary)
                categories = account_summary["categories"]
                source = "holdings"
            else:
                percentages = normalize_percentages({"Cash": 100})
                categories = buckets_from_percentages(balance, percentages)
                source = "default_cash"

            total_for_pct = asset_bucket_total(categories)
            percentages = {
                key: (categories.get(key, 0.0) / total_for_pct * 100.0 if total_for_pct else 0.0)
                for key in ASSET_BUCKETS
            }

        for key in totals:
            totals[key] += categories.get(key, 0.0)

        rows.append({
            "account_id": account_id,
            "institution_name": acc.get('institution_name') or "Unknown",
            "name": acc.get('name') or "Account",
            "official_name": acc.get('official_name'),
            "type": acc_type,
            "subtype": acc.get('subtype'),
            "balance_current": balance,
            "categories": {key: categories.get(key, 0.0) for key in ASSET_BUCKETS},
            "percentages": {key: percentages.get(key, 0.0) for key in ASSET_BUCKETS},
            "source": source,
            "holdings_count": holdings_count_by_account.get(account_id, 0)
        })

    for row in load_manual_asset_rows():
        rows.append(row)
        for key in totals:
            totals[key] += row["categories"].get(key, 0.0)

    rows.sort(key=lambda r: (r["institution_name"], r["type"] or "", r["name"]))
    payload = {"accounts": rows, "totals": totals, "categories": list(ASSET_BUCKETS)}
    ALLOCATION_CACHE["time"] = now
    ALLOCATION_CACHE["payload"] = payload
    ALLOCATION_CACHE["user_id"] = user_id
    return payload

@plaid_bp.route('/api/allocation_accounts', methods=['GET'])
def get_allocation_accounts():
    try:
        return jsonify(build_allocation_accounts_payload())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@plaid_bp.route('/api/allocation_history', methods=['GET'])
def get_allocation_history():
    try:
        user_id = current_user_id()
        allocation_payload = build_allocation_accounts_payload()
        pct_by_account = {
            row["account_id"]: normalize_percentages(row.get("percentages") or {})
            for row in allocation_payload.get("accounts", [])
            if row.get("source") != "manual_asset"
        }
        manual_asset_totals = empty_asset_buckets()
        for row in allocation_payload.get("accounts", []):
            if row.get("source") != "manual_asset":
                continue
            for key in ASSET_BUCKETS:
                manual_asset_totals[key] += float((row.get("categories") or {}).get(key) or 0.0)
        manual_asset_values_by_date = load_manual_asset_values_by_date()

        with get_db() as conn:
            history_rows = conn.execute(
                """
                SELECT h.date, h.account_id, h.balance_current, a.type
                FROM account_balances_history h
                INNER JOIN accounts a ON h.account_id = a.account_id AND a.user_id = h.user_id
                WHERE h.user_id = ?
                ORDER BY h.date ASC
                """,
                (user_id,)
            ).fetchall()

        by_date = {row["date"]: row for row in load_allocation_history_snapshots()}
        for group in by_date.values():
            if group.get("source") in ("imported", "snapshot"):
                group["Real Estate"] = 0.0
        actual_account_dates = set()
        for row in history_rows:
            date = row["date"]
            if not date:
                continue
            actual_account_dates.add((row["account_id"], date))
            if date in by_date and by_date[date].get("source") in ("imported", "snapshot"):
                by_date[date] = {
                    "date": date,
                    "Net Worth": 0.0,
                    "Cash": 0.0,
                    "Stock": 0.0,
                    "Bond": 0.0,
                    "Real Estate": 0.0,
                    "liabilities": 0.0,
                    "source": "plaid"
                }
            group = by_date.setdefault(date, {
                "date": date,
                "Net Worth": 0.0,
                "Cash": 0.0,
                "Stock": 0.0,
                "Bond": 0.0,
                "Real Estate": 0.0,
                "liabilities": 0.0,
                "source": "plaid"
            })
            balance = float(row["balance_current"] or 0.0)
            if row["type"] == "credit":
                group["liabilities"] += balance
                continue
            pct = pct_by_account.get(row["account_id"], normalize_percentages({"Cash": 100}))
            for key in ASSET_BUCKETS:
                group[key] += balance * pct.get(key, 0.0) / 100.0

        for estimate in load_account_value_estimates():
            date = estimate.get("date")
            account_id = estimate.get("account_id")
            if not date or (account_id, date) in actual_account_dates:
                continue
            group = by_date.setdefault(date, {
                "date": date,
                "Net Worth": 0.0,
                "Cash": 0.0,
                "Stock": 0.0,
                "Bond": 0.0,
                "Real Estate": 0.0,
                "liabilities": 0.0,
                "source": "estimated"
            })
            value = float(estimate.get("value") or 0.0)
            percentages = normalize_percentages({
                "Cash": estimate.get("cash_pct"),
                "Stock": estimate.get("stock_pct"),
                "Bond": estimate.get("bond_pct"),
                "Real Estate": estimate.get("real_estate_pct")
            })
            for key in ASSET_BUCKETS:
                group[key] += value * percentages.get(key, 0.0) / 100.0

        if not by_date:
            today = __import__('datetime').date.today().isoformat()
            by_date[today] = {
                "date": today,
                "Net Worth": 0.0,
                "Cash": 0.0,
                "Stock": 0.0,
                "Bond": 0.0,
                "Real Estate": 0.0,
                "liabilities": 0.0
            }

        for group in by_date.values():
            manual_values = manual_asset_values_by_date.get(group["date"])
            if manual_values:
                for key in ASSET_BUCKETS:
                    group[key] += manual_values.get(key, 0.0)
            elif group.get("source") not in ("imported", "snapshot"):
                for key in ASSET_BUCKETS:
                    group[key] += manual_asset_totals.get(key, 0.0)
            group["Net Worth"] = (
                group["Cash"] + group["Stock"] + group["Bond"] + group["Real Estate"] - group["liabilities"]
            )

        series = [by_date[date] for date in sorted(by_date.keys())]
        return jsonify({"history": series, "categories": ["Net Worth", *ASSET_BUCKETS]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@plaid_bp.route('/api/allocation_overrides', methods=['GET', 'POST'])
def allocation_overrides_api():
    if request.method == 'GET':
        return jsonify(load_allocation_overrides())

    try:
        data = request.get_json(silent=True) or {}
        account_id = data.get('account_id')
        percentages = data.get('percentages')
        if not account_id or not isinstance(percentages, dict):
            return jsonify({"error": "Missing account_id or percentages"}), 400

        overrides = load_allocation_overrides()
        if data.get('clear'):
            overrides.pop(account_id, None)
        else:
            overrides[account_id] = normalize_percentages(percentages)
        save_allocation_overrides(overrides)
        ALLOCATION_CACHE["time"] = 0.0
        ALLOCATION_CACHE["payload"] = None
        return jsonify({"status": "success", "overrides": overrides})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@plaid_bp.route('/api/portfolio_allocation', methods=['GET'])
def get_portfolio_allocation():
    user_id = current_user_id()
    client = get_plaid_client()
    
    # Initialize categories
    allocation = empty_asset_buckets()
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get all Plaid accounts in database (to count depository cash and unclassified investments)
        cursor.execute("SELECT account_id, name, official_name, type, subtype, balance_current, institution_name, item_id FROM accounts WHERE user_id = ?", (user_id,))
        db_accounts = [dict(r) for r in cursor.fetchall()]
        
        # Get all active Plaid tokens
        cursor.execute("SELECT access_token, item_id, status FROM plaid_tokens WHERE user_id = ?", (user_id,))
        tokens_rows = cursor.fetchall()
        conn.close()
    except Exception as db_err:
        return jsonify({"error": f"Database error: {db_err}"}), 500
        
    holdings_account_ids = set()
    successful_holdings_item_ids = set()
    investment_item_ids = {a.get('item_id') for a in db_accounts if a.get('type') == 'investment'}
    
    # Query holdings from Plaid investments API
    if client:
        from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
        for t in tokens_rows:
            access_token = t['access_token']
            item_id = t['item_id']
            if t['status'] == 'error_consent' or item_id not in investment_item_ids:
                continue
                
            try:
                req = InvestmentsHoldingsGetRequest(access_token=access_token)
                res = client.investments_holdings_get(req).to_dict()
                
                holdings = res.get('holdings', [])
                securities = res.get('securities', [])
                
                sec_map = {s['security_id']: s for s in securities}
                
                for h in holdings:
                    acc_id = h['account_id']
                    sec_id = h['security_id']
                    sec = sec_map.get(sec_id, {})
                    val = holding_market_value(h, sec)
                    
                    holdings_account_ids.add(acc_id)
                    
                    allocation[coerce_asset_bucket(classify_security_bucket(sec))] += val
                
                successful_holdings_item_ids.add(item_id)
                
                # Determine holdings sync status
                from datetime import datetime, timedelta
                holdings_sync_status = 'no_holdings'
                
                # Check if this item has investment accounts in db
                db_conn = get_db()
                db_cursor = db_conn.cursor()
                db_cursor.execute("SELECT COUNT(*) FROM accounts WHERE item_id = ? AND type = 'investment' AND user_id = ?", (item_id, user_id))
                has_inv = db_cursor.fetchone()[0] > 0
                
                if holdings:
                    holdings_sync_status = 'synced'
                elif has_inv:
                    # It has investment accounts, but holdings returned empty!
                    # Check if it was created in the last 15 minutes
                    db_cursor.execute("SELECT created_at FROM plaid_tokens WHERE item_id = ? AND user_id = ?", (item_id, user_id))
                    created_at_row = db_cursor.fetchone()
                    created_at_str = created_at_row[0] if created_at_row else None
                    
                    is_pending = False
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str)
                            if datetime.now() - created_at < timedelta(minutes=15):
                                is_pending = True
                        except Exception:
                            pass
                            
                    if is_pending:
                        holdings_sync_status = 'syncing'
                    else:
                        holdings_sync_status = 'no_holdings'
                else:
                    holdings_sync_status = 'no_holdings'
                db_conn.close()
                
                # Update status to active on successful holdings fetch
                try:
                    with get_db() as conn:
                        conn.execute(
                            """
                            UPDATE plaid_tokens 
                            SET status = 'active', error_message = NULL, holdings_sync_status = ?, holdings_last_synced = ?
                            WHERE item_id = ? AND user_id = ?
                            """,
                            (holdings_sync_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item_id, user_id)
                        )
                        conn.commit()
                except Exception as status_err:
                    print(f"Error updating active holdings status: {status_err}")
                        
            except Exception as holdings_err:
                print(f"Skipping holdings for token {item_id}: {holdings_err}")
                status = 'active'
                holdings_sync_status = 'failed'
                try:
                    if hasattr(holdings_err, 'body'):
                        err_body = json.loads(holdings_err.body)
                        err_code = err_body.get('error_code')
                        if err_code == 'ADDITIONAL_CONSENT_REQUIRED':
                            status = 'error_consent'
                            holdings_sync_status = 'error_consent'
                        elif err_code == 'ITEM_LOGIN_REQUIRED':
                            status = 'error_login'
                            holdings_sync_status = 'error_login'
                            
                    with get_db() as conn:
                        conn.execute(
                            "UPDATE plaid_tokens SET status = ?, error_message = ?, holdings_sync_status = ? WHERE item_id = ? AND user_id = ?",
                            (status, str(holdings_err), holdings_sync_status, item_id, user_id)
                        )
                        conn.commit()
                except Exception as status_err:
                    print(f"Error updating holdings error status: {status_err}")
                
    # Process depository cash and unclassified accounts from database
    for acc in db_accounts:
        acc_id = acc['account_id']
        val = acc['balance_current'] or 0.0
        acc_type = acc['type']
        item_id = acc['item_id']
        
        if acc_id == 'Legacy':
            allocation['Cash'] += val
            continue
            
        if acc_type == 'credit':
            continue
            
        if acc_id in holdings_account_ids:
            continue
            
        if acc_type == 'depository':
            allocation['Cash'] += val
        elif acc_type == 'investment':
            allocation['Cash'] += val
                
    for asset in load_manual_asset_rows():
        for key in ASSET_BUCKETS:
            allocation[key] += float((asset.get("categories") or {}).get(key) or 0.0)
    
    return jsonify(allocation)
