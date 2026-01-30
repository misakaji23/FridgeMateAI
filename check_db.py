import sqlite3
import os

db_path = 'inventory.db'

if not os.path.exists(db_path):
    print(f"Database {db_path} does not exist.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", tables)
    
    for table_name in tables:
        t = table_name[0]
        print(f"\nSchema for {t}:")
        cursor.execute(f"PRAGMA table_info({t})")
        columns = cursor.fetchall()
        for col in columns:
            print(col)

    conn.close()
