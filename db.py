import sqlite3

DB_Name = "bookings.db"

def init_db():
    conn = sqlite3.connect(DB_Name)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            service TEXT,
            day TEXT,
            hour INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_booking(user_id, user_name, service, day, hour):
    conn = sqlite3.connect(DB_Name)
    conn.execute(
        "INSERT INTO bookings (user_id, user_name, service, day, hour) VALUES (?, ?, ?, ?, ?)",
        (user_id, user_name, service, day, hour),
    )
    conn.commit()
    conn.close()

def get_busy_hours(day):
    conn = sqlite3.connect(DB_Name)
    rows = conn.execute("SELECT hour FROM bookings WHERE day = ?", (day,)).fetchall()
    conn.close()
    return [row[0] for row in rows]
