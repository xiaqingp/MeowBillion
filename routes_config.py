import json
from flask import Blueprint, request, jsonify

from database import get_db
from auth import current_user_id

config_bp = Blueprint('config', __name__)

CATEGORY_CONFIG_KEY = 'categories_config'
ANALYSIS_RULES_CONFIG_KEY = 'analysis_rules'

DEFAULT_CATEGORIES_CONFIG = {
    "categories": [
        "Internal Transfer",
        "Other",
        "Rentals",
        "Travel"
    ],
    "rules": {
        "Travel": ["Flight", "Food", "Hotel", "Other", "Transport"],
        "Rentals": ["Rent", "Mortgage", "HOA", "Management", "Maintenance", "Other"]
    }
}

DEFAULT_ANALYSIS_RULES_CONFIG = {
    "travel": {
        "category": "Travel",
        "trip_source": "note",
        "category_source": "subtype",
        "year_prefix": True,
        "fallback_year": "Note"
    },
    "rentals": {
        "category": "Rentals",
        "property_source": "note",
        "category_source": "subtype",
        "fallback_property": "Unassigned",
        "fallback_category": "Unclassified"
    }
}


def scoped_key(key, user_id=None):
    user_id = user_id or current_user_id()
    return f"{user_id}:{key}" if user_id else key


def ensure_app_config_table(conn):
    conn.execute('''
    CREATE TABLE IF NOT EXISTS app_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')


def normalize_categories_config(data):
    if not isinstance(data, dict):
        raise ValueError("Category config must be an object")
    categories = data.get('categories')
    rules = data.get('rules')
    if not isinstance(categories, list) or not isinstance(rules, dict):
        raise ValueError("Missing categories or rules in data")
    canonical_names = {
        "income": "Income"
    }
    clean_categories = []
    seen_categories = set()
    for category in categories:
        name = str(category).strip()
        if not name:
            continue
        name = canonical_names.get(name.lower(), name)
        key = name.lower()
        if key in seen_categories:
            continue
        seen_categories.add(key)
        clean_categories.append(name)
    clean_categories.sort(key=lambda category: category.lower())
    clean_rules = {}
    for category, subcategories in rules.items():
        if not isinstance(subcategories, list):
            continue
        category_name = str(category).strip()
        category_name = canonical_names.get(category_name.lower(), category_name)
        clean_rules[category_name] = [
            str(subcategory).strip()
            for subcategory in subcategories
            if str(subcategory).strip()
        ]
    return {
        "categories": clean_categories,
        "rules": clean_rules
    }


def save_categories_config_to_db(conn, data):
    normalized = normalize_categories_config(data)
    ensure_app_config_table(conn)
    conn.execute(
        """
        INSERT INTO app_config (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (scoped_key(CATEGORY_CONFIG_KEY), json.dumps(normalized, ensure_ascii=False))
    )
    conn.commit()
    return normalized


def normalize_analysis_rules_config(data):
    if not isinstance(data, dict):
        raise ValueError("Analysis rules config must be an object")
    config = json.loads(json.dumps(DEFAULT_ANALYSIS_RULES_CONFIG))
    for section, defaults in DEFAULT_ANALYSIS_RULES_CONFIG.items():
        incoming = data.get(section) if isinstance(data.get(section), dict) else {}
        for key, default_value in defaults.items():
            value = incoming.get(key, default_value)
            if isinstance(default_value, bool):
                config[section][key] = bool(value)
            else:
                config[section][key] = str(value).strip() or default_value
    return config


def save_analysis_rules_config_to_db(conn, data):
    normalized = normalize_analysis_rules_config(data)
    ensure_app_config_table(conn)
    conn.execute(
        """
        INSERT INTO app_config (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (scoped_key(ANALYSIS_RULES_CONFIG_KEY), json.dumps(normalized, ensure_ascii=False))
    )
    conn.commit()
    return normalized


def load_analysis_rules_config_from_db():
    conn = get_db()
    try:
        ensure_app_config_table(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_config WHERE key = ?", (scoped_key(ANALYSIS_RULES_CONFIG_KEY),))
        row = cursor.fetchone()
        if row:
            return normalize_analysis_rules_config(json.loads(row['value']))

        return save_analysis_rules_config_to_db(conn, DEFAULT_ANALYSIS_RULES_CONFIG)
    finally:
        conn.close()


def load_categories_config_from_db():
    conn = get_db()
    try:
        ensure_app_config_table(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_config WHERE key = ?", (scoped_key(CATEGORY_CONFIG_KEY),))
        row = cursor.fetchone()
        if row:
            return normalize_categories_config(json.loads(row['value']))

        return save_categories_config_to_db(conn, DEFAULT_CATEGORIES_CONFIG)
    finally:
        conn.close()


@config_bp.route('/api/config/categories', methods=['GET', 'POST'])
def categories_config_api():
    if request.method == 'GET':
        try:
            return jsonify(load_categories_config_from_db())
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            data = request.get_json() or {}
            conn = get_db()
            try:
                save_categories_config_to_db(conn, data)
            finally:
                conn.close()
            return jsonify({"status": "success"})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@config_bp.route('/api/config/analysis_rules', methods=['GET', 'POST'])
def analysis_rules_config_api():
    if request.method == 'GET':
        try:
            return jsonify(load_analysis_rules_config_from_db())
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    try:
        data = request.get_json() or {}
        conn = get_db()
        try:
            save_analysis_rules_config_to_db(conn, data)
        finally:
            conn.close()
        return jsonify({"status": "success"})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@config_bp.route('/api/check_duplicate', methods=['GET'])
def check_duplicate_transaction():
    try:
        merchant = request.args.get('merchant')
        date_str = request.args.get('date')
        if not merchant or not date_str:
            return jsonify({"error": "Missing merchant or date"}), 400
            
        month_prefix = date_str[:7]
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND merchant = ? AND date LIKE ?",
            (current_user_id(), merchant, f"{month_prefix}%")
        )
        count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            "exists": count > 0,
            "count": count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
