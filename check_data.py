import sqlite3
conn = sqlite3.connect('aquamon.db')
cursor = conn.execute("SELECT * FROM readings WHERE type='temperature' ORDER BY timestamp DESC LIMIT 5")
rows = cursor.fetchall()
if rows:
    print("SUCCESS: Found live data!")
    for row in rows:
        print(f"Time: {row[3]}, Temp: {row[2]}°C")
else:
    print("NO DATA YET: Waiting for first reading...")
conn.close()
