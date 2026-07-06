import re


def normalize_merchant_key(merchant):
    name = (merchant or "").lower().strip()
    name = re.sub(r"['’]", "", name)
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def infer_transaction_classification_from_history(cursor, merchant, direction, min_count=3, user_id=None):
    merchant_key = normalize_merchant_key(merchant)
    direction = (direction or "").strip().lower()
    if not merchant_key or not direction:
        return None

    user_clause = "AND user_id = ?" if user_id else ""
    params = []
    if user_id:
        params.append(user_id)
    params.append(direction)
    cursor.execute(
        """
        SELECT merchant, type, subtype
        FROM transactions
        WHERE reviewed = 1
          {user_clause}
          AND merchant IS NOT NULL
          AND TRIM(merchant) != ''
          AND lower(COALESCE(direction, '')) = ?
          AND type IS NOT NULL
          AND TRIM(type) != ''
        """.format(user_clause=user_clause),
        tuple(params)
    )
    matches = []
    for row in cursor.fetchall():
        row_merchant = row["merchant"] if hasattr(row, "keys") else row[0]
        if normalize_merchant_key(row_merchant) != merchant_key:
            continue
        row_type = (row["type"] if hasattr(row, "keys") else row[1]) or ""
        row_subtype = (row["subtype"] if hasattr(row, "keys") else row[2]) or ""
        row_type = row_type.strip()
        row_subtype = row_subtype.strip()
        if row_type:
            matches.append((row_type, row_subtype))

    if len(matches) < min_count:
        return None
    unique_pairs = set(matches)
    if len(unique_pairs) != 1:
        return None
    learned_type, learned_subtype = matches[0]
    return {
        "type": learned_type,
        "subtype": learned_subtype,
        "source": "merchant_history",
        "match_count": len(matches)
    }


def predict_custom_type(plaid_primary, plaid_detailed, merchant, is_income):
    merchant_lower = (merchant or "").lower()
    
    # Check merchant name first for common ones
    if "costco" in merchant_lower or "trader joe" in merchant_lower or "safeway" in merchant_lower or "h mart" in merchant_lower or "grocer" in merchant_lower:
        return "Groceries"
    if "amazon" in merchant_lower or "mktplace" in merchant_lower:
        return "Shopping"
    if "google fi" in merchant_lower or "ziply" in merchant_lower or "internet" in merchant_lower:
        return "Internet"
    if "netflix" in merchant_lower or "spotify" in merchant_lower or "youtube" in merchant_lower or "subscr" in merchant_lower:
        return "Subscription"
    if "gas" in merchant_lower or "shell" in merchant_lower or "chevron" in merchant_lower or "exxon" in merchant_lower:
        return "Gas"
        
    # Check Plaid categories
    primary = (plaid_primary or '').upper()
    detailed = (plaid_detailed or '').upper()
    
    if primary == 'FOOD_AND_DRINK':
        if 'GROCERIES' in detailed:
            return 'Groceries'
        return 'Restaurant'
    if primary == 'GENERAL_MERCHANDISE':
        if 'SUPERSTORES' in detailed or 'WHOLESALE' in detailed:
            return 'Groceries'
        return 'Shopping'
    if primary == 'RENT_AND_UTILITIES':
        if 'RENT' in detailed:
            return 'Rent'
        if 'TELEPHONE' in detailed:
            return 'Phone'
        if 'INTERNET' in detailed:
            return 'Internet'
        return 'Utility'
    if primary == 'TRANSPORTATION':
        if 'GAS' in detailed:
            return 'Gas'
        return 'Transport'
    if primary == 'TRAVEL':
        return 'Travel'
    if primary == 'LOAN_PAYMENTS':
        return 'Loan'
    if primary == 'MEDICAL':
        return 'Medical'
    if primary == 'ENTERTAINMENT':
        return 'Entertaining'
    if primary == 'BANK_FEES':
        return 'Bank Fees'
        
    return 'Other'


def constrain_category_to_config(category, categories):
    configured = [str(c).strip() for c in (categories or []) if str(c).strip()]
    if not configured:
        return category or "Other"

    by_lower = {c.lower(): c for c in configured}
    category_key = (category or "").strip().lower()
    if category_key in by_lower:
        return by_lower[category_key]
    if "other" in by_lower:
        return by_lower["other"]
    return configured[0]
