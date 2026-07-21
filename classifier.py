import re
from collections import Counter


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
          AND COALESCE(pending, 0) = 0
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

    counts = Counter(matches)
    ranked = counts.most_common(2)
    if not ranked or ranked[0][1] < min_count:
        return None
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    (learned_type, learned_subtype), winner_count = ranked[0]
    return {
        "type": learned_type,
        "subtype": learned_subtype,
        "source": "history",
        "confidence": 0.95,
        "reason": f"Learned from the most common reviewed classification ({winner_count} of {len(matches)}).",
        "match_count": winner_count,
        "total_count": len(matches)
    }


def constrain_classification_to_config(classification, categories, category_rules=None):
    result = dict(classification or {})
    original_type = (result.get("type") or "Other").strip()
    constrained_type = constrain_category_to_config(original_type, categories)
    result["type"] = constrained_type
    if constrained_type.lower() != original_type.lower():
        result["subtype"] = ""
    elif category_rules is not None and result.get("subtype"):
        configured_subtypes = next(
            (
                values
                for category, values in category_rules.items()
                if str(category).strip().lower() == constrained_type.lower()
            ),
            [],
        )
        by_lower = {
            str(value).strip().lower(): str(value).strip()
            for value in configured_subtypes
            if str(value).strip()
        }
        result["subtype"] = by_lower.get(str(result["subtype"]).strip().lower(), "")
    return result


def predict_custom_type(plaid_primary, plaid_detailed, merchant, is_income):
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


def predict_transaction_classification(cursor, plaid_primary, plaid_detailed, merchant, direction, categories, category_rules=None, user_id=None):
    learned = infer_transaction_classification_from_history(cursor, merchant, direction, user_id=user_id)
    if learned:
        return constrain_classification_to_config(learned, categories, category_rules)

    predicted = constrain_category_to_config(
        predict_custom_type(plaid_primary, plaid_detailed, merchant, direction == "inflow"),
        categories
    )
    if predicted and predicted != "Other":
        return {
            "type": predicted,
            "subtype": "",
            "source": "plaid_category",
            "confidence": 0.6,
            "reason": "Mapped from Plaid personal finance category."
        }
    return {
        "type": "Other",
        "subtype": "",
        "source": "fallback",
        "confidence": 0.1,
        "reason": "No stable history or Plaid category mapping matched."
    }


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
