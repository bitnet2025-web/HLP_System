import os
import json
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, datetime, timedelta, timezone
from collections import Counter
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

# =====================
# GLOBAL TIMEZONE CONFIG (EAT / UTC+3)
# =====================
EAT = timezone(timedelta(hours=3))

def get_eat_now():
    """Returns the current EAT datetime object."""
    return datetime.now(timezone.utc).astimezone(EAT)

def get_eat_time_str(fmt='%Y-%m-%d %H:%M'):
    """Returns a formatted EAT time string."""
    return get_eat_now().strftime(fmt)

# Neon PostgreSQL Connection String (uses Environment Variable with default fallback)
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://neondb_owner:npg_Jn1KX4zPUbTC@ep-noisy-paper-axjguij9-pooler.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require"
)
LOCAL_SQLITE = 'hlp_system.db'

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "hlp_secret_key")
import sqlite3
import os

# 1. Define DATABASE once at the top of your project
DATABASE = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database.db')

# 2. Centralized Database Helper
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn
# =====================
# NEON / POSTGRES DYNAMIC DB ADAPTER
# =====================
class DBConn:
    """Context manager handling dynamic queries across SQLite or Neon PostgreSQL."""
    def __init__(self, db_url=None):
        self.db_url = db_url or DATABASE_URL

    def __enter__(self):
        if self.db_url and self.db_url.startswith("postgres"):
            self.conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
            self.is_postgres = True
        else:
            self.conn = sqlite3.connect(LOCAL_SQLITE)
            self.conn.row_factory = sqlite3.Row
            self.is_postgres = False
        return self

    def execute(self, query, params=()):
        cursor = self.conn.cursor()
        sql_query = query
        if self.is_postgres:
            # Convert SQLite placeholders and definitions to PostgreSQL
            sql_query = sql_query.replace("?", "%s")
            sql_query = sql_query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            sql_query = sql_query.replace("PRAGMA table_info", "SELECT column_name FROM information_schema.columns WHERE table_name = ")
        
        cursor.execute(sql_query, params)
        return cursor

    def commit(self):
        self.conn.commit()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.conn.close()

# Helper function to execute queries across routes easily
def execute_query(query, params=(), fetch_all=False, fetch_one=False, commit=False):
    with DBConn() as db:
        cur = db.execute(query, params)
        res = None
        if fetch_all:
            res = cur.fetchall()
        elif fetch_one:
            res = cur.fetchone()
        if commit:
            db.commit()
        return res
def init_db():
    with get_db_connection() as conn:
        # Create ppm_assets table if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ppm_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_name TEXT NOT NULL,
                asset_section TEXT NOT NULL,
                model_serial TEXT,
                maintenance_frequency TEXT,
                next_schedule_date TEXT
            )
        """)
        
        # Create section_ppm table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS section_ppm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ppm_date TEXT,
                ppm_month TEXT,
                section_name TEXT,
                equipment_name TEXT,
                technician_name TEXT,
                work_details TEXT,
                supervisor_name TEXT DEFAULT 'Pending Signature',
                supervisor_signed_at TEXT,
                chief_engineer_name TEXT DEFAULT 'Pending Signature',
                chief_signed_at TEXT
            )
        """)
        
        # Create room_ppm table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS room_ppm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ppm_date TEXT,
                ppm_month TEXT,
                room_number TEXT,
                technician_name TEXT,
                notes TEXT,
                supervisor_name TEXT DEFAULT 'Pending Signature',
                supervisor_signed_at TEXT,
                chief_engineer_name TEXT DEFAULT 'Pending Signature',
                chief_signed_at TEXT
            )
        """)
        conn.commit()

# Run table creation on startup
init_db()
# =====================
# DATA STORAGE & DB CONFIG
# =====================
def fix_requisitions_table():
    with DBConn() as db:
        if db.is_postgres:
            # PostgreSQL schema check
            cur = db.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'requisitions';")
            columns = [row['column_name'] for row in cur.fetchall()]
        else:
            cur = db.execute("PRAGMA table_info(requisitions)")
            columns = [row[1] for row in cur.fetchall()]
        
        if 'id' not in columns and len(columns) > 0:
            print("Adding 'id' column to requisitions...")
            db.execute("ALTER TABLE requisitions RENAME TO requisitions_old")
            db.execute('''
                CREATE TABLE requisitions (
                    id SERIAL PRIMARY KEY,
                    date TEXT,
                    requester TEXT,
                    dept TEXT,
                    item TEXT,
                    qty TEXT,
                    purpose TEXT,
                    status TEXT DEFAULT 'PENDING'
                )
            ''')
            db.execute('''
                INSERT INTO requisitions (date, requester, dept, item, qty, purpose, status)
                SELECT date, requester, dept, item, qty, purpose, status FROM requisitions_old
            ''')
            db.execute("DROP TABLE requisitions_old")
            db.commit()

def fix_database_columns():
    with DBConn() as db:
        if db.is_postgres:
            cur = db.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'requisitions';")
            columns = [row['column_name'] for row in cur.fetchall()]
        else:
            cur = db.execute("PRAGMA table_info(requisitions)")
            columns = [column[1] for column in cur.fetchall()]
        
        if columns:
            if 'date_ordered' not in columns:
                db.execute("ALTER TABLE requisitions ADD COLUMN date_ordered TEXT")
            if 'date_received' not in columns:
                db.execute("ALTER TABLE requisitions ADD COLUMN date_received TEXT")
            db.commit()

def init_db():
    with DBConn() as db:
        # 1. Dynamic Asset Inventory Ledger
        db.execute("""
            CREATE TABLE IF NOT EXISTS ppm_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_section TEXT NOT NULL,       
                machine_name TEXT NOT NULL UNIQUE,  
                model_serial TEXT,
                location_details TEXT,
                next_schedule_date TEXT NOT NULL,   
                maintenance_frequency TEXT          
            );
        """)

        # 2. Major Plant & Equipment Section PPM Logs
        db.execute("""
            CREATE TABLE IF NOT EXISTS section_ppm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_name TEXT NOT NULL, 
                equipment_name TEXT NOT NULL,
                ppm_date TEXT NOT NULL,
                technician_name TEXT NOT NULL,
                supervisor_name TEXT DEFAULT 'Pending Signature',
                chief_engineer_name TEXT DEFAULT 'Pending Signature',
                supervisor_signed_at TEXT,
                chief_signed_at TEXT,
                checked_by_supervisor TEXT DEFAULT 'Pending Confirmation',
                work_details TEXT,
                status TEXT DEFAULT 'Pending Supervisor',
                ppm_month TEXT
            );
        """)

        # 3. Room-Specific PPM Ledger Table
        db.execute("""
            CREATE TABLE IF NOT EXISTS room_ppm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_number TEXT NOT NULL,
                ppm_date TEXT NOT NULL,
                technician_name TEXT NOT NULL,
                supervisor_name TEXT DEFAULT 'Pending Signature',
                chief_engineer_name TEXT DEFAULT 'Pending Signature',
                supervisor_signed_at TEXT,
                chief_signed_at TEXT,
                checked_by_supervisor TEXT DEFAULT 'Pending Confirmation',
                notes TEXT,
                status TEXT DEFAULT 'Pending Supervisor',
                ppm_month TEXT
            );
        """)

        # 4. HLP Rates Table
        db.execute('''
            CREATE TABLE IF NOT EXISTS hlp_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                elect_rate REAL DEFAULT 19.33,
                water_ncc_rate REAL DEFAULT 67.00,
                water_bh_rate REAL DEFAULT 68.00,
                lpg_rate REAL DEFAULT 113.00,
                diesel_rate REAL DEFAULT 222.00,
                updated_at TEXT
            )
        ''')
        
        cursor = db.execute('SELECT COUNT(*) as cnt FROM hlp_rates')
        row = cursor.fetchone()
        cnt = row['cnt'] if isinstance(row, dict) else row[0]
        if cnt == 0:
            current_now = get_eat_time_str('%Y-%m-%d %H:%M:%S')
            db.execute('''
                INSERT INTO hlp_rates (elect_rate, water_ncc_rate, water_bh_rate, lpg_rate, diesel_rate, updated_at)
                VALUES (19.33, 67.00, 68.00, 113.00, 222.00, ?)
            ''', (current_now,))

        # 5. HLP Calculator Logs Table
        db.execute('''
            CREATE TABLE IF NOT EXISTS hlp_calculator_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                elect_units REAL, elect_rate REAL, elect_cost REAL,
                water_ncc_units REAL, water_ncc_rate REAL, water_ncc_cost REAL,
                water_bh_units REAL, water_bh_rate REAL, water_bh_cost REAL,
                lpg_pct REAL, lpg_scm REAL, lpg_rate REAL, lpg_cost REAL,
                diesel_units REAL, diesel_rate REAL, diesel_cost REAL,
                total_cost REAL,
                created_by TEXT,
                created_at TEXT
            )
        ''')

        # 6. Shift Handovers Table
        db.execute("""
            CREATE TABLE IF NOT EXISTS shift_handovers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section TEXT NOT NULL,
                technician_name TEXT NOT NULL,
                handover_text TEXT NOT NULL,
                report_date TEXT NOT NULL,
                status TEXT DEFAULT 'Pending Handover',
                resolved_by TEXT,
                resolved_at TEXT
            );
        """)

        # 7. HLP Core Readings & System Tables
        db.execute('''
            CREATE TABLE IF NOT EXISTS hlp_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reading_date TEXT,
                section TEXT,
                parameter TEXT,
                time_slot TEXT,
                value TEXT,
                UNIQUE(reading_date, section, parameter)
            )
        ''')
        
        db.execute('''
            CREATE TABLE IF NOT EXISTS requisitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, requester TEXT, dept TEXT, item TEXT, qty TEXT, purpose TEXT, status TEXT
            )
        ''')
        
        db.execute('''
            CREATE TABLE IF NOT EXISTS fuel_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT, fuel_type TEXT, quantity REAL, reference_no TEXT, received_by TEXT
            )
        ''')
        
        db.execute('''
            CREATE TABLE IF NOT EXISTS report_signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT,
                role TEXT,
                user_name TEXT,
                signed_at TEXT,
                UNIQUE(report_date, role)
            )
        ''')
        
        db.execute("""
            CREATE TABLE IF NOT EXISTS daily_report_status (
                report_date TEXT PRIMARY KEY,
                status TEXT DEFAULT 'Pending Supervisor', 
                submitted_by TEXT,
                submitted_at TEXT,
                approved_by TEXT,
                approved_at TEXT,
                updated_at TEXT
            )
        """)

        # SAFE DATABASE MIGRATION UPGRADE PATCHES
        missing_columns = [
            ("section_ppm", "supervisor_name", "TEXT DEFAULT 'Pending Signature'"),
            ("section_ppm", "chief_engineer_name", "TEXT DEFAULT 'Pending Signature'"),
            ("section_ppm", "supervisor_signed_at", "TEXT"),
            ("section_ppm", "chief_signed_at", "TEXT"),
            ("section_ppm", "ppm_month", "TEXT"),
            ("room_ppm", "supervisor_name", "TEXT DEFAULT 'Pending Signature'"),
            ("room_ppm", "chief_engineer_name", "TEXT DEFAULT 'Pending Signature'"),
            ("room_ppm", "supervisor_signed_at", "TEXT"),
            ("room_ppm", "chief_signed_at", "TEXT"),
            ("room_ppm", "ppm_month", "TEXT"),
            ("daily_report_status", "updated_at", "TEXT")
        ]

        for table, column, col_type in missing_columns:
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type};")
            except Exception:
                pass

        db.commit()

# Run migrations and setup safely
try:
    fix_requisitions_table()
    fix_database_columns()
    init_db()
except Exception as e:
    print(f"Database setup error: {e}")

# =====================
# USER HANDLING
# =====================
USERS_FILE = os.path.join(app.root_path, 'users.json')

DEFAULT_USERS = {
    "admin": {
        "password": os.environ.get("ADMIN_PASSWORD", "admin123"),
        "role": "ADMIN",
        "section": "ALL"
    },
    "supervisor": {
        "password": os.environ.get("SUPERVISOR_PASSWORD", "super123"),
        "role": "SUPERVISOR",
        "section": "ALL"
    },
    "technician": {
        "password": os.environ.get("TECH_PASSWORD", "123"),
        "role": "TECHNICIAN",
        "section": "ALL"
    }
}

def load_users():
    """Load users from users.json, falling back to defaults if file is missing/corrupted."""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            app.logger.error(f"Error loading users.json: {e}")
            return DEFAULT_USERS
    return DEFAULT_USERS

def save_users(users_data):
    """Write current users dictionary back to users.json."""
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, indent=4)
        return True
    except Exception as e:
        app.logger.error(f"Error saving users.json: {e}")
        return False

# Initialize USERS dictionary
USERS = load_users()

READINGS = {
    "drafts": [],
    "confirmed": [],
    "rates": {
        "electricity": 19.33, "ncc": 67.0, "borehole": 68.0, 
        "lpg_rate": 18.5, "lpg_scm": 113.0, "diesel": 160.0,
    }
}

def get_current_month_str():
    return datetime.now().strftime("%Y-%m")

def init_db_migration():
    """Populate default values for migrated columns"""
    current_m = get_current_month_str()
    try:
        with DBConn() as db:
            db.execute("UPDATE section_ppm SET ppm_month = ? WHERE ppm_month IS NULL OR ppm_month = ''", (current_m,))
            db.execute("UPDATE room_ppm SET ppm_month = ? WHERE ppm_month IS NULL OR ppm_month = ''", (current_m,))
            db.commit()
    except Exception as e:
        print(f"Migration patch failed: {e}")

init_db_migration()

# =====================
# AUTHENTICATION
# =====================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session: 
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_role = str(session.get("role", "")).upper()
            allowed_roles = [r.upper() for r in roles]
            if user_role not in allowed_roles:
                flash(f"Unauthorized: {user_role} access denied.")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# =====================
# SYSTEM UTILITY HELPERS
# =====================
def get_unified_readings_for_date(target_date):
    readings_dict = {}
    alt_date = ""
    if target_date and "-" in target_date:
        p = target_date.split("-")
        if len(p) == 3:
            alt_date = f"{p[2]}/{p[1]}/{p[0]}"
    
    try:
        with DBConn() as db:
            cursor = db.execute(
                "SELECT parameter, value FROM hlp_readings WHERE reading_date = ? OR reading_date = ?", 
                (target_date, alt_date)
            )
            for row in cursor.fetchall():
                param = str(row['parameter']).strip()
                val = row['value']
                
                if val is None or str(val).strip() == "":
                    continue
                
                clean_key = param
                if clean_key.lower().startswith("f_plumbing_"):
                    clean_key = "f_" + clean_key[11:]
                
                readings_dict[clean_key] = val
                readings_dict[param] = val
                readings_dict[param.replace(":", "")] = val
                readings_dict[param.replace(" ", "_").lower().replace(":", "")] = val
    except Exception as e:
        print(f"CRITICAL ENGINE FETCH ERROR: {e}")
        
    return readings_dict

def calculate_hlp_costs(unified_data):
    rates = READINGS["rates"]
    def gv(k): 
        return unified_data.get(k, unified_data.get(k.replace(":","").replace("_",""), 0))
    try:
        elec_units = max(0, float(gv('f_kwh_00:00')) - float(gv('f_kwh_06:00')))
        water_units = max(0, float(gv('f_flow_ncc_23:59')) - float(gv('f_flow_ncc_00:00')))
        lpg_used = float(gv('f_lpg_consumed'))
    except (ValueError, TypeError):
        elec_units = water_units = lpg_used = 0

    costs = {
        "elec_units": elec_units, "elec_total": elec_units * rates["electricity"],
        "water_units": water_units, "water_total": water_units * rates["ncc"],
        "lpg_total": (lpg_used * rates["lpg_rate"]) * rates["lpg_scm"]
    }
    costs["grand_total"] = costs["elec_total"] + costs["water_total"] + costs["lpg_total"]
    return costs
# =====================
# SYSTEM ROUTES
# =====================

from flask import send_from_directory
# In your Flask app.py / routes file
from flask import send_from_directory
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session



@app.route('/sw.js')
@app.route('/service-worker.js')
def serve_sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").lower().strip()
        password = request.form.get("password", "").strip()

        # Reload USERS to ensure fresh data
        current_users = load_users()

        if username in current_users and current_users[username].get("password") == password:
            session.clear()
            session["user"] = username
            session["role"] = current_users[username].get("role", "TECHNICIAN").upper()
            session["section"] = current_users[username].get("section", "ALL").upper()

            return redirect(url_for("dashboard"))

        flash("Invalid credentials", "danger")
    return render_template("login.html")
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    time_range = request.args.get("range", "monthly")
    current_month = datetime.now().strftime("%B %Y")

    bar_labels = ["General", "Plant", "Kitchen", "Laundry", "Building"]
    machinery_dept_completed = [0, 0, 0, 0, 0]
    machinery_dept_pending = [0, 0, 0, 0, 0]
    requisition_dept_costs = [0.0, 0.0, 0.0, 0.0, 0.0]

    machinery_completed = 0
    machinery_pending = 0
    room_completed = 0
    room_pending = 0

    return render_template(
        "dashboard.html",
        role=session.get("role", "TECHNICIAN"),
        user=session.get("user", "User"),
        current_month=current_month,
        time_range=time_range,
        machinery_completed=machinery_completed,
        machinery_pending=machinery_pending,
        room_completed=room_completed,
        room_pending=room_pending,
        bar_labels=bar_labels,
        machinery_dept_completed=machinery_dept_completed,
        machinery_dept_pending=machinery_dept_pending,
        requisition_dept_costs=requisition_dept_costs
    )
@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    # Verify Admin or Supervisor Role
    user_role = session.get("role", "").upper()
    if user_role not in ["ADMIN", "SUPERVISOR"]:
        flash("Access denied. Admin or Supervisor privileges required.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        action = request.form.get("action")

        # 1. HANDLE RATE UPDATE
        if action == "update_rates":
            if "rates" not in READINGS:
                READINGS["rates"] = {}

            READINGS["rates"].update({
                "electricity": float(request.form.get("elec_rate", 19.33)),
                "ncc": float(request.form.get("ncc_rate", 67.0)),
                "borehole": float(request.form.get("borehole_rate", 68.0)),
                "diesel": float(request.form.get("diesel_rate", 160.0)),
                "lpg": float(request.form.get("lpg_rate", 18.5))
            })
            flash("Global rates updated successfully!", "success")
            return redirect(url_for("admin"))

        # 2. HANDLE PASSWORD RESET
        elif action == "reset_password":
            target_user = request.form.get("target_user", "").lower().strip()
            new_password = request.form.get("new_password", "").strip()

            if not new_password:
                flash("Password cannot be empty.", "warning")
            elif target_user in USERS:
                USERS[target_user]["password"] = new_password
                
                # Save changes permanently to users.json
                if save_users(USERS):
                    flash(f"Password updated and saved permanently for '{target_user}'!", "success")
                else:
                    flash("Password updated in session, but failed to write to file.", "warning")
            else:
                flash(f"User '{target_user}' not found in system.", "danger")
            
            return redirect(url_for("admin"))

    # GET REQUEST LOGIC
    current_rates = READINGS.get("rates", {
        "electricity": 19.33,
        "ncc": 67.0,
        "borehole": 68.0,
        "diesel": 160.0,
        "lpg": 18.5
    })
    return render_template("admin.html", rates=current_rates)
# =====================
# REQUISITIONS SYSTEM
# =====================
@app.route("/approve_requisition/<int:id>", methods=["POST"])
@login_required
@role_required("SUPERVISOR", "ADMIN")
def approve_requisition(id):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("UPDATE requisitions SET status = 'APPROVED' WHERE id = ?", (id,))
    flash("Requisition approved!")
    return redirect(url_for('material_requisition'))

# --- 3. REJECT REQUISITION ---
@app.route('/reject_requisition/<int:id>', methods=['POST'])
def reject_requisition(id):
    db = sqlite3.connect('hlp_database.db')
    cursor = db.cursor()
    cursor.execute("""
        UPDATE requisitions 
        SET status = 'REJECTED' 
        WHERE id = ?
    """, (id,))
    db.commit()
    db.close()
    return redirect(url_for('material_requisition'))

# --- 1. MARK REQUISITION AS ORDERED ---
@app.route('/order_requisition/<int:id>', methods=['POST'])
def order_requisition(id):
    import datetime
    order_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    db = sqlite3.connect('hlp_database.db')
    cursor = db.cursor()
    cursor.execute("""
        UPDATE requisitions 
        SET status = 'ORDERED', date_ordered = ? 
        WHERE id = ?
    """, (order_date, id))
    db.commit()
    db.close()
    return redirect(url_for('material_requisition'))

# --- 2. CONFIRM MATERIAL RECEIPT ---
@app.route('/receive_requisition/<int:id>', methods=['POST'])
def receive_requisition(id):
    import datetime
    receive_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    db = sqlite3.connect('hlp_database.db')
    cursor = db.cursor()
    cursor.execute("""
        UPDATE requisitions 
        SET status = 'RECEIVED', date_received = ? 
        WHERE id = ?
    """, (receive_date, id))
    db.commit()
    db.close()
    return redirect(url_for('material_requisition'))

from flask import render_template, request, session, url_for, redirect
import sqlite3
import datetime # Safe top-level import

@app.route('/material_requisition', methods=['GET', 'POST'])
def material_requisition():
    # --- POST REQUEST: HANDLE FORM SUBMISSIONS ---
    if request.method == 'POST':
        requester = request.form.get('technician_name', 'Unknown')
        item = request.form.get('item')
        qty = request.form.get('qty')
        purpose = request.form.get('purpose')
        dept = session.get('department', 'Engineering')
        
        # Fixed datetime invocation syntax
        current_date = current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        db = sqlite3.connect('hlp_database.db')
        cursor = db.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requisitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                requester TEXT,
                dept TEXT,
                item TEXT,
                qty TEXT,
                purpose TEXT,
                status TEXT DEFAULT 'PENDING',
                date_ordered TEXT,
                date_received TEXT
            )
        """)
        
        cursor.execute("""
            INSERT INTO requisitions (date, requester, dept, item, qty, purpose, status)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING')
        """, (current_date, requester, dept, item, qty, purpose))
        db.commit()
        db.close()
        return redirect(url_for('material_requisition'))

    # --- GET REQUEST: FILTERS, LEDGER, & GRAPH INGESTION ---
    selected_month = request.args.get('month', '')
    selected_year = request.args.get('year', '2026')

    db = sqlite3.connect('hlp_database.db')
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requisitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            requester TEXT,
            dept TEXT,
            item TEXT,
            qty TEXT,
            purpose TEXT,
            status TEXT DEFAULT 'PENDING',
            date_ordered TEXT,
            date_received TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fuel_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fuel_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            received_by TEXT,
            date TEXT
        )
    """)
    db.commit()

    cursor.execute("SELECT * FROM fuel_logs ORDER BY id DESC LIMIT 10")
    fuel_history = cursor.fetchall()

    cursor.execute("SELECT * FROM requisitions ORDER BY id DESC")
    requisitions = cursor.fetchall()

    query = """
        SELECT 
            TRIM(LOWER(item)) as item_name, 
            COUNT(id) as order_frequency,
            SUM(CASE WHEN UPPER(status) = 'RECEIVED' THEN CAST(qty AS REAL) ELSE 0 END) as total_received
        FROM requisitions
        WHERE 1=1
    """
    params = []
    
    if selected_month:
        query += " AND date LIKE ?"
        params.append(f"%-{selected_month}-%")
    if selected_year:
        query += " AND date LIKE ?"
        params.append(f"%{selected_year}%")
        
    query += " GROUP BY LOWER(item) ORDER BY order_frequency DESC LIMIT 10"
    
    cursor.execute(query, params)
    chart_data = cursor.fetchall()
    db.close()

    chart_labels = [row['item_name'].title() for row in chart_data]
    chart_frequencies = [row['order_frequency'] for row in chart_data]
    chart_received_qtys = [row['total_received'] for row in chart_data]

    return render_template(
        'requisitions.html',
        requisitions=requisitions,
        fuel_history=fuel_history,
        selected_month=selected_month,
        selected_year=selected_year,
        chart_labels=chart_labels,
        chart_frequencies=chart_frequencies,
        chart_received_qtys=chart_received_qtys
    )
@app.route("/update_rates", methods=["POST"])
@login_required
def update_rates():
    # Verify admin role safely (handles case differences)
    if session.get("role", "").upper() != "ADMIN":
        flash("Access denied. Admin privileges required.", "danger")
        return redirect(url_for("dashboard"))

    # Extract rates from form submission
    electricity = request.form.get("electricity")
    ncc = request.form.get("ncc")
    borehole = request.form.get("borehole")
    lpg_rate = request.form.get("lpg_rate")
    lpg_scm = request.form.get("lpg_scm")
    diesel = request.form.get("diesel")

    # Update in-memory dictionary or database
    if "rates" not in READINGS:
        READINGS["rates"] = {}

    READINGS["rates"].update({
        "electricity": float(electricity) if electricity else 19.33,
        "ncc": float(ncc) if ncc else 67.0,
        "borehole": float(borehole) if borehole else 68.0,
        "lpg_rate": float(lpg_rate) if lpg_rate else 18.5,
        "lpg_scm": float(lpg_scm) if lpg_scm else 113.0,
        "diesel": float(diesel) if diesel else 160.0
    })

    flash("Utility rates updated successfully!", "success")
    # Redirecting prevents the blank page
    return redirect(url_for("dash_admin"))

@app.route("/admin/archives")
@login_required
@role_required("ADMIN", "SUPERVISOR", "ELECTRICAL", "PLUMBING", "HVAC")
def confirmed_readings_view():
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT DISTINCT reading_date FROM hlp_readings ORDER BY reading_date DESC"
        archives = conn.execute(query).fetchall()
    return render_template("archives.html", archives=archives)

@app.route("/dashboard/<section>")
@login_required
def section_dashboard(section):
    context = {"section": section, "values": {}, "mode": "edit", "today_date": date.today().strftime("%Y-%m-%d")}
    return render_template(f"{section}_dashboard.html", **context)


# ========================================================
# CORE ROUTE: SUPERVISOR UNIFIED MASTER DASHBOARD
# ========================================================

from flask import render_template, request, redirect, url_for, flash, session

# In-memory storage structure for HLP records
HLP_RECORDS = []

@app.route("/hlp-calculator", methods=["GET"])
def hlp_calculator():
    rates = READINGS.get("rates", {
        "elect": 19.33,
        "water_ncc": 67.00,
        "water_bh": 68.00,
        "lpg": 113.00,
        "diesel": 222.00
    })
    
    # Filter active (non-archived) records
    active_records = [r for r in HLP_RECORDS if not r.get("archived", False)]
    
    return render_template("hlp_calculator.html", rates=rates, records=active_records)


@app.route("/save-hlp-report", methods=["POST"])
def save_hlp_report():
    report_date = request.form.get("report_date")
    
    # Calculate costs
    elect_units = float(request.form.get("elect_units") or 0)
    elect_rate = float(request.form.get("elect_rate") or 0)
    elect_cost = elect_units * elect_rate

    water_ncc_units = float(request.form.get("water_ncc_units") or 0)
    water_ncc_rate = float(request.form.get("water_ncc_rate") or 0)
    water_ncc_cost = water_ncc_units * water_ncc_rate

    water_bh_units = float(request.form.get("water_bh_units") or 0)
    water_bh_rate = float(request.form.get("water_bh_rate") or 0)
    water_bh_cost = water_bh_units * water_bh_rate

    lpg_pct = float(request.form.get("lpg_pct") or 0)
    lpg_scm = lpg_pct * 18.5
    lpg_rate = float(request.form.get("lpg_rate") or 0)
    lpg_cost = lpg_scm * lpg_rate

    diesel_units = float(request.form.get("diesel_units") or 0)
    diesel_rate = float(request.form.get("diesel_rate") or 0)
    diesel_cost = diesel_units * diesel_rate

    total_cost = elect_cost + water_ncc_cost + water_bh_cost + lpg_cost + diesel_cost

    record = {
        "id": len(HLP_RECORDS) + 1,
        "date": report_date,
        "elect_units": elect_units,
        "elect_cost": elect_cost,
        "water_ncc_units": water_ncc_units,
        "water_ncc_cost": water_ncc_cost,
        "water_bh_units": water_bh_units,
        "water_bh_cost": water_bh_cost,
        "lpg_pct": lpg_pct,
        "lpg_cost": lpg_cost,
        "diesel_units": diesel_units,
        "diesel_cost": diesel_cost,
        "total_cost": total_cost,
        "archived": False
    }

    HLP_RECORDS.insert(0, record)  # Add new record at the top
    flash("HLP Report saved successfully!", "success")
    return redirect(url_for("hlp_calculator"))


@app.route("/archive-hlp-report/<int:record_id>", methods=["POST"])
def archive_hlp_report(record_id):
    for record in HLP_RECORDS:
        if record["id"] == record_id:
            record["archived"] = True
            flash(f"Record for {record['date']} archived successfully.", "info")
            break
    return redirect(url_for("hlp_calculator"))



from datetime import datetime, timedelta

from flask import render_template, request, redirect, url_for, flash, session
import sqlite3

def get_db_connection():
    conn = sqlite3.connect('hlp_database.db')  # Use your existing DB file name
    conn.row_factory = sqlite3.Row
    return conn


# 3. ADMIN RATE ADJUSTMENT ROUTE
@app.route('/update-hlp-rates', methods=['POST'])
def update_hlp_rates():
    if session.get('role') != 'admin':
        flash("Unauthorized: Only Admins can update rates.", "danger")
        return redirect(url_for('hlp_calculator'))
        
    elect_rate = float(request.form.get('elect_rate'))
    water_ncc_rate = float(request.form.get('water_ncc_rate'))
    water_bh_rate = float(request.form.get('water_bh_rate'))
    lpg_rate = float(request.form.get('lpg_rate'))
    diesel_rate = float(request.form.get('diesel_rate'))

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO hlp_rates (elect_rate, water_ncc_rate, water_bh_rate, lpg_rate, diesel_rate)
        VALUES (?, ?, ?, ?, ?)
    ''', (elect_rate, water_ncc_rate, water_bh_rate, lpg_rate, diesel_rate))
    conn.commit()
    conn.close()

    flash("HLP Base Rates updated successfully!", "success")
    return redirect(url_for('hlp_calculator'))

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo  # Standard library in Python 3.9+
from flask import request, session, redirect, url_for, render_template, flash

# Define local timezone (East Africa Time: UTC+3)
LOCAL_TZ = ZoneInfo("Africa/Nairobi")

@app.route('/ppm', endpoint='ppm')
@app.route("/ppm_hub", methods=["GET", "POST"])
@login_required
def ppm_hub():
    user_role = (session.get("role") or session.get("user_role") or "").upper()
    
    # 1. Fetch current time in East Africa Time (EAT)
    now_eat = datetime.now(LOCAL_TZ)
    today_str = now_eat.strftime("%Y-%m-%d %H:%M")
    month_prefix = now_eat.strftime("%Y-%m")
    
    # Fallback if get_current_month_str() is not globally available
    try:
        current_month = get_current_month_str()
    except NameError:
        current_month = now_eat.strftime("%B %Y")
    
    search_room = request.args.get("search_room", "").strip()

    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        
        # --- POST REQUESTS: HANDLING FORM SUBMISSIONS ---
        if request.method == "POST":
            form_type = request.form.get("form_type")
            
            if form_type == "register_asset":
                machine_name = request.form.get("machine_name", "").strip()
                asset_section = request.form.get("asset_section", "").strip().upper()
                model_serial = request.form.get("model_serial", "").strip()
                maintenance_frequency = request.form.get("maintenance_frequency", "").strip()
                next_schedule_date = request.form.get("next_schedule_date", "").strip()
                
                if machine_name and asset_section:
                    conn.execute("""
                        INSERT INTO ppm_assets (machine_name, asset_section, model_serial, maintenance_frequency, next_schedule_date)
                        VALUES (?, ?, ?, ?, ?)
                    """, (machine_name, asset_section, model_serial, maintenance_frequency, next_schedule_date))
                    flash(f"Asset '{machine_name}' registered successfully!", "success")
                else:
                    flash("Failed to register asset. Machine name and section are required.", "danger")
                
            elif form_type == "log_section_ppm":
                equipment_name = request.form.get("equipment_name", "").strip()
                technician_name = request.form.get("technician_name", "").strip()
                work_details = request.form.get("work_details", "").strip()
                update_next_date = request.form.get("update_next_date", "").strip()

                # Look up section_name directly from ppm_assets OR read from form field
                section_name = request.form.get("section_name", "").strip().upper()
                if not section_name:
                    asset = conn.execute(
                        "SELECT asset_section FROM ppm_assets WHERE machine_name = ?", 
                        (equipment_name,)
                    ).fetchone()
                    section_name = asset["asset_section"].upper() if asset and asset["asset_section"] else "GENERAL"

                # Insert into section_ppm WITH local EAT section_name and timestamps
                conn.execute("""
                    INSERT INTO section_ppm (
                        ppm_date, ppm_month, section_name, equipment_name, 
                        technician_name, work_details, supervisor_name, chief_engineer_name
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'Pending Signature', 'Pending Signature')
                """, (
                    today_str, 
                    current_month, 
                    section_name, 
                    equipment_name, 
                    technician_name, 
                    work_details
                ))
                
                # Update Asset Next Schedule Date if provided
                if update_next_date:
                    conn.execute(
                        "UPDATE ppm_assets SET next_schedule_date = ? WHERE machine_name = ?", 
                        (update_next_date, equipment_name)
                    )
                flash(f"PPM record logged for {equipment_name}.", "success")
                
            elif form_type == "log_room_ppm":
                room_number = request.form.get("room_number", "").strip()
                technician_name = request.form.get("technician_name", "").strip()
                notes = request.form.get("notes", "").strip()

                if room_number:
                    conn.execute("""
                        INSERT INTO room_ppm (
                            ppm_date, ppm_month, room_number, technician_name, 
                            notes, supervisor_name, chief_engineer_name
                        )
                        VALUES (?, ?, ?, ?, ?, 'Pending Signature', 'Pending Signature')
                    """, (
                        today_str, 
                        current_month, 
                        room_number, 
                        technician_name, 
                        notes
                    ))
                    flash(f"PPM record logged for Room {room_number}.", "success")
                else:
                    flash("Room number is required.", "danger")
                
            conn.commit()
            return redirect(url_for("ppm_hub"))

        # --- GET REQUESTS: RENDER LOG MODULES ---
        
        # 1. Fetch Registered Assets & Schedule Alerts
        assets = conn.execute("SELECT * FROM ppm_assets ORDER BY machine_name ASC").fetchall()
        alerts = conn.execute("SELECT * FROM ppm_assets WHERE next_schedule_date <= ?", (today_str,)).fetchall()
        
        # 2. Master Schedules Grouping by Section
        schedules_by_field = {}
        for section in ["ELECTRICAL", "PLUMBING", "HVAC", "KITCHEN", "LAUNDRY", "BOILER"]:
            schedules_by_field[section] = conn.execute(
                "SELECT * FROM ppm_assets WHERE UPPER(asset_section) = ?", 
                (section,)
            ).fetchall()

        # 3. Active Serviced Logs for Current Month
        raw_serviced_logs = conn.execute("""
            SELECT s.*, COALESCE(s.section_name, a.asset_section, 'GENERAL') as resolved_section 
            FROM section_ppm s
            LEFT JOIN ppm_assets a ON s.equipment_name = a.machine_name
            WHERE s.ppm_month = ? 
               OR s.ppm_date LIKE ? 
               OR s.ppm_date LIKE ?
            ORDER BY s.id DESC
        """, (current_month, f"{current_month}%", f"{month_prefix}%")).fetchall()

        # Pre-populate default sections dictionary
        ledgers = {s: [] for s in ["ELECTRICAL", "PLUMBING", "HVAC", "KITCHEN", "LAUNDRY", "BOILER"]}

        # Group records dynamically
        for log in raw_serviced_logs:
            sec = (log["resolved_section"] or "GENERAL").upper()
            if sec not in ledgers:
                ledgers[sec] = []
            ledgers[sec].append(log)

        # 4. Room PPM Query
        if search_room:
            rooms = conn.execute("""
                SELECT * FROM room_ppm 
                WHERE (ppm_month = ? OR ppm_date LIKE ? OR ppm_date LIKE ?) 
                  AND room_number LIKE ? 
                ORDER BY id DESC
            """, (current_month, f"{current_month}%", f"{month_prefix}%", f"%{search_room}%")).fetchall()
        else:
            rooms = conn.execute("""
                SELECT * FROM room_ppm 
                WHERE (ppm_month = ? OR ppm_date LIKE ? OR ppm_date LIKE ?) 
                ORDER BY id DESC
            """, (current_month, f"{current_month}%", f"{month_prefix}%")).fetchall()

        # 5. Archive Engine: Historical Months Data
        past_section_months = conn.execute(
            "SELECT DISTINCT ppm_month FROM section_ppm WHERE ppm_month != ? AND ppm_month IS NOT NULL ORDER BY ppm_month DESC", 
            (current_month,)
        ).fetchall()
        
        past_room_months = conn.execute(
            "SELECT DISTINCT ppm_month FROM room_ppm WHERE ppm_month != ? AND ppm_month IS NOT NULL ORDER BY ppm_month DESC", 
            (current_month,)
        ).fetchall()
        
        # Consolidate distinct historical months
        all_archive_months = sorted(
            list(set([m["ppm_month"] for m in past_section_months if m["ppm_month"]] + 
                     [m["ppm_month"] for m in past_room_months if m["ppm_month"]])), 
            reverse=True
        )
        
        # Compile archive datasets
        archived_data = {}
        for month in all_archive_months:
            archived_data[month] = {
                "machinery": conn.execute("""
                    SELECT s.*, COALESCE(s.section_name, a.asset_section, 'GENERAL') as asset_section 
                    FROM section_ppm s 
                    LEFT JOIN ppm_assets a ON s.equipment_name = a.machine_name 
                    WHERE s.ppm_month = ? 
                    ORDER BY s.id DESC
                """, (month,)).fetchall(),
                "rooms": conn.execute(
                    "SELECT * FROM room_ppm WHERE ppm_month = ? ORDER BY id DESC", 
                    (month,)
                ).fetchall()
            }

    return render_template(
        "ppm_hub.html", 
        today_str=today_str, 
        user_role=user_role, 
        assets=assets, 
        alerts=alerts,
        schedules_by_field=schedules_by_field, 
        ledgers=ledgers, 
        rooms=rooms, 
        search_room=search_room,
        archived_data=archived_data
    )


@app.route('/verify_ppm_action/<action_role>/<table_type>/<int:record_id>', methods=['POST'])
@login_required
def verify_ppm_action(action_role, table_type, record_id):
    # Retrieve user details from session gracefully
    approver_name = (
        session.get('user_name') or 
        session.get('username') or 
        session.get('name') or 
        ('Chief Engineer' if action_role == 'admin' else 'Supervisor')
    )

    # Correct time to local Nairobi/EAT time
    current_time = datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M')

    with sqlite3.connect(DATABASE) as conn:
        if table_type == 'section':
            if action_role == 'supervisor':
                conn.execute(
                    "UPDATE section_ppm SET supervisor_name = ?, supervisor_signed_at = ? WHERE id = ?",
                    (approver_name, current_time, record_id)
                )
            elif action_role == 'admin':
                conn.execute(
                    "UPDATE section_ppm SET chief_engineer_name = ?, chief_signed_at = ? WHERE id = ?",
                    (approver_name, current_time, record_id)
                )
        elif table_type == 'room':
            if action_role == 'supervisor':
                conn.execute(
                    "UPDATE room_ppm SET supervisor_name = ?, supervisor_signed_at = ? WHERE id = ?",
                    (approver_name, current_time, record_id)
                )
            elif action_role == 'admin':
                conn.execute(
                    "UPDATE room_ppm SET chief_engineer_name = ?, chief_signed_at = ? WHERE id = ?",
                    (approver_name, current_time, record_id)
                )
        conn.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True,
            'status': 'success',
            'approver': approver_name,
            'timestamp': current_time
        })

    # Preserve scroll position by returning to the modified row
    return redirect(url_for('ppm_hub', _anchor=f"row-{table_type}-{record_id}"))


@app.route('/delete_ppm_entry/<table_type>/<int:record_id>', methods=['POST'])
@login_required
def delete_ppm_entry(table_type, record_id):
    try:
        with sqlite3.connect(DATABASE) as conn:
            if table_type == 'section':
                conn.execute("DELETE FROM section_ppm WHERE id = ?", (record_id,))
            elif table_type == 'room':
                conn.execute("DELETE FROM room_ppm WHERE id = ?", (record_id,))
            conn.commit()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': True, 'message': 'Entry deleted'})

        return redirect(url_for('ppm_hub'))
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'message': str(e)}), 400
        return redirect(url_for('ppm_hub'))


@app.route('/edit_ppm_entry/<table_type>/<int:record_id>', methods=['POST'])
@login_required
def edit_ppm_entry(table_type, record_id):
    technician_name = request.form.get('technician_name', '').strip()
    target_name = request.form.get('target_name', '').strip()
    work_details = request.form.get('work_details', '').strip()

    with sqlite3.connect(DATABASE) as conn:
        if table_type == 'section':
            conn.execute("""
                UPDATE section_ppm 
                SET technician_name = ?, equipment_name = ?, work_details = ? 
                WHERE id = ?
            """, (technician_name, target_name, work_details, record_id))
        elif table_type == 'room':
            conn.execute("""
                UPDATE room_ppm 
                SET technician_name = ?, room_number = ?, notes = ? 
                WHERE id = ?
            """, (technician_name, target_name, work_details, record_id))
        conn.commit()

    return redirect(url_for('ppm_hub', _anchor=f"row-{table_type}-{record_id}"))
@app.route("/engineering/dashboard", methods=["GET"])
@login_required
def engineering_dashboard():
    # 1. Determine Time Frame Filters
    time_range = request.args.get("range", "monthly") # Default to current month
    current_date = datetime.now()
    
    # Calculate months needed based on selection
    months_list = []
    if time_range == "semiannual":
        # Past 6 months
        for i in range(6):
            d = current_date - datetime.timedelta(days=i*30)
            months_list.append(d.strftime("%Y-%m"))
    elif time_range == "annual":
        # Past 12 months
        for i in range(12):
            d = current_date - datetime.timedelta(days=i*30)
            months_list.append(d.strftime("%Y-%m"))
    else:
        # Default: Just current month
        months_list.append(current_date.strftime("%Y-%m"))
        
    # Format placeholders for SQL IN clauses (?, ?, ?)
    placeholders = ",".join(["?"] * len(months_list))

    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        
        # ----------------------------------------------------
        # SECTION A: MACHINERY (FIELDS) PPM AGGREGATIONS
        # ----------------------------------------------------
        comp_sect = conn.execute(f"""
            SELECT COUNT(*) FROM section_ppm WHERE ppm_month IN ({placeholders}) AND status = 'Approved'
        """, months_list).fetchone()[0] or 0
        
        pend_sect = conn.execute(f"""
            SELECT COUNT(*) FROM section_ppm WHERE ppm_month IN ({placeholders}) AND (status != 'Approved' OR status IS NULL)
        """, months_list).fetchone()[0] or 0

        departments = ["ELECTRICAL", "PLUMBING", "HVAC", "KITCHEN", "LAUNDRY", "BOILER"]
        dept_comp = []
        dept_pend = []
        for dept in departments:
            c = conn.execute(f"""
                SELECT COUNT(s.id) FROM section_ppm s JOIN ppm_assets a ON s.equipment_name = a.machine_name
                WHERE a.asset_section = ? AND s.ppm_month IN ({placeholders}) AND s.status = 'Approved'
            """, [dept] + months_list).fetchone()[0] or 0
            p = conn.execute(f"""
                SELECT COUNT(s.id) FROM section_ppm s JOIN ppm_assets a ON s.equipment_name = a.machine_name
                WHERE a.asset_section = ? AND s.ppm_month IN ({placeholders}) AND (s.status != 'Approved' OR s.status IS NULL)
            """, [dept] + months_list).fetchone()[0] or 0
            dept_comp.append(c)
            dept_pend.append(p)

        # ----------------------------------------------------
        # SECTION B: GUEST ROOMS PPM AGGREGATIONS
        # ----------------------------------------------------
        comp_room = conn.execute(f"""
            SELECT COUNT(*) FROM room_ppm WHERE ppm_month IN ({placeholders}) AND status = 'Approved'
        """, months_list).fetchone()[0] or 0
        
        pend_room = conn.execute(f"""
            SELECT COUNT(*) FROM room_ppm WHERE ppm_month IN ({placeholders}) AND (status != 'Approved' OR status IS NULL)
        """, months_list).fetchone()[0] or 0

        # ----------------------------------------------------
        # SECTION C: MATERIAL REQUISITION EXPENSE CODES (UPDATED)
        # ----------------------------------------------------
        # Change this to match your backend table name
        REQUISITION_TABLE_NAME = "requisitions" 
        
        dept_costs = []
        
        # Check if the table exists before querying it to prevent crashes
        table_check = conn.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name=?
        """, (REQUISITION_TABLE_NAME,)).fetchone()
        
        if table_check:
            for dept in departments:
                try:
                    # Pull data assuming columns: department, total_price, and request_date
                    cost = conn.execute(f"""
                        SELECT SUM(total_price) FROM {REQUISITION_TABLE_NAME} 
                        WHERE UPPER(department) = ? AND strftime('%Y-%m', request_date) IN ({placeholders})
                    """, [dept] + months_list).fetchone()[0] or 0
                    dept_costs.append(round(cost, 2))
                except sqlite3.OperationalError:
                    # Fallback to 0 if your column names differ (e.g., if it's 'cost' instead of 'total_price')
                    dept_costs.append(0)
        else:
            print(f"⚠️ Warning: Table '{REQUISITION_TABLE_NAME}' not found. Cost charts display skipped.")
            dept_costs = [0] * len(departments)

    return render_template(
        "engineering_dashboard.html",
        time_range=time_range,
        current_month=current_date.strftime("%B %Y"),
        
        # Machinery Pack
        machinery_completed=comp_sect,
        machinery_pending=pend_sect,
        bar_labels=departments,
        machinery_dept_completed=dept_comp,
        machinery_dept_pending=dept_pend,
        
        # Rooms Pack
        room_completed=comp_room,
        room_pending=pend_room,
        
        # Finance Requisition Pack
        requisition_dept_costs=dept_costs
    )

@app.route('/delete_hlp_report/<int:record_id>', methods=['POST'])
def delete_hlp_report(record_id):
    # Retrieve and delete the record logic here
    # Example:
    # record = Record.query.get_or_404(record_id)
    # db.session.delete(record)
    # db.session.commit()
    
    return redirect(url_for('hlp_calculator'))
# =====================
# FUEL INVENTORY
# =====================
# --- 4. UPDATE FUEL DELIVERY LOGS ---
@app.route('/fuel_update', methods=['POST'])
def fuel_update():
    import datetime
    fuel_type = request.form.get('fuel_type')
    qty = request.form.get('qty')
    received_by = session.get('username', 'Technician')
    
    # Fixed datetime tracking syntax right here
    date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    db = sqlite3.connect('hlp_database.db')
    cursor = db.cursor()
    
    # Table structural safeguard
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fuel_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fuel_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            received_by TEXT,
            date TEXT
        )
    """)
    
    cursor.execute("""
        INSERT INTO fuel_logs (fuel_type, quantity, received_by, date)
        VALUES (?, ?, ?, ?)
    """, (fuel_type, qty, received_by, date_now))
    db.commit()
    db.close()
    return redirect(url_for('material_requisition'))

@app.route("/delete-fuel/<int:id>", methods=["POST"])
@login_required
def delete_fuel(id):
    with sqlite3.connect(DATABASE) as conn:
        conn.execute("DELETE FROM fuel_inventory WHERE id = ?", (id,))
    flash("Fuel record deleted.")
    return redirect(url_for('material_requisition'))

@app.route("/clear-requisitions", methods=["POST"])

@login_required

@role_required("ADMIN")

def clear_requisitions():

    with sqlite3.connect(DATABASE) as conn:

        conn.execute("DELETE FROM requisitions")

    flash("History cleared.")

    return redirect(url_for('material_requisition'))


if __name__ == '__main__':
    app.config['PROPAGATE_EXCEPTIONS'] = True
    app.run(host='127.0.0.1', port=5050, debug=True)