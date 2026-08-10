# ==============================
# HLP Management System - Database Module
# ==============================
import sqlite3
import os
from datetime import datetime
from hlp_core.config import DATA_DIR, METERS, RATES

DB_PATH = os.path.join(DATA_DIR, "hlp_data.db")

# ------------------------------
# 1. DATABASE INITIALIZATION
# ------------------------------
def init_db():
    """Initialize the database and tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            meter_name TEXT NOT NULL,
            yesterday REAL DEFAULT 0,
            today REAL DEFAULT 0,
            consumption REAL DEFAULT 0,
            cost REAL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

# ------------------------------
# 2. INSERT OR UPDATE READINGS
# ------------------------------
def add_reading(meter_name, yesterday, today):
    """Add a new reading and calculate consumption and cost."""
    consumption = today - yesterday
    rate = RATES.get(meter_name, None)
    cost = round(consumption * rate, 2) if rate else None

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO readings (date, meter_name, yesterday, today, consumption, cost)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (datetime.now().strftime("%Y-%m-%d"), meter_name, yesterday, today, consumption, cost))
    conn.commit()
    conn.close()

# ------------------------------
# 3. FETCH DATA
# ------------------------------
def get_readings_by_date(date_str):
    """Fetch all meter readings for a specific date."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM readings WHERE date = ?", (date_str,))
    data = c.fetchall()
    conn.close()
    return data

def get_latest_reading(meter_name):
    """Fetch the latest reading for a given meter."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT today FROM readings
        WHERE meter_name = ?
        ORDER BY id DESC LIMIT 1
    """, (meter_name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

# ------------------------------
# 4. FETCH SUMMARY DATA
# ------------------------------
def get_summary_for_date(date_str):
    """Summarize consumption and cost per meter for a given date."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT meter_name, consumption, cost FROM readings
        WHERE date = ?
    """, (date_str,))
    summary = c.fetchall()
    conn.close()
    return summary

# ------------------------------
# 5. CLEANUP / RESET (optional)
# ------------------------------
def clear_all_data():
    """Delete all records from database (admin use only)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM readings")
    conn.commit()
    conn.close()

# Initialize database automatically when imported
init_db()
import sqlite3

DATABASE = 'hlp_system.db'

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        
        # 1. Existing Requisitions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS requisitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                requester TEXT,
                dept TEXT,
                item TEXT,
                qty TEXT,
                purpose TEXT,
                status TEXT DEFAULT 'Pending'
            )
        ''')

        # 2. NEW: HLP Master Readings Table
        # This is what allows you to search by DATE and MONTH.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hlp_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reading_date TEXT NOT NULL,   -- Format: 2026-03-02
                section TEXT NOT NULL,        -- Electrical, Plumbing, HVAC
                parameter TEXT NOT NULL,      -- e.g., 'f_kwh', 'f_rc1'
                time_slot TEXT NOT NULL,      -- e.g., '06:00', '12:00'
                value REAL,
                UNIQUE(reading_date, parameter, time_slot)
            )
        ''')
        conn.commit()
    print("Database initialized with HLP tables.")
with sqlite3.connect(DATABASE) as conn:
    # Add columns if they don't exist
    try:
        conn.execute("ALTER TABLE requisitions ADD COLUMN date_ordered TEXT")
        conn.execute("ALTER TABLE requisitions ADD COLUMN date_received TEXT")
    except:
        pass # Columns already exist
if __name__ == "__main__":
    init_db()