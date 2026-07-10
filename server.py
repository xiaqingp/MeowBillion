import os
import re
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

from database import init_db
from routes_plaid import plaid_bp
from routes_transactions import transactions_bp
from routes_config import config_bp
from routes_metadata import metadata_bp
from auth import auth_bp

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.getenv("APP_SECRET_KEY", "dev-local-change-me")

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(plaid_bp)
app.register_blueprint(transactions_bp)
app.register_blueprint(config_bp)
app.register_blueprint(metadata_bp)

DAILY_SYNC_TIME_KEY = "daily_sync_time"
DAILY_AUTO_SYNC_DATE_KEY = "daily_auto_sync_date"
DEFAULT_DAILY_SYNC_TIME = "16:00"


@app.before_request
def require_login_for_api():
    if not request.path.startswith("/api/") or request.path.startswith("/api/auth/"):
        return None
    from auth import current_user_id
    if not current_user_id():
        return jsonify({"error": "Authentication required"}), 401
    return None

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/credentials_status')
def credentials_status():
    last_sync = "N/A"
    last_attempt = "N/A"
    try:
        from database import get_db
        from auth import current_user_id
        from routes_plaid import load_user_plaid_credentials
        user_id = current_user_id()
        creds = load_user_plaid_credentials(user_id)
        conn = get_db()
        cursor = conn.cursor()
        for key, target in ((f"{user_id}:last_success_at", "success"), (f"{user_id}:last_sync_attempt_at", "attempt"), (f"{user_id}:last_sync_time", "legacy")):
            cursor.execute("SELECT value FROM sync_metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row and target == "success":
                last_sync = row[0]
            elif row and target == "attempt":
                last_attempt = row[0]
            elif row and target == "legacy" and last_sync == "N/A":
                last_sync = row[0]
        conn.close()
    except Exception as e:
        print(f"Error querying last_sync_time: {e}")
        creds = None
        
    return jsonify({
        "has_credentials": bool(creds),
        "env": (creds or {}).get("environment", "development"),
        "last_sync_time": last_sync,
        "last_success_at": last_sync,
        "last_sync_attempt_at": last_attempt
    })


def normalize_daily_sync_time(value):
    value = str(value or "").strip()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("Daily sync time must use 24-hour HH:MM format")
    return value


def load_daily_sync_time(conn):
    row = conn.execute("SELECT value FROM app_config WHERE key = ?", (DAILY_SYNC_TIME_KEY,)).fetchone()
    try:
        return normalize_daily_sync_time(row["value"] if row else DEFAULT_DAILY_SYNC_TIME)
    except ValueError:
        return DEFAULT_DAILY_SYNC_TIME


def current_user_is_admin(conn, user_id):
    row = conn.execute("SELECT role FROM users WHERE id = ? AND active = 1", (user_id,)).fetchone()
    return bool(row and row["role"] == "admin")


@app.route('/api/sync_schedule', methods=['GET', 'POST'])
def sync_schedule_api():
    from auth import current_user_id
    from database import get_db

    user_id = current_user_id()
    with get_db() as conn:
        can_edit = current_user_is_admin(conn, user_id)
        if request.method == 'POST':
            if not can_edit:
                return jsonify({"error": "Only an administrator can change the daily sync time"}), 403
            try:
                daily_sync_time = normalize_daily_sync_time((request.get_json(silent=True) or {}).get("daily_sync_time"))
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
            conn.execute(
                """
                INSERT INTO app_config (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """,
                (DAILY_SYNC_TIME_KEY, daily_sync_time),
            )
            conn.commit()
        return jsonify({"daily_sync_time": load_daily_sync_time(conn), "can_edit": can_edit})

def start_scheduler():
    import threading
    import time
    from datetime import datetime
    
    def scheduler_loop():
        print(" * Background Auto-Sync Scheduler started.")
        while True:
            try:
                from database import get_db
                from routes_plaid import perform_sync
                with get_db() as conn:
                    now = datetime.now()
                    sync_time = load_daily_sync_time(conn)
                    scheduled_at = datetime.fromisoformat(f"{now.date().isoformat()}T{sync_time}")
                    last_run = conn.execute(
                        "SELECT value FROM sync_metadata WHERE key = ?", (DAILY_AUTO_SYNC_DATE_KEY,)
                    ).fetchone()
                    should_run = now >= scheduled_at and not (last_run and last_run["value"] == now.date().isoformat())
                    users = [r["id"] for r in conn.execute("SELECT id FROM users WHERE active = 1").fetchall()] if should_run else []
                if not should_run:
                    time.sleep(30)
                    continue
                print(f" * [{datetime.now().isoformat()}] Starting scheduled auto-sync ({sync_time})...")
                total_new = 0
                for user_id in users:
                    try:
                        total_new += int((perform_sync(user_id=user_id) or {}).get("new_transactions_count") or 0)
                    except Exception as user_err:
                        print(f" * [{datetime.now().isoformat()}] Auto-sync failed for user {user_id}: {user_err}")
                with get_db() as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO sync_metadata (key, value) VALUES (?, ?)",
                        (DAILY_AUTO_SYNC_DATE_KEY, datetime.now().date().isoformat()),
                    )
                    conn.commit()
                print(f" * [{datetime.now().isoformat()}] Auto-sync complete. Synced {total_new} transactions.")
            except Exception as e:
                print(f" * [{datetime.now().isoformat()}] Auto-sync failed: {e}")
            time.sleep(30)
                
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()

if __name__ == '__main__':
    # Initialize DB (and auto-migrate columns if necessary)
    init_db()
    
    # Start auto-sync scheduler
    start_scheduler()
    
    port = os.environ.get('PORT')
    if not port:
        import socket
        test_port = 8090
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(('127.0.0.1', test_port))
                    port = test_port
                    break
                except OSError:
                    test_port += 1
        os.environ['PORT'] = str(port)
    else:
        port = int(port)

    host = os.environ.get('HOST', '127.0.0.1')
    display_host = '127.0.0.1' if host in ('0.0.0.0', '') else host
    print(f" * MeowBillion listening on: http://{display_host}:{port}")
    if host == '0.0.0.0':
        print(f" * Tailscale/LAN access: http://<your-tailscale-ip>:{port}")
    app.run(host=host, port=port, debug=True, use_reloader=False)
