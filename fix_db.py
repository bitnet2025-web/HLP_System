import sqlite3

DATABASE = 'hlp_system.db'

def fix():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    print("Adding missing hlp_readings table...")
    
    # Create the table that the error says is missing
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hlp_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reading_date TEXT NOT NULL,
            section TEXT NOT NULL,
            parameter TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            value REAL,
            UNIQUE(reading_date, parameter, time_slot)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Success! The table 'hlp_readings' now exists.")

if __name__ == "__main__":
    fix()