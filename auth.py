import os
import sqlite3
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Blueprint, g, jsonify, has_request_context, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db

auth_bp = Blueprint("auth", __name__)
MOBILE_SESSION_TTL_DAYS = 30


def current_user_id():
    if not has_request_context():
        return None
    return getattr(g, "mobile_user_id", None) or session.get("user_id")


def utc_now():
    return datetime.now(timezone.utc)


def issue_mobile_session(conn, user_id, device_name):
    token = secrets.token_urlsafe(48)
    now = utc_now()
    expires_at = now + timedelta(days=MOBILE_SESSION_TTL_DAYS)
    conn.execute(
        """
        INSERT INTO mobile_session_tokens
        (id, user_id, token_hash, device_name, created_at, expires_at, last_used_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid.uuid4().hex,
            user_id,
            hashlib.sha256(token.encode("utf-8")).hexdigest(),
            (device_name or "Android device").strip()[:120] or "Android device",
            now.isoformat(),
            expires_at.isoformat(),
            now.isoformat(),
        ),
    )
    return token, expires_at.isoformat()


def authenticate_mobile_token(authorization_header):
    if not authorization_header or not authorization_header.startswith("Bearer "):
        return None
    token = authorization_header.removeprefix("Bearer ").strip()
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = utc_now().isoformat()
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, user_id FROM mobile_session_tokens
            WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE mobile_session_tokens SET last_used_at = ? WHERE id = ?",
            (now, row["id"]),
        )
        conn.commit()
    return {"session_id": row["id"], "user_id": row["user_id"]}


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


@auth_bp.route("/api/auth/mobile/login", methods=["POST"])
def mobile_login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, email, display_name, role, password_hash FROM users WHERE email = ? AND active = 1",
            (email,),
        ).fetchone()
        if not row or not check_password_hash(row["password_hash"], password):
            return jsonify({"error": "Invalid email or password"}), 401
        token, expires_at = issue_mobile_session(conn, row["id"], data.get("device_name"))
        conn.commit()
    return jsonify({
        "access_token": token,
        "expires_at": expires_at,
        "user": {key: row[key] for key in ("id", "email", "display_name", "role")},
    })


@auth_bp.route("/api/auth/mobile/logout", methods=["POST"])
@login_required
def mobile_logout():
    session_id = getattr(g, "mobile_session_id", None)
    if session_id:
        with get_db() as conn:
            conn.execute(
                "UPDATE mobile_session_tokens SET revoked_at = ? WHERE id = ? AND user_id = ?",
                (utc_now().isoformat(), session_id, current_user_id()),
            )
            conn.commit()
    return jsonify({"status": "success"})


@auth_bp.route("/api/auth/mobile/sessions", methods=["GET"])
@login_required
def mobile_sessions():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, device_name, created_at, expires_at, revoked_at, last_used_at
            FROM mobile_session_tokens
            WHERE user_id = ?
            ORDER BY last_used_at DESC
            """,
            (current_user_id(),),
        ).fetchall()
    return jsonify({"sessions": [dict(row) for row in rows]})


@auth_bp.route("/api/auth/mobile/sessions/<session_id>", methods=["DELETE"])
@login_required
def revoke_mobile_session(session_id):
    with get_db() as conn:
        cursor = conn.execute(
            """
            UPDATE mobile_session_tokens
            SET revoked_at = ?
            WHERE id = ? AND user_id = ? AND revoked_at IS NULL
            """,
            (utc_now().isoformat(), session_id, current_user_id()),
        )
        conn.commit()
    if not cursor.rowcount:
        return jsonify({"error": "Session not found"}), 404
    return jsonify({"status": "success"})


@auth_bp.route("/api/auth/mobile/sessions/revoke_others", methods=["POST"])
@login_required
def revoke_other_mobile_sessions():
    current_session_id = getattr(g, "mobile_session_id", None)
    with get_db() as conn:
        cursor = conn.execute(
            """
            UPDATE mobile_session_tokens
            SET revoked_at = ?
            WHERE user_id = ? AND id != ? AND revoked_at IS NULL
            """,
            (utc_now().isoformat(), current_user_id(), current_session_id),
        )
        conn.commit()
    return jsonify({"status": "success", "revoked_count": cursor.rowcount})


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "success"})
