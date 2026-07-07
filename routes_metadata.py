import uuid

from flask import Blueprint, jsonify, request

from auth import current_user_id
from database import get_db

metadata_bp = Blueprint("metadata", __name__)


def _trip_payload(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "year": row["year"],
        "destination": row["destination"] or "",
        "budget": row["budget"],
        "currency": row["currency"] or "USD",
        "travelers": row["travelers"] or "",
        "notes": row["notes"] or "",
        "status": row["status"] or "active",
    }


def _property_payload(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "address": row["address"] or "",
        "city": row["city"] or "",
        "state": row["state"] or "",
        "active": int(row["active"] if row["active"] is not None else 1),
        "notes": row["notes"] or "",
    }


def _rule_payload(row):
    return {
        "id": row["id"],
        "rental_property_id": row["rental_property_id"],
        "name": row["name"] or "",
        "merchant_contains": row["merchant_contains"] or "",
        "account_name_contains": row["account_name_contains"] or "",
        "direction": row["direction"] or "",
        "amount_min": row["amount_min"],
        "amount_max": row["amount_max"],
        "default_subtype": row["default_subtype"] or "",
        "enabled": int(row["enabled"] if row["enabled"] is not None else 1),
    }


def _clean_text(value):
    return str(value or "").strip()


def _clean_year(value):
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _clean_float(value):
    if value in (None, ""):
        return None
    return float(value)


def _clean_direction(value):
    direction = _clean_text(value).lower()
    return direction if direction in ("", "inflow", "outflow") else ""


def _property_exists(conn, user_id, property_id):
    return conn.execute(
        "SELECT 1 FROM rental_properties WHERE id = ? AND user_id = ?",
        (property_id, user_id),
    ).fetchone() is not None


def _rule_matches(rule, tx):
    merchant = (tx["merchant"] or "").lower()
    account = " ".join([
        tx["account_name_raw"] or "",
        tx["account_display_name"] or "",
        tx["institution_name"] or "",
    ]).lower()
    direction = (tx["direction"] or "").lower()
    amount = abs(float(tx["amount"] or 0))

    merchant_contains = (rule["merchant_contains"] or "").strip().lower()
    if merchant_contains and merchant_contains not in merchant:
        return False

    account_contains = (rule["account_name_contains"] or "").strip().lower()
    if account_contains and account_contains not in account:
        return False

    rule_direction = (rule["direction"] or "").strip().lower()
    if rule_direction and rule_direction != direction:
        return False

    if rule["amount_min"] is not None and amount < float(rule["amount_min"]):
        return False
    if rule["amount_max"] is not None and amount > float(rule["amount_max"]):
        return False
    return True


def apply_rental_property_rules_to_transaction(cursor, user_id, tx_id, rental_property_id=None, rule_id=None):
    tx = cursor.execute(
        """
        SELECT t.transaction_id,
               t.merchant,
               t.amount,
               t.direction,
               t.reviewed,
               t.imported_from_legacy,
               t.account_name AS account_name_raw,
               a.name AS account_display_name,
               a.institution_name AS institution_name
        FROM transactions t
        LEFT JOIN accounts a ON t.account_name = a.account_id AND a.user_id = t.user_id
        WHERE t.transaction_id = ? AND t.user_id = ?
        """,
        (tx_id, user_id),
    ).fetchone()
    if not tx or int(tx["reviewed"] or 0) == 1 or int(tx["imported_from_legacy"] or 0) == 1:
        return False

    params = [user_id]
    rule_clauses = ["user_id = ?", "enabled = 1"]
    if rental_property_id:
        rule_clauses.append("rental_property_id = ?")
        params.append(rental_property_id)
    if rule_id:
        rule_clauses.append("id = ?")
        params.append(rule_id)
    rules = cursor.execute(
        """
        SELECT *
        FROM rental_property_match_rules
        WHERE {where_sql}
        ORDER BY created_at ASC, id ASC
        """.format(where_sql=" AND ".join(rule_clauses)),
        tuple(params),
    ).fetchall()
    for rule in rules:
        if not _rule_matches(rule, tx):
            continue
        cursor.execute(
            """
            UPDATE transactions
            SET type = 'Rentals',
                subtype = ?,
                rental_property_id = ?,
                trip_id = NULL,
                prediction_source = 'rental_property_rule',
                prediction_confidence = 0.95,
                prediction_reason = ?
            WHERE transaction_id = ? AND user_id = ? AND reviewed = 0
            """,
            (
                rule["default_subtype"] or "",
                rule["rental_property_id"],
                f"Matched rental property rule: {rule['name'] or rule['id']}",
                tx_id,
                user_id,
            ),
        )
        return cursor.rowcount > 0
    return False


def apply_rental_property_rules_to_unreviewed(cursor, user_id, rental_property_id=None, rule_id=None):
    params = [user_id]
    rule_clauses = ["user_id = ?", "enabled = 1"]
    if rental_property_id:
        rule_clauses.append("rental_property_id = ?")
        params.append(rental_property_id)
    if rule_id:
        rule_clauses.append("id = ?")
        params.append(rule_id)
    rule_rows = cursor.execute(
        f"SELECT id FROM rental_property_match_rules WHERE {' AND '.join(rule_clauses)}",
        tuple(params),
    ).fetchall()
    if not rule_rows:
        return 0

    tx_rows = cursor.execute(
        """
        SELECT transaction_id
        FROM transactions
        WHERE user_id = ?
          AND reviewed = 0
          AND imported_from_legacy = 0
        ORDER BY date DESC, transaction_id DESC
        """,
        (user_id,),
    ).fetchall()
    count = 0
    for tx in tx_rows:
        before = cursor.execute(
            "SELECT rental_property_id, subtype, type FROM transactions WHERE transaction_id = ? AND user_id = ?",
            (tx["transaction_id"], user_id),
        ).fetchone()
        if apply_rental_property_rules_to_transaction(cursor, user_id, tx["transaction_id"], rental_property_id, rule_id):
            after = cursor.execute(
                "SELECT rental_property_id, subtype, type FROM transactions WHERE transaction_id = ? AND user_id = ?",
                (tx["transaction_id"], user_id),
            ).fetchone()
            if tuple(before) != tuple(after):
                count += 1
    return count


@metadata_bp.route("/api/trips", methods=["GET", "POST"])
def trips_api():
    user_id = current_user_id()
    if request.method == "GET":
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM trips
                WHERE user_id = ?
                ORDER BY COALESCE(year, 0) DESC, lower(name)
                """,
                (user_id,),
            ).fetchall()
        return jsonify([_trip_payload(row) for row in rows])

    data = request.get_json() or {}
    name = _clean_text(data.get("name"))
    if not name:
        return jsonify({"error": "Trip name is required"}), 400
    trip_id = f"trip_{uuid.uuid4().hex}"
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO trips
            (id, user_id, name, year, destination, budget, currency, travelers, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trip_id,
                user_id,
                name,
                _clean_year(data.get("year")),
                _clean_text(data.get("destination")),
                _clean_float(data.get("budget")),
                _clean_text(data.get("currency")) or "USD",
                _clean_text(data.get("travelers")),
                _clean_text(data.get("notes")),
                _clean_text(data.get("status")) or "active",
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM trips WHERE id = ? AND user_id = ?", (trip_id, user_id)).fetchone()
    return jsonify(_trip_payload(row)), 201


@metadata_bp.route("/api/trips/<trip_id>", methods=["PATCH", "DELETE"])
def trip_detail_api(trip_id):
    user_id = current_user_id()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM trips WHERE id = ? AND user_id = ?", (trip_id, user_id)).fetchone()
        if not row:
            return jsonify({"error": "Trip not found"}), 404

        if request.method == "DELETE":
            refs = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND trip_id = ?",
                (user_id, trip_id),
            ).fetchone()[0]
            if refs:
                conn.execute(
                    "UPDATE trips SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                    (trip_id, user_id),
                )
                status = "archived"
            else:
                conn.execute("DELETE FROM trips WHERE id = ? AND user_id = ?", (trip_id, user_id))
                status = "deleted"
            conn.commit()
            return jsonify({"status": status})

        data = request.get_json() or {}
        name = _clean_text(data.get("name", row["name"]))
        if not name:
            return jsonify({"error": "Trip name is required"}), 400
        conn.execute(
            """
            UPDATE trips
            SET name = ?,
                year = ?,
                destination = ?,
                budget = ?,
                currency = ?,
                travelers = ?,
                notes = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (
                name,
                _clean_year(data.get("year", row["year"])),
                _clean_text(data.get("destination", row["destination"])),
                _clean_float(data.get("budget", row["budget"])),
                _clean_text(data.get("currency", row["currency"])) or "USD",
                _clean_text(data.get("travelers", row["travelers"])),
                _clean_text(data.get("notes", row["notes"])),
                _clean_text(data.get("status", row["status"])) or "active",
                trip_id,
                user_id,
            ),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM trips WHERE id = ? AND user_id = ?", (trip_id, user_id)).fetchone()
    return jsonify(_trip_payload(updated))


@metadata_bp.route("/api/rental_properties", methods=["GET", "POST"])
def rental_properties_api():
    user_id = current_user_id()
    if request.method == "GET":
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT * FROM rental_properties
                WHERE user_id = ?
                ORDER BY active DESC, lower(name)
                """,
                (user_id,),
            ).fetchall()
        return jsonify([_property_payload(row) for row in rows])

    data = request.get_json() or {}
    name = _clean_text(data.get("name"))
    if not name:
        return jsonify({"error": "Property name is required"}), 400
    property_id = f"rprop_{uuid.uuid4().hex}"
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO rental_properties
            (id, user_id, name, address, city, state, active, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                property_id,
                user_id,
                name,
                _clean_text(data.get("address")),
                _clean_text(data.get("city")),
                _clean_text(data.get("state")),
                1 if data.get("active", 1) else 0,
                _clean_text(data.get("notes")),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM rental_properties WHERE id = ? AND user_id = ?",
            (property_id, user_id),
        ).fetchone()
    return jsonify(_property_payload(row)), 201


@metadata_bp.route("/api/rental_properties/<property_id>", methods=["PATCH", "DELETE"])
def rental_property_detail_api(property_id):
    user_id = current_user_id()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM rental_properties WHERE id = ? AND user_id = ?",
            (property_id, user_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Property not found"}), 404

        if request.method == "DELETE":
            refs = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND rental_property_id = ?",
                (user_id, property_id),
            ).fetchone()[0]
            if refs:
                conn.execute(
                    """
                    UPDATE rental_properties
                    SET active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                    """,
                    (property_id, user_id),
                )
                status = "archived"
            else:
                conn.execute(
                    "DELETE FROM rental_properties WHERE id = ? AND user_id = ?",
                    (property_id, user_id),
                )
                status = "deleted"
            conn.commit()
            return jsonify({"status": status})

        data = request.get_json() or {}
        name = _clean_text(data.get("name", row["name"]))
        if not name:
            return jsonify({"error": "Property name is required"}), 400
        conn.execute(
            """
            UPDATE rental_properties
            SET name = ?,
                address = ?,
                city = ?,
                state = ?,
                active = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (
                name,
                _clean_text(data.get("address", row["address"])),
                _clean_text(data.get("city", row["city"])),
                _clean_text(data.get("state", row["state"])),
                1 if data.get("active", row["active"]) else 0,
                _clean_text(data.get("notes", row["notes"])),
                property_id,
                user_id,
            ),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM rental_properties WHERE id = ? AND user_id = ?",
            (property_id, user_id),
        ).fetchone()
    return jsonify(_property_payload(updated))


@metadata_bp.route("/api/rental_property_match_rules", methods=["GET", "POST"])
def rental_property_rules_api():
    user_id = current_user_id()
    if request.method == "GET":
        property_id = _clean_text(request.args.get("rental_property_id"))
        params = [user_id]
        where = ["user_id = ?"]
        if property_id:
            where.append("rental_property_id = ?")
            params.append(property_id)
        with get_db() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM rental_property_match_rules
                WHERE {' AND '.join(where)}
                ORDER BY created_at ASC, id ASC
                """,
                tuple(params),
            ).fetchall()
        return jsonify([_rule_payload(row) for row in rows])

    data = request.get_json() or {}
    property_id = _clean_text(data.get("rental_property_id"))
    if not property_id:
        return jsonify({"error": "Missing rental_property_id"}), 400
    with get_db() as conn:
        if not _property_exists(conn, user_id, property_id):
            return jsonify({"error": "Property not found"}), 404
        rule_id = f"rrule_{uuid.uuid4().hex}"
        conn.execute(
            """
            INSERT INTO rental_property_match_rules
            (id, user_id, rental_property_id, name, merchant_contains, account_name_contains,
             direction, amount_min, amount_max, default_subtype, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                user_id,
                property_id,
                _clean_text(data.get("name")),
                _clean_text(data.get("merchant_contains")),
                _clean_text(data.get("account_name_contains")),
                _clean_direction(data.get("direction")),
                _clean_float(data.get("amount_min")),
                _clean_float(data.get("amount_max")),
                _clean_text(data.get("default_subtype")),
                1 if data.get("enabled", 1) else 0,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM rental_property_match_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id),
        ).fetchone()
    return jsonify(_rule_payload(row)), 201


@metadata_bp.route("/api/rental_property_match_rules/<rule_id>", methods=["PATCH", "DELETE"])
def rental_property_rule_detail_api(rule_id):
    user_id = current_user_id()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM rental_property_match_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Rule not found"}), 404

        if request.method == "DELETE":
            conn.execute(
                "DELETE FROM rental_property_match_rules WHERE id = ? AND user_id = ?",
                (rule_id, user_id),
            )
            conn.commit()
            return jsonify({"status": "deleted"})

        data = request.get_json() or {}
        property_id = _clean_text(data.get("rental_property_id", row["rental_property_id"]))
        if not _property_exists(conn, user_id, property_id):
            return jsonify({"error": "Property not found"}), 404
        conn.execute(
            """
            UPDATE rental_property_match_rules
            SET rental_property_id = ?,
                name = ?,
                merchant_contains = ?,
                account_name_contains = ?,
                direction = ?,
                amount_min = ?,
                amount_max = ?,
                default_subtype = ?,
                enabled = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (
                property_id,
                _clean_text(data.get("name", row["name"])),
                _clean_text(data.get("merchant_contains", row["merchant_contains"])),
                _clean_text(data.get("account_name_contains", row["account_name_contains"])),
                _clean_direction(data.get("direction", row["direction"])),
                _clean_float(data.get("amount_min", row["amount_min"])),
                _clean_float(data.get("amount_max", row["amount_max"])),
                _clean_text(data.get("default_subtype", row["default_subtype"])),
                1 if data.get("enabled", row["enabled"]) else 0,
                rule_id,
                user_id,
            ),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM rental_property_match_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id),
        ).fetchone()
    return jsonify(_rule_payload(updated))


@metadata_bp.route("/api/rental_property_match_rules/apply", methods=["POST"])
def apply_rental_property_rules_api():
    user_id = current_user_id()
    data = request.get_json() or {}
    property_id = _clean_text(data.get("rental_property_id"))
    rule_id = _clean_text(data.get("rule_id"))
    with get_db() as conn:
        if property_id and not _property_exists(conn, user_id, property_id):
            return jsonify({"error": "Property not found"}), 404
        if rule_id:
            row = conn.execute(
                "SELECT 1 FROM rental_property_match_rules WHERE id = ? AND user_id = ?",
                (rule_id, user_id),
            ).fetchone()
            if not row:
                return jsonify({"error": "Rule not found"}), 404
        updated = apply_rental_property_rules_to_unreviewed(conn.cursor(), user_id, property_id or None, rule_id or None)
        conn.commit()
    return jsonify({"status": "success", "updated_count": updated})
