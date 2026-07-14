import json
import sqlite3
import math
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify

from database import get_db
from auth import current_user_id
from routes_config import load_analysis_rules_config_from_db, load_categories_config_from_db
from classifier import infer_transaction_classification_from_history, normalize_merchant_key

transactions_bp = Blueprint('transactions', __name__)

def load_canonical_categories():
    try:
        categories = load_categories_config_from_db().get('categories', [])
    except Exception:
        categories = []
    return {category.lower(): category for category in categories}

def normalize_category_name(category, canonical_categories=None):
    name = (category or '').strip() or 'Other'
    return (canonical_categories or {}).get(name.lower(), name)

def get_analysis_rules():
    try:
        return load_analysis_rules_config_from_db()
    except Exception:
        return {
            "travel": {"category": "Travel", "trip_source": "note", "category_source": "subtype", "year_prefix": True, "fallback_year": "Note"},
            "rentals": {"category": "Rentals", "property_source": "note", "category_source": "subtype", "fallback_property": "Unassigned", "fallback_category": "Unclassified"}
        }

def configured_category_key(rules, section, fallback):
    return str((rules.get(section) or {}).get("category") or fallback).strip().lower()

def apply_stable_history_to_unreviewed(cursor, merchant, direction, user_id):
    learned = infer_transaction_classification_from_history(cursor, merchant, direction, user_id=user_id)
    if not learned:
        return 0

    merchant_key = normalize_merchant_key(merchant)
    if not merchant_key:
        return 0

    cursor.execute(
        """
        SELECT transaction_id, merchant
        FROM transactions
        WHERE user_id = ?
          AND reviewed = 0
          AND COALESCE(pending, 0) = 0
          AND imported_from_legacy = 0
          AND lower(COALESCE(direction, '')) = ?
        """,
        (user_id, (direction or "").lower())
    )
    targets = [
        row["transaction_id"]
        for row in cursor.fetchall()
        if normalize_merchant_key(row["merchant"]) == merchant_key
    ]
    for tx_id in targets:
        cursor.execute(
            """
            UPDATE transactions
            SET type = ?, subtype = ?, prediction_source = ?, prediction_confidence = ?, prediction_reason = ?
            WHERE transaction_id = ? AND user_id = ?
            """,
            (
                learned["type"],
                learned["subtype"],
                "history",
                learned.get("confidence", 0.95),
                learned.get("reason", "Learned from consistent reviewed transactions."),
                tx_id,
                user_id
            )
        )
    return len(targets)

def parse_amount_filter(raw):
    text = (raw or '').strip().replace('$', '').replace(',', '')
    if not text:
        return None
    try:
        if text.startswith('>='):
            return ('gte', float(text[2:].strip()))
        if text.startswith('<='):
            return ('lte', float(text[2:].strip()))
        if text.startswith('>'):
            return ('gt', float(text[1:].strip()))
        if text.startswith('<'):
            return ('lt', float(text[1:].strip()))
        if '-' in text:
            left, right = text.split('-', 1)
            low = float(left.strip())
            high = float(right.strip())
            return ('range', min(low, high), max(low, high))
        value = float(text)
        tolerance = max(value * 0.10, 5.0)
        return ('range', max(value - tolerance, 0.0), value + tolerance)
    except Exception:
        return None

def fetch_paginated_transactions(page=1, limit=100, query='', direction='all', category='all', subtype='all', reviewed_filter='all', start_date='', end_date='', account='all', amount_filter='', assignment='all'):
    user_id = current_user_id()
    params = [user_id]
    where_clauses = ["t.user_id = ?"]
    
    if query:
        where_clauses.append("(t.merchant LIKE ? OR t.note LIKE ? OR t.type LIKE ? OR t.subtype LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])

    if start_date:
        where_clauses.append("t.date >= ?")
        params.append(start_date)

    if end_date:
        where_clauses.append("t.date <= ?")
        params.append(end_date)

    if account and account != 'all':
        accounts = [a.strip() for a in account.split(',') if a.strip()]
        if accounts:
            placeholders = ",".join(["?"] * len(accounts))
            where_clauses.append(f"t.account_name IN ({placeholders})")
            params.extend(accounts)

    if assignment and assignment != 'all':
        kind, _, assignment_id = assignment.partition(':')
        assignment_id = assignment_id.strip()
        if kind == 'trip' and assignment_id:
            where_clauses.append("t.trip_id = ?")
            params.append(assignment_id)
        elif kind == 'rental' and assignment_id:
            where_clauses.append("t.rental_property_id = ?")
            params.append(assignment_id)

    parsed_amount = parse_amount_filter(amount_filter)
    if parsed_amount:
        mode = parsed_amount[0]
        if mode == 'range':
            where_clauses.append("ABS(t.amount) BETWEEN ? AND ?")
            params.extend([parsed_amount[1], parsed_amount[2]])
        elif mode == 'gt':
            where_clauses.append("ABS(t.amount) > ?")
            params.append(parsed_amount[1])
        elif mode == 'gte':
            where_clauses.append("ABS(t.amount) >= ?")
            params.append(parsed_amount[1])
        elif mode == 'lt':
            where_clauses.append("ABS(t.amount) < ?")
            params.append(parsed_amount[1])
        elif mode == 'lte':
            where_clauses.append("ABS(t.amount) <= ?")
            params.append(parsed_amount[1])
        
    # Multi-select Direction
    if direction and direction != 'all':
        dirs = [d.strip() for d in direction.split(',') if d.strip()]
        if dirs and len(dirs) < 2:
            where_clauses.append("t.direction = ?")
            params.append(dirs[0])
        
    # Multi-select Category
    if category and category != 'all':
        cats = [c.strip() for c in category.split(',') if c.strip()]
        if cats:
            placeholders = ",".join(["?"] * len(cats))
            where_clauses.append(f"t.type IN ({placeholders})")
            params.extend(cats)
    if subtype and subtype != 'all':
        where_clauses.append("t.subtype = ?")
        params.append(subtype)
        
    # Multi-select transaction status.
    if reviewed_filter and reviewed_filter != 'all':
        stats = [s.strip() for s in reviewed_filter.split(',') if s.strip()]
        if "none" in stats:
            where_clauses.append("1 = 0")
        elif stats:
            status_clauses = []
            for s in stats:
                if s in ('pending',):
                    status_clauses.append("COALESCE(t.pending, 0) = 1")
                elif s in ('needs_review', 'unreviewed_plaid', 'unreviewed'):
                    status_clauses.append("(COALESCE(t.pending, 0) = 0 AND t.reviewed = 0)")
                elif s in ('reviewed', 'manually_reviewed'):
                    status_clauses.append("(COALESCE(t.pending, 0) = 0 AND t.reviewed = 1 AND t.imported_from_legacy = 0 AND t.legacy_matched = 0 AND COALESCE(t.account_name, '') != 'Legacy' AND lower(COALESCE(t.type, '')) != 'internal transfer')")
                elif s == 'manual':
                    status_clauses.append("(COALESCE(t.pending, 0) = 0 AND t.imported_from_legacy = 0 AND COALESCE(t.account_name, '') = 'Legacy')")
                elif s == 'transfer':
                    status_clauses.append("(COALESCE(t.pending, 0) = 0 AND lower(COALESCE(t.type, '')) = 'internal transfer')")
                elif s == 'legacy_matched':
                    status_clauses.append("(COALESCE(t.pending, 0) = 0 AND t.legacy_matched = 1)")
                elif s == 'legacy_imported':
                    status_clauses.append("(COALESCE(t.pending, 0) = 0 AND t.imported_from_legacy = 1 AND t.legacy_matched = 0)")
            if status_clauses:
                where_clauses.append("(" + " OR ".join(status_clauses) + ")")
        
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
        
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Get total count
    count_query = f"SELECT COUNT(*) FROM transactions t {where_sql}"
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]
    
    # 2. Get paginated transactions
    offset = (page - 1) * limit
    data_query = f"""
        SELECT 
            t.transaction_id, 
            t.date, 
            t.authorized_date,
            t.type, 
            t.merchant, 
            t.amount, 
            t.direction, 
            t.pending, 
            t.categories, 
            t.location, 
            t.payment_channel, 
            t.is_b,
            t.ratio,
            t.ipay,
            t.bpay,
            t.mown,
            t.note,
            t.subtype,
            t.reviewed,
            t.imported_from_legacy,
            t.legacy_matched,
            t.prediction_source,
            t.prediction_confidence,
            t.prediction_reason,
            t.trip_id,
            tr.name AS trip_name,
            tr.year AS trip_year,
            t.rental_property_id,
            rp.name AS rental_property_name,
            t.account_name AS account_name_raw,
            a.name AS account_name,
            a.type AS account_type,
            a.subtype AS account_subtype,
            a.institution_name AS institution_name
        FROM transactions t
        LEFT JOIN accounts a ON t.account_name = a.account_id AND a.user_id = t.user_id
        LEFT JOIN trips tr ON t.trip_id = tr.id AND tr.user_id = t.user_id
        LEFT JOIN rental_properties rp ON t.rental_property_id = rp.id AND rp.user_id = t.user_id
        {where_sql}
        ORDER BY t.date DESC, t.transaction_id DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(data_query, params + [limit, offset])
    rows = cursor.fetchall()
    total_pages = math.ceil(total_count / limit) if total_count > 0 else 1
    
    txs = []
    for r in rows:
        transfer_candidate = None
        if r['type'] == 'Internal Transfer':
            cursor.execute(
                """
                SELECT t.transaction_id, t.date, t.merchant, t.amount, t.direction, a.name AS account_name
                FROM transactions t
                LEFT JOIN accounts a ON t.account_name = a.account_id AND a.user_id = t.user_id
                WHERE t.transaction_id != ?
                  AND t.user_id = ?
                  AND t.amount = ?
                  AND t.direction != ?
                  AND t.account_name != ?
                  AND abs(julianday(t.date) - julianday(?)) <= 3
                ORDER BY abs(julianday(t.date) - julianday(?)) ASC
                LIMIT 1
                """,
                (r['transaction_id'], user_id, r['amount'], r['direction'], r['account_name_raw'], r['date'], r['date'])
            )
            cp = cursor.fetchone()
            if cp:
                transfer_candidate = {
                    "TransactionID": cp[0],
                    "Date": cp[1],
                    "Merchant": cp[2],
                    "Amount": cp[3],
                    "Direction": cp[4],
                    "AccountName": 'Legacy' if cp[5] == 'Legacy' else (cp[5] or cp[0])
                }

        txs.append({
            "TransactionID": r['transaction_id'],
            "Date": r['date'],
            "AuthorizedDate": r['authorized_date'],
            "Type": r['type'],
            "Merchant": r['merchant'],
            "Amount": r['amount'],
            "Direction": r['direction'],
            "Pending": r['pending'],
            "Categories": r['categories'],
            "Location": r['location'],
            "PaymentChannel": r['payment_channel'],
            "IsB": r['is_b'] or 'n',
            "Ratio": r['ratio'] if r['ratio'] is not None else 1.0,
            "Ipay": r['ipay'],
            "Bpay": r['bpay'],
            "Mown": r['mown'] or 0.0,
            "Note": r['note'] or '',
            "SubType": r['subtype'] or '',
            "Reviewed": r['reviewed'] or 0,
            "ImportedFromLegacy": r['imported_from_legacy'] or 0,
            "LegacyMatched": r['legacy_matched'] or 0,
            "PredictionSource": r['prediction_source'] or '',
            "PredictionConfidence": r['prediction_confidence'] or 0,
            "PredictionReason": r['prediction_reason'] or '',
            "TripID": r['trip_id'] or '',
            "TripName": r['trip_name'] or '',
            "TripYear": r['trip_year'],
            "RentalPropertyID": r['rental_property_id'] or '',
            "RentalPropertyName": r['rental_property_name'] or '',
            "AccountName": 'Legacy' if r['account_name_raw'] == 'Legacy' else (r['account_name'] or r['transaction_id']),
            "AccountType": r['account_type'],
            "AccountSubtype": r['account_subtype'],
            "InstitutionName": r['institution_name'],
            "TransferCandidate": transfer_candidate
        })
        
    conn.close()
        
    return {
        "transactions": txs,
        "page": page,
        "limit": limit,
        "total_count": total_count,
        "total_pages": total_pages
    }

@transactions_bp.route('/api/transactions', methods=['GET'])
def get_transactions():
    import time
    start = time.perf_counter()
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        query = request.args.get('query', '').strip()
        direction = request.args.get('direction', 'all').strip()
        category = request.args.get('category', 'all').strip()
        subtype = request.args.get('subtype', 'all').strip()
        reviewed_filter = request.args.get('reviewed_filter', 'unreviewed').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        account = request.args.get('account', 'all').strip()
        amount_filter = request.args.get('amount', '').strip()
        assignment = request.args.get('assignment', 'all').strip()
        
        result = fetch_paginated_transactions(page, limit, query, direction, category, subtype, reviewed_filter, start_date, end_date, account, amount_filter, assignment)
        duration = (time.perf_counter() - start) * 1000
        print(f" * [/api/transactions] Fetch took {duration:.2f}ms")
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/transaction_filter_options', methods=['GET'])
def transaction_filter_options():
    try:
        user_id = current_user_id()
        with get_db() as conn:
            date_range = conn.execute(
                "SELECT MIN(date) AS min_date, MAX(date) AS max_date FROM transactions WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            rows = conn.execute(
                """
                SELECT t.account_name AS account_id,
                       COALESCE(a.name, t.account_name) AS account_name,
                       COALESCE(a.institution_name, CASE WHEN t.account_name = 'Legacy' THEN 'Legacy' ELSE '' END) AS institution_name,
                       COUNT(*) AS tx_count
                FROM transactions t
                LEFT JOIN accounts a ON t.account_name = a.account_id AND a.user_id = t.user_id
                WHERE t.user_id = ?
                GROUP BY t.account_name, account_name, institution_name
                ORDER BY institution_name, account_name
                """,
                (user_id,)
            ).fetchall()
            status_counts = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN COALESCE(pending, 0) = 1 THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN COALESCE(pending, 0) = 0 AND reviewed = 0 THEN 1 ELSE 0 END) AS needs_review,
                    SUM(CASE
                        WHEN COALESCE(pending, 0) = 0
                         AND reviewed = 1
                         AND imported_from_legacy = 0
                         AND legacy_matched = 0
                         AND COALESCE(account_name, '') != 'Legacy'
                         AND lower(COALESCE(type, '')) != 'internal transfer'
                        THEN 1 ELSE 0 END) AS reviewed,
                    SUM(CASE
                        WHEN COALESCE(pending, 0) = 0
                         AND imported_from_legacy = 0
                         AND COALESCE(account_name, '') = 'Legacy'
                        THEN 1 ELSE 0 END) AS manual,
                    SUM(CASE
                        WHEN COALESCE(pending, 0) = 0
                         AND lower(COALESCE(type, '')) = 'internal transfer'
                        THEN 1 ELSE 0 END) AS transfer,
                    SUM(CASE
                        WHEN COALESCE(pending, 0) = 0
                         AND legacy_matched = 1
                        THEN 1 ELSE 0 END) AS legacy_matched,
                    SUM(CASE
                        WHEN COALESCE(pending, 0) = 0
                         AND imported_from_legacy = 1
                         AND legacy_matched = 0
                        THEN 1 ELSE 0 END) AS legacy_imported
                FROM transactions
                WHERE user_id = ?
                """,
                (user_id,)
            ).fetchone()
            trip_rows = conn.execute(
                """
                SELECT tr.id,
                       TRIM(COALESCE(tr.year || ' ', '') || tr.name) AS label,
                       COUNT(*) AS tx_count
                FROM transactions t
                JOIN trips tr ON t.trip_id = tr.id AND tr.user_id = t.user_id
                WHERE t.user_id = ?
                GROUP BY tr.id, label
                ORDER BY COALESCE(tr.year, 0) DESC, lower(tr.name)
                """,
                (user_id,)
            ).fetchall()
            rental_rows = conn.execute(
                """
                SELECT rp.id,
                       rp.name AS label,
                       COUNT(*) AS tx_count
                FROM transactions t
                JOIN rental_properties rp ON t.rental_property_id = rp.id AND rp.user_id = t.user_id
                WHERE t.user_id = ?
                GROUP BY rp.id, rp.name
                ORDER BY lower(rp.name)
                """,
                (user_id,)
            ).fetchall()

            status_defs = [
                ("pending", "Pending"),
                ("needs_review", "Needs review"),
                ("reviewed", "Reviewed"),
                ("manual", "Manual"),
                ("transfer", "Transfer"),
                ("legacy_matched", "Legacy matched"),
                ("legacy_imported", "Legacy imported"),
            ]
            statuses = [
                {"value": value, "label": label, "count": int(status_counts[value] or 0)}
                for value, label in status_defs
                if int(status_counts[value] or 0) > 0
            ]
        return jsonify({
            "min_date": date_range["min_date"],
            "max_date": date_range["max_date"],
            "accounts": [dict(r) for r in rows],
            "trips": [dict(r) for r in trip_rows],
            "rental_properties": [dict(r) for r in rental_rows],
            "statuses": statuses
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/monthly_analysis', methods=['GET'])
def monthly_analysis():
    try:
        user_id = current_user_id()
        analysis_rules = get_analysis_rules()
        rental_category = configured_category_key(analysis_rules, "rentals", "Rentals")
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT substr(date, 1, 7) AS month,
                       SUM(CASE WHEN lower(COALESCE(type, '')) = 'income'
                                THEN COALESCE(ipay, 0) ELSE 0 END) AS income,
                       SUM(CASE WHEN lower(COALESCE(type, '')) = 'income'
                                THEN 0 ELSE -COALESCE(ipay, 0) END) AS expense,
                       SUM(CASE WHEN lower(COALESCE(type, '')) NOT IN ('income', 'mortgage')
                                THEN -COALESCE(ipay, 0) ELSE 0 END) AS expense_ex_mortgage,
                       SUM(CASE WHEN lower(COALESCE(type, '')) NOT IN ('income', 'mortgage', 'tax', 'internal transfer', ?)
                                THEN -COALESCE(ipay, 0) ELSE 0 END) AS living_expense
                FROM transactions
                WHERE user_id = ?
                  AND date IS NOT NULL AND date != ''
                  AND COALESCE(pending, 0) = 0
                  AND lower(COALESCE(type, '')) NOT IN ('internal transfer', ?)
                GROUP BY substr(date, 1, 7)
                ORDER BY month ASC
                """,
                (rental_category, user_id, rental_category)
            ).fetchall()
            category_rows = conn.execute(
                """
                SELECT substr(date, 1, 7) AS month,
                       COALESCE(type, 'Other') AS category,
                       SUM(-COALESCE(ipay, 0)) AS amount
                FROM transactions
                WHERE user_id = ?
                  AND date IS NOT NULL AND date != ''
                  AND COALESCE(pending, 0) = 0
                  AND lower(COALESCE(type, '')) NOT IN ('income', 'internal transfer', ?)
                GROUP BY substr(date, 1, 7), COALESCE(type, 'Other')
                HAVING ABS(amount) > 0.005
                ORDER BY month ASC, amount DESC
                """,
                (user_id, rental_category)
            ).fetchall()
            yearly_rows = conn.execute(
                """
                SELECT substr(date, 1, 4) AS year,
                       SUM(CASE WHEN lower(COALESCE(type, '')) = 'income'
                                THEN COALESCE(ipay, 0) ELSE 0 END) AS income,
                       SUM(CASE WHEN lower(COALESCE(type, '')) = 'income'
                                THEN 0 ELSE -COALESCE(ipay, 0) END) AS expense,
                       SUM(CASE WHEN lower(COALESCE(type, '')) NOT IN ('income', 'mortgage')
                                THEN -COALESCE(ipay, 0) ELSE 0 END) AS expense_ex_mortgage
                FROM transactions
                WHERE user_id = ?
                  AND date IS NOT NULL AND date != ''
                  AND COALESCE(pending, 0) = 0
                  AND lower(COALESCE(type, '')) NOT IN ('internal transfer', ?)
                GROUP BY substr(date, 1, 4)
                ORDER BY year ASC
                """,
                (user_id, rental_category)
            ).fetchall()
            income_subcategory_rows = conn.execute(
                """
                SELECT substr(date, 1, 7) AS month,
                       COALESCE(NULLIF(TRIM(subtype), ''), 'Uncategorized') AS subcategory,
                       SUM(COALESCE(ipay, 0)) AS amount
                FROM transactions
                WHERE user_id = ?
                  AND date IS NOT NULL AND date != ''
                  AND COALESCE(pending, 0) = 0
                  AND lower(COALESCE(type, '')) = 'income'
                GROUP BY substr(date, 1, 7), COALESCE(NULLIF(TRIM(subtype), ''), 'Uncategorized')
                HAVING ABS(SUM(COALESCE(ipay, 0))) > 0.005
                ORDER BY month ASC, lower(subcategory) ASC
                """,
                (user_id,)
            ).fetchall()

        months = []
        totals = {"income": 0.0, "expense": 0.0, "living_expense": 0.0, "net_savings": 0.0}
        for r in rows:
            income = float(r["income"] or 0.0)
            expense = float(r["expense"] or 0.0)
            expense_ex_mortgage = float(r["expense_ex_mortgage"] or 0.0)
            living = float(r["living_expense"] or 0.0)
            net = income - expense
            months.append({
                "month": r["month"],
                "income": income,
                "expense": expense,
                "expense_ex_mortgage": expense_ex_mortgage,
                "living_expense": living,
                "net_savings": net,
                "savings_rate": (net / income if income else 0.0)
            })
            totals["income"] += income
            totals["expense"] += expense
            totals["living_expense"] += living
            totals["net_savings"] += net

        canonical_categories = load_canonical_categories()
        category_lookup = {}
        category_totals = {}
        for r in category_rows:
            amount = float(r["amount"] or 0.0)
            category = normalize_category_name(r["category"], canonical_categories)
            month_categories = category_lookup.setdefault(r["month"], {})
            month_categories[category] = month_categories.get(category, 0.0) + amount
            category_totals[category] = category_totals.get(category, 0.0) + amount

        category_order = sorted(category_totals.keys(), key=lambda category: category.lower())
        categories_by_month = {
            month: [
                {"category": category, "amount": amount}
                for category, amount in sorted(items.items(), key=lambda item: item[0].lower())
            ]
            for month, items in category_lookup.items()
        }
        category_matrix = [
            {
                "month": month["month"],
                "categories": {category: category_lookup.get(month["month"], {}).get(category, 0.0) for category in category_order}
            }
            for month in months
        ]

        yearly = []
        for r in yearly_rows:
            income = float(r["income"] or 0.0)
            expense = float(r["expense"] or 0.0)
            expense_ex_mortgage = float(r["expense_ex_mortgage"] or 0.0)
            net = income - expense
            yearly.append({
                "year": r["year"],
                "income": income,
                "expense": expense,
                "expense_ex_mortgage": expense_ex_mortgage,
                "net_savings": net,
                "savings_rate": (net / income if income else 0.0)
            })

        yearly_category_lookup = {}
        yearly_category_totals = {}
        for month, items in category_lookup.items():
            year = month[:4]
            year_categories = yearly_category_lookup.setdefault(year, {})
            for category, amount in items.items():
                year_categories[category] = year_categories.get(category, 0.0) + amount
                yearly_category_totals[category] = yearly_category_totals.get(category, 0.0) + amount
        yearly_category_order = sorted(yearly_category_totals.keys(), key=lambda category: category.lower())
        yearly_category_matrix = [
            {
                "year": row["year"],
                "categories": {category: yearly_category_lookup.get(row["year"], {}).get(category, 0.0) for category in yearly_category_order}
            }
            for row in yearly
        ]

        income_subcategory_lookup = {}
        income_subcategory_totals = {}
        for row in income_subcategory_rows:
            amount = float(row["amount"] or 0.0)
            subcategory = row["subcategory"]
            month_subcategories = income_subcategory_lookup.setdefault(row["month"], {})
            month_subcategories[subcategory] = month_subcategories.get(subcategory, 0.0) + amount
            income_subcategory_totals[subcategory] = income_subcategory_totals.get(subcategory, 0.0) + amount
        income_subcategory_order = sorted(income_subcategory_totals, key=lambda name: name.lower())
        income_subcategory_matrix = [
            {
                "month": row["month"],
                "subcategories": {
                    name: income_subcategory_lookup.get(row["month"], {}).get(name, 0.0)
                    for name in income_subcategory_order
                }
            }
            for row in months
        ]
        yearly_income_lookup = {}
        for month, subcategories in income_subcategory_lookup.items():
            year_subcategories = yearly_income_lookup.setdefault(month[:4], {})
            for name, amount in subcategories.items():
                year_subcategories[name] = year_subcategories.get(name, 0.0) + amount
        yearly_income_subcategory_matrix = [
            {
                "year": row["year"],
                "subcategories": {
                    name: yearly_income_lookup.get(row["year"], {}).get(name, 0.0)
                    for name in income_subcategory_order
                }
            }
            for row in yearly
        ]

        totals["savings_rate"] = totals["net_savings"] / totals["income"] if totals["income"] else 0.0
        recent = months[-12:]
        return jsonify({
            "totals": totals,
            "months": months,
            "recent_months": recent,
            "yearly": yearly,
            "categories_by_month": categories_by_month,
            "category_order": category_order,
            "category_totals": category_totals,
            "category_matrix": category_matrix,
            "yearly_category_order": yearly_category_order,
            "yearly_category_totals": yearly_category_totals,
            "yearly_category_matrix": yearly_category_matrix,
            "income_subcategory_order": income_subcategory_order,
            "income_subcategory_matrix": income_subcategory_matrix,
            "yearly_income_subcategory_matrix": yearly_income_subcategory_matrix
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def parse_trip_name(value, year_prefix=True, fallback_year="Note"):
    text = (value or '').strip()
    if not text:
        return {"year": fallback_year, "trip": fallback_year, "sort_year": -1}
    year = text[:4]
    if year_prefix and year.isdigit():
        trip = text[4:].strip(" -_|:/") or text
        return {"year": year, "trip": trip[:64], "sort_year": int(year)}
    return {"year": fallback_year, "trip": text[:64], "sort_year": -1}

def transaction_field(row, field_name, fallback=""):
    allowed = {"note", "subtype", "merchant"}
    if field_name not in allowed:
        return fallback
    return row[field_name] or fallback

@transactions_bp.route('/api/travel_analysis', methods=['GET'])
def travel_analysis():
    try:
        user_id = current_user_id()
        analysis_rules = get_analysis_rules()
        travel_rules = analysis_rules.get("travel") or {}
        travel_category = configured_category_key(analysis_rules, "travel", "Travel")
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT t.transaction_id,
                       t.date,
                       t.merchant,
                       t.amount,
                       t.direction,
                       t.account_name AS account_name_raw,
                       a.name AS account_name,
                       a.type AS account_type,
                       a.subtype AS account_subtype,
                       a.institution_name AS institution_name,
                       t.subtype,
                       t.note,
                       t.trip_id,
                       tr.name AS trip_name,
                       tr.year AS trip_year,
                       COALESCE(
                           t.ipay,
                           CASE
                               WHEN lower(COALESCE(t.direction, '')) IN ('inflow', 'income', 'credit')
                               THEN ABS(COALESCE(t.amount, 0))
                               ELSE -ABS(COALESCE(t.amount, 0))
                           END
                       ) AS signed_amount
                FROM transactions t
                LEFT JOIN accounts a ON t.account_name = a.account_id AND a.user_id = t.user_id
                LEFT JOIN trips tr ON t.trip_id = tr.id AND tr.user_id = t.user_id
                WHERE t.user_id = ?
                  AND lower(COALESCE(t.type, '')) = ?
                  AND COALESCE(t.pending, 0) = 0
                ORDER BY t.date DESC
                """,
                (user_id, travel_category)
            ).fetchall()

        trips = {}
        category_totals = {}
        for r in rows:
            amount = -float(r["signed_amount"] or 0.0)
            subtype = (transaction_field(r, travel_rules.get("category_source"), "Unclassified") or "Unclassified").strip() or "Unclassified"
            tx_year = (r["date"] or "")[:4]
            trip_year = str(r["trip_year"] or tx_year or "Unknown")
            sort_year = int(trip_year) if trip_year.isdigit() else -1
            trip_name = (r["trip_name"] or "").strip()
            if not trip_name:
                trip_name = f"Unassigned Travel {trip_year}"
            key = (r["trip_id"] or "", trip_year, trip_name)
            if key not in trips:
                trips[key] = {
                    "trip_id": r["trip_id"] or "",
                    "year": trip_year,
                    "sort_year": sort_year,
                    "trip": trip_name,
                    "total": 0.0,
                    "count": 0,
                    "first_date": r["date"],
                    "last_date": r["date"],
                    "categories": {},
                    "transactions": []
                }
            trip = trips[key]
            trip["total"] += amount
            trip["count"] += 1
            trip["categories"][subtype] = trip["categories"].get(subtype, 0.0) + amount
            trip["transactions"].append({
                "transaction_id": r["transaction_id"],
                "date": r["date"],
                "merchant": r["merchant"],
                "category": subtype,
                "amount": amount,
                "raw_amount": float(r["amount"] or 0.0),
                "ipay": float(r["signed_amount"] or 0.0),
                "direction": r["direction"],
                "account_name": 'Legacy' if r["account_name_raw"] == 'Legacy' else (r["account_name"] or r["account_name_raw"]),
                "account_name_raw": r["account_name_raw"],
                "account_type": r["account_type"],
                "account_subtype": r["account_subtype"],
                "institution_name": r["institution_name"],
                "note": r["note"]
            })
            category_totals[subtype] = category_totals.get(subtype, 0.0) + amount
            if r["date"]:
                trip["first_date"] = min(trip["first_date"], r["date"])
                trip["last_date"] = max(trip["last_date"], r["date"])

        category_order = sorted(category_totals.keys(), key=lambda category: category.lower())
        def trip_sort_key(trip):
            try:
                last_ordinal = datetime.strptime(trip["last_date"], "%Y-%m-%d").toordinal() if trip["last_date"] else 0
            except Exception:
                last_ordinal = 0
            return (
                trip["sort_year"] < 0,
                -trip["sort_year"],
                -last_ordinal,
                trip["trip"].lower()
            )

        sorted_trips = sorted(
            trips.values(),
            key=trip_sort_key
        )

        years = []
        year_lookup = {}
        for trip in sorted_trips:
            year = trip["year"]
            if year not in year_lookup:
                year_group = {"year": year, "trips": []}
                year_lookup[year] = year_group
                years.append(year_group)
            year_lookup[year]["trips"].append({
                "trip_id": trip["trip_id"],
                "year": trip["year"],
                "trip": trip["trip"],
                "total": trip["total"],
                "count": trip["count"],
                "first_date": trip["first_date"],
                "last_date": trip["last_date"],
                "categories": trip["categories"],
                "transactions": sorted(
                    trip["transactions"],
                    key=lambda tx: (tx.get("date") or "", tx.get("merchant") or ""),
                    reverse=True
                )
            })

        return jsonify({
            "category_order": category_order,
            "years": years
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/rental_analysis', methods=['GET'])
def rental_analysis():
    try:
        user_id = current_user_id()
        analysis_rules = get_analysis_rules()
        rental_rules = analysis_rules.get("rentals") or {}
        rental_category = configured_category_key(analysis_rules, "rentals", "Rentals")
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT t.transaction_id,
                       t.date,
                       t.merchant,
                       t.amount,
                       t.direction,
                       t.account_name AS account_name_raw,
                       a.name AS account_name,
                       a.type AS account_type,
                       a.subtype AS account_subtype,
                       a.institution_name AS institution_name,
                       t.subtype,
                       t.note,
                       t.rental_property_id,
                       rp.name AS property_name,
                       COALESCE(
                           t.ipay,
                           CASE
                               WHEN lower(COALESCE(t.direction, '')) IN ('inflow', 'income', 'credit') THEN ABS(COALESCE(t.amount, 0))
                               ELSE -ABS(COALESCE(t.amount, 0))
                           END
                       ) AS signed_amount
                FROM transactions t
                LEFT JOIN accounts a ON t.account_name = a.account_id AND a.user_id = t.user_id
                LEFT JOIN rental_properties rp ON t.rental_property_id = rp.id AND rp.user_id = t.user_id
                WHERE t.user_id = ?
                  AND lower(COALESCE(t.type, '')) = ?
                  AND COALESCE(t.pending, 0) = 0
                ORDER BY t.date DESC
                """,
                (user_id, rental_category)
            ).fetchall()

        properties = {}
        category_totals = {}
        for r in rows:
            property_name = (r["property_name"] or "").strip() or "Unassigned Rental Property"
            category = (
                transaction_field(r, rental_rules.get("category_source"), rental_rules.get("fallback_category") or "Unclassified")
                or rental_rules.get("fallback_category")
                or "Unclassified"
            ).strip() or "Unclassified"
            signed_amount = float(r["signed_amount"] or 0.0)
            month = (r["date"] or "")[:7]
            year = (r["date"] or "")[:4]
            property_key = r["rental_property_id"] or f"unassigned:{property_name}"

            if property_key not in properties:
                properties[property_key] = {
                    "property_id": r["rental_property_id"] or "",
                    "property": property_name,
                    "total": 0.0,
                    "income": 0.0,
                    "expense": 0.0,
                    "count": 0,
                    "first_date": r["date"],
                    "last_date": r["date"],
                    "categories": {},
                    "monthly": {},
                    "yearly": {},
                    "transactions": []
                }

            prop = properties[property_key]
            prop["total"] += signed_amount
            prop["income"] += max(signed_amount, 0.0)
            prop["expense"] += max(-signed_amount, 0.0)
            prop["count"] += 1
            prop["categories"][category] = prop["categories"].get(category, 0.0) + signed_amount
            category_totals[category] = category_totals.get(category, 0.0) + abs(signed_amount)

            if month:
                month_categories = prop["monthly"].setdefault(month, {})
                month_categories[category] = month_categories.get(category, 0.0) + signed_amount
            if year:
                year_categories = prop["yearly"].setdefault(year, {})
                year_categories[category] = year_categories.get(category, 0.0) + signed_amount

            prop["transactions"].append({
                "transaction_id": r["transaction_id"],
                "date": r["date"],
                "merchant": r["merchant"],
                "category": category,
                "amount": signed_amount,
                "raw_amount": float(r["amount"] or 0.0),
                "direction": r["direction"],
                "account_name": 'Legacy' if r["account_name_raw"] == 'Legacy' else (r["account_name"] or r["account_name_raw"]),
                "account_name_raw": r["account_name_raw"],
                "account_type": r["account_type"],
                "account_subtype": r["account_subtype"],
                "institution_name": r["institution_name"],
                "note": r["note"]
            })

            if r["date"]:
                prop["first_date"] = min(prop["first_date"] or r["date"], r["date"])
                prop["last_date"] = max(prop["last_date"] or r["date"], r["date"])

        category_order = sorted(category_totals.keys(), key=lambda category: category.lower())
        property_list = []
        for prop in properties.values():
            monthly_rows = [
                {
                    "month": month,
                    "categories": {category: categories.get(category, 0.0) for category in category_order},
                    "total": sum(categories.values())
                }
                for month, categories in sorted(prop["monthly"].items())
            ]
            yearly_rows = [
                {
                    "year": year,
                    "categories": {category: categories.get(category, 0.0) for category in category_order},
                    "total": sum(categories.values())
                }
                for year, categories in sorted(prop["yearly"].items())
            ]
            prop["monthly_matrix"] = monthly_rows
            prop["yearly_matrix"] = yearly_rows
            prop["transactions"] = sorted(
                prop["transactions"],
                key=lambda tx: (tx.get("date") or "", tx.get("merchant") or ""),
                reverse=True
            )
            property_list.append(prop)

        property_list.sort(key=lambda prop: (prop.get("property") or "").lower())
        return jsonify({
            "category_order": category_order,
            "properties": property_list
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/update_transaction', methods=['POST'])
def update_transaction():
    try:
        user_id = current_user_id()
        data = request.get_json() or {}
        tx_id = data.get('transaction_id')
        custom_type = data.get('type', 'Other')
        is_b = data.get('is_b', 'n')
        ratio = float(data.get('ratio', 1.0))
        mown = float(data.get('mown', 0.0))
        note = data.get('note', '')
        subtype = data.get('subtype', '')
        trip_id = (data.get('trip_id') or '').strip() or None
        rental_property_id = (data.get('rental_property_id') or '').strip() or None
        
        if not tx_id:
            return jsonify({"error": "Missing transaction_id"}), 400
            
        conn = get_db()
        cursor = conn.cursor()
        
        # Fetch existing transaction to get direction, amount, merchant, and settlement state.
        cursor.execute("SELECT amount, direction, merchant, pending FROM transactions WHERE transaction_id = ? AND user_id = ?", (tx_id, user_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "Transaction not found"}), 404
        if int(row['pending'] or 0) == 1:
            conn.close()
            return jsonify({"error": "Pending transactions cannot be reviewed until they are posted."}), 409
            
        amount = abs(float(row['amount']))
        direction = row['direction']
        merchant = row['merchant']
        custom_type_lower = (custom_type or '').strip().lower()
        if custom_type_lower == 'travel':
            rental_property_id = None
            if trip_id:
                exists = cursor.execute(
                    "SELECT 1 FROM trips WHERE id = ? AND user_id = ?",
                    (trip_id, user_id)
                ).fetchone()
                if not exists:
                    conn.close()
                    return jsonify({"error": "Trip not found"}), 404
        elif custom_type_lower == 'rentals':
            trip_id = None
            if rental_property_id:
                exists = cursor.execute(
                    "SELECT 1 FROM rental_properties WHERE id = ? AND user_id = ?",
                    (rental_property_id, user_id)
                ).fetchone()
                if not exists:
                    conn.close()
                    return jsonify({"error": "Property not found"}), 404
        else:
            trip_id = None
            rental_property_id = None
        
        # Calculate ipay and bpay
        if direction == 'inflow':
            ipay = amount
            bpay = 0.0
        else:
            if is_b == 'y':
                ipay = -amount * ratio
                bpay = -amount * (1.0 - ratio)
            elif is_b == 'b':
                ipay = 0.0
                bpay = -amount
            else:  # 'n'
                ipay = -amount
                bpay = 0.0
                
        cursor.execute(
            """
            UPDATE transactions 
            SET type = ?, is_b = ?, ratio = ?, ipay = ?, bpay = ?, mown = ?, note = ?, subtype = ?, trip_id = ?, rental_property_id = ?, reviewed = 1 
            WHERE transaction_id = ? AND user_id = ?
            """,
            (custom_type, is_b, ratio, ipay, bpay, mown, note, subtype, trip_id, rental_property_id, tx_id, user_id)
        )
        auto_applied_count = apply_stable_history_to_unreviewed(cursor, merchant, direction, user_id)
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "auto_applied_count": auto_applied_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/update_transaction_assignment', methods=['POST'])
def update_transaction_assignment():
    try:
        user_id = current_user_id()
        data = request.get_json() or {}
        tx_id = data.get('transaction_id')
        trip_id = (data.get('trip_id') or '').strip() or None
        rental_property_id = (data.get('rental_property_id') or '').strip() or None
        if not tx_id:
            return jsonify({"error": "Missing transaction_id"}), 400

        conn = get_db()
        row = conn.execute(
            "SELECT type, reviewed FROM transactions WHERE transaction_id = ? AND user_id = ?",
            (tx_id, user_id)
        ).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "Transaction not found"}), 404
        if int(row["reviewed"] or 0) == 1:
            conn.close()
            return jsonify({"error": "Reviewed transactions must be de-reviewed before changing assignment."}), 409

        tx_type = (row["type"] or "").strip().lower()
        if tx_type == "travel":
            rental_property_id = None
            if trip_id:
                exists = conn.execute(
                    "SELECT 1 FROM trips WHERE id = ? AND user_id = ?",
                    (trip_id, user_id)
                ).fetchone()
                if not exists:
                    conn.close()
                    return jsonify({"error": "Trip not found"}), 404
        elif tx_type == "rentals":
            trip_id = None
            if rental_property_id:
                exists = conn.execute(
                    "SELECT 1 FROM rental_properties WHERE id = ? AND user_id = ?",
                    (rental_property_id, user_id)
                ).fetchone()
                if not exists:
                    conn.close()
                    return jsonify({"error": "Property not found"}), 404
        else:
            trip_id = None
            rental_property_id = None

        conn.execute(
            """
            UPDATE transactions
            SET trip_id = ?, rental_property_id = ?
            WHERE transaction_id = ? AND user_id = ?
            """,
            (trip_id, rental_property_id, tx_id, user_id)
        )
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/unconfirm_transaction', methods=['POST'])
def unconfirm_transaction():
    try:
        user_id = current_user_id()
        data = request.get_json() or {}
        tx_id = data.get('transaction_id')
        if not tx_id:
            return jsonify({"error": "Missing transaction_id"}), 400
            
        conn = get_db()
        row = conn.execute("SELECT pending FROM transactions WHERE transaction_id = ? AND user_id = ?", (tx_id, user_id)).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "Transaction not found"}), 404
        if int(row['pending'] or 0) == 1:
            conn.close()
            return jsonify({"error": "Pending transactions cannot be changed until they are posted."}), 409
        conn.execute("UPDATE transactions SET reviewed = 0 WHERE transaction_id = ? AND user_id = ?", (tx_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/confirm_transfer', methods=['POST'])
def confirm_transfer():
    try:
        user_id = current_user_id()
        data = request.get_json() or {}
        tx_id_1 = data.get('tx_id_1')
        tx_id_2 = data.get('tx_id_2')
        if not tx_id_1 or not tx_id_2:
            return jsonify({"error": "Missing transaction IDs"}), 400
            
        conn = get_db()
        cursor = conn.cursor()

        pending_rows = cursor.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND transaction_id IN (?, ?) AND pending = 1",
            (user_id, tx_id_1, tx_id_2)
        ).fetchone()[0]
        if pending_rows:
            conn.close()
            return jsonify({"error": "Pending transactions cannot be confirmed as transfers until they are posted."}), 409
        
        for tx_id in [tx_id_1, tx_id_2]:
            cursor.execute("SELECT amount, direction FROM transactions WHERE transaction_id = ? AND user_id = ?", (tx_id, user_id))
            tx = cursor.fetchone()
            if not tx:
                continue
            amount, direction = tx
            # ipay is positive for inflow, negative for outflow
            ipay = amount if direction == 'inflow' else -amount
            
            cursor.execute(
                """
                UPDATE transactions 
                SET type = 'Internal Transfer', is_b = 'n', ratio = 1.0, ipay = ?, bpay = 0.0, mown = 0.0, reviewed = 1 
                WHERE transaction_id = ? AND user_id = ?
                """,
                (ipay, tx_id, user_id)
            )
            
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/categories', methods=['GET'])
def get_categories():
    try:
        user_id = current_user_id()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT type FROM transactions WHERE user_id = ? AND type IS NOT NULL AND type != ''", (user_id,))
        canonical_categories = load_canonical_categories()
        cats = [
            normalize_category_name("Income" if str(r[0]).strip().lower() == "income" else r[0], canonical_categories)
            for r in cursor.fetchall()
        ]
        conn.close()
        deduped = {}
        for category in cats:
            deduped.setdefault(str(category).lower(), category)
        return jsonify(sorted(deduped.values(), key=lambda category: category.lower()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/category_options', methods=['GET'])
def get_category_options():
    try:
        config = load_categories_config_from_db()
        categories = config.get('categories', [])
        rules = config.get('rules', {})
        return jsonify({
            "categories": categories,
            "subcategories": {category: rules.get(category, []) for category in categories},
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/delete_transaction', methods=['POST'])
def delete_transaction():
    try:
        user_id = current_user_id()
        data = request.get_json() or {}
        tx_id = data.get('transaction_id')
        if not tx_id:
            return jsonify({"error": "Missing transaction_id"}), 400
            
        conn = get_db()
        conn.execute("DELETE FROM transactions WHERE transaction_id = ? AND user_id = ?", (tx_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/merge_candidates', methods=['GET'])
def get_merge_candidates():
    try:
        user_id = current_user_id()
        legacy_id = request.args.get('legacy_id')
        if not legacy_id:
            return jsonify({"error": "Missing legacy_id"}), 400
            
        conn = get_db()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Get the legacy transaction details
        cursor.execute("SELECT date, amount, direction FROM transactions WHERE transaction_id = ? AND user_id = ?", (legacy_id, user_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "Legacy transaction not found"}), 404
            
        legacy_date = row['date']
        legacy_amount = row['amount']
        legacy_direction = row['direction']
        
        # 2. Query candidates: Plaid transactions (account_name != 'Legacy')
        cursor.execute(
            """
            SELECT t.*, a.name AS account_name_label 
            FROM transactions t
            LEFT JOIN accounts a ON t.account_name = a.account_id AND a.user_id = t.user_id
            WHERE t.user_id = ?
              AND t.account_name != 'Legacy' AND t.direction = ?
            """,
            (user_id, legacy_direction)
        )
        all_plaid = [dict(r) for r in cursor.fetchall()]
        conn.close()
        
        # Score and filter candidates in python for complex sorting
        legacy_dt = datetime.strptime(legacy_date, '%Y-%m-%d')
        candidates = []
        for p in all_plaid:
            p_date_str = p['authorized_date'] if p['authorized_date'] else p['date']
            p_dt = datetime.strptime(p_date_str, '%Y-%m-%d')
            date_diff = abs((legacy_dt - p_dt).days)
            
            # Match within 15 days window
            if date_diff <= 15:
                amount_diff = abs(legacy_amount - p['amount'])
                score = date_diff * 1.0
                if amount_diff > 0.01:
                    score += 100.0  # Heavy penalty for different amounts
                
                candidates.append({
                    "transaction_id": p['transaction_id'],
                    "date": p['date'],
                    "amount": p['amount'],
                    "merchant": p['merchant'],
                    "direction": p['direction'],
                    "account_name": p['account_name_label'] or p['account_name'],
                    "reviewed": p['reviewed'],
                    "date_diff": date_diff,
                    "score": score
                })
        
        # Sort by score ascending (lowest score is best match)
        candidates.sort(key=lambda x: x['score'])
        return jsonify(candidates[:5])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/merge_transactions', methods=['POST'])
def merge_transactions():
    try:
        user_id = current_user_id()
        data = request.get_json() or {}
        legacy_id = data.get('legacy_id')
        plaid_id = data.get('plaid_id')
        if not legacy_id or not plaid_id:
            return jsonify({"error": "Missing legacy_id or plaid_id"}), 400
            
        conn = get_db()
        cursor = conn.cursor()
        
        # 1. Fetch manual classifications from legacy
        cursor.execute("SELECT type, is_b, ratio, ipay, bpay, mown, note, subtype FROM transactions WHERE transaction_id = ? AND user_id = ?", (legacy_id, user_id))
        l_row = cursor.fetchone()
        if not l_row:
            conn.close()
            return jsonify({"error": "Legacy transaction not found"}), 404
            
        l_type, l_is_b, l_ratio, l_ipay, l_bpay, l_mown, l_note, l_subtype = l_row
        
        # 2. Update Plaid transaction
        conn.execute(
            """
            UPDATE transactions 
            SET type = ?, is_b = ?, ratio = ?, ipay = ?, bpay = ?, mown = ?, note = ?, subtype = ?, 
                reviewed = 1, imported_from_legacy = 1, legacy_matched = 1
            WHERE transaction_id = ? AND user_id = ?
            """,
            (l_type, l_is_b, l_ratio, l_ipay, l_bpay, l_mown, l_note, l_subtype, plaid_id, user_id)
        )
        
        # 3. Delete legacy duplicate
        conn.execute("DELETE FROM transactions WHERE transaction_id = ? AND user_id = ?", (legacy_id, user_id))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/create_manual_transaction', methods=['POST'])
def create_manual_transaction():
    try:
        user_id = current_user_id()
        data = request.get_json() or {}
        
        tx_date = data.get('date') or datetime.now().strftime('%Y-%m-%d')
        merchant = data.get('merchant', 'Manual Transaction')
        t_type = data.get('type', 'Other')
        amount = float(data.get('amount', 0.0))
        direction = data.get('direction', 'outflow')
        is_b = data.get('is_b', 'n')
        ratio = float(data.get('ratio', 1.0))
        mown = float(data.get('mown', 0.0))
        note = data.get('note', '')
        subtype = data.get('subtype', '')
        reviewed = int(data.get('reviewed', 1))
        
        ipay = 0.0
        bpay = 0.0
        abs_amount = abs(amount)
        if direction == 'inflow':
            ipay = abs_amount
            bpay = 0.0
        else:
            if is_b == 'y':
                ipay = -abs_amount * ratio
                bpay = -abs_amount * (1.0 - ratio)
            elif is_b == 'b':
                ipay = 0.0
                bpay = -abs_amount
            else:
                ipay = -abs_amount
                bpay = 0.0
                
        tx_id = f"manual_{uuid.uuid4().hex[:12]}"
        
        conn = get_db()
        conn.execute(
            """
            INSERT INTO transactions (
                transaction_id, date, type, merchant, amount, direction, account_name,
                authorized_date, pending, categories, location, payment_channel,
                is_b, ratio, ipay, bpay, mown, note, subtype, reviewed,
                imported_from_legacy, legacy_matched, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, '[]', '{}', 'other', ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
            """,
            (
                tx_id,
                tx_date,
                t_type,
                merchant,
                abs_amount,
                direction,
                'Legacy',
                tx_date,
                is_b,
                ratio,
                ipay,
                bpay,
                mown,
                note,
                subtype,
                reviewed,
                user_id
            )
        )
        
        conn.execute(
            """
            INSERT OR IGNORE INTO accounts (account_id, name, official_name, type, subtype, user_id)
            VALUES ('Legacy', 'Legacy', 'Legacy Spreadsheet Data', 'depository', 'checking', ?)
            """
            ,
            (user_id,)
        )
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "transaction_id": tx_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transactions_bp.route('/api/disconnect', methods=['POST'])
def disconnect_accounts():
    try:
        user_id = current_user_id()
        with get_db() as conn:
            conn.execute("DELETE FROM plaid_tokens WHERE user_id = ?", (user_id,))
            conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
