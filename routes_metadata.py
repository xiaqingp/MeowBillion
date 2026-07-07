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


def _clean_text(value):
    return str(value or "").strip()


def _clean_year(value):
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _clean_float(value):
    if value in (None, ""):
        return None
    return float(value)


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
