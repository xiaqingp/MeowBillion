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
