import re


TRANSACTIONS_SOURCE = "transactions"
INVESTMENTS_SOURCE = "investments"


def ensure_plaid_transaction_aliases(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS plaid_transaction_aliases (
            user_id TEXT NOT NULL,
            source TEXT NOT NULL,
            source_transaction_id TEXT NOT NULL,
            canonical_transaction_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, source, source_transaction_id)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_plaid_transaction_aliases_canonical
        ON plaid_transaction_aliases(user_id, canonical_transaction_id)
        """
    )


def normalized_description(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def resolve_plaid_transaction_alias(cursor, user_id, source, source_transaction_id):
    ensure_plaid_transaction_aliases(cursor)
    row = cursor.execute(
        """
        SELECT canonical_transaction_id
        FROM plaid_transaction_aliases
        WHERE user_id = ? AND source = ? AND source_transaction_id = ?
        """,
        (user_id, source, source_transaction_id),
    ).fetchone()
    return row["canonical_transaction_id"] if row else None


def link_plaid_transaction_alias(cursor, user_id, source, source_transaction_id, canonical_transaction_id):
    ensure_plaid_transaction_aliases(cursor)
    cursor.execute(
        """
        INSERT INTO plaid_transaction_aliases
            (user_id, source, source_transaction_id, canonical_transaction_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, source, source_transaction_id)
        DO UPDATE SET canonical_transaction_id = excluded.canonical_transaction_id
        """,
        (user_id, source, source_transaction_id, canonical_transaction_id),
    )


def find_unique_cross_source_match(
    cursor,
    user_id,
    incoming_source,
    transaction_id,
    account_id,
    date_str,
    merchant,
    amount,
    direction,
):
    """Return a match only when an opposite Plaid feed has one unambiguous candidate."""
    if not user_id or not account_id or not date_str or not merchant:
        return None
    if incoming_source == INVESTMENTS_SOURCE:
        channel_clause = "COALESCE(payment_channel, '') != 'investment'"
    else:
        channel_clause = "payment_channel = 'investment'"
    rows = cursor.execute(
        f"""
        SELECT *
        FROM transactions
        WHERE user_id = ?
          AND transaction_id != ?
          AND account_name = ?
          AND amount = ?
          AND direction = ?
          AND pending = 0
          AND imported_from_legacy = 0
          AND {channel_clause}
          AND (
              ABS(julianday(date) - julianday(?)) <= 1
              OR ABS(julianday(COALESCE(authorized_date, date)) - julianday(?)) <= 1
          )
        """,
        (user_id, transaction_id, account_id, amount, direction, date_str, date_str),
    ).fetchall()
    matches = [row for row in rows if normalized_description(row["merchant"]) == normalized_description(merchant)]
    return matches[0] if len(matches) == 1 else None


def reconcile_existing_cross_source_duplicates(conn):
    """Collapse confident regular/investment pairs, keeping the investment row canonical."""
    ensure_plaid_transaction_aliases(conn)
    merged = 0
    investment_rows = conn.execute(
        """
        SELECT * FROM transactions
        WHERE payment_channel = 'investment'
          AND pending = 0
          AND imported_from_legacy = 0
          AND user_id IS NOT NULL
          AND user_id != ''
        ORDER BY date, transaction_id
        """
    ).fetchall()
    for investment in investment_rows:
        regular = find_unique_cross_source_match(
            conn,
            investment["user_id"],
            INVESTMENTS_SOURCE,
            investment["transaction_id"],
            investment["account_name"],
            investment["date"],
            investment["merchant"],
            investment["amount"],
            investment["direction"],
        )
        if not regular:
            link_plaid_transaction_alias(
                conn, investment["user_id"], INVESTMENTS_SOURCE,
                investment["transaction_id"], investment["transaction_id"]
            )
            continue

        canonical_id = investment["transaction_id"]
        regular_id = regular["transaction_id"]
        # Keep user-entered context if it exists only on the regular-feed copy.
        conn.execute(
            """
            UPDATE transactions
            SET note = CASE WHEN COALESCE(note, '') = '' THEN COALESCE(?, '') ELSE note END,
                trip_id = COALESCE(trip_id, ?),
                rental_property_id = COALESCE(rental_property_id, ?),
                is_reimbursement = MAX(COALESCE(is_reimbursement, 0), ?),
                reviewed = MAX(COALESCE(reviewed, 0), ?)
            WHERE transaction_id = ? AND user_id = ?
            """,
            (
                regular["note"], regular["trip_id"], regular["rental_property_id"],
                int(regular["is_reimbursement"] or 0), int(regular["reviewed"] or 0),
                canonical_id, investment["user_id"],
            ),
        )
        link_plaid_transaction_alias(
            conn, investment["user_id"], INVESTMENTS_SOURCE, canonical_id, canonical_id
        )
        link_plaid_transaction_alias(
            conn, investment["user_id"], TRANSACTIONS_SOURCE, regular_id, canonical_id
        )
        conn.execute(
            "DELETE FROM transactions WHERE transaction_id = ? AND user_id = ?",
            (regular_id, investment["user_id"]),
        )
        merged += 1
    return merged
