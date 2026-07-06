import os
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

from database import init_db
from routes_plaid import plaid_bp
from routes_transactions import transactions_bp
from routes_config import config_bp

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')

# Register Blueprints
app.register_blueprint(plaid_bp)
app.register_blueprint(transactions_bp)
app.register_blueprint(config_bp)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/credentials_status')
def credentials_status():
    last_sync = "N/A"
    try:
        from database import get_db
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM sync_metadata WHERE key = 'last_sync_time'")
        row = cursor.fetchone()
        if row:
            last_sync = row[0]
        conn.close()
    except Exception as e:
        print(f"Error querying last_sync_time: {e}")
        
    return jsonify({
        "has_credentials": bool(os.getenv("PLAID_CLIENT_ID") and os.getenv("PLAID_SECRET")),
        "env": os.getenv("PLAID_ENV", "sandbox"),
        "last_sync_time": last_sync
    })

def start_scheduler():
    import threading
    import time
    from datetime import datetime, timedelta
    
    def scheduler_loop():
        print(" * Background Auto-Sync Scheduler started.")
        while True:
            now = datetime.now()
            next_run = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
            sleep_seconds = (next_run - now).total_seconds()
            
            print(f" * Next scheduled auto-sync: {next_run.strftime('%Y-%m-%d %H:%M:%S')} (sleeping {sleep_seconds:.1f}s)")
            
            target_date = next_run.date()
            while datetime.now().date() < target_date:
                time.sleep(30)
                
            print(f" * [{datetime.now().isoformat()}] Starting scheduled auto-sync...")
            try:
                from routes_plaid import perform_sync
                new_txs = perform_sync()
                print(f" * [{datetime.now().isoformat()}] Auto-sync complete. Synced {new_txs} transactions.")
            except Exception as e:
                print(f" * [{datetime.now().isoformat()}] Auto-sync failed: {e}")
                
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
