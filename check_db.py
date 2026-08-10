import sqlite3

def check():
    conn = sqlite3.connect('hlp_system.db')
    cursor = conn.cursor()
    cursor.execute("SELECT reading_date, parameter, value FROM hlp_readings LIMIT 10")
    rows = cursor.fetchall()
    
    print("\n--- DATABASE CONTENT CHECK ---")
    if not rows:
        print("THE DATABASE IS EMPTY. No readings were saved.")
    else:
        for r in rows:
            print(f"Date: {r[0]} | Name: {r[1]} | Value: {r[2]}")
    print("------------------------------\n")
    conn.close()

if __name__ == "__main__":
    check()