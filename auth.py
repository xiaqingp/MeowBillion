import os
import sqlite3
import uuid
from functools import wraps
from flask import Blueprint, jsonify, has_request_context, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db

auth_bp = Blueprint("auth", __name__)


def current_user_id():
    if not has_request_context():
        return None
    return session.get("user_id")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user_id():
            return jsonify({"error": "Authentication required"}), 401
        return fn(*args, **kwargs)
    return wrapper


def users_exist(conn):
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0


def signups_allowed():
    return os.getenv("ALLOW_SIGNUPS", "true").strip().lower() not in ("0", "false", "no")


def adopt_unowned_data(conn, user_id):
    tables = [
        "plaid_tokens",
        "accounts",
        "transactions",
        "account_balances_history",
        "allocation_overrides",
        "manual_assets",
        "manual_asset_values",
        "allocation_history_snapshots",
        "account_value_estimates",
        "trips",
        "rental_properties",
        "rental_property_match_rules",
    ]
    for table in tables:
        conn.execute(f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL OR user_id = ''", (user_id,))

    for key in ("categories_config", "analysis_rules", "last_sync_time"):
        row = conn.execute("SELECT value FROM app_config WHERE key = ?", (key,)).fetchone()
        if row:
            conn.execute(
                """
                INSERT OR REPLACE INTO app_config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (f"{user_id}:{key}", row["value"]),
            )
        row = conn.execute("SELECT value FROM sync_metadata WHERE key = ?", (key,)).fetchone()
        if row:
            conn.execute(
                "INSERT OR REPLACE INTO sync_metadata (key, value) VALUES (?, ?)",
                (f"{user_id}:{key}", row["value"]),
            )


def create_user(conn, email, password, display_name, role):
    email = (email or "").strip().lower()
    display_name = (display_name or "").strip() or email
    if not email or not password:
        raise ValueError("Email and password are required")
    user_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO users (id, email, password_hash, display_name, role, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        """,
        (user_id, email, generate_password_hash(password), display_name, role),
    )
    return user_id


@auth_bp.route("/api/auth/status", methods=["GET"])
def auth_status():
    with get_db() as conn:
        exists = users_exist(conn)
        user = None
        if current_user_id():
            row = conn.execute(
                "SELECT id, email, display_name, role FROM users WHERE id = ?",
                (current_user_id(),),
            ).fetchone()
            user = dict(row) if row else None
    return jsonify({
        "setup_required": not exists,
        "authenticated": bool(user),
        "allow_signups": signups_allowed(),
        "user": user,
    })


@auth_bp.route("/api/auth/setup", methods=["POST"])
def setup():
    data = request.get_json() or {}
    with get_db() as conn:
        if users_exist(conn):
            return jsonify({"error": "Setup already completed"}), 409
        try:
            user_id = create_user(conn, data.get("email"), data.get("password"), data.get("display_name"), "admin")
            adopt_unowned_data(conn, user_id)
            conn.commit()
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    session["user_id"] = user_id
    return jsonify({"status": "success"})


@auth_bp.route("/api/auth/signup", methods=["POST"])
def signup():
    if not signups_allowed():
        return jsonify({"error": "Signups are disabled"}), 403
    data = request.get_json() or {}
    with get_db() as conn:
        if not users_exist(conn):
            return jsonify({"error": "Run setup first"}), 409
        try:
            user_id = create_user(conn, data.get("email"), data.get("password"), data.get("display_name"), "user")
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({"error": "Email already exists"}), 409
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    session["user_id"] = user_id
    return jsonify({"status": "success"})


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ? AND active = 1",
            (email,),
        ).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401
    session["user_id"] = row["id"]
    return jsonify({"status": "success"})


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "success"})
